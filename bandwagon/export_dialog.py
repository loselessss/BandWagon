"""One export dialog shared by clipboard and image files."""
import copy
import json

from PIL import Image
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .dialogs import _dialog_style, _no_help_button
from .checkbox import TickCheckBox as QCheckBox
from .i18n import tr
from .imaging import pil_to_pixmap, render_analysis_overlay


DEFAULT_OPTIONS = dict(photo=True, border=True, bands=False, marker_mw=True, lane_mw=False, annotation=True,
                       text_transparency=0, graphic_transparency=0, linked=True)


def render_export(source, lanes, options, font_scale=1.0, band_style='area'):
    """The preview and final export use the same rendering path."""
    return render_analysis_overlay(
        source, lanes, transparent_bg=not options["photo"], band_style=band_style,
        show_border=options["border"], show_marker_mw=options["marker_mw"],
        show_annotation=options["annotation"], show_bands=options.get('bands', False), mw_marker_only=False,
        show_lane_mw=options.get('lane_mw', False),
        text_opacity=100 - options["text_transparency"],
        graphic_opacity=100 - options["graphic_transparency"],
        image_opacity=100 - options["graphic_transparency"], font_scale=font_scale)


class ExportPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 220)
        self.pixmap = None

    def paintEvent(self, event):
        painter = QPainter(self)
        for y in range(0, self.height(), 16):
            for x in range(0, self.width(), 16):
                painter.fillRect(x, y, 16, 16,
                                 QColor("#b8bec4" if (x // 16 + y // 16) % 2 else "#e0e4e8"))
        if self.pixmap is not None:
            size = self.pixmap.size().scaled(self.size(), Qt.KeepAspectRatio)
            target = QRectF((self.width() - size.width()) / 2,
                            (self.height() - size.height()) / 2, size.width(), size.height())
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            painter.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))


class ExportDialog(QDialog):
    def __init__(self, source, lanes, settings, parent=None, saving=False, band_style=None):
        super().__init__(parent)
        _no_help_button(self)
        self.setWindowTitle(tr("export_options_title"))
        self.setStyleSheet(_dialog_style())
        self.resize(720, 520)
        self.settings = settings
        self._source = source
        self._lanes = lanes
        self.band_style = band_style or getattr(parent, '_band_display_style', 'area')
        saved = dict(DEFAULT_OPTIONS)
        try:
            values = json.loads(settings.value("export/options", "{}"))
            for key, default in saved.items():
                value = values.get(key, default)
                saved[key] = (value if isinstance(value, bool) else default) if isinstance(default, bool) \
                    else max(0, min(100, int(value)))
        except (ValueError, TypeError, AttributeError):
            pass
        if saved["linked"]:
            saved["graphic_transparency"] = saved["text_transparency"]
        root = QVBoxLayout(self)
        columns = QHBoxLayout()
        controls = QVBoxLayout()
        self.select_all = QPushButton(tr("export_select_all"))
        self.select_all.clicked.connect(self._select_all)
        controls.addWidget(self.select_all)
        self.checks = {}
        for key, label in (("photo", "export_include_photo"), ("border", "export_component_border"),
                           ("bands", "export_component_bands"),
                           ("marker_mw", "export_component_marker_mw"),
                           ("lane_mw", "export_component_lane_mw"),
                           ("annotation", "export_component_annotation")):
            check = QCheckBox(tr(label)); check.setChecked(saved[key])
            check.setStyleSheet(parent._checkbox_css() if parent else "")
            controls.addWidget(check); self.checks[key] = check
        hint = QLabel(tr("export_elements_hint")); hint.setWordWrap(True)
        controls.addWidget(hint)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        self.text_alpha = QSpinBox(); self.graphic_alpha = QSpinBox()
        for spin, key in ((self.text_alpha, "text_transparency"),
                          (self.graphic_alpha, "graphic_transparency")):
            spin.setRange(0, 100); spin.setSuffix(" %"); spin.setValue(saved[key])
        form.addRow(tr("export_text_transparency"), self.text_alpha)
        form.addRow(tr("export_graphic_transparency"), self.graphic_alpha)
        controls.addLayout(form)
        self.linked = QCheckBox(tr("export_link_transparency"))
        self.linked.setStyleSheet(parent._checkbox_css() if parent else "")
        self.linked.setChecked(saved["linked"])
        controls.addWidget(self.linked)
        transparency_hint = QLabel(tr("export_transparency_hint")); transparency_hint.setWordWrap(True)
        controls.addWidget(transparency_hint)
        controls.addStretch()
        columns.addLayout(controls, 1)
        self.preview = ExportPreview(); columns.addWidget(self.preview, 2)
        root.addLayout(columns, 1)
        self.summary = QLabel(); self.summary.setWordWrap(True); root.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.submit = buttons.button(QDialogButtonBox.Ok)
        self.submit.setText(tr("export_save_action" if saving else "export_copy_action"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("btn_cancel"))
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(80)
        self.timer.timeout.connect(self.refresh_preview)
        for check in self.checks.values():
            check.toggled.connect(self.schedule_preview)
        self.text_alpha.valueChanged.connect(lambda value: self._alpha_changed(self.graphic_alpha, value))
        self.graphic_alpha.valueChanged.connect(lambda value: self._alpha_changed(self.text_alpha, value))
        self.linked.toggled.connect(self._link_changed)
        # Cache a bounded preview source; sliders never render the full camera image.
        self.preview_source = source.copy() if max(source.size) <= 900 else source.resize(
            (max(1, round(source.width * 900 / max(source.size))),
             max(1, round(source.height * 900 / max(source.size)))), Image.Resampling.BILINEAR)
        self.preview_scale = self.preview_source.width / source.width
        self.preview_lanes = []
        for lane in lanes:
            item = copy.copy(lane)
            item.x1 = round(lane.x1 * self.preview_scale); item.x2 = round(lane.x2 * self.preview_scale)
            item.peaks = None if lane.peaks is None else [round(y * self.preview_scale) for y in lane.peaks]
            item.peak_bounds = None if not lane.peak_bounds else [
                (round(a * self.preview_scale), round(b * self.preview_scale)) for a, b in lane.peak_bounds]
            self.preview_lanes.append(item)
        self.refresh_preview()

    def options(self):
        return {**{key: check.isChecked() for key, check in self.checks.items()},
                "text_transparency": self.text_alpha.value(),
                "graphic_transparency": self.graphic_alpha.value(), "linked": self.linked.isChecked()}

    def _select_all(self):
        for check in self.checks.values():
            check.setChecked(True)
        self.schedule_preview()

    def _alpha_changed(self, other, value):
        if self.linked.isChecked():
            other.blockSignals(True); other.setValue(value); other.blockSignals(False)
        self.schedule_preview()

    def _link_changed(self, checked):
        if checked:
            self._alpha_changed(self.graphic_alpha, self.text_alpha.value())

    def schedule_preview(self, *_):
        self.timer.start()

    def refresh_preview(self):
        options = self.options()
        rendered = render_export(self.preview_source, self.preview_lanes, options,
                                 self.preview_scale, self.band_style)
        self.preview.pixmap = pil_to_pixmap(rendered)
        self.preview.update()
        visible = rendered.getchannel("A").getbbox() is not None
        self.submit.setEnabled(visible)
        self.summary.setText(tr("export_preview_hint") if visible else tr("export_empty_hint"))

    def accept(self):
        self.timer.stop()
        self.refresh_preview()
        if not self.submit.isEnabled():
            return
        self.settings.setValue("export/options", json.dumps(self.options()))
        self.settings.sync()
        super().accept()
