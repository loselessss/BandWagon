import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer


class UndoHistoryTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Analyzer()
        self.window._orig = Image.new("RGB", (100, 80), "white")
        self.window._after_load("undo-test.png")

    def tearDown(self):
        self.window._saved_snapshot = self.window._project_state_snapshot()
        self.window.close()
        self.window.deleteLater()

    def test_document_details_undo_and_redo_in_order(self):
        self.assertEqual(self.window._EDIT_MAX, 200)

        self.window.sp_prom.setValue(80)
        self.assertEqual(len(self.window._edit_ops), 1)
        self.window._commit_document_state()
        self.window.memo_edit.setPlainText("note")
        self.window._finish_memo_group()
        self.window._switch_channel("Red")

        self.window._undo()
        self.assertEqual(self.window._ch, "RGB")
        self.assertEqual(self.window.memo_edit.toPlainText(), "note")
        self.assertEqual(self.window.sp_prom.value(), 80)

        self.window._undo()
        self.assertEqual(self.window.memo_edit.toPlainText(), "")
        self.assertEqual(self.window.sp_prom.value(), 80)

        self.window._undo()
        self.assertEqual(self.window.sp_prom.value(), 90)

        self.window._redo()
        self.window._redo()
        self.window._redo()
        self.assertEqual(
            (self.window.sp_prom.value(), self.window.memo_edit.toPlainText(),
             self.window._ch),
            (80, "note", "Red"),
        )

    def test_continuous_memo_typing_is_one_step(self):
        self.window.memo_edit.setPlainText("a")
        self.window.memo_edit.setPlainText("ab")
        self.assertEqual(len(self.window._edit_ops), 1)

        self.window._finish_memo_group()
        self.window.memo_edit.setPlainText("abc")
        self.window._finish_memo_group()
        self.assertEqual(len(self.window._edit_ops), 2)

        self.window._undo()
        self.assertEqual(self.window.memo_edit.toPlainText(), "ab")
        self.window._undo()
        self.assertEqual(self.window.memo_edit.toPlainText(), "")

    def test_memo_history_does_not_move_typing_cursor(self):
        self.window.memo_edit.setPlainText("ac")
        cursor = self.window.memo_edit.textCursor()
        cursor.setPosition(1)
        self.window.memo_edit.setTextCursor(cursor)

        self.window.memo_edit.insertPlainText("b")

        self.assertEqual(self.window.memo_edit.toPlainText(), "abc")
        self.assertEqual(self.window.memo_edit.textCursor().position(), 2)

    def test_geometry_undo_restores_previous_vertical_range(self):
        self.window.gel.vrange = (10, 60)
        self.window._commit_document_state()

        self.window._rotate(90)
        self.assertIsNone(self.window.gel.vrange)

        self.window._undo()
        self.assertEqual(self.window.gel.vrange, (10, 60))

        self.window._redo()
        self.assertIsNone(self.window.gel.vrange)

    def test_undo_captures_unfinished_fine_rotation_preview(self):
        self.window.rot_slider.setValue(3)
        self.assertEqual(self.window._edit_pos, -1)

        self.window._undo()

        self.assertEqual(len(self.window._edit_ops), 1)
        self.assertEqual(self.window._edit_pos, -1)
        self.assertEqual(self.window.rot_slider.value(), 0)
        self.assertTrue(self.window.btn_redo.isEnabled())

    def test_history_keeps_latest_two_hundred_steps(self):
        for i in range(205):
            self.window.memo_edit.setPlainText(f"note-{i}")
            self.window._finish_memo_group()

        self.assertEqual(len(self.window._edit_ops), 200)
        for _ in range(200):
            self.window._undo()
        self.assertEqual(self.window.memo_edit.toPlainText(), "note-4")

    def test_project_restores_channel_and_band_display_style(self):
        self.window._switch_channel("Blue")
        self.window.combo_band_style.setCurrentIndex(1)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = str(Path(temp_dir) / "history.bandwagon")
            self.window._write_project_file(path)

            self.window._switch_channel("RGB")
            self.window.combo_band_style.setCurrentIndex(0)
            self.window.open_project(path)

        self.assertEqual(self.window._ch, "Blue")
        self.assertEqual(self.window._band_display_style, "line")
        self.assertEqual(self.window.combo_band_style.currentIndex(), 1)


if __name__ == "__main__":
    unittest.main()
