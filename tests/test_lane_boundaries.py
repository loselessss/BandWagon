import unittest
import numpy as np
from bandwagon.imaging import lane_boundary_signal
from bandwagon.lanes import LanesMixin


class LaneBoundaryTest(unittest.TestCase):
    def test_missing_internal_lane_keeps_observed_centres(self):
        x = np.arange(600)
        centres = [35, 115, 195, 275, 355, 435, 515]
        signal = sum(np.exp(-.5 * ((x - c) / 12) ** 2)
                     for c in centres if c != 275)
        spans = LanesMixin._split_lanes_by_count(signal, 7, 600)
        self.assertEqual(len(spans), 7)
        for (left, right), centre in zip(spans, centres):
            self.assertLess(left, centre)
            self.assertGreater(right, centre)
        self.assertLess(abs(spans[1][0] - 75), 10)

    def test_connected_band_and_cumulative_spacing_drift(self):
        image = np.full((240, 500), 220., dtype=float)
        centres = [28, 105, 190, 290, 418]
        for y in (30, 100, 165):
            for x in centres:
                image[y:y + 8, x - 18:x + 19] -= 55
        image[60:80, 10:438] -= 65
        spans = LanesMixin._split_lanes_by_count(lane_boundary_signal(image, 5), 5, 500)
        self.assertEqual(len(spans), 5)
        for (left, _), a, b in zip(spans[1:], centres, centres[1:]):
            self.assertGreater(left, a + 18)
            self.assertLess(left, b - 18)
        self.assertLess(spans[1][0], 85)

    def test_unequal_gaps_faint_bands_and_background_gradient(self):
        image = np.tile(180 + 40 * np.arange(500) / 500, (240, 1))
        edges = [0, 108, 192, 310, 393, 500]
        for i, (left, right) in enumerate(zip(edges, edges[1:])):
            image[35:42, left + 12:right - 12] -= 90 if i == 0 else 18
        spans = LanesMixin._split_lanes_by_count(lane_boundary_signal(image, 5), 5, 500)
        self.assertEqual(len(spans), 5)
        for (left, _), expected in zip(spans[1:], edges[1:-1]):
            self.assertLessEqual(abs(left - expected), 6)
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], 499)
        self.assertTrue(all(a[1] + 1 == b[0] for a, b in zip(spans, spans[1:])))

    def test_selected_vertical_range_ignores_outside_stain(self):
        image = np.full((200, 300), 220, dtype=np.uint8)
        for x in (15, 115, 215):
            image[100:110, x:x + 70] = 180
        expected = lane_boundary_signal(image, 3, (80, 160))
        image[:70, 75:145] = 0
        np.testing.assert_array_equal(lane_boundary_signal(image, 3, (80, 160)), expected)

    def test_blank_and_too_many_lanes_are_rejected(self):
        signal = lane_boundary_signal(np.full((50, 100), 200, dtype=np.uint8), 5)
        self.assertIsNone(LanesMixin._split_lanes_by_count(signal, 5, 100))
        self.assertIsNone(LanesMixin._split_lanes_by_count(np.ones(10), 8, 10))

    def test_flat_evidence_does_not_shift_uniform_boundaries(self):
        self.assertEqual(LanesMixin._split_lanes_by_count(np.ones(500), 5, 500),
                         [(0, 99), (100, 199), (200, 299), (300, 399), (400, 499)])

    def test_noisy_gaps_cannot_move_boundaries_more_than_fifteen_percent(self):
        rng = np.random.default_rng(42)
        signal = rng.uniform(.1, 1, 900)
        spans = LanesMixin._split_lanes_by_count(signal, 15, 900)
        for i, (left, _) in enumerate(spans[1:], 1):
            self.assertLessEqual(abs(left - i * 60), 9)
        self.assertTrue(all(42 <= right - left + 1 <= 78 for left, right in spans))
