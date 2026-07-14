"""bandwagon.app

메인 윈도우 Analyzer(QMainWindow). 다른 모든 모듈을 조립한다.

기능별 메서드는 대부분 믹스인으로 분리돼 있다(StyleMixin/GeometryMixin/
LanesMixin/FileIOMixin) — 여기 남은 건 윈도우 골격(_build,
탭 빌드 진입점, 메뉴/단축키)과 여러 믹스인이 공유하는 공용 다이얼로그
헬퍼뿐이다. 어떤 메서드가 어느 파일에 있는지 헷갈리면 그 파일의 모듈
docstring을 보면 된다. 웨스턴 블롯 합성은 별도 독립 모듈(composite.py)이
담당한다 — 합성 결과를 .bwcomposite 파일로 내보내고 FileIOMixin이 그걸
임포트한다.
"""
import sys, os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QAction, QSizePolicy, QMessageBox, QSplitter,
    QStatusBar, QMenu, QTabWidget, QDialog, QDialogButtonBox,
    QScrollArea, QCheckBox,
)
from PyQt5.QtCore import Qt, QTimer, QStandardPaths
from . import i18n
from .i18n import tr
from .theme import *
from .meta import (APP_NAME, APP_VERSION, RELEASE_DATE, HAS_CV2)
from .models import CurveModel
from .widgets import GelView, ProfileView
from .dialogs import _dialog_style, _no_help_button
from .style import StyleMixin
from .geometry import GeometryMixin
from .lanes import LanesMixin
from .fileio import FileIOMixin


class Analyzer(StyleMixin, GeometryMixin, LanesMixin, FileIOMixin, QMainWindow):
    # "파일 > 열기"가 새로 띄우는 창들의 참조를 여기 계속 들고 있는다 —
    # 파이썬이 지역 변수로만 들고 있으면 GC가 곧바로 회수해 Qt가 창을
    # 닫아버린다. QApplication은 기본이 quitOnLastWindowClosed=True라
    # 마지막 창이 닫힐 때 앱도 같이 종료된다(추가 설정 불필요).
    _open_windows = []

    def __init__(self, path=None, splash=None):
        super().__init__()
        self._base_title = f"{APP_NAME} v{APP_VERSION}"
        self.setWindowTitle(self._base_title)
        self.setMinimumSize(1080, 700)
        self.resize(1380, 860)

        self._orig = None
        self._display = None
        self._gray_orig = None
        # 합성 모드에서 분석용으로 쓰는 UV 단독 그레이스케일(None=평소 모드).
        # 화면(_orig)엔 가시광+UV 블렌드가 보이지만 분석은 이 값을 본다.
        self._wb_gray_override = None
        # 편집 기록 재생의 시작 그레이스케일 오버라이드(=_edit_pristine에
        # 정렬된 UV 단독 강도). 합성 파일을 임포트한 세션에서 편집을 시작할
        # 때 그 시점의 _wb_gray_override가 여기에 고정되고, 이후 회전/자르기/
        # 펴기 등이 apply_edit_op을 통해 이 값도 함께 변환해 정렬을 유지한다.
        # (평소 세션에서는 계속 None.)
        self._edit_gray_pristine = None
        # 밴드 표시 방식: "area"(경계 영역, 기본) 또는 "line"(피크 위치 한 줄).
        # 둘 다 같은 peak_bounds/peaks를 보여주는 방식만 다를 뿐, 정량값과는
        # 무관 — render_analysis_overlay()와 GelView.paintEvent() 양쪽이
        # 이 값을 참조해 그리는 방식을 바꾼다.
        self._band_display_style = "area"
        # 보정 탭(회전/펴기)에서 격자+중앙 십자선 가이드를 켤지 — 체크박스로
        # 사용자가 직접 끌 수 있다. 탭 자체가 다른 탭이면 이 값이 True여도
        # 가이드는 안 보인다(_on_tab_changed가 둘 다 확인).
        self._guides_enabled = True
        self._pristine_orig = None  # 불러온 직후의 원본 (전체 초기화 시 이 상태로 복귀)
        self._rot_base = None      # 정밀 회전 미리보기용 스냅샷 (세션 시작 시점 원본)
        self._curve_base = None    # 부채꼴(곡률) 보정 미리보기용 스냅샷 (세션 시작 시점 원본)
        self._shear_base = None    # 기울기(전단) 보정 미리보기용 스냅샷 (세션 시작 시점 원본)
        # 이번 세션에서 한 번이라도 커밋했는지 추적 — True면 다음 커밋은
        # 새 연산을 쌓지 않고 이번 세션 항목 하나만 절대값으로 교체한다
        # (release를 여러 번 해도 누적/오염되지 않도록). 세션 종료 시
        # (_finalize_pending_*/_reset_*) 다시 False로.
        self._rot_session_pushed = False
        self._bow_session_pushed = False
        self._shear_session_pushed = False
        # 정밀회전·곡률보정·기울기보정 드래그 중 화면에만 쓰는 다운스케일 캐시.
        # self._orig은 release 전까지 안 건드리고 이 작은 이미지만 갱신해
        # 무거운 cv2 연산을 가볍게 만든다.
        self._preview_small = None
        self._preview_scale = 1.0
        # 밝기/대비/톤커브 드래그 중에만 쓰는 색보정 미리보기용 축소본.
        # 드래그가 끝나 원본 해상도로 확정하면(_refresh_display(preview=False)) None으로 폐기.
        self._color_preview_base = None
        # ── 되돌리기/다시하기: 연산 리스트 재생 방식 ──────────────────────
        # 이미지를 단계마다 저장하지 않고 '가벼운 연산 기록만 들고 있다가
        # 필요할 때 처음부터 다시 계산'한다(리플레이 방식).
        #   _edit_pristine: 마지막 '새 원본' 시점의 이미지(로드 시/WB 적용 시)
        #   _edit_ops: pristine 이후의 (연산이름, 파라미터) 전체 목록
        #   _edit_pos: 그중 몇 개까지가 '현재 적용된 것'인지(포인터)
        # self._orig = pristine에 edit_ops[:edit_pos+1]을 재적용한 결과
        # (_replay_history가 담당). 되돌리기/다시하기는 pos만 옮기고 재생.
        self._edit_pristine = None
        self._edit_ops = []        # [(op_name, params_dict), ...]
        self._edit_pos = -1        # edit_ops[:edit_pos+1]까지가 '현재 적용된' 연산들
        self._EDIT_MAX = 20        # 최대 20단계까지만 기록(그 이상은 가장 오래된 것 폐기)
        # edit_ops 안에 'lanes'(레인 구성) 기록이 전혀 없는 지점까지
        # 되돌렸을 때 복원할 기준값 — _adjust_pristine과 같은 역할.
        self._lanes_pristine = []
        # _auto_lanes()가 레인을 N개 한꺼번에 만들 때, 그 안에서 호출하는
        # _on_lane_added()가 매번 따로 커밋하면 한 번의 '자동 검출'이
        # 되돌리기 N단계로 쌓인다 — 이걸 막는 동안만 True로 둔다.
        self._suppress_lane_commit = False
        # edit_ops 안에 'adjust'(밝기/대비/커브) 기록이 전혀 없는 지점까지
        # 되돌렸을 때 복원할 기준값. 항상 0/0/항등 커브는 아니다 — 프로젝트를
        # 불러오면 그 안에 저장된 값이 이 세션의 출발점이 된다(_snapshot_
        # adjust_baseline이 _reset_session_state/open_project에서 갱신).
        self._adjust_pristine = {"bright": 0, "contrast": 0, "curves": {}}
        self._last_dir = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) \
                         or os.path.expanduser("~")  # 파일 열기/저장 기본 폴더 (System32 등으로 안 떨어지게)
        # 현재 작업 중인 .bandwagon 프로젝트 파일 경로 — 있으면 "프로젝트 저장"이
        # 대화상자 없이 이 경로에 바로 덮어쓴다(Ctrl+S 반복 저장을 편하게).
        # 이미지만 열었거나(프로젝트로 저장한 적 없음) 새 세션을 시작하면
        # None으로 되돌아간다(_reset_session_state).
        self._current_project_path = None
        self._saved_snapshot = None   # closeEvent가 이걸 현재 상태와 비교해 저장 여부를 물어봄
        self._img_hash_cache = (None, None)  # (self._orig 참조, 해시) — _project_state_snapshot 캐시

        self.curves = {c: CurveModel() for c in ("RGB", "Red", "Green", "Blue")}
        self._ch = "RGB"
        self.lanes = []

        self._build()
        if path:
            # 그림 경로뿐 아니라, 탐색기에서 .bandwagon 파일을 더블클릭해
            # 실행된 경우(파일 연결)에도 여기로 경로가 넘어온다 — 확장자를
            # 보고 알아서 그림/프로젝트로 나눠 연다.
            QTimer.singleShot(0, lambda: self.open_path_smart(path))
        # 창이 뜬 뒤(이벤트 루프 시작 후) 백그라운드에서 scipy/cv2를 미리 데워둔다.
        # 부팅은 빠른 채로, 첫 분석/펴기 클릭 때의 '멈칫'을 없앤다. 200ms 정도
        # 늦춰 시작해 최초 화면 렌더링과 경쟁하지 않게 한다.
        QTimer.singleShot(200, self._prewarm_heavy_imports)
        # 저장 안 한 변경사항이 있으면 제목표시줄에 "*"를 붙인다. 편집이
        # 일어나는 모든 지점(레인/커브/밝기/메모/분석 파라미터 등)마다
        # 일일이 dirty 플래그를 세우는 대신, closeEvent가 이미 쓰는
        # _project_state_snapshot() 해시 비교를 주기적으로 재사용한다 —
        # 코드 중복 없이 항상 같은 기준으로 판단된다.
        self._title_timer = QTimer(self)
        self._title_timer.timeout.connect(self._refresh_title)
        self._title_timer.start(2000)

    def _prewarm_heavy_imports(self):
        """데몬 스레드에서 scipy·cv2를 미리 import해 첫 분석/펴기 클릭 때의
        지연을 없앤다. 이 스레드는 모듈 import만 하고 Qt 위젯/시그널은
        절대 건드리지 않는다(스레드 안전성). import는 파이썬 import-lock으로
        보호되므로 데우는 중 사용자가 분석을 눌러도 안전하게 대기만 한다."""
        import threading

        def _warm():
            try:
                from scipy.interpolate import PchipInterpolator  # noqa: F401
                from scipy.signal import find_peaks               # noqa: F401
                from scipy.stats import linregress                # noqa: F401
            except Exception:
                pass
            if HAS_CV2:
                try:
                    import cv2  # noqa: F401
                except Exception:
                    pass

        threading.Thread(target=_warm, name="prewarm-heavy-imports", daemon=True).start()

    def _splash_step(self, text):
        """예전엔 부팅 스플래시 진행 메시지를 갱신했으나, 스플래시는 이제
        PyInstaller 실행파일의 네이티브 스플래시로만 처리하므로 여기서는
        아무 일도 하지 않는다(_build() 안 여러 호출부를 그대로 두기 위해
        형태만 남긴 무동작 메서드)."""
        return

    def _build(self):
        self._splash_step(tr("splash_loading_ui"))
        self._apply_palette()

        mb = self.menuBar(); mb.setStyleSheet(self._menubar_css())

        # ── 파일: 열기/붙여넣기 + 프로젝트 저장 + 결과 이미지 내보내기를
        # 전부 한 메뉴로 묶는다. 웨스턴블롯은 성격이 다른(별도 창에서
        # 작업하는) 흐름이라 여기 안 넣고 따로 분리한다.
        m_file = mb.addMenu(tr("menu_file"))
        a = QAction(tr("menu_new_window"), self); a.triggered.connect(self.new_window)
        a.setShortcut("Ctrl+N"); a.setToolTip(tr("menu_new_window_tip")); m_file.addAction(a)
        a = QAction(tr("dlg_open_title"), self); a.triggered.connect(self.open_anything)
        a.setShortcut("Ctrl+O"); m_file.addAction(a)
        # "최근 파일"은 매번 다시 열 때(aboutToShow) 항목을 새로 채운다 —
        # 다른 창에서 방금 연 파일이 바로 반영되어야 하고, 목록은 파일
        # 하나로 공유되므로(레지스트리 아님, ~/.bandwagon_recent.json) 매번
        # 디스크에서 다시 읽는 게 캐싱보다 간단하고 항상 최신이다.
        self.m_recent = m_file.addMenu(tr("menu_recent_files"))
        self.m_recent.aboutToShow.connect(self._rebuild_recent_menu)
        a = QAction(tr("toolbar_paste"), self); a.triggered.connect(self.paste_image)
        a.setShortcut("Ctrl+V"); m_file.addAction(a)  # 포커스 위젯에 먹히지 않게 단축키를 액션에 직접 건다
        m_file.addSeparator()
        a = QAction(tr("toolbar_project_save"), self); a.triggered.connect(self.save_project)
        a.setShortcut("Ctrl+S"); a.setToolTip(tr("toolbar_project_save_tip")); m_file.addAction(a)
        a = QAction(tr("toolbar_project_save_as"), self); a.triggered.connect(self.save_project_as)
        a.setShortcut("Ctrl+Shift+S"); a.setToolTip(tr("toolbar_project_save_as_tip")); m_file.addAction(a)
        a = QAction(tr("menu_project_open_location"), self); a.triggered.connect(self.open_project_location)
        a.setToolTip(tr("menu_project_open_location_tip")); m_file.addAction(a)
        m_file.addSeparator()
        a = QAction(tr("toolbar_copy_result"), self); a.triggered.connect(self.copy_image)
        a.setToolTip(tr("toolbar_copy_result_tip")); m_file.addAction(a)
        a = QAction(tr("toolbar_save_result"), self); a.triggered.connect(self.save_image)
        a.setToolTip(tr("toolbar_save_result_tip")); m_file.addAction(a)
        a = QAction(tr("toolbar_export_csv"), self); a.triggered.connect(self.export_csv)
        m_file.addAction(a)

        # ── 웨스턴블롯 ────────────────────────────────────────────────
        # "새로 만들기"(스튜디오 열기)와 "기존 파일 불러오기"를 나란히 둬서
        # 프로젝트 메뉴의 저장/새로 저장과 비슷한 짝을 이룬다 — 다만 합성은
        # "지금 세션에 다시 덮어쓸 경로"라는 개념이 없어(스튜디오가 메인
        # 창 상태를 전혀 참조하지 않는 독립 창이라, 자세한 이유는
        # composite.py 모듈 docstring 참고) '저장/다른 이름으로 저장' 짝
        # 대신 이 형태로 갔다.
        m_wb = mb.addMenu(tr("menu_western"))
        a = QAction(tr("menu_western_open"), self); a.triggered.connect(self.open_composite_studio)
        a.setToolTip(tr("toolbar_composite_studio_tip")); m_wb.addAction(a)
        a = QAction(tr("toolbar_composite_import"), self)
        a.triggered.connect(lambda _checked=False: self.import_composite())
        a.setToolTip(tr("toolbar_composite_import_tip")); m_wb.addAction(a)

        # ── 편집 ─────────────────────────────────────────────────────
        m_edit = mb.addMenu(tr("menu_edit"))
        a = QAction(tr("toolbar_reset_all"), self); a.triggered.connect(self.reset_all)
        m_edit.addAction(a)
        m_edit.addSeparator()
        self.btn_undo = QAction(tr("toolbar_undo"), self)
        self.btn_undo.setShortcut("Ctrl+Z")
        self.btn_undo.setToolTip(tr("toolbar_undo_tip"))
        self.btn_undo.triggered.connect(self._undo)
        self.btn_undo.setEnabled(False)
        m_edit.addAction(self.btn_undo)
        self.btn_redo = QAction(tr("toolbar_redo"), self)
        self.btn_redo.setShortcut("Ctrl+Y")
        self.btn_redo.setToolTip(tr("toolbar_redo_tip"))
        self.btn_redo.triggered.connect(self._redo)
        self.btn_redo.setEnabled(False)
        m_edit.addAction(self.btn_redo)

        # ── 정보 ─────────────────────────────────────────────────────
        m_info = mb.addMenu(tr("menu_info"))
        a = QAction(tr("toolbar_help"), self); a.triggered.connect(self._show_help)
        m_info.addAction(a)
        a = QAction(tr("toolbar_about"), self); a.triggered.connect(self._show_about)
        m_info.addAction(a)

        # ── 언어 ─────────────────────────────────────────────────────
        # 예전엔 토글 버튼 하나였는데, 지금 언어가 뭔지 헷갈리지 않게
        # 두 언어를 나란히 두고 고르는 방식으로 바꿨다.
        m_lang = mb.addMenu(tr("menu_language"))
        a = QAction(tr("lang_name_ko"), self); a.triggered.connect(lambda: self._set_language("ko"))
        m_lang.addAction(a)
        a = QAction(tr("lang_name_en"), self); a.triggered.connect(lambda: self._set_language("en"))
        m_lang.addAction(a)

        central = QWidget(); self.setCentralWidget(central)
        root = QHBoxLayout(central); root.setContentsMargins(10, 10, 10, 10); root.setSpacing(10)
        split = QSplitter(Qt.Horizontal); root.addWidget(split)

        left = QWidget()
        lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0); lv.setSpacing(8)

        zoom_row = QHBoxLayout(); zoom_row.setSpacing(6)
        zoom_out = QPushButton(tr("zoom_out")); zoom_out.setFixedWidth(48); zoom_out.setStyleSheet(self._btn_css())
        zoom_in = QPushButton(tr("zoom_in")); zoom_in.setFixedWidth(48); zoom_in.setStyleSheet(self._btn_css())
        zoom_reset = QPushButton("100%"); zoom_reset.setFixedWidth(48); zoom_reset.setStyleSheet(self._btn_css())
        zoom_reset.setToolTip(tr("zoom_reset_tip"))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet(f"color:{MUTE};font-size:10px;")
        self.zoom_label.setFixedWidth(40); self.zoom_label.setAlignment(Qt.AlignCenter)
        zoom_hint = QLabel(tr("zoom_hint"))
        zoom_hint.setStyleSheet(f"color:{MUTE};font-size:10px;")
        zoom_out.clicked.connect(lambda: self._zoom_step(1 / 1.25))
        zoom_in.clicked.connect(lambda: self._zoom_step(1.25))
        zoom_reset.clicked.connect(self._zoom_reset)
        zoom_row.addWidget(zoom_out); zoom_row.addWidget(zoom_in)
        zoom_row.addWidget(self.zoom_label); zoom_row.addWidget(zoom_reset)
        zoom_row.addWidget(zoom_hint); zoom_row.addStretch()
        self.chk_overlay = QCheckBox(tr("chk_show_overlay"))
        self.chk_overlay.setChecked(True)
        self.chk_overlay.setStyleSheet(f"color:{MUTE};font-size:10px;" + self._checkbox_css())
        self.chk_overlay.setToolTip(tr("chk_show_overlay_tip"))
        self.chk_overlay.toggled.connect(self._on_overlay_toggled)
        zoom_row.addWidget(self.chk_overlay)
        self.chk_guides = QCheckBox(tr("chk_show_guides"))
        self.chk_guides.setChecked(True)
        self.chk_guides.setStyleSheet(f"color:{MUTE};font-size:10px;" + self._checkbox_css())
        self.chk_guides.setToolTip(tr("chk_show_guides_tip"))
        self.chk_guides.toggled.connect(self._on_guides_toggled)
        zoom_row.addWidget(self.chk_guides)
        lv.addLayout(zoom_row)

        self.gel = GelView()
        self.gel.laneAdded.connect(self._on_lane_added)
        self.gel.laneEdgeChanged.connect(self._on_lane_edge_changed)
        self.gel.cornerChanged.connect(self._on_corner_changed)
        self.gel.vrangeChanged.connect(self._on_vrange_changed)
        self.gel.zoomChanged.connect(self._on_zoom_changed)
        lv.addWidget(self.gel, 1)
        self.profile = ProfileView()
        lv.addWidget(self.profile)
        split.addWidget(left)

        right = QWidget(); right.setMinimumWidth(330); right.setMaximumWidth(380)
        rv = QVBoxLayout(right); rv.setContentsMargins(4, 4, 4, 4); rv.setSpacing(8)
        self.tabs = QTabWidget(); self.tabs.setStyleSheet(self._tabs_css())
        self.tabs.setUsesScrollButtons(False)
        self.tabs.tabBar().setExpanding(True)
        rv.addWidget(self.tabs)
        split.addWidget(right)
        split.setStretchFactor(0, 3); split.setStretchFactor(1, 1)

        self._splash_step(tr("splash_loading_tabs"))
        tab_steps = [
            (self._build_tab_correct, tr("splash_tab_adjust")),  # 요청#3: 펴기+보정 통합
            (self._build_tab_lanes, tr("splash_tab_lanes")),
            (self._build_tab_analysis, tr("splash_tab_analysis")),
            (self._build_tab_std, tr("splash_tab_std")),
            (self._build_tab_memo, tr("splash_tab_memo")),
        ]
        for _fn, _label in tab_steps:
            self._splash_step(_label)
            _fn()

        self._splash_step(tr("splash_almost_done"))
        # 커브 위젯이 생성된 뒤에 연결 (탭 전환 시 커브 갱신)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # currentChanged는 탭이 "바뀔 때"만 발생해 처음 뜬 탭(인덱스 0)에는
        # 신호가 안 온다 — 시작할 때부터 보정 탭이 활성이니 가이드 상태를
        # 한 번 직접 맞춰준다.
        self._on_tab_changed(self.tabs.currentIndex())

        self.status = QStatusBar(); self.status.setStyleSheet(f"background:{INK1};color:{MUTE};")
        self.setStatusBar(self.status)
        self.status.showMessage(tr("status_ready"))

    def _new_page(self):
        # 탭 콘텐츠 위젯 자체에 배경을 직접 줌 — QScrollArea 안에 들어가면
        # QTabWidget::pane 스타일이 더 이상 자동으로 배경을 칠해주지 않는다.
        w = QWidget()
        w.setStyleSheet(f"background:{INK2};")
        return w

    def _add_tab(self, page: QWidget, title: str):
        """탭 페이지를 QScrollArea로 감싸 추가한다. 창이 작아져 내용이
        넘쳐도(특히 커브 위젯이 있는 보정 탭) 스크롤로 전부 접근 가능하게 한다."""
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QScrollArea.NoFrame)
        # QScrollArea 자체 배경뿐 아니라, 내부 viewport(별도 위젯)에도 명시적으로
        # 배경을 줘야 한다 — 안 그러면 Qt 기본 흰색 팔레트가 그대로 비친다.
        sa.viewport().setStyleSheet(f"background:{INK2};")
        sa.setStyleSheet(
            f"QScrollArea{{background:{INK2};border:none;}}"
            f"QScrollBar:vertical{{background:{INK1};width:10px;}}"
            f"QScrollBar::handle:vertical{{background:{INK4};border-radius:5px;min-height:24px;}}"
            f"QScrollBar::add-line,QScrollBar::sub-line{{height:0;}}")
        sa.setWidget(page)
        self.tabs.addTab(sa, title)

















    def _box(self, icon, title, text, buttons=QMessageBox.Ok):
        m = QMessageBox(self); m.setIcon(icon); m.setWindowTitle(title); m.setText(text)
        m.setStandardButtons(buttons); m.setStyleSheet(_dialog_style())
        return m

    def _info(self, t, x): self._box(QMessageBox.Information, t, x).exec_()
    def _warn(self, t, x): self._box(QMessageBox.Warning, t, x).exec_()

    def _set_language(self, lang):
        if lang == i18n.CURRENT_LANG:
            return
        self._info(tr("lang_switch_title"), tr("lang_switch_restart_msg"))
        i18n.set_lang(lang)  # 저장 + 전역 갱신; 다음 실행부터 적용

    def _show_about(self):
        self._info(tr("about_title", app=APP_NAME),
                   f"{APP_NAME}\n"
                   f"{tr('about_version', version=APP_VERSION, date=RELEASE_DATE)}\n\n"
                   f"{tr('about_author')}\n\n"
                   f"{tr('about_license_notice')}")

    def _show_help(self):
        dlg = QDialog(self)
        _no_help_button(dlg)
        dlg.setWindowTitle(tr("toolbar_help"))
        dlg.setMinimumSize(560, 620)
        dlg.setStyleSheet(_dialog_style())
        lay = QVBoxLayout(dlg)

        text = QLabel(tr("help_html", app=APP_NAME))
        text.setWordWrap(True)
        text.setStyleSheet(f"color:{INKT}; font-size:12px;")
        text.setTextFormat(Qt.RichText)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setWidget(text)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{INK2};}}")
        lay.addWidget(scroll, 1)

        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(dlg.accept)
        lay.addWidget(bb)
        dlg.exec_()

    def _ask(self, t, x):
        m = self._box(QMessageBox.Question, t, x, QMessageBox.Yes | QMessageBox.No)
        m.setDefaultButton(QMessageBox.Yes)
        m.button(QMessageBox.Yes).setText(tr("btn_yes"))
        m.button(QMessageBox.No).setText(tr("btn_no"))
        return m.exec_() == QMessageBox.Yes

    def keyPressEvent(self, e):
        if e.modifiers() == Qt.ControlModifier:
            if e.key() == Qt.Key_V:
                self.paste_image()
            elif e.key() == Qt.Key_C:
                # 분석/레인 표에 포커스가 있으면 선택 셀을 표로 복사,
                # 그 외(캔버스 등)에서는 기존처럼 결과 이미지를 복사한다(요청#9).
                fw = QApplication.focusWidget()
                if fw in (getattr(self, "result_table", None), getattr(self, "lane_table", None)):
                    self._copy_table_selection(fw)
                else:
                    self.copy_image()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            # 젤 영역 지정 모드에서 코너 4개가 있으면 Enter로 바로 변환 적용
            if getattr(self, "btn_corner", None) is not None and self.btn_corner.isChecked() \
                    and len(self.gel.corners) == 4:
                self._manual_warp()
            else:
                super().keyPressEvent(e)
        else:
            super().keyPressEvent(e)

    def _copy_table_selection(self, table):
        """선택한 표 셀들을 탭(TSV) 형식으로 클립보드에 복사한다 — 엑셀/구글시트에
        그대로 붙여넣을 수 있다. 선택이 없으면 아무 일도 하지 않는다."""
        ranges = table.selectedRanges()
        if not ranges:
            return
        rng = ranges[0]
        lines = []
        for r in range(rng.topRow(), rng.bottomRow() + 1):
            cells = []
            for c in range(rng.leftColumn(), rng.rightColumn() + 1):
                it = table.item(r, c)
                cells.append(it.text() if it is not None else "")
            lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))
        if hasattr(self, "status"):
            self.status.showMessage(tr("status_table_copied"))

    def _switch_channel(self, ch):
        self.curves[self._ch] = self.curve.model
        self._ch = ch
        self.curve.channel = ch
        self.curve.model = self.curves[ch]
        self.curve._sel = None
        self.curve.set_histogram(self._hist_for(ch))









    # ── 정밀 회전: 절대각, release해도 슬라이더가 값을 유지 ──────────────





    # ── 부채꼴(곡률) 보정: 정밀 회전과 동일한 절대값+세션 유지 모델 ──────




































































    # ── 프로젝트 저장/불러오기 (.bandwagon) ──────────────────────────────
    # ZIP 안에 image.png(self._orig, 무손실) + project.json(밝기/대비/톤커브/
    # 레인/분석 파라미터)만 둔다. 분석 결과는 저장하지 않고, 불러온 뒤 같은
    # 입력으로 run_analysis()를 다시 돌려 재계산한다(포맷을 가볍게, 둘 사이
    # 불일치 여지 없이 — 코드가 항상 진리의 원천).



