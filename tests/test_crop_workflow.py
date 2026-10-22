import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent, QSettings
from PyQt5.QtGui import QMouseEvent, QColor
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.i18n import tr
from bandwagon.models import Lane
from bandwagon.lane_geometry import valid_lane_spans


class CropWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = str(Path(self.temp.name) / 'layout.ini')
        self.enterContext(patch('bandwagon.app.QSettings', side_effect=lambda *args: QSettings(path, QSettings.IniFormat)))
        self.errors = self.enterContext(patch('sys.excepthook'))
        self.win = Analyzer()
        self.source = Image.new('RGB', (200, 160), 'white')
        self.win._orig = self.source.copy()
        self.win._after_load('crop-test.png')
        self.win.resize(1000, 700); self.win.show(); self.app.processEvents()

    def tearDown(self):
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close(); self.app.processEvents()
        self.errors.assert_not_called()
        self.temp.cleanup()

    def drag(self, start, end):
        gel = self.win.gel
        def point(pair):
            return QPoint(round(gel._ix_to_wx(pair[0])), round(gel._iy_to_wy(pair[1])))
        a, b = point(start), point(end)
        QTest.mousePress(gel, Qt.LeftButton, pos=a)
        QApplication.sendEvent(gel, QMouseEvent(QEvent.MouseMove, QPointF(b),
                                                Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.mouseRelease(gel, Qt.LeftButton, pos=b)
        self.app.processEvents()

    def test_paste_selects_rotation_in_ribbon_and_settings_from_other_tools(self):
        self.win._select_ribbon_tool('manual_lanes')
        self.win.ribbon.setCurrentIndex(0)
        with patch.object(self.win, '_read_clipboard_image', return_value=self.source.copy()):
            self.win.ribbon_strips[0].buttons['paste'].click()
        self.assertEqual(self.win.ribbon.currentIndex(), 0)
        self.assertEqual(self.win._active_tool, 'rotate')
        self.assertTrue(self.win.ribbon_strips[0].buttons['rotate'].isChecked())
        self.assertEqual(self.win.settings_title.text(), tr('tool_orientation'))
        self.assertTrue(self.win.rot_spin.isVisible())

    def test_automatic_area_detection_is_first_crop_action(self):
        self.win._select_ribbon_tool('crop')
        layout = self.win.correct_tools['crop'][1].layout()
        self.assertIs(layout.itemAt(0).widget(), self.win.btn_auto_warp)
        self.assertEqual(self.win.gel.mode, 'crop')
        self.assertEqual(self.win.gel.crop_rect, (0, 0, 200, 160))

    def test_crop_drag_creates_rectangle_then_moves_it(self):
        self.win._select_ribbon_tool('crop')
        self.drag((35, 25), (135, 115))
        rect = self.win.gel.crop_rect
        np.testing.assert_allclose(rect, (35, 25, 135, 115), atol=.8)
        self.assertEqual(self.win.gel.corners, [])
        self.drag((75, 65), (195, 155))
        left, top, right, bottom = self.win.gel.crop_rect
        self.assertAlmostEqual(right - left, rect[2] - rect[0])
        self.assertAlmostEqual(bottom - top, rect[3] - rect[1])
        self.assertLessEqual(right, 200); self.assertLessEqual(bottom, 160)
        self.assertIsNone(self.win.gel._crop_drag)

    def test_all_eight_crop_handles_preserve_axis_aligned_bounds(self):
        self.win._select_ribbon_tool('crop')
        for handle in ('nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'):
            with self.subTest(handle=handle):
                gel = self.win.gel
                gel.crop_rect = (40, 30, 140, 120)
                gel._crop_fresh = False
                xs = {'w': 40, 'e': 140}; ys = {'n': 30, 's': 120}
                x = next((v for k, v in xs.items() if k in handle), 90)
                y = next((v for k, v in ys.items() if k in handle), 75)
                dx = -15 if 'w' in handle else 15 if 'e' in handle else 0
                dy = -15 if 'n' in handle else 15 if 's' in handle else 0
                self.drag((x, y), (x + dx, y + dy))
                expected = (25 if 'w' in handle else 40, 15 if 'n' in handle else 30,
                            155 if 'e' in handle else 140, 135 if 's' in handle else 120)
                np.testing.assert_allclose(gel.crop_rect, expected, atol=.8)

    def test_crop_escape_preserves_pixels_and_clears_selection(self):
        self.win._select_ribbon_tool('crop')
        self.drag((25, 25), (150, 120))
        QTest.keyClick(self.win, Qt.Key_Escape)
        self.assertEqual(self.win.gel.mode, 'view')
        self.assertIsNone(self.win.gel.crop_rect)
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())
        self.assertEqual(self.win._edit_pos, -1)

    def test_crop_applies_to_rgb_and_uv_and_undo_restores_crop_selection(self):
        pixels = np.arange(160 * 200, dtype=np.uint8).reshape(160, 200)
        self.win._wb_gray_override = pixels.copy()
        self.win._pristine_wb_gray_override = pixels.copy()
        self.win._select_ribbon_tool('crop')
        self.win.gel.crop_rect = (20, 15, 150, 120)
        QTest.keyClick(self.win, Qt.Key_Return)
        self.assertEqual(self.win._orig.size, (130, 105))
        np.testing.assert_array_equal(self.win._wb_gray_override, pixels[15:120, 20:150])
        self.win._undo()
        self.assertEqual(self.win._orig.size, self.source.size)
        self.assertEqual(self.win.gel.mode, 'crop')
        self.assertEqual(self.win.gel.crop_rect, (20, 15, 150, 120))
        self.win._redo()
        self.assertEqual(self.win._orig.size, (130, 105))
        self.assertIsNone(self.win.gel.crop_rect)

    def test_crop_mask_darkens_only_outside_selection(self):
        self.win._select_ribbon_tool('crop')
        gel = self.win.gel
        gel.crop_rect = (40, 30, 160, 130); gel.update(); self.app.processEvents()
        image = gel.grab().toImage()
        def sample(x, y):
            return QColor(image.pixel(round(gel._ix_to_wx(x)), round(gel._iy_to_wy(y)))).red()
        self.assertEqual(sample(55, 45), 255)
        self.assertLess(sample(20, 20), 150)

    def test_double_click_applies_crop_at_original_resolution_when_zoomed(self):
        self.win._select_ribbon_tool('crop')
        gel = self.win.gel
        gel.crop_rect = (45, 35, 155, 125)
        gel._crop_fresh = False
        gel.set_zoom(1.5)
        centre = QPoint(round(gel._ix_to_wx(100)), round(gel._iy_to_wy(80)))
        QTest.mouseDClick(gel, Qt.LeftButton, pos=centre)
        self.assertEqual(self.win._orig.size, (110, 90))
        self.assertEqual(gel.mode, 'view')

    def test_auto_warp_turns_off_rectangular_crop_mode(self):
        self.win._select_ribbon_tool('crop')
        quad = np.array([[5, 5], [190, 5], [190, 150], [5, 150]], dtype=np.float32)
        with patch('bandwagon.geometry.find_gel_quad', return_value=quad), \
                patch.object(self.win, '_ask', return_value=False):
            self.win._auto_warp()
        self.assertFalse(self.win.btn_crop.isChecked())
        self.assertTrue(self.win.btn_corner.isChecked())
        self.assertEqual(self.win.gel.mode, 'corner')
        self.assertIsNone(self.win.gel.crop_rect)

    def test_manual_lane_add_resize_and_move_cannot_overlap_even_after_table_reorder(self):
        self.win.lanes = [Lane(1, 110, 150), Lane(0, 30, 80)]
        self.win.gel.set_lanes(self.win.lanes); self.win._rebuild_lane_table()
        self.assertFalse(self.win._on_lane_added(60, 120))
        self.assertEqual(len(self.win.lanes), 2)
        self.win._select_ribbon_tool('manual_lanes')
        self.drag((80, 80), (160, 80))
        spans = [(lane.x1, lane.x2) for lane in self.win.lanes]
        self.assertTrue(valid_lane_spans(spans, 200))
        self.assertLess(max(lane.x2 for lane in self.win.lanes if lane.x1 < 110), 110)
        self.drag((60, 3), (175, 3))
        self.assertTrue(valid_lane_spans([(lane.x1, lane.x2) for lane in self.win.lanes], 200))
        self.assertTrue(all(lane.x2 < 200 for lane in self.win.lanes))

    def test_invalid_auto_lanes_do_not_destroy_current_lanes(self):
        self.win.lanes = [Lane(0, 10, 50)]
        self.win.sp_lane_n.setValue(2)
        with patch('bandwagon.lanes.lane_boundary_signal', return_value=np.ones(200)), \
                patch.object(self.win, '_split_lanes_by_count', return_value=[(0, 120), (100, 199)]), \
                patch.object(self.win, '_info') as info:
            self.win._auto_lanes()
        info.assert_called_once()
        self.assertEqual([(lane.x1, lane.x2) for lane in self.win.lanes], [(10, 50)])


if __name__ == '__main__':
    unittest.main()
