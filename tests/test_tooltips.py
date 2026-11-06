import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PyQt5.QtCore import QEvent, QPoint
from PyQt5.QtGui import QHelpEvent
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel, QTableWidget
from bandwagon.tooltips import allow_hover_help, QuietTooltips


class TooltipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_redundant_hover_help_is_blocked(self):
        policy = QuietTooltips()
        for widget in (QPushButton('Copy image'), QLabel('Sensitivity'), QTableWidget()):
            event = QHelpEvent(QEvent.ToolTip, QPoint(), QPoint())
            self.assertFalse(allow_hover_help(widget))
            self.assertTrue(policy.eventFilter(widget, event))

    def test_unlabelled_icons_and_explicit_warning_are_kept(self):
        for text in ('', '↑', '×'):
            self.assertTrue(allow_hover_help(QPushButton(text)))
        warning = QPushButton('Extrapolation')
        warning.setProperty('essentialHoverHelp', True)
        self.assertTrue(allow_hover_help(warning))
