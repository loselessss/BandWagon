"""bandwagon.geometry

GeometryMixin — 색감 보정(밝기/대비/톤커브) + 기하변환(회전/반전/정밀회전/
곡률보정/펴기/코너지정) + 되돌리기·다시하기 엔진을 한 덩어리로 묶었다.
이 셋을 같이 두는 이유: 전부 같은 _record_op/_replay_history 엔진을
공유하고, "보정" 탭(_build_tab_correct) 하나가 이 전부의 UI를 담당하기
때문이다. Analyzer(GeometryMixin, ...)로 섞여 들어간다.

레인 구성(lanes.py의 LanesMixin)도 같은 되돌리기 스택을 쓰지만, 실제
레인 상태(self.lanes)는 LanesMixin이 소유한다 — _replay_history()는
재생 중 만난 가장 최근 'lanes' 연산의 params를 self._apply_lanes_snapshot()
(LanesMixin이 정의)에 넘기기만 하고, 그 내용은 모른다.
"""
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import (
    QGroupBox, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider,
    QSpinBox, QWidget,
)
from PyQt5.QtCore import Qt

from .i18n import tr
from .theme import *
from .meta import HAS_CV2
from .imaging import pil_to_pixmap, downscale_for_preview, apply_bow_correction, apply_shear_correction, apply_edit_op, find_gel_quad
from .models import CurveModel
from .widgets import CurveWidget, ChannelBar, SliderRow


class GeometryMixin:
    # _replay_history()가 레인 구성 기준선을 추적하다가, 이 종류의 연산을
    # 만나면 그 이전 레인 구성은 무효(기하가 바뀌면 레인 x1/x2 좌표가
    # 더는 안 맞으므로 실제로도 자동 초기화됨)라고 보고 리셋한다.
    # "adjust"/"lanes" 자신은 포함하지 않는다.
    _GEOMETRY_OPS = frozenset({
        "rotate", "flip", "invert_colors", "fine_rotate",
        "bow_correct", "shear_correct", "warp",
    })

    def _section_label(self, text):
        """통합 보정 탭의 구역 구분용 소제목 라벨."""
        lab = QLabel(text)
        lab.setStyleSheet(f"color:{CYAN};font-size:11px;font-weight:bold;"
                          f"padding:2px 0;border-bottom:1px solid {LINE2};")
        return lab

    def _build_tab_correct(self):
        """펴기/보정 통합 탭(요청 #3). 기하 보정(회전·펴기·곡률·자르기)을
        먼저, 색감 보정(밝기/대비·반전·커브)을 나중에 배치 — 작업 순서가
        자연스럽게 '기하 먼저, 색감 나중'이 되도록."""
        page = self._new_page(); v = QVBoxLayout(page); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)

        # ===== 기하 보정 =====
        v.addWidget(self._section_label(tr("section_geometry")))

        rot = QGroupBox(tr("group_rotate_flip")); rot.setStyleSheet(self._group_css())
        rv = QVBoxLayout(rot); rv.setSpacing(5)
        row1 = QHBoxLayout(); row1.setSpacing(5)
        for label, fn in [(tr("rotate_left90"), lambda: self._rotate(-90)),
                          (tr("rotate_right90"), lambda: self._rotate(90)),
                          ("180°", lambda: self._rotate(180))]:
            b = QPushButton(label); b.clicked.connect(fn); b.setStyleSheet(self._btn_css()); row1.addWidget(b)
        rv.addLayout(row1)
        row2 = QHBoxLayout(); row2.setSpacing(5)
        for label, fn in [(tr("flip_h"), lambda: self._flip("h")),
                          (tr("flip_v"), lambda: self._flip("v"))]:
            b = QPushButton(label); b.clicked.connect(fn); b.setStyleSheet(self._btn_css()); row2.addWidget(b)
        rv.addLayout(row2)

        # 정밀 회전 (1도 단위) — 드래그하면 바로 적용되는 실시간 미리보기.
        # 별도 적용 버튼 없음: 슬라이더를 놓거나 숫자입력 후 포커스를 옮기면 그 자리에서 확정.
        fine_row = QHBoxLayout(); fine_row.setSpacing(6)
        fine_lbl = QLabel(tr("fine_rotate_label")); fine_lbl.setFixedWidth(28)
        fine_lbl.setStyleSheet(f"color:{MUTE};font-size:11px;")
        fine_row.addWidget(fine_lbl)
        self.rot_slider = QSlider(Qt.Horizontal)
        self.rot_slider.setRange(-180, 180); self.rot_slider.setValue(0)
        self.rot_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
            f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
            f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
        fine_row.addWidget(self.rot_slider, 1)
        self.rot_spin = QSpinBox(); self.rot_spin.setRange(-180, 180); self.rot_spin.setSuffix("°")
        self.rot_spin.setFixedWidth(64); self.rot_spin.setStyleSheet(self._spin_css())
        fine_row.addWidget(self.rot_spin)
        btn_rot_reset = QPushButton(tr("btn_reset")); btn_rot_reset.setStyleSheet(self._btn_css())
        btn_rot_reset.clicked.connect(self._reset_fine_rotation)
        fine_row.addWidget(btn_rot_reset)
        rv.addLayout(fine_row)

        self.rot_slider.valueChanged.connect(self._on_rot_value_changed)
        self.rot_spin.valueChanged.connect(self._on_rot_value_changed)
        self.rot_slider.sliderReleased.connect(self._commit_fine_rotation)
        self.rot_spin.editingFinished.connect(self._commit_fine_rotation)

        fine_note = QLabel(tr("fine_rotate_note"))
        fine_note.setStyleSheet(f"color:{MUTE};font-size:9px;"); fine_note.setWordWrap(True)
        rv.addWidget(fine_note)
        v.addWidget(rot)

        region = QGroupBox(tr("group_region")); region.setStyleSheet(self._group_css())
        rgl = QVBoxLayout(region); rgl.setSpacing(5)
        info = QLabel(tr("warp_intro"))
        info.setStyleSheet(f"color:{MUTE};font-size:11px;"); info.setWordWrap(True)
        rgl.addWidget(info)
        auto = QPushButton(tr("btn_auto_warp")); auto.clicked.connect(self._auto_warp); auto.setStyleSheet(self._btn_accent_css())
        rgl.addWidget(auto)
        sub = QLabel(tr("warp_or_manual_corners")); sub.setStyleSheet(f"color:{MUTE};font-size:10px;"); sub.setAlignment(Qt.AlignCenter)
        rgl.addWidget(sub)
        self.btn_corner = QPushButton(tr("btn_corner_mode_off")); self.btn_corner.setCheckable(True)
        self.btn_corner.clicked.connect(self._toggle_corner_mode); self.btn_corner.setStyleSheet(self._btn_css())
        rgl.addWidget(self.btn_corner)
        order_hint = QLabel(tr("corner_click_order"))
        order_hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); order_hint.setWordWrap(True)
        order_hint.setAlignment(Qt.AlignCenter)
        rgl.addWidget(order_hint)
        self.corner_label = QLabel(tr("corner_count", n=0))
        self.corner_label.setStyleSheet(f"color:{CYAN};font-size:11px;font-family:'DejaVu Sans Mono';")
        self.corner_label.setAlignment(Qt.AlignCenter)
        rgl.addWidget(self.corner_label)
        wrow = QHBoxLayout(); wrow.setSpacing(6)
        wr = QPushButton(tr("btn_apply_warp")); wr.clicked.connect(self._manual_warp); wr.setStyleSheet(self._btn_css())
        wc = QPushButton(tr("btn_reset_corners")); wc.clicked.connect(self._clear_corners); wc.setStyleSheet(self._btn_css())
        wrow.addWidget(wr); wrow.addWidget(wc)
        rgl.addLayout(wrow)
        v.addWidget(region)

        bow = QGroupBox(tr("group_bow_correction")); bow.setStyleSheet(self._group_css())
        bv = QVBoxLayout(bow)
        bow_info = QLabel(tr("bow_correction_info"))
        bow_info.setStyleSheet(f"color:{MUTE};font-size:10px;"); bow_info.setWordWrap(True)
        bv.addWidget(bow_info)
        brow = QHBoxLayout(); brow.setSpacing(6)
        blbl = QLabel(tr("label_curvature")); blbl.setFixedWidth(28); blbl.setStyleSheet(f"color:{MUTE};font-size:11px;")
        brow.addWidget(blbl)
        self.bow_slider = QSlider(Qt.Horizontal)
        self.bow_slider.setRange(-150, 150); self.bow_slider.setValue(0)
        self.bow_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
            f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
            f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
        brow.addWidget(self.bow_slider, 1)
        self.bow_spin = QSpinBox(); self.bow_spin.setRange(-150, 150); self.bow_spin.setSuffix("px")
        self.bow_spin.setFixedWidth(64); self.bow_spin.setStyleSheet(self._spin_css())
        brow.addWidget(self.bow_spin)
        btn_bow_reset = QPushButton(tr("btn_reset")); btn_bow_reset.setStyleSheet(self._btn_css())
        btn_bow_reset.clicked.connect(self._reset_bow_correction)
        brow.addWidget(btn_bow_reset)
        bv.addLayout(brow)
        bow_hint = QLabel(tr("bow_sign_hint"))
        bow_hint.setStyleSheet(f"color:{MUTE};font-size:9px;"); bow_hint.setWordWrap(True)
        bv.addWidget(bow_hint)
        v.addWidget(bow)

        self.bow_slider.valueChanged.connect(self._on_bow_value_changed)
        self.bow_spin.valueChanged.connect(self._on_bow_value_changed)
        self.bow_slider.sliderReleased.connect(self._commit_bow_correction)
        self.bow_spin.editingFinished.connect(self._commit_bow_correction)

        # 기울기(전단) 보정 — bow_correct와 동일한 UI/세션 패턴이되 축이 다르다
        # (bow: 열 기준 세로 포물선 / shear: 행 기준 가로 선형).
        shear = QGroupBox(tr("group_shear_correction")); shear.setStyleSheet(self._group_css())
        shv = QVBoxLayout(shear)
        shear_info = QLabel(tr("shear_correction_info"))
        shear_info.setStyleSheet(f"color:{MUTE};font-size:10px;"); shear_info.setWordWrap(True)
        shv.addWidget(shear_info)
        shrow = QHBoxLayout(); shrow.setSpacing(6)
        shlbl = QLabel(tr("label_shear")); shlbl.setFixedWidth(28); shlbl.setStyleSheet(f"color:{MUTE};font-size:11px;")
        shrow.addWidget(shlbl)
        self.shear_slider = QSlider(Qt.Horizontal)
        self.shear_slider.setRange(-150, 150); self.shear_slider.setValue(0)
        self.shear_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
            f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
            f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
        shrow.addWidget(self.shear_slider, 1)
        self.shear_spin = QSpinBox(); self.shear_spin.setRange(-150, 150); self.shear_spin.setSuffix("px")
        self.shear_spin.setFixedWidth(64); self.shear_spin.setStyleSheet(self._spin_css())
        shrow.addWidget(self.shear_spin)
        btn_shear_reset = QPushButton(tr("btn_reset")); btn_shear_reset.setStyleSheet(self._btn_css())
        btn_shear_reset.clicked.connect(self._reset_shear_correction)
        shrow.addWidget(btn_shear_reset)
        shv.addLayout(shrow)
        shear_hint = QLabel(tr("shear_sign_hint"))
        shear_hint.setStyleSheet(f"color:{MUTE};font-size:9px;"); shear_hint.setWordWrap(True)
        shv.addWidget(shear_hint)
        v.addWidget(shear)

        self.shear_slider.valueChanged.connect(self._on_shear_value_changed)
        self.shear_spin.valueChanged.connect(self._on_shear_value_changed)
        self.shear_slider.sliderReleased.connect(self._commit_shear_correction)
        self.shear_spin.editingFinished.connect(self._commit_shear_correction)


        # ===== 색감 보정 =====
        v.addWidget(self._section_label(tr("section_color")))

        # 드래그 중(valueChanged)에는 캔버스 크기 축소본에만 색보정을 적용해
        # 가볍게 미리보기하고(_refresh_display(preview=True)), 슬라이더를 놓으면
        # (released) 원본 해상도로 확정한다. valueChanged(int)가 넘기는 슬라이더
        # 값이 preview 인자에 잘못 들어가지 않도록 람다로 감싼다.
        self.sl_bright = SliderRow(tr("slider_brightness"), -100, 100, 0)
        self.sl_bright.valueChanged.connect(lambda _=None: self._refresh_display(preview=True))
        self.sl_contrast = SliderRow(tr("slider_contrast"), -100, 100, 0)
        self.sl_contrast.valueChanged.connect(lambda _=None: self._refresh_display(preview=True))
        self.sl_bright.released.connect(self._commit_adjust)
        self.sl_contrast.released.connect(self._commit_adjust)
        v.addWidget(self.sl_bright); v.addWidget(self.sl_contrast)
        invert_row = QHBoxLayout(); invert_row.setSpacing(6)
        btn_invert = QPushButton(tr("btn_invert_colors")); btn_invert.clicked.connect(self._invert_colors)
        btn_invert.setStyleSheet(self._btn_css())
        invert_row.addWidget(btn_invert)
        invert_hint = QLabel(tr("invert_hint"))
        invert_hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); invert_hint.setWordWrap(True)
        invert_row.addWidget(invert_hint, 1)
        v.addLayout(invert_row)
        # 고정크기 위젯을 alignment로 직접 넣으면 Qt5.15/Windows에서 위젯 주변에
        # 갱신 안 되는 죽은 영역이 생겨 흰배경으로 남는다. 컨테이너로 감싸 중앙 배치.
        ch_wrap = QWidget(); ch_h = QHBoxLayout(ch_wrap)
        ch_h.setContentsMargins(0, 0, 0, 0); ch_h.addStretch()
        self.channel_bar = ChannelBar(); self.channel_bar.channelChanged.connect(self._switch_channel)
        ch_h.addWidget(self.channel_bar); ch_h.addStretch()
        v.addWidget(ch_wrap)
        cv_wrap = QWidget(); cv_h = QHBoxLayout(cv_wrap)
        cv_h.setContentsMargins(0, 0, 0, 0); cv_h.addStretch()
        self.curve = CurveWidget("RGB"); self.curve.changed.connect(self._on_curve_changed)
        self.curve.released.connect(self._commit_adjust)
        cv_h.addWidget(self.curve); cv_h.addStretch()
        v.addWidget(cv_wrap)
        brow = QHBoxLayout(); brow.setSpacing(6)
        bc = QPushButton(tr("btn_reset_curve")); bc.clicked.connect(self._reset_curve); bc.setStyleSheet(self._btn_css())
        ba = QPushButton(tr("btn_reset_adjust_all")); ba.clicked.connect(self._reset_adjust); ba.setStyleSheet(self._btn_css())
        brow.addWidget(bc); brow.addWidget(ba)
        v.addLayout(brow)
        note = QLabel(tr("adjust_display_only_note"))
        note.setStyleSheet(f"color:{MUTE};font-size:10px;"); note.setWordWrap(True)
        v.addWidget(note)

        v.addStretch()
        self._add_tab(page, tr("tab_adjust"))

    def _on_curve_changed(self):
        # 커브 점을 드래그하는 중(changed) — 축소본에만 적용해 가볍게 미리보기.
        # 점 편집을 끝내면(curve.released → _commit_adjust) 원본 해상도로 확정된다.
        self.curves[self._ch] = self.curve.model
        self._refresh_display(preview=True)

    def _reset_curve(self):
        self.curves[self._ch].reset()
        self.curve.model = self.curves[self._ch]
        self.curve._sel = None
        self.curve.update()
        self._refresh_display()
        self._commit_adjust()

    def _reset_adjust(self):
        self.sl_bright.setValue(0); self.sl_contrast.setValue(0)
        for m in self.curves.values(): m.reset()
        self.curve.model = self.curves[self._ch]; self.curve._sel = None
        self.curve.update()
        self._refresh_display()
        self._commit_adjust()

    def _hist_for(self, ch):
        if self._orig is None:
            return None
        arr = np.array(self._orig.convert("RGB"))
        if ch == "RGB": flat = arr.mean(axis=2).ravel()
        elif ch == "Red": flat = arr[:, :, 0].ravel()
        elif ch == "Green": flat = arr[:, :, 1].ravel()
        else: flat = arr[:, :, 2].ravel()
        h, _ = np.histogram(flat.astype(np.uint8), bins=256, range=(0, 256))
        mx = h.max()
        return h.astype(float) / mx if mx else h.astype(float)

    def _apply_color_pipeline(self, base_img):
        """base_img(PIL RGB)에 현재 밝기/대비/톤커브를 적용한 새 PIL 이미지를
        반환한다. 순수 함수 — self._display 등 상태를 건드리지 않으므로
        원본 해상도(확정)와 축소본(드래그 미리보기) 양쪽에 그대로 쓴다."""
        arr = np.asarray(base_img.convert("RGB"), dtype=np.float32)
        arr = arr + float(self.sl_bright.value())
        c = float(self.sl_contrast.value())
        f = (259 * (c + 255)) / (255 * (259 - c)) if c != 255 else 10.0
        arr = np.clip(f * (arr - 128) + 128, 0, 255).astype(np.uint8)
        arr = self.curves["RGB"].lut()[arr]
        for i, ch in enumerate(("Red", "Green", "Blue")):
            arr[:, :, i] = self.curves[ch].lut()[arr[:, :, i]]
        return Image.fromarray(arr, "RGB")

    def _refresh_display(self, preview=False):
        """색보정 결과를 캔버스에 반영한다.

        preview=True(슬라이더/커브 드래그 중): 캔버스 크기에 맞춰 미리 줄인
        축소본(_color_preview_base)에만 파이프라인을 적용해 매 프레임 전체
        해상도 이미지를 재변환하는 렉을 없앤다. self._display(분석/저장에
        쓰는 확정 이미지)는 건드리지 않는다.

        preview=False(놓았을 때/되돌리기/파일 로드 등): 원본 해상도로 계산해
        self._display를 확정한다."""
        if self._orig is None:
            return
        if preview:
            if getattr(self, "_color_preview_base", None) is None:
                cs = self.gel.size()
                self._color_preview_base, _ = downscale_for_preview(
                    self._orig, cs.width(), cs.height())
            out = self._apply_color_pipeline(self._color_preview_base)
        else:
            self._color_preview_base = None   # 확정했으니 축소 캐시 폐기
            out = self._apply_color_pipeline(self._orig)
            self._display = out
        self.gel.set_image(pil_to_pixmap(out), out.size)
        self.status.showMessage(
            tr("status_image_info", w=self._orig.width, h=self._orig.height,
               bright=self.sl_bright.value(), contrast=self.sl_contrast.value()))

    def _rotate(self, deg):
        if self._orig is None: return
        self._finalize_pending_rotation()
        self._finalize_pending_bow()
        self._finalize_pending_shear()
        self._record_op("rotate", {"deg": deg})
        self._after_geometry_change()

    def _flip(self, d):
        if self._orig is None: return
        self._finalize_pending_rotation()
        self._finalize_pending_bow()
        self._finalize_pending_shear()
        self._record_op("flip", {"dir": d})
        self._after_geometry_change()

    def _invert_colors(self):
        """색상을 반전한다(예: 어두운 배경 위 밝은 밴드로 스캔된 이미지를
        통상적인 밝은 배경/짙은 밴드 형태로 바꿀 때 사용). 밝기·대비와는
        달리 원본 자체를 바꾸므로 밴드 검출 결과에도 실제로 영향을 준다.
        그래서 회전/반전과 같은 '확정 변환'으로 취급해 되돌리기 기록에 남긴다."""
        if self._orig is None: return
        self._finalize_pending_rotation()
        self._finalize_pending_bow()
        self._finalize_pending_shear()
        self._record_op("invert_colors", {})
        self._after_geometry_change()
        self.status.showMessage(tr("status_color_inverted"))

    def _on_rot_value_changed(self, v):
        """슬라이더/스핀박스 동기화 + 라이브 미리보기. v는 세션 기준
        이미지(_rot_base) 대비 절대각 — release해도 슬라이더가 0으로
        안 돌아가야 표시값과 실제 회전 상태가 항상 일치한다.

        드래그 중엔 self._orig을 안 건드리고 다운스케일 미리보기만 그린다
        (저품질 상태가 분석/저장에 쓰이는 걸 방지). _orig 갱신은 release
        시(_commit_fine_rotation)에 원본 해상도로만 한다."""
        if self.rot_slider.value() != v:
            self.rot_slider.blockSignals(True); self.rot_slider.setValue(v); self.rot_slider.blockSignals(False)
        if self.rot_spin.value() != v:
            self.rot_spin.blockSignals(True); self.rot_spin.setValue(v); self.rot_spin.blockSignals(False)
        if self._orig is None:
            return
        if self._rot_base is None:
            if v == 0:
                return
            self._rot_base = self._orig.copy()
            self._rot_session_pushed = False
            canvas_size = self.gel.size()
            self._preview_small, self._preview_scale = downscale_for_preview(
                self._rot_base, canvas_size.width(), canvas_size.height())
        # expand=False: 캔버스 크기 유지, 모서리만 살짝 잘림(흰 배경이
        # 계속 늘어나는 걸 방지). v==0이면 _rot_base 자체를 보여준다 —
        # 이미 한 번 커밋했다면 self._orig엔 이전 각도가 baked-in이라
        # 그대로 그리면 0인데 그림은 돌아간 채로 보이는 불일치가 생긴다.
        preview = self._preview_small if v == 0 else self._preview_small.rotate(
            -v, resample=Image.BILINEAR, expand=False, fillcolor=(255, 255, 255))
        self.gel.set_image(pil_to_pixmap(preview), preview.size)
        self.status.showMessage(
            tr("status_image_info", w=self._orig.width, h=self._orig.height,
               bright=self.sl_bright.value(), contrast=self.sl_contrast.value()))

    def _apply_fine_rotation(self, deg):
        """세션의 절대 각도(deg, _rot_base 기준)를 연산 기록에 반영한다.
        같은 세션의 여러 커밋은 _rot_base가 고정 기준선이므로 새 연산을
        쌓지 않고 이번 세션 몫의 항목 하나만 교체한다(더하면 틀어짐).
        deg=0이면 이번 세션 기록이 있을 때 그 항목만 지운다."""
        if deg == 0:
            if self._rot_session_pushed:
                del self._edit_ops[self._edit_pos]
                self._edit_pos -= 1
                self._rot_session_pushed = False
                self._replay_history()
                if hasattr(self, "btn_undo"):
                    self.btn_undo.setEnabled(self._edit_pos >= 0)
            return
        if self._rot_session_pushed:
            self._edit_ops[self._edit_pos] = ("fine_rotate", {"deg": deg})
            self._replay_history()
        else:
            self._record_op("fine_rotate", {"deg": deg})
            self._rot_session_pushed = True

    def _finalize_pending_rotation(self):
        """정밀 회전 세션을 완전히 끝낸다 — 다른 작업(코너 지정/되돌리기/
        곡률보정 등)으로 넘어가기 전에 호출되어, release 전 각도까지
        확정 기록한다. _apply_fine_rotation() 안에서 결국 _replay_history()가
        돌면서 _sync_geom_sliders()가 슬라이더를 현재 값으로 맞춰주므로,
        여기서 슬라이더를 0으로 강제로 되돌리지 않는다 — 예전엔 그렇게
        했었는데, 그러면 값은 실제로 적용된 채(0이 아님) 슬라이더만 0으로
        보이는 불일치가 생겼다(다른 모드로 넘어갈 때마다 재현되던 버그).

        이미 이 값 그대로 커밋돼 있으면(=재생으로 세션이 막 복원된 직후
        다른 모드로 또 넘어가는 경우) 다시 적용하지 않는다 — 안 그러면
        모드를 바꿀 때마다 매번 불필요하게 재계산해, 이미 적용된 보정이
        한 번 더 적용되는 것처럼(실제로는 같은 결과를 다시 그리는 것뿐
        이지만) 보이는 깜빡임이 생긴다."""
        if self._rot_base is None:
            return
        v = self.rot_slider.value()
        if self._rot_session_pushed and self._edit_pos >= 0 \
                and self._edit_ops[self._edit_pos] == ("fine_rotate", {"deg": v}):
            return
        self._apply_fine_rotation(v)
        self._preview_small = None
        self._preview_scale = 1.0

    def _commit_fine_rotation(self):
        """슬라이더 release(또는 입력 완료) 시 호출. 고품질로 다시 렌더해
        _orig/분석 데이터에 반영한다. 세션은 끝내지 않아 슬라이더가 현재
        각도를 계속 보여준다 — 같은 자리에서 다시 드래그하면 여전히
        이번 _rot_base를 기준으로 절대각을 계산한다."""
        if self._rot_base is None:
            return
        self._finalize_pending_bow()
        self._finalize_pending_shear()
        deg = self.rot_slider.value()
        self._apply_fine_rotation(deg)
        if deg == 0:
            # 기준선으로 완전히 돌아왔으니 세션도 같이 종료
            self._rot_base = None
            self._preview_small = None
            self._preview_scale = 1.0
            self._rot_session_pushed = False
        self._refresh_after_pixels_changed()
        if deg == 0:
            self.status.showMessage(tr("status_fine_rotation_reset"))
        else:
            self.status.showMessage(tr("status_fine_rotation_applied"))

    def _reset_fine_rotation(self):
        """정밀 회전을 0°로 되돌린다 — 드래그 중이든 커밋을 마쳤든 세션
        시작 시점(_rot_base)으로 완전히 복귀한다."""
        if self._rot_base is None:
            self.rot_slider.setValue(0)
            return
        self._apply_fine_rotation(0)
        self._rot_base = None
        self._preview_small = None
        self._preview_scale = 1.0
        self._rot_session_pushed = False
        self.rot_slider.blockSignals(True); self.rot_slider.setValue(0); self.rot_slider.blockSignals(False)
        self.rot_spin.blockSignals(True); self.rot_spin.setValue(0); self.rot_spin.blockSignals(False)
        self._refresh_after_pixels_changed()
        self.status.showMessage(tr("status_fine_rotation_reset"))

    @staticmethod
    def _apply_bow_correction(img, amount):
        return apply_bow_correction(img, amount)

    def _on_bow_value_changed(self, v):
        """_on_rot_value_changed와 동일한 패턴(곡률보정판). v는 세션
        기준(_curve_base) 대비 절대 휨 정도(px)이며, release해도 유지된다."""
        if self.bow_slider.value() != v:
            self.bow_slider.blockSignals(True); self.bow_slider.setValue(v); self.bow_slider.blockSignals(False)
        if self.bow_spin.value() != v:
            self.bow_spin.blockSignals(True); self.bow_spin.setValue(v); self.bow_spin.blockSignals(False)
        if self._orig is None:
            return
        if self._curve_base is None:
            if v == 0:
                return
            self._curve_base = self._orig.copy()
            self._bow_session_pushed = False
            canvas_size = self.gel.size()
            self._preview_small, self._preview_scale = downscale_for_preview(
                self._curve_base, canvas_size.width(), canvas_size.height())
        # amount는 원본 px 단위라 미리보기 비율(_preview_scale)로 맞춰
        # 줄인다. v==0이면 _curve_base 자체를 보여준다(이유는 위 회전
        # 버전 참고 — self._orig엔 이전 곡률이 baked-in일 수 있음).
        preview = self._preview_small if v == 0 else self._apply_bow_correction(
            self._preview_small, v * self._preview_scale)
        self.gel.set_image(pil_to_pixmap(preview), preview.size)
        self.status.showMessage(
            tr("status_image_info", w=self._orig.width, h=self._orig.height,
               bright=self.sl_bright.value(), contrast=self.sl_contrast.value()))

    def _apply_bow_op(self, amount):
        """_apply_fine_rotation과 동일한 절대값-교체 로직(곡률보정판)."""
        if amount == 0:
            if self._bow_session_pushed:
                del self._edit_ops[self._edit_pos]
                self._edit_pos -= 1
                self._bow_session_pushed = False
                self._replay_history()
                if hasattr(self, "btn_undo"):
                    self.btn_undo.setEnabled(self._edit_pos >= 0)
            return
        if self._bow_session_pushed:
            self._edit_ops[self._edit_pos] = ("bow_correct", {"amount": amount})
            self._replay_history()
        else:
            self._record_op("bow_correct", {"amount": amount})
            self._bow_session_pushed = True

    def _finalize_pending_bow(self):
        """_finalize_pending_rotation과 동일한 역할(곡률보정판)."""
        if self._curve_base is None:
            return
        v = self.bow_slider.value()
        if self._bow_session_pushed and self._edit_pos >= 0 \
                and self._edit_ops[self._edit_pos] == ("bow_correct", {"amount": v}):
            return
        self._apply_bow_op(v)
        self._preview_small = None
        self._preview_scale = 1.0

    def _commit_bow_correction(self):
        """_commit_fine_rotation과 동일한 역할(곡률보정판) — 세션을
        끝내지 않아 슬라이더가 현재 값을 계속 보여준다."""
        if self._curve_base is None:
            return
        self._finalize_pending_rotation()
        self._finalize_pending_shear()
        amount = self.bow_slider.value()
        self._apply_bow_op(amount)
        if amount == 0:
            self._curve_base = None
            self._preview_small = None
            self._preview_scale = 1.0
            self._bow_session_pushed = False
        self._refresh_after_pixels_changed()
        if amount == 0:
            self.status.showMessage(tr("status_bow_reset"))
        else:
            self.status.showMessage(tr("status_bow_applied"))

    def _reset_bow_correction(self):
        """_reset_fine_rotation과 동일한 역할(곡률보정판)."""
        if self._curve_base is None:
            self.bow_slider.setValue(0)
            return
        self._apply_bow_op(0)
        self._curve_base = None
        self._preview_small = None
        self._preview_scale = 1.0
        self._bow_session_pushed = False
        self.bow_slider.blockSignals(True); self.bow_slider.setValue(0); self.bow_slider.blockSignals(False)
        self.bow_spin.blockSignals(True); self.bow_spin.setValue(0); self.bow_spin.blockSignals(False)
        self._refresh_after_pixels_changed()
        self.status.showMessage(tr("status_bow_reset"))

    @staticmethod
    def _apply_shear_correction(img, amount):
        return apply_shear_correction(img, amount)

    def _on_shear_value_changed(self, v):
        """_on_bow_value_changed와 동일한 패턴(기울기보정판). v는 세션
        기준(_shear_base) 대비 절대 이동량(px)이며, release해도 유지된다."""
        if self.shear_slider.value() != v:
            self.shear_slider.blockSignals(True); self.shear_slider.setValue(v); self.shear_slider.blockSignals(False)
        if self.shear_spin.value() != v:
            self.shear_spin.blockSignals(True); self.shear_spin.setValue(v); self.shear_spin.blockSignals(False)
        if self._orig is None:
            return
        if self._shear_base is None:
            if v == 0:
                return
            self._shear_base = self._orig.copy()
            self._shear_session_pushed = False
            canvas_size = self.gel.size()
            self._preview_small, self._preview_scale = downscale_for_preview(
                self._shear_base, canvas_size.width(), canvas_size.height())
        # amount는 원본 px 단위라 미리보기 비율(_preview_scale)로 맞춰 줄인다.
        # v==0이면 _shear_base 자체를 보여준다(이유는 회전/곡률보정 버전과 동일
        # — self._orig엔 이전 기울기가 baked-in일 수 있음).
        preview = self._preview_small if v == 0 else self._apply_shear_correction(
            self._preview_small, v * self._preview_scale)
        self.gel.set_image(pil_to_pixmap(preview), preview.size)
        self.status.showMessage(
            tr("status_image_info", w=self._orig.width, h=self._orig.height,
               bright=self.sl_bright.value(), contrast=self.sl_contrast.value()))

    def _apply_shear_op(self, amount):
        """_apply_bow_op과 동일한 절대값-교체 로직(기울기보정판)."""
        if amount == 0:
            if self._shear_session_pushed:
                del self._edit_ops[self._edit_pos]
                self._edit_pos -= 1
                self._shear_session_pushed = False
                self._replay_history()
                if hasattr(self, "btn_undo"):
                    self.btn_undo.setEnabled(self._edit_pos >= 0)
            return
        if self._shear_session_pushed:
            self._edit_ops[self._edit_pos] = ("shear_correct", {"amount": amount})
            self._replay_history()
        else:
            self._record_op("shear_correct", {"amount": amount})
            self._shear_session_pushed = True

    def _finalize_pending_shear(self):
        """_finalize_pending_bow와 동일한 역할(기울기보정판)."""
        if self._shear_base is None:
            return
        v = self.shear_slider.value()
        if self._shear_session_pushed and self._edit_pos >= 0 \
                and self._edit_ops[self._edit_pos] == ("shear_correct", {"amount": v}):
            return
        self._apply_shear_op(v)
        self._preview_small = None
        self._preview_scale = 1.0

    def _commit_shear_correction(self):
        """_commit_bow_correction과 동일한 역할(기울기보정판) — 세션을
        끝내지 않아 슬라이더가 현재 값을 계속 보여준다."""
        if self._shear_base is None:
            return
        self._finalize_pending_rotation()
        self._finalize_pending_bow()
        amount = self.shear_slider.value()
        self._apply_shear_op(amount)
        if amount == 0:
            self._shear_base = None
            self._preview_small = None
            self._preview_scale = 1.0
            self._shear_session_pushed = False
        self._refresh_after_pixels_changed()
        if amount == 0:
            self.status.showMessage(tr("status_shear_reset"))
        else:
            self.status.showMessage(tr("status_shear_applied"))

    def _reset_shear_correction(self):
        """_reset_bow_correction과 동일한 역할(기울기보정판)."""
        if self._shear_base is None:
            self.shear_slider.setValue(0)
            return
        self._apply_shear_op(0)
        self._shear_base = None
        self._preview_small = None
        self._preview_scale = 1.0
        self._shear_session_pushed = False
        self.shear_slider.blockSignals(True); self.shear_slider.setValue(0); self.shear_slider.blockSignals(False)
        self.shear_spin.blockSignals(True); self.shear_spin.setValue(0); self.shear_spin.blockSignals(False)
        self._refresh_after_pixels_changed()
        self.status.showMessage(tr("status_shear_reset"))

    def _refresh_after_pixels_changed(self):
        """픽셀이 바뀌면 코너/자르기 선택을 비우고 분석용 그레이스케일·
        히스토그램을 다시 계산한다. 커브/밝기/대비, 정밀회전 기준선, 레인은
        건드리지 않는다 — 레인은 _record_op()가 먼저 호출하는
        _replay_history()(=_apply_lanes_snapshot)가 이미 올바른 상태로
        맞춰놓은 뒤이므로, 여기서 또 비우면 막 복원한 레인을 덮어써 버린다
        (기하변환을 만나면 레인 기준선이 비워지는 동작 자체는
        _GEOMETRY_OPS 리셋 규칙으로 그대로 재현된다). 화면 줌/팬은
        기본값으로 되돌린다."""
        self.gel.clear_corners()
        self.gel.clear_crop()
        self.gel.clear_vrange()
        self.gel.reset_zoom()
        self.corner_label.setText(tr("corner_count", n=0))
        # WB 합성 모드는 화면(_orig)엔 가시광+UV 블렌드가 보이지만 분석은
        # UV 단독 강도로 해야 하므로, _wb_gray_override가 있으면 그걸 쓴다.
        if self._wb_gray_override is not None:
            self._gray_orig = self._wb_gray_override
        else:
            self._gray_orig = np.array(self._orig.convert("L"), dtype=np.uint8)
        self._update_vrange_label()   # _gray_orig가 확정된 뒤라야 전체 높이(H)가 맞게 표시됨
        self.curve.set_histogram(self._hist_for(self._ch))
        self._refresh_display()

    def _record_op(self, op_name, params):
        """편집 연산 하나를 기록하고 처음부터 재생해 _orig을 갱신한다 —
        그래야 _orig이 항상 '재생 결과'라는 불변식이 깨지지 않는다.
        현재 위치보다 미래의 연산(되돌리기 후 새로 편집한 경우의 옛
        다시하기 가지)은 여기서 잘라낸다(표준 undo/redo 동작)."""
        if self._edit_pristine is None:
            # pristine이 아직 없으면(막 불러온 직후 등) 현재 _orig을 새
            # pristine으로 놓고 기록을 새로 시작한다.
            if self._orig is None:
                return
            self._edit_pristine = self._orig.copy()
            # 이 시점의 UV 오버라이드(합성 임포트 세션이면 존재)를 재생
            # 시작 그레이스케일로 함께 고정한다 — 없으면 None(평소 세션).
            self._edit_gray_pristine = (
                self._wb_gray_override.copy() if self._wb_gray_override is not None else None)
            self._edit_ops = []
            self._edit_pos = -1
        del self._edit_ops[self._edit_pos + 1:]   # 다시하기 가지 제거
        # 정밀회전/곡률보정의 세션 내 교체는 _apply_fine_rotation()/
        # _apply_bow_op()이 직접 처리하므로(_rot_session_pushed 등으로
        # 세션 경계 추적), 여기서는 모든 연산을 그냥 추가만 한다.
        self._edit_ops.append((op_name, params))
        self._edit_pos += 1
        if len(self._edit_ops) > self._EDIT_MAX:
            # 가장 오래된 연산을 pristine에 영구히 합쳐 리스트에서 제거한다
            # — 기록이 무한히 늘지 않으면서도 남은 연산은 항상 pristine
            # 기준으로 재생 가능하다는 불변식이 유지된다.
            oldest_op, oldest_params = self._edit_ops.pop(0)
            # 가장 오래된 연산을 pristine에 합칠 때, 재생 시작 그레이스케일
            # 오버라이드도 같은 연산으로 함께 변환해야 정렬이 유지된다
            # (합성 임포트 세션에서만 _edit_gray_pristine이 non-None).
            self._edit_pristine, self._edit_gray_pristine = apply_edit_op(
                self._edit_pristine, self._edit_gray_pristine, oldest_op, oldest_params)
            self._edit_pos -= 1
            if oldest_op == "adjust":
                # 폐기되는 adjust가 남아있던 adjust 기록 중 가장 오래된
                # 것이었다면, 그게 이제 새 기준값이 된다(없으면 무해).
                self._adjust_pristine = oldest_params
            elif oldest_op == "lanes":
                self._lanes_pristine = oldest_params["lanes"]
        self._replay_history()
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(self._edit_pos >= 0)
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(False)  # 새로 편집했으니 다시하기 가지는 없음

    def _replay_history(self):
        """_edit_pristine부터 _edit_ops[:_edit_pos+1]을 순서대로 다시 적용해
        self._orig(과 분석용 그레이스케일 오버라이드)을 재계산한다. 되돌리기·
        다시하기·연산 추가 후 항상 거쳐야 _orig이 최신 상태가 된다.
        합성 파일을 임포트한 세션이면 재생 시작 그레이스케일 오버라이드가
        _edit_gray_pristine에 있어, 기하 연산이 이미지와 함께 그 오버라이드도
        변환하며 분석용 UV 정렬을 유지한다(평소 세션에서는 None으로 시작).

        'adjust'(밝기/대비/톤커브) 연산은 픽셀을 안 바꾸지만, 재생 범위
        안에서 가장 마지막으로 만난 것을 기억해 슬라이더/커브 위젯에
        반영한다(_apply_adjust_snapshot) — 그래야 되돌리기/다시하기가
        색감 보정도 다른 편집과 똑같이 한 단계로 다룬다.

        'lanes'(레인 구성)도 같은 방식으로 추적하되, _GEOMETRY_OPS에 속한
        연산을 만나면 그 이전 레인 기록은 버린다(=None) — 기하가 바뀌면
        레인 좌표가 더는 안 맞아 실제로도 자동 초기화되므로, 되돌리기로
        그 시점에 갈 때도 같은 결과(레인 없음 또는 그 이후에 다시 잡은
        레인)가 나와야 한다.

        정밀회전/곡률(부채꼴)/기울기 보정 슬라이더도 마지막(=_edit_pos)
        연산이 그 종류일 때만 값을 보여주고, 그 직전 이미지를 세션
        기준(_rot_base 등)으로 다시 세워둔다(_sync_geom_sliders) — 이걸
        안 하면 되돌리기로 곡률보정이 적용된 지점에 왔을 때 이미지는
        보정된 채인데 슬라이더만 0으로 보이는 불일치가 생긴다(실사용
        중 발견된 버그)."""
        if self._edit_pristine is None:
            return
        img = self._edit_pristine
        # 재생 시작 그레이스케일 오버라이드 — 보통은 None이지만, 합성 파일을
        # 임포트한 세션에서는 편집 시작 시점의 UV 단독 강도가 여기에 고정돼
        # 있어(_edit_gray_pristine), 이후 기하 연산이 apply_edit_op을 통해
        # 이 값도 함께 변환하며 정렬을 유지한다.
        gray = self._edit_gray_pristine
        adjust_snapshot = None
        lanes_snapshot = None
        # 회전/곡률/기울기는 각자 "가장 마지막으로 만난 값"을 따로 기억한다
        # (adjust_snapshot과 동일한 원리) — 예전엔 '진짜 마지막 연산'일 때만
        # 값을 보여줘서, 기울기 보정 뒤에 커브 하나만 더 만져도(마지막
        # 연산이 'adjust'가 되어) 기울기 슬라이더가 0으로 보이는 버그가
        # 있었다. 실제 이미지엔 기울기가 여전히 적용돼 있는데 슬라이더만
        # 거짓으로 0을 보여주는 불일치였다(실사용 중 보고됨).
        last_rot = None
        last_bow = None
        last_shear = None
        ops = self._edit_ops[: self._edit_pos + 1]
        pre_last_img = None
        n = len(ops)
        for i, (op_name, params) in enumerate(ops):
            if i == n - 1:
                pre_last_img = img   # 마지막 연산을 적용하기 '직전' 상태 — 세션 기준으로 재사용
            img, gray = apply_edit_op(img, gray, op_name, params)
            if op_name == "adjust":
                adjust_snapshot = params
            elif op_name == "lanes":
                lanes_snapshot = params
            elif op_name in self._GEOMETRY_OPS:
                lanes_snapshot = None
            if op_name == "fine_rotate":
                last_rot = params
            elif op_name == "bow_correct":
                last_bow = params
            elif op_name == "shear_correct":
                last_shear = params
        self._orig = img
        self._wb_gray_override = gray
        self._apply_adjust_snapshot(adjust_snapshot)
        self._apply_lanes_snapshot(lanes_snapshot)
        last_op = ops[-1][0] if ops else None
        self._sync_geom_sliders(last_op, last_rot, last_bow, last_shear, pre_last_img)

    def _sync_geom_sliders(self, last_op, last_rot, last_bow, last_shear, pre_last_img):
        """정밀회전/곡률/기울기 슬라이더 표시값을 각자 마지막으로 적용된
        값으로 맞춘다 — 다른 종류의 연산(색감 보정 등)을 나중에 해도 이미
        적용된 값이 그대로 보여야 한다(입력값을 건드리면 안 됨).

        '라이브로 이어서 드래그 가능한 세션' 상태(_rot_base 등)는 그 셋
        중 하나가 진짜 마지막 연산일 때만 연다 — 그래야 드래그 기준
        이미지(직전 상태)를 정확히 알 수 있다. 마지막이 아니면 표시값만
        보여주고 세션은 닫아둔다(그 자리에서 다시 드래그하면 새 연산으로
        기록됨 — 이미 다른 연산이 그 위에 쌓인 뒤라 이전 세션을 이어서
        고쳐 쓸 수 없기 때문)."""
        if not hasattr(self, "rot_slider"):
            return   # UI가 아직 만들어지기 전(이론상 도달 안 함) 방어

        rot_deg = last_rot["deg"] if last_rot else 0
        self._rot_base = pre_last_img if last_op == "fine_rotate" else None
        self._rot_session_pushed = last_op == "fine_rotate"
        self.rot_slider.blockSignals(True); self.rot_slider.setValue(rot_deg); self.rot_slider.blockSignals(False)
        self.rot_spin.blockSignals(True); self.rot_spin.setValue(rot_deg); self.rot_spin.blockSignals(False)

        bow_amt = last_bow["amount"] if last_bow else 0
        self._curve_base = pre_last_img if last_op == "bow_correct" else None
        self._bow_session_pushed = last_op == "bow_correct"
        self.bow_slider.blockSignals(True); self.bow_slider.setValue(bow_amt); self.bow_slider.blockSignals(False)
        self.bow_spin.blockSignals(True); self.bow_spin.setValue(bow_amt); self.bow_spin.blockSignals(False)

        shear_amt = last_shear["amount"] if last_shear else 0
        self._shear_base = pre_last_img if last_op == "shear_correct" else None
        self._shear_session_pushed = last_op == "shear_correct"
        self.shear_slider.blockSignals(True); self.shear_slider.setValue(shear_amt); self.shear_slider.blockSignals(False)
        self.shear_spin.blockSignals(True); self.shear_spin.setValue(shear_amt); self.shear_spin.blockSignals(False)

    def _commit_adjust(self):
        """밝기/대비/톤커브 조정을 되돌리기 스택에 한 단계로 기록한다.
        슬라이더를 놓거나(release) 커브 점 편집을 끝냈을 때만 호출되므로
        (widgets.SliderRow/CurveWidget의 released 신호), 드래그 중 매
        프레임마다 기록이 쌓이지 않는다."""
        if self._orig is None:
            return
        self._record_op("adjust", {
            "bright": self.sl_bright.value(),
            "contrast": self.sl_contrast.value(),
            "curves": {ch: m.to_dict() for ch, m in self.curves.items()},
        })

    def _snapshot_adjust_baseline(self):
        """현재 밝기/대비/톤커브 값을 '이 세션의 adjust 기록 없음' 기준값으로
        저장한다. _reset_session_state(새 이미지 시작)와 open_project(저장된
        값 복원) 직후에 호출 — 그래야 되돌리기로 adjust 기록이 하나도 없는
        지점까지 가면 0/0/항등이 아니라 이 기준값으로 정확히 복귀한다."""
        self._adjust_pristine = {
            "bright": self.sl_bright.value(),
            "contrast": self.sl_contrast.value(),
            "curves": {ch: m.to_dict() for ch, m in self.curves.items()},
        }

    def _apply_adjust_snapshot(self, snapshot):
        """되돌리기/다시하기로 적용 위치가 바뀐 뒤, 그 시점의 밝기/대비/
        톤커브 상태를 슬라이더·커브 위젯에 반영한다. snapshot이 None이면
        (그 지점까지 'adjust' 기록이 전혀 없으면) self._adjust_pristine
        (이 세션의 출발점 — 보통 0/0/항등이지만 프로젝트를 불러왔다면 그
        값)으로 되돌린다."""
        if not hasattr(self, "sl_bright"):
            return   # UI가 아직 만들어지기 전(이론상 도달 안 함) 방어
        snapshot = snapshot if snapshot is not None else self._adjust_pristine
        bright = snapshot.get("bright", 0)
        contrast = snapshot.get("contrast", 0)
        curve_dicts = snapshot.get("curves", {})
        self.sl_bright.setValue(bright)
        self.sl_contrast.setValue(contrast)
        for ch in self.curves:
            cdict = curve_dicts.get(ch)
            self.curves[ch] = CurveModel.from_dict(cdict) if cdict else CurveModel()
        self.curve.model = self.curves[self._ch]
        self.curve._sel = None
        self.curve.set_histogram(self._hist_for(self._ch))
        self._refresh_display()

    def _undo(self):
        """한 단계 이전 상태로 이동한다(연산 포인터를 한 칸 뒤로 옮기고 재생).
        스타크래프트 리플레이처럼 이미지를 저장해 둔 게 아니라, pristine부터
        그 지점까지 연산을 처음부터 다시 계산하는 것이라 약간의 시간이
        들지만, 매 단계의 이미지를 메모리에 쌓아두지 않아도 된다."""
        if self._edit_pos < 0:
            self.status.showMessage(tr("status_nothing_to_undo"))
            return
        self._finalize_pending_rotation()  # 진행 중인 미리보기 회전을 먼저 확정/정리
        self._finalize_pending_bow()        # 진행 중인 미리보기 곡률보정도 정리
        self._finalize_pending_shear()
        undone_op, undone_params = self._edit_ops[self._edit_pos]
        self._edit_pos -= 1
        self._replay_history()
        self.gel.crop_rect = None
        self.gel._crop_a = self.gel._crop_b = None
        if undone_op == "warp":
            # '펴기 실행'을 되돌린 거라면 백지로 보내지 않고 그때 쓴 코너
            # 지정 상태로 복귀시킨다 — 코너만 살짝 다듬어 바로 다시 펴기를
            # 실행할 수 있어야지, 처음부터 다시 코너를 찍게 하면 안 된다.
            self.gel.corners = [tuple(p) for p in undone_params["corners"]]
            if hasattr(self, "corner_label"):
                self.corner_label.setText(tr("corner_count", n=len(self.gel.corners)))
            if hasattr(self, "btn_corner"):
                self._enter_manual_corner_mode()
        else:
            self.gel.corners = []
            if hasattr(self, "corner_label"):
                self.corner_label.setText(tr("corner_count", n=0))
        self._after_geometry_change()
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(self._edit_pos >= 0)
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(self._edit_pos < len(self._edit_ops) - 1)
        self.status.showMessage(tr("status_undo_done", n=self._edit_pos + 1))

    def _redo(self):
        """되돌리기로 거슬러 올라갔던 걸 한 단계 다시 앞으로 이동한다(연산
        포인터를 한 칸 앞으로 옮기고 처음부터 재생). 이미 적용했던 연산을
        다시 계산하는 것뿐이라 결과는 항상 이전과 똑같다(결정적)."""
        if self._edit_pos + 1 >= len(self._edit_ops):
            self.status.showMessage(tr("status_nothing_to_redo"))
            return
        self._finalize_pending_rotation()
        self._finalize_pending_bow()
        self._finalize_pending_shear()
        self._edit_pos += 1
        self._replay_history()
        self.gel.corners = []
        self.gel.crop_rect = None
        self.gel._crop_a = self.gel._crop_b = None
        if hasattr(self, "corner_label"):
            self.corner_label.setText(tr("corner_count", n=0))
        self._after_geometry_change()
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(self._edit_pos >= 0)
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(self._edit_pos < len(self._edit_ops) - 1)
        self.status.showMessage(tr("status_redo_done"))

    def _after_geometry_change(self):
        """빠른 회전(90/180)·반전·자르기·펴기처럼 한 번에 확정되는 변환 뒤,
        그리고 되돌리기/다시하기 뒤에도 호출된다. 정밀회전/곡률/기울기
        보정 슬라이더 상태는 그 전에 이미 실행된 _replay_history()가
        _sync_geom_sliders로 현재 위치에 맞게 정리해뒀으므로 여기서는
        건드리지 않는다(예전엔 여기서 무조건 0으로 밀어버려서, 되돌리기로
        곡률보정이 적용된 지점에 돌아왔을 때 이미지는 보정된 채인데
        슬라이더만 0으로 보이는 불일치가 있었다)."""
        self._refresh_after_pixels_changed()

    def _on_tab_changed(self, i):
        """탭을 전환하면 이전 탭에서 켜둔 마우스 동작(레인 수동 검출/코너 지정/
        자르기/세로 범위 지정 모드)을 모두 끈다. 안 그러면 다른 탭으로
        넘어가서도 이미지 위에서 마우스가 이전 모드대로 동작해 혼란을 준다."""
        self.curve.update()
        if hasattr(self, "btn_lane") and self.btn_lane.isChecked():
            self.btn_lane.blockSignals(True); self.btn_lane.setChecked(False); self.btn_lane.blockSignals(False)
            self.btn_lane.setText(tr("btn_manual_lane_off"))
        if hasattr(self, "btn_corner") and self.btn_corner.isChecked():
            self.btn_corner.blockSignals(True); self.btn_corner.setChecked(False); self.btn_corner.blockSignals(False)
            self.btn_corner.setText(tr("btn_corner_mode_off"))
        if hasattr(self, "btn_vrange") and self.btn_vrange.isChecked():
            self.btn_vrange.blockSignals(True); self.btn_vrange.setChecked(False); self.btn_vrange.blockSignals(False)
            self.btn_vrange.setText(tr("btn_vrange_mode_off"))
        self.gel.set_mode("view")
        # 통합 보정 탭(회전/펴기/곡률/기울기)이 항상 탭 목록의 첫 번째로
        # 추가되므로(_build() 참고) 인덱스 0으로 판별한다 — 이 탭에서만
        # 격자+중앙 십자선 가이드를 보여줘 수평/수직이 맞는지 확인하기
        # 쉽게 한다. 사용자가 체크박스로 꺼뒀으면(_guides_enabled=False)
        # 이 탭이어도 안 보인다.
        self.gel.show_guides = self._guides_enabled and (i == 0)
        self.gel.update()

    def _on_guides_toggled(self, on):
        """캔버스 위 격자+중앙 십자선 가이드 체크박스. 지금 탭이 보정 탭이
        아니면 어차피 _on_tab_changed가 곧 다시 판단하지만, 보정 탭에
        머문 채로 체크박스만 눌렀을 때도 바로 반영되도록 여기서 직접
        갱신한다."""
        self._guides_enabled = on
        self.gel.show_guides = on and (self.tabs.currentIndex() == 0)
        self.gel.update()

    def _set_exclusive_mode(self, which: str, on: bool):
        """레인 수동 조정 / 코너 지정 / 자르기 / 세로 범위 지정 중 하나만
        활성화. 켤 때 진행 중인 정밀회전/곡률 미리보기를 먼저 확정 기록한다
        — 안 그러면 미리보기가 편집 기록 없이 다른 작업으로 넘어가 되돌리기
        에서 그 단계가 사라질 수 있다. 진행 중인 게 없으면 finalize는
        아무것도 하지 않으므로 안전하다."""
        if on:
            had_pending = (self._curve_base is not None) or (self._rot_base is not None) \
                          or (self._shear_base is not None)
            self._finalize_pending_rotation()
            self._finalize_pending_bow()
            self._finalize_pending_shear()
            if had_pending:
                self._refresh_after_pixels_changed()
            for btn, m in [(self.btn_lane, "lane"), (self.btn_corner, "corner"),
                           (getattr(self, "btn_vrange", None), "vrange")]:
                if btn is not None and m != which and btn.isChecked():
                    btn.blockSignals(True); btn.setChecked(False); btn.blockSignals(False)
            self.gel.set_mode(which)
        else:
            self.gel.set_mode("view")

    def _toggle_vrange_mode(self, on):
        self._set_exclusive_mode("vrange", on)
        self.btn_vrange.setText(tr("btn_vrange_mode_on") if on else tr("btn_vrange_mode_off"))

    def _on_vrange_changed(self, _has_range):
        """세로 범위를 새로 그리거나 기존 줄을 드래그해 조정한 뒤 호출.
        범위가 바뀌면 그 범위로 다시 분석을 돌려야 하므로, 레인 경계를
        바꿨을 때(_on_lane_edge_changed)와 동일하게 기존 분석 결과를
        무효화한다."""
        self._update_vrange_label()
        for lane in self.lanes:
            lane.peaks = None
            lane.peak_area = None
            lane.peak_volume = None
            lane.peak_prom = None
            lane.peak_bounds = None
            lane.n_smear = 0
            lane.mw = []
        self.profile.set_lanes([])
        self.result_table.setRowCount(0)
        self.status.showMessage(tr("status_lane_changed_reanalyze"))

    def _clear_vrange(self):
        self.gel.clear_vrange()
        self._update_vrange_label()

    def _update_vrange_label(self):
        if not hasattr(self, "vrange_label"):
            return
        H = self._gray_orig.shape[0] if self._gray_orig is not None else 0
        if self.gel.vrange:
            top, bot = self.gel.vrange
            pct = round(100 * (bot - top + 1) / H) if H > 0 else 0
            self.vrange_label.setText(tr("vrange_label_set", top=top, bot=bot, h=H, pct=pct))
        else:
            self.vrange_label.setText(tr("vrange_label_full", h=H))

    def _zoom_step(self, factor):
        self.gel.set_zoom(self.gel._zoom * factor)

    def _zoom_reset(self):
        self.gel.reset_zoom()

    def _on_zoom_changed(self, zoom):
        self.zoom_label.setText(f"{round(zoom * 100)}%")

    def _on_overlay_toggled(self, on):
        self.gel.show_overlay = on
        self.gel.update()

    def _toggle_corner_mode(self, on):
        self._set_exclusive_mode("corner", on)
        self.btn_corner.setText(tr("btn_corner_mode_on") if on else tr("btn_corner_mode_off"))

    def _on_corner_changed(self, n):
        self.corner_label.setText(tr("corner_count", n=n))
        if n >= 4:
            self.status.showMessage(tr("corner_done_msg"))

    def _clear_corners(self):
        self.gel.clear_corners(); self.corner_label.setText(tr("corner_count", n=0))

    def _manual_warp(self):
        if not HAS_CV2:
            self._warn(tr("opencv_required_title"), tr("opencv_required_warp_msg")); return
        if self._orig is None:
            self._info(tr("no_image_title"), tr("no_image_msg")); return
        if len(self.gel.corners) != 4:
            self._info(tr("corner_insufficient_title"), tr("corner_insufficient_msg", n=len(self.gel.corners)) +
                       tr("corner_click_order")); return
        self._finalize_pending_rotation()
        self._finalize_pending_bow()
        self._finalize_pending_shear()
        self._warp(np.array(self.gel.corners, dtype=np.float32))

    def _auto_warp(self):
        if not HAS_CV2:
            self._warn(tr("opencv_required_title"), tr("opencv_required_autodetect_msg")); return
        if self._orig is None:
            self._info(tr("no_image_title"), tr("no_image_msg")); return
        self._finalize_pending_rotation()
        self._finalize_pending_bow()
        self._finalize_pending_shear()
        img = np.array(self._orig.convert("RGB"))
        quad = find_gel_quad(img)
        if quad is None:
            self._info(tr("warp_detect_fail_title"), tr("warp_detect_fail_msg") +
                       tr("corner_click_order")); self._enter_manual_corner_mode(); return
        ordered = self._order_corners(quad)
        self.gel.corners = [tuple(map(float, p)) for p in ordered]
        self.gel.update(); self.corner_label.setText(tr("corner_count_auto"))
        if self._ask(tr("auto_detect_done_title"), tr("auto_detect_done_msg")):
            self._warp(ordered)
        else:
            self._enter_manual_corner_mode()

    def _enter_manual_corner_mode(self):
        """코너 지정 모드를 켜고 버튼 상태를 맞춘다 (자동 인식 실패/거절 시 공통 사용)."""
        self.btn_corner.setChecked(True)
        self.btn_corner.setText(tr("btn_corner_mode_on"))
        self.gel.set_mode("corner")

    def _warp(self, src):
        # 실제 퍼스펙티브 계산은 apply_edit_op()의 "warp" 분기가 그대로
        # 수행한다(여기서 미리 계산해 두면 _record_op의 재생과 중복된다).
        # 상태바에 보여줄 결과 크기만 가볍게 미리 구해둔다.
        tl, tr_, br, bl = src
        wt = np.linalg.norm(tr_ - tl); wb = np.linalg.norm(br - bl)
        hl = np.linalg.norm(bl - tl); hr = np.linalg.norm(br - tr_)
        ow = max(int(round(max(wt, wb))), 10); oh = max(int(round(max(hl, hr))), 10)
        self._record_op("warp", {"corners": src.tolist() if hasattr(src, "tolist") else list(src)})
        self.btn_corner.setChecked(False); self.btn_corner.setText(tr("btn_corner_mode_off"))
        self.gel.set_mode("view")
        self._after_geometry_change()
        self.status.showMessage(tr("status_warp_done", w=ow, h=oh))

    @staticmethod
    def _order_corners(pts):
        pts = pts.reshape(4, 2)
        s = pts.sum(axis=1); d = np.diff(pts, axis=1).ravel()
        return np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                         pts[np.argmax(s)], pts[np.argmax(d)]], dtype=np.float32)
