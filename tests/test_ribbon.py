import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QPoint
from bandwagon.composite import CompositeStudio
from bandwagon.imaging import pil_to_pixmap
from bandwagon.ribbon import ToolStrip
from bandwagon.app import Analyzer
from bandwagon.models import Lane


class RibbonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

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

    def test_every_ribbon_category_and_file_command_has_an_icon(self):
        win = Analyzer()
        try:
            win.show(); self.app.processEvents()
            self.assertEqual(win.ribbon.count(), 6)
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

    def test_lane_actions_follow_settings_without_large_blank_space(self):
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
                        gap = win.btn_run_analysis.y() - scroll.y() - scroll.height()
                        self.assertLessEqual(gap, 12)
                        self.assertFalse(win.lane_table.isVisible())
                        self.assertTrue(win.btn_run_analysis.isVisible())
        finally:
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
