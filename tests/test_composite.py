import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication
from bandwagon.app import Analyzer
from bandwagon.composite import CompositeStudio, export_composite, load_composite
from bandwagon.imaging import apply_edit_op, uv_only_grayscale, warp_uv_to_visible
from bandwagon.models import Lane
from scripts.generate_composite_qa import fixture


class CompositeQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.visible, self.uv, self.truth = fixture()

    def test_bright_uv_detects_known_bands(self):
        gray = uv_only_grayscale(self.uv)
        for i, expected in enumerate(self.truth["lanes"]):
            lane = Lane(i, expected["x1"], expected["x2"])
            lane.analyze(gray, 20, 10)
            np.testing.assert_array_equal(lane.peaks, expected["peaks_y"])

    def test_geometry_keeps_display_and_analysis_aligned(self):
        gray = np.array(self.uv.convert("L"))
        for op, params in [("rotate", {"deg": 90}), ("rotate", {"deg": -90}),
                           ("fine_rotate", {"deg": 12}), ("bow_correct", {"amount": 20}),
                           ("shear_correct", {"amount": 15}), ("flip", {"dir": "h"})]:
            with self.subTest(op=op, params=params):
                rgb, actual = apply_edit_op(self.uv, gray, op, params)
                # Interior pixels avoid intentionally different padding colors.
                np.testing.assert_allclose(np.array(rgb.convert("L"))[25:-25, 25:-25],
                                           actual[25:-25, 25:-25], atol=1)

    def test_reset_preserves_uv_after_import_and_project_reload(self):
        with tempfile.TemporaryDirectory() as temp:
            composite = str(Path(temp) / "qa.bwcomposite")
            project = str(Path(temp) / "qa.bandwagon")
            gray = 255 - np.array(self.uv.convert("L"))
            export_composite(composite, self.visible, gray)
            win = Analyzer()
            try:
                win.import_composite(composite)
                win.reset_all()
                np.testing.assert_array_equal(win._gray_orig, gray)
                self.assertTrue(win._write_project_file(project))
                win.open_project(project)
                win.reset_all()
                np.testing.assert_array_equal(win._gray_orig, gray)
            finally:
                win._saved_snapshot = win._project_state_snapshot()
                win.close()

    def test_identity_alignment_and_lossless_roundtrip(self):
        warped = warp_uv_to_visible(self.uv, self.truth["identity_corners"], self.visible.size)
        np.testing.assert_array_equal(warped, self.uv)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "qa.bwcomposite"
            gray = uv_only_grayscale(warped)
            export_composite(path, self.visible, gray)
            blend, loaded = load_composite(path)
            np.testing.assert_array_equal(blend, self.visible)
            np.testing.assert_array_equal(loaded, gray)

    def test_invalid_corners_are_rejected(self):
        for corners in ([[0, 0]] * 4, [[0, 0], [319, 239], [319, 0], [0, 239]]):
            with self.subTest(corners=corners), self.assertRaises(ValueError):
                warp_uv_to_visible(self.uv, corners, self.visible.size)


if __name__ == "__main__":
    unittest.main()
