"""bandwagon.style

StyleMixin — 다크 테마 stylesheet 문자열 헬퍼들. 전부 순수 문자열을
반환하거나 self.setPalette/setStyleSheet만 하는, 다른 기능과 거의 얽히지
않는 코드라 app.py에서 분리했다. Analyzer(StyleMixin, ...)로 섞여 들어간다.
"""
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor

from .theme import *
from .dialogs import _table_css


class StyleMixin:
    def _apply_palette(self):
        p = self.palette(); p.setColor(QPalette.Window, QColor(INK1)); self.setPalette(p)
        # 메인윈도우에 setStyleSheet를 하면 그 스타일시트가 모든 자식(커브/젤뷰)으로
        # 전파돼 커스텀 paintEvent가 'hover할 때만 보임' 버그를 일으킨다.
        # 앱 전역(QApplication) 스타일시트로 적용하면 위젯별로는 먹지만
        # 메인윈도우→자식 전파 경로는 타지 않는다.
        QApplication.instance().setStyleSheet(
            f"QLabel{{color:{INKT};background:transparent;}}"
            f"QToolTip{{background:{INK3};color:{INKT};border:1px solid {LINE2};}}"
            f"QSplitter::handle{{background:{LINE};}}"
            f"QScrollBar:vertical{{background:{INK1};width:10px;}}"
            f"QScrollBar::handle:vertical{{background:{INK4};border-radius:5px;min-height:24px;}}"
            f"QScrollBar::add-line,QScrollBar::sub-line{{height:0;}}")

    def _toolbar_css(self):
        return (f"QToolBar{{background:{INK1};border-bottom:1px solid {LINE};padding:6px 10px;spacing:4px;}}"
                f"QToolBar::separator{{width:1px;background:{LINE};margin:5px 6px;}}"
                f"QToolButton{{color:{INKT};background:{INK2};border:1px solid {LINE};"
                f"border-radius:6px;padding:6px 13px;font-size:12px;}}"
                f"QToolButton:hover{{background:{INK4};border-color:{LINE2};}}")

    def _tabs_css(self):
        return (f"QTabWidget::pane{{border:1px solid {LINE};border-radius:8px;background:{INK2};top:-1px;}}"
                f"QTabBar::tab{{background:transparent;color:{MUTE};padding:7px 4px;"
                f"border-bottom:2px solid transparent;font-size:11px;}}"
                f"QTabBar::tab:selected{{color:{CYAN};border-bottom:2px solid {CYAN};}}"
                f"QTabBar::tab:hover:!selected{{color:{INKT};}}")

    def _group_css(self):
        return (f"QGroupBox{{color:{MUTE};font-size:10px;border:1px solid {LINE};"
                f"border-radius:8px;margin-top:10px;padding:10px 8px 8px 8px;}}"
                f"QGroupBox::title{{subcontrol-position:top left;left:10px;top:-7px;padding:0 4px;background:{INK2};}}")

    def _btn_css(self):
        return (f"QPushButton{{background:{INK3};color:{INKT};border:1px solid {LINE};"
                f"border-radius:6px;padding:6px 10px;font-size:11px;}}"
                f"QPushButton:hover{{background:{INK4};border-color:{LINE2};}}"
                f"QPushButton:checked{{background:rgba(63,180,230,0.18);border-color:{CYAN};color:{CYAN};}}")

    def _btn_accent_css(self):
        return (f"QPushButton{{background:{CYAN};color:#06161f;border:none;border-radius:6px;"
                f"padding:8px 14px;font-size:12px;font-weight:bold;}}"
                f"QPushButton:hover{{background:#5cc6f2;}}")

    def _spin_css(self):
        # 다크 배경에서 QSpinBox 기본 화살표가 거의 안 보이는 문제가 있어
        # (실제 보고됨), 화살표 버튼 배경·테두리와 화살표 자체(border-color
        # 삼각형 트릭)를 명시적으로 그려 또렷하게 만든다.
        return (
            f"QSpinBox{{background:{INK3};color:{INKT};border:1px solid {LINE};"
            f"border-radius:5px;padding:3px 6px;}}"
            f"QSpinBox:focus{{border-color:{CYAN};}}"
            f"QSpinBox::up-button{{subcontrol-origin:border;subcontrol-position:top right;"
            f"width:16px;background:{INK4};border-left:1px solid {LINE};"
            f"border-bottom:1px solid {LINE};border-top-right-radius:5px;}}"
            f"QSpinBox::up-button:hover{{background:{LINE};}}"
            f"QSpinBox::down-button{{subcontrol-origin:border;subcontrol-position:bottom right;"
            f"width:16px;background:{INK4};border-left:1px solid {LINE};"
            f"border-bottom-right-radius:5px;}}"
            f"QSpinBox::down-button:hover{{background:{LINE};}}"
            # 삼각형의 좌우 테두리를 transparent 대신 버튼 배경색(INK4)으로 둔다.
            # 일부 Qt/윈도우에서 transparent 테두리가 투명 처리되지 않아 화살표가
            # 네모로 깨져 보이는데, 배경색과 같은 색을 쓰면 어디서든 삼각형으로 보인다.
            f"QSpinBox::up-arrow{{width:0;height:0;border-left:4px solid {INK4};"
            f"border-right:4px solid {INK4};border-bottom:6px solid {INKT};}}"
            f"QSpinBox::up-arrow:disabled{{border-bottom-color:{MUTE};}}"
            f"QSpinBox::down-arrow{{width:0;height:0;border-left:4px solid {INK4};"
            f"border-right:4px solid {INK4};border-top:6px solid {INKT};}}"
            f"QSpinBox::down-arrow:disabled{{border-top-color:{MUTE};}}"
        )

    def _combo_css(self):
        # ::down-arrow를 명시적으로 CSS 삼각형으로 그린다. 스타일시트가 적용된
        # QComboBox는 일부 환경에서 기본 드롭다운 화살표가 네모(미싱 글리프)로
        # 깨져 보이는데, 삼각형을 직접 그리면 폰트와 무관하게 항상 제대로 보인다.
        return (f"QComboBox{{background:{INK3};color:{INKT};border:1px solid {LINE};border-radius:5px;padding:3px 8px;}}"
                f"QComboBox::drop-down{{subcontrol-origin:padding;subcontrol-position:center right;"
                f"width:18px;border-left:1px solid {LINE};}}"
                f"QComboBox::down-arrow{{width:0;height:0;border-left:4px solid {INK3};"
                f"border-right:4px solid {INK3};border-top:6px solid {INKT};margin-right:5px;}}"
                f"QComboBox QAbstractItemView{{background:{INK3};color:{INKT};"
                f"selection-background-color:{CYAN};selection-color:#06161f;}}")

    def _table_css(self):
        return _table_css()

    def _checkbox_css(self):
        # 다크 테마에서 기본 체크박스 표시기가 거의 안 보여, 표시기를 명시적으로
        # 그린다. 체크 시 청록색으로 채워 on/off가 한눈에 보이게 한다(글리프 미사용).
        return (f"QCheckBox::indicator{{width:15px;height:15px;border:1px solid {LINE2};"
                f"border-radius:3px;background:{INK3};}}"
                f"QCheckBox::indicator:hover{{border-color:{CYAN};}}"
                f"QCheckBox::indicator:checked{{background:{CYAN};border-color:{CYAN};}}")

    def _compact_btn_css(self):
        # 레인 순서/삭제용 작은 버튼 — 기본 _btn_css는 padding이 커서 좁은 칸에서
        # 글자가 잘려 보이지 않았다. 여백/글자 크기를 줄여 촘촘하게 만든다(요청#7).
        return (f"QPushButton{{background:{INK3};color:{INKT};border:1px solid {LINE};"
                f"border-radius:4px;padding:0px 2px;font-size:10px;}}"
                f"QPushButton:hover{{background:{INK4};border-color:{LINE2};}}"
                f"QPushButton:disabled{{background:{INK2};color:{MUTE};border-color:{LINE};}}")
