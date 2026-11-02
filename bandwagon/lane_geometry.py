"""Shared checks for inclusive lane pixel ranges."""
import math
import numpy as np


def signal_lane_spans(signal, partitions, marker_index=None):
    """Fit analysis windows inside search partitions, allowing unused margins.

    The marker's measured signal width is preferred, not its partition width.
    Without a reliable marker, use the median measured lane width. Flat or
    ambiguous evidence leaves the partition unchanged rather than inventing a
    narrow band. Search partitions are disjoint, so fitted windows cannot overlap.
    """
    signal = np.asarray(signal, dtype=float)
    if signal.ndim != 1 or not np.isfinite(signal).all() or not valid_lane_spans(partitions, len(signal)):
        return None
    supports = []
    for left, right in partitions:
        local = signal[left:right + 1]
        floor = float(np.percentile(local, 15))
        amplitude = float(local.max() - floor)
        if amplitude <= max(.002, abs(float(local.max())) * .12):
            supports.append(None)
            continue
        peak = int(np.argmax(local))
        threshold = floor + amplitude * .20
        indices = np.flatnonzero(local > threshold)
        groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
        interior = [g for g in groups if 3 <= len(g) <= len(local) * .90
                    and g[0] > 0 and g[-1] < len(local) - 1]
        # A dark frame edge must not win over an isolated interior lane.
        if interior:
            group = max(interior, key=lambda g: float(np.sum(local[g] - floor)))
        else:
            group = next(g for g in groups if peak in g)
        lo, hi = int(group[0]), int(group[-1])
        measured = hi - lo + 1
        # A clipped plateau is not trustworthy as a reference width.
        reliable = lo > 0 and hi < len(local) - 1 and 3 <= measured <= len(local) * .90
        supports.append((left + lo, left + hi, reliable))
    reference = supports[marker_index] if marker_index is not None and 0 <= marker_index < len(supports) else None
    if reference is not None and reference[2]:
        target = reference[1] - reference[0] + 1
    else:
        widths = [item[1] - item[0] + 1 for item in supports if item is not None and item[2]]
        target = int(round(float(np.median(widths)))) if widths else None
    if target is None:
        return list(partitions)
    # A small shoulder allowance avoids truncating the threshold crossing.
    target += max(2, int(round(target * .08)))
    target = min(target, min(b - a + 1 for a, b in partitions))
    result = []
    for (left, right), support in zip(partitions, supports):
        centre = (left + right) / 2 if support is None else (support[0] + support[1]) / 2
        start = max(left, min(right - target + 1, int(round(centre - (target - 1) / 2))))
        result.append((start, start + target - 1))
    return result if valid_lane_spans(result, len(signal), count=len(partitions)) else None


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
