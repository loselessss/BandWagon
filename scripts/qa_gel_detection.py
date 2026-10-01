"""Inspect lane/band detection on a local gel; never copy the input into Git.

Example: python scripts/qa_gel_detection.py IMAGE --crop 275 325 880 1145
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image, ImageDraw

from bandwagon.imaging import lane_boundary_signal
from bandwagon.lanes import LanesMixin
from bandwagon.models import Lane


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('--crop', nargs=4, type=int)
    parser.add_argument('--rotate', type=int, default=90)
    parser.add_argument('--count', type=int, default=15)
    parser.add_argument('--output', default='build/gel-detection-qa.png')
    args = parser.parse_args()
    with Image.open(args.image) as source:
        image = source.convert('RGB')
    if args.crop: image = image.crop(tuple(args.crop))
    image = image.rotate(args.rotate, expand=True)
    gray = np.array(image.convert('L'))
    spans = LanesMixin._split_lanes_by_count(
        lane_boundary_signal(gray, args.count), args.count, image.width)
    if spans is None: raise SystemExit('No lane signal found')
    draw = ImageDraw.Draw(image)
    counts, heights = [], []
    for i, (left, right) in enumerate(spans):
        lane = Lane(i, left, right)
        lane.analyze(gray, 11, 6, threshold_pct=40)
        color = ('#ff7676', '#6af2cf', '#ffd36a')[i % 3]
        draw.rectangle((left, 0, right, image.height - 1), outline=color)
        draw.text((left + 2, 2), str(i + 1), fill=color)
        for top, bottom in lane.peak_bounds:
            draw.rectangle((left, top, right, bottom), outline=color)
            heights.append(bottom - top)
        counts.append(len(lane.peaks))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print('Lane widths:', [right - left + 1 for left, right in spans])
    print('Bands per lane:', counts)
    print('Maximum band height:', max(heights, default=0))
    print('Preview:', output.resolve())


if __name__ == '__main__':
    main()
