"""bandwagon.dialogs

마커 입력/프리셋 관리 다이얼로그 + 다이얼로그 공용 스타일.

(BandWagon v1.1을 모듈로 분할한 것 — 동작은 원본과 동일.)
"""
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFileDialog, QSlider, QGroupBox, QStatusBar,
    QToolBar, QAction, QSizePolicy, QMessageBox, QSplitter, QTableWidget,
    QTableWidgetItem, QHeaderView, QTabWidget, QSpinBox, QDoubleSpinBox,
    QComboBox, QInputDialog, QDialog, QDialogButtonBox, QFormLayout,
    QScrollArea, QCheckBox,
)
from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF, QRect, QSize, pyqtSignal, QTimer, QStandardPaths
from PyQt5.QtGui import (
    QPainter, QPen, QColor, QPixmap, QImage, QBrush,
    QPainterPath, QLinearGradient, QFont, QPolygonF, QPalette,
)
from .theme import *
from .i18n import tr
from .presets import (
    load_marker_presets, save_marker_presets,
    export_marker_presets_csv, import_marker_presets_csv,
)


_ICON_CACHE = {}   # (direction, hex_color, size) -> 저장된 PNG의 절대경로


def _triangle_icon_path(direction, hex_color, size=10):
    """작은 삼각형 화살표를 즉석에서 그려 임시 PNG로 저장하고 그 경로를
    돌려준다. QSS의 '0크기 위젯 + 테두리로 삼각형 만들기' 트릭이 이
    환경에서 스핀박스/콤보박스 둘 다 뭉개진 모양으로 깨져 보이는 게
    실사용 중 확인됐다. data: URI로 바로 넣는 것도 시도했지만 Qt
    스타일시트의 url()이 data: 스킴을 지원하지 않아(실제 파일 경로만
    인식) 조용히 무시됐다 — 그래서 실제 파일로 저장해 경로로 참조한다.
    같은 조합은 프로세스당 한 번만 그려서 캐싱한다."""
    key = (direction, hex_color, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    import tempfile, os
    from PIL import Image, ImageDraw
    # 작은 크기에서 폴리곤을 바로 그리면 PIL이 안티에일리어싱 없이 그려
    # 가장자리가 거칠어 보인다(특히 위쪽 화살표에서 눈에 띔). 4배 크기로
    # 그린 뒤 LANCZOS로 축소해 매끈하게 만든다(슈퍼샘플링).
    scale = 4
    big = size * scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = QColor(hex_color)
    rgba = (color.red(), color.green(), color.blue(), 255)
    cx = big / 2.0
    if direction == "up":
        d.polygon([(cx - 3.5 * scale, big * 0.62), (cx + 3.5 * scale, big * 0.62), (cx, big * 0.30)], fill=rgba)
    else:
        d.polygon([(cx - 3.5 * scale, big * 0.38), (cx + 3.5 * scale, big * 0.38), (cx, big * 0.70)], fill=rgba)
    img = img.resize((size, size), Image.LANCZOS)
    fd, path = tempfile.mkstemp(prefix=f"bandwagon_arrow_{direction}_", suffix=".png")
    os.close(fd)
    img.save(path, format="PNG")
    path = path.replace("\\", "/")   # QSS url()은 슬래시만 안전하게 인식
    _ICON_CACHE[key] = path
    return path


def _no_help_button(dlg):
    """제목표시줄의 '?' 컨텍스트 도움말 버튼을 없앤다. WhatsThis 텍스트를
    이 앱 어디에도 걸어두지 않아서, 눌러봤자 커서만 금지 모양으로 바뀌고
    아무 일도 안 일어나 혼란만 준다(실사용 중 확인된 문제)."""
    dlg.setWindowFlags(dlg.windowFlags() & ~Qt.WindowContextHelpButtonHint)


def _dialog_style():
    up_icon = _triangle_icon_path("up", INKT)
    down_icon = _triangle_icon_path("down", INKT)
    return (f"QDialog{{background:{INK2};}}"
            f"QLabel{{color:{INKT};}}"
            f"QDoubleSpinBox,QSpinBox{{background:{INK3};color:{INKT};"
            f"border:1px solid {LINE};border-radius:4px;padding:3px;}}"
            f"QDoubleSpinBox::up-button,QSpinBox::up-button{{subcontrol-origin:border;"
            f"subcontrol-position:top right;width:16px;background:{INK4};"
            f"border-left:1px solid {LINE};border-bottom:1px solid {LINE};"
            f"border-top-right-radius:4px;}}"
            f"QDoubleSpinBox::up-button:hover,QSpinBox::up-button:hover{{background:{LINE};}}"
            f"QDoubleSpinBox::down-button,QSpinBox::down-button{{subcontrol-origin:border;"
            f"subcontrol-position:bottom right;width:16px;background:{INK4};"
            f"border-left:1px solid {LINE};border-bottom-right-radius:4px;}}"
            f"QDoubleSpinBox::down-button:hover,QSpinBox::down-button:hover{{background:{LINE};}}"
            f"QDoubleSpinBox::up-arrow,QSpinBox::up-arrow{{image:url({up_icon});width:10px;height:10px;}}"
            f"QDoubleSpinBox::down-arrow,QSpinBox::down-arrow{{image:url({down_icon});width:10px;height:10px;}}"
            f"QComboBox::drop-down{{subcontrol-origin:border;subcontrol-position:top right;"
            f"width:20px;border-left:1px solid {LINE};background:{INK4};"
            f"border-top-right-radius:4px;border-bottom-right-radius:4px;}}"
            f"QComboBox::drop-down:hover{{background:{LINE};}}"
            f"QComboBox::down-arrow{{image:url({down_icon});width:10px;height:10px;}}"
            f"QPushButton{{background:{INK3};color:{INKT};border:1px solid {LINE};"
            f"border-radius:5px;padding:5px 14px;}}"
            f"QPushButton:hover{{background:{INK4};}}")


def _table_css():
    """QTableWidget 공용 스타일. Analyzer(self._table_css)와 독립 다이얼로그인
    MarkerPresetManager가 둘 다 쓰므로 모듈 레벨 함수로 둔다(Analyzer 메서드로만
    있으면 Analyzer보다 먼저 정의되는 다이얼로그 클래스에서 호출할 수 없다)."""
    return (f"QTableWidget{{background:{INK1};color:{INKT};gridline-color:{LINE};"
            f"border:1px solid {LINE};border-radius:6px;}}"
            f"QHeaderView::section{{background:{INK2};color:{MUTE};border:none;"
            f"border-bottom:1px solid {LINE};padding:5px;font-size:10px;}}"
            f"QTableWidget::item:selected{{background:rgba(63,180,230,0.30);color:{INKT};}}"
            f"QTableWidget::item:selected:!active{{background:rgba(63,180,230,0.30);color:{INKT};}}")


class MarkerDialog(QDialog):
    def __init__(self, n, existing, parent=None):
        super().__init__(parent)
        _no_help_button(self)
        self.setWindowTitle(tr("marker_dialog_title"))
        self.setMinimumWidth(320)
        self.setStyleSheet(_dialog_style() +
                            f"QComboBox{{background:{INK3};color:{INKT};border:1px solid {LINE};"
                            f"border-radius:4px;padding:3px;}}"
                            f"QComboBox QAbstractItemView{{background:{INK3};color:{INKT};"
                            f"selection-background-color:{CYAN};selection-color:#06161f;"
                            f"border:1px solid {LINE};}}")
        self.n = n
        self.presets = load_marker_presets()

        lay = QVBoxLayout(self)

        prow = QHBoxLayout()
        prow.addWidget(QLabel(tr("preset_label")))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem(tr("preset_manual_entry"))
        for p in self.presets:
            self.preset_combo.addItem(p["name"])
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        prow.addWidget(self.preset_combo, 1)
        manage = QPushButton(tr("preset_manage_btn")); manage.clicked.connect(self._manage_presets)
        prow.addWidget(manage)
        lay.addLayout(prow)

        self.hint = QLabel(tr("marker_hint_default", n=n))
        self.hint.setWordWrap(True)
        self.hint.setStyleSheet(f"color:{MUTE};font-size:10px;")
        lay.addWidget(self.hint)

        self.form = QFormLayout(); self.spins = []; self.match_combos = []
        for i in range(n):
            sb = QDoubleSpinBox(); sb.setRange(0.1, 10000); sb.setDecimals(1)
            sb.setValue(existing[i] if i < len(existing) else 0.0)
            self.form.addRow(f"Band {i + 1}:", sb); self.spins.append(sb)
        lay.addLayout(self.form)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _set_band_row_visible(self, sb, visible):
        """"Band i:" 스핀박스 행(라벨+필드)을 통째로 보이거나 숨긴다.
        불일치(매칭) 모드에서는 같은 값을 스핀박스와 매칭 드롭다운
        두 군데에 겹쳐 보여줘서 뭘 봐야 할지 헷갈린다는 피드백이 있어,
        그 모드에서는 스핀박스를 숨기고 매칭 드롭다운 하나만 보여준다.
        (스핀박스 자체는 값 저장용으로 계속 쓰이므로 지우지는 않는다 —
        values()가 여전히 self.spins에서 읽는다.)"""
        sb.setVisible(visible)
        label = self.form.labelForField(sb)
        if label is not None:
            label.setVisible(visible)

    def _on_preset_changed(self, idx):
        # 기존에 수동매칭용으로 추가했던 행(라벨+콤보)을 먼저 깨끗이 제거
        for combo in self.match_combos:
            row_idx = self.form.getWidgetPosition(combo)[0]
            if row_idx >= 0:
                self.form.removeRow(row_idx)
        self.match_combos = []

        if idx == 0:  # 직접 입력
            self.hint.setText(tr("marker_hint_default", n=self.n))
            for sb in self.spins:
                sb.setEnabled(True)
                self._set_band_row_visible(sb, True)
            return

        preset = self.presets[idx - 1]
        mw = preset["mw"]
        if len(mw) == self.n:
            # 밴드 개수가 일치 → 위에서 아래로 그대로 자동 채움
            for sb, v in zip(self.spins, mw):
                sb.setValue(v); sb.setEnabled(True)
                self._set_band_row_visible(sb, True)
            self.hint.setText(tr("marker_hint_matched", name=preset['name'], n=self.n))
        else:
            # 개수 불일치 → 수동 매칭 모드: 검출된 밴드마다 프리셋 값을 고르게 함.
            # 스핀박스는 숨기고(값은 내부적으로만 유지) 매칭 드롭다운 하나만 보여줘
            # "같은 숫자를 두 군데서 봐야 하나" 하는 혼란을 없앤다.
            self.hint.setText(tr("marker_hint_mismatch", name=preset['name'], preset_n=len(mw), n=self.n))
            options = ["—"] + [f"{v:g} kDa" for v in mw]
            for i, sb in enumerate(self.spins):
                sb.setEnabled(False)
                self._set_band_row_visible(sb, False)
                combo = QComboBox()
                combo.addItems(options)
                # 검출 순서와 프리셋 순서가 같다고 가정하고 1차 추정값을 미리 선택
                guess = i + 1 if i < len(mw) else 0
                combo.setCurrentIndex(guess)
                combo.currentIndexChanged.connect(
                    lambda v, j=i, mwlist=mw: self._apply_match(j, v, mwlist))
                self.form.addRow(tr("preset_match_row_label", n=i + 1), combo)
                self.match_combos.append(combo)
                self._apply_match(i, guess, mw)

    def _apply_match(self, row, combo_idx, mw_list):
        self.spins[row].setValue(mw_list[combo_idx - 1] if combo_idx > 0 else 0.0)

    def _manage_presets(self):
        dlg = MarkerPresetManager(self.presets, self)
        if dlg.exec_():
            self.presets = dlg.presets
            save_marker_presets(self.presets)
            cur_name = self.preset_combo.currentText()
            self.preset_combo.blockSignals(True)
            self.preset_combo.clear()
            self.preset_combo.addItem(tr("preset_manual_entry"))
            for p in self.presets:
                self.preset_combo.addItem(p["name"])
            i = self.preset_combo.findText(cur_name)
            self.preset_combo.setCurrentIndex(i if i >= 0 else 0)
            self.preset_combo.blockSignals(False)

    def values(self):
        return [s.value() for s in self.spins]


class MarkerPresetManager(QDialog):
    """마커 프리셋 추가/삭제용 작은 관리 창."""
    def __init__(self, presets, parent=None):
        super().__init__(parent)
        _no_help_button(self)
        self.setWindowTitle(tr("preset_manager_title"))
        self.setMinimumWidth(320)
        self.setStyleSheet(_dialog_style())
        self.presets = [dict(p) for p in presets]

        lay = QVBoxLayout(self)
        self.listw = QTableWidget(0, 2)
        self.listw.setHorizontalHeaderLabels([tr("preset_col_name"), tr("preset_col_bands")])
        self.listw.verticalHeader().setVisible(False)  # 행번호 열(첫 칸)이 다이얼로그
        # 기본 팔레트의 밝은 배경으로 남아 깨져 보이는 문제 — 의미도 없는 정보라 숨김
        self.listw.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.listw.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.listw.setStyleSheet(_table_css())
        self._reload()
        lay.addWidget(self.listw, 1)

        row = QHBoxLayout()
        add = QPushButton(tr("preset_add_btn")); add.clicked.connect(self._add)
        rm = QPushButton(tr("preset_remove_btn")); rm.clicked.connect(self._remove)
        row.addWidget(add); row.addWidget(rm)
        lay.addLayout(row)

        io_row = QHBoxLayout()
        exp = QPushButton(tr("preset_export_btn")); exp.clicked.connect(self._export)
        imp = QPushButton(tr("preset_import_btn")); imp.clicked.connect(self._import)
        io_row.addWidget(exp); io_row.addWidget(imp)
        lay.addLayout(io_row)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _reload(self):
        self.listw.setRowCount(0)
        for p in self.presets:
            r = self.listw.rowCount(); self.listw.insertRow(r)
            self.listw.setItem(r, 0, QTableWidgetItem(p["name"]))
            self.listw.setItem(r, 1, QTableWidgetItem(", ".join(f"{v:g}" for v in p["mw"])))

    def _add(self):
        # flags를 명시하면(기본값 대신) Qt가 '?' 컨텍스트 도움말 버튼을
        # 자동으로 안 붙인다 — WhatsThis 텍스트가 없어 눌러도 아무 효과
        # 없이 커서만 바뀌는 문제를 없애기 위함(_no_help_button과 동일 목적).
        no_help_flags = Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        name, ok = QInputDialog.getText(
            self, tr("preset_add_title"), tr("preset_add_name_label"), flags=no_help_flags)
        if not ok or not name.strip():
            return
        text, ok = QInputDialog.getText(
            self, tr("preset_add_title"), tr("preset_add_mw_label"), flags=no_help_flags)
        if not ok or not text.strip():
            return
        try:
            mw = [float(x.strip()) for x in text.split(",") if x.strip()]
            if not mw:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, tr("input_error_title"), tr("preset_mw_parse_error"))
            return
        self.presets.append({"name": name.strip(), "mw": mw})
        self._reload()

    def _remove(self):
        rows = sorted({i.row() for i in self.listw.selectedIndexes()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.presets):
                del self.presets[r]
        self._reload()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("preset_export_dialog_title"), "bandwagon_markers.csv", tr("preset_csv_filter"))
        if not path:
            return
        try:
            export_marker_presets_csv(path, self.presets)
        except Exception as e:
            QMessageBox.warning(self, tr("input_error_title"), tr("preset_export_error", err=str(e)))
            return
        QMessageBox.information(self, tr("preset_export_dialog_title"),
                                 tr("preset_export_success", n=len(self.presets)))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("preset_import_dialog_title"), "", tr("preset_csv_filter"))
        if not path:
            return
        try:
            imported = import_marker_presets_csv(path)
        except Exception as e:
            QMessageBox.warning(self, tr("input_error_title"), tr("preset_import_error", err=str(e)))
            return
        if not imported:
            QMessageBox.warning(self, tr("input_error_title"), tr("preset_import_empty"))
            return
        self.presets.extend(imported)
        self._reload()
        QMessageBox.information(self, tr("preset_import_dialog_title"),
                                 tr("preset_import_success", n=len(imported)))


