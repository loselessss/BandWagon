import os
import unittest
import numpy as np
from unittest.mock import patch
from PIL import Image
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication
from bandwagon.app import Analyzer
from bandwagon.models import Lane


class MwReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_upper_edges_drive_both_calibration_and_samples(self):
        win = Analyzer()
        try:
            win._orig = Image.new('RGB', (120, 160), 'white'); win._after_load('upper.png')
            marker = Lane(0, 0, 50); marker.kind = 'marker'
            marker.marker_mw = [100, 50, 25]
            marker.peaks = np.array([30, 90, 145]); marker.peak_bounds = [(10, 40), (70, 100), (130, 150)]
            sample = Lane(1, 60, 110)
            sample.peaks = np.array([55, 110, 149]); sample.peak_bounds = [(10, 60), (70, 120), (130, 155)]
            win.lanes = [marker, sample]
            self.assertTrue(win._compute_mw())
            self.assertEqual(sample.mw, [100, 50, 25])
            before = list(sample.mw)
            sample.peaks = np.array([58, 118, 153])  # broader/lower maxima, same upper edges
            win.gel.band_display_style = 'line'
            self.assertTrue(win._compute_mw()); self.assertEqual(sample.mw, before)
            self.assertEqual(marker.mw, marker.marker_mw)
        finally:
            win._saved_snapshot = win._project_state_snapshot(); win.close()

    def test_missing_or_invalid_bounds_fall_back_to_peak(self):
        lane = Lane(0, 0, 10); lane.peaks = [20, 40, 60, 80]
        self.assertEqual(lane.mw_reference_y(0), 20)
        lane.peak_bounds = [(10, 30), (50, 70), (float('nan'), 70)]
        self.assertEqual([lane.mw_reference_y(i) for i in range(4)], [10, 40, 60, 80])

    def test_crop_apply_uses_manual_perspective_when_corner_tool_active(self):
        win = Analyzer()
        try:
            win._orig = Image.new('RGB', (120, 160), 'white'); win._after_load('quad.png')
            win._select_ribbon_tool('crop'); win._enter_manual_corner_mode()
            win.gel.corners = [(10, 20), (110, 30), (100, 140), (20, 130)]
            win._apply_crop_or_perspective()
            self.assertEqual(win._edit_ops[-1][0], 'warp')
            self.assertLess(win._orig.width, 120); self.assertLess(win._orig.height, 160)
            win._undo(); self.assertEqual(win._orig.size, (120, 160))
        finally:
            win._saved_snapshot = win._project_state_snapshot(); win.close()

    def test_options_and_clipboard_command_are_reachable(self):
        win = Analyzer()
        try:
            self.assertIn(win.marker_presets_action, win.options_menu.actions())
            self.assertIn(win.m_language.menuAction(), win.options_menu.actions())
            for item in win.m_info.actions():
                if not item.isSeparator() and item.menu() is not win.m_language:
                    self.assertIn(item, win.options_menu.actions())
            self.assertIn('copy', win.ribbon_strips[3].buttons)
            self.assertEqual(list(win.ribbon_strips[0].buttons)[2:5], ['rotate', 'crop', 'bow'])
            self.assertNotIn('flip', win.ribbon_tools); self.assertNotIn('shear', win.ribbon_tools)
        finally: win.close()

    def test_prepared_marker_mismatch_is_not_silently_mapped(self):
        win = Analyzer()
        try:
            win._orig = Image.new('RGB', (120, 160), 'white'); win._after_load('mismatch.png')
            preset = {'name': 'Four bands', 'mw': [100, 75, 50, 25]}
            win.marker_preset_combo.addItem(preset['name'], preset)
            win.marker_preset_combo.setCurrentIndex(win.marker_preset_combo.count() - 1)
            lane = Lane(0, 0, 50); lane.peaks = np.array([30, 70, 110])
            win.lanes = [lane]
            self.assertFalse(win._apply_prepared_marker())
            self.assertEqual(lane.kind, 'sample'); self.assertEqual(lane.marker_mw, [])
            self.assertTrue(win._prepared_marker_pending)
            lane.peaks = np.array([30, 50, 70, 110])
            self.assertTrue(win._apply_prepared_marker())
            self.assertEqual(lane.marker_mw, preset['mw'])
            self.assertFalse(win._prepared_marker_pending)
            lane.kind = 'sample'; lane.marker_mw = []  # explicit removal/undo
            self.assertFalse(win._apply_prepared_marker())
            self.assertEqual(lane.kind, 'sample')
            win.sp_marker_lane.setValue(3)
            win._update_marker_controls()
            self.assertEqual(win.marker_lane_combo.currentIndex(), -1)
            win._configure_marker_lane()
            self.assertEqual(lane.kind, 'sample')
            win.run_analysis()
            self.assertEqual(win.sp_marker_lane.value(), 3)
            self.assertEqual(win.lanes[0].kind, 'sample')
        finally:
            win._saved_snapshot = win._project_state_snapshot(); win.close()
