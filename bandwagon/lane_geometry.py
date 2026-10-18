"""Shared checks for inclusive lane pixel ranges."""
import math


def valid_lane_spans(spans, width, *, count=None, contiguous=False):
    if width <= 0 or not spans or (count is not None and len(spans) != count):
        return False
    for pair in spans:
        if len(pair) != 2 or any(not math.isfinite(value) or value != int(value) for value in pair):
            return False
        left, right = pair
        if not 0 <= left <= right < width:
            return False
    ordered = sorted(spans)
    for a, b in zip(ordered, ordered[1:]):
        if a[1] >= b[0] or (contiguous and a[1] + 1 != b[0]):
            return False
    return not contiguous or (ordered[0][0] == 0 and ordered[-1][1] == width - 1)


def lane_limits(lanes, lane, width):
    """Nearest neighbours in image order, independent of table ordering."""
    lower, upper = 0, width - 1
    centre = (lane.x1 + lane.x2) / 2
    for other in lanes:
        if other is lane:
            continue
        if (other.x1 + other.x2) / 2 < centre:
            lower = max(lower, other.x2 + 1)
        else:
            upper = min(upper, other.x1 - 1)
    return lower, upper
