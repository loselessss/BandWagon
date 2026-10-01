import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PIL import Image, ImageDraw
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QPushButton, QGroupBox

from bandwagon.app import Analyzer
from bandwagon.i18n import tr
from bandwagon.imaging import apply_edit_op, apply_reference_curve, reference_curve


class AdjustControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.errors = self.enterContext(patch("sys.excepthook"))
        self.win = Analyzer()
        self.source = Image.new("RGB", (1800, 1200), "#bccddd")
        ImageDraw.Draw(self.source).rectangle((300, 200, 1400, 400), fill="#203050")
        self.win._orig = self.source.copy()
        self.win._after_load("control-test.png")
        self.win.resize(900, 620); self.win.show(); self.win.activateWindow()
        self.app.processEvents()

    def tearDown(self):
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close()
        self.errors.assert_not_called()

    def click(self, key):
        button = next(b for b in self.win.findChildren(QPushButton) if b.text() == tr(key))
        for name, (_, group) in self.win.correct_tools.items():
            if group.isAncestorOf(button):
                self.win._select_ribbon_tool(name)
                break
        self.app.processEvents()
        QTest.mouseClick(button, Qt.LeftButton)
        self.app.processEvents()

    def test_reset_and_invert_buttons_and_undo_actions(self):
        self.win.correction_tabs.setCurrentIndex(1)
        self.win.curves["RGB"].add_point(100, 170)
        self.win._commit_adjust()
        self.click("btn_reset_curve")
        self.assertEqual(self.win.curves["RGB"].points, [(0, 0), (255, 255)])
        self.win.btn_undo.trigger()
        self.assertIn((100, 170), self.win.curves["RGB"].points)
        self.win.sl_bright.setValue(20)
        self.win._commit_adjust()
        self.click("btn_reset_adjust_all")
        self.assertEqual(self.win.sl_bright.value(), 0)
        self.assertEqual(self.win.curves["RGB"].points, [(0, 0), (255, 255)])
        before = np.array(self.win._orig)
        self.click("btn_invert_colors")
        np.testing.assert_array_equal(np.array(self.win._orig), 255 - before)
        self.win.btn_undo.trigger()
        np.testing.assert_array_equal(np.array(self.win._orig), before)
        self.win.btn_redo.trigger()
        np.testing.assert_array_equal(np.array(self.win._orig), 255 - before)

    def test_geometry_controls_follow_workflow_order(self):
        layout = self.win.correction_tabs.widget(0).widget().layout()
        titles = [layout.itemAt(i).widget().title() for i in range(layout.count())
                  if isinstance(layout.itemAt(i).widget(), QGroupBox)]
        self.assertEqual(titles, [tr("tool_rotate"), tr("tool_flip"), tr("tool_crop"), tr("tool_warp"),
                                  tr("group_bow_correction"), tr("group_shear_correction")])
        for name in self.win.correct_tools:
            self.win._select_ribbon_tool(name)
            self.assertEqual([key for key, (_, group) in self.win.correct_tools.items()
                              if group.isVisibleTo(self.win.tabs)], [name])

    def test_repeated_invert_clicks_restore_colors_and_undo_redo(self):
        self.win.correction_tabs.setCurrentIndex(1)
        original = np.array(self.win._orig)
        for n in range(1, 5):
            self.click("btn_invert_colors")
            np.testing.assert_array_equal(np.array(self.win._orig),
                                          255 - original if n % 2 else original)
        self.assertEqual(len(self.win._edit_ops), 4)
        self.win.btn_undo.trigger()
        np.testing.assert_array_equal(np.array(self.win._orig), 255 - original)
        self.win.btn_redo.trigger()
        np.testing.assert_array_equal(np.array(self.win._orig), original)

    def test_repeated_rotation_and_flip_are_not_deduplicated(self):
        original = self.win._orig.tobytes()
        self.win._flip("h"); self.win._flip("h")
        self.assertEqual(self.win._orig.tobytes(), original)
        for _ in range(4):
            self.win._rotate(90)
        self.assertEqual(self.win._orig.size, self.source.size)
        self.assertEqual(self.win._orig.tobytes(), original)

    def test_auto_and_manual_warp_buttons(self):
        quad = np.array([[100, 100], [1500, 100], [1500, 1000], [100, 1000]], dtype=np.float32)
        with patch("bandwagon.geometry.find_gel_quad", return_value=quad), patch.object(self.win, "_ask", return_value=True):
            self.click("btn_auto_warp")
        self.assertEqual(self.win._orig.size, (1400, 900))
        self.win.btn_undo.trigger()
        self.assertEqual(self.win._orig.size, self.source.size)
        self.win.gel.corners = quad.tolist()
        self.click("btn_apply_warp")
        self.assertEqual(self.win._orig.size, (1400, 900))

    def test_curve_clicks_keep_zoom_pan_and_image_coordinates(self):
        self.win._select_ribbon_tool('curve')
        self.app.processEvents()
        gel = self.win.gel
        gel.set_zoom(2.3); gel._pan_x = 160; gel._pan_y = -75; gel._recompute_rect()
        expected = (gel._img_size, gel._rect.getRect(), gel._pan_x, gel._pan_y)
        seen = []
        self.win.curve.changed.connect(lambda: seen.append(
            (gel._img_size, gel._rect.getRect(), gel._pan_x, gel._pan_y)))
        for point in (QPoint(90, 80), QPoint(160, 180), QPoint(220, 110)):
            QTest.mouseClick(self.win.curve, Qt.LeftButton, pos=point)
            self.app.processEvents()
            self.assertEqual((gel._img_size, gel._rect.getRect(), gel._pan_x, gel._pan_y), expected)
        self.assertTrue(seen)
        self.assertTrue(all(value == expected for value in seen))
        self.assertFalse(self.win.canvas_mode_hint.isVisible())

    def test_auto_warp_can_open_reference_correction_and_cancel_it(self):
        self.win.chk_warp_curve.setChecked(True)
        quad = np.array([[100, 100], [1500, 100], [1500, 1000], [100, 1000]], dtype=np.float32)
        with patch("bandwagon.geometry.find_gel_quad", return_value=quad), \
                patch.object(self.win, "_ask", return_value=True):
            self.click("btn_auto_warp")
        self.assertIsNotNone(self.win._inline_curve)
        self.win._inline_curve.cancel()
        self.assertEqual(self.win._orig.size, (1400, 900))
        self.assertEqual([op for op, _ in self.win._edit_ops], ["warp"])

    def test_switching_geometry_preserves_pending_values(self):
        self.win.rot_slider.setValue(4)
        self.win.bow_slider.setValue(15)
        self.win.shear_slider.setValue(12)
        self.win._commit_shear_correction()
        self.assertEqual(self.win._edit_ops, [
            ("fine_rotate", {"deg": 4}), ("bow_correct", {"amount": 15}),
            ("shear_correct", {"amount": 12})])
        self.win.btn_undo.trigger()
        self.assertEqual(self.win.shear_slider.value(), 0)
        self.assertEqual(self.win.bow_slider.value(), 15)

    def test_ribbon_switch_commits_pending_rotation_and_inline_curve(self):
        self.win.rot_slider.setValue(4)
        self.win._select_ribbon_tool('bow')
        self.assertEqual(self.win._edit_ops[-1], ('fine_rotate', {'deg': 4}))
        self.win.btn_reference_bow.click()
        editor = self.win._inline_curve
        editor.points[2] = (900, editor.baseline - 30)
        editor.preview()
        self.win.ribbon_strips[1].buttons['brightness'].click()
        self.assertIsNone(self.win._inline_curve)
        self.assertEqual(self.win._active_tool, 'brightness')
        self.assertEqual(self.win._edit_ops[-1][0], 'reference_bow')
        self.win._undo()
        self.assertEqual(self.win._edit_ops[self.win._edit_pos][0], 'fine_rotate')

    def test_crop_enter_and_undo_preserve_rgb_and_uv(self):
        self.win._wb_gray_override = np.asarray(self.source.convert('L')).copy()
        self.win._pristine_wb_gray_override = self.win._wb_gray_override.copy()
        self.win._select_ribbon_tool('crop')
        self.assertEqual(self.win.gel.mode, 'corner')
        self.win.gel.corners = [[100, 80], [700, 80], [700, 600], [100, 600]]
        QTest.keyClick(self.win, Qt.Key_Return)
        self.assertEqual(self.win._orig.size, (600, 520))
        np.testing.assert_array_equal(self.win._wb_gray_override,
            np.asarray(self.source.convert('L'))[80:600, 100:700])
        self.win._undo()
        self.assertEqual(self.win._orig.size, self.source.size)
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())

    def test_crop_escape_and_tool_switch_end_pointer_mode(self):
        self.win._select_ribbon_tool('crop')
        QTest.keyClick(self.win, Qt.Key_Escape)
        self.assertEqual(self.win.gel.mode, 'view')
        self.assertFalse(self.win.btn_crop.isChecked())
        self.win._select_ribbon_tool('crop')
        self.win._select_ribbon_tool('manual_lanes')
        self.assertEqual(self.win.gel.mode, 'view')
        self.assertTrue(self.win.lane_table.isVisible())
        self.win.btn_lane.click()
        self.win._select_ribbon_tool('range')
        self.assertFalse(self.win.btn_lane.isChecked())
        self.assertFalse(self.win.lane_table.isVisible())

    def test_file_ribbon_commits_preview_without_losing_selected_tool(self):
        self.win._select_ribbon_tool('bow')
        self.win.btn_reference_bow.click()
        self.win._inline_curve.points[2] = (900, 300)
        self.win.ribbon.setCurrentIndex(0)
        self.assertIsNone(self.win._inline_curve)
        self.assertEqual(self.win._edit_ops[-1][0], 'reference_bow')
        self.assertEqual(self.win.ribbon.currentIndex(), 0)
        self.win.ribbon.setCurrentIndex(1)
        self.assertEqual(self.win._active_tool, 'bow')

    def test_copy_shortcut_path_uses_committed_full_resolution_preview(self):
        self.win.rot_slider.setValue(4)
        self.win._commit_fine_rotation()
        self.win._select_ribbon_tool('brightness')
        self.win.sl_bright.setValue(20)
        seen = []
        with patch.object(self.win, '_export_options', side_effect=lambda image: seen.append(image.copy())):
            self.win.copy_image()
        self.assertEqual(seen[0].size, self.source.size)
        self.assertEqual(seen[0].tobytes(), self.win._apply_color_pipeline(self.win._orig).tobytes())
        self.win._undo()
        self.assertEqual(self.win.sl_bright.value(), 0)

    def test_reference_dialog_drag_preview_apply_and_undo(self):
        def edit_dialog(dialog):
            self.app.processEvents()
            view = self.win.gel
            dialog.preview()
            x, y = dialog.points[2]
            start = QPoint(round(view._ix_to_wx(x)), round(view._iy_to_wy(y)))
            end = start + QPoint(-50, 35)
            before = self.win._orig.tobytes()
            initial = view._pm.toImage()
            QTest.mousePress(view, Qt.LeftButton, pos=start)
            self.app.sendEvent(view, QMouseEvent(QEvent.MouseMove, QPointF(end),
                                               Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
            QTest.qWait(80)
            self.assertIsNotNone(dialog.drag)
            self.assertNotEqual(view._pm.toImage(), initial)
            QTest.mouseRelease(view, Qt.LeftButton, pos=end)
            self.assertNotEqual(dialog.points[2], (x, y))
            corrected = view._pm.toImage()
            dialog.show_original(True)
            self.assertEqual(view._pm.toImage(), initial)
            dialog.show_original(False)
            self.assertEqual(view._pm.toImage(), corrected)
            self.assertEqual(self.win._orig.tobytes(), before)
            dialog.apply()
        self.win.btn_reference_bow.click()
        edit_dialog(self.win._inline_curve)
        self.assertEqual(self.win._edit_ops[-1][0], "reference_bow")
        self.assertNotEqual(self.win._orig.tobytes(), self.source.tobytes())
        self.win.btn_undo.trigger()
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())

    def test_direct_curve_moves_pixels_with_handle_and_cancels(self):
        gray = np.full((100, 200), 255, dtype=np.uint8)
        gray[50, :] = 0
        points = [[0, 50], [50, 50], [100, 30], [150, 50], [199, 50]]
        out, uv = apply_edit_op(Image.fromarray(gray).convert('RGB'), gray,
                                'reference_bow', {'points': points, 'baseline': 50})
        self.assertEqual(int(np.argmin(np.asarray(out)[:, 100, 0])), 30)
        np.testing.assert_array_equal(np.asarray(out)[:, :, 0], uv)
        self.win.btn_reference_bow.click()
        self.win._inline_curve.points[2] = (900, 300)
        self.win._inline_curve.preview()
        self.win.btn_undo.trigger()
        self.assertIsNone(self.win._inline_curve)
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())

    def test_left_grip_moves_whole_curve_preserving_shape_and_preview(self):
        self.win.btn_reference_bow.click()
        editor = self.win._inline_curve
        editor.points[2] = (editor.points[2][0], editor.baseline - 50)
        editor.preview()
        self.app.processEvents()
        points = np.array(editor.points)
        image = self.win.gel._pm.toImage()
        grip = editor.line_grip().toPoint()
        end = grip + QPoint(0, -18)
        QTest.mousePress(self.win.gel, Qt.LeftButton, pos=grip)
        self.app.sendEvent(self.win.gel, QMouseEvent(QEvent.MouseMove, QPointF(end),
                           Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
        QTest.qWait(80)
        self.assertEqual(editor.drag, 'all')
        moved = np.array(editor.points)
        np.testing.assert_array_equal(points[:, 0], moved[:, 0])
        np.testing.assert_allclose(moved[:, 1] - points[:, 1], moved[0, 1] - points[0, 1])
        self.assertLess(moved[0, 1], points[0, 1])
        self.assertNotEqual(self.win.gel._pm.toImage(), image)
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())
        QTest.mouseRelease(self.win.gel, Qt.LeftButton, pos=end)
        editor.apply()
        self.win.btn_undo.trigger()
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())

    def test_asymmetric_reference_flattens_band_and_preserves_uv_alignment(self):
        points = [[0, 55], [35, 48], [80, 70], [145, 85], [199, 60]]
        curve = reference_curve(points, np.arange(200))
        gray = np.full((150, 200), 255, dtype=np.uint8)
        for x, y in enumerate(curve):
            gray[round(y), x] = 0
        image = Image.fromarray(gray).convert("RGB")
        output, uv = apply_edit_op(image, gray, "reference_bow", {"points": points})
        np.testing.assert_array_equal(np.asarray(output)[:, :, 0], uv)
        locations = np.argmin(uv, axis=0)
        self.assertLessEqual(np.ptp(locations), 1)
        self.assertAlmostEqual(float(np.median(locations)), np.mean(np.array(points)[:, 1]), delta=1)
        flat = [[0, 50], [199, 50]]
        self.assertEqual(apply_reference_curve(image, flat).tobytes(), image.tobytes())


if __name__ == "__main__":
    unittest.main()
