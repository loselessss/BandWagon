"""Rectangular crop interaction, in original image coordinates."""
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainterPath, QPen


class CropToolMixin:
    def reset_crop(self):
        self.crop_rect = (0., 0., float(self._img_size[0]), float(self._img_size[1])) if self._pm is not None else None
        self._crop_drag = None
        self._crop_fresh = True
        self.cropChanged.emit(self.crop_rect)
        self.update()

    def cancel_crop(self):
        self.crop_rect = None
        self._crop_drag = None
        self.cropChanged.emit(None)
        self.update()

    def _crop_handle_points(self):
        if self.crop_rect is None:
            return {}
        left, top, right, bottom = self.crop_rect
        x1, x2 = self._ix_to_wx(left), self._ix_to_wx(right)
        y1, y2 = self._iy_to_wy(top), self._iy_to_wy(bottom)
        return {'nw': (x1, y1), 'ne': (x2, y1), 'se': (x2, y2), 'sw': (x1, y2),
                'n': ((x1 + x2) / 2, y1), 'e': (x2, (y1 + y2) / 2),
                's': ((x1 + x2) / 2, y2), 'w': (x1, (y1 + y2) / 2)}

    def _crop_hit(self, wx, wy):
        for handle, (x, y) in self._crop_handle_points().items():
            if abs(x - wx) <= 9 and abs(y - wy) <= 9:
                return handle
        if self.crop_rect is not None:
            x, y = self._wpos_to_img(wx, wy)
            left, top, right, bottom = self.crop_rect
            if left < x < right and top < y < bottom and not self._crop_fresh:
                return 'move'
        return 'new'

    def _crop_press(self, event):
        if self.crop_rect is None:
            self.reset_crop()
        handle = self._crop_hit(event.x(), event.y())
        if handle == 'new' and not self._rect.contains(event.pos()):
            return
        self._crop_drag = (handle, self._wpos_to_img(event.x(), event.y()), self.crop_rect)

    def _crop_move(self, event):
        if self._crop_drag is None:
            handle = self._crop_hit(event.x(), event.y())
            cursors = {'nw': Qt.SizeFDiagCursor, 'se': Qt.SizeFDiagCursor,
                       'ne': Qt.SizeBDiagCursor, 'sw': Qt.SizeBDiagCursor,
                       'n': Qt.SizeVerCursor, 's': Qt.SizeVerCursor,
                       'e': Qt.SizeHorCursor, 'w': Qt.SizeHorCursor, 'move': Qt.SizeAllCursor}
            self.setCursor(cursors.get(handle, Qt.CrossCursor))
            return
        handle, (start_x, start_y), original = self._crop_drag
        x, y = self._wpos_to_img(event.x(), event.y())
        width, height = self._img_size
        x, y = max(0., min(width, x)), max(0., min(height, y))
        left, top, right, bottom = original
        if handle == 'new':
            left, right = sorted((max(0., min(width, start_x)), x))
            top, bottom = sorted((max(0., min(height, start_y)), y))
        elif handle == 'move':
            dx = max(-left, min(width - right, x - start_x))
            dy = max(-top, min(height - bottom, y - start_y))
            left, right, top, bottom = left + dx, right + dx, top + dy, bottom + dy
        else:
            min_w, min_h = min(2., width), min(2., height)
            if 'w' in handle:
                left = min(x, right - min_w)
            if 'e' in handle:
                right = max(x, left + min_w)
            if 'n' in handle:
                top = min(y, bottom - min_h)
            if 's' in handle:
                bottom = max(y, top + min_h)
        self.crop_rect = (left, top, right, bottom)
        self.cropChanged.emit(self.crop_rect)
        self.update()

    def _crop_release(self, event):
        if self._crop_drag is None:
            return
        self._crop_move(event)
        _, _, original = self._crop_drag
        left, top, right, bottom = self.crop_rect
        if right - left < min(2, self._img_size[0]) or bottom - top < min(2, self._img_size[1]):
            self.crop_rect = original
        else:
            self._crop_fresh = False
        self._crop_drag = None
        self.cropChanged.emit(self.crop_rect)
        self.update()

    def _draw_crop_overlay(self, painter):
        if self.crop_rect is None:
            return
        left, top, right, bottom = self.crop_rect
        x1, x2 = self._ix_to_wx(left), self._ix_to_wx(right)
        y1, y2 = self._iy_to_wy(top), self._iy_to_wy(bottom)
        box = QRectF(x1, y1, x2 - x1, y2 - y1)
        painter.save()
        painter.setClipRect(self._rect)
        shade = QPainterPath()
        shade.setFillRule(Qt.OddEvenFill)
        shade.addRect(QRectF(self._rect)); shade.addRect(box)
        painter.fillPath(shade, QColor(0, 0, 0, 155))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 95), 1))
        for fraction in (1 / 3, 2 / 3):
            x, y = x1 + box.width() * fraction, y1 + box.height() * fraction
            painter.drawLine(QPointF(x, y1), QPointF(x, y2))
            painter.drawLine(QPointF(x1, y), QPointF(x2, y))
        painter.setPen(QPen(QColor('white'), 1.5))
        painter.drawRect(box)
        painter.setPen(QPen(QColor('#202020'), 1))
        painter.setBrush(QColor('white'))
        for x, y in self._crop_handle_points().values():
            painter.drawRect(QRectF(x - 3.5, y - 3.5, 7, 7))
        painter.restore()
