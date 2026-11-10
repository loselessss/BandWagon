import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.i18n import tr
from bandwagon.models import Lane


class LaneWorkflowTest(unittest.TestCase):
    def test_horizontal_range_limits_detection_and_restores_full_image_coordinates(self):
        self.win._select_ribbon_tool('manual_lanes')
        self.win.chk_lane_xrange.setChecked(True)
        self.win.sp_lane_left.setValue(20); self.win.sp_lane_right.setValue(139)
        with patch('bandwagon.lanes.lane_boundary_signal', return_value=np.ones(120)) as signal, \
                patch.object(self.win, '_split_lanes_by_count', return_value=[(0,59),(60,119)]), \
                patch('bandwagon.lanes.signal_lane_spans', return_value=[(5,40),(70,110)]):
            self.win._auto_lanes()
        self.assertEqual(signal.call_args.args[0].shape, (160,120))
        self.assertEqual([(lane.x1,lane.x2) for lane in self.win.lanes], [(25,60),(90,130)])
        self.assertEqual(self.win.gel.hrange, [20,139])
        self.assertEqual(self.win._capture_project_metadata()['analysis_params']['lane_xrange'], [20,139])
        self.win._select_ribbon_tool('marker')
        self.assertIsNone(self.win.gel.hrange)

    def test_invalid_horizontal_range_keeps_existing_lanes(self):
        self.win._auto_lanes()
        before = [(lane.x1,lane.x2) for lane in self.win.lanes]
        self.win.chk_lane_xrange.setChecked(True)
        self.win.sp_lane_left.setValue(100); self.win.sp_lane_right.setValue(20)
        with patch.object(self.win, '_info') as info:
            self.win._auto_lanes()
        info.assert_called_once()
        self.assertEqual([(lane.x1,lane.x2) for lane in self.win.lanes], before)

    def test_horizontal_range_resets_after_rotation_and_undo_restores_it(self):
        self.win._select_ribbon_tool('manual_lanes')
        self.win.chk_lane_xrange.setChecked(True)
        self.win.sp_lane_left.setValue(20); self.win.sp_lane_right.setValue(139)
        self.win._commit_document_state()
        self.win._rotate(90)
        self.assertIsNone(self.win._lane_xrange())
        self.win._undo()
        self.assertEqual(self.win._lane_xrange(), [20,139])

    def test_lane_sensitivity_waits_for_detection_and_is_saved_separately(self):
        self.win._auto_lanes()
        self.win.run_analysis()
        before = [(lane.x1, lane.x2) for lane in self.win.lanes]
        band_sensitivity = self.win.sp_prom.value()
        with patch.object(self.win, '_auto_lanes') as detect:
            self.win.sp_lane_sensitivity.setValue(80)
            detect.assert_not_called()
        self.assertFalse(self.win._analysis_stale)
        self.assertEqual(self.win.sp_prom.value(), band_sensitivity)
        self.assertEqual([(lane.x1, lane.x2) for lane in self.win.lanes], before)
        self.assertEqual(self.win._current_document_snapshot()['analysis_params']['lane_sensitivity'], 80)
        self.assertEqual(self.win._capture_project_metadata()['analysis_params']['lane_sensitivity'], 80)
        self.win._apply_document_snapshot({'analysis_params': {}})
        self.assertEqual(self.win.sp_lane_sensitivity.value(), 50)

    def test_marker_selection_fits_only_untouched_auto_lanes(self):
        signal = np.zeros(160); signal[20:50] = 1; signal[95:145] = 1
        with patch('bandwagon.lanes.lane_boundary_signal', return_value=signal):
            self.win._auto_lanes()
        before = [(lane.x1, lane.x2) for lane in self.win.lanes]
        self.win.lane_table.item(1, 0).setText('Sample')
        self.win.lane_table.cellWidget(0, 1).activated[int].emit(1)
        after = [(lane.x1, lane.x2) for lane in self.win.lanes]
        self.assertLess(after[0][1] - after[0][0], before[0][1] - before[0][0])
        self.assertEqual({b-a+1 for a, b in after}, {32})
        self.assertTrue(all(abs((a+b)-(c+d)) <= 1 for (a,b),(c,d) in zip(before, after)))
        self.assertEqual(self.win.lanes[1].name, 'Sample')
        self.assertTrue(all(lane.peaks is None for lane in self.win.lanes))
        self.win._undo()
        self.assertEqual([(lane.x1, lane.x2) for lane in self.win.lanes], before)
        self.win._redo()
        self.assertEqual([(lane.x1, lane.x2) for lane in self.win.lanes], after)

    def test_marker_selection_never_overwrites_manually_adjusted_width(self):
        signal = np.zeros(160); signal[20:50] = 1; signal[95:145] = 1
        with patch('bandwagon.lanes.lane_boundary_signal', return_value=signal):
            self.win._auto_lanes()
        self.win.lanes[0].x1 += 2
        self.win._on_lane_edge_changed()
        before = [(lane.x1, lane.x2) for lane in self.win.lanes]
        self.win.lane_table.cellWidget(0, 1).activated[int].emit(1)
        self.assertEqual([(lane.x1, lane.x2) for lane in self.win.lanes], before)

    def test_auto_lanes_measure_marker_width_instead_of_image_margin(self):
        preset = {'name': 'Three bands', 'mw': [100, 50, 25]}
        self.win.marker_preset_combo.addItem(preset['name'], preset)
        self.win.marker_preset_combo.setCurrentIndex(self.win.marker_preset_combo.count() - 1)
        self.win._select_ribbon_tool('manual_lanes')
        self.win._auto_lanes(); self.win.run_analysis()
        self.assertGreater(self.win.lanes[0].x1, 0)
        self.assertLess(self.win.lanes[-1].x2, 159)
        self.assertEqual(len({lane.x2 - lane.x1 + 1 for lane in self.win.lanes}), 1)
        self.assertEqual(self.win.lanes[0].kind, 'marker')
        self.assertTrue(self.win.lanes[1].mw)
        self.assertEqual(self.win._active_tool, 'manual_lanes')

    def test_legacy_overlapping_lanes_are_not_analyzed_twice(self):
        self.win.lanes = [Lane(0, 10, 90), Lane(1, 80, 140)]
        with patch.object(self.win, '_info') as info, patch.object(Lane, 'analyze') as analyze:
            self.assertFalse(self.win.run_analysis())
        info.assert_called_once()
        analyze.assert_not_called()

    def test_reference_layout_preserves_marker_metadata_and_undo(self):
        self.win._auto_lanes(); self.win.run_analysis()
        reference = self.win.lanes[0]
        reference.x1, reference.x2 = 5, 74
        reference.kind = 'marker'; reference.name = 'My ladder'
        reference.marker_mw = [100, 50, 25]
        self.win._commit_lanes()
        self.win.gel.selected_lane = self.win.lanes[0]
        previous = [lane.to_dict() for lane in self.win.lanes]
        self.win._lanes_from_reference()
        self.assertEqual([(lane.x1, lane.x2) for lane in self.win.lanes], [(5, 74), (75, 144)])
        self.assertEqual(self.win.lanes[0].name, 'My ladder')
        self.assertEqual(self.win.lanes[0].kind, 'marker')
        self.assertEqual(self.win.lanes[0].marker_mw, [100, 50, 25])
        self.assertIs(self.win.gel.selected_lane, self.win.lanes[0])
        self.assertTrue(all(lane.profile is not None for lane in self.win.lanes))
        after = [lane.to_dict() for lane in self.win.lanes]
        self.win._undo()
        self.assertEqual([lane.to_dict() for lane in self.win.lanes], previous)
        self.win._redo()
        self.assertEqual([lane.to_dict() for lane in self.win.lanes], after)

    def test_invalid_reference_layout_keeps_previous_lanes_and_analysis(self):
        self.win._auto_lanes(); self.win.run_analysis()
        self.win.gel.selected_lane = self.win.lanes[0]
        before = [lane.to_dict() for lane in self.win.lanes]
        self.win.sp_lane_n.setValue(4)
        with patch.object(self.win, '_info') as info, patch.object(self.win, 'run_analysis') as analyze:
            self.win._lanes_from_reference()
        info.assert_called_once()
        analyze.assert_not_called()
        self.assertEqual([lane.to_dict() for lane in self.win.lanes], before)

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
        self.win._select_ribbon_tool('marker')
        combo = self.win.lane_table.cellWidget(0, 1)
        combo.setCurrentIndex(1)
        combo.activated[int].emit(1)

    def test_explicit_band_analysis_after_lane_detection_keeps_tool(self):
        with patch.object(self.win, "run_analysis", wraps=self.win.run_analysis) as analyze:
            self.win._auto_lanes(); self.win.run_analysis()
            analyze.assert_called_once()
        self.assertEqual(len(self.win.lanes), 2)
        self.assertTrue(all(len(lane.peaks) == 3 for lane in self.win.lanes))
        self.assertEqual(self.win.result_table.rowCount(), 6)
        self.assertFalse(self.win._analysis_stale)
        self.assertEqual(self.win.analysis_notice.text(), tr("analysis_ready", n=6))
        self.assertEqual(self.win.lane_table.rowCount(), 2)
        self.assertEqual(self.win.ribbon.currentIndex(), 1)

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
        self.win._auto_lanes(); self.win.run_analysis()
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
        self.win._auto_lanes(); self.win.run_analysis()
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
        self.assertEqual(self.win._active_tool, 'marker')
        self.assertTrue(all(len(lane.mw) == 3 for lane in self.win.lanes))
        self.assertNotEqual(self.win.mw_r2_label.text(), tr('mw_regression_placeholder'))
        self.win._select_ribbon_tool('marker')
        self.assertEqual(self.win.marker_lane_combo.currentIndex(), 1)

    def test_marker_setup_cancel_keeps_preview_and_kind(self):
        self.win._auto_lanes(); self.win.run_analysis()
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
            self.win.sp_marker_lane.setValue(2)
            self.win._auto_lanes(); self.win.run_analysis()
            self.assertEqual(self.win.marker_preset_combo.currentText(), 'Test ladder')
            self.win.marker_lane_combo.setCurrentIndex(1)
            with patch('bandwagon.lanes.MarkerDialog') as dialog:
                self.win.btn_marker_setup.click()
                dialog.assert_not_called()
            self.assertEqual(self.win.lanes[0].kind, 'sample')
            self.assertEqual(self.win.lanes[1].marker_mw, [100, 50, 25])
            self.assertEqual(self.win._active_tool, 'marker')
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
            self.win._auto_lanes(); self.win.run_analysis()
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
            self.assertEqual(self.win._active_tool, 'marker')
            self.assertTrue(self.win.lanes[1].mw)

    def test_preset_mismatch_keeps_band_matching_confirmation_and_cancel(self):
        from bandwagon.dialogs import MarkerDialog
        presets = [{'name': 'Short ladder', 'mw': [100, 25]}]
        with patch('bandwagon.lanes.load_marker_presets', return_value=presets), \
                patch('bandwagon.dialogs.load_marker_presets', return_value=presets):
            self.win._auto_lanes(); self.win.run_analysis()
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
        self.win._auto_lanes(); self.win.run_analysis()
        self.win._select_ribbon_tool('marker')
        with patch('bandwagon.lanes.MarkerDialog') as dialog:
            dialog.return_value.exec_.return_value = 1
            dialog.return_value.values.return_value = [100, 0, 0]
            self.win.btn_marker_setup.click()
        self.assertEqual(self.win._active_tool, 'marker')
        self.assertEqual(self.win.mw_r2_label.text(), tr('mw_regression_placeholder'))
        self.assertTrue(all(not lane.mw for lane in self.win.lanes))

    def test_removing_marker_and_undo_recalculate_mw(self):
        self.win._auto_lanes(); self.win.run_analysis()
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
