"""Recover an interrupted edit without copying full-resolution image buffers."""
from functools import wraps
from PyQt5.QtCore import QSignalBlocker
from PyQt5.QtWidgets import QAbstractSlider, QSpinBox
from .i18n import tr
from .models import CurveModel


def memory_safe_edit(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        if getattr(self, "_memory_edit_active", False):
            return method(self, *args, **kwargs)
        state = None
        self._memory_edit_active = True
        try:
            # All image operations replace buffers rather than modifying originals.
            # Keep references, not image copies; copy only small mutable containers.
            candidate = {key: (value.copy() if isinstance(value, (list, dict)) else value)
                     for key, value in self.__dict__.items()}
            candidate["curves"] = {key: CurveModel.from_dict(value.to_dict())
                                   for key, value in self.curves.items()}
            gel_state = self.gel.__dict__.copy()
            gel_state["corners"] = list(self.gel.corners)
            controls = [(w, w.value()) for w in self.findChildren(QAbstractSlider)]
            controls += [(w, w.value()) for w in self.findChildren(QSpinBox)]
            widgets = [(w, w.__dict__.copy()) for w in
                       (self.curve, self.profile, self.std_view, self.channel_bar)]
            memo = self.memo_edit.toPlainText()
            style = self.combo_band_style.currentIndex()
            state = candidate
            return method(self, *args, **kwargs)
        except Exception as error:
            # OpenCV reports allocation failures as cv2.error (StsNoMem = -4).
            if not isinstance(error, MemoryError) and not (
                    type(error).__module__ == "cv2" and getattr(error, "code", None) == -4):
                raise
            error.__traceback__ = None  # release temporary arrays before restoring
            if state is not None:
                self.__dict__.update(state)
                self.gel.__dict__.update(gel_state)
                for widget, attributes in widgets:
                    widget.__dict__.update(attributes)
                    widget.update()
                self.curve.model = self.curves[self._ch]
                for widget, value in controls:
                    blocker = QSignalBlocker(widget)
                    widget.setValue(value)
                    del blocker
                self.sl_bright.val.setText(str(self.sl_bright.value()))
                self.sl_contrast.val.setText(str(self.sl_contrast.value()))
                for widget, setter, value in (
                        (self.memo_edit, self.memo_edit.setPlainText, memo),
                        (self.combo_band_style, self.combo_band_style.setCurrentIndex, style)):
                    blocker = QSignalBlocker(widget)
                    setter(value)
                    del blocker
                self.gel.update()
                self.profile.set_lanes(self.lanes)
                self._rebuild_lane_table()
                self._refresh_results()
                self.btn_undo.setEnabled(self._edit_pos >= 0)
                self.btn_redo.setEnabled(self._edit_pos < len(self._edit_ops) - 1)
            self.status.showMessage(tr("memory_edit_failed"), 15000)
            return False
        finally:
            self._memory_edit_active = False
    return guarded
