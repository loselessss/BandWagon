"""Deterministic synthetic QA data, NOT experimental observations.

Run: python -m scripts.generate_composite_qa
"""
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


def fixture():
    width, height = 320, 240
    ys = np.arange(height)[:, None]
    signal = np.zeros((height, width), dtype=float)
    lanes = []
    for i, (left, strength) in enumerate(((55, 60), (140, 120), (225, 180))):
        centers = [65, 120, 180]
        for center in centers:
            signal[:, left:left + 31] += strength * np.exp(-0.5 * ((ys - center) / 4) ** 2)
        lanes.append({"x1": left, "x2": left + 30, "peaks_y": centers, "amplitude": strength})
    gray = np.clip(np.rint(12 + signal), 0, 255).astype(np.uint8)
    visible = Image.new("RGB", (width, height), (190, 175, 160))
    draw = ImageDraw.Draw(visible)
    draw.rectangle((0, 0, width - 1, height - 1), outline="red", width=3)
    draw.text((4, 4), "SYNTHETIC QA - NOT EXPERIMENTAL", fill="black")
    # Deliberate visible-only distraction: must NEVER become a UV band.
    draw.rectangle((10, 90, 309, 98), fill="black")
    for i, lane in enumerate(lanes):
        draw.rectangle((lane["x1"], 22, lane["x2"], 33), fill="navy")
        draw.text((lane["x1"], 38), f"L{i + 1}", fill="black")
    return visible, Image.fromarray(gray).convert("RGB"), {
        "synthetic": True, "size": [width, height], "lanes": lanes,
        "identity_corners": [[0, 0], [319, 0], [319, 239], [0, 239]],
        "perspective_corners": [[55, 30], [395, 55], [370, 295], [35, 275]],
        "visible_only_artifact_y": [90, 98],
    }


def main():
    output = Path(__file__).resolve().parents[1] / "qa" / "western_blot"
    output.mkdir(parents=True, exist_ok=True)
    visible, uv, truth = fixture()
    visible.save(output / "01_visible.png")
    uv.save(output / "02_uv_bright.png")
    Image.fromarray(255 - np.array(uv)).save(output / "03_uv_dark.png")
    matrix = cv2.getPerspectiveTransform(np.float32(truth["identity_corners"]), np.float32(truth["perspective_corners"]))
    transformed = cv2.warpPerspective(np.array(uv), matrix, (440, 330), borderValue=(12, 12, 12))
    Image.fromarray(transformed).save(output / "04_uv_perspective.png")
    annotated = Image.fromarray(transformed)
    draw = ImageDraw.Draw(annotated)
    for index, (x, y) in enumerate(truth["perspective_corners"], 1):
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), outline="red", width=2)
        draw.text((x + 7, y), str(index), fill="red")
    annotated.save(output / "05_corner_guide_NOT_FOR_ANALYSIS.png")
    (output / "ground_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
