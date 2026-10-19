import unittest
import numpy as np
from bandwagon.imaging import lane_boundary_signal
from bandwagon.lanes import LanesMixin
from bandwagon.lane_geometry import valid_lane_spans, regular_lane_spans


class LaneBoundaryTest(unittest.TestCase):
    def test_distinct_centres_cannot_bypass_width_limits(self):
        x = np.arange(600)
        signal = sum(np.exp(-.5 * ((x - centre) / 12) ** 2)
                     for centre in (25, 90, 210, 330, 450, 560))
        spans = LanesMixin._split_lanes_by_count(signal, 6, 600)
        self.assertTrue(valid_lane_spans(spans, 600, count=6, contiguous=True))
        self.assertTrue(all(70 <= right - left + 1 <= 130 for left, right in spans))

    def test_reference_layout_keeps_marker_fixed_and_all_widths_equal(self):
        for reference, slot in (((15, 64), 0), ((215, 264), 4), ((465, 514), 9)):
            spans = regular_lane_spans(reference, 10, 540, slot)
            self.assertTrue(valid_lane_spans(spans, 540, count=10))
            self.assertEqual(spans[slot], reference)
            self.assertEqual([b - a + 1 for a, b in spans], [50] * 10)
            self.assertTrue(all(a[1] + 1 == b[0] for a, b in zip(spans, spans[1:])))

    def test_reference_layout_retains_margins_and_rejects_clipping(self):
        self.assertEqual(regular_lane_spans((215, 264), 10, 540),
                         [(15 + i * 50, 64 + i * 50) for i in range(10)])
        for reference, count, width, slot in (((10, 79), 3, 200, None),
                                               ((0, 49), 3, 200, 1),
                                               ((-1, 30), 3, 200, None)):
            self.assertIsNone(regular_lane_spans(reference, count, width, slot))

    def test_detection_never_overlaps_or_leaves_image_for_varied_counts(self):
        rng = np.random.default_rng(21)
        for width, count in ((60, 30), (200, 15), (730, 15), (1200, 60), (6000, 15)):
            for kind in ('noise', 'smooth', 'flat'):
                signal = rng.uniform(.01, 1, width)
                if kind == 'smooth':
                    from scipy.ndimage import gaussian_filter1d
                    signal = gaussian_filter1d(signal, width / count * .12)
                elif kind == 'flat':
                    signal[:] = 1
                spans = LanesMixin._split_lanes_by_count(signal, count, width)
                with self.subTest(width=width, count=count, kind=kind):
                    self.assertTrue(valid_lane_spans(spans, width, count=count, contiguous=True))
                    self.assertTrue(all(np.ceil(width / count * .7) <= b - a + 1 <=
                                        np.floor(width / count * 1.3) for a, b in spans))

    def test_global_partition_does_not_split_wide_gap_into_narrow_lanes(self):
        x = np.arange(750)
        centres = [30, 82, 134, 184, 225, 268, 312, 355, 400, 444,
                   488, 532, 579, 635, 706]
        signal = sum((.03 if i in (4, 5) else 1.) *
                     np.exp(-.5 * ((x - c) / 13) ** 2)
                     for i, c in enumerate(centres))
        spans = LanesMixin._split_lanes_by_count(signal, 15, 750)
        self.assertEqual(len(spans), 15)
        for (left, right), centre in zip(spans, centres):
            self.assertLess(left, centre)
            self.assertGreater(right, centre)
            self.assertGreaterEqual(right - left + 1, 32)

    def test_global_partition_large_image_covers_every_pixel(self):
        x = np.arange(6000)
        signal = 1 + np.cos(x * 2 * np.pi / 400)
        spans = LanesMixin._global_lane_partition(signal, 15, len(x))
        self.assertEqual(len(spans), 15)
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], 5999)
        self.assertTrue(all(a <= b for a, b in spans))
        self.assertTrue(all(a[1] + 1 == b[0] for a, b in zip(spans, spans[1:])))

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
