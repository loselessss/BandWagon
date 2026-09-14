import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PIL import Image
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QApplication, QMessageBox

from bandwagon.app import Analyzer


class RecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.location = patch("bandwagon.recovery.recovery_directory", return_value=self.directory)
        self.location.start()
        self.windows = []
        self.win = self.new_window()
        self.win._orig = Image.new("RGB", (100, 80), "white")
        self.win._after_load("test.png")

    def new_window(self):
        win = Analyzer()
        self.windows.append(win)
        return win

    def tearDown(self):
        for win in self.windows:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()
            win.deleteLater()
        self.location.stop()
        self.temp.cleanup()

    def test_autosave_preserves_dirty_state_and_skips_unchanged(self):
        self.win._autosave()
        self.assertIsNone(self.win._recovery_path)
        self.win.memo_edit.setPlainText("unsaved memo")
        saved = self.win._saved_snapshot
        self.win._autosave()
        path = self.win._recovery_path
        self.assertTrue(path.exists())
        self.assertIsNone(self.win._current_project_path)
        self.assertEqual(self.win._saved_snapshot, saved)
        with patch.object(self.win, "_write_project_file") as writer:
            self.win._autosave()
            writer.assert_not_called()

    def test_recovery_round_trip_including_uv_and_analysis_settings(self):
        self.win.memo_edit.setPlainText("recover me")
        self.win.sp_prom.setValue(75)
        self.win._band_display_style = "line"
        self.win._wb_gray_override = np.full((80, 100), 42, dtype=np.uint8)
        self.win._autosave()
        restored = self.new_window()
        self.assertTrue(restored._restore_recovery(self.win._recovery_path))
        self.assertEqual(restored.memo_edit.toPlainText(), "recover me")
        self.assertEqual(restored.sp_prom.value(), 75)
        self.assertEqual(restored._band_display_style, "line")
        np.testing.assert_array_equal(restored._wb_gray_override, self.win._wb_gray_override)
        self.assertIsNone(restored._current_project_path)
        self.assertNotEqual(restored._saved_snapshot, restored._project_state_snapshot())

    def test_manual_save_clears_recovery(self):
        self.win.memo_edit.setPlainText("saved")
        self.win._autosave()
        backup = self.win._recovery_path
        target = self.directory / "manual.bandwagon"
        self.assertTrue(self.win._write_project_file(str(target)))
        self.assertFalse(backup.exists())
        self.assertEqual(self.win._current_project_path, str(target))
        self.assertEqual(self.win._saved_snapshot, self.win._project_state_snapshot())

    def test_failed_replace_keeps_previous_project_and_recovery(self):
        target = self.directory / "manual.bandwagon"
        self.win._write_project_file(str(target))
        original = target.read_bytes()
        self.win.memo_edit.setPlainText("new work")
        self.win._autosave()
        backup = self.win._recovery_path
        old_backup = backup.read_bytes()
        self.win.memo_edit.setPlainText("newer work")
        with patch("bandwagon.fileio.os.replace", side_effect=OSError("disk error")), patch.object(self.win, "_warn"):
            self.assertFalse(self.win._write_project_file(str(target)))
            with self.assertLogs(level="ERROR"):
                self.win._autosave()
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(backup.read_bytes(), old_backup)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])

    def test_running_window_is_not_offered_for_recovery(self):
        self.win.memo_edit.setPlainText("live")
        self.win._autosave()
        other = self.new_window()
        with patch("bandwagon.recovery.QMessageBox.question") as question:
            other.offer_recovery()
            question.assert_not_called()

    def test_cancel_keeps_orphan_and_no_discards_it(self):
        self.win.memo_edit.setPlainText("orphan")
        self.win._autosave()
        path = self.win._recovery_path
        self.win._recovery_lock.unlock()
        other = self.new_window()
        with patch("bandwagon.recovery.QMessageBox.question", return_value=QMessageBox.Cancel):
            other.offer_recovery()
        self.assertTrue(path.exists())
        with patch("bandwagon.recovery.QMessageBox.question", return_value=QMessageBox.No):
            other.offer_recovery()
        self.assertFalse(path.exists())

    def test_close_cancel_retains_backup(self):
        self.win.memo_edit.setPlainText("keep")
        self.win._autosave()
        path = self.win._recovery_path
        with patch.object(QMessageBox, "exec_"), patch.object(QMessageBox, "clickedButton", return_value=None):
            event = QCloseEvent()
            self.win.closeEvent(event)
        self.assertFalse(event.isAccepted())
        self.assertTrue(path.exists())

    def test_corrupt_recovery_is_retained(self):
        path = self.directory / "broken.bandwagon"
        path.write_bytes(b"broken")
        with patch.object(self.win, "_warn"):
            self.assertFalse(self.win._restore_recovery(path))
        self.assertEqual(path.read_bytes(), b"broken")

    def test_image_replacement_retains_previous_recovery(self):
        self.win.memo_edit.setPlainText("previous session")
        self.win._autosave()
        previous = self.win._recovery_path
        self.win._orig = Image.new("RGB", (60, 40), "black")
        self.win._after_load("replacement.png")
        self.win._autosave()
        self.assertTrue(previous.exists())
        self.assertIsNone(self.win._recovery_path)

    def test_dead_process_lock_can_be_recovered_into_new_window(self):
        # os._exit deliberately skips QLockFile's destructor, like a crash.
        code = '''
import os, sys
from pathlib import Path
from PIL import Image
from PyQt5.QtWidgets import QApplication
from bandwagon.app import Analyzer
import bandwagon.recovery as recovery
recovery.recovery_directory = lambda: Path(sys.argv[1])
app = QApplication([])
win = Analyzer()
win._orig = Image.new("RGB", (30, 20), "white")
win._after_load("crashed.png")
win.memo_edit.setPlainText("survived crash")
win._autosave()
os._exit(0 if win._recovery_path.exists() else 1)
'''
        subprocess.run([sys.executable, "-c", code, str(self.directory)],
                       check=True, timeout=30, cwd=Path(__file__).resolve().parents[1])
        old_path = next(self.directory.glob("*.bandwagon"))
        recovered = []
        with patch.object(Analyzer, "_open_windows", recovered), patch(
            "bandwagon.recovery.QMessageBox.question", return_value=QMessageBox.Yes
        ):
            self.win.offer_recovery()
        self.windows.extend(recovered)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].memo_edit.toPlainText(), "survived crash")
        self.assertIsNone(recovered[0]._current_project_path)
        self.assertNotEqual(Path(recovered[0]._last_dir), self.directory)
        self.assertTrue(recovered[0]._recovery_path.exists())
        self.assertFalse(old_path.exists())


if __name__ == "__main__":
    unittest.main()
