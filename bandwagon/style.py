"""Application-wide Fluent styling; widget helpers share the same tokens."""
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor, QFont, QFontDatabase
from .theme import *
from . import fluent


class StyleMixin:
    def _apply_palette(self):
        app = QApplication.instance()
        palette = app.palette()
        for role, color in ((QPalette.Window, INK1), (QPalette.WindowText, INKT),
                            (QPalette.Base, INK0), (QPalette.AlternateBase, INK2),
                            (QPalette.Text, INKT), (QPalette.Button, INK3),
                            (QPalette.ButtonText, INKT), (QPalette.Highlight, '#254553'),
                            (QPalette.HighlightedText, INKT), (QPalette.ToolTipBase, INK3),
                            (QPalette.ToolTipText, INKT)):
            palette.setColor(role, QColor(color))
        palette.setColor(QPalette.Disabled, QPalette.Text, QColor('#777777'))
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor('#777777'))
        app.setPalette(palette)
        families = QFontDatabase().families()
        family = next((f for f in ('Segoe UI Variable', 'Segoe UI', 'Malgun Gothic') if f in families), app.font().family())
        app.setFont(QFont(family, 9))
        app.setStyleSheet(fluent.stylesheet())
        from .fluent_icons import install_icons
        install_icons(app)

    def _menubar_css(self): return fluent.menu()
    def _tabs_css(self): return fluent.tabs()
    def _group_css(self): return fluent.group()
    def _btn_css(self): return fluent.button()
    def _danger_btn_css(self, compact=False): return fluent.button(compact=compact, danger=True)
    def _btn_accent_css(self): return fluent.button(accent=True)
    def _disclosure_css(self): return fluent.disclosure()
    def _spin_css(self): return fluent.inputs()
    def _combo_css(self): return fluent.inputs()
    def _table_css(self): return fluent.table()
    def _checkbox_css(self): return fluent.checkbox()
    def _compact_btn_css(self): return fluent.button(compact=True)
