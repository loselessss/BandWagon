import os
import subprocess
import sys
import tempfile
import unittest
import json
import threading
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PIL import Image
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

from bandwagon.app import Analyzer
from bandwagon.recovery import RecoveryWriter


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

    def autosave(self):
        self.win._autosave()
        self.wait_for_save(self.win)

    def wait_for_save(self, win):
        import time
        deadline = time.monotonic() + 10
        while win._recovery_worker is not None:
            self.app.processEvents()
            if time.monotonic() > deadline:
                self.fail("Autosave did not finish")
            time.sleep(0.005)

    def new_window(self):
        win = Analyzer()
        self.windows.append(win)
        return win

    def tearDown(self):
        for win in self.windows:
            self.wait_for_save(win)
            win._saved_snapshot = win._project_state_snapshot()
            win.close()
            win.deleteLater()
        self.location.stop()
        self.temp.cleanup()

    @contextmanager
    def paused_save(self):
        entered, release = threading.Event(), threading.Event()
        original = RecoveryWriter.run

        def run(worker):
            entered.set()
            if not release.wait(10):
                worker.error = "Test timed out"
                return
            original(worker)

        with patch.object(RecoveryWriter, "run", run):
            self.win._autosave()
            self.assertTrue(entered.wait(3))
            try:
                yield self.win._recovery_path
            finally:
                release.set()
                self.wait_for_save(self.win)

    def test_ui_remains_responsive_and_revision_is_captured(self):
        self.win.memo_edit.setPlainText("first revision")
        with self.paused_save() as path:
            worker = self.win._recovery_worker
            heartbeat = []
            QTimer.singleShot(0, lambda: heartbeat.append(True))
            self.app.processEvents()
            self.assertEqual(heartbeat, [True])
            self.win.memo_edit.setPlainText("second revision")
            self.win._autosave()
            self.assertIs(self.win._recovery_worker, worker)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(json.loads(archive.read("project.json"))["memo"], "first revision")
        self.assertNotEqual(self.win._recovery_snapshot, self.win._project_state_snapshot())
        self.autosave()
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(json.loads(archive.read("project.json"))["memo"], "second revision")

    def test_manual_save_invalidates_pending_autosave(self):
        self.win.memo_edit.setPlainText("manual wins")
        with self.paused_save() as path:
            self.assertTrue(self.win._write_project_file(str(self.directory / "manual.bandwagon")))
        self.assertFalse(path.exists())
        self.assertIsNone(self.win._recovery_snapshot)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])

    def test_replacing_image_preserves_pending_previous_session(self):
        self.win.memo_edit.setPlainText("previous session")
        with self.paused_save() as path:
            self.win._orig = Image.new("RGB", (60, 40), "black")
            self.win._after_load("replacement.png")
            self.win._clear_recovery()
        self.assertTrue(path.exists())
        self.assertIsNone(self.win._recovery_path)
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(json.loads(archive.read("project.json"))["memo"], "previous session")

    def test_close_during_autosave_discards_pending_file(self):
        self.win.memo_edit.setPlainText("closing")
        with self.paused_save() as path:
            self.win._saved_snapshot = self.win._project_state_snapshot()
            self.win.close()
            self.assertTrue(self.win._closing)
        self.assertFalse(path.exists())
        self.assertEqual(list(self.directory.glob("*.tmp")), [])
        self.windows.remove(self.win)

    def test_background_encoding_failure_keeps_previous_backup(self):
        self.win.memo_edit.setPlainText("safe revision")
        self.autosave()
        path = self.win._recovery_path
        previous = path.read_bytes()
        self.win.memo_edit.setPlainText("failed revision")
        with patch.object(Image.Image, "save", side_effect=MemoryError("low memory")):
            with self.assertLogs(level="ERROR"):
                self.autosave()
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])
        self.assertNotEqual(self.win._recovery_snapshot, self.win._project_state_snapshot())

    def test_autosave_preserves_dirty_state_and_skips_unchanged(self):
        self.autosave()
        self.assertIsNone(self.win._recovery_path)
        self.win.memo_edit.setPlainText("unsaved memo")
        saved = self.win._saved_snapshot
        self.autosave()
        path = self.win._recovery_path
        self.assertTrue(path.exists())
        self.assertIsNone(self.win._current_project_path)
        self.assertEqual(self.win._saved_snapshot, saved)
        with patch.object(self.win, "_write_project_file") as writer:
            self.autosave()
            writer.assert_not_called()

    def test_recovery_round_trip_including_uv_and_analysis_settings(self):
        self.win.memo_edit.setPlainText("recover me")
        self.win.sp_prom.setValue(75)
        self.win._band_display_style = "line"
        self.win._wb_gray_override = np.full((80, 100), 42, dtype=np.uint8)
        self.autosave()
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
        self.autosave()
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
        self.autosave()
        backup = self.win._recovery_path
        old_backup = backup.read_bytes()
        self.win.memo_edit.setPlainText("newer work")
        with patch("bandwagon.fileio.os.replace", side_effect=OSError("disk error")), patch.object(self.win, "_warn"):
            self.assertFalse(self.win._write_project_file(str(target)))
            with self.assertLogs(level="ERROR"):
                self.autosave()
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(backup.read_bytes(), old_backup)
        self.assertEqual(list(self.directory.glob("*.tmp")), [])

    def test_running_window_is_not_offered_for_recovery(self):
        self.win.memo_edit.setPlainText("live")
        self.autosave()
        other = self.new_window()
        with patch("bandwagon.recovery.QMessageBox.question") as question:
            other.offer_recovery()
            question.assert_not_called()

    def test_cancel_keeps_orphan_and_no_discards_it(self):
        self.win.memo_edit.setPlainText("orphan")
        self.autosave()
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
        self.autosave()
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
        self.autosave()
        previous = self.win._recovery_path
        self.win._orig = Image.new("RGB", (60, 40), "black")
        self.win._after_load("replacement.png")
        self.autosave()
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
while win._recovery_worker is not None:
    app.processEvents()
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
        self.assertEqual(recovered[0]._recovery_path, old_path)


if __name__ == "__main__":
    unittest.main()
