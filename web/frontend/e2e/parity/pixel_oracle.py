"""Exact RGBA screenshot comparator used by the Playwright parity gate.

Artifacts are intentionally written to the caller-selected external output
directory. The repository stores the oracle, never screenshots or reports.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


def compare(expected_path: Path, actual_path: Path, diff_path: Path | None) -> dict:
    expected = Image.open(expected_path).convert("RGBA")
    actual = Image.open(actual_path).convert("RGBA")
    if expected.size != actual.size:
        return {
            "expected": str(expected_path),
            "actual": str(actual_path),
            "expected_size": expected.size,
            "actual_size": actual.size,
            "differing_pixels": expected.width * expected.height,
            "total_pixels": expected.width * expected.height,
            "difference_ratio": 1.0,
            "bounding_box": [0, 0, expected.width, expected.height],
            "error": "image dimensions differ",
        }

    difference = ImageChops.difference(expected, actual)
    # RGBA getbbox can ignore RGB changes where the alpha difference is zero.
    rgb_difference = difference.convert("RGB")
    bbox = rgb_difference.getbbox()
    expected_pixels = expected.load()
    actual_pixels = actual.load()
    differing_pixels = 0
    maximum_channel_delta = 0
    difference_samples = []
    for y in range(expected.height):
        for x in range(expected.width):
            expected_pixel = expected_pixels[x, y]
            actual_pixel = actual_pixels[x, y]
            deltas = tuple(abs(left - right) for left, right in zip(expected_pixel, actual_pixel))
            pixel_delta = max(deltas)
            if pixel_delta == 0:
                continue
            differing_pixels += 1
            maximum_channel_delta = max(maximum_channel_delta, pixel_delta)
            if len(difference_samples) < 100:
                difference_samples.append({
                    "x": x,
                    "y": y,
                    "expected": expected_pixel,
                    "actual": actual_pixel,
                    "maximum_channel_delta": pixel_delta,
                })
    total_pixels = expected.width * expected.height

    if diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        # Black is identical; saturated magenta marks any changed pixel. This
        # makes sparse one-pixel regressions obvious in an external report.
        marker = Image.new("RGBA", expected.size, (0, 0, 0, 255))
        marker.putdata([
            (255, 0, 255, 255) if pixel != (0, 0, 0) else (0, 0, 0, 255)
            for pixel in rgb_difference.getdata()
        ])
        marker.save(diff_path)

    return {
        "expected": str(expected_path),
        "actual": str(actual_path),
        "expected_size": expected.size,
        "actual_size": actual.size,
        "differing_pixels": differing_pixels,
        "total_pixels": total_pixels,
        "difference_ratio": differing_pixels / total_pixels if total_pixels else 0,
        "bounding_box": list(bbox) if bbox else None,
        "maximum_channel_delta": maximum_channel_delta,
        "difference_samples": difference_samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--diff", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = compare(args.expected, args.actual, args.diff)
    encoded = json.dumps(result, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
