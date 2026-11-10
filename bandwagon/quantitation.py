"""Measure source pixels once, while detection stays in edited coordinates.

No resampled intensities or reflected/padded border pixels enter the integral.
Coordinate buffers are restricted to strips of each band's source bounding box.
"""
import numpy as np

from .imaging import reference_curve


PIXEL_OPS = {'rotate', 'flip', 'crop', 'fine_rotate', 'bow_correct',
             'reference_bow', 'shear_correct', 'warp', 'invert_colors'}


def write_quantitation_source(archive, source, geometry):
    if source is None:
        return
    import zipfile
    from PIL import Image
    with archive.open(zipfile.ZipInfo('quant_source.png'), 'w', force_zip64=True) as stream:
        Image.fromarray(source, 'L').save(stream, format='PNG')
    archive.writestr('quant_geometry.json', geometry)


class SourceQuantitation:
    def __init__(self, gray, operations, invertible_colors=True):
        self.gray = gray
        self.steps = []
        self.inverted = False
        h, w = gray.shape
        for name, p in operations:
            if name not in PIXEL_OPS:
                continue
            ow, oh = w, h
            matrix = None
            if name == 'invert_colors':
                self.inverted ^= invertible_colors
                continue
            if name == 'rotate':
                deg = p['deg'] % 360
                if deg == 90:
                    matrix = [[0, -1, h-1], [1, 0, 0], [0, 0, 1]]
                    ow, oh = h, w
                elif deg == 270:
                    matrix = [[0, 1, 0], [-1, 0, w-1], [0, 0, 1]]
                    ow, oh = h, w
                elif deg == 180:
                    matrix = [[-1, 0, w-1], [0, -1, h-1], [0, 0, 1]]
                else:
                    raise ValueError('Unsupported orthogonal rotation')
            elif name == 'fine_rotate':
                angle = np.deg2rad(p['deg']); c, s = np.cos(angle), np.sin(angle)
                cx, cy = (w-1)/2, (h-1)/2
                matrix = [[c, -s, cx-c*cx+s*cy],
                          [s, c, cy-s*cx-c*cy], [0, 0, 1]]
            elif name == 'flip':
                matrix = ([[-1, 0, w-1], [0, 1, 0], [0, 0, 1]] if p['dir'] == 'h'
                          else [[1, 0, 0], [0, -1, h-1], [0, 0, 1]])
            elif name == 'crop':
                l, t, r, b = p['box']; ow, oh = r-l, b-t
                matrix = [[1, 0, -l], [0, 1, -t], [0, 0, 1]]
            elif name == 'warp':
                import cv2
                src = np.asarray(p['corners'], dtype=np.float32)
                tl, tr, br, bl = src
                ow = max(round(max(np.linalg.norm(tr-tl), np.linalg.norm(br-bl))), 10)
                oh = max(round(max(np.linalg.norm(bl-tl), np.linalg.norm(br-tr))), 10)
                dst = np.float32([[0, 0], [ow-1, 0], [ow-1, oh-1], [0, oh-1]])
                matrix = cv2.getPerspectiveTransform(src, dst)
            if matrix is not None:
                matrix = np.asarray(matrix, dtype=float)
                inverse = np.linalg.inv(matrix)
            else:
                inverse = None
            self.steps.append((name, p, w, h, ow, oh, matrix, inverse))
            w, h = ow, oh
        self.size = w, h

    @staticmethod
    def _matrix(x, y, m):
        den = m[2, 0]*x + m[2, 1]*y + m[2, 2]
        with np.errstate(divide='ignore', invalid='ignore'):
            return ((m[0, 0]*x + m[0, 1]*y + m[0, 2])/den,
                    (m[1, 0]*x + m[1, 1]*y + m[1, 2])/den)

    @staticmethod
    def _nonlinear(x, y, step, reverse):
        name, p, w, h = step[:4]
        if name in ('bow_correct', 'reference_bow'):
            if name == 'bow_correct':
                shift = float(p['amount'])*((x-w/2)/(w/2))**2
            else:
                curve = reference_curve(p['points'], x)
                baseline = p.get('baseline')
                shift = (np.mean(np.asarray(p['points'])[:, 1])-curve if baseline is None
                         else curve-baseline)
            return x, y-shift if reverse else y+shift
        if name != 'shear_correct':
            raise ValueError('Unknown geometry operation: '+name)
        amount, vertical, taper = p['amount'], p.get('vertical', 0), p.get('trapezoid', 0)
        a = 1-max(float(taper), 0)/100
        b = 1+min(float(taper), 0)/100
        if reverse:
            if taper:
                yy = y/max(h-1, 1)
                yy = a*yy/(b+(a-b)*yy)
                x = (w-1)/2+(x-(w-1)/2)*(a+(b-a)*yy)
                y = yy*max(h-1, 1)
            y = y-float(vertical)*((x-w/2)/max(w-1, 1))
            x = x-float(amount)*((y-h/2)/max(h-1, 1))
        else:
            x = x+float(amount)*((y-h/2)/max(h-1, 1))
            y = y+float(vertical)*((x-w/2)/max(w-1, 1))
            if taper:
                yy = y/max(h-1, 1)
                x = (w-1)/2+(x-(w-1)/2)/(a+(b-a)*yy)
                y = b*yy/(a-(a-b)*yy)*max(h-1, 1)
        return x, y

    def map(self, x, y, reverse=False):
        x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
        valid = np.isfinite(x) & np.isfinite(y)
        for step in (reversed(self.steps) if reverse else self.steps):
            name, p, w, h, ow, oh, matrix, inverse = step
            if matrix is None:
                x, y = self._nonlinear(x, y, step, reverse)
            else:
                x, y = self._matrix(x, y, inverse if reverse else matrix)
            vw, vh = (w, h) if reverse else (ow, oh)
            valid &= np.isfinite(x) & np.isfinite(y)
            valid &= (x >= -.5) & (x < vw-.5) & (y >= -.5) & (y < vh-.5)
        return x, y, valid

    def measure(self, x1, x2, top, bottom):
        """Return (width-normalized integral, source-pixel volume).

        Background is the line joining original intensities at the two detected
        band edges. Empty rows caused by enlargement are interpolated only for
        background estimation; they contribute no signal/area.
        """
        if bottom <= top:
            return 0., 0.
        # Sample the entire outline: curved edges need more than four corners.
        xx = np.linspace(x1-.5, x2+.5, max(2, x2-x1+2))
        yy = np.linspace(top-.5, bottom+.5, max(2, bottom-top+2))
        px = np.concatenate((xx, xx, np.full_like(yy, x1-.5), np.full_like(yy, x2+.5)))
        py = np.concatenate((np.full_like(xx, top-.5), np.full_like(xx, bottom+.5), yy, yy))
        sx, sy, _ = self.map(px, py, reverse=True)
        finite = np.isfinite(sx) & np.isfinite(sy)
        if not finite.any():
            return 0., 0.
        h, w = self.gray.shape
        left = max(0, int(np.floor(sx[finite].min()))-2)
        right = min(w, int(np.ceil(sx[finite].max()))+3)
        first = max(0, int(np.floor(sy[finite].min()))-2)
        last = min(h, int(np.ceil(sy[finite].max()))+3)
        n = bottom-top+1
        sums, counts = np.zeros(n), np.zeros(n)
        for start in range(first, last, 64):
            end = min(start+64, last)
            ox, oy = np.meshgrid(np.arange(left, right), np.arange(start, end))
            dx, dy, valid = self.map(ox, oy)
            valid &= (dx >= x1-.5) & (dx < x2+.5) & (dy >= top-.5) & (dy < bottom+.5)
            if not valid.any():
                continue
            bins = np.clip(np.floor(dy[valid]-top+.5).astype(int), 0, n-1)
            pixels = self.gray[start:end, left:right][valid].astype(float)
            signal = pixels if self.inverted else 255-pixels
            sums += np.bincount(bins, weights=signal, minlength=n)
            counts += np.bincount(bins, minlength=n)
        populated = counts > 0
        if not populated.any():
            return 0., 0.
        rows = np.arange(n)
        means = np.interp(rows, rows[populated], sums[populated]/counts[populated])
        background = np.linspace(means[0], means[-1], n)
        volume = float(np.maximum(means-background, 0).dot(counts))
        # Original transverse length, not the stretched display width.
        tx, ty, _ = self.map(xx, np.full_like(xx, (top+bottom)/2), reverse=True)
        width = float(np.hypot(np.diff(tx), np.diff(ty)).sum())
        return volume/max(width, 1e-9), volume

    def apply(self, lanes):
        for lane in lanes:
            if lane.peak_bounds is None:
                continue
            values = [self.measure(lane.x1, lane.x2, int(t), int(b)) for t, b in lane.peak_bounds]
            lane.peak_area = np.array([v[0] for v in values])
            lane.peak_volume = np.array([v[1] for v in values])
