"""Direct curve handles and a compact command bar on the main image."""
import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt, QEvent, QTimer, QPointF, QSize, QRectF
from PyQt5.QtGui import QPainter, QPainterPath, QPen, QColor, QPixmap, QIcon
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QToolButton, QToolTip
from .imaging import apply_reference_curve, reference_curve, pil_to_pixmap
from .i18n import tr


def command_icon(name):
    pm = QPixmap(24, 24); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor('#e8edf2'), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    path = QPainterPath()
    if name == 'apply':
        path.moveTo(5, 12); path.lineTo(10, 17); path.lineTo(19, 6)
    elif name == 'cancel':
        path.moveTo(6, 6); path.lineTo(18, 18); path.moveTo(18, 6); path.lineTo(6, 18)
    elif name == 'reset':
        p.drawArc(5, 5, 15, 15, 40 * 16, 290 * 16)
        path.moveTo(4, 4); path.lineTo(4, 10); path.lineTo(10, 10)
    elif name == 'original':
        path.moveTo(2, 12); path.quadTo(12, 0, 22, 12); path.quadTo(12, 24, 2, 12)
        p.drawEllipse(9, 9, 6, 6)
    elif name == 'fit':
        for x, y, dx, dy in ((4, 4, 1, 1), (20, 4, -1, 1), (4, 20, 1, -1), (20, 20, -1, -1)):
            path.moveTo(x, y + 5 * dy); path.lineTo(x, y); path.lineTo(x + 5 * dx, y)
    else:
        p.drawEllipse(3, 3, 18, 18); p.drawLine(12, 10, 12, 17); p.drawPoint(12, 7)
    p.drawPath(path); p.end()
    return QIcon(pm)


class CurveOverlay(QWidget):
    def __init__(self, owner):
        super().__init__(owner.gel)
        self.owner = owner
        self.gel = owner.gel
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(self.gel.rect())

    def paintEvent(self, event):
        c = self.owner
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor('#c58aff'), 2))
        xs = np.linspace(0, c.width - 1, min(c.width, 600))
        ys = reference_curve(c.points, xs)
        path = QPainterPath()
        for i, (x, y) in enumerate(zip(xs, ys)):
            pt = QPointF(self.gel._ix_to_wx(x), self.gel._iy_to_wy(y))
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        p.drawPath(path)
        p.setBrush(QColor('#30203f'))
        for x, y in c.points:
            p.drawEllipse(QPointF(self.gel._ix_to_wx(x), self.gel._iy_to_wy(y)), 6, 6)
        # A separate, small left-side grip translates the whole curve.
        grip = c.line_grip()
        p.setBrush(QColor('#30203f'))
        p.drawRoundedRect(QRectF(grip.x() - 7, grip.y() - 13, 14, 26), 4, 4)
        p.drawLine(QPointF(grip.x(), grip.y() - 7), QPointF(grip.x(), grip.y() + 7))
        for sign in (-1, 1):
            y = grip.y() + sign * 7
            p.drawLine(QPointF(grip.x(), y), QPointF(grip.x() - 3, y - sign * 3))
            p.drawLine(QPointF(grip.x(), y), QPointF(grip.x() + 3, y - sign * 3))


class InlineCurve(QWidget):
    def __init__(self, window):
        super().__init__(window.gel)
        self.window = window; self.gel = window.gel
        self.width, self.height = window._orig.size
        self.baseline = (self.height - 1) / 2
        self.points = [(float(x), self.baseline) for x in np.linspace(0, self.width - 1, 5)]
        self.drag = None; self.original = False
        self.group_start = None
        self.previous_overlay = self.gel.show_overlay
        self.gel.show_overlay = False
        source = window._apply_color_pipeline(window._orig)
        ratio = min(1, 1000 / max(source.size))
        self.small = source.resize((max(2, round(source.width * ratio)),
                                    max(2, round(source.height * ratio))), Image.Resampling.BILINEAR)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(33)
        self.timer.timeout.connect(self.preview)
        self.overlay = CurveOverlay(self); self.overlay.show()
        self.setStyleSheet('QWidget{background:#202a35;border-radius:8px;} QToolButton{color:#e8edf2;border:0;padding:7px;border-radius:5px;} QToolButton:hover{background:#3b4655;} QToolButton:pressed{background:#56406d;}')
        row = QHBoxLayout(self); row.setContentsMargins(5, 4, 5, 4)
        for name, label, action in (
            ('reset', 'reference_reset', self.reset), ('original', 'reference_hold_original', None),
            ('fit', 'curve_fit', lambda: self.gel.set_zoom(1)),
            ('help', 'curve_inline_hint', None), ('apply', 'reference_apply', self.apply),
            ('cancel', 'btn_cancel', self.cancel)):
            b = QToolButton(); b.setIcon(command_icon(name)); b.setIconSize(QSize(24, 24))
            b.setToolTip(tr(label)); b.setAccessibleName(tr(label))
            if name in ('apply', 'cancel'):
                b.setText(tr(label)); b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            if action: b.clicked.connect(action)
            if name == 'original':
                b.pressed.connect(lambda: self.show_original(True))
                b.released.connect(lambda: self.show_original(False))
            if name == 'help':
                b.clicked.connect(lambda checked=False, button=b:
                                  QToolTip.showText(button.mapToGlobal(button.rect().topLeft()),
                                                    tr('curve_inline_hint'), button))
            row.addWidget(b)
        self.adjustSize(); self.place(); self.show(); self.raise_()
        self.gel.installEventFilter(self)
        self.previous_undo = window.btn_undo.isEnabled()
        window.btn_undo.setEnabled(True)
        window.correction_tabs.setEnabled(False)

    def place(self):
        self.move(max(0, (self.gel.width() - self.sizeHint().width()) // 2), max(0, self.gel.height() - self.sizeHint().height() - 8))
        self.overlay.setGeometry(self.gel.rect())

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Resize: self.place()
        if kind in (QEvent.Paint, QEvent.Wheel): self.overlay.update()
        if kind == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            grip = self.line_grip()
            if abs(event.x() - grip.x()) <= 10 and abs(event.y() - grip.y()) <= 16:
                self.drag = 'all'
                self.group_start = (event.y(), list(self.points))
                return True
            for i, (x, y) in enumerate(self.points):
                if (self.gel._ix_to_wx(x) - event.x()) ** 2 + (self.gel._iy_to_wy(y) - event.y()) ** 2 <= 144:
                    self.drag = i; return True
            return True
        if kind == QEvent.MouseMove and self.drag is not None:
            self.move_point(event); return True
        if kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self.drag is not None: self.move_point(event)
            self.drag = None; self.group_start = None; return True
        if kind == QEvent.ToolTip:
            grip = self.line_grip()
            if abs(event.x() - grip.x()) <= 10 and abs(event.y() - grip.y()) <= 16:
                QToolTip.showText(event.globalPos(), tr('curve_move_line'), self.gel)
                return True
        return False

    def line_grip(self):
        y = self.gel._iy_to_wy(float(np.mean(np.asarray(self.points)[:, 1])))
        return QPointF(14, float(np.clip(y, 17, max(17, self.gel.height() - 17))))

    def move_point(self, event):
        i = self.drag
        if i == 'all':
            start_y, points = self.group_start
            delta = (event.y() - start_y) * self.height / max(1, self.gel._rect.height())
            delta = float(np.clip(delta, -min(y for _, y in points),
                                  self.height - 1 - max(y for _, y in points)))
            self.points = [(x, y + delta) for x, y in points]
        else:
            x, y = self.gel._wpos_to_img(event.x(), event.y())
            x = self.points[i][0] if i in (0, 4) else float(np.clip(x, self.points[i-1][0] + .01, self.points[i+1][0] - .01))
            self.points[i] = (x, y)
        self.overlay.update()
        if not self.timer.isActive(): self.timer.start()

    def preview(self):
        self.timer.stop()
        sx = (self.small.width - 1) / (self.width - 1)
        sy = (self.small.height - 1) / (self.height - 1)
        points = [(x * sx, y * sy) for x, y in self.points]
        out = self.small if self.original else apply_reference_curve(self.small, points, self.baseline * sy)
        self.gel.set_image(pil_to_pixmap(out), (self.width, self.height))

    def show_original(self, on):
        self.original = on; self.preview()

    def reset(self):
        self.points = [(float(x), self.baseline) for x in np.linspace(0, self.width - 1, 5)]
        self.preview(); self.overlay.update()

    def finish(self):
        self.timer.stop(); self.gel.removeEventFilter(self)
        self.window._inline_curve = None
        self.window.correction_tabs.setEnabled(True)
        self.window.btn_undo.setEnabled(self.previous_undo)
        self.gel.show_overlay = self.previous_overlay
        self.small = None
        self.overlay.hide(); self.overlay.deleteLater()
        self.hide(); self.deleteLater()

    def cancel(self):
        self.finish(); self.window._refresh_display()

    def apply(self):
        params = {'points': [list(p) for p in self.points], 'baseline': self.baseline}
        changed = any(abs(y - self.baseline) > 1e-6 for _, y in self.points)
        self.finish()
        if changed: self.window._record_op('reference_bow', params)
        self.window._after_geometry_change()
