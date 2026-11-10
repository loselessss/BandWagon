import os
import json
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import numpy as np
from PIL import Image
from PyQt5.QtWidgets import QApplication

from bandwagon.app import Analyzer
from bandwagon.imaging import apply_edit_op
from bandwagon.models import Lane
from bandwagon.quantitation import SourceQuantitation
from bandwagon.recovery import RecoveryWriter


class SourceQuantitationTest(unittest.TestCase):
    def setUp(self):
        self.gray = np.full((100, 100), 245, np.uint8)
        self.gray[5:16, 45:55] = 145

    def test_identity_matches_existing_integral(self):
        lane = Lane(1, 40, 60)
        lane.analyze(self.gray, 1, 2, threshold_pct=0)
        expected = lane.peak_area.copy(), lane.peak_volume.copy()
        SourceQuantitation(self.gray, []).apply([lane])
        np.testing.assert_allclose(lane.peak_area, expected[0])
        np.testing.assert_allclose(lane.peak_volume, expected[1])

    def test_stretch_counts_each_original_pixel_once(self):
        ops = [('shear_correct', {'amount': 0, 'trapezoid': 80})]
        context = SourceQuantitation(self.gray, ops)
        _, y, _ = context.map(np.array([50., 50.]), np.array([1., 21.]))
        top, bottom = int(np.floor(y[0])), int(np.ceil(y[1]))
        _, volume = context.measure(0, 99, top, bottom)
        self.assertAlmostEqual(volume, 11*10*100, delta=1)
        stretched, _ = apply_edit_op(Image.fromarray(self.gray).convert('RGB'), None, *ops[0])
        # Demonstrate the inflation that the old resampled-pixel integral had.
        self.assertGreater(float((245-np.asarray(stretched)[:, :, 0].astype(float)).clip(0).sum()),
                           volume*2)

    def test_geometry_roundtrips_and_output_dimensions(self):
        cases = [
            ('rotate', {'deg': 90}), ('rotate', {'deg': -90}), ('rotate', {'deg': 180}),
            ('flip', {'dir': 'h'}), ('flip', {'dir': 'v'}),
            ('crop', {'box': [5, 7, 90, 86]}), ('fine_rotate', {'deg': 17}),
            ('bow_correct', {'amount': 19}),
            ('reference_bow', {'points': [[0, 30], [50, 48], [99, 35]], 'baseline': 42}),
            ('reference_bow', {'points': [[0, 30], [50, 48], [99, 35]]}),
            ('shear_correct', {'amount': 18, 'vertical': -13, 'trapezoid': 60}),
            ('shear_correct', {'amount': -14, 'vertical': 21, 'trapezoid': -60}),
            ('warp', {'corners': [[20, 10], [80, 15], [90, 90], [10, 80]]}),
        ]
        image = Image.fromarray(self.gray).convert('RGB')
        for op in cases:
            with self.subTest(op=op[0], params=op[1]):
                ctx = SourceQuantitation(self.gray, [op])
                x, y = np.array([35., 50., 63.]), np.array([33., 50., 67.])
                dx, dy, _ = ctx.map(x, y)
                sx, sy, _ = ctx.map(dx, dy, reverse=True)
                np.testing.assert_allclose(sx, x, atol=1e-8)
                np.testing.assert_allclose(sy, y, atol=1e-8)
                edited, _ = apply_edit_op(image, None, *op)
                self.assertEqual(ctx.size, edited.size)

    def test_chained_crop_rotation_and_curve_preserve_signal(self):
        ops = [('crop', {'box': [20, 0, 80, 50]}), ('rotate', {'deg': 180}),
               ('bow_correct', {'amount': 2}), ('flip', {'dir': 'h'})]
        context = SourceQuantitation(self.gray, ops)
        self.assertAlmostEqual(context.measure(0, 59, 27, 49)[1], 11000, delta=1)

    def test_inverse_coordinates_match_actual_image_resampling(self):
        yy, xx = np.mgrid[:80, :120]
        image = Image.fromarray(np.stack((xx, yy, np.full_like(xx, 50)), axis=-1).astype('uint8'))
        cases = [
            ('rotate', {'deg': 90}), ('rotate', {'deg': -90}), ('rotate', {'deg': 180}),
            ('flip', {'dir': 'h'}), ('flip', {'dir': 'v'}),
            ('crop', {'box': [5, 7, 90, 76]}), ('fine_rotate', {'deg': 17}),
            ('bow_correct', {'amount': 19}),
            ('reference_bow', {'points': [[0, 20], [50, 35], [119, 25]], 'baseline': 30}),
            ('shear_correct', {'amount': 18, 'vertical': -13, 'trapezoid': 60}),
            ('warp', {'corners': [[20, 10], [80, 15], [90, 70], [10, 60]]}),
        ]
        for op in cases:
            with self.subTest(op=op[0]):
                context = SourceQuantitation(np.zeros((80, 120), np.uint8), [op])
                edited, _ = apply_edit_op(image, None, *op)
                dy, dx = np.mgrid[:edited.height, :edited.width]
                sx, sy, valid = context.map(dx, dy, reverse=True)
                valid &= (sx > 3) & (sx < 116) & (sy > 3) & (sy < 76)
                actual = np.array(edited)
                np.testing.assert_allclose(actual[:, :, 0][valid], sx[valid], atol=1.1)
                np.testing.assert_allclose(actual[:, :, 1][valid], sy[valid], atol=1.1)

    def test_reflected_padding_is_not_quantified(self):
        # All output rows sample reflected border in the display, but there are
        # no actual original pixels in that part of the corrected image.
        context = SourceQuantitation(self.gray, [('reference_bow', {
            'points': [[0, 30], [99, 30]], 'baseline': -170})])
        self.assertEqual(context.measure(0, 99, 10, 40), (0., 0.))

    def test_uv_ignores_display_inversion(self):
        ops = [('invert_colors', {})]
        normal = SourceQuantitation(255-self.gray, ops)
        uv = SourceQuantitation(self.gray, ops, invertible_colors=False)
        self.assertEqual(normal.measure(40, 60, 1, 20), uv.measure(40, 60, 1, 20))


class SourceQuantitationProjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.win = Analyzer()
        gray = np.full((100, 100), 245, np.uint8)
        gray[5:16, 45:55] = 145
        self.win._orig = Image.fromarray(gray).convert('RGB')
        self.win._after_load('synthetic gel')

    def tearDown(self):
        self.win._detach_recovery()
        self.win._dispose_closed_window()
        self.app.processEvents()

    def test_source_and_geometry_survive_save_reopen_and_undo(self):
        original = self.win._gray_orig.copy()
        self.win._record_op('shear_correct', {'amount': 0, 'trapezoid': 80})
        self.win._refresh_after_pixels_changed()
        self.win.lanes = [Lane(1, 0, 99)]
        self.win.sp_prom.setValue(99)
        self.win.run_analysis()
        detector = Lane(1, 0, 99)
        detector.analyze(self.win._gray_orig, 2, self.win.sp_dist.value(),
                         threshold_pct=self.win.sl_band_thresh.value())
        np.testing.assert_array_equal(self.win.lanes[0].peaks, detector.peaks)
        self.assertEqual(self.win.lanes[0].peak_bounds, detector.peak_bounds)
        expected = self.win.lanes[0].peak_volume.copy()
        self.assertTrue(len(expected))
        np.testing.assert_array_equal(self.win._quant_source, original)
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/'source.bandwagon')
            self.assertTrue(self.win._write_project_file(path))
            self.assertTrue(self.win.open_project(path))
        np.testing.assert_array_equal(self.win._quant_source, original)
        np.testing.assert_allclose(self.win.lanes[0].peak_volume, expected)
        prefix = list(self.win._quant_prefix)
        self.win._rotate(90)
        self.win._undo()
        self.assertEqual(self.win._quant_prefix, prefix)
        self.win.run_analysis()
        np.testing.assert_allclose(self.win.lanes[0].peak_volume, expected)

    def test_reset_after_reopen_retains_original_quantitation_baseline(self):
        self.win._record_op('shear_correct', {'amount': 0, 'trapezoid': 80})
        self.win._refresh_after_pixels_changed()
        original = self.win._quant_source.copy()
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/'reset.bandwagon')
            self.assertTrue(self.win._write_project_file(path))
            self.assertTrue(self.win.open_project(path))
        baseline = list(self.win._quant_prefix)
        self.win._rotate(90)
        self.win.reset_all()
        np.testing.assert_array_equal(self.win._quant_source, original)
        self.assertEqual(self.win._quant_prefix, baseline)
        self.assertEqual(SourceQuantitation(original, baseline).size, self.win._orig.size)
        # Opening a genuinely different image must discard that baseline.
        self.win._orig = Image.new('RGB', (70, 80), 'white')
        self.win._after_load('new image')
        self.assertIsNone(self.win._quant_source)
        self.assertIsNone(self.win._pristine_quant_source)

    def test_history_compaction_retains_quantitation_geometry(self):
        self.win._EDIT_MAX = 2
        self.win._record_op('crop', {'box': [10, 0, 90, 90]})
        self.win._record_op('flip', {'dir': 'h'})
        self.win._record_op('rotate', {'deg': 180})
        self.assertEqual(self.win._quant_source.shape, (100, 100))
        self.assertEqual(self.win._quant_prefix, [('crop', {'box': [10, 0, 90, 90]})])
        context = SourceQuantitation(self.win._quant_source,
                                     self.win._quant_prefix+self.win._edit_ops[:self.win._edit_pos+1])
        self.assertEqual(context.size, self.win._orig.size)

    def test_recovery_writer_preserves_source_and_captured_geometry(self):
        self.win._record_op('crop', {'box': [10, 0, 90, 90]})
        self.win._refresh_after_pixels_changed()
        with tempfile.TemporaryDirectory() as folder:
            writer = RecoveryWriter(None, Path(folder)/'backup.bandwagon', None,
                                    json.dumps(self.win._capture_project_metadata()),
                                    self.win._orig, None, self.win._quant_source,
                                    self.win._quantitation_geometry())
            # A later edit must not change the already captured backup revision.
            self.win._rotate(90)
            writer.run()
            self.assertIsNone(writer.error)
            self.assertTrue(self.win.open_project(writer.temporary))
            self.assertEqual(self.win._orig.size, (80, 90))
            self.assertEqual(self.win._quant_source.shape, (100, 100))
            self.assertEqual(self.win._quant_prefix, [['crop', {'box': [10, 0, 90, 90]}]])
            self.assertIsNone(writer.quant_source)
            writer.deleteLater()

    def test_old_project_without_source_uses_saved_image(self):
        # Legacy archives remain readable without pretending to recover pixels
        # that were never stored in them.
        import zipfile
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/'legacy.bandwagon')
            with zipfile.ZipFile(path, 'w') as archive:
                with archive.open('image.png', 'w') as stream:
                    self.win._orig.save(stream, format='PNG')
                archive.writestr('project.json', json.dumps(self.win._capture_project_metadata()))
            self.assertTrue(self.win.open_project(path))
        self.assertIsNone(self.win._quant_source)
        self.win._rotate(90)
        self.assertEqual(self.win._quant_source.shape, (100, 100))


if __name__ == '__main__':
    unittest.main()
