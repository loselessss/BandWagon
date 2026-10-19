import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PIL import Image
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QPushButton
from bandwagon.app import Analyzer
from bandwagon.i18n import tr


class WorkflowNavigationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = Analyzer()
        pixels = np.full((160, 160), 230, dtype=np.uint8)
        for x in (10, 90):
            for y in (30, 70, 110):
                pixels[y:y + 5, x:x + 50] = 25
        self.win._orig = Image.fromarray(pixels).convert('RGB')
        self.win._after_load('workflow.png')
        self.win.sp_lane_n.setValue(2)

    def tearDown(self):
        editor = getattr(self.win, '_inline_curve', None)
        if editor is not None: editor.cancel()
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close()
        self.app.processEvents()

    def choose_pending(self, label):
        clicked = []
        case = self
        class ChoiceBox:
            def __init__(self): self.buttons = []; self.clicked = None
            def addButton(self, text, role):
                button = QPushButton(text)
                button.clicked.connect(lambda: setattr(self, 'clicked', button))
                self.buttons.append(button)
                return button
            def setStandardButtons(self, buttons): pass
            def exec_(self):
                for button in self.buttons:
                    if button.text() == tr(label):
                        clicked.append(label); button.click(); return 0
                case.fail('Pending-edit choice was not offered')
            def clickedButton(self): return self.clicked
        # Native QMessageBoxes are unsupported by Qt's Windows offscreen plugin;
        # keep real button clicks and test the decision handling independently.
        self.enterContext(patch.object(self.win, '_box', return_value=ChoiceBox()))
        return clicked

    def test_four_steps_connect_detection_marker_results_and_copy(self):
        self.assertEqual(self.win.ribbon.currentIndex(), 0)
        self.win.workflow_next.click()
        self.assertEqual(self.win.ribbon.currentIndex(), 1)
        self.assertEqual(self.win.gel.mode, 'lane')
        self.assertFalse(self.win.workflow_next.isEnabled())
        self.win._auto_lanes()
        self.assertTrue(self.win.workflow_next.isEnabled())
        self.win.sp_prom.setValue(85)
        self.assertFalse(self.win.workflow_next.isEnabled())
        self.assertEqual(self.win.workflow_hint.text(), tr('workflow_stale_hint'))
        self.win.btn_detect_bands.click()
        self.assertTrue(self.win.workflow_next.isEnabled())
        self.win.workflow_next.click()
        self.assertEqual(self.win.ribbon.currentIndex(), 2)
        self.assertFalse(self.win.workflow_next.isEnabled())
        presets = [{'name': 'Workflow ladder', 'mw': [100, 50, 25]}]
        with patch('bandwagon.lanes.load_marker_presets', return_value=presets):
            self.win._update_marker_presets()
        self.win.marker_preset_combo.setCurrentIndex(1)
        self.win.gel.laneSelected.emit(self.win.lanes[1])
        self.assertEqual(self.win.marker_lane_combo.currentIndex(), 1)
        with patch('bandwagon.lanes.MarkerDialog') as dialog:
            self.win.btn_marker_setup.click()
            dialog.assert_not_called()
        self.assertEqual(self.win.ribbon.currentIndex(), 3)
        self.assertEqual(self.win.result_table.rowCount(), 6)
        self.assertEqual(self.win.lanes[1].marker_mw, [100, 50, 25])
        with patch.object(self.win, 'copy_image') as copy:
            self.win.workflow_next.click()
            copy.assert_called_once()

    def test_free_navigation_keeps_analysis_selection_and_settings(self):
        self.win._auto_lanes()
        self.win._select_ribbon_tool('manual_lanes')
        lane = self.win.lanes[1]
        self.win.gel.selected_lane = lane
        before = [item.to_dict() for item in self.win.lanes]
        self.win.band_settings_toggle.setChecked(True)
        for stage in (2, 3, 0, 1):
            self.win.ribbon.setCurrentIndex(stage)
            self.assertIs(self.win.gel.selected_lane, lane)
            if stage == 2: self.assertEqual(self.win.marker_lane_combo.currentIndex(), 1)
        self.assertTrue(self.win.band_settings_toggle.isChecked())
        self.assertEqual([item.to_dict() for item in self.win.lanes], before)
        self.assertIn(lane.name, self.win.selected_lane_summary.text())

    def test_selecting_lane_edge_without_drag_does_not_invalidate_analysis(self):
        self.win._auto_lanes()
        self.win._select_ribbon_tool('manual_lanes'); self.win.show(); self.app.processEvents()
        lane = self.win.lanes[0]
        point = QPoint(round(self.win.gel._ix_to_wx(lane.x2)), round(self.win.gel._rect.center().y()))
        before = self.win.result_table.rowCount()
        QTest.mouseClick(self.win.gel, Qt.LeftButton, pos=point)
        self.assertIs(self.win.gel.selected_lane, lane)
        self.assertFalse(self.win._analysis_stale)
        self.assertEqual(self.win.result_table.rowCount(), before)
        self.assertTrue(self.win.workflow_next.isEnabled())

    def test_empty_stages_are_accessible_but_cannot_advance(self):
        empty = Analyzer()
        try:
            for stage in range(4):
                empty.ribbon.setCurrentIndex(stage)
                self.assertEqual(empty.ribbon.currentIndex(), stage)
                self.assertFalse(empty.workflow_next.isEnabled())
                self.assertEqual(empty.workflow_hint.text(), tr('workflow_empty_hint'))
        finally: empty.close()

    def test_cancel_step_change_keeps_unapplied_crop_and_navigation(self):
        self.win._select_ribbon_tool('crop')
        self.win.gel.crop_rect = (10, 20, 140, 150)
        self.win.gel._crop_fresh = False
        clicked = self.choose_pending('btn_cancel')
        self.win.ribbon.setCurrentIndex(1)
        self.assertTrue(clicked)
        self.assertEqual(self.win.ribbon.currentIndex(), 0)
        self.assertEqual(self.win._active_tool, 'crop')
        self.assertEqual(self.win.gel.crop_rect, (10, 20, 140, 150))
        self.assertEqual(self.win._orig.size, (160, 160))
        self.assertEqual(self.win.workflow_next.text(), tr('workflow_to_lanes'))

    def test_reclicking_active_crop_or_curve_keeps_unapplied_edit(self):
        self.win._select_ribbon_tool('crop')
        rect = (10, 20, 140, 150)
        self.win.gel.crop_rect = rect; self.win.gel._crop_fresh = False
        self.win.ribbon_strips[0].buttons['crop'].click()
        self.assertEqual(self.win.gel.crop_rect, rect)
        self.win._cancel_crop()
        self.win._select_ribbon_tool('bow'); self.win._reference_bow()
        editor = self.win._inline_curve
        editor.points[2] = (80, 50)
        self.win.ribbon_strips[0].buttons['bow'].click()
        self.assertIs(self.win._inline_curve, editor)
        self.assertFalse(self.win._edit_ops)

    def test_clicking_current_stage_leaves_notes_without_losing_them(self):
        self.win.memo_action.trigger()
        self.win.memo_edit.setPlainText('Workflow notes')
        self.assertEqual(self.win._active_tool, 'memo')
        self.win.ribbon.tabBarClicked.emit(0)
        self.assertEqual(self.win._active_tool, 'rotate')
        self.win.memo_action.trigger()
        self.assertEqual(self.win.memo_edit.toPlainText(), 'Workflow notes')

    def test_apply_crop_before_step_change_is_undoable(self):
        self.win._select_ribbon_tool('crop')
        self.win.gel.crop_rect = (10, 20, 140, 150)
        self.win.gel._crop_fresh = False
        clicked = self.choose_pending('workflow_apply_continue')
        self.win.ribbon.setCurrentIndex(1)
        self.assertTrue(clicked)
        self.assertEqual(self.win.ribbon.currentIndex(), 1)
        self.assertEqual(self.win._orig.size, (130, 130))
        self.win._undo()
        self.assertEqual(self.win._orig.size, (160, 160))

    def test_discard_curve_before_step_change_does_not_change_pixels(self):
        before = self.win._orig.tobytes()
        self.win._select_ribbon_tool('bow')
        self.win._reference_bow()
        self.win._inline_curve.points[2] = (80, 50)
        self.win._inline_curve.preview()
        clicked = self.choose_pending('workflow_discard_continue')
        self.win.ribbon.setCurrentIndex(1)
        self.assertTrue(clicked)
        self.assertIsNone(self.win._inline_curve)
        self.assertEqual(self.win._orig.tobytes(), before)
        self.assertFalse(self.win._edit_ops)

    def test_marker_panel_fits_long_preset_and_lane_names_at_minimum_size(self):
        self.win._auto_lanes()
        self.win.lanes[0].name = 'Very long sample name ' * 8
        presets = [{'name': 'Very long manufacturer and marker preset ' * 8, 'mw': [100, 50, 25]}]
        with patch('bandwagon.lanes.load_marker_presets', return_value=presets):
            self.win._select_ribbon_tool('marker')
        self.win.resize(900, 620); self.win.show(); self.app.processEvents()
        self.assertEqual(self.win.lane_settings_scroll.horizontalScrollBar().maximum(), 0)
        self.assertTrue(self.win.workflow_next.isVisible())
        for combo in (self.win.marker_preset_combo, self.win.marker_lane_combo):
            self.assertLessEqual(combo.width(), self.win.lane_settings_scroll.viewport().width())


if __name__ == '__main__':
    unittest.main()
