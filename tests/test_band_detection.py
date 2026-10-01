import unittest

import numpy as np

from bandwagon.models import Lane


class BandDetectionTest(unittest.TestCase):
    def test_background_gradient_and_broad_smear_do_not_become_bands(self):
        y = np.arange(500)
        intensity = 20 + .08 * y + 45 * np.exp(-((y - 250) / 110) ** 2)
        intensity[60:67] += 70
        intensity[350:359] += 55
        gray = np.repeat((255 - intensity)[:, None], 24, axis=1)
        lane = Lane(0, 0, 23)
        lane.analyze(gray, 11, 6)
        self.assertEqual(len(lane.peaks), 2)
        for actual, (left, right) in zip(lane.peaks, ((60, 66), (350, 358))):
            self.assertGreaterEqual(actual, left)
            self.assertLessEqual(actual, right)
        self.assertTrue(all(r - l < 20 for l, r in lane.peak_bounds))
        np.testing.assert_allclose(lane.profile, intensity)
        self.assertTrue(all(value > 0 for value in lane.peak_volume))

    def test_narrow_band_on_smear_is_kept_without_integrating_whole_smear(self):
        intensity = np.full(400, 15.0)
        intensity[80:300] += 60
        intensity[180:187] += 50
        lane = Lane(0, 0, 9)
        lane.analyze(np.repeat((255 - intensity)[:, None], 10, axis=1), 11, 6)
        self.assertEqual(list(lane.peaks), [183])
        self.assertLess(lane.peak_bounds[0][1] - lane.peak_bounds[0][0], 15)
        l, r = lane.peak_bounds[0]
        raw = intensity[l:r + 1]
        expected = np.clip(raw - np.linspace(raw[0], raw[-1], len(raw)), 0, None).sum() * 10
        self.assertAlmostEqual(lane.peak_volume[0], expected)

    def test_background_estimate_respects_selected_vertical_range(self):
        gray = np.full((300, 20), 220.0)
        gray[145:152] = 100
        lane = Lane(0, 0, 19)
        lane.analyze(gray, 11, 6, y_top=100, y_bot=200)
        peaks = lane.peaks.copy()
        bounds = list(lane.peak_bounds)
        gray[:100] = 0
        gray[201:] = 0
        lane.analyze(gray, 11, 6, y_top=100, y_bot=200)
        np.testing.assert_array_equal(lane.peaks, peaks)
        self.assertEqual(lane.peak_bounds, bounds)
