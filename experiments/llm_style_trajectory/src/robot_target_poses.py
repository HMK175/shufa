"""Convert resampled workspace paths into robot end-effector target poses.

This module deliberately stops before IK or robot control. It produces a
generic target-pose sequence that can later feed an AUBO i5 dry-run adapter.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CSV = (
    EXP_DIR
    / "outputs"
    / "batch_20260613_154131"
    / "u5c71_xingkai_20260613_154132_009898"
    / "robot_workspace_trajectory_resampled.csv"
)

TARGET_POSE_FIELDS = [
    "pose_id",
    "t_s",
    "X_m",
    "Y_m",
    "Z_m",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "qw",
    "qx",
    "qy",
    "qz",
    "pen_down",
    "segment_type",
    "speed_m_s",
    "source_X_mm",
    "source_Y_mm",
    "source_Z_mm",
]


@dataclass(frozen=True)
class TargetPoseConfig:
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0
    origin_z_m: float = 0.0
    roll_deg: float = 180.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    paper_size_mm: float = 120.0
    z_min_mm: float = 0.0
    z_max_mm: float = 8.0
    max_step_m: float = 0.015
    quaternion_tolerance: float = 1e-6


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def rpy_to_quaternion(roll_deg: float, pitch_deg: float, yaw_deg: float) -> tuple[float, float, float, float]:
    """Return (qw, qx, qy, qz) for roll/pitch/yaw in degrees."""

    roll = math.radians(float(roll_deg))
    pitch = math.radians(float(pitch_deg))
    yaw = math.radians(float(yaw_deg))
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)

    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if norm <= 0:
        return 1.0, 0.0, 0.0, 0.0
    return qw / norm, qx / norm, qy / norm, qz / norm


def _distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = _float(b["X_m"]) - _float(a["X_m"])
    dy = _float(b["Y_m"]) - _float(a["Y_m"])
    dz = _float(b["Z_m"]) - _float(a["Z_m"])
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _row_has_time(row: dict[str, Any]) -> bool:
    return "t_s" in row and row.get("t_s") not in {None, ""}


def build_target_pose_rows(rows: Sequence[dict[str, Any]], config: TargetPoseConfig) -> list[dict[str, Any]]:
    q = rpy_to_quaternion(config.roll_deg, config.pitch_deg, config.yaw_deg)
    target_rows: list[dict[str, Any]] = []
    has_time = all(_row_has_time(row) for row in rows) if rows else False
    current_t = 0.0

    for idx, row in enumerate(rows):
        x_mm = _float(row.get("X_mm"))
        y_mm = _float(row.get("Y_mm"))
        z_mm = _float(row.get("Z_mm"))
        speed_m_s = _float(row.get("speed_m_s")) or (_float(row.get("speed_mm_s")) / 1000.0)
        target = {
            "pose_id": idx,
            "t_s": 0.0,
            "X_m": config.origin_x_m + x_mm / 1000.0,
            "Y_m": config.origin_y_m + y_mm / 1000.0,
            "Z_m": config.origin_z_m + z_mm / 1000.0,
            "roll_deg": config.roll_deg,
            "pitch_deg": config.pitch_deg,
            "yaw_deg": config.yaw_deg,
            "qw": q[0],
            "qx": q[1],
            "qy": q[2],
            "qz": q[3],
            "pen_down": _int(row.get("pen_down")),
            "segment_type": str(row.get("segment_type", "")),
            "speed_m_s": speed_m_s,
            "source_X_mm": x_mm,
            "source_Y_mm": y_mm,
            "source_Z_mm": z_mm,
        }
        if has_time:
            target["t_s"] = _float(row.get("t_s"))
        elif idx == 0:
            target["t_s"] = 0.0
        else:
            step = _distance_m(target_rows[-1], target)
            speed = max(speed_m_s or _float(target_rows[-1].get("speed_m_s")), 1e-9)
            current_t += step / speed
            target["t_s"] = current_t
        target_rows.append(target)
    return target_rows


def _path_length_m(rows: Sequence[dict[str, Any]]) -> float:
    return sum(_distance_m(a, b) for a, b in zip(rows, rows[1:]))


def _max_step_m(rows: Sequence[dict[str, Any]]) -> float:
    if len(rows) < 2:
        return 0.0
    return max(_distance_m(a, b) for a, b in zip(rows, rows[1:]))


def _has_nonfinite(rows: Sequence[dict[str, Any]]) -> bool:
    numeric_fields = ["t_s", "X_m", "Y_m", "Z_m", "qw", "qx", "qy", "qz", "speed_m_s"]
    for row in rows:
        for field in numeric_fields:
            value = _float(row.get(field))
            if not math.isfinite(value):
                return True
    return False


def _time_monotonic(rows: Sequence[dict[str, Any]]) -> bool:
    times = [_float(row.get("t_s")) for row in rows]
    return all(b >= a for a, b in zip(times, times[1:]))


def _quaternions_normalized(rows: Sequence[dict[str, Any]], tolerance: float) -> bool:
    for row in rows:
        norm = math.sqrt(
            _float(row.get("qw")) ** 2
            + _float(row.get("qx")) ** 2
            + _float(row.get("qy")) ** 2
            + _float(row.get("qz")) ** 2
        )
        if abs(norm - 1.0) > tolerance:
            return False
    return True


def summarize_target_poses(rows: Sequence[dict[str, Any]], config: TargetPoseConfig) -> dict[str, Any]:
    warnings: list[str] = []
    half = config.paper_size_mm / 2.0
    if rows:
        xs_mm = [_float(row["source_X_mm"]) for row in rows]
        ys_mm = [_float(row["source_Y_mm"]) for row in rows]
        zs_mm = [_float(row["source_Z_mm"]) for row in rows]
    else:
        xs_mm = ys_mm = zs_mm = [0.0]

    xy_in_bounds = min(xs_mm) >= -half and max(xs_mm) <= half and min(ys_mm) >= -half and max(ys_mm) <= half
    z_in_bounds = min(zs_mm) >= config.z_min_mm and max(zs_mm) <= config.z_max_mm
    max_step = _max_step_m(rows)
    nonfinite = _has_nonfinite(rows)
    time_monotonic = _time_monotonic(rows)
    q_ok = _quaternions_normalized(rows, config.quaternion_tolerance)

    if not xy_in_bounds:
        warnings.append(f"XY source path exceeds paper bounds +/-{half:g}mm")
    if not z_in_bounds:
        warnings.append(f"Z source path exceeds expected range {config.z_min_mm:g}..{config.z_max_mm:g}mm")
    if max_step > config.max_step_m:
        warnings.append(f"max_step_m {max_step:.6f} exceeds limit {config.max_step_m:.6f}")
    if nonfinite:
        warnings.append("target pose rows contain NaN or inf")
    if not time_monotonic:
        warnings.append("target pose time is not monotonic")
    if not q_ok:
        warnings.append("target pose quaternion is not normalized")

    speeds = [_float(row.get("speed_m_s")) for row in rows]
    duration = _float(rows[-1]["t_s"]) if rows else 0.0
    return {
        "point_count": len(rows),
        "duration_s": round(duration, 6),
        "path_length_m": round(_path_length_m(rows), 6),
        "max_step_m": round(max_step, 6),
        "max_speed_m_s": round(max(speeds), 6) if speeds else 0.0,
        "segment_counts": dict(sorted(Counter(str(row.get("segment_type", "")) for row in rows).items())),
        "source_x_mm_range": [round(min(xs_mm), 6), round(max(xs_mm), 6)],
        "source_y_mm_range": [round(min(ys_mm), 6), round(max(ys_mm), 6)],
        "source_z_mm_range": [round(min(zs_mm), 6), round(max(zs_mm), 6)],
        "xy_within_paper_bounds": xy_in_bounds,
        "z_within_expected_range": z_in_bounds,
        "has_nan_or_inf": nonfinite,
        "time_monotonic": time_monotonic,
        "quaternion_normalized": q_ok,
        "recommended_for_ik_dry_run": not warnings,
        "warnings": warnings,
        "scope": "target pose only; no IK, no robot command, no real AUBO i5 control",
    }


def _write_target_pose_csv(rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TARGET_POSE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: (
                        f"{_float(row[field]):.9f}"
                        if field not in {"pose_id", "pen_down", "segment_type"}
                        else row.get(field, "")
                    )
                    for field in TARGET_POSE_FIELDS
                }
            )


def _report_markdown(csv_path: Path, out_csv: Path, summary: dict[str, Any], config: TargetPoseConfig) -> str:
    lines = [
        "# Robot Target Pose Report",
        "",
        "Scope: target pose only; no IK, no robot command, no real AUBO i5 control.",
        "",
        "## Inputs and Outputs",
        "",
        f"- source_csv: `{csv_path}`",
        f"- robot_target_poses_csv: `{out_csv}`",
        "",
        "## Pose Convention",
        "",
        f"- origin_m: `({config.origin_x_m}, {config.origin_y_m}, {config.origin_z_m})`",
        "- coordinate_mapping: `X_m = X_mm / 1000 + origin_x_m`; same for Y/Z",
        f"- fixed_rpy_deg: `({config.roll_deg}, {config.pitch_deg}, {config.yaw_deg})`",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for key in [
        "point_count",
        "duration_s",
        "path_length_m",
        "max_step_m",
        "max_speed_m_s",
        "segment_counts",
        "source_x_mm_range",
        "source_y_mm_range",
        "source_z_mm_range",
        "xy_within_paper_bounds",
        "z_within_expected_range",
        "has_nan_or_inf",
        "time_monotonic",
        "quaternion_normalized",
        "recommended_for_ik_dry_run",
        "warnings",
    ]:
        value: Any = summary.get(key, "")
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "This file is an IK-preparation artifact. Before any AUBO i5 real-machine run, IP, TCP, tool, fixture, emergency stop, and safety limits must be confirmed again.",
            "",
        ]
    )
    return "\n".join(lines)


def process_csv(csv_path: Path | str, config: TargetPoseConfig | None = None, out_dir: Path | str | None = None) -> dict[str, Any]:
    source = Path(csv_path)
    cfg = config or TargetPoseConfig()
    rows = _read_csv(source)
    target_rows = build_target_pose_rows(rows, cfg)
    target_dir = Path(out_dir) if out_dir else source.parent
    out_csv = target_dir / "robot_target_poses.csv"
    report_md = target_dir / "robot_target_pose_report.md"
    summary_json = target_dir / "robot_target_pose_summary.json"
    summary = summarize_target_poses(target_rows, cfg)
    _write_target_pose_csv(target_rows, out_csv)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_report_markdown(source, out_csv, summary, cfg), encoding="utf-8")
    return {
        "source_csv": str(source),
        "target_pose_csv": str(out_csv),
        "report_md": str(report_md),
        "summary_json": str(summary_json),
        "summary": summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert workspace CSV into robot end-effector target poses")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="robot_workspace_trajectory_resampled.csv path")
    parser.add_argument("--out-dir", default=None, help="Output directory; defaults to the source CSV directory")
    parser.add_argument("--origin-x-m", type=float, default=0.0)
    parser.add_argument("--origin-y-m", type=float, default=0.0)
    parser.add_argument("--origin-z-m", type=float, default=0.0)
    parser.add_argument("--roll-deg", type=float, default=180.0)
    parser.add_argument("--pitch-deg", type=float, default=0.0)
    parser.add_argument("--yaw-deg", type=float, default=0.0)
    parser.add_argument("--paper-size-mm", type=float, default=120.0)
    parser.add_argument("--z-min-mm", type=float, default=0.0)
    parser.add_argument("--z-max-mm", type=float, default=8.0)
    parser.add_argument("--max-step-m", type=float, default=0.015)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = TargetPoseConfig(
        origin_x_m=args.origin_x_m,
        origin_y_m=args.origin_y_m,
        origin_z_m=args.origin_z_m,
        roll_deg=args.roll_deg,
        pitch_deg=args.pitch_deg,
        yaw_deg=args.yaw_deg,
        paper_size_mm=args.paper_size_mm,
        z_min_mm=args.z_min_mm,
        z_max_mm=args.z_max_mm,
        max_step_m=args.max_step_m,
    )
    result = process_csv(args.csv, config=config, out_dir=args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
