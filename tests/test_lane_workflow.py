import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.i18n import tr


class LaneWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = Analyzer()
        image = np.full((160, 160), 230, dtype=np.uint8)
        for x in (10, 90):
            for y in (30, 70, 110):
                image[y:y + 5, x:x + 50] = 25
        self.win._orig = Image.fromarray(image).convert("RGB")
        self.win._after_load("bands.png")
        self.win.sp_lane_n.setValue(2)
        self.win._select_ribbon_tool("lane_list")

    def tearDown(self):
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close()

    def add_manual_lane(self):
        self.win._on_lane_added(10, 59)
        return self.win.lanes[0]

    def choose_marker(self):
        combo = self.win.lane_table.cellWidget(0, 1)
        combo.setCurrentIndex(1)
        combo.activated[int].emit(1)

    def test_auto_detection_also_analyzes_without_switching_tools(self):
        with patch.object(self.win, "run_analysis", wraps=self.win.run_analysis) as analyze:
            self.win._auto_lanes()
            analyze.assert_called_once()
        self.assertEqual(len(self.win.lanes), 2)
        self.assertTrue(all(len(lane.peaks) == 3 for lane in self.win.lanes))
        self.assertEqual(self.win.result_table.rowCount(), 6)
        self.assertFalse(self.win._analysis_stale)
        self.assertEqual(self.win.analysis_notice.text(), tr("analysis_ready", n=6))
        self.assertEqual(self.win.lane_table.rowCount(), 2)
        self.assertEqual(self.win.ribbon.currentIndex(), 2)

    def test_marker_selection_analyzes_manual_lane_and_opens_mw(self):
        self.add_manual_lane()
        with patch("bandwagon.lanes.MarkerDialog") as dialog:
            dialog.return_value.exec_.return_value = 1
            dialog.return_value.values.return_value = [100, 50, 25]
            self.choose_marker()
            self.assertEqual(dialog.call_args.args[0], 3)
        lane = self.win.lanes[0]
        self.assertEqual(lane.kind, "marker")
        self.assertEqual(lane.marker_mw, [100, 50, 25])
        self.assertEqual(lane.mw, [100, 50, 25])
        self.assertEqual(self.win.result_table.rowCount(), 3)
        self.assertEqual(self.win.ribbon.currentIndex(), 2)

    def test_marker_selection_reanalyzes_stale_results(self):
        self.add_manual_lane()
        self.win.run_analysis()
        self.win.sp_prom.setValue(self.win.sp_prom.value() - 1)
        self.assertTrue(self.win._analysis_stale)
        with patch.object(self.win, "run_analysis", wraps=self.win.run_analysis) as analyze, \
                patch("bandwagon.lanes.MarkerDialog") as dialog:
            dialog.return_value.exec_.return_value = 0
            self.choose_marker()
            analyze.assert_called_once()
            dialog.assert_called_once()
        self.assertFalse(self.win._analysis_stale)
        self.assertEqual(self.win.lanes[0].kind, "sample")

    def test_marker_cancel_keeps_original_type_and_can_reopen(self):
        self.win._auto_lanes()
        with patch("bandwagon.lanes.MarkerDialog") as dialog, \
                patch.object(self.win, "run_analysis", wraps=self.win.run_analysis) as analyze:
            dialog.return_value.exec_.return_value = 0
            self.choose_marker()
            self.assertEqual(self.win.lanes[0].kind, "sample")
            self.assertEqual(self.win.lane_table.cellWidget(0, 1).currentIndex(), 0)
            dialog.return_value.exec_.return_value = 1
            dialog.return_value.values.return_value = [100, 50, 25]
            self.choose_marker()
            self.choose_marker()
            self.assertEqual(dialog.call_count, 3)
            analyze.assert_not_called()
        self.assertEqual(self.win.lanes[0].kind, "marker")

    def test_no_bands_explains_settings_without_changing_type(self):
        self.win._orig = Image.new("RGB", (160, 160), "white")
        self.win._after_load("blank.png")
        self.add_manual_lane()
        with patch.object(self.win, "_info") as info, \
                patch("bandwagon.lanes.MarkerDialog") as dialog:
            self.choose_marker()
            dialog.assert_not_called()
            info.assert_called_once_with(tr("no_bands_title"), tr("no_bands_run_analysis_msg"))
        self.assertEqual(self.win.lanes[0].kind, "sample")
        self.assertEqual(self.win.lane_table.cellWidget(0, 1).currentIndex(), 0)

    def test_full_workflow_opens_mw_results_after_marker_confirmation(self):
        self.win._auto_lanes()
        self.win._select_ribbon_tool('manual_lanes')
        self.win.btn_detect_bands.click()
        self.assertEqual(self.win._active_tool, 'manual_lanes')
        self.win.ribbon_strips[2].buttons['marker'].click()
        self.assertEqual(self.win._active_tool, 'marker')
        self.win.marker_lane_combo.setCurrentIndex(1)
        self.assertIs(self.win.gel.selected_lane, self.win.lanes[1])
        with patch('bandwagon.lanes.MarkerDialog') as dialog:
            dialog.return_value.exec_.return_value = 1
            dialog.return_value.values.return_value = [100, 50, 25]
            self.win.btn_marker_setup.click()
        self.assertEqual(self.win.lanes[1].kind, 'marker')
        self.assertEqual(self.win._active_tool, 'results')
        self.assertTrue(all(len(lane.mw) == 3 for lane in self.win.lanes))
        self.assertNotEqual(self.win.mw_r2_label.text(), tr('mw_regression_placeholder'))
        self.win._select_ribbon_tool('marker')
        self.assertEqual(self.win.marker_lane_combo.currentIndex(), 1)

    def test_marker_setup_cancel_keeps_preview_and_kind(self):
        self.win._auto_lanes()
        self.win._select_ribbon_tool('marker')
        with patch('bandwagon.lanes.MarkerDialog') as dialog:
            dialog.return_value.exec_.return_value = 0
            self.win.btn_marker_setup.click()
        self.assertEqual(self.win._active_tool, 'marker')
        self.assertEqual(self.win.lanes[0].kind, 'sample')

    def test_preset_can_be_chosen_before_lane_and_applies_without_dialog(self):
        presets = [{'name': 'Test ladder', 'mw': [100, 50, 25]}]
        with patch('bandwagon.lanes.load_marker_presets', return_value=presets), \
                patch('bandwagon.dialogs.load_marker_presets', return_value=presets):
            self.win._select_ribbon_tool('marker')
            self.assertFalse(self.win.btn_marker_setup.isEnabled())
            self.win.marker_preset_combo.setCurrentIndex(1)
            self.win._auto_lanes()
            self.assertEqual(self.win.marker_preset_combo.currentText(), 'Test ladder')
            self.win.marker_lane_combo.setCurrentIndex(1)
            with patch('bandwagon.lanes.MarkerDialog') as dialog:
                self.win.btn_marker_setup.click()
                dialog.assert_not_called()
            self.assertEqual(self.win.lanes[0].kind, 'sample')
            self.assertEqual(self.win.lanes[1].marker_mw, [100, 50, 25])
            self.assertEqual(self.win._active_tool, 'results')
            self.assertTrue(self.win.lanes[0].mw)
            presets[0]['mw'][0] = 200
            self.assertEqual(self.win.lanes[1].marker_mw[0], 100)
            self.win._undo()
            self.assertEqual(self.win.lanes[1].kind, 'sample')
            self.win._redo()
            self.assertEqual(self.win.lanes[1].kind, 'marker')
            self.assertEqual(self.win.lanes[1].marker_mw, [100, 50, 25])

    def test_matching_preset_reanalyzes_stale_bands_and_applies_immediately(self):
        presets = [{'name': 'Test ladder', 'mw': [100, 50, 25]}]
        with patch('bandwagon.lanes.load_marker_presets', return_value=presets):
            self.win._auto_lanes()
            self.win._select_ribbon_tool('marker')
            self.win.marker_preset_combo.setCurrentIndex(1)
            self.win.sp_prom.setValue(95)
            self.assertTrue(self.win._analysis_stale)
            with patch.object(self.win, 'run_analysis', wraps=self.win.run_analysis) as analyze, \
                    patch('bandwagon.lanes.MarkerDialog') as dialog:
                self.win.btn_marker_setup.click()
                analyze.assert_called_once()
                dialog.assert_not_called()
            self.assertEqual(self.win.lanes[0].marker_mw, [100, 50, 25])
            self.assertFalse(self.win._analysis_stale)
            self.assertEqual(self.win._active_tool, 'results')
            self.assertTrue(self.win.lanes[1].mw)

    def test_preset_mismatch_keeps_band_matching_confirmation_and_cancel(self):
        from bandwagon.dialogs import MarkerDialog
        presets = [{'name': 'Short ladder', 'mw': [100, 25]}]
        with patch('bandwagon.lanes.load_marker_presets', return_value=presets), \
                patch('bandwagon.dialogs.load_marker_presets', return_value=presets):
            self.win._auto_lanes()
            self.win._select_ribbon_tool('marker')
            self.win.marker_preset_combo.setCurrentIndex(1)
            def cancel(dialog):
                self.assertEqual(len(dialog.match_combos), 3)
                self.assertEqual(dialog.values(), [100, 25, 0])
                return 0
            with patch.object(MarkerDialog, 'exec_', cancel):
                self.win.btn_marker_setup.click()
            self.assertEqual(self.win.lanes[0].kind, 'sample')
            self.assertEqual(self.win.lanes[0].marker_mw, [])
            self.assertEqual(self.win.marker_preset_combo.currentText(), 'Short ladder')

    def test_missing_reference_points_stay_in_marker_setup(self):
        self.win._auto_lanes()
        self.win._select_ribbon_tool('marker')
        with patch('bandwagon.lanes.MarkerDialog') as dialog:
            dialog.return_value.exec_.return_value = 1
            dialog.return_value.values.return_value = [100, 0, 0]
            self.win.btn_marker_setup.click()
        self.assertEqual(self.win._active_tool, 'marker')
        self.assertEqual(self.win.mw_r2_label.text(), tr('mw_regression_placeholder'))
        self.assertTrue(all(not lane.mw for lane in self.win.lanes))

    def test_removing_marker_and_undo_recalculate_mw(self):
        self.win._auto_lanes()
        with patch('bandwagon.lanes.MarkerDialog') as dialog:
            dialog.return_value.exec_.return_value = 1
            dialog.return_value.values.return_value = [100, 50, 25]
            self.choose_marker()
        self.assertTrue(self.win.lanes[1].mw)
        combo = self.win.lane_table.cellWidget(0, 1)
        combo.setCurrentIndex(0); combo.activated[int].emit(0)
        self.assertTrue(all(not lane.mw for lane in self.win.lanes))
        self.assertEqual(self.win.mw_r2_label.text(), tr('mw_regression_placeholder'))
        self.win._undo()
        self.assertEqual(self.win.lanes[0].kind, 'marker')
        self.assertTrue(self.win.lanes[1].mw)
        self.win._redo()
        self.assertTrue(all(not lane.mw for lane in self.win.lanes))

    def test_unmatched_marker_band_stays_zero_not_point_one(self):
        from bandwagon.dialogs import MarkerDialog
        with patch('bandwagon.dialogs.load_marker_presets', return_value=[]):
            dialog = MarkerDialog(3, [100, 0, 25], self.win)
        try:
            self.assertEqual(dialog.values(), [100, 0, 25])
            dialog._apply_match(0, 0, [100, 50, 25])
            self.assertEqual(dialog.values()[0], 0)
        finally:
            dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
