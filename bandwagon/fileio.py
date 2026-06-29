"""bandwagon.fileio

FileIOMixin — 이미지 열기/붙여넣기/저장, 프로젝트(.bandwagon) 저장·불러오기,
CSV 내보내기, 세션 초기화/전체 초기화. Analyzer(FileIOMixin, ...)로
섞여 들어간다.

이 믹스인은 거의 모든 다른 기능의 상태를 두루 읽고 쓴다(레인은
LanesMixin, 밝기/대비/커브는 GeometryMixin, 합성은 WesternMixin 소유) —
'새 이미지로 세션을 다시 시작'하는 지점이 본질적으로 모든 기능의 상태를
한 번에 정리해야 하는 자리이기 때문이다."""
import csv
import io
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageGrab
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

from .i18n import tr
from .theme import *
from .meta import APP_NAME, APP_VERSION, GELPROJ_FORMAT_VERSION
from .imaging import pil_to_pixmap, render_analysis_overlay
from .models import CurveModel, Lane
from .dialogs import _dialog_style


class FileIOMixin:

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("dlg_open_image_title"), self._last_dir,
                                              "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)")
        if path:
            self._last_dir = str(Path(path).parent)
            self.load_image(path)

    def _read_clipboard_image(self):
        """클립보드에서 이미지를 읽어 PIL Image로 반환한다(없으면 None).
        paste_image()와 WB 탭의 썸네일 붙여넣기가 공유하는 헬퍼."""
        try:
            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                return img.convert("RGB")
        except Exception:
            pass
        qi = QApplication.clipboard().image()
        if not qi.isNull():
            buf = qi.convertToFormat(QImage.Format_ARGB32)
            w, h = buf.width(), buf.height()
            ptr = buf.bits(); ptr.setsize(h * w * 4)
            arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 4))
            rgb = np.stack([arr[:, :, 2], arr[:, :, 1], arr[:, :, 0]], axis=2)
            return Image.fromarray(rgb, "RGB")
        return None

    def paste_image(self):
        img = self._read_clipboard_image()
        if img is not None:
            self._orig = img; self._after_load(tr("clipboard_source_name")); return
        self.status.showMessage(tr("clipboard_empty_msg"))

    def load_image(self, path):
        try:
            self._orig = Image.open(path).convert("RGB")
            self._after_load(Path(path).name)
        except Exception as ex:
            self._warn(tr("open_failed_title"), str(ex))

    def _reset_session_state(self):
        """현재 self._orig 기준으로 레인/코너/자르기/정밀회전/커브/밝기·대비를
        기본값으로 되돌리고 분석용 데이터를 다시 계산한다(self._orig 자체는
        호출부가 미리 설정). 편집 기록(_edit_pristine/_edit_ops/_edit_pos)도
        여기서 비운다 — 새 pristine은 다음 _record_op 때 현재 _orig 기준으로
        자동 재설정된다."""
        self._edit_pristine = None
        self._edit_ops = []
        self._edit_pos = -1
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(False)
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(False)
        # 이 메서드는 '새로운 이미지로 세션을 다시 시작'하는 모든 경로
        # (이미지 열기/붙여넣기/프로젝트 열기/전체 초기화)에서 불린다. WB 합성
        # 모드는 _wb_apply_composite()가 별도로 처리하며 이 메서드를 거치지
        # 않으므로, 여기서는 항상 평소 모드로 되돌린다.
        self._wb_gray_override = None
        self._wb_visible_orig = None
        self._clear_lanes()
        self.gel.clear_corners(); self.corner_label.setText(tr("corner_count", n=0))
        self.gel.clear_crop()
        self.gel.clear_vrange()
        self._rot_base = None
        self._rot_session_pushed = False
        self.rot_slider.blockSignals(True); self.rot_slider.setValue(0); self.rot_slider.blockSignals(False)
        self.rot_spin.blockSignals(True); self.rot_spin.setValue(0); self.rot_spin.blockSignals(False)
        self._curve_base = None
        self._bow_session_pushed = False
        self.bow_slider.blockSignals(True); self.bow_slider.setValue(0); self.bow_slider.blockSignals(False)
        self.bow_spin.blockSignals(True); self.bow_spin.setValue(0); self.bow_spin.blockSignals(False)
        for m in self.curves.values(): m.reset()
        self.curve.model = self.curves[self._ch]; self.curve._sel = None
        self.sl_bright.setValue(0); self.sl_contrast.setValue(0)
        self._snapshot_adjust_baseline()
        self._snapshot_lanes_baseline()
        self.profile.set_lanes([]); self.std_view.clear()
        self.result_table.setRowCount(0)
        if self._orig is not None:
            self._gray_orig = np.array(self._orig.convert("L"), dtype=np.uint8)
            self.curve.set_histogram(self._hist_for(self._ch))
        else:
            self._gray_orig = None
            self.curve.set_histogram(None)
        self._update_vrange_label()   # _gray_orig가 확정된 뒤라야 전체 높이(H)가 맞게 표시됨
        self._refresh_display()

    def _after_load(self, name):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — {name}")
        self._pristine_orig = self._orig.copy()   # 전체 초기화 시 복귀할 기준
        self._reset_session_state()

    def _ask_overlay_option(self):
        """분석 결과가 있을 때 '사진만/분석 포함(합성)'을 묻는다.
        반환값: True(분석 포함) / False(사진만) / None(취소)."""
        has_analysis = any(l.peaks is not None and len(l.peaks) > 0 for l in self.lanes)
        if not has_analysis:
            return False
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(tr("export_image_title"))
        box.setText(tr("export_image_question"))
        box.setStyleSheet(_dialog_style())
        btn_plain = box.addButton(tr("export_plain"), QMessageBox.ActionRole)
        btn_overlay = box.addButton(tr("export_with_overlay"), QMessageBox.ActionRole)
        box.addButton(tr("btn_cancel"), QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is btn_overlay:
            return True
        if clicked is btn_plain:
            return False
        return None

    def copy_image(self):
        src = self._display or self._orig
        if src is None:
            self.status.showMessage(tr("nothing_to_copy_msg")); return
        with_overlay = self._ask_overlay_option()
        if with_overlay is None:
            return
        out_img = render_analysis_overlay(src, self.lanes, band_style=self._band_display_style) if with_overlay else src
        QApplication.clipboard().setPixmap(pil_to_pixmap(out_img))
        self.status.showMessage(tr("status_copied_to_clipboard") +
                                (tr("overlay_included_suffix") if with_overlay else ""))

    def save_image(self):
        src = self._display or self._orig
        if src is None:
            self.status.showMessage(tr("nothing_to_save_msg")); return

        with_overlay = self._ask_overlay_option()
        if with_overlay is None:
            return

        out_img = render_analysis_overlay(src, self.lanes, band_style=self._band_display_style) if with_overlay else src
        default_name = tr("default_filename_with_overlay") if with_overlay else "gel_result.png"
        default_path = str(Path(self._last_dir) / default_name)
        path, _ = QFileDialog.getSaveFileName(self, tr("toolbar_save_result"), default_path, "PNG (*.png);;TIFF (*.tif)")
        if path:
            self._last_dir = str(Path(path).parent)
            out_img.save(path); self.status.showMessage(tr("status_saved", path=path))

    def save_project(self):
        if self._orig is None:
            self.status.showMessage(tr("nothing_to_save_msg")); return
        default_path = str(Path(self._last_dir) / "bandwagon_project.bandwagon")
        path, _ = QFileDialog.getSaveFileName(self, tr("toolbar_project_save"), default_path,
                                               tr("gelproj_filter"))
        if not path:
            return
        if not path.lower().endswith(".bandwagon"):
            path += ".bandwagon"
        try:
            project = {
                "format_version": GELPROJ_FORMAT_VERSION,
                "app_version": APP_VERSION,
                "bright": self.sl_bright.value(),
                "contrast": self.sl_contrast.value(),
                "channel": self._ch,
                "curves": {ch: m.to_dict() for ch, m in self.curves.items()},
                "lanes": [lane.to_dict() for lane in self.lanes],
                "analysis_params": {
                    "prominence": self.sp_prom.value(),
                    "distance": self.sp_dist.value(),
                    "band_threshold": self.sl_band_thresh.value(),
                    "smear_max_px": self.sp_smear.value(),
                    "vrange": list(self.gel.vrange) if self.gel.vrange else None,
                },
                "has_results": any(l.peaks is not None for l in self.lanes),
                "has_wb_override": self._wb_gray_override is not None,
            }
            buf = io.BytesIO()
            self._orig.save(buf, format="PNG")
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("image.png", buf.getvalue())
                z.writestr("project.json", json.dumps(project, ensure_ascii=False, indent=2))
                # WB 합성 모드(_orig가 화면용 블렌드일 때)는 실제 분석에 쓰던
                # UV 단독 그레이스케일을 따로 저장해야 한다. 안 그러면 다시
                # 열었을 때 블렌드 이미지에서 그레이스케일을 자동 재계산하게
                # 되어, 가시광의 마커 글자가 분석에 다시 섞여 들어간다.
                if self._wb_gray_override is not None:
                    gbuf = io.BytesIO()
                    Image.fromarray(self._wb_gray_override, "L").save(gbuf, format="PNG")
                    z.writestr("wb_gray_override.png", gbuf.getvalue())
            self._last_dir = str(Path(path).parent)
            self.status.showMessage(tr("status_project_saved", path=path))
        except Exception as ex:
            self._warn(tr("project_save_failed_title"), str(ex))

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("toolbar_project_open"), self._last_dir,
                                              tr("gelproj_filter"))
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "r") as z:
                project = json.loads(z.read("project.json").decode("utf-8"))
                img_bytes = z.read("image.png")
                names = z.namelist()
                wb_gray_bytes = z.read("wb_gray_override.png") if "wb_gray_override.png" in names else None
            if project.get("format_version", 1) > GELPROJ_FORMAT_VERSION:
                self._warn(tr("version_warning_title"), tr("version_warning_msg"))

            self._orig = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            self._after_load(Path(path).name)   # _gray_orig 재계산 등 표준 초기화

            # WB 합성으로 저장된 프로젝트라면, _after_load가 방금 자동 계산한
            # 그레이스케일(블렌드 이미지에서 파생 — 마커 글자가 섞여 부정확)을
            # 저장해둔 UV 단독 그레이스케일로 덮어쓴다. has_wb_override 플래그가
            # True인데 파일이 없으면(구버전 .bandwagon 등) 조용히 평소 모드로
            # 동작한다 — 사용자가 다시 분석을 돌리면 알게 되므로 막지 않는다.
            if project.get("has_wb_override") and wb_gray_bytes is not None:
                self._wb_gray_override = np.array(
                    Image.open(io.BytesIO(wb_gray_bytes)).convert("L"), dtype=np.uint8)
                self._gray_orig = self._wb_gray_override
                self.curve.set_histogram(self._hist_for(self._ch))

            # _after_load > _reset_session_state 가 밝기/대비/커브/레인을 전부
            # 기본값으로 되돌려 둔 상태이므로, 그 위에 저장된 상태를 다시 입힌다.
            self.sl_bright.setValue(int(project.get("bright", 0)))
            self.sl_contrast.setValue(int(project.get("contrast", 0)))

            for ch, cdict in (project.get("curves") or {}).items():
                if ch in self.curves:
                    self.curves[ch] = CurveModel.from_dict(cdict)
            self.curve.model = self.curves[self._ch]
            self.curve._sel = None
            self.curve.set_histogram(self._hist_for(self._ch))
            self._snapshot_adjust_baseline()

            self.lanes = [Lane.from_dict(d) for d in project.get("lanes", [])]
            self.gel.set_lanes(self.lanes)
            self._rebuild_lane_table()
            self._snapshot_lanes_baseline()

            ap = project.get("analysis_params") or {}
            if "prominence" in ap:
                self.sp_prom.setValue(int(ap["prominence"]))
            if "distance" in ap:
                self.sp_dist.setValue(int(ap["distance"]))
            if "band_threshold" in ap:
                self.sl_band_thresh.setValue(int(ap["band_threshold"]))
            if "smear_max_px" in ap:
                self.sp_smear.setValue(int(ap["smear_max_px"]))
            vr = ap.get("vrange")
            if vr and len(vr) == 2:
                self.gel.vrange = (int(vr[0]), int(vr[1]))
                self._update_vrange_label()

            self._refresh_display()
            if self.lanes and project.get("has_results"):
                self.run_analysis()   # 저장 당시 분석 결과가 있었으면 동일 입력으로 재계산
            self.status.showMessage(tr("status_project_loaded", path=path, n=len(self.lanes)))
        except KeyError:
            self._warn(tr("open_failed_title"), tr("gelproj_invalid_msg"))
        except Exception as ex:
            self._warn(tr("project_open_failed_title"), str(ex))

    def export_csv(self):
        if not any(l.peaks is not None for l in self.lanes):
            self.status.showMessage(tr("run_analysis_first_msg")); return
        default_path = str(Path(self._last_dir) / "gel_analysis.csv")
        path, _ = QFileDialog.getSaveFileName(self, tr("toolbar_export_csv"), default_path, "CSV (*.csv)")
        if not path: return
        self._last_dir = str(Path(path).parent)
        H = self._gray_orig.shape[0] if self._gray_orig is not None else 1
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["Lane", "Type", "Band", "Y(px)", "Rf", "MW(kDa)", "Intensity", "Volume"])
            for lane in self.lanes:
                if lane.peaks is None: continue
                kind = {"sample": "Sample", "marker": "Marker", "bsa": "BSA"}[lane.kind]
                for j, py in enumerate(lane.peaks):
                    mw = lane.mw[j] if j < len(lane.mw) and lane.mw[j] is not None else ""
                    inten = lane.peak_area[j] if lane.peak_area is not None else ""
                    vol = lane.peak_volume[j] if lane.peak_volume is not None else ""
                    w.writerow([lane.name, kind, j + 1, int(py), f"{py/H:.4f}", mw,
                                f"{inten:.2f}" if inten != "" else "",
                                f"{vol:.1f}" if vol != "" else ""])
        self.status.showMessage(tr("status_csv_saved", path=path))

    def reset_all(self):
        # 합성 탭 진행 상태도 함께 비운다 — '전체 초기화'가 그 탭만 남겨두면
        # 일부만 초기화된 것처럼 보여 혼란스럽다.
        self._wb_reset_ui()

        if self._pristine_orig is not None:
            # 불러온 이미지는 그대로 두고, 그 이후의 모든 편집(회전/반전/자르기/
            # 펴기/커브/밝기·대비/레인/WB 합성 등)만 되돌린다.
            self._orig = self._pristine_orig.copy()
            self._reset_session_state()
            self.status.showMessage(tr("status_reset_to_loaded"))
        else:
            self._orig = self._display = self._gray_orig = None
            self.gel._pm = None; self.gel.update()
            self._reset_session_state()
            self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
            self.status.showMessage(tr("status_reset_done"))
