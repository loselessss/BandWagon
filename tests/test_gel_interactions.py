import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.geometry import GeometryMixin
from bandwagon.imaging import find_gel_quad
from bandwagon.i18n import tr
from bandwagon.models import Lane


class GelInteractionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_guide_control_lives_on_adjust_tab(self):
        win = Analyzer()
        try:
            self.assertIs(win.chk_guides.parentWidget(), win.tabs.widget(0).widget())
            self.assertTrue(win.gel.show_guides)
            win.tabs.setCurrentWidget(win.analysis_tab)
            self.assertFalse(win.gel.show_guides)
            win.tabs.setCurrentIndex(0)
            win.chk_guides.setChecked(False)
            self.assertFalse(win.gel.show_guides)
        finally:
            win.close()

    def test_enter_after_lane_name_opens_next_name(self):
        win = Analyzer()
        try:
            win._orig = Image.new("RGB", (100, 100), "white")
            win._after_load("sample.png")
            win.lanes = [Lane(0, 10, 30), Lane(1, 40, 60)]
            win._rebuild_lane_table()
            win.show()
            win.tabs.setCurrentIndex(1)
            self.app.processEvents()
            win.lane_table.editItem(win.lane_table.item(0, 0))
            editor = win.lane_table.focusWidget()
            editor.setText("First")
            QTest.keyClick(editor, Qt.Key_Return)
            QTest.qWait(50)
            self.assertEqual(win.lanes[0].name, "First")
            self.assertEqual(win.lane_table.currentRow(), 1)
            self.assertEqual(win.lane_table.focusWidget().selectedText(), "Lane 2")
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_copy_uses_shared_export_dialog(self):
        win = Analyzer()
        try:
            lane = Lane(0, 10, 50)
            lane.kind = "marker"
            lane.peaks = [40]
            win.lanes = [lane]

            from bandwagon.export_dialog import ExportDialog
            def choose_marker_overlay(dialog):
                self.assertIsInstance(dialog, ExportDialog)
                dialog.checks["photo"].setChecked(False)
                dialog.checks["annotation"].setChecked(False)
                return ExportDialog.Accepted

            with patch.object(ExportDialog, "exec_", choose_marker_overlay):
                options = win._export_options(Image.new("RGB", (100, 100)))
                self.assertFalse(options["photo"])
                self.assertFalse(options["annotation"])
                self.assertTrue(options["marker_mw"])
        finally:
            win.close()

    def test_lane_keyboard_navigation_and_escape(self):
        win = Analyzer()
        try:
            win._orig = Image.new("RGB", (100, 100), "white")
            win._after_load("sample.png")
            win.lanes = [Lane(0, 10, 30), Lane(1, 40, 60)]
            win._rebuild_lane_table()
            win.show(); win.tabs.setCurrentIndex(1)
            self.app.processEvents()
            win.lane_table.editItem(win.lane_table.item(0, 0))
            QTest.keyClick(win.lane_table.focusWidget(), Qt.Key_Return)
            QTest.qWait(30)
            self.assertEqual(win.lane_table.currentRow(), 1)
            QTest.keyClick(win.lane_table.focusWidget(), Qt.Key_Backtab)
            QTest.qWait(30)
            self.assertEqual(win.lane_table.currentRow(), 0)
            editor = win.lane_table.focusWidget()
            editor.setText("Discard this")
            QTest.keyClick(editor, Qt.Key_Escape)
            self.assertEqual(win.lanes[0].name, "Lane 1")
            win.btn_lane.click()
            self.assertEqual(win.gel.mode, "lane")
            QTest.keyClick(win, Qt.Key_Escape)
            self.assertEqual(win.gel.mode, "view")
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_analysis_status_and_lane_selection(self):
        win = Analyzer()
        try:
            win._orig = Image.new("RGB", (100, 100), "white")
            win._after_load("sample.png")
            win.lanes = [Lane(0, 10, 30), Lane(1, 40, 60)]
            win._rebuild_lane_table()
            win.lane_table.setCurrentCell(1, 0)
            self.assertIs(win.gel.selected_lane, win.lanes[1])
            win._on_gel_lane_selected(win.lanes[0])
            self.assertEqual(win.lane_table.currentRow(), 0)
            win.sp_prom.setValue(win.sp_prom.value() - 1)
            self.assertEqual(win.analysis_notice.text(), tr("analysis_stale"))
            win.run_analysis()
            self.assertFalse(win._analysis_stale)
            self.assertEqual(win.analysis_notice.text(), tr("analysis_empty"))
            self.assertFalse(win.advanced_geometry_toggle.isChecked())
            self.assertFalse(win.band_settings_toggle.isChecked())
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_canvas_band_opens_matching_intensity_row(self):
        win = Analyzer()
        try:
            win._orig = Image.new("RGB", (100, 100), "white")
            win._after_load("sample.png")
            lane = Lane(0, 20, 60)
            lane.peaks = np.array([40, 70])
            lane.peak_bounds = [(35, 45), (65, 75)]
            lane.peak_area = np.array([12.5, 34.5])
            win.lanes = [lane]
            win.gel.set_lanes(win.lanes)
            win._refresh_results()
            win.show()
            self.app.processEvents()
            win.tabs.setCurrentIndex(1)
            for style, band_index in (("area", 0), ("line", 1)):
                win.gel.band_display_style = style
                y = 40 if band_index == 0 else 70
                pos = QPoint(round(win.gel._ix_to_wx(40)), round(win.gel._iy_to_wy(y)))
                QTest.mouseClick(win.gel, Qt.LeftButton, pos=pos)
                self.assertIs(win.tabs.currentWidget(), win.analysis_tab)
                self.assertEqual(win.result_table.currentRow(), band_index)
                self.assertEqual(win.result_table.currentColumn(), 3)
                self.assertEqual(win.result_table.item(band_index, 3).text(),
                                 "12.5" if band_index == 0 else "34.5")
                self.assertEqual(win.gel.selected_band, (lane, band_index))
                win.tabs.setCurrentIndex(1)
            win.gel.show_overlay = False
            QTest.mouseClick(win.gel, Qt.LeftButton,
                             pos=QPoint(round(win.gel._ix_to_wx(40)),
                                        round(win.gel._iy_to_wy(40))))
            self.assertEqual(win.tabs.currentIndex(), 1)
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_blue_gel_is_found_inside_vignetted_camera_frame(self):
        h, w = 380, 420
        y, x = np.mgrid[:h, :w]
        lighting = np.clip(210 - 25 * ((x - w / 2) / w) ** 2
                           - 28 * ((y - h / 2) / h) ** 2, 0, 255).astype(np.uint8)
        image = np.repeat(lighting[:, :, None], 3, axis=2)
        expected = np.array([[95, 60], [370, 80], [350, 320], [80, 300]], np.float32)
        cv2.fillConvexPoly(image, expected.astype(np.int32), (115, 150, 195))
        for row in (110, 175, 240):
            cv2.line(image, (130, row), (325, row + 8), (70, 95, 140), 7)
        quad = find_gel_quad(image)
        self.assertIsNotNone(quad)
        ordered = GeometryMixin._order_corners(quad)
        self.assertLess(float(np.max(np.linalg.norm(ordered - expected, axis=1))), 25)

    def test_camera_frame_is_not_accepted_as_gel(self):
        image = np.full((300, 400, 3), 210, dtype=np.uint8)
        cv2.rectangle(image, (0, 0), (399, 299), (30, 30, 30), 18)
        self.assertIsNone(find_gel_quad(image))

    def test_gray_gel_survives_uneven_lighting(self):
        h, w = 400, 500
        y, x = np.mgrid[:h, :w]
        background = np.clip(170 + 50 * x / w + 25 * y / h, 0, 255).astype(np.uint8)
        image = np.repeat(background[:, :, None], 3, axis=2)
        expected = np.array([[100, 70], [410, 55], [430, 330], [90, 345]], np.float32)
        cv2.fillConvexPoly(image, expected.astype(np.int32), (105, 105, 105))
        quad = find_gel_quad(image)
        self.assertIsNotNone(quad)
        ordered = GeometryMixin._order_corners(quad)
        self.assertLess(float(np.max(np.linalg.norm(ordered - expected, axis=1))), 20)

    def test_auto_warp_uses_detected_corners(self):
        image = np.full((380, 420, 3), 205, dtype=np.uint8)
        corners = np.array([[95, 60], [370, 80], [350, 320], [80, 300]], np.int32)
        cv2.fillConvexPoly(image, corners, (115, 150, 195))
        win = Analyzer()
        try:
            win._orig = Image.fromarray(image)
            win._after_load("gel.png")
            with patch.object(win, "_ask", return_value=True):
                win._auto_warp()
            self.assertLess(win._orig.width, 420)
            self.assertLess(win._orig.height, 380)
            self.assertEqual(win._edit_ops[-1][0], "warp")
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()


if __name__ == "__main__":
    unittest.main()
