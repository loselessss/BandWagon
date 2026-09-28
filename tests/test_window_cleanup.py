import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PIL import Image
from PyQt5.QtCore import QCoreApplication, QEvent
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5 import sip
from bandwagon.app import Analyzer


class WindowCleanupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_window(self):
        win = Analyzer()
        Analyzer._open_windows.append(win)
        win._orig = Image.new("RGB", (100, 80), "white")
        win._after_load("test.png")
        return win

    def test_repeated_close_releases_images_and_widgets(self):
        count = len(Analyzer._open_windows)
        for _ in range(3):
            win = self.make_window()
            self.assertTrue(win.close())
            self.assertEqual(len(Analyzer._open_windows), count)
            self.assertIsNone(win._orig)
            self.assertIsNone(win._pristine_orig)
            self.assertIsNone(win.gel._pm)
            self.assertFalse(win._title_timer.isActive())
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.assertTrue(sip.isdeleted(win))

    def test_cancel_preserves_window_and_image(self):
        win = self.make_window()
        original = win._orig
        win.memo_edit.setPlainText("unsaved")
        with patch.object(QMessageBox, "exec_"), patch.object(
                QMessageBox, "clickedButton", return_value=None):
            self.assertFalse(win.close())
        self.assertIn(win, Analyzer._open_windows)
        self.assertIs(win._orig, original)
        self.assertFalse(win._closing)
        win._saved_snapshot = win._project_state_snapshot()
        win.close()

    def test_update_check_delays_deletion_but_releases_image(self):
        win = self.make_window()
        from unittest.mock import Mock
        worker = Mock()
        win._update_worker = worker
        win.close()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertFalse(sip.isdeleted(win))
        self.assertIsNone(win._orig)
        with patch.object(win, "_info") as info:
            win._update_check_completed(None, True)
            info.assert_not_called()
        win._update_check_finished()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertTrue(sip.isdeleted(win))
