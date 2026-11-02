import unittest
import numpy as np
from bandwagon.lane_geometry import signal_lane_spans, valid_lane_spans
from bandwagon.imaging import lane_boundary_signal


class MarkerWidthTest(unittest.TestCase):
    def test_marker_width_is_used_without_left_background_or_overlap(self):
        signal = np.zeros(400)
        for left, right in ((30, 60), (120, 175), (235, 260), (320, 380)):
            signal[left:right] = 1
        parts = [(0, 99), (100, 199), (200, 299), (300, 399)]
        spans = signal_lane_spans(signal, parts, 0)
        self.assertTrue(valid_lane_spans(spans, 400, count=4))
        self.assertGreater(spans[0][0], 20)
        self.assertLess(spans[-1][1], 399)
        self.assertEqual(len({b-a+1 for a, b in spans}), 1)
        self.assertLessEqual(spans[0][1]-spans[0][0]+1, 34)
        self.assertLessEqual(spans[0][0], 30)
        self.assertGreaterEqual(spans[0][1], 59)

    def test_marker_can_be_in_middle_or_right(self):
        signal = np.zeros(300)
        signal[20:80] = 1; signal[135:165] = 1; signal[235:265] = 1
        parts = [(0, 99), (100, 199), (200, 299)]
        for marker in (1, 2):
            spans = signal_lane_spans(signal, parts, marker)
            self.assertEqual({b-a+1 for a, b in spans}, {32})

    def test_dark_image_border_does_not_replace_marker_signal(self):
        signal = np.zeros(200)
        signal[:8] = 1.5
        signal[30:60] = 1
        signal[130:160] = .7
        spans = signal_lane_spans(signal, [(0, 99), (100, 199)], 0)
        self.assertGreater(spans[0][0], 20)
        self.assertLess(spans[0][1], 70)
        self.assertEqual({b-a+1 for a, b in spans}, {32})

    def test_flat_evidence_is_not_mistaken_for_full_width_band(self):
        parts = [(0, 49), (50, 99)]
        self.assertEqual(signal_lane_spans(np.ones(100), parts, 0), parts)
        self.assertIsNone(signal_lane_spans(np.full(100, np.nan), parts, 0))

    def test_real_signal_pipeline_excludes_background_margin(self):
        image = np.full((240, 320), 220, dtype=np.uint8)
        for x, width in ((25, 35), (105, 45), (185, 30), (265, 40)):
            for y in (30, 65, 110, 150, 190):
                image[y:y+6, x:x+width] = 40
        signal = lane_boundary_signal(image, 4)
        spans = signal_lane_spans(signal, [(0, 79), (80, 159), (160, 239), (240, 319)], 0)
        self.assertGreater(spans[0][0], 15)
        self.assertLess(spans[-1][1], 319)
        self.assertTrue(valid_lane_spans(spans, 320, count=4))
        self.assertEqual(len({b-a+1 for a, b in spans}), 1)
        self.assertTrue(25 <= spans[0][1]-spans[0][0]+1 <= 45)

    def test_missing_lane_keeps_count_and_common_width(self):
        signal = np.zeros(300); signal[30:60] = 1; signal[230:260] = .3
        spans = signal_lane_spans(signal, [(0, 99), (100, 199), (200, 299)], 0)
        self.assertEqual(len(spans), 3)
        self.assertEqual({b-a+1 for a, b in spans}, {32})
        self.assertTrue(valid_lane_spans(spans, 300))
