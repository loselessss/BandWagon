import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
from PIL import Image
from PyQt5.QtCore import QPoint, QPointF, Qt, QElapsedTimer, QEvent
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QLineEdit

from bandwagon.app import Analyzer
from bandwagon.geometry import GeometryMixin
from bandwagon.imaging import find_gel_quad
from bandwagon.i18n import tr
from bandwagon.models import Lane


class GelInteractionsTest(unittest.TestCase):
    def test_lane_width_drag_highlight_clears_on_tool_switch(self):
        win = Analyzer()
        try:
            win._orig = Image.new('RGB', (200, 200), 'white')
            win._after_load('lane-highlight.png')
            lane = Lane(0, 30, 100)
            win.lanes = [lane]
            win._rebuild_lane_table()
            win.gel.set_lanes(win.lanes)
            win._select_ribbon_tool('manual_lanes')
            win.show(); self.app.processEvents()
            win.btn_lane.click()
            gel = win.gel
            start = QPoint(round(gel._ix_to_wx(lane.x2)), round(gel._rect.center().y()))
            end = QPoint(round(gel._ix_to_wx(120)), start.y())
            QTest.mousePress(gel, Qt.LeftButton, pos=start)
            QApplication.sendEvent(gel, QMouseEvent(QEvent.MouseMove, QPointF(end),
                                                   Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            QTest.mouseRelease(gel, Qt.LeftButton, pos=end)
            lane = win.lanes[0]
            self.assertGreater(lane.x2, 100)
            self.assertIs(gel.selected_lane, lane)
            win._select_ribbon_tool('lane_list')
            self.assertEqual(gel.mode, 'view')
            self.assertIsNone(gel.selected_lane)
            self.assertIsNone(gel._lane_edge_drag)
            win._select_ribbon_tool('manual_lanes')
            win.btn_lane.click()
            gel.selected_lane = lane
            QTest.keyClick(win, Qt.Key_Escape)
            self.assertIsNone(gel.selected_lane)
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_corner_guides_are_hidden_outside_corner_mode_without_losing_points(self):
        win = Analyzer()
        try:
            win._orig = Image.new('RGB', (160, 200), 'white')
            win._after_load('corner-guides.png')
            win.show(); self.app.processEvents()
            points = [(10, 10), (145, 15), (150, 185), (15, 180)]
            for tool in ('auto_lanes', 'manual_lanes', 'lane_list', 'marker', 'results'):
                win._select_ribbon_tool(tool)
                for mode in ('view', 'lane', 'vrange'):
                    with self.subTest(tool=tool, mode=mode):
                        win.gel.set_mode(mode)
                        win.gel.corners = []
                        plain = win.gel.grab().toImage()
                        win.gel.corners = list(points)
                        self.assertEqual(win.gel.grab().toImage(), plain)
                        self.assertEqual(win.gel.corners, points)
            win.gel.set_mode('corner')
            with_guides = win.gel.grab().toImage()
            win.gel.corners = []
            self.assertNotEqual(win.gel.grab().toImage(), with_guides)
            win.gel.corners = list(points)
            win._select_ribbon_tool('auto_lanes')
            self.assertEqual(win.gel.mode, 'view')
            self.assertEqual(win.gel.corners, points)
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_lane_click_in_mw_results_scrolls_to_sample_without_selecting_band(self):
        win = Analyzer()
        try:
            win._orig = Image.new('RGB', (160, 200), 'white')
            win._after_load('lane-results.png')
            win.lanes = [Lane(0, 10, 60), Lane(1, 90, 140)]
            for lane in win.lanes:
                lane.peaks = np.arange(20, 180, 5)
                lane.peak_bounds = [(int(y), int(y) + 1) for y in lane.peaks]
                lane.peak_area = np.full(len(lane.peaks), 30.0)
                lane.peak_volume = np.full(len(lane.peaks), 150.0)
            win._rebuild_lane_table(); win._refresh_results(); win.gel.set_lanes(win.lanes)
            win._select_ribbon_tool('results'); win.resize(900, 620); win.show()
            self.app.processEvents()
            pos = QPoint(round(win.gel._ix_to_wx(115)), round(win.gel._iy_to_wy(190)))
            QTest.mouseClick(win.gel, Qt.LeftButton, pos=pos)
            self.app.processEvents()
            row = len(win.lanes[0].peaks)
            self.assertEqual(win.result_table.currentRow(), row)
            self.assertEqual(win.result_table.currentColumn(), 0)
            self.assertIs(win.gel.selected_lane, win.lanes[1])
            self.assertIsNone(win.gel.selected_band)
            self.assertIs(win.tabs.currentWidget(), win.analysis_tab)
            rect = win.result_table.visualItemRect(win.result_table.item(row, 0))
            self.assertTrue(win.result_table.viewport().rect().intersects(rect))
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_for_lane_editor(self, win, row):
        # Advancing to a cell is queued; a fixed 30ms wait can send the next
        # key to the previous editor on busy Windows runners.
        timer = QElapsedTimer(); timer.start()
        while timer.elapsed() < 1000:
            editor = win.lane_table.focusWidget()
            if (win.lane_table.currentRow() == row and isinstance(editor, QLineEdit)
                    and editor.property("lane_row") == row and editor.hasFocus()):
                return editor
            QTest.qWait(10)
        self.fail(f"Lane {row} name editor did not receive focus")

    def test_guide_control_lives_on_adjust_tab(self):
        win = Analyzer()
        try:
            self.assertIs(win.chk_guides.parentWidget(), win.correction_tabs.widget(0).widget())
            self.assertTrue(win.gel.show_guides)
            win._select_ribbon_tool('curve')
            self.assertFalse(win.gel.show_guides)
            self.assertFalse(win.bow_spin.isVisibleTo(win.correction_tabs))
            self.assertTrue(win.curve.isVisibleTo(win.correction_tabs))
            win._select_ribbon_tool('rotate')
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
            win._select_ribbon_tool('lane_list')
            win.activateWindow()
            self.app.processEvents()
            win.lane_table.editItem(win.lane_table.item(0, 0))
            editor = win.lane_table.focusWidget()
            editor.setText("First")
            QTest.keyClick(editor, Qt.Key_Return)
            editor = self.wait_for_lane_editor(win, 1)
            self.assertEqual(win.lanes[0].name, "First")
            self.assertEqual(win.lane_table.currentRow(), 1)
            self.assertEqual(editor.selectedText(), "Lane 2")
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
            win.show(); win._select_ribbon_tool('manual_lanes')
            win.activateWindow()
            self.app.processEvents()
            win.lane_table.editItem(win.lane_table.item(0, 0))
            QTest.keyClick(win.lane_table.focusWidget(), Qt.Key_Return)
            editor = self.wait_for_lane_editor(win, 1)
            self.assertEqual(win.lane_table.currentRow(), 1)
            QTest.keyClick(editor, Qt.Key_Backtab)
            editor = self.wait_for_lane_editor(win, 0)
            self.assertEqual(win.lane_table.currentRow(), 0)
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
            self.assertEqual(win.analysis_notice.text(), tr("analysis_no_bands"))
            win._select_ribbon_tool('bow')
            self.assertTrue(win.bow_spin.isVisibleTo(win.correction_tabs))
            self.assertFalse(win.shear_spin.isVisibleTo(win.correction_tabs))
            win._select_ribbon_tool('shear')
            self.assertTrue(win.shear_spin.isVisibleTo(win.correction_tabs))
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
