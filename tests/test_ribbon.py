import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication, QAbstractButton
from PyQt5.QtCore import QPoint
from PyQt5.QtGui import QFont
from bandwagon.composite import CompositeStudio
from bandwagon.imaging import pil_to_pixmap
from bandwagon.ribbon import ToolStrip
from bandwagon.app import Analyzer
from bandwagon.models import Lane
from bandwagon.i18n import tr


class RibbonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_analysis_order_and_notes_belong_to_file_ribbon(self):
        win = Analyzer()
        try:
            self.assertEqual(list(win.ribbon_strips[2].buttons)[-5:], ['run', 'marker', 'results', 'quant', 'marker_presets'])
            self.assertNotIn(tr('tab_analysis'), [win.ribbon.tabText(i) for i in range(win.ribbon.count())])
            self.assertEqual(win.ribbon_tools['results'][0], 2)
            self.assertEqual(win.ribbon_tools['quant'][0], 2)
            self.assertIn('memo', win.ribbon_strips[0].buttons)
            self.assertEqual(win.ribbon_tools['memo'][0], 0)
            self.assertFalse(win.ribbon_strips[0].buttons['memo'].icon().isNull())
            win.ribbon_strips[0].buttons['memo'].click()
            self.assertEqual(win.ribbon.currentIndex(), 0)
            self.assertEqual(win._active_tool, 'memo')
            self.assertEqual(win.tabs.currentIndex(), 4)
            self.assertTrue(win.memo_edit.isVisibleTo(win.tabs))
            win.memo_edit.setPlainText('Keep this note')
            win.ribbon_strips[2].buttons['results'].click()
            self.assertEqual(win._active_tool, 'results')
            win.ribbon_strips[2].buttons['quant'].click()
            self.assertEqual(win._active_tool, 'quant')
            win.ribbon.setCurrentIndex(0)
            self.assertEqual(win._active_tool, 'memo')
            self.assertEqual(win.memo_edit.toPlainText(), 'Keep this note')
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_overflow_arrows_reveal_remaining_commands(self):
        strip = ToolStrip([(str(i), 'tool_rotate', 'rotate', lambda: None, True)
                           for i in range(12)])
        try:
            strip.resize(300, 80); strip.show(); self.app.processEvents()
            bar = strip.scroll.horizontalScrollBar()
            self.assertGreater(bar.maximum(), 0)
            self.assertTrue(strip.right.isVisible())
            strip.right.click()
            self.assertGreater(bar.value(), 0)
            strip.select('11')
            self.assertTrue(strip.buttons['11'].isChecked())
            self.assertGreater(bar.value(), bar.maximum() // 2)
        finally:
            strip.close()

    def test_lane_and_result_panels_route_within_the_same_ribbon(self):
        win = Analyzer()
        try:
            win._select_ribbon_tool('lane_list')
            win._select_ribbon_tool('results')
            self.assertEqual(win.ribbon.currentIndex(), 2)
            win.tabs.setCurrentIndex(1)
            self.assertEqual(win._active_tool, 'lane_list')
            self.assertEqual(win.tabs.currentIndex(), 1)
            win.tabs.setCurrentIndex(2)
            self.assertEqual(win._active_tool, 'results')
            win.ribbon_strips[2].buttons['quant'].click()
            self.assertEqual(win.tabs.currentIndex(), 3)
            win.ribbon.setCurrentIndex(1)
            win.ribbon.setCurrentIndex(2)
            self.assertEqual(win._active_tool, 'quant')
            self.assertEqual(win.ribbon.currentIndex(), 2)
            self.assertIn('make', win.ribbon_strips[3].buttons)
            self.assertIn('undo', win.ribbon_strips[4].buttons)
        finally:
            win.close()

    def test_marker_presets_have_one_ribbon_action_and_keep_selected_tool(self):
        win = Analyzer()
        try:
            win._select_ribbon_tool('lane_list')
            button = win.ribbon_strips[2].buttons['marker_presets']
            self.assertFalse(button.isCheckable())
            self.assertFalse(button.icon().isNull())
            self.assertEqual(button.toolTip(), tr('marker_preset_btn_tip'))
            self.assertEqual(sum(item.text() == tr('tool_marker_presets')
                                 for item in win.findChildren(QAbstractButton)), 1)
            self.assertFalse(any(item.text() == tr('btn_manage_marker_presets')
                                 for item in win.findChildren(QAbstractButton)))
            with patch('bandwagon.lanes.load_marker_presets', return_value={}), \
                    patch('bandwagon.lanes.MarkerPresetManager') as dialog, \
                    patch('bandwagon.lanes.save_marker_presets') as save:
                dialog.return_value.exec_.return_value = 0
                button.click()
                dialog.assert_called_once_with({}, win)
                save.assert_not_called()
            self.assertEqual(win._active_tool, 'lane_list')
            self.assertTrue(win.ribbon_strips[2].buttons['lane_list'].isChecked())
        finally:
            win.close()

    def test_marker_presets_ribbon_saves_accepted_changes_without_image(self):
        win = Analyzer()
        try:
            presets = {'Example': [100, 50, 25]}
            with patch('bandwagon.lanes.load_marker_presets', return_value={}), \
                    patch('bandwagon.lanes.MarkerPresetManager') as dialog, \
                    patch('bandwagon.lanes.save_marker_presets') as save:
                dialog.return_value.exec_.return_value = 1
                dialog.return_value.presets = presets
                win.ribbon_strips[2].buttons['marker_presets'].click()
                save.assert_called_once_with(presets)
            self.assertIsNone(win._orig)
            self.assertEqual(win.status.currentMessage(), tr('status_presets_saved', n=1))
        finally:
            win.close()

    def test_every_ribbon_category_and_file_command_has_an_icon(self):
        win = Analyzer()
        try:
            win.show(); self.app.processEvents()
            self.assertEqual(win.ribbon.count(), 5)
            for index in range(win.ribbon.count()):
                with self.subTest(category=win.ribbon.tabText(index)):
                    self.assertFalse(win.ribbon.tabIcon(index).isNull())
            win.ribbon.setCurrentIndex(0); self.app.processEvents()
            for name, button in win.ribbon_strips[0].buttons.items():
                with self.subTest(command=name):
                    self.assertFalse(button.icon().isNull())
        finally:
            win.close()

    def test_lane_table_follows_tool_settings_without_large_blank_space(self):
        win = Analyzer()
        try:
            win.show()
            for size in ((1050, 850), (900, 620)):
                win.resize(*size)
                for tool in ('manual_lanes', 'lane_list'):
                    with self.subTest(size=size, tool=tool):
                        win._select_ribbon_tool(tool)
                        self.app.processEvents()
                        group = win.lane_tools[tool]
                        panel = win.lane_table.parentWidget()
                        bottom = group.mapTo(panel, QPoint(0, group.height())).y()
                        self.assertLessEqual(win.lane_table.y() - bottom, 40)
                        self.assertGreater(win.lane_table.height(), 150)
        finally:
            win.close()

    def test_lane_settings_remain_compact_without_footer_actions(self):
        win = Analyzer()
        try:
            win.show()
            for size in ((1050, 850), (900, 620)):
                win.resize(*size)
                for tool in ('auto_lanes', 'range', 'bands'):
                    with self.subTest(size=size, tool=tool):
                        win._select_ribbon_tool(tool)
                        self.app.processEvents()
                        scroll = win.lane_settings_scroll
                        self.assertLessEqual(scroll.height(), scroll.sizeHint().height() + 2)
                        self.assertFalse(win.lane_table.isVisible())
        finally:
            win.close()

    def test_detection_action_exists_only_once_and_keeps_preview(self):
        win = Analyzer()
        try:
            image = np.full((180, 120, 3), 255, dtype=np.uint8)
            image[40:46] = 20; image[100:106] = 20
            win._orig = Image.fromarray(image); win._after_load('ribbon-analysis.png')
            win.lanes = [Lane(0, 10, 50), Lane(1, 60, 100)]
            win._rebuild_lane_table(); win._select_ribbon_tool('memo'); win.show()
            self.app.processEvents()
            actions = [button for button in win.findChildren(QAbstractButton)
                       if button.text() == tr('btn_run_analysis')]
            self.assertEqual(len(actions), 1)
            self.assertIs(actions[0], win.ribbon_strips[2].buttons['run'])
            actions[0].click(); self.app.processEvents()
            self.assertEqual(win._active_tool, 'bands')
            self.assertEqual(win.ribbon.currentIndex(), 2)
            self.assertFalse(win.result_table.isVisible())
            self.assertTrue(win.gel.isVisible())
            self.assertEqual(win.result_table.rowCount(), 4)
            self.assertEqual(win.analysis_notice.text(), tr('analysis_ready', n=4))
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_analysis_without_input_does_not_switch_to_results(self):
        win = Analyzer()
        try:
            win._select_ribbon_tool('memo')
            with patch.object(win, '_info') as info:
                win.ribbon_strips[2].buttons['run'].click()
            info.assert_called_once()
            self.assertEqual(win._active_tool, 'memo')
            win._orig = Image.new('RGB', (100, 100), 'white')
            win._after_load('empty.png')
            with patch.object(win, '_info') as info:
                win.ribbon_strips[2].buttons['run'].click()
            info.assert_called_once()
            self.assertEqual(win._active_tool, 'memo')
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_zero_detected_bands_still_show_completed_result(self):
        win = Analyzer()
        try:
            win._orig = Image.new('RGB', (100, 100), 'white'); win._after_load('empty-bands.png')
            win.lanes = [Lane(0, 10, 50)]; win._rebuild_lane_table()
            win._select_ribbon_tool('memo')
            win.ribbon_strips[2].buttons['run'].click()
            self.assertEqual(win._active_tool, 'bands')
            self.assertEqual(win.result_table.rowCount(), 0)
            self.assertEqual(win.analysis_notice.text(), tr('analysis_no_bands'))
            win.sp_prom.setValue(80)
            self.assertEqual(win.analysis_notice.text(), tr('analysis_stale'))
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_empty_profile_is_compact_but_real_graph_retains_its_height(self):
        win = Analyzer()
        try:
            self.assertEqual(win.profile.height(), 64)
            lane = Lane(0, 10, 40)
            lane.profile = np.arange(100, dtype=float)
            win.profile.set_lanes([lane])
            self.assertEqual(win.profile.height(), 150)
            win.profile.set_lanes([])
            self.assertEqual(win.profile.height(), 64)
        finally:
            win.close()

    def test_lane_rows_fit_controls_and_larger_name_font(self):
        win = Analyzer()
        try:
            font = QFont(win.lane_table.font()); font.setPointSize(18)
            win.lane_table.setFont(font)
            win.lanes = [Lane(0, 10, 40), Lane(1, 50, 80)]
            win.lanes[0].name = 'Long lane name / 긴 레인 이름'
            win._rebuild_lane_table()
            win._select_ribbon_tool('lane_list'); win.show(); self.app.processEvents()
            for row in range(2):
                combo = win.lane_table.cellWidget(row, 1)
                self.assertGreaterEqual(combo.height(), combo.sizeHint().height())
                self.assertGreaterEqual(win.lane_table.rowHeight(row),
                                        win.lane_table.fontMetrics().height() + 12)
            self.assertEqual(win.lane_table.item(0, 0).toolTip(), win.lanes[0].name)
        finally:
            win._saved_snapshot = win._project_state_snapshot()
            win.close()

    def test_studio_ribbon_preserves_corners_and_matches_export_blend(self):
        errors = self.enterContext(patch('sys.excepthook'))
        studio = CompositeStudio()
        try:
            studio.show(); self.app.processEvents()
            studio._visible_img = Image.new('RGB', (100, 80), (160, 170, 180))
            studio._uv_img = Image.new('RGB', (100, 80), (60, 90, 120))
            corners = [(0, 0), (99, 0), (99, 79), (0, 79)]
            studio.gel.corners = corners[:]
            for name in ('align', 'blend', 'export', 'photos'):
                studio.ribbon.buttons[name].click()
                self.app.processEvents()
                self.assertEqual(studio.gel.corners, corners)
                self.assertEqual(studio.gel.mode, 'corner' if name == 'align' else 'view')
                self.assertEqual([key for key, widgets in studio.tool_widgets.items()
                                  if any(widget.isVisibleTo(studio) for widget in widgets)], [name])
            studio._show_studio_tool('blend')
            for bright in (True, False):
                studio.bright_bands.setChecked(bright)
                for opacity in (0, 60, 100):
                    studio.opacity_slider.setValue(opacity); studio._refresh_canvas()
                    blend, gray = studio._compute_full_res()
                    self.assertEqual(studio.gel._pm.toImage(), pil_to_pixmap(blend).toImage())
                    self.assertEqual(gray.shape, (80, 100))
            errors.assert_not_called()
        finally:
            studio.close()


if __name__ == '__main__':
    unittest.main()
