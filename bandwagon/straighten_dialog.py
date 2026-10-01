"""Fit a visible band with draggable reference points before straightening."""
import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt, QPointF, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QPainterPath, QPen, QColor
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialogButtonBox

from .widgets import GelView
from .dialogs import _dialog_style, _no_help_button
from .imaging import reference_curve, apply_reference_curve, pil_to_pixmap
from .i18n import tr


class ReferenceView(GelView):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.points = []
        self.drag_index = None

    def reset_reference(self, y=None):
        w, h = self._img_size
        y = h / 2 if y is None else y
        self.points = [(float(x), float(y)) for x in np.linspace(0, w - 1, 5)]
        self.update()
        self.changed.emit()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        for i, (x, y) in enumerate(self.points):
            if (self._ix_to_wx(x) - event.x()) ** 2 + (self._iy_to_wy(y) - event.y()) ** 2 <= 144:
                self.drag_index = i
                return
        _, y = self._wpos_to_img(event.x(), event.y())
        self.reset_reference(y)

    def mouseMoveEvent(self, event):
        if self.drag_index is None:
            return super().mouseMoveEvent(event)
        i = self.drag_index
        x, y = self._wpos_to_img(event.x(), event.y())
        if i in (0, len(self.points) - 1):
            x = self.points[i][0]
        else:
            gap = min(1, (self.points[i + 1][0] - self.points[i - 1][0]) / 4)
            x = float(np.clip(x, self.points[i - 1][0] + gap, self.points[i + 1][0] - gap))
        self.points[i] = (x, y)
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, event):
        if self.drag_index is not None and event.button() == Qt.LeftButton:
            self.mouseMoveEvent(event)
            self.drag_index = None
            self.changed.emit()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.points:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        target = float(np.mean(np.asarray(self.points)[:, 1]))
        w, _ = self._img_size
        painter.setPen(QPen(QColor("#f5d55b"), 1, Qt.DashLine))
        painter.drawLine(QPointF(self._ix_to_wx(0), self._iy_to_wy(target)),
                         QPointF(self._ix_to_wx(w - 1), self._iy_to_wy(target)))
        xs = np.linspace(0, w - 1, min(w, 600))
        ys = reference_curve(self.points, xs)
        path = QPainterPath()
        for i, (x, y) in enumerate(zip(xs, ys)):
            point = QPointF(self._ix_to_wx(x), self._iy_to_wy(y))
            path.moveTo(point) if i == 0 else path.lineTo(point)
        painter.setPen(QPen(QColor("#ff746d"), 2))
        painter.drawPath(path)
        painter.setBrush(QColor("#ffffff"))
        for x, y in self.points:
            painter.drawEllipse(QPointF(self._ix_to_wx(x), self._iy_to_wy(y)), 6, 6)


class StraightenDialog(QDialog):
    def __init__(self, source, parent=None):
        super().__init__(parent)
        _no_help_button(self)
        self.setWindowTitle(tr("reference_bow_title"))
        self.setStyleSheet(_dialog_style())
        self.resize(900, 680)
        self.source_size = source.size
        ratio = min(1, 1000 / max(source.size))
        self.small = source.resize((max(2, round(source.width * ratio)),
                                    max(2, round(source.height * ratio))), Image.Resampling.BILINEAR)
        layout = QVBoxLayout(self)
        hint = QLabel(tr("reference_bow_hint")); hint.setWordWrap(True); layout.addWidget(hint)
        self.view = ReferenceView(); self.view.set_image(pil_to_pixmap(self.small), self.small.size)
        self.view.reset_reference()
        layout.addWidget(self.view, 1)
        self.showing_original = False
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(33)
        self.preview_timer.timeout.connect(self.update_preview)
        self.view.changed.connect(self.schedule_preview)
        self.finished.connect(self.preview_timer.stop)
        self.update_preview()
        row = QHBoxLayout()
        reset = QPushButton(tr("reference_reset")); reset.clicked.connect(self.reset_reference); row.addWidget(reset)
        original = QPushButton(tr("reference_hold_original"))
        original.pressed.connect(lambda: self.show_original(True))
        original.released.connect(lambda: self.show_original(False))
        row.addWidget(original)
        row.addStretch()
        layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(tr("reference_apply"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("btn_cancel"))
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def schedule_preview(self):
        # Coalesce mouse events without postponing updates until dragging ends.
        if not self.preview_timer.isActive():
            self.preview_timer.start()

    def update_preview(self):
        self.preview_timer.stop()
        image = self.small if self.showing_original else apply_reference_curve(self.small, self.view.points)
        self.view.set_image(pil_to_pixmap(image), self.small.size)

    def show_original(self, on):
        self.showing_original = on
        self.update_preview()

    def reset_reference(self):
        self.view.reset_reference()

    def source_points(self):
        sx = (self.source_size[0] - 1) / (self.small.width - 1)
        sy = (self.source_size[1] - 1) / (self.small.height - 1)
        return [[x * sx, y * sy] for x, y in self.view.points]
