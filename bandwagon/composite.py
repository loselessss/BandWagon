"""bandwagon.composite

웨스턴 블롯 합성 '스튜디오' — 가시광 사진과 UV 사진을 코너 4점으로 정렬해
합성하는 독립 모듈. 예전 WesternMixin(메인 윈도우에 섞여 들어가던 탭)과
달리, 이건 완전히 분리된 QDialog다:

  1) 스튜디오를 연다 → 가시광/UV 두 장을 불러오고 코너를 맞춰 합성한다.
  2) '.bwcomposite' 파일로 내보낸다 — 그 안엔 '화면용 블렌드(RGB)'와
     '분석용 UV 단독 그레이스케일(L)' 두 장이 쌍으로 들어간다.
  3) 메인 앱에서 그 파일을 '합성 불러오기'로 임포트하면, 블렌드가 화면용
     원본이 되고 분석은 UV 그레이스케일로 돈다(밴드 검출은 평소와 동일).

이렇게 파일을 사이에 두고 분리한 덕에:
  - 메인 앱의 되돌리기 히스토리가 가시광/UV 원본 전체를 붙들고 있을
    필요가 없다(예전 wb_composite 연산이 원본을 복사해 스택에 쌓던
    메모리 부담이 사라진다).
  - 합성 로직과 분석 로직이 서로의 상태를 안 건드린다 — 계약은 오직
    '이미지 두 장'뿐.

Qt에 의존하지 않는 순수 변환은 전부 imaging.py에 그대로 있고, 여기선
그걸 가져다 쓴다. 재사용 위젯도 widgets.py의 GelView/ThumbView뿐이라,
이 모듈은 Analyzer(메인 윈도우) 내부를 전혀 참조하지 않는다.
"""
import io
import json
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageGrab
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QSlider,
    QVBoxLayout, QWidget,
)

from .i18n import tr
from .theme import CYAN, INK2, INK3, INKT, MUTE
from .dialogs import _dialog_style
from .imaging import (
    blend_for_uv_canvas, blend_visible_uv, downscale_for_preview,
    pil_to_pixmap, uv_only_grayscale, warp_uv_to_visible, warp_visible_to_uv,
)
from .widgets import GelView, ThumbView


COMPOSITE_EXT = ".bwcomposite"
COMPOSITE_FORMAT_VERSION = 1


# ═══════════════════════════════════════════════════════════════════
#  파일 입출력 — 순수 함수 (Qt 위젯 없이도 호출 가능, 테스트 쉬움)
# ═══════════════════════════════════════════════════════════════════
def export_composite(path, blend_img, uv_gray, meta=None):
    """합성 결과를 .bwcomposite(zip)로 저장한다.

    blend_img: 화면용 블렌드 PIL RGB (가시광+UV).
    uv_gray:   분석용 UV 단독 그레이스케일 — np.uint8 2D 배열 또는 PIL 'L'.
               blend_img와 반드시 같은 크기(가시광 좌표계).
    meta:      선택적 부가정보(opacity/corners 등) — 재현/디버그용.

    화면용과 분석용을 굳이 둘 다 저장하는 이유: UV 단독 그레이스케일을
    블렌드 RGB에서 나중에 되만들 수 없기 때문이다(가시광이 이미 섞임).
    분석은 UV 강도만 봐야 가시광의 밝은 마커 글자·종이가 가짜 밴드로
    잡히지 않는다."""
    if isinstance(uv_gray, np.ndarray):
        uv_gray_img = Image.fromarray(uv_gray, "L")
    else:
        uv_gray_img = uv_gray.convert("L")
    if uv_gray_img.size != blend_img.size:
        raise ValueError(
            f"블렌드({blend_img.size})와 UV 그레이스케일({uv_gray_img.size}) 크기가 다릅니다.")

    header = {
        "format": "bwcomposite",
        "format_version": COMPOSITE_FORMAT_VERSION,
    }
    if meta:
        header.update(meta)

    bbuf = io.BytesIO(); blend_img.convert("RGB").save(bbuf, format="PNG")
    gbuf = io.BytesIO(); uv_gray_img.save(gbuf, format="PNG")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("blend.png", bbuf.getvalue())
        z.writestr("uv_gray.png", gbuf.getvalue())
        z.writestr("meta.json", json.dumps(header, ensure_ascii=False, indent=2))


def load_composite(path):
    """.bwcomposite를 읽어 (blend_img: PIL RGB, uv_gray: np.uint8 2D)로 반환.
    파일이 규격에 안 맞으면 ValueError."""
    with zipfile.ZipFile(path, "r") as z:
        names = z.namelist()
        if "blend.png" not in names or "uv_gray.png" not in names:
            raise ValueError("올바른 합성 파일이 아닙니다(blend/uv_gray 누락).")
        blend = Image.open(io.BytesIO(z.read("blend.png"))).convert("RGB")
        gray = np.array(Image.open(io.BytesIO(z.read("uv_gray.png"))).convert("L"),
                        dtype=np.uint8)
    if gray.shape[:2] != (blend.height, blend.width):
        raise ValueError("블렌드와 UV 그레이스케일 크기가 일치하지 않습니다.")
    return blend, gray


# ═══════════════════════════════════════════════════════════════════
#  합성 스튜디오 다이얼로그
# ═══════════════════════════════════════════════════════════════════
class CompositeStudio(QDialog):
    """가시광+UV를 코너 정렬해 합성하고 .bwcomposite로 내보내는 독립 창.

    코너 지정 캔버스(GelView, corner 모드)의 배경에 라이브 블렌드를 그려,
    코너를 잡는 동시에 정합 결과를 바로 확인한다(예전 WesternMixin과 같은
    UX). 내보내기는 항상 원본 해상도로 다시 계산하므로 미리보기 축소와
    무관하게 결과 품질이 유지된다.

    exec_()가 QDialog.Accepted를 돌려주고 last_export_path가 채워지면,
    호출부(메인 윈도우)는 그 파일을 곧바로 임포트할지 물어볼 수 있다."""

    def __init__(self, parent=None, last_dir=None):
        super().__init__(parent)
        self.setWindowTitle(tr("composite_studio_title"))
        self.setStyleSheet(_dialog_style())
        self.setMinimumSize(520, 640)
        self._visible_img = None    # 가시광 원본 (PIL RGB)
        self._uv_img = None         # UV 원본 (PIL RGB)
        self._last_dir = last_dir or str(Path.home())
        self.last_export_path = None   # 내보내기 성공 시 채워짐(호출부가 임포트 판단에 사용)
        self._build()

    # ── UI ──────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(12, 12, 12, 12); root.setSpacing(8)

        info = QLabel(tr("composite_intro"))
        info.setStyleSheet(f"color:{MUTE};font-size:11px;"); info.setWordWrap(True)
        root.addWidget(info)

        # 0) 이미 만들어둔 .bwcomposite가 있으면 처음부터 다시 만들 필요 없이
        # 바로 열기 — export 직후 흐름(last_export_path + accept)과 똑같이
        # 처리해서 메인 창(fileio.open_composite_studio)이 그대로 이어받는다.
        btn_load_existing = QPushButton(tr("toolbar_composite_import"))
        btn_load_existing.setToolTip(tr("toolbar_composite_import_tip"))
        btn_load_existing.clicked.connect(self._load_existing)
        btn_load_existing.setStyleSheet(self._btn_css())
        root.addWidget(btn_load_existing)

        # 1) 두 장 불러오기
        load_box = QGroupBox(tr("wb_group_load")); load_box.setStyleSheet(self._group_css())
        load_row = QHBoxLayout(load_box); load_row.setSpacing(10)

        vis_col = QVBoxLayout(); vis_col.setSpacing(4)
        self.thumb_visible = ThumbView(side=96)
        self.thumb_visible.clicked.connect(self._on_thumb_visible)
        vis_col.addWidget(self.thumb_visible, 0, Qt.AlignHCenter)
        vcap = QLabel(tr("wb_caption_visible")); vcap.setAlignment(Qt.AlignCenter)
        vcap.setStyleSheet(f"color:{MUTE};font-size:10px;"); vis_col.addWidget(vcap)
        load_row.addLayout(vis_col)

        uv_col = QVBoxLayout(); uv_col.setSpacing(4)
        self.thumb_uv = ThumbView(side=96)
        self.thumb_uv.clicked.connect(self._on_thumb_uv)
        uv_col.addWidget(self.thumb_uv, 0, Qt.AlignHCenter)
        ucap = QLabel(tr("wb_caption_uv")); ucap.setAlignment(Qt.AlignCenter)
        ucap.setStyleSheet(f"color:{MUTE};font-size:10px;"); uv_col.addWidget(ucap)
        load_row.addLayout(uv_col)
        root.addWidget(load_box)

        thumb_hint = QLabel(tr("wb_thumb_click_hint"))
        thumb_hint.setStyleSheet(f"color:{MUTE};font-size:9px;"); thumb_hint.setWordWrap(True)
        root.addWidget(thumb_hint)

        # 2) 정렬 캔버스 (코너 지정 + 라이브 블렌드)
        corner_box = QGroupBox(tr("wb_group_align")); corner_box.setStyleSheet(self._group_css())
        corner_v = QVBoxLayout(corner_box)
        chint = QLabel(tr("wb_corner_hint"))
        chint.setStyleSheet(f"color:{MUTE};font-size:10px;"); chint.setWordWrap(True)
        corner_v.addWidget(chint)
        self.corner_label = QLabel(tr("corner_count", n=0))
        self.corner_label.setStyleSheet(f"color:{CYAN};font-size:11px;font-family:'DejaVu Sans Mono';")
        corner_v.addWidget(self.corner_label)
        btn_clear = QPushButton(tr("btn_reset_corners")); btn_clear.clicked.connect(self._clear_corners)
        btn_clear.setStyleSheet(self._btn_css()); corner_v.addWidget(btn_clear)
        root.addWidget(corner_box)

        self.gel = GelView()
        self.gel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.gel.setMinimumWidth(0); self.gel.setMinimumHeight(240)
        self.gel.set_mode("corner")
        self.gel.cornerChanged.connect(self._on_corner_changed)
        root.addWidget(self.gel, 1)

        # 3) 오파시티
        op_row = QHBoxLayout(); op_row.setSpacing(6)
        op_lbl = QLabel(tr("wb_opacity_label")); op_lbl.setStyleSheet(f"color:{MUTE};font-size:11px;")
        op_row.addWidget(op_lbl)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100); self.opacity_slider.setValue(60)
        self.opacity_slider.setStyleSheet(self._slider_css())
        self.opacity_slider.valueChanged.connect(lambda _v: self._refresh_canvas())
        op_row.addWidget(self.opacity_slider, 1)
        root.addLayout(op_row)
        op_hint = QLabel(tr("wb_opacity_hint"))
        op_hint.setStyleSheet(f"color:{MUTE};font-size:9px;"); op_hint.setWordWrap(True)
        root.addWidget(op_hint)

        # 4) 내보내기 / 닫기
        btn_export = QPushButton(tr("composite_btn_export")); btn_export.clicked.connect(self._export)
        btn_export.setStyleSheet(self._btn_accent_css())
        root.addWidget(btn_export)
        export_hint = QLabel(tr("composite_export_hint"))
        export_hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); export_hint.setWordWrap(True)
        root.addWidget(export_hint)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ── 이미지 불러오기 ──────────────────────────────────────────────
    def _pick_image_for(self, target):
        """빈 썸네일 클릭 시 파일/클립보드 선택. target: 'visible' | 'uv'."""
        box = QMessageBox(self); box.setIcon(QMessageBox.Question)
        box.setWindowTitle(tr("wb_pick_source_title")); box.setText(tr("wb_pick_source_msg"))
        box.setStyleSheet(_dialog_style())
        btn_file = box.addButton(tr("wb_pick_source_file"), QMessageBox.ActionRole)
        btn_paste = box.addButton(tr("wb_pick_source_paste"), QMessageBox.ActionRole)
        box.addButton(tr("btn_cancel"), QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        img = None
        if clicked is btn_file:
            title = tr("wb_btn_load_visible") if target == "visible" else tr("wb_btn_load_uv")
            path, _ = QFileDialog.getOpenFileName(
                self, title, self._last_dir,
                "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)")
            if not path:
                return
            try:
                img = Image.open(path).convert("RGB")
            except Exception as ex:
                QMessageBox.warning(self, tr("open_failed_title"), str(ex)); return
            self._last_dir = str(Path(path).parent)
        elif clicked is btn_paste:
            img = self._read_clipboard_image()
            if img is None:
                QMessageBox.information(self, tr("wb_pick_source_title"), tr("clipboard_empty_msg"))
                return
        else:
            return

        if target == "visible":
            self._visible_img = img
            self.thumb_visible.set_image(img)
        else:
            self._uv_img = img
            self.thumb_uv.set_image(img)
            self.gel.clear_corners()
            self.corner_label.setText(tr("corner_count", n=0))
            self.gel.set_image(pil_to_pixmap(img), img.size)
        self._refresh_canvas()

    @staticmethod
    def _read_clipboard_image():
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

    def _on_thumb_visible(self):
        if self._visible_img is None:
            self._pick_image_for("visible")
        else:
            self._show_image_dialog(tr("wb_reference_dialog_title"), self._visible_img)

    def _on_thumb_uv(self):
        if self._uv_img is None:
            self._pick_image_for("uv")
        else:
            self._show_image_dialog(tr("wb_uv_reference_dialog_title"), self._uv_img)

    def _show_image_dialog(self, title, pil_img):
        dlg = QDialog(self); dlg.setWindowTitle(title); dlg.setStyleSheet(_dialog_style())
        lay = QVBoxLayout(dlg)
        lbl = QLabel(); lbl.setPixmap(pil_to_pixmap(pil_img).scaled(
            700, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(lbl)
        bb = QDialogButtonBox(QDialogButtonBox.Ok); bb.accepted.connect(dlg.accept)
        lay.addWidget(bb); dlg.exec_()

    # ── 코너/오파시티 변화 → 캔버스 다시 그리기 ──────────────────────
    def _on_corner_changed(self, n):
        self.corner_label.setText(tr("corner_count", n=n))
        self._refresh_canvas()

    def _clear_corners(self):
        self.gel.clear_corners()
        self.corner_label.setText(tr("corner_count", n=0))
        self._refresh_canvas()

    def _refresh_canvas(self):
        """정렬 캔버스 배경을 다시 계산한다(좌표계는 항상 UV 원본 크기).
        UV만 있으면 UV 그대로, 가시광+코너 4점이 다 있으면 가시광을 UV
        좌표계로 역변환해 얹은 라이브 블렌드를 보여준다. 큰 이미지에서
        워프가 무거우므로 캔버스 크기에 맞춰 축소해 계산한다(코너도 같은
        비율로 축소)."""
        if self._uv_img is None:
            return
        corners = self.gel.corners
        cs = self.gel.size()
        uv_small, uv_scale = downscale_for_preview(self._uv_img, cs.width(), cs.height())
        if self._visible_img is not None and len(corners) == 4:
            try:
                opacity = self.opacity_slider.value() / 100.0
                corners_small = [(x * uv_scale, y * uv_scale) for x, y in corners]
                vis_on_uv = warp_visible_to_uv(self._visible_img, corners_small, uv_small.size)
                canvas_img = blend_for_uv_canvas(uv_small, vis_on_uv, opacity)
            except Exception:
                canvas_img = uv_small
        else:
            canvas_img = uv_small
        # _img_size는 좌표 변환 기준이라 항상 원본 UV 크기를 넘긴다
        # (그림은 작아도 코너 클릭은 원본 좌표로 계산됨).
        self.gel.set_image(pil_to_pixmap(canvas_img), self._uv_img.size)

    # ── 내보내기 ────────────────────────────────────────────────────
    def _compute_full_res(self):
        """현재 정렬 상태로 (블렌드 RGB, UV 단독 그레이스케일)을 원본 해상도로
        계산해 반환한다. apply 전 검증과 실제 내보내기가 공유한다."""
        uv_corners = np.array(self.gel.corners, dtype=np.float32)
        warped = warp_uv_to_visible(self._uv_img, uv_corners, self._visible_img.size)
        opacity = self.opacity_slider.value() / 100.0
        blend = blend_visible_uv(self._visible_img, warped, opacity)
        gray = uv_only_grayscale(warped)   # UV 강도만 — 분석용
        return blend, gray

    def _export(self):
        if self._visible_img is None:
            QMessageBox.information(self, tr("wb_need_visible_title"), tr("wb_need_visible_msg")); return
        if self._uv_img is None or len(self.gel.corners) != 4:
            QMessageBox.information(self, tr("wb_need_uv_corners_title"), tr("wb_need_uv_corners_msg")); return
        try:
            blend, gray = self._compute_full_res()
        except Exception as ex:
            QMessageBox.warning(self, tr("wb_apply_failed_title"), str(ex)); return

        default_path = str(Path(self._last_dir) / ("composite" + COMPOSITE_EXT))
        path, _ = QFileDialog.getSaveFileName(
            self, tr("composite_btn_export"), default_path,
            tr("composite_file_filter"))
        if not path:
            return
        if not path.lower().endswith(COMPOSITE_EXT):
            path += COMPOSITE_EXT
        try:
            export_composite(path, blend, gray, meta={
                "opacity": self.opacity_slider.value() / 100.0,
                "corners": [[float(x), float(y)] for x, y in self.gel.corners],
            })
        except Exception as ex:
            QMessageBox.warning(self, tr("wb_apply_failed_title"), str(ex)); return
        self._last_dir = str(Path(path).parent)
        self.last_export_path = path
        # 내보내기가 곧 이 창의 목적이므로, 성공하면 창을 accept로 닫아
        # 호출부가 '방금 저장한 걸 바로 분석으로 열까요?'를 물을 수 있게 한다.
        self.accept()

    def _load_existing(self):
        """이미 내보내둔 .bwcomposite를 골라 곧바로 분석으로 넘긴다.
        .bwcomposite는 최종 블렌드/그레이스케일만 담고 원본 가시광·UV
        사진은 안 남기므로(설계상 의도적으로 안 그렇게 함 — 클래스
        docstring 참고), 이 창 안에서 다시 정렬 편집을 이어갈 방법은
        없다 — 그래서 _export()와 똑같이 last_export_path만 채우고
        accept()해서, 호출부(open_composite_studio)의 '지금 분석할까요?'
        흐름을 그대로 재사용한다."""
        path, _ = QFileDialog.getOpenFileName(
            self, tr("toolbar_composite_import"), self._last_dir,
            tr("composite_file_filter"))
        if not path:
            return
        try:
            load_composite(path)   # 형식 검증만 — 실제 사용은 호출부의 import_composite가 함
        except Exception as ex:
            QMessageBox.warning(self, tr("composite_import_failed_title"), str(ex)); return
        self._last_dir = str(Path(path).parent)
        self.last_export_path = path
        self.accept()

    # ── 스타일 헬퍼 (메인 윈도우 StyleMixin에 의존하지 않도록 자체 보유) ──
    def _group_css(self):
        return (f"QGroupBox{{color:{INKT};border:1px solid {INK3};border-radius:8px;"
                f"margin-top:8px;padding:8px;font-size:11px;font-weight:bold;background:{INK2};}}"
                f"QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 4px;}}")

    def _btn_css(self):
        return (f"QPushButton{{background:{INK3};color:{INKT};border:none;border-radius:6px;"
                f"padding:6px 10px;font-size:11px;}}"
                f"QPushButton:hover{{background:{INKT};color:{INK2};}}")

    def _btn_accent_css(self):
        return (f"QPushButton{{background:{CYAN};color:{INK2};border:none;border-radius:6px;"
                f"padding:8px 12px;font-size:12px;font-weight:bold;}}"
                f"QPushButton:hover{{background:{INKT};}}")

    def _slider_css(self):
        return (f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
                f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
                f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
                f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
