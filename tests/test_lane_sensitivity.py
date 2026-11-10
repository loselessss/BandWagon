import unittest
import numpy as np
from bandwagon.imaging import lane_boundary_signal


class LaneSensitivityTest(unittest.TestCase):
    def test_default_is_unchanged_and_higher_retains_faint_signal(self):
        gray = np.full((80, 160), 200., dtype=np.float32)
        gray[:, 20:35] = 199.
        gray[:, 100:120] = 175.
        np.testing.assert_array_equal(lane_boundary_signal(gray, 2),
                                      lane_boundary_signal(gray, 2, sensitivity=50))
        low = lane_boundary_signal(gray, 2, sensitivity=1)
        high = lane_boundary_signal(gray, 2, sensitivity=100)
        self.assertGreater(high[20:35].mean(), low[20:35].mean())
        self.assertTrue(np.isfinite(high).all())
        for value in (0, 101, float('nan')):
            with self.assertRaises(ValueError):
                lane_boundary_signal(gray, 2, sensitivity=value)
