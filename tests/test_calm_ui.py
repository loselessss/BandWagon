import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PIL import Image
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.models import Lane
from bandwagon.export_dialog import DEFAULT_OPTIONS, render_export


class CalmUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        settings_path = str(Path(self.temp.name) / 'layout.ini')
        self.enterContext(patch('bandwagon.app.QSettings',
                                side_effect=lambda *args: QSettings(settings_path, QSettings.IniFormat)))
        self.win = Analyzer()
        self.source = Image.new('RGB', (160, 120), (138, 150, 160))
        self.win._orig = self.source.copy()
        self.win._after_load('focus.png')
        self.win.lanes = [Lane(0, 10, 60), Lane(1, 90, 140)]
        self.win.gel.set_lanes(self.win.lanes)
        self.win._select_ribbon_tool('manual_lanes')
        self.win.resize(1000, 700)
        self.win.show()
        self.app.processEvents()

    def tearDown(self):
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close()
        self.app.processEvents()
        self.temp.cleanup()

    def test_profile_collapse_gives_image_more_space_and_survives_tool_switch(self):
        self.assertTrue(self.win.profile_section.isVisible())
        self.assertFalse(self.win.profile.isVisible())
        height = self.win.gel.height()
        self.win.profile_toggle.click()
        self.app.processEvents()
        self.assertTrue(self.win.profile.isVisible())
        self.assertLess(self.win.gel.height(), height)
        self.win._select_ribbon_tool('bow')
        self.assertFalse(self.win.profile_section.isVisible())
        self.win._select_ribbon_tool('manual_lanes')
        self.assertTrue(self.win.profile.isVisible())
        self.assertTrue(self.win._layout_settings.value('view/profile_expanded', type=bool))

    def test_optional_settings_expand_without_running_detection_or_losing_values(self):
        self.assertTrue(self.win.sp_prom.isVisible())
        self.assertFalse(self.win.sl_band_thresh.isVisible())
        self.assertFalse(self.win.combo_band_style.isVisible())
        with patch.object(self.win, 'run_analysis') as analyze:
            self.win.band_settings_toggle.click()
            self.win.lane_style_toggle.click()
            self.app.processEvents()
            self.assertTrue(self.win.sl_band_thresh.isVisible())
            self.assertTrue(self.win.combo_band_style.isVisible())
            self.win.sl_band_thresh.setValue(55)
            self.win._select_ribbon_tool('lane_list')
            self.win._select_ribbon_tool('manual_lanes')
            self.assertEqual(self.win.sl_band_thresh.value(), 55)
            self.assertTrue(self.win.sl_band_thresh.isVisible())
            analyze.assert_not_called()

    def test_focus_view_leaves_unselected_image_untinted_and_export_unchanged(self):
        gel = self.win.gel
        before = render_export(self.source, self.win.lanes, DEFAULT_OPTIONS).tobytes()
        def interior():
            gel.repaint()
            return QColor(gel.grab().toImage().pixel(round(gel._ix_to_wx(35)),
                                                    round(gel._iy_to_wy(80)))).getRgb()[:3]
        self.assertEqual(interior(), (138, 150, 160))
        self.win.chk_focus_overlay.setChecked(False)
        self.assertNotEqual(interior(), (138, 150, 160))
        self.assertFalse(gel.focus_overlay)
        self.win.chk_focus_overlay.setChecked(True)
        self.assertEqual(interior(), (138, 150, 160))
        self.assertEqual(render_export(self.source, self.win.lanes, DEFAULT_OPTIONS).tobytes(), before)


if __name__ == '__main__':
    unittest.main()
