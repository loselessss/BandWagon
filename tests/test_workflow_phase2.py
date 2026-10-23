import csv
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication, QPushButton

from bandwagon.app import Analyzer
from bandwagon.export_dialog import DEFAULT_OPTIONS, render_export
from bandwagon.i18n import tr
from bandwagon.models import Lane


class WorkflowPhase2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = Analyzer()
        self.enterContext(patch.object(self.win, '_warn', side_effect=lambda title, message: self.fail(f'{title}: {message}')))
        pixels = np.full((160, 240), 230, dtype=np.uint8)
        for index, x in enumerate((10, 90, 170)):
            for y in (30, 70, 110):
                pixels[y:y + 5, x:x + 50] = 25 + index * 40
        self.win._orig = Image.fromarray(pixels).convert('RGB')
        self.win._after_load('phase2.png')
        self.win.lanes = [Lane(i, x, x + 49) for i, x in enumerate((10, 90, 170))]
        self.win._commit_lanes()
        self.assertTrue(self.win.run_analysis())

    def tearDown(self):
        self.win._cancel_crop(); self.win._clear_corners()
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close(); self.win.deleteLater(); self.app.processEvents()

    def pending_choice(self, key):
        class ChoiceBox:
            def __init__(self): self.buttons = []; self.selected = None
            def addButton(self, text, role):
                button = QPushButton(text); self.buttons.append(button); return button
            def setStandardButtons(self, buttons): pass
            def exec_(self):
                self.selected = next(button for button in self.buttons if button.text() == tr(key))
            def clickedButton(self): return self.selected
        return patch.object(self.win, '_box', return_value=ChoiceBox())

    def assign_bsa(self, index, amount):
        self.win.quant_lane_combo.setCurrentIndex(index)
        self.win.quant_amount.setValue(amount)
        self.win.quant_apply.click()

    def test_quant_assign_remove_undo_and_redo_recalculate_without_detection(self):
        self.win._select_ribbon_tool('quant')
        volumes = [lane.peak_volume.copy() for lane in self.win.lanes]
        with patch.object(self.win, 'run_analysis') as detect:
            self.assign_bsa(0, 2)
            self.assign_bsa(1, 1)
            self.assertIsNotNone(self.win.std_view._xy)
            self.assertIn(self.win.lanes[2].name, self.win.std_label.text())
            self.win.quant_remove.click()
            self.assertIsNone(self.win.std_view._xy)
            self.win._undo()
            self.assertEqual(self.win.lanes[1].kind, 'bsa')
            self.assertIsNotNone(self.win.std_view._xy)
            self.win._redo()
            self.assertEqual(self.win.lanes[1].kind, 'sample')
            self.assertIsNone(self.win.std_view._xy)
            detect.assert_not_called()
        for lane, expected in zip(self.win.lanes, volumes):
            np.testing.assert_array_equal(lane.peak_volume, expected)

    def test_quant_selection_tracks_preview_and_protects_marker(self):
        self.win.lanes[0].kind = 'marker'; self.win.lanes[0].marker_mw = [100, 50, 25]
        self.win._commit_lanes()
        self.win._select_ribbon_tool('quant')
        self.win._on_gel_lane_selected(self.win.lanes[2])
        self.assertEqual(self.win.quant_lane_combo.currentIndex(), 2)
        self.win.quant_lane_combo.setCurrentIndex(0)
        self.assertIs(self.win.gel.selected_lane, self.win.lanes[0])
        self.assertFalse(self.win.quant_apply.isEnabled())
        self.assertFalse(self.win.quant_remove.isEnabled())
        self.win._set_quant_standard(True)
        self.assertEqual(self.win.lanes[0].kind, 'marker')
        self.assertEqual(self.win.lanes[0].marker_mw, [100, 50, 25])
        self.win.workflow_next.click()
        self.assertEqual(self.win._active_tool, 'results')

    def test_identical_standard_volumes_or_amounts_do_not_raise_or_keep_old_fit(self):
        self.assign_bsa(0, 2); self.assign_bsa(1, 1)
        self.assertIsNotNone(self.win.std_view._xy)
        self.win.lanes[1].peak_volume = self.win.lanes[0].peak_volume.copy()
        self.win._compute_std()
        self.assertIsNone(self.win.std_view._xy)
        self.assertEqual(self.win.std_label.text(), tr('quant_invalid_standards'))
        self.win.lanes[1].peak_volume *= .5
        self.win.lanes[1].bsa_amount = 2
        self.win._compute_std()
        self.assertIsNone(self.win.std_view._xy)

    def test_zero_amount_blank_standard_remains_supported(self):
        self.assign_bsa(0, 1); self.assign_bsa(1, 0)
        self.assertEqual(self.win.lanes[1].bsa_amount, 0)
        self.assertIsNotNone(self.win.std_view._xy)
        self.win._on_gel_lane_selected(self.win.lanes[1])
        self.assertEqual(self.win.quant_amount.value(), 0)

    def test_stale_results_clear_quant_and_block_all_output_paths(self):
        self.assign_bsa(0, 2); self.assign_bsa(1, 1)
        self.win.sp_prom.setValue(80)
        self.assertTrue(self.win._analysis_stale)
        self.assertIsNone(self.win.std_view._xy)
        with patch.object(self.win, '_export_options') as options, \
                patch('bandwagon.fileio.QFileDialog.getSaveFileName') as destination, \
                patch('bandwagon.fileio.copy_pil_image_to_clipboard') as clipboard:
            for output in (self.win.copy_image, self.win.save_image, self.win.export_csv):
                output()
                self.assertEqual(self.win._active_tool, 'manual_lanes')
            options.assert_not_called(); destination.assert_not_called(); clipboard.assert_not_called()

    def test_save_and_copy_cancel_keep_pending_crop(self):
        self.win._select_ribbon_tool('crop')
        rect = (20, 20, 210, 140)
        self.win.gel.crop_rect = rect; self.win.gel._crop_fresh = False
        with self.pending_choice('btn_cancel'), \
                patch.object(self.win, '_export_options') as options, \
                patch.object(self.win, '_write_project_file') as write:
            self.win._current_project_path = 'unused.bandwagon'
            self.win.copy_image(); self.win.save_project()
            options.assert_not_called(); write.assert_not_called()
        self.assertEqual(self.win.gel.crop_rect, rect)
        self.assertEqual(self.win._orig.size, (240, 160))

    def test_partial_perspective_selection_cannot_be_applied_on_output(self):
        self.win._select_ribbon_tool('crop'); self.win._enter_manual_corner_mode()
        self.win.gel.corners = [(10., 10.), (220., 10.)]
        with self.pending_choice('workflow_apply_continue'):
            self.assertFalse(self.win._prepare_output())
        self.assertEqual(self.win._active_tool, 'crop')
        self.assertEqual(len(self.win.gel.corners), 2)
        with self.pending_choice('workflow_discard_continue'):
            self.assertTrue(self.win._prepare_output())
        self.assertFalse(self.win.gel.corners)

    def test_project_resumes_quant_selection_and_preserves_values_and_export_pixels(self):
        self.win.lanes[2].kind = 'marker'; self.win.lanes[2].marker_mw = [100, 50, 25]
        self.win._commit_lanes()
        self.win._select_ribbon_tool('quant')
        self.assign_bsa(0, 2); self.assign_bsa(1, 1)
        expected = [[lane.peaks.tolist(), lane.peak_volume.tolist(), lane.mw] for lane in self.win.lanes]
        rendered = render_export(self.win._display, self.win.lanes, DEFAULT_OPTIONS).tobytes()
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'resume.bandwagon')
            self.assertTrue(self.win._write_project_file(path))
            self.assertTrue(self.win.open_project(path))
        self.assertEqual(self.win._active_tool, 'quant')
        self.assertEqual(self.win.quant_lane_combo.currentIndex(), 1)
        self.assertIs(self.win.gel.selected_lane, self.win.lanes[1])
        self.assertIsNotNone(self.win.std_view._xy)
        self.assertEqual([[lane.peaks.tolist(), lane.peak_volume.tolist(), lane.mw] for lane in self.win.lanes], expected)
        self.assertEqual(render_export(self.win._display, self.win.lanes, DEFAULT_OPTIONS).tobytes(), rendered)
        self.assertEqual(self.win._project_state_snapshot(), self.win._saved_snapshot)

    def test_stale_project_resumes_at_detection_without_silent_reanalysis(self):
        self.win._select_ribbon_tool('results'); self.win.sp_dist.setValue(8)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'stale.bandwagon')
            self.assertTrue(self.win._write_project_file(path))
            with patch.object(self.win, 'run_analysis') as detect:
                self.assertTrue(self.win.open_project(path))
                detect.assert_not_called()
        self.assertTrue(self.win._analysis_stale)
        self.assertEqual(self.win._active_tool, 'manual_lanes')
        self.assertFalse(self.win.workflow_next.isEnabled())

    def test_prepared_marker_preset_survives_project_on_another_computer(self):
        preset = {'name': 'Project-only marker', 'mw': [100, 50, 25]}
        self.win._select_ribbon_tool('marker')
        self.win.marker_preset_combo.addItem(preset['name'], preset)
        self.win.marker_preset_combo.setCurrentIndex(self.win.marker_preset_combo.count() - 1)
        self.win.sp_marker_lane.setValue(2)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'prepared.bandwagon')
            self.assertTrue(self.win._write_project_file(path))
            with patch('bandwagon.lanes.load_marker_presets', return_value=[]):
                self.win._update_marker_presets()
                self.assertTrue(self.win.open_project(path))
        self.assertEqual(self.win._active_tool, 'marker')
        self.assertEqual(self.win.marker_preset_combo.currentData(), preset)
        self.assertTrue(self.win._prepared_marker_pending)
        self.assertEqual(self.win.sp_marker_lane.value(), 2)
        self.assertTrue(self.win.run_analysis())
        self.assertEqual(self.win.lanes[1].marker_mw, preset['mw'])

    def test_only_marker_preparation_not_navigation_marks_project_dirty(self):
        before = self.win._project_state_snapshot()
        self.win._select_ribbon_tool('quant')
        self.win._on_gel_lane_selected(self.win.lanes[2])
        self.assertEqual(self.win._project_state_snapshot(), before)
        preset = {'name': 'Prepared marker', 'mw': [100, 50, 25]}
        self.win.marker_preset_combo.addItem(preset['name'], preset)
        self.win.marker_preset_combo.setCurrentIndex(self.win.marker_preset_combo.count() - 1)
        self.assertNotEqual(self.win._project_state_snapshot(), before)

    def test_legacy_project_chooses_results_and_malformed_workflow_is_ignored(self):
        for workflow in (None, {'tool': ['invalid'], 'selected_lane': 'bad', 'marker_number': 'bad'}):
            with self.subTest(workflow=workflow), tempfile.TemporaryDirectory() as folder:
                path = str(Path(folder) / 'legacy.bandwagon')
                metadata = self.win._capture_project_metadata()
                metadata.pop('workflow', None)
                if workflow is not None: metadata['workflow'] = workflow
                image = io.BytesIO(); self.win._orig.save(image, 'PNG')
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('project.json', json.dumps(metadata))
                    archive.writestr('image.png', image.getvalue())
                self.assertTrue(self.win.open_project(path))
                self.assertEqual(self.win._active_tool, 'results')

    def test_csv_cancel_and_image_cancel_do_not_modify_analysis(self):
        expected = self.win._project_state_snapshot()
        with patch.object(self.win, '_export_options', return_value=None), \
                patch('bandwagon.fileio.QFileDialog.getSaveFileName', return_value=('', '')):
            self.win.copy_image(); self.win.save_image(); self.win.export_csv()
        self.assertEqual(self.win._project_state_snapshot(), expected)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'results.csv')
            with patch('bandwagon.fileio.QFileDialog.getSaveFileName', return_value=(path, 'CSV')):
                self.win.export_csv()
            with open(path, encoding='utf-8-sig', newline='') as source:
                rows = list(csv.reader(source))
            self.assertEqual(len(rows), 10)
            self.assertEqual(rows[1][0], self.win.lanes[0].name)
            self.assertEqual(float(rows[1][-1]), round(self.win.lanes[0].peak_volume[0], 1))

    def test_western_entry_uses_same_actions_and_import_keeps_occupied_window(self):
        self.assertIs(self.win.ribbon_strips[0].buttons['western'].menu(), self.win.m_western)
        with patch('bandwagon.fileio.QFileDialog.getOpenFileName', return_value=('test.bwcomposite', '')), \
                patch.object(self.win, '_open_path_here_or_new_window') as open_file:
            self.win.import_composite()
            open_file.assert_called_once_with('test.bwcomposite')
        with patch.object(self.win, '_add_recent_file'), patch.object(self.win, 'import_composite') as load, \
                patch.object(self.win, '_show_composite_studio_window') as studio:
            self.win.open_path_smart('test.bwcomposite')
            load.assert_called_once_with('test.bwcomposite'); studio.assert_not_called()

    def test_copy_and_saved_image_use_identical_rendering(self):
        captured = []
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'export.png')
            with patch.object(self.win, '_export_options', return_value=dict(DEFAULT_OPTIONS)), \
                    patch('bandwagon.fileio.copy_pil_image_to_clipboard', side_effect=lambda image, cb: captured.append(image.copy())), \
                    patch('bandwagon.fileio.QFileDialog.getSaveFileName', return_value=(path, 'PNG')):
                self.win.copy_image(); self.win.save_image()
            with Image.open(path) as saved:
                self.assertEqual(saved.size, captured[0].size)
                self.assertEqual(saved.tobytes(), captured[0].tobytes())

    def test_western_import_really_opens_new_window_and_keeps_uv_signal(self):
        from bandwagon.composite import export_composite
        before = self.win._project_state_snapshot()
        previous = set(Analyzer._open_windows)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'new.bwcomposite')
            gray = np.full((80, 90), 123, dtype=np.uint8)
            export_composite(path, Image.new('RGB', (90, 80), 'blue'), gray)
            try:
                with patch('bandwagon.fileio.QFileDialog.getOpenFileName', return_value=(path, '')), \
                        patch('bandwagon.fileio._save_recent_files'):
                    self.win.import_composite()
                opened = [win for win in Analyzer._open_windows if win not in previous]
                self.assertEqual(len(opened), 1)
                np.testing.assert_array_equal(opened[0]._gray_orig, gray)
                self.assertEqual(opened[0]._active_tool, 'rotate')
                self.assertEqual(self.win._project_state_snapshot(), before)
            finally:
                for win in list(Analyzer._open_windows):
                    if win not in previous:
                        win._saved_snapshot = win._project_state_snapshot(); win.close()


if __name__ == '__main__':
    unittest.main()
