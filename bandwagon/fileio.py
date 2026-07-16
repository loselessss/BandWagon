"""bandwagon.fileio

FileIOMixin — 이미지 열기/붙여넣기/저장, 프로젝트(.bandwagon) 저장·불러오기,
CSV 내보내기, 세션 초기화/전체 초기화. Analyzer(FileIOMixin, ...)로
섞여 들어간다.

이 믹스인은 거의 모든 다른 기능의 상태를 두루 읽고 쓴다(레인은
LanesMixin, 밝기/대비/커브는 GeometryMixin) — '새 이미지로 세션을 다시
시작'하는 지점이 본질적으로 모든 기능의 상태를 한 번에 정리해야 하는
자리이기 때문이다. 웨스턴 블롯 합성 파일(.bwcomposite)을 불러오는
import_composite()도 여기 있다(합성 자체는 독립 모듈 composite.py 담당)."""
import csv
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageGrab
from PyQt5.QtWidgets import QApplication, QAction, QDialog, QFileDialog, QMessageBox

from .i18n import tr
from .theme import *
from .meta import APP_NAME, APP_VERSION, GELPROJ_FORMAT_VERSION
from .imaging import pil_to_pixmap, render_analysis_overlay
from .models import CurveModel, Lane
from .dialogs import _dialog_style


_RECENT_FILES_PATH = Path(os.path.expanduser("~")) / ".bandwagon_recent.json"
_RECENT_FILES_MAX = 10


def _load_recent_files():
    """최근 연 파일 경로 목록(최신이 맨 앞)을 읽는다. 없거나 손상됐으면 빈 목록."""
    try:
        if _RECENT_FILES_PATH.exists():
            data = json.loads(_RECENT_FILES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [p for p in data if isinstance(p, str)]
    except Exception:
        pass
    return []


def _save_recent_files(paths):
    try:
        _RECENT_FILES_PATH.write_text(json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # 저장 실패해도(권한 등) 앱 동작에는 영향 없음


class FileIOMixin:

    def _add_recent_file(self, path):
        """파일을 열 때마다 "최근 파일" 목록 맨 앞으로 옮긴다(이미 있으면
        중복 없이 그 항목을 앞으로 이동). open_path_smart()가 그림/프로젝트/
        합성 파일 구분 없이 여는 모든 경로에서 공통으로 호출하므로, 메뉴
        클릭이든 탐색기 파일 연결로 실행됐든 똑같이 기록된다."""
        path = str(Path(path).resolve())
        recent = [p for p in _load_recent_files() if p != path]
        recent.insert(0, path)
        _save_recent_files(recent[:_RECENT_FILES_MAX])

    def _open_recent_file(self, path):
        """"최근 파일" 메뉴 항목 클릭 — 파일이 그새 지워지거나 옮겨졌으면
        조용히 실패하지 않고 알려준 뒤 목록에서 빼준다."""
        if not Path(path).exists():
            self._warn(tr("recent_file_missing_title"), tr("recent_file_missing_msg", path=path))
            recent = [p for p in _load_recent_files() if p != path]
            _save_recent_files(recent)
            return
        self._open_path_here_or_new_window(path)

    def _clear_recent_files(self):
        _save_recent_files([])

    def _rebuild_recent_menu(self):
        """"최근 파일" 서브메뉴가 열리기 직전(aboutToShow)마다 항목을 새로
        채운다 — 다른 창에서 방금 연 파일도 바로 반영되고, 파일 하나를
        여러 창이 공유하니 캐싱보다 그때그때 다시 읽는 게 항상 정확하다."""
        self.m_recent.clear()
        recent = _load_recent_files()
        if not recent:
            a = QAction(tr("menu_recent_empty"), self); a.setEnabled(False)
            self.m_recent.addAction(a)
            return
        for path in recent:
            a = QAction(Path(path).name, self)
            a.setToolTip(path)
            a.triggered.connect(lambda _checked=False, p=path: self._open_recent_file(p))
            self.m_recent.addAction(a)
        self.m_recent.addSeparator()
        a = QAction(tr("menu_recent_clear"), self); a.triggered.connect(self._clear_recent_files)
        self.m_recent.addAction(a)

    def _open_path_here_or_new_window(self, path):
        """지금 창이 비어있으면 그 자리에 열고, 아니면(이미 뭔가 열려 있으면)
        내용을 바꾸지 않고 새 창을 띄운다 — open_anything()과 "최근 파일"
        메뉴가 공유하는 판단 로직."""
        if self._orig is None:
            self.open_path_smart(path)
            return
        win = self.__class__(None, splash=None)   # Analyzer를 여기서 직접 import하면 순환 참조가 생김
        self.__class__._open_windows.append(win)
        win.open_path_smart(path)
        win.show()

    def new_window(self):
        """완전히 빈 새 창을 하나 더 연다 — 파일 선택 없이 그냥 새 세션을
        시작하고 싶을 때(예: 클립보드 붙여넣기로 시작할 예정이거나, 나중에
        볼 자리를 미리 띄워두고 싶을 때) 쓴다. open_anything()과 달리
        지금 창이 비어있어도 상관없이 항상 새 창을 띄운다 — 사용자가
        명시적으로 "새 창"을 눌렀으니 그 의도를 그대로 따른다."""
        win = self.__class__(None, splash=None)   # Analyzer를 여기서 직접 import하면 순환 참조가 생김
        self.__class__._open_windows.append(win)
        win.show()

    def open_anything(self):
        """"열기" 메뉴의 단일 진입점 — 그림 파일과 프로젝트(.bandwagon)를
        구분하지 않고 한 대화상자에서 고르면, 확장자를 보고 알아서
        load_image()/open_project()로 나눠 보낸다. 예전엔 "그림 열기"와
        "프로젝트 열기"가 툴바에 따로 있었는데, 사용자 입장에서 어차피
        "그냥 파일 열기"일 뿐이라 구분할 이유가 없어서 합쳤다.

        지금 창이 비어있으면(self._orig is None, 아직 아무 이미지도 안 연
        상태) 그 자리에 바로 연다 — 굳이 빈 창을 하나 더 남겨둘 이유가
        없기 때문. 이미 뭔가 열려 있는 창이면 그 내용을 바꾸지 않고 새
        창을 하나 더 띄운다 — 여러 젤을 동시에 띄워두고 비교하기 위함
        (예: 마커/설정을 나란히 맞춰보기)."""
        path, _ = QFileDialog.getOpenFileName(self, tr("dlg_open_title"), self._last_dir,
                                              tr("dlg_open_filter"))
        if not path:
            return
        self._last_dir = str(Path(path).parent)
        self._open_path_here_or_new_window(path)

    def open_path_smart(self, path):
        """확장자를 보고 그림/프로젝트/합성 파일을 알아서 연다.
        open_anything()의 새 창뿐 아니라, 탐색기에서 파일을 더블클릭해
        실행됐을 때(커맨드라인 인자로 경로가 넘어옴, __main__.py 참고)도
        쓴다. .bwcomposite는 메인 창에서 바로 분석을 시작하면서, 빈 합성
        스튜디오도 비모달로 같이 띄운다(원본 가시광/UV 사진은 파일 안에
        없어 이 파일 자체를 스튜디오로 다시 불러올 순 없지만, 새로 합성을
        만들거나 다른 합성 파일을 불러올 때 바로 쓸 수 있게).

        어떤 경로로 열렸든(메뉴/파일 연결/"최근 파일") 여기 한 곳만 거치므로
        "최근 파일" 기록도 여기서 공통으로 한다."""
        self._add_recent_file(path)
        lower = path.lower()
        if lower.endswith(".bandwagon"):
            self.open_project(path)
        elif lower.endswith(".bwcomposite"):
            self.import_composite(path)
            self._show_composite_studio_window()
        else:
            self.load_image(path)

    def _show_composite_studio_window(self):
        """합성 스튜디오를 비모달로 띄운다 — open_composite_studio()는
        모달(exec_)이라 끝날 때까지 메인 창을 못 건드리는데, 여긴 이미
        메인 창에서 분석 중이라 그렇게 막을 이유가 없다. 안에서 "합성
        내보내기"나 "기존 합성 파일 불러오기"로 accept되면(=창을 닫으면),
        평소 모달 흐름과 동일하게 바로 분석할지 물어본다."""
        from .composite import CompositeStudio
        dlg = CompositeStudio(self, last_dir=self._last_dir)

        def _on_finished(result):
            if dlg._last_dir:
                self._last_dir = dlg._last_dir
            if result == QDialog.Accepted and dlg.last_export_path:
                if self._ask(tr("composite_open_now_title"), tr("composite_open_now_msg")):
                    self.import_composite(dlg.last_export_path)

        dlg.finished.connect(_on_finished)
        dlg.setModal(False)
        dlg.show()
        self.__class__._open_windows.append(dlg)   # GC 방지용 참조 유지

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
        self._edit_gray_pristine = None
        self._edit_ops = []
        self._edit_pos = -1
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(False)
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(False)
        # 이 메서드는 '새로운 이미지로 세션을 다시 시작'하는 모든 경로
        # (이미지 열기/붙여넣기/프로젝트 열기/합성 불러오기/전체 초기화)에서
        # 불린다. 항상 평소 모드로 되돌리고, 합성 임포트는 import_composite()가
        # 이 초기화 뒤에 UV 오버라이드를 다시 설정한다(open_project의 WB
        # 오버라이드 분기와 동일).
        self._wb_gray_override = None
        self._current_project_path = None
        self._clear_lanes()
        self.gel.clear_corners(); self.corner_label.setText(tr("corner_count", n=0))
        self.gel.clear_vrange()
        self._rot_base = None
        self._rot_session_pushed = False
        self.rot_slider.blockSignals(True); self.rot_slider.setValue(0); self.rot_slider.blockSignals(False)
        self.rot_spin.blockSignals(True); self.rot_spin.setValue(0); self.rot_spin.blockSignals(False)
        self._curve_base = None
        self._bow_session_pushed = False
        self.bow_slider.blockSignals(True); self.bow_slider.setValue(0); self.bow_slider.blockSignals(False)
        self.bow_spin.blockSignals(True); self.bow_spin.setValue(0); self.bow_spin.blockSignals(False)
        self._shear_base = None
        self._shear_session_pushed = False
        self.shear_slider.blockSignals(True); self.shear_slider.setValue(0); self.shear_slider.blockSignals(False)
        self.shear_spin.blockSignals(True); self.shear_spin.setValue(0); self.shear_spin.blockSignals(False)
        for m in self.curves.values(): m.reset()
        self.curve.model = self.curves[self._ch]; self.curve._sel = None
        self.sl_bright.setValue(0); self.sl_contrast.setValue(0)
        self._snapshot_adjust_baseline()
        self._snapshot_lanes_baseline()
        self.profile.set_lanes([]); self.std_view.clear()
        self.result_table.setRowCount(0)
        self.memo_edit.setPlainText("")
        if self._orig is not None:
            self._gray_orig = np.array(self._orig.convert("L"), dtype=np.uint8)
            self.curve.set_histogram(self._hist_for(self._ch))
        else:
            self._gray_orig = None
            self.curve.set_histogram(None)
        self._update_vrange_label()   # _gray_orig가 확정된 뒤라야 전체 높이(H)가 맞게 표시됨
        self._refresh_display()
        # 방금 리셋한 상태를 "저장된 상태" 기준으로 잡는다 — 프로젝트를 연
        # 경우 open_project()가 자기 값들을 복원한 뒤 다시 한번 갱신한다.
        self._saved_snapshot = self._project_state_snapshot()

    def _project_state_snapshot(self):
        """지금 상태를 나타내는 해시. 창을 닫을 때 마지막 저장 시점과
        비교해 '저장 안 한 변경사항이 있는지' 판단하는 데 쓴다. 이미지
        픽셀까지 포함해야 한다 — 회전/자르기 같은 편집은 레인/커브 같은
        메타데이터를 안 바꾸고 이미지 자체만 바꾸기 때문이다.

        제목표시줄 '*' 표시(_refresh_title)가 이 함수를 몇 초마다 반복
        호출한다. self._orig.tobytes()는 압축 없는 원본 픽셀 사본이라
        (PNG보다 훨씬 빠르지만) 호출할 때마다 이미지 크기만큼 메모리를
        일시적으로 더 쓴다 — self._orig 객체 자체가 바뀌지 않는 한(즉
        편집으로 재할당되지 않는 한) 해시가 그대로일 수밖에 없으므로,
        객체 identity로 캐싱해 실제로 이미지가 바뀐 순간에만 다시
        해싱한다. 대부분의 틱(사진은 그대로, 레인/커브/메모만 만지는
        중)은 이 캐시를 그대로 재사용해 tobytes() 호출 자체를 건너뛴다."""
        if self._orig is None:
            self._img_hash_cache = (None, None)
            return None
        if self._img_hash_cache[0] is not self._orig:
            h_img = hashlib.sha256(); h_img.update(self._orig.tobytes())
            self._img_hash_cache = (self._orig, h_img.hexdigest())
        h = hashlib.sha256()
        h.update(self._img_hash_cache[1].encode())
        meta = {
            "bright": self.sl_bright.value(),
            "contrast": self.sl_contrast.value(),
            "channel": self._ch,
            "curves": {ch: m.to_dict() for ch, m in self.curves.items()},
            "lanes": [lane.to_dict() for lane in self.lanes],
            "memo": self.memo_edit.toPlainText(),
            "analysis_params": {
                "prominence": self.sp_prom.value(),
                "distance": self.sp_dist.value(),
                "band_threshold": self.sl_band_thresh.value(),
                "smear_max_px": self.sp_smear.value(),
                "vrange": list(self.gel.vrange) if self.gel.vrange else None,
            },
        }
        h.update(json.dumps(meta, sort_keys=True).encode())
        return h.hexdigest()

    def closeEvent(self, event):
        """창을 닫기 전에, 마지막 저장 이후 바뀐 게 있으면 저장할지 물어본다."""
        if self._project_state_snapshot() == getattr(self, "_saved_snapshot", None):
            event.accept(); return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(tr("unsaved_changes_title"))
        box.setText(tr("unsaved_changes_msg"))
        box.setStyleSheet(_dialog_style())
        btn_save = box.addButton(tr("unsaved_save_btn"), QMessageBox.AcceptRole)
        box.addButton(tr("unsaved_discard_btn"), QMessageBox.DestructiveRole)
        btn_cancel = box.addButton(tr("btn_cancel"), QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is btn_cancel:
            event.ignore(); return
        if clicked is btn_save:
            self.save_project()
            # 저장 대화상자에서 사용자가 취소했을 수 있으니, 실제로 저장
            # 됐는지(스냅샷이 최신과 일치하는지) 확인하고 안 됐으면 닫지 않는다.
            if self._project_state_snapshot() != self._saved_snapshot:
                event.ignore(); return
        event.accept()

    def _after_load(self, name):
        self._base_title = f"{APP_NAME} v{APP_VERSION} — {name}"
        self._pristine_orig = self._orig.copy()   # 전체 초기화 시 복귀할 기준
        self._reset_session_state()   # _saved_snapshot을 방금 리셋한 상태 기준으로 갱신
        self._refresh_title()

    def _refresh_title(self):
        """저장 안 한 변경사항이 있으면 제목표시줄 앞에 '*'를 붙인다.
        _title_timer(app.py)가 주기적으로 부르고, 저장/불러오기 직후에도
        바로 반영되도록 즉시 한 번 더 호출한다."""
        dirty = self._project_state_snapshot() != getattr(self, "_saved_snapshot", None)
        base = getattr(self, "_base_title", f"{APP_NAME} v{APP_VERSION}")
        self.setWindowTitle(f"* {base}" if dirty else base)

    def _ask_overlay_option(self):
        """분석 결과가 있을 때 '사진만/분석 포함(합성)/오버레이만(투명 배경)'을
        묻는다. 반환값: "overlay" / "plain" / "overlay_only" / None(취소)."""
        has_analysis = any(l.peaks is not None and len(l.peaks) > 0 for l in self.lanes)
        if not has_analysis:
            return "plain"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(tr("export_image_title"))
        box.setText(tr("export_image_question"))
        box.setStyleSheet(_dialog_style())
        btn_plain = box.addButton(tr("export_plain"), QMessageBox.ActionRole)
        btn_overlay = box.addButton(tr("export_with_overlay"), QMessageBox.ActionRole)
        btn_overlay_only = box.addButton(tr("export_overlay_only"), QMessageBox.ActionRole)
        box.addButton(tr("btn_cancel"), QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is btn_overlay:
            return "overlay"
        if clicked is btn_overlay_only:
            return "overlay_only"
        if clicked is btn_plain:
            return "plain"
        return None

    def _render_for_export(self, src, choice):
        """_ask_overlay_option()의 선택에 따라 내보낼 이미지를 만든다.
        "overlay_only"는 사진 없이 완전 투명 배경 위에 레인/밴드/MW만
        그린다 — 다른 배경 위에 겹쳐 쓰거나 발표 자료에 붙여넣기 좋다."""
        if choice == "overlay_only":
            return render_analysis_overlay(src, self.lanes, band_style=self._band_display_style,
                                           transparent_bg=True)
        if choice == "overlay":
            return render_analysis_overlay(src, self.lanes, band_style=self._band_display_style)
        return src

    def copy_image(self):
        src = self._display or self._orig
        if src is None:
            self.status.showMessage(tr("nothing_to_copy_msg")); return
        choice = self._ask_overlay_option()
        if choice is None:
            return
        out_img = self._render_for_export(src, choice)
        QApplication.clipboard().setPixmap(pil_to_pixmap(out_img))
        suffix = tr("overlay_included_suffix") if choice in ("overlay", "overlay_only") else ""
        self.status.showMessage(tr("status_copied_to_clipboard") + suffix)

    def save_image(self):
        src = self._display or self._orig
        if src is None:
            self.status.showMessage(tr("nothing_to_save_msg")); return

        choice = self._ask_overlay_option()
        if choice is None:
            return

        out_img = self._render_for_export(src, choice)
        default_name = {"overlay": tr("default_filename_with_overlay"),
                        "overlay_only": tr("default_filename_overlay_only")}.get(choice, "gel_result.png")
        default_path = str(Path(self._last_dir) / default_name)
        path, _ = QFileDialog.getSaveFileName(self, tr("toolbar_save_result"), default_path, "PNG (*.png);;TIFF (*.tif)")
        if path:
            self._last_dir = str(Path(path).parent)
            out_img.save(path); self.status.showMessage(tr("status_saved", path=path))

    def save_project(self):
        """Ctrl+S / "프로젝트 저장" — 이미 이 세션에서 연/저장한 프로젝트
        파일이 있으면(_current_project_path) 대화상자 없이 그 경로에 바로
        덮어쓴다. 아직 한 번도 저장한 적 없으면(경로를 모름) 어차피 경로를
        물어야 하므로 save_project_as()와 동일하게 동작한다."""
        if self._orig is None:
            self.status.showMessage(tr("nothing_to_save_msg")); return
        if self._current_project_path:
            self._write_project_file(self._current_project_path)
        else:
            self.save_project_as()

    def save_project_as(self):
        """"프로젝트 새로 저장" — 이미 저장한 경로가 있어도 항상 새 파일
        이름/위치를 물어본다(사본 만들기 용도)."""
        if self._orig is None:
            self.status.showMessage(tr("nothing_to_save_msg")); return
        default_path = self._current_project_path or str(Path(self._last_dir) / "bandwagon_project.bandwagon")
        path, _ = QFileDialog.getSaveFileName(self, tr("toolbar_project_save_as"), default_path,
                                               tr("gelproj_filter"))
        if not path:
            return
        if not path.lower().endswith(".bandwagon"):
            path += ".bandwagon"
        self._write_project_file(path)

    def _write_project_file(self, path):
        try:
            project = {
                "format_version": GELPROJ_FORMAT_VERSION,
                "app_version": APP_VERSION,
                "bright": self.sl_bright.value(),
                "contrast": self.sl_contrast.value(),
                "channel": self._ch,
                "curves": {ch: m.to_dict() for ch, m in self.curves.items()},
                "lanes": [lane.to_dict() for lane in self.lanes],
                "memo": self.memo_edit.toPlainText(),
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
            self._current_project_path = path
            # 제목표시줄이 클립보드/이전 이미지 이름에 머물러 있지 않도록,
            # 저장 성공 시 지금 작업 중인 프로젝트 파일 이름으로 갱신한다.
            self._base_title = f"{APP_NAME} v{APP_VERSION} — {Path(path).name}"
            self._saved_snapshot = self._project_state_snapshot()
            self._refresh_title()
            self.status.showMessage(tr("status_project_saved", path=path))
        except Exception as ex:
            self._warn(tr("project_save_failed_title"), str(ex))

    def open_project_location(self):
        """프로젝트 현재 위치 열기 — 탐색기(맥은 Finder)로 지금 파일을
        선택한 채 폴더를 연다. 아직 저장/열기한 프로젝트 파일이 없으면
        (경로를 모르면) 아무것도 하지 않고 상태바에 안내만 띄운다."""
        if not self._current_project_path:
            self.status.showMessage(tr("no_project_path_msg")); return
        import subprocess, sys
        path = str(Path(self._current_project_path))
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", path])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", path])
            else:
                subprocess.run(["xdg-open", str(Path(path).parent)])
        except Exception as ex:
            self._warn(tr("open_failed_title"), str(ex))

    def open_project(self, path=None):
        if path is None:
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

            self.memo_edit.setPlainText(project.get("memo", ""))

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
            self._last_dir = str(Path(path).parent)
            self._current_project_path = path
            # _reset_session_state가 이미 한 번 스냅샷을 찍었지만, 그건 복원
            # 전(빈 상태) 기준이었다 — 방금 불러온 상태로 다시 맞춰야 "저장 안
            # 한 변경사항 있음"으로 잘못 뜨지 않는다.
            self._saved_snapshot = self._project_state_snapshot()
            self._refresh_title()
            self.status.showMessage(tr("status_project_loaded", path=path, n=len(self.lanes)))
        except KeyError:
            self._warn(tr("open_failed_title"), tr("gelproj_invalid_msg"))
        except Exception as ex:
            self._warn(tr("project_open_failed_title"), str(ex))

    def open_composite_studio(self):
        """웨스턴 블롯 합성 스튜디오(독립 다이얼로그)를 연다. 합성 후
        사용자가 .bwcomposite로 내보내면, 방금 저장한 파일을 곧바로
        분석용으로 열지 물어본다."""
        from .composite import CompositeStudio
        dlg = CompositeStudio(self, last_dir=self._last_dir)
        result = dlg.exec_()
        if dlg._last_dir:
            self._last_dir = dlg._last_dir
        if result == QDialog.Accepted and dlg.last_export_path:
            if self._ask(tr("composite_open_now_title"), tr("composite_open_now_msg")):
                self.import_composite(dlg.last_export_path)

    def import_composite(self, path=None):
        """.bwcomposite(합성 스튜디오 산출물)를 불러와 새 분석 세션을 시작한다.
        화면용 블렌드가 원본이 되고, 분석용 그레이스케일은 UV 단독 강도를
        쓴다 — open_project의 WB 오버라이드 분기와 동일한 원리다.

        일반 이미지 열기(load_image)와 같은 '새 세션 시작'이라, 합성은
        되돌리기 히스토리에 특수 연산으로 남지 않는다(그 지점이 새 출발점).
        이후 편집·분석은 평소와 완전히 동일하게 동작한다."""
        from .composite import load_composite
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("composite_import_title"), self._last_dir,
                tr("composite_file_filter"))
            if not path:
                return
        try:
            blend, gray = load_composite(path)
        except Exception as ex:
            self._warn(tr("composite_import_failed_title"), str(ex)); return

        self._orig = blend
        self._after_load(Path(path).name)   # 표준 초기화 (여기서 _gray_orig는 블렌드 기준으로 잡힘)
        # _reset_session_state가 방금 자동 계산한 그레이스케일(블렌드에서 파생 —
        # 가시광이 섞여 부정확)을 저장된 UV 단독 그레이스케일로 덮어쓴다.
        self._wb_gray_override = gray
        self._gray_orig = gray
        self.curve.set_histogram(self._hist_for(self._ch))
        self._last_dir = str(Path(path).parent)
        self.status.showMessage(tr("status_composite_imported", path=Path(path).name))

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
            self._base_title = f"{APP_NAME} v{APP_VERSION}"
            self._refresh_title()
            self.status.showMessage(tr("status_reset_done"))
