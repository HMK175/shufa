"""Inspect CalliRewrite seq_extract npz files and draft-convert them to CSV.

This is a probe utility only. It does not run CalliRewrite or touch the main
trajectory pipeline.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np


def _as_round_lengths(value: np.ndarray) -> List[int]:
    if value.ndim == 0:
        return [int(value)]
    return [int(v) for v in value.tolist()]


def _sample_quadratic(
    start_xy: np.ndarray,
    control_xy: np.ndarray,
    end_xy: np.ndarray,
    samples: int,
) -> Iterable[Tuple[float, float]]:
    ts = np.linspace(0.0, 1.0, max(2, samples), dtype=np.float32)
    for t in ts:
        point = ((1.0 - t) ** 2) * start_xy + 2.0 * (1.0 - t) * t * control_xy + (t**2) * end_xy
        yield float(point[0]), float(point[1])


def decode_points(npz_path: Path, curve_samples: int) -> List[Tuple[float, float]]:
    data = np.load(npz_path, allow_pickle=True, encoding="latin1")
    required = {"strokes_data", "init_cursors", "image_size", "round_length", "init_width"}
    missing = required.difference(data.files)
    if missing:
        raise ValueError(f"Missing required CalliRewrite fields: {sorted(missing)}")

    strokes_data = np.asarray(data["strokes_data"])
    init_cursors = np.asarray(data["init_cursors"])
    image_size = float(np.asarray(data["image_size"]).item())
    round_lengths = _as_round_lengths(np.asarray(data["round_length"]))

    if init_cursors.ndim == 1:
        init_cursors = init_cursors.reshape(1, -1)
    if init_cursors.ndim >= 3:
        init_cursors = init_cursors.reshape(-1, init_cursors.shape[-1])

    points: List[Tuple[float, float]] = []
    cursor_idx = 0
    stroke_base = 0

    for round_length in round_lengths:
        if cursor_idx >= len(init_cursors):
            break
        cursor_xy = init_cursors[cursor_idx].astype(np.float32) * image_size
        cursor_idx += 1

        if points:
            points.append((float("nan"), float("nan")))
        points.append((float(cursor_xy[1]), float(cursor_xy[0])))

        prev_window_size = 128.0
        prev_scaling = 1.0

        for offset in range(round_length):
            stroke_idx = stroke_base + offset
            if stroke_idx >= len(strokes_data):
                break
            row = np.asarray(strokes_data[stroke_idx], dtype=np.float32)
            if row.size < 7:
                raise ValueError(f"strokes_data row {stroke_idx} has {row.size} values, expected >= 7")

            pen_state = int(row[0])
            x1y1 = row[1:3]
            x2y2 = row[3:5]
            next_scaling = float(row[6])

            curr_window_size = max(32.0, min(prev_scaling * prev_window_size, image_size))
            end_offset_xy = np.array([x2y2[1], x2y2[0]], dtype=np.float32) * (curr_window_size / 2.0)
            end_xy = np.clip(cursor_xy + end_offset_xy, 0.0, image_size - 1.0)

            if pen_state == 0:
                control_xy = cursor_xy + np.array([x1y1[1], x1y1[0]], dtype=np.float32) * (curr_window_size / 2.0)
                for x, y in _sample_quadratic(cursor_xy, control_xy, end_xy, curve_samples):
                    points.append((y, x))
            else:
                if points and not np.isnan(points[-1][0]):
                    points.append((float("nan"), float("nan")))
                points.append((float(end_xy[1]), float(end_xy[0])))

            cursor_xy = end_xy
            prev_scaling = next_scaling
            prev_window_size = curr_window_size

        stroke_base += round_length

    return points


def inspect_npz(npz_path: Path) -> str:
    data = np.load(npz_path, allow_pickle=True, encoding="latin1")
    lines = [f"file: {npz_path}", "fields:"]
    for field in data.files:
        value = data[field]
        preview = np.asarray(value).reshape(-1)[:8]
        lines.append(f"- {field}: shape={value.shape}, dtype={value.dtype}, preview={preview.tolist()}")
    return "\n".join(lines)


def write_csv(points: Sequence[Tuple[float, float]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["y", "x"])
        for y, x in points:
            if np.isnan(y) or np.isnan(x):
                writer.writerow(["nan", "nan"])
            else:
                writer.writerow([f"{y:.3f}", f"{x:.3f}"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("npz", type=Path, help="CalliRewrite seq_extract .npz file")
    parser.add_argument("--out", type=Path, default=None, help="Optional output CSV path")
    parser.add_argument("--samples", type=int, default=8, help="Samples per quadratic segment")
    args = parser.parse_args()

    print(inspect_npz(args.npz))
    points = decode_points(args.npz, args.samples)
    print(f"decoded_points: {len(points)}")
    print(f"first_points: {points[:10]}")

    if args.out:
        write_csv(points, args.out)
        print(f"wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
