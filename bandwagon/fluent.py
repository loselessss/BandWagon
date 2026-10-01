"""Shared Fluent-inspired desktop surfaces and controls (Qt Widgets)."""
from .theme import *


def button(accent=False, compact=False, danger=False):
    bg, fg = (CYAN, '#10212b') if accent else (INK3, '#ffb4ab' if danger else INKT)
    padding = '1px 3px' if compact else '6px 10px'
    return (f'QPushButton{{background:{bg};color:{fg};border:1px solid {LINE2 if accent else LINE};'
            f'border-bottom-color:{LINE2};border-radius:4px;padding:{padding};font-size:12px;}}'
            f'QPushButton:hover{{background:{"#8cddff" if accent else INK4};}}'
            f'QPushButton:pressed{{background:{"#55b8e5" if accent else INK2};border-color:{LINE};}}'
            f'QPushButton:focus{{border:1px solid {CYAN};}}'
            f'QPushButton:checked{{background:#254553;color:{CYAN};border-color:{CYAN};}}'
            f'QPushButton:disabled{{background:{INK2};color:#777777;border-color:{LINE};}}')


def tabs():
    return (f'QTabWidget::pane{{border:1px solid {LINE};border-radius:8px;background:{INK2};}}'
            f'QTabBar::tab{{background:transparent;color:{MUTE};padding:8px 3px;'
            'border-bottom:3px solid transparent;font-size:12px;min-height:16px;}'
            f'QTabBar::tab:selected{{background:{INK2};color:{INKT};border-bottom-color:{CYAN};}}'
            f'QTabBar::tab:hover:!selected{{background:{INK3};color:{INKT};}}')


def group():
    return (f'QGroupBox{{background:{INK2};color:{INKT};font-size:12px;'
            f'border:1px solid {LINE};border-radius:8px;margin-top:15px;padding:14px 8px 9px;}}'
            f'QGroupBox::title{{subcontrol-position:top left;left:12px;top:0;padding:0 5px;background:{INK2};}}')


def inputs():
    from .dialogs import _triangle_icon_path
    up, down = _triangle_icon_path('up', INKT), _triangle_icon_path('down', INKT)
    return (f'QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit,QPlainTextEdit,QTextBrowser{{'
            f'background:{INK0};color:{INKT};border:1px solid {LINE};border-bottom:1px solid {LINE2};'
            'border-radius:4px;padding:5px 6px;selection-background-color:#254553;}'
            f'QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus,QComboBox:focus,QTextEdit:focus{{border-bottom:2px solid {CYAN};}}'
            f'QLineEdit:disabled,QSpinBox:disabled,QComboBox:disabled{{color:#777777;background:{INK2};}}'
            'QSpinBox,QDoubleSpinBox{padding-right:20px;}'
            'QSpinBox::up-button,QDoubleSpinBox::up-button{subcontrol-origin:border;subcontrol-position:top right;width:18px;border:0;}'
            'QSpinBox::down-button,QDoubleSpinBox::down-button{subcontrol-origin:border;subcontrol-position:bottom right;width:18px;border:0;}'
            f'QSpinBox::up-arrow,QDoubleSpinBox::up-arrow{{image:url({up});width:10px;height:10px;}}'
            f'QSpinBox::down-arrow,QDoubleSpinBox::down-arrow{{image:url({down});width:10px;height:10px;}}'
            'QComboBox{padding-right:24px;}'
            'QComboBox::drop-down{width:22px;border:0;}'
            f'QComboBox::down-arrow{{image:url({down});width:10px;height:10px;}}'
            f'QComboBox QAbstractItemView{{background:{INK3};color:{INKT};selection-background-color:#254553;selection-color:{INKT};border:1px solid {LINE2};padding:4px;}}')


def table():
    return (f'QTableWidget,QTableView,QListWidget{{background:{INK0};alternate-background-color:{INK2};'
            f'color:{INKT};gridline-color:{LINE};border:1px solid {LINE};border-radius:6px;}}'
            f'QHeaderView::section{{background:{INK2};color:{MUTE};border:0;border-bottom:1px solid {LINE};padding:7px 5px;font-size:12px;}}'
            f'QTableWidget::item,QListWidget::item{{padding:4px;border:0;}}'
            f'QTableWidget::item:selected,QTableWidget::item:selected:!active,QListWidget::item:selected{{background:#254553;color:{INKT};}}'
            f'QTableWidget QLineEdit{{background:{INK0};color:{INKT};border:1px solid {CYAN};}}')


def menu():
    return (f'QMenuBar{{background:{INK1};color:{INKT};padding:3px 6px;border:0;}}'
            f'QMenuBar::item{{padding:7px 10px;background:transparent;border-radius:4px;}}'
            f'QMenuBar::item:selected{{background:{INK3};}}'
            f'QMenu{{background:{INK2};color:{INKT};border:1px solid {LINE2};border-radius:8px;padding:5px;}}'
            f'QMenu::item{{padding:7px 26px 7px 24px;border-radius:4px;}}'
            f'QMenu::item:selected{{background:{INK4};}}QMenu::item:disabled{{color:#777777;}}'
            f'QMenu::separator{{height:1px;background:{LINE};margin:5px 8px;}}')


def checkbox():
    return (f'QCheckBox{{color:{INKT};spacing:7px;}}'
            f'QCheckBox::indicator{{width:16px;height:16px;border:1px solid {LINE2};border-radius:4px;background:{INK0};}}'
            f'QCheckBox::indicator:hover{{border-color:{INKT};}}'
            f'QCheckBox::indicator:checked{{background:#0078d4;border-color:#0078d4;}}')


def disclosure():
    return (f'QToolButton{{background:{INK3};color:{INKT};border:1px solid {LINE};border-radius:4px;padding:6px;}}'
            f'QToolButton:hover{{background:{INK4};}}QToolButton:pressed{{background:{INK2};}}'
            f'QToolButton:focus{{border-color:{CYAN};}}QToolButton:disabled{{color:#777777;}}')


def surfaces():
    return (f'QDialog,QMessageBox,QInputDialog{{background:{INK1};color:{INKT};}}'
            f'QLabel{{color:{INKT};background:transparent;}}'
            f'QToolTip{{background:{INK3};color:{INKT};border:1px solid {LINE2};border-radius:4px;padding:7px;}}'
            f'QSplitter::handle{{background:{INK1};width:5px;height:5px;}}'
            f'QScrollArea{{border:0;background:{INK2};}}'
            f'QScrollBar:vertical{{background:transparent;width:8px;}}'
            f'QScrollBar:horizontal{{background:transparent;height:8px;}}'
            f'QScrollBar::handle{{background:{LINE2};border-radius:3px;min-width:24px;min-height:24px;}}'
            f'QScrollBar::handle:hover{{background:{MUTE};}}'
            'QScrollBar::add-line,QScrollBar::sub-line{width:0;height:0;}'
            'QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}'
            f'QProgressBar{{background:{INK3};color:{INKT};border:0;border-radius:3px;text-align:center;min-height:6px;}}'
            f'QProgressBar::chunk{{background:{CYAN};border-radius:3px;}}'
            f'QSlider::groove:horizontal{{height:4px;background:{LINE2};border-radius:2px;}}'
            f'QSlider::sub-page:horizontal{{background:{CYAN};border-radius:2px;}}'
            f'QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;background:{CYAN};border:3px solid {INKT};border-radius:9px;}}')


def stylesheet():
    return surfaces() + button() + inputs() + tabs() + group() + table() + menu() + checkbox() + disclosure()
