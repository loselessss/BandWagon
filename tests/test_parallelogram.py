import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import cv2
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.imaging import apply_shear_correction, apply_edit_op


class ParallelogramMathTest(unittest.TestCase):
    def test_both_signs_straighten_lanes_and_bands(self):
        h, w = 200, 240
        for amount in (-50, 50):
            pixels = np.full((h, w), 240, np.uint8)
            for y in range(h):
                x = round(110 - amount * ((y - h / 2) / (h - 1)))
                pixels[y, x - 1:x + 2] = 20
            corrected = np.asarray(apply_shear_correction(Image.fromarray(pixels), amount))[:, :, 0]
            self.assertGreater(np.ptp(np.argmin(pixels[20:-20], axis=1)), 20)
            self.assertLessEqual(np.ptp(np.argmin(corrected[20:-20], axis=1)), 1)
            pixels.fill(240)
            for x in range(w):
                y = round(90 - amount * ((x - w / 2) / (w - 1)))
                pixels[y - 1:y + 2, x] = 20
            corrected = np.asarray(apply_shear_correction(Image.fromarray(pixels), 0, amount))[:, :, 0]
            self.assertGreater(np.ptp(np.argmin(pixels[:, 20:-20], axis=0)), 20)
            self.assertLessEqual(np.ptp(np.argmin(corrected[:, 20:-20], axis=0)), 1)

    def test_combined_strip_maps_match_full_reference_with_bounded_memory(self):
        arr = np.random.default_rng(3).integers(0, 256, (275, 330, 3), dtype=np.uint8)
        h, w = arr.shape[:2]
        image = Image.fromarray(arr)
        for horizontal, vertical in ((40, 25), (-40, 25), (40, -25), (0, -80)):
            x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
            y -= vertical * ((x - w / 2) / (w - 1))
            x -= horizontal * ((y - h / 2) / (h - 1))
            expected = cv2.remap(arr, x, y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            shapes = []
            original = cv2.remap
            def remap(source, map_x, map_y, *args, **kwargs):
                shapes.append(map_x.shape)
                return original(source, map_x, map_y, *args, **kwargs)
            with patch('cv2.remap', side_effect=remap):
                actual = apply_shear_correction(image, horizontal, vertical)
            np.testing.assert_array_equal(np.asarray(actual), expected)
            self.assertEqual(shapes, [(128, w), (128, w), (19, w)])

    def test_uv_alignment_and_legacy_parameters(self):
        gray = np.random.default_rng(7).integers(0, 256, (150, 180), dtype=np.uint8)
        rgb = Image.fromarray(gray).convert('RGB')
        for params in ({'amount': 35}, {'amount': 35, 'vertical': -23}, {'amount': 0, 'vertical': 70}):
            result, uv = apply_edit_op(rgb, gray, 'shear_correct', params)
            np.testing.assert_array_equal(np.asarray(result)[:, :, 0], uv)
            self.assertEqual(result.size, rgb.size)
        old, _ = apply_edit_op(rgb, None, 'shear_correct', {'amount': 35})
        np.testing.assert_array_equal(old, apply_shear_correction(rgb, 35, 0))
        self.assertIs(apply_shear_correction(rgb, 0, 0), rgb)

    def test_small_images_preserve_dimensions(self):
        for size in ((1, 1), (1, 20), (20, 1)):
            image = Image.new('RGB', size, 'white')
            self.assertEqual(apply_shear_correction(image, 150, -150).size, size)


class ParallelogramControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = Analyzer()
        self.enterContext(patch('bandwagon.fileio._save_recent_files'))
        pixels = np.random.default_rng(4).integers(0, 256, (150, 200), dtype=np.uint8)
        self.source = Image.fromarray(pixels).convert('RGB')
        self.win._orig = self.source.copy(); self.win._after_load('shear.png')
        self.win._pristine_wb_gray_override = pixels.copy()
        self.win._wb_gray_override = pixels.copy(); self.win._gray_orig = pixels.copy()
        self.win._select_ribbon_tool('bow')

    def tearDown(self):
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close(); self.win.deleteLater(); self.app.processEvents()

    def correct(self, x=30, y=20):
        self.win.shear_slider.setValue(x)
        self.win.shear_vertical_slider.setValue(y)
        self.win._commit_shear_correction()

    def test_preview_commit_undo_redo_and_reset_both_axes(self):
        self.win.shear_slider.setValue(30); self.win.shear_vertical_slider.setValue(20)
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())
        self.assertEqual(self.win.shear_vertical_spin.value(), 20)
        self.win._commit_shear_correction()
        self.assertEqual(self.win._edit_ops, [('shear_correct', {'amount': 30, 'vertical': 20})])
        expected = apply_shear_correction(self.source, 30, 20)
        self.assertEqual(self.win._orig.tobytes(), expected.tobytes())
        np.testing.assert_array_equal(np.asarray(expected)[:, :, 0], self.win._wb_gray_override)
        self.win._undo()
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())
        self.assertEqual(self.win.shear_vertical_spin.value(), 0)
        self.win._redo()
        self.assertEqual(self.win._orig.tobytes(), expected.tobytes())
        self.assertEqual(self.win.shear_vertical_spin.value(), 20)
        self.win._reset_shear_correction()
        self.assertEqual((self.win.shear_slider.value(), self.win.shear_vertical_slider.value()), (0, 0))
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())

    def test_zero_horizontal_keeps_vertical_and_repeated_commit_does_not_compound(self):
        self.correct()
        self.win.shear_slider.setValue(0); self.win._commit_shear_correction()
        expected = apply_shear_correction(self.source, 0, 20)
        self.assertEqual(self.win._edit_ops, [('shear_correct', {'amount': 0, 'vertical': 20})])
        for _ in range(3): self.win._commit_shear_correction()
        self.assertEqual(self.win._orig.tobytes(), expected.tobytes())
        self.assertEqual(len(self.win._edit_ops), 1)
        self.win.shear_vertical_spin.setValue(0); self.win._commit_shear_correction()
        self.assertEqual(self.win._orig.tobytes(), self.source.tobytes())

    def test_tool_switch_commits_preview_and_new_image_clears_both_axes(self):
        self.win.shear_vertical_slider.setValue(-25)
        self.win._select_ribbon_tool('marker')
        self.assertEqual(self.win._edit_ops[-1], ('shear_correct', {'amount': 0, 'vertical': -25}))
        self.win._orig = self.source.copy(); self.win._after_load('new.png')
        self.assertEqual((self.win.shear_spin.value(), self.win.shear_vertical_spin.value()), (0, 0))

    def test_save_reload_keeps_rgb_uv_pixels_and_analysis_coordinates(self):
        self.correct()
        expected = self.win._orig.tobytes(); uv = self.win._gray_orig.copy()
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'corrected.bandwagon')
            self.assertTrue(self.win._write_project_file(path))
            self.assertTrue(self.win.open_project(path))
        self.assertEqual(self.win._orig.tobytes(), expected)
        np.testing.assert_array_equal(self.win._gray_orig, uv)
        self.assertEqual(self.win.shear_vertical_spin.value(), 0)

    def test_new_axis_after_other_geometry_does_not_repeat_old_axis(self):
        self.correct(x=30, y=0)
        self.win._rotate(180)
        before = self.win._orig.copy()
        self.win.shear_vertical_slider.setValue(20); self.win._commit_shear_correction()
        self.assertEqual(self.win._edit_ops[-1], ('shear_correct', {'amount': 0, 'vertical': 20}))
        self.assertEqual(self.win._orig.tobytes(), apply_shear_correction(before, 0, 20).tobytes())


if __name__ == '__main__':
    unittest.main()
