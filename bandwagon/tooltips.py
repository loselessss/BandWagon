"""Keep hover help only where a control has no readable label."""
from PyQt5.QtCore import QObject, QEvent
from PyQt5.QtWidgets import QApplication, QWidget, QAbstractButton, QToolTip


def allow_hover_help(widget):
    if widget.property('essentialHoverHelp'):
        return True
    if not isinstance(widget, QAbstractButton):
        return False
    text = widget.text().replace('&', '').strip()
    return not text or text in ('↑', '↓', '×', '?', '←', '→')


class QuietTooltips(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.ToolTip and isinstance(obj, QWidget) and not allow_hover_help(obj):
            QToolTip.hideText()
            event.accept()
            return True
        return False


def install_quiet_tooltips():
    app = QApplication.instance()
    if not hasattr(app, '_bandwagon_tooltip_policy'):
        app._bandwagon_tooltip_policy = QuietTooltips(app)
        app.installEventFilter(app._bandwagon_tooltip_policy)
