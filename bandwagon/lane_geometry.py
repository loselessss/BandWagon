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


def regular_lane_spans(reference, count, width, reference_index=None):
    """Repeat a full lane interval without moving or resizing the reference.

    The reference includes the inter-lane spacing (not just the dark band).
    Unused image margins are allowed; clipping or overlapping is not.
    """
    if not isinstance(count, int) or count < 1 or not valid_lane_spans([reference], width):
        return None
    left, right = map(int, reference)
    pitch = right - left + 1
    available_left = left // pitch
    available_right = (width - 1 - right) // pitch
    first_slot = max(0, count - 1 - available_right)
    last_slot = min(count - 1, available_left)
    if first_slot > last_slot:
        return None
    if reference_index is None:
        expected = round(((left + right) / 2 + .5) * count / width - .5)
        reference_index = min(last_slot, max(first_slot, expected))
    if reference_index != int(reference_index) or not first_slot <= reference_index <= last_slot:
        return None
    start = left - int(reference_index) * pitch
    spans = [(start + i * pitch, start + (i + 1) * pitch - 1) for i in range(count)]
    return spans if valid_lane_spans(spans, width, count=count) else None
