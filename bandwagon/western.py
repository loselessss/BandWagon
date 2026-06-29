"""bandwagon.western

웨스턴 블롯 합성(가시광 + UV 오버레이) 탭 — UI 구성과 상호작용 핸들러.

WesternMixin은 Analyzer(QMainWindow)에 믹스인으로 섞여 들어간다:
    class Analyzer(WesternMixin, QMainWindow): ...
별도 객체가 아니라 메서드 묶음이라, self.gel/self._record_op 같은 메인
윈도우 상태를 그대로 쓸 수 있다.

현재 탭은 비활성화 상태(app.py 탭 목록에서 해당 줄이 주석 처리됨) —
그 줄 주석만 풀면 복구된다."""
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSizePolicy, QSlider, QVBoxLayout,
)

from .dialogs import _dialog_style
from .i18n import tr
from .imaging import (
    blend_for_uv_canvas, blend_visible_uv, downscale_for_preview,
    pil_to_pixmap, warp_uv_to_visible, warp_visible_to_uv,
)
from .theme import CYAN, INK3, INKT, MUTE
from .widgets import GelView, ThumbView


class WesternMixin:
    """가시광/UV 두 이미지를 코너 정렬해 합성하는 탭. 정렬 캔버스 하나에서
    코너 4점을 잡으면서 동시에 라이브 블렌드 미리보기까지 본다(별도 큰
    미리보기 패널 없이 캔버스가 그 역할을 겸함). '적용'하면 블렌드가
    화면용 메인 이미지가 되고, 분석은 UV 단독 그레이스케일로 돈다."""

    def _wb_init_state(self):
        """Analyzer.__init__에서 호출. 합성 관련 상태 중 이 탭 전용인
        것만 여기서 초기화한다(_wb_gray_override/_wb_visible_orig처럼
        편집-기록 재생 엔진이 공유하는 상태는 app.py 쪽에 남아있다)."""
        self._wb_visible_img = None    # 불러온 가시광 원본 (PIL)
        self._wb_uv_img = None         # 불러온 UV 원본 (PIL)

    def _build_tab_wb(self):
        page = self._new_page(); v = QVBoxLayout(page); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)

        info = QLabel(tr("wb_intro"))
        info.setStyleSheet(f"color:{MUTE};font-size:11px;"); info.setWordWrap(True)
        v.addWidget(info)

        # ── 1) 가시광/UV 불러오기 — 빈 썸네일 클릭 → 불러오기/붙여넣기 선택 ──
        load_box = QGroupBox(tr("wb_group_load")); load_box.setStyleSheet(self._group_css())
        load_row = QHBoxLayout(); load_row.setSpacing(10)

        vis_col = QVBoxLayout(); vis_col.setSpacing(4)
        self.wb_thumb_visible = ThumbView(side=96)
        self.wb_thumb_visible.clicked.connect(self._wb_on_thumb_visible_clicked)
        vis_col.addWidget(self.wb_thumb_visible, 0, Qt.AlignHCenter)
        vis_caption = QLabel(tr("wb_caption_visible")); vis_caption.setAlignment(Qt.AlignCenter)
        vis_caption.setStyleSheet(f"color:{MUTE};font-size:10px;")
        vis_col.addWidget(vis_caption)
        load_row.addLayout(vis_col)

        uv_col = QVBoxLayout(); uv_col.setSpacing(4)
        self.wb_thumb_uv = ThumbView(side=96)
        self.wb_thumb_uv.clicked.connect(self._wb_on_thumb_uv_clicked)
        uv_col.addWidget(self.wb_thumb_uv, 0, Qt.AlignHCenter)
        uv_caption = QLabel(tr("wb_caption_uv")); uv_caption.setAlignment(Qt.AlignCenter)
        uv_caption.setStyleSheet(f"color:{MUTE};font-size:10px;")
        uv_col.addWidget(uv_caption)
        load_row.addLayout(uv_col)

        load_box.setLayout(load_row)
        v.addWidget(load_box)
        thumb_hint = QLabel(tr("wb_thumb_click_hint"))
        thumb_hint.setStyleSheet(f"color:{MUTE};font-size:9px;"); thumb_hint.setWordWrap(True)
        v.addWidget(thumb_hint)

        # ── 2) 정렬 캔버스: 코너 지정 + 라이브 블렌드를 한 화면에서 ─────
        corner_box = QGroupBox(tr("wb_group_align")); corner_box.setStyleSheet(self._group_css())
        corner_v = QVBoxLayout(corner_box)
        corner_hint = QLabel(tr("wb_corner_hint"))
        corner_hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); corner_hint.setWordWrap(True)
        corner_v.addWidget(corner_hint)
        self.wb_corner_label = QLabel(tr("corner_count", n=0))
        self.wb_corner_label.setStyleSheet(f"color:{CYAN};font-size:11px;font-family:'DejaVu Sans Mono';")
        corner_v.addWidget(self.wb_corner_label)
        btn_clear_corners = QPushButton(tr("btn_reset_corners")); btn_clear_corners.clicked.connect(self._wb_clear_corners)
        btn_clear_corners.setStyleSheet(self._btn_css())
        corner_v.addWidget(btn_clear_corners)
        v.addWidget(corner_box)

        # 코너 지정용 캔버스(GelView를 corner 모드로 재사용). 배경 픽스맵은
        # 'UV 원본'이 아니라 '가시광을 코너 기준으로 UV 좌표계에 역변환해
        # 얹은 라이브 블렌드'이며, 코너가 바뀔 때마다 다시 계산해 교체한다.
        # 기본 setMinimumSize(420,420)이 이 좁은 패널보다 넓어 가로 스크롤을
        # 유발하므로 setMinimumWidth(0)으로 다시 낮춘다.
        self.wb_gel = GelView()
        self.wb_gel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.wb_gel.setMinimumWidth(0)
        self.wb_gel.setMinimumHeight(220)
        self.wb_gel.set_mode("corner")
        self.wb_gel.cornerChanged.connect(self._wb_on_corner_changed)
        v.addWidget(self.wb_gel, 1)

        # ── 3) 오파시티만 (큰 미리보기 패널 없음 — 위 캔버스가 그 역할) ──
        op_row = QHBoxLayout(); op_row.setSpacing(6)
        op_lbl = QLabel(tr("wb_opacity_label")); op_lbl.setStyleSheet(f"color:{MUTE};font-size:11px;")
        op_row.addWidget(op_lbl)
        self.wb_opacity_slider = QSlider(Qt.Horizontal)
        self.wb_opacity_slider.setRange(0, 100); self.wb_opacity_slider.setValue(60)
        self.wb_opacity_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
            f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
            f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
        self.wb_opacity_slider.valueChanged.connect(self._wb_on_opacity_changed)
        op_row.addWidget(self.wb_opacity_slider, 1)
        v.addLayout(op_row)
        opacity_hint = QLabel(tr("wb_opacity_hint"))
        opacity_hint.setStyleSheet(f"color:{MUTE};font-size:9px;"); opacity_hint.setWordWrap(True)
        v.addWidget(opacity_hint)

        btn_apply = QPushButton(tr("wb_btn_apply")); btn_apply.clicked.connect(self._wb_apply_composite)
        btn_apply.setStyleSheet(self._btn_accent_css())
        v.addWidget(btn_apply)
        apply_hint = QLabel(tr("wb_apply_hint"))
        apply_hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); apply_hint.setWordWrap(True)
        v.addWidget(apply_hint)

        self._add_tab(page, tr("tab_wb"))

    def _wb_pick_image_for(self, target):
        """빈 썸네일 클릭 시 뜨는 선택 다이얼로그(파일 열기/클립보드 붙여넣기).
        target은 "visible" 또는 "uv"."""
        box = self._box(QMessageBox.Question, tr("wb_pick_source_title"),
                         tr("wb_pick_source_msg"), QMessageBox.NoButton)
        btn_file = box.addButton(tr("wb_pick_source_file"), QMessageBox.ActionRole)
        btn_paste = box.addButton(tr("wb_pick_source_paste"), QMessageBox.ActionRole)
        box.addButton(tr("btn_cancel"), QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        img = None
        if clicked is btn_file:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("wb_btn_load_visible") if target == "visible" else tr("wb_btn_load_uv"),
                self._last_dir, "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)")
            if not path:
                return
            try:
                img = Image.open(path).convert("RGB")
            except Exception as ex:
                self._warn(tr("open_failed_title"), str(ex)); return
            self._last_dir = str(Path(path).parent)
        elif clicked is btn_paste:
            img = self._read_clipboard_image()
            if img is None:
                self.status.showMessage(tr("clipboard_empty_msg")); return
        else:
            return  # 취소

        if target == "visible":
            self._wb_visible_img = img
            self.wb_thumb_visible.set_image(img)
        else:
            self._wb_uv_img = img
            self.wb_thumb_uv.set_image(img)
            self.wb_gel.clear_corners()
            self.wb_corner_label.setText(tr("corner_count", n=0))
            self.wb_gel.set_image(pil_to_pixmap(img), img.size)
        self._wb_refresh_canvas()

    def _wb_on_thumb_visible_clicked(self):
        if self._wb_visible_img is None:
            self._wb_pick_image_for("visible")
        else:
            self._wb_show_image_dialog(tr("wb_reference_dialog_title"), self._wb_visible_img)

    def _wb_on_thumb_uv_clicked(self):
        if self._wb_uv_img is None:
            self._wb_pick_image_for("uv")
        else:
            self._wb_show_image_dialog(tr("wb_uv_reference_dialog_title"), self._wb_uv_img)

    def _wb_on_corner_changed(self, n):
        self.wb_corner_label.setText(tr("corner_count", n=n))
        self._wb_refresh_canvas()

    def _wb_clear_corners(self):
        self.wb_gel.clear_corners()
        self.wb_corner_label.setText(tr("corner_count", n=0))
        self._wb_refresh_canvas()

    def _wb_on_opacity_changed(self, v):
        self._wb_refresh_canvas()

    def _wb_refresh_canvas(self):
        """정렬 캔버스(wb_gel)의 배경 픽스맵을 다시 계산해 교체한다(좌표계는
        항상 UV 원본 크기 — set_image는 코너 좌표를 안 건드림).

        UV만 있으면 UV 원본 그대로, 가시광+코너 4점이 다 있으면 가시광을
        코너 기준으로 UV 좌표계에 역변환해 얹은 라이브 블렌드를 보여준다
        (워프 실패 시 조용히 UV 원본으로 복귀).

        큰 이미지에서 워프가 무거울 수 있어 캔버스 크기에 비례해 축소한
        뒤 계산한다(코너도 같은 비율로 축소). '적용' 시 _wb_apply_composite
        가 원본 해상도로 다시 계산하므로 결과 품질엔 영향 없다."""
        if self._wb_uv_img is None:
            return
        corners = self.wb_gel.corners
        canvas_size = self.wb_gel.size()
        uv_small, uv_scale = downscale_for_preview(
            self._wb_uv_img, canvas_size.width(), canvas_size.height())
        if self._wb_visible_img is not None and len(corners) == 4:
            try:
                opacity = self.wb_opacity_slider.value() / 100.0
                corners_small = [(x * uv_scale, y * uv_scale) for x, y in corners]
                vis_on_uv = warp_visible_to_uv(self._wb_visible_img, corners_small, uv_small.size)
                canvas_img = blend_for_uv_canvas(uv_small, vis_on_uv, opacity)
            except Exception:
                canvas_img = uv_small
        else:
            canvas_img = uv_small
        # set_image의 두 번째 인자(_img_size)는 좌표 변환의 기준이라 항상
        # 원본 UV 크기를 넘긴다 — 그림은 작아도 코너 클릭은 원본 좌표로 계산.
        self.wb_gel.set_image(pil_to_pixmap(canvas_img), self._wb_uv_img.size)

    def _wb_apply_composite(self):
        """현재 정렬 상태로 블렌드(화면용)와 UV 단독 그레이스케일(분석용)을
        만들어 메인 이미지로 적용한다. 이후 워크플로우는 평소와 동일하다.

        wb_composite는 '이전 이미지를 변형'하는 연산이 아니라 가시광+UV를
        합쳐 새 이미지를 만드는 특수 연산이다(자세한 내용은
        imaging.apply_edit_op의 wb_composite 분기 참고)."""
        if self._wb_visible_img is None:
            self._info(tr("wb_need_visible_title"), tr("wb_need_visible_msg")); return
        if self._wb_uv_img is None or len(self.wb_gel.corners) != 4:
            self._info(tr("wb_need_uv_corners_title"), tr("wb_need_uv_corners_msg")); return
        try:
            uv_corners = np.array(self.wb_gel.corners, dtype=np.float32)
            warped = warp_uv_to_visible(self._wb_uv_img, uv_corners, self._wb_visible_img.size)
            opacity = self.wb_opacity_slider.value() / 100.0
            blend_visible_uv(self._wb_visible_img, warped, opacity)  # 미리 한 번 돌려 실패를 여기서 잡음
        except Exception as ex:
            self._warn(tr("wb_apply_failed_title"), str(ex)); return

        self._record_op("wb_composite", {
            "visible_img": self._wb_visible_img.copy(),
            "uv_img": self._wb_uv_img.copy(),
            "corners": self.wb_gel.corners,
            "opacity": self.wb_opacity_slider.value() / 100.0,
        })
        self._wb_visible_orig = self._wb_visible_img.copy()  # 참고용으로 보관
        self._after_geometry_change()           # _gray_orig 재계산 시 오버라이드가 자동 적용됨
        self.status.showMessage(tr("status_wb_applied"))

    def _wb_show_image_dialog(self, title, pil_img):
        """가시광/UV 원본을 큰 다이얼로그로 보여주는 헬퍼 — 사진이 이미 있는
        썸네일을 클릭하면 이걸 거친다."""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setStyleSheet(_dialog_style())
        lay = QVBoxLayout(dlg)
        lbl = QLabel(); lbl.setPixmap(pil_to_pixmap(pil_img).scaled(
            700, 700, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(lbl)
        bb = QDialogButtonBox(QDialogButtonBox.Ok); bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec_()

    def _wb_reset_ui(self):
        """'전체 초기화'에서 호출 — 이 탭에서 불러온 사진/코너/캔버스를 모두
        비운다. 탭이 비활성화돼 있으면(wb_gel이 아직 생성 안 됨) 위젯 쪽은
        건드리지 않고 상태만 비운다."""
        self._wb_visible_img = None
        self._wb_uv_img = None
        if hasattr(self, "wb_gel"):
            self.wb_gel.set_image(None, (1, 1)); self.wb_gel.clear_corners()
            self.wb_corner_label.setText(tr("corner_count", n=0))
            self.wb_thumb_visible.set_image(None)
            self.wb_thumb_uv.set_image(None)
