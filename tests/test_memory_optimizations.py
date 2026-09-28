import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt5.QtWidgets import QApplication
from bandwagon.app import Analyzer
from bandwagon.imaging import apply_bow_correction, apply_shear_correction


class MemoryOptimizationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = Analyzer()
        self.image = Image.fromarray(np.random.default_rng(42).integers(
            0, 256, (259, 137, 3), dtype=np.uint8))
        self.win._orig = self.image
        self.win._after_load("test")

    def tearDown(self):
        self.win._saved_snapshot = self.win._project_state_snapshot()
        self.win.close()

    def test_color_lut_matches_previous_pipeline(self):
        win = self.win
        win.curves["Red"].points = [(0, 10), (80, 120), (255, 240)]
        win.curves["Red"]._rebuild()
        for bright in (-100, 0, 73):
            for contrast in (-90, 0, 85):
                with patch.object(win.sl_bright, "value", return_value=bright), \
                     patch.object(win.sl_contrast, "value", return_value=contrast):
                    arr = np.asarray(self.image, dtype=np.float32)
                    arr = arr + float(bright)
                    f = (259 * (float(contrast) + 255)) / (255 * (259 - float(contrast)))
                    arr = np.clip(f * (arr - 128) + 128, 0, 255).astype(np.uint8)
                    arr = win.curves["RGB"].lut()[arr]
                    for i, ch in enumerate(("Red", "Green", "Blue")):
                        arr[:, :, i] = win.curves[ch].lut()[arr[:, :, i]]
                    np.testing.assert_array_equal(np.asarray(win._apply_color_pipeline(self.image)), arr)

    def test_strips_match_full_maps_including_boundaries(self):
        import cv2
        arr = np.asarray(self.image)
        h, w = arr.shape[:2]
        for bow, fn in ((True, apply_bow_correction), (False, apply_shear_correction)):
            for amount in (-150.5, 0, 137.25):
                x, y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
                if bow:
                    shift = float(amount) * ((np.arange(w, dtype=np.float32) - w / 2.0) / (w / 2.0)) ** 2
                    y = y - shift[None, :]
                else:
                    shift = float(amount) * ((np.arange(h, dtype=np.float32) - h / 2.0) / max(h - 1, 1))
                    x = x - shift[:, None]
                expected = cv2.remap(arr, x, y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                np.testing.assert_array_equal(np.asarray(fn(self.image, amount)), expected)

    def test_failed_edit_restores_image_and_history(self):
        win = self.win
        before = win._orig
        history = list(win._edit_ops)
        pos = win._edit_pos
        with patch("bandwagon.geometry.apply_edit_op", side_effect=MemoryError):
            self.assertFalse(win._rotate(90))
        self.assertIs(win._orig, before)
        self.assertEqual(win._edit_ops, history)
        self.assertEqual(win._edit_pos, pos)
        self.assertIn("메모리", win.status.currentMessage())
        win._rotate(90)
        self.assertEqual(win._orig.size, before.size[::-1])

    def test_failed_save_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.bandwagon"
            self.assertTrue(self.win._write_project_file(str(path)))
            saved = path.read_bytes()
            with patch.object(Image.Image, "save", side_effect=MemoryError), \
                 patch.object(self.win, "_warn"):
                self.assertFalse(self.win._write_project_file(str(path)))
            self.assertEqual(path.read_bytes(), saved)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_late_failure_restores_display_and_can_retry(self):
        win = self.win
        original, display = win._orig, win._display
        pos = win._edit_pos
        with patch.object(win, "_refresh_after_pixels_changed", side_effect=MemoryError):
            self.assertFalse(win._rotate(90))
        self.assertIs(win._orig, original)
        self.assertIs(win._display, display)
        self.assertEqual(win._edit_pos, pos)
        win._rotate(90)
        self.assertEqual(win._orig.size, original.size[::-1])

    def test_histograms_match_previous_average(self):
        arr = np.asarray(self.image)
        for ch in ("RGB", "Red", "Green", "Blue"):
            flat = arr.mean(axis=2) if ch == "RGB" else arr[:, :, ("Red", "Green", "Blue").index(ch)]
            counts, _ = np.histogram(flat.astype(np.uint8), bins=256, range=(0, 256))
            np.testing.assert_array_equal(self.win._hist_for(ch), counts / counts.max())
