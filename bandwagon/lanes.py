"""bandwagon.lanes

LanesMixin — 레인 지정(자동검출/수동추가/이동/삭제/이름/종류/마커) +
밴드 분석 실행 + MW 보정곡선 + 표준곡선. Analyzer(LanesMixin, ...)로
섞여 들어간다.

레인 구성도 GeometryMixin이 관리하는 되돌리기 스택(_record_op/
_replay_history)에 함께 기록된다 — _commit_lanes()가 "lanes" 연산을
기록하고, _apply_lanes_snapshot()이 _replay_history()의 호출을 받아
복원을 책임진다(자세한 내용은 geometry.py의 _GEOMETRY_OPS 주석 참고)."""
import numpy as np
from PyQt5.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QPushButton, QSlider, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)
from PyQt5.QtCore import Qt

from .i18n import tr
from .theme import *
from .models import Lane
from .widgets import StdCurveView
from .dialogs import MarkerDialog, MarkerPresetManager, _dialog_style, _no_help_button
from .presets import load_marker_presets, save_marker_presets


class LanesMixin:

    def _build_tab_lanes(self):
        page = self._new_page(); v = QVBoxLayout(page); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)
        box = QGroupBox(tr("group_lane_assign")); box.setStyleSheet(self._group_css())
        h = QVBoxLayout(box)

        nrow = QHBoxLayout(); nrow.setSpacing(6)
        nlabel = QLabel(tr("chk_lane_count")); nlabel.setStyleSheet(f"color:{INKT};")
        nrow.addWidget(nlabel)
        self.sp_lane_n = QSpinBox(); self.sp_lane_n.setRange(2, 60); self.sp_lane_n.setValue(15)
        self.sp_lane_n.setStyleSheet(self._spin_css())
        nrow.addWidget(self.sp_lane_n)
        h.addLayout(nrow)
        nhint = QLabel(tr("lane_count_hint"))
        nhint.setStyleSheet(f"color:{MUTE};font-size:10px;"); nhint.setWordWrap(True)
        h.addWidget(nhint)

        auto = QPushButton(tr("btn_auto_detect_lanes")); auto.clicked.connect(self._auto_lanes)
        auto.setStyleSheet(self._btn_accent_css())
        h.addWidget(auto)
        self.btn_lane = QPushButton(tr("btn_manual_lane_on")); self.btn_lane.setCheckable(True); self.btn_lane.setChecked(True)
        self.btn_lane.clicked.connect(self._toggle_lane_mode); self.btn_lane.setStyleSheet(self._btn_css())
        h.addWidget(self.btn_lane)
        hint = QLabel(tr("lane_manual_hint"))
        hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); hint.setWordWrap(True)
        h.addWidget(hint)
        clear = QPushButton(tr("btn_clear_all_lanes")); clear.clicked.connect(self._on_clear_lanes_clicked); clear.setStyleSheet(self._btn_css())
        h.addWidget(clear)
        preset_btn = QPushButton(tr("btn_manage_marker_presets")); preset_btn.clicked.connect(self._open_marker_presets)
        preset_btn.setStyleSheet(self._btn_css())
        preset_btn.setToolTip(tr("marker_preset_btn_tip"))
        h.addWidget(preset_btn)
        v.addWidget(box)

        vr_box = QGroupBox(tr("group_vrange")); vr_box.setStyleSheet(self._group_css())
        vrv = QVBoxLayout(vr_box); vrv.setSpacing(5)
        vr_info = QLabel(tr("vrange_intro"))
        vr_info.setStyleSheet(f"color:{MUTE};font-size:11px;"); vr_info.setWordWrap(True)
        vrv.addWidget(vr_info)
        self.btn_vrange = QPushButton(tr("btn_vrange_mode_off")); self.btn_vrange.setCheckable(True)
        self.btn_vrange.clicked.connect(self._toggle_vrange_mode); self.btn_vrange.setStyleSheet(self._btn_css())
        vrv.addWidget(self.btn_vrange)
        vr_hint = QLabel(tr("vrange_drag_hint"))
        vr_hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); vr_hint.setWordWrap(True)
        vrv.addWidget(vr_hint)
        self.vrange_label = QLabel(tr("vrange_label_full", h=0))
        self.vrange_label.setStyleSheet(f"color:{CYAN};font-size:11px;font-family:'DejaVu Sans Mono';")
        vrv.addWidget(self.vrange_label)
        vr_reset = QPushButton(tr("btn_reset_vrange")); vr_reset.clicked.connect(self._clear_vrange)
        vr_reset.setStyleSheet(self._btn_css())
        vrv.addWidget(vr_reset)
        v.addWidget(vr_box)

        det_box = QGroupBox(tr("group_band_detect")); det_box.setStyleSheet(self._group_css())
        f = QFormLayout(det_box)
        self.sp_prom = QSpinBox(); self.sp_prom.setRange(1, 100); self.sp_prom.setValue(90)
        self.sp_prom.setStyleSheet(self._spin_css())
        self.sp_prom.setToolTip(tr("sensitivity_tip"))
        self.sp_dist = QSpinBox(); self.sp_dist.setRange(1, 50); self.sp_dist.setValue(6); self.sp_dist.setStyleSheet(self._spin_css())
        f.addRow(tr("label_sensitivity"), self.sp_prom)
        f.addRow(tr("label_min_band_spacing"), self.sp_dist)

        # 밴드 경계(=정량 적분 범위) 임계값 — '피크 높이의 N%까지 떨어지는
        # 지점을 경계로 본다'. find_peaks의 left/right_bases(인접 피크
        # 사이 골짜기)를 그대로 쓰면 밴드가 촘촘할 때 영역이 서로 이어져
        # 보이는데, 값을 올리면 피크에 더 가깝게 끊어 경계가 좁아진다.
        # peak_area/peak_volume의 적분 범위 자체라 정량값도 함께 바뀐다.
        thresh_row = QHBoxLayout(); thresh_row.setSpacing(6)
        self.sl_band_thresh = QSlider(Qt.Horizontal)
        self.sl_band_thresh.setRange(5, 80); self.sl_band_thresh.setValue(40)
        self.sl_band_thresh.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
            f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
            f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
        self.lbl_band_thresh = QLabel("40%")
        self.lbl_band_thresh.setStyleSheet(f"color:{CYAN};font-family:'DejaVu Sans Mono';")
        self.lbl_band_thresh.setFixedWidth(36)
        self.sl_band_thresh.valueChanged.connect(
            lambda v: self.lbl_band_thresh.setText(f"{v}%"))
        thresh_row.addWidget(self.sl_band_thresh, 1)
        thresh_row.addWidget(self.lbl_band_thresh)
        thresh_label = QLabel(tr("label_band_threshold"))
        thresh_label.setToolTip(tr("band_threshold_tip"))
        f.addRow(thresh_label, thresh_row)

        # smear(폭 넓게 퍼진 피크) 자동 제외. 0=끔(기본값) — 0보다 크게
        # 두면, 밴드 경계 폭(위~아래 길이, px)이 이 값을 넘는 피크는
        # smear로 보아 결과(표/정량값/MW 계산)에서 통째로 뺀다. 상대적인
        # '뾰족함' 비율이 아니라 절대 길이(px) 제한이라 동작이 직관적이다.
        smear_row = QHBoxLayout(); smear_row.setSpacing(6)
        self.sl_smear = QSlider(Qt.Horizontal)
        self.sl_smear.setRange(0, 500); self.sl_smear.setValue(0)
        self.sl_smear.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{INK3};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;"
            f"background:{INKT};border:2px solid {CYAN};border-radius:8px;}}"
            f"QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}")
        self.sp_smear = QSpinBox(); self.sp_smear.setRange(0, 500); self.sp_smear.setValue(0)
        self.sp_smear.setSuffix("px"); self.sp_smear.setFixedWidth(70)
        self.sp_smear.setStyleSheet(self._spin_css())
        self.sl_smear.valueChanged.connect(self.sp_smear.setValue)
        self.sp_smear.valueChanged.connect(self.sl_smear.setValue)
        smear_row.addWidget(self.sl_smear, 1)
        smear_row.addWidget(self.sp_smear)
        smear_label = QLabel(tr("label_smear_thresh"))
        smear_label.setToolTip(tr("smear_thresh_tip"))
        f.addRow(smear_label, smear_row)
        v.addWidget(det_box)

        # 밴드 표시 방식: 선(피크 위치 한 줄) / 영역(경계 박스). 둘 다 같은
        # peak_bounds를 쓰므로 정량값과는 무관 — 순수하게 화면/저장 이미지의
        # 표시 방법만 바꾼다.
        style_row = QHBoxLayout(); style_row.setSpacing(6)
        style_label = QLabel(tr("label_band_display"))
        style_row.addWidget(style_label)
        self.combo_band_style = QComboBox()
        self.combo_band_style.addItems([tr("band_style_area"), tr("band_style_line")])
        self.combo_band_style.setStyleSheet(self._combo_css())
        self.combo_band_style.currentIndexChanged.connect(self._on_band_style_changed)
        style_row.addWidget(self.combo_band_style, 1)
        v.addLayout(style_row)

        run = QPushButton(tr("btn_run_analysis")); run.clicked.connect(self.run_analysis); run.setStyleSheet(self._btn_accent_css())
        v.addWidget(run)
        run_hint = QLabel(tr("run_analysis_hint"))
        run_hint.setStyleSheet(f"color:{MUTE};font-size:10px;"); run_hint.setWordWrap(True)
        v.addWidget(run_hint)

        self.lane_table = QTableWidget(0, 3)
        self.lane_table.setHorizontalHeaderLabels([tr("lane_col_name"), tr("lane_col_type"), tr("lane_col_order_delete")])
        self.lane_table.verticalHeader().setVisible(False)
        self.lane_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.lane_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.lane_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.lane_table.setStyleSheet(self._table_css())
        self.lane_table.cellChanged.connect(self._on_lane_renamed)
        v.addWidget(self.lane_table, 1)
        self._add_tab(page, tr("tab_lanes"))

    def _build_tab_analysis(self):
        page = self._new_page(); v = QVBoxLayout(page); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)
        note = QLabel(tr("analysis_tab_note"))
        note.setStyleSheet(f"color:{MUTE};font-size:10px;"); note.setWordWrap(True)
        v.addWidget(note)

        self.mw_r2_label = QLabel(tr("mw_regression_placeholder"))
        self.mw_r2_label.setStyleSheet(
            f"color:{CYAN};font-size:11px;font-family:'DejaVu Sans Mono';")
        self.mw_r2_label.setWordWrap(True)
        v.addWidget(self.mw_r2_label)

        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels([tr("col_lane"), tr("col_band"), tr("col_mw_kda"), tr("col_intensity"), tr("col_volume")])
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.result_table.setStyleSheet(self._table_css())
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 요청#9: 결과는 편집 불가(읽기 전용)
        self.result_table.setSelectionMode(QTableWidget.ExtendedSelection)
        v.addWidget(self.result_table, 1)
        self._add_tab(page, tr("tab_analysis"))

    def _build_tab_std(self):
        page = self._new_page(); v = QVBoxLayout(page); v.setContentsMargins(10, 10, 10, 10); v.setSpacing(8)
        self.std_view = StdCurveView(); v.addWidget(self.std_view, 1)
        self.std_label = QLabel(tr("std_label_placeholder"))
        self.std_label.setStyleSheet(f"color:{MUTE};font-size:11px;"); self.std_label.setWordWrap(True)
        self.std_label.setAlignment(Qt.AlignCenter)
        v.addWidget(self.std_label)
        self._add_tab(page, tr("tab_std"))

    def _commit_lanes(self):
        """레인 구성(개수/경계/이름/종류/마커값)을 되돌리기 스택에 한
        단계로 기록한다. 분석 결과(peaks 등)는 포함하지 않는다 — 어차피
        레인이 바뀌면 결과는 무효화되고, 복원 후 다시 '밴드 분석 실행'을
        누르면 똑같이 재계산되기 때문(Lane.to_dict와 같은 설계)."""
        if self._orig is None:
            return
        self._record_op("lanes", {"lanes": [l.to_dict() for l in self.lanes]})

    def _snapshot_lanes_baseline(self):
        """현재 레인 구성을 '이 세션의 lanes 기록 없음' 기준값으로 저장한다.
        _reset_session_state(새 이미지 시작 — 보통 빈 리스트)와
        open_project(저장된 레인 복원) 직후에 호출한다."""
        self._lanes_pristine = [l.to_dict() for l in self.lanes]

    def _apply_lanes_snapshot(self, snapshot):
        """되돌리기/다시하기로 적용 위치가 바뀐 뒤, 그 시점의 레인 구성을
        복원한다. Lane.to_dict()/from_dict()는 분석 결과(peaks 등)를 담지
        않으므로(프로젝트 저장용 설계 — 위 docstring 참고), 경계(x1,x2)가
        기존 레인과 그대로인 것만 분석 결과를 이어받는다. 경계가 바뀐
        레인은 그 결과가 더는 유효하지 않으므로 비워서(다시 분석 필요)
        기존 동작을 유지한다.

        이 구분이 필요한 이유: _commit_lanes()는 레인 '경계'가 안 바뀐
        커밋(예: 마커 종류/MW만 바꾸는 _edit_marker)에서도 호출되는데,
        그때마다 _record_op가 곧바로 _replay_history를 돌려 여기로
        들어온다. 예전엔 무조건 분석 결과를 비워서, 마커 MW를 지정해
        방금 계산한 결과가 커밋 직후 바로 사라지는 문제가 있었다(실사용
        중 확인: peaks가 None이 되고 레인 객체 자체가 새로 바뀜)."""
        if not hasattr(self, "lane_table"):
            return   # UI가 아직 만들어지기 전(이론상 도달 안 함) 방어
        dicts = snapshot["lanes"] if snapshot is not None else self._lanes_pristine
        old_by_geom = {(l.x1, l.x2): l for l in self.lanes}
        new_lanes = []
        for d in dicts:
            lane = Lane.from_dict(d)
            old = old_by_geom.get((lane.x1, lane.x2))
            if old is not None:
                lane.profile = old.profile
                lane.peaks = old.peaks
                lane.peak_area = old.peak_area
                lane.peak_volume = old.peak_volume
                lane.peak_prom = old.peak_prom
                lane.peak_bounds = old.peak_bounds
                lane.n_smear = old.n_smear
                lane.mw = old.mw
            new_lanes.append(lane)
        self.lanes = new_lanes
        self.gel.set_lanes(self.lanes)
        # profile/결과표도 위와 같은 이유로 무조건 비우지 않는다 — ProfileView.set_lanes는
        # profile이 None인 레인을 알아서 걸러내고, _refresh_results()도 peaks가 None인
        # 레인은 건너뛰므로, 경계가 안 바뀐 레인의 보존된 결과는 그대로 다시 보여주고
        # 진짜 무효화된(경계가 바뀐) 레인은 자연히 빈 채로 나온다.
        self.profile.set_lanes(self.lanes)
        self._refresh_results()
        self._rebuild_lane_table()

    def _toggle_lane_mode(self, on):
        self._set_exclusive_mode("lane", on)
        self.btn_lane.setText(tr("btn_manual_lane_on") if on else tr("btn_manual_lane_off"))

    def _on_lane_added(self, x1, x2):
        lane = Lane(len(self.lanes), x1, x2)
        self.lanes.append(lane)
        self._renumber_lanes()
        self.gel.set_lanes(self.lanes)
        self._rebuild_lane_table()
        self.status.showMessage(tr("status_lane_added", name=lane.name, x1=x1, x2=x2))
        if not self._suppress_lane_commit:
            self._commit_lanes()

    def _on_lane_edge_changed(self):
        """레인 경계를 드래그해 폭을 조정하거나, 레인 라벨을 드래그해 위치를
        옮긴 뒤 호출. 레인 구성이 바뀌었으므로 기존 밴드 분석 결과는 무효화한다."""
        for lane in self.lanes:
            lane.peaks = None
            lane.peak_area = None
            lane.peak_volume = None
            lane.peak_prom = None
            lane.peak_bounds = None
            lane.mw = []
        self.gel.set_lanes(self.lanes)
        self.profile.set_lanes([])
        self.result_table.setRowCount(0)
        self._rebuild_lane_table()
        self.status.showMessage(tr("status_lane_changed_reanalyze"))
        self._commit_lanes()

    def _auto_lanes(self):
        """세로 방향 강도 프로파일에서 레인(밴드가 모인 열)을 자동 검출.
        레인 개수를 폭으로 균등 분할한 뒤 경계를 신호가 약한 지점(골)으로
        살짝 보정한다 — 항상 정확히 N개가 나오는 게 목표이며, 세밀한 경계는
        레인 모드에서 드래그로 다듬는 걸 전제로 한다.

        예전엔 개수를 안 정하고도 돌릴 수 있었는데(전역/지역 임계값으로
        레인을 스스로 찾는 방식), 실제 젤 사진에서는 신호가 약한 레인이
        배경으로 오인돼 절반도 못 잡는 경우가 흔해 사실상 못 쓸 수준이었다
        (실제 이미지로 확인: 15개 중 4~6개만 검출). 레인 개수는 촬영한
        사람이 이미 알고 있는 값이라 입력을 아예 필수로 바꿔 그 불안정한
        경로 자체를 없앴다."""
        if self._gray_orig is None:
            self._info(tr("no_image_title"), tr("no_image_msg")); return
        g = self._gray_orig.astype(float)
        W = g.shape[1]
        col = 255.0 - g.mean(axis=0)            # 밴드가 많을수록 큰 값
        col = np.clip(col - np.percentile(col, 5), 0, None)
        if col.max() <= 0:
            self._info(tr("detect_fail_title"), tr("detect_fail_no_signal")); return
        k = max(3, W // 300)
        sm = np.convolve(col, np.ones(k) / k, mode="same")

        n_target = self.sp_lane_n.value()
        spans = self._split_lanes_by_count(sm, n_target, W)
        if spans is None:
            self._info(tr("detect_fail_title"), tr("detect_fail_count_msg", n=n_target))
            return

        self._clear_lanes()
        self._suppress_lane_commit = True
        try:
            for a, b in spans:
                self._on_lane_added(int(a), int(b))
        finally:
            self._suppress_lane_commit = False
        self._commit_lanes()   # 자동 검출 전체를 되돌리기 한 단계로 기록
        self.status.showMessage(tr("status_auto_lane_done", n=len(spans)))

    @staticmethod
    def _split_lanes_by_count(sm, n_target, W):
        """평활화된 세로-평균 강도 프로파일 sm을 정확히 n_target개 구간으로
        나눈다. 폭을 균등하게 n_target등분하는 것을 기본으로 삼고, 등분선
        바로 근처(±15%)에 등분선 지점 자체보다 뚜렷이 약한 골(신호가
        need_ratio 이하)이 있을 때만 그 골로 살짝 옮긴다.

        예전에는 ±40% 범위에서 무조건 가장 약한 지점으로 스냅했는데, 그
        범위가 넓다 보니 사실상 항상 뭔가에는 끌려가버려 레인 폭이
        지그재그로 들쭉날쭉해지는 문제가 있었다(실제 젤 사진으로 확인함).
        "뚜렷한 근거가 있을 때만 소폭 보정, 없으면 등분선 그대로"로 바꿔
        균등함을 기본값으로 두었다.

        완벽한 자동 분리보다 '항상 정확히 N개가 나오는 안정성'을 우선한다
        — 경계는 레인 모드에서 바로 드래그해 다듬을 수 있다."""
        if sm.max() <= 0 or n_target <= 0:
            return None
        seg_w = W / n_target
        snap_r = max(1, int(seg_w * 0.15))
        need_ratio = 0.75   # 골이 등분선 지점 신호의 75% 이하로 뚜렷이 약할 때만 스냅
        bounds = [0]
        for i in range(1, n_target):
            center = min(max(int(round(i * seg_w)), 0), W - 1)
            lo = max(0, center - snap_r); hi = min(W, center + snap_r)
            lo = max(lo, bounds[-1] + 1)
            if hi <= lo:
                bounds.append(center)
                continue
            local = sm[lo:hi]
            valley = lo + int(np.argmin(local))
            bounds.append(valley if sm[valley] <= need_ratio * sm[center] else center)
        bounds.append(W)
        # 경계가 역전되거나 겹치지 않도록 단조 증가 보정
        for i in range(1, len(bounds)):
            if bounds[i] <= bounds[i - 1]:
                bounds[i] = bounds[i - 1] + 1
        bounds[-1] = max(bounds[-1], W)
        spans = [(bounds[i], min(bounds[i + 1], W) - 1) for i in range(len(bounds) - 1)]
        return spans

    def _clear_lanes(self):
        """레인 목록을 비우는 저수준 동작 — 기하변환으로 좌표가 무효화될
        때나 새 이미지를 시작할 때도 내부적으로 쓰이므로, 여기서는 되돌리기
        기록을 남기지 않는다(그런 자동 초기화까지 별도 단계로 쌓이면 안
        됨 — _replay_history의 _GEOMETRY_OPS 리셋 규칙이 이미 같은 효과를
        재현한다). 사용자가 직접 누르는 '레인 전체 삭제' 버튼은
        _on_clear_lanes_clicked가 처리한다."""
        self.lanes = []
        self.gel.set_lanes([])
        self.profile.set_lanes([])
        self.result_table.setRowCount(0)
        self._rebuild_lane_table()

    def _on_clear_lanes_clicked(self):
        self._clear_lanes()
        self._commit_lanes()
        self.status.showMessage(tr("status_lanes_cleared"))

    def _rebuild_lane_table(self):
        self.lane_table.blockSignals(True)
        self.lane_table.setRowCount(0)
        for row, lane in enumerate(self.lanes):
            r = self.lane_table.rowCount(); self.lane_table.insertRow(r)
            item = QTableWidgetItem(lane.name); item.setForeground(lane.color)
            self.lane_table.setItem(r, 0, item)
            combo = QComboBox(); combo.addItems([tr("lane_kind_sample"), tr("lane_kind_marker"), tr("lane_kind_bsa")]); combo.setStyleSheet(self._combo_css())
            combo.setCurrentIndex({"sample": 0, "marker": 1, "bsa": 2}[lane.kind])
            # activated는 currentIndexChanged와 달리 '같은 항목을 다시 선택'해도
            # 신호가 발생한다 — 그래야 이미 '마커'인 상태에서 마커를 다시 눌렀을 때
            # MW 입력창을 재오픈할 수 있다(별도 MW 버튼을 없앤 대신 이 방식을 씀).
            combo.activated.connect(lambda idx, l=lane: self._set_lane_kind(l, idx))
            self.lane_table.setCellWidget(r, 1, combo)
            order = QWidget(); oh = QHBoxLayout(order); oh.setContentsMargins(0, 0, 0, 0); oh.setSpacing(2)
            up = QPushButton("Up"); up.setFixedWidth(26); up.setFixedHeight(20); up.setStyleSheet(self._compact_btn_css())
            up.setEnabled(row > 0); up.clicked.connect(lambda _, i=row: self._move_lane(i, -1))
            down = QPushButton("Dn"); down.setFixedWidth(26); down.setFixedHeight(20); down.setStyleSheet(self._compact_btn_css())
            down.setEnabled(row < len(self.lanes) - 1); down.clicked.connect(lambda _, i=row: self._move_lane(i, 1))
            delbtn = QPushButton(tr("btn_delete")); delbtn.setFixedWidth(38); delbtn.setFixedHeight(20); delbtn.setStyleSheet(self._compact_btn_css())
            delbtn.setToolTip(tr("delete_this_lane_tip"))
            delbtn.clicked.connect(lambda _, i=row: self._delete_lane(i))
            oh.addWidget(up); oh.addWidget(down); oh.addWidget(delbtn)
            self.lane_table.setCellWidget(r, 2, order)
        self.lane_table.blockSignals(False)

    def _renumber_lanes(self):
        """레인 목록 순서를 기준으로 idx(번호·색상)를 다시 매긴다.
        사용자가 직접 이름을 바꾼 레인("Lane N" 기본 이름이 아닌 것)은 이름을 보존한다."""
        for i, lane in enumerate(self.lanes):
            lane.idx = i
            lane.name = lane.name if not lane.name.startswith("Lane ") else f"Lane {i + 1}"

    def _move_lane(self, idx, delta):
        """레인 표시/번호 순서를 위(-1)/아래(+1)로 한 칸 옮긴다.
        레인의 이미지상 위치(x1/x2)는 그대로 두고, 목록 순서·번호(색상 포함)만 바꾼다."""
        j = idx + delta
        if j < 0 or j >= len(self.lanes):
            return
        self.lanes[idx], self.lanes[j] = self.lanes[j], self.lanes[idx]
        self._renumber_lanes()
        self.gel.set_lanes(self.lanes)
        self.profile.set_lanes(self.lanes if any(l.peaks is not None for l in self.lanes) else [])
        self._rebuild_lane_table()
        self.status.showMessage(tr("status_lane_reordered"))
        self._commit_lanes()

    def _delete_lane(self, idx):
        """레인 하나만 삭제하고, 남은 레인 번호를 1,2,3...으로 재정렬한다."""
        if idx < 0 or idx >= len(self.lanes):
            return
        name = self.lanes[idx].name
        del self.lanes[idx]
        self._renumber_lanes()
        self.gel.set_lanes(self.lanes)
        self.profile.set_lanes(self.lanes if any(l.peaks is not None for l in self.lanes) else [])
        self.result_table.setRowCount(0)
        self._rebuild_lane_table()
        self.status.showMessage(tr("status_lane_deleted", name=name, n=len(self.lanes)))
        self._commit_lanes()

    def _on_lane_renamed(self, row, col):
        if col == 0 and row < len(self.lanes):
            it = self.lane_table.item(row, 0)
            if it:
                self.lanes[row].name = it.text(); self.gel.update()
                self._commit_lanes()

    def _set_lane_kind(self, lane, idx):
        lane.kind = ["sample", "marker", "bsa"][idx]
        if lane.kind == "marker":
            self._edit_marker(lane)
        elif lane.kind == "bsa":
            dlg = QInputDialog(self); dlg.setStyleSheet(_dialog_style()); _no_help_button(dlg)
            dlg.setWindowTitle(tr("bsa_conc_title")); dlg.setLabelText(tr("bsa_conc_label", name=lane.name))
            dlg.setInputMode(QInputDialog.DoubleInput)
            dlg.setDoubleRange(0, 100000); dlg.setDoubleDecimals(2); dlg.setDoubleValue(max(lane.bsa_amount, 1.0))
            if dlg.exec_():
                lane.bsa_amount = dlg.doubleValue()
        self.gel.update()
        self._commit_lanes()

    def _edit_marker(self, lane):
        if lane.peaks is None or len(lane.peaks) == 0:
            self._info(tr("no_bands_title"), tr("no_bands_run_analysis_msg"))
            return
        dlg = MarkerDialog(len(lane.peaks), lane.marker_mw, self)
        if dlg.exec_():
            lane.marker_mw = dlg.values()
            # run_analysis()가 매번 하는 gel.set_lanes/profile.set_lanes를
            # 여기서도 해줘야, 젤 이미지 위 kDa 라벨이 "밴드 분석 실행"을
            # 다시 누르지 않아도 바로 나타난다(실사용 스크린샷으로 확인:
            # OK 직후엔 라벨이 안 뜨고 재분석해야만 떴었음).
            self.gel.set_lanes(self.lanes)
            self.profile.set_lanes(self.lanes)
            self._compute_mw(); self._refresh_results()

    def _open_marker_presets(self):
        """밴드 분석 여부와 무관하게, 레인 탭에서 바로 마커 프리셋을 추가/삭제."""
        presets = load_marker_presets()
        dlg = MarkerPresetManager(presets, self)
        if dlg.exec_():
            save_marker_presets(dlg.presets)
            self.status.showMessage(tr("status_presets_saved", n=len(dlg.presets)))

    def _on_band_style_changed(self, idx):
        """밴드를 '영역'(경계 박스) 또는 '선'(피크 위치 한 줄)으로 어떻게
        그릴지 바꾼다. 정량값(peak_area/peak_volume)에는 전혀 영향이 없는
        순수 표시 옵션 — combo의 0번이 영역, 1번이 선(아래 STRINGS의
        band_style_area/band_style_line 순서와 일치해야 함)."""
        self._band_display_style = "area" if idx == 0 else "line"
        self.gel.band_display_style = self._band_display_style
        self.gel.update()  # 화면 캔버스 즉시 다시 그리기 (분석을 다시 돌릴 필요 없음)

    def run_analysis(self):
        if self._gray_orig is None:
            self._info(tr("no_image_title"), tr("no_image_msg")); return
        if not self.lanes:
            self._info(tr("no_lanes_title"), tr("no_lanes_msg")); return
        # UI의 '민감도'는 값이 클수록 더 약한 밴드까지 잡히도록 직관적으로 보이게
        # 했고, 실제 find_peaks가 쓰는 prominence는 반대(값이 작을수록 더 잘 잡힘)
        # 라서 여기서 뒤집어 변환한다.
        prom = self.sp_prom.maximum() + self.sp_prom.minimum() - self.sp_prom.value()
        dist = self.sp_dist.value()
        thresh = self.sl_band_thresh.value()
        smear_max_px = self.sp_smear.value()
        y_top, y_bot = self.gel.vrange if self.gel.vrange else (None, None)
        for lane in self.lanes:
            lane.analyze(self._gray_orig, prom, dist, threshold_pct=thresh,
                         y_top=y_top, y_bot=y_bot, smear_max_px=smear_max_px)
        self.gel.set_lanes(self.lanes)
        self.profile.set_lanes(self.lanes)
        self._compute_mw()
        self._refresh_results()
        self._compute_std()
        total = sum(len(l.peaks) for l in self.lanes if l.peaks is not None)
        n_smear = sum(getattr(l, "n_smear", 0) for l in self.lanes)
        if n_smear > 0:
            self.status.showMessage(tr("status_analysis_done_smear", n=total, s=n_smear))
        else:
            self.status.showMessage(tr("status_analysis_done", n=total))

    def _compute_mw(self):
        markers = [l for l in self.lanes if l.kind == "marker"
                   and l.peaks is not None and len(l.peaks) > 0 and len(l.marker_mw) >= 2]
        if not markers or self._gray_orig is None:
            return
        H = self._gray_orig.shape[0]
        rf, logmw = [], []
        for lane in markers:
            n = min(len(lane.peaks), len(lane.marker_mw))
            for i in range(n):
                if lane.marker_mw[i] > 0:
                    rf.append(lane.peaks[i] / H); logmw.append(np.log10(lane.marker_mw[i]))
        if len(rf) < 2:
            return

        # rf 기준으로 정렬하고, 같은 rf가 중복되면(마커 레인이 여러 개라 위치가
        # 겹치는 경우) 평균을 내어 PCHIP에 필요한 '엄격히 증가하는 x'를 만든다.
        rf_arr = np.array(rf); logmw_arr = np.array(logmw)
        order = np.argsort(rf_arr)
        rf_sorted = rf_arr[order]; logmw_sorted = logmw_arr[order]
        rf_uniq, logmw_uniq = [], []
        for x, y in zip(rf_sorted, logmw_sorted):
            if rf_uniq and x - rf_uniq[-1] < 1e-9:
                logmw_uniq[-1] = (logmw_uniq[-1] + y) / 2
            else:
                rf_uniq.append(x); logmw_uniq.append(y)

        if len(rf_uniq) < 2:
            return

        # 마커 3점 이상이면 PCHIP(곡선이되 단조성 보장, 마커 점을 정확히
        # 통과)을 쓴다 — 선형회귀처럼 전체에 직선 하나를 욱여넣지 않아
        # 마커 사이에서 MW 순서가 뒤집히는 현상이 없다.
        from scipy.interpolate import PchipInterpolator
        from scipy.stats import linregress
        pchip = PchipInterpolator(rf_uniq, logmw_uniq, extrapolate=True)
        rf_min, rf_max = rf_uniq[0], rf_uniq[-1]

        # R²는 기존처럼 '선형 회귀했다면 얼마나 잘 맞았을까'를 참고 지표로만 보여준다
        # (PCHIP 자체는 점들을 정확히 통과하므로 그 자체의 R²는 항상 1이라 의미가 없다)
        _, _, r_lin, _, _ = linregress(rf_uniq, logmw_uniq)
        r2 = r_lin ** 2

        for lane in self.lanes:
            if lane.peaks is None: continue
            if lane.kind == "marker":
                # 마커는 사용자가 입력한 절대값이 정답이므로 보간/회귀로 덮어쓰지 않는다.
                n = min(len(lane.peaks), len(lane.marker_mw))
                lane.mw = [lane.marker_mw[i] if lane.marker_mw[i] > 0 else None for i in range(n)]
                lane.mw += [None] * (len(lane.peaks) - n)
            else:
                mw_list = []
                for py in lane.peaks:
                    x = py / H
                    # 마커 범위 밖(가장 큰/작은 마커보다 더 위/아래)은 외삽이라
                    # 신뢰도가 떨어지므로 범위 끝값으로 고정(clamp)해 비현실적인
                    # 값이 나오지 않게 한다.
                    xc = min(max(x, rf_min), rf_max)
                    mw_list.append(round(10 ** float(pchip(xc)), 1))
                lane.mw = mw_list
        self.gel.update()
        self.mw_r2_label.setText(tr("mw_interp_result", r2=r2, n_markers=len(markers), n_points=len(rf_uniq)))
        self.status.showMessage(tr("status_mw_interp_done", r2=r2, n_markers=len(markers)))

    def _compute_std(self):
        bsa = [l for l in self.lanes if l.kind == "bsa" and l.peak_volume is not None and len(l.peak_volume) > 0]
        if len(bsa) < 2:
            self.std_view.clear()
            self.std_label.setText(tr("std_need_more_lanes"))
            return
        amounts = [l.bsa_amount for l in bsa]
        vols = [float(l.peak_volume.sum()) for l in bsa]   # 부피 기준 정량
        from scipy.stats import linregress
        slope, icept, r, _, _ = linregress(vols, amounts)
        r2 = r ** 2
        self.std_view.set_fit(vols, amounts, slope, icept, r2)
        est_lines = []
        for lane in self.lanes:
            if lane.kind != "sample" or lane.peak_volume is None: continue
            tot = float(lane.peak_volume.sum())
            est = slope * tot + icept
            est_lines.append(tr("std_sample_est_line", name=lane.name, est=est))
        txt = tr("std_curve_summary", r2=r2, slope=slope, icept=icept)
        if est_lines:
            txt += "\n\n" + tr("std_sample_est_header") + "\n" + "\n".join(est_lines)
        self.std_label.setText(txt)

    def _refresh_results(self):
        self.result_table.setRowCount(0)
        for lane in self.lanes:
            if lane.peaks is None: continue
            for j in range(len(lane.peaks)):
                r = self.result_table.rowCount(); self.result_table.insertRow(r)
                mw = f"{lane.mw[j]:.1f}" if j < len(lane.mw) and lane.mw[j] is not None and lane.mw[j] > 0 else "—"
                inten = f"{lane.peak_area[j]:.1f}" if lane.peak_area is not None else "—"
                vol = f"{lane.peak_volume[j]:.0f}" if lane.peak_volume is not None else "—"
                for c, val in enumerate([lane.name, str(j + 1), mw, inten, vol]):
                    it = QTableWidgetItem(val); it.setForeground(lane.color)
                    self.result_table.setItem(r, c, it)
