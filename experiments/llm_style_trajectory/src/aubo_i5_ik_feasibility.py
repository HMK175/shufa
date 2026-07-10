"""Offline AUBO i5 IK feasibility pre-check.

This is a conservative geometry and data-quality dry-run. It does not solve
IK, import AUBO SDK modules, connect to hardware, or send robot commands.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from target_pose_defaults import (
    select_default_target_pose_csv,
    retiming_metadata,
    target_pose_kind,
    target_pose_output_suffix,
)


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CSV = select_default_target_pose_csv()

REQUIRED_FIELDS = [
    "pose_id",
    "t_s",
    "X_m",
    "Y_m",
    "Z_m",
    "qw",
    "qx",
    "qy",
    "qz",
    "pen_down",
    "segment_type",
    "speed_m_s",
]

POINT_FIELDS = [
    "pose_id",
    "X_m",
    "Y_m",
    "Z_m",
    "radius_m",
    "step_m",
    "speed_m_s",
    "time_ok",
    "quaternion_ok",
    "within_envelope",
    "has_nan_or_inf",
    "notes",
]


@dataclass(frozen=True)
class FeasibilityConfig:
    paper_half_width_m: float = 0.060
    paper_half_height_m: float = 0.060
    z_min_m: float = 0.0
    z_max_m: float = 0.008
    max_step_m: float = 0.015
    max_speed_m_s: float = 0.10
    quaternion_tolerance: float = 1e-6
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0
    origin_z_m: float = 0.0
    envelope_min_radius_m: float = 0.0
    envelope_max_radius_m: float = 0.90


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def _is_finite(value: Any) -> bool:
    try:
        return math.isfinite(_float(value))
    except (TypeError, ValueError):
        return False


def _row_has_nonfinite(row: dict[str, Any], fields: Sequence[str]) -> bool:
    return any(not _is_finite(row.get(field)) for field in fields)


def _range(values: Sequence[float]) -> list[float]:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return [0.0, 0.0]
    return [round(min(finite), 6), round(max(finite), 6)]


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = _float(b.get("X_m")) - _float(a.get("X_m"))
    dy = _float(b.get("Y_m")) - _float(a.get("Y_m"))
    dz = _float(b.get("Z_m")) - _float(a.get("Z_m"))
    value = math.sqrt(dx * dx + dy * dy + dz * dz)
    return value if math.isfinite(value) else float("nan")


def _radius(row: dict[str, Any], config: FeasibilityConfig) -> float:
    dx = _float(row.get("X_m")) - config.origin_x_m
    dy = _float(row.get("Y_m")) - config.origin_y_m
    dz = _float(row.get("Z_m")) - config.origin_z_m
    value = math.sqrt(dx * dx + dy * dy + dz * dz)
    return value if math.isfinite(value) else float("nan")


def _quaternion_norm(row: dict[str, Any]) -> float:
    value = math.sqrt(
        _float(row.get("qw")) ** 2
        + _float(row.get("qx")) ** 2
        + _float(row.get("qy")) ** 2
        + _float(row.get("qz")) ** 2
    )
    return value if math.isfinite(value) else float("nan")


def _quaternion_ok(row: dict[str, Any], config: FeasibilityConfig) -> bool:
    norm = _quaternion_norm(row)
    return math.isfinite(norm) and abs(norm - 1.0) <= config.quaternion_tolerance


def _source_xy_values(row: dict[str, Any]) -> tuple[float, float]:
    if "source_X_mm" in row and "source_Y_mm" in row:
        return _float(row.get("source_X_mm")) / 1000.0, _float(row.get("source_Y_mm")) / 1000.0
    return _float(row.get("X_m")), _float(row.get("Y_m"))


def _source_z_value(row: dict[str, Any]) -> float:
    if "source_Z_mm" in row:
        return _float(row.get("source_Z_mm")) / 1000.0
    return _float(row.get("Z_m"))


def _required_fields_present(fieldnames: Sequence[str]) -> tuple[bool, list[str]]:
    missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    return not missing, missing


def _time_monotonic(rows: Sequence[dict[str, Any]]) -> bool:
    times = [_float(row.get("t_s")) for row in rows]
    return all(math.isfinite(value) for value in times) and all(b >= a for a, b in zip(times, times[1:]))


def _max_step(rows: Sequence[dict[str, Any]]) -> float:
    steps = [_distance(a, b) for a, b in zip(rows, rows[1:])]
    finite = [step for step in steps if math.isfinite(step)]
    return max(finite) if finite else 0.0


def _max_speed(rows: Sequence[dict[str, Any]]) -> float:
    speeds = [_float(row.get("speed_m_s")) for row in rows]
    finite = [speed for speed in speeds if math.isfinite(speed)]
    return max(finite) if finite else 0.0


def build_points(rows: Sequence[dict[str, Any]], config: FeasibilityConfig) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    previous_t: float | None = None
    for row in rows:
        radius = _radius(row, config)
        step = _distance(previous, row) if previous is not None else 0.0
        t = _float(row.get("t_s"))
        time_ok = previous_t is None or (math.isfinite(t) and t >= previous_t)
        q_ok = _quaternion_ok(row, config)
        nonfinite = _row_has_nonfinite(row, ["t_s", "X_m", "Y_m", "Z_m", "qw", "qx", "qy", "qz", "speed_m_s"])
        within = (
            math.isfinite(radius)
            and radius >= config.envelope_min_radius_m
            and radius <= config.envelope_max_radius_m
        )
        notes = []
        if not time_ok:
            notes.append("time not monotonic")
        if not q_ok:
            notes.append("quaternion not normalized")
        if nonfinite:
            notes.append("NaN or inf")
        if not within:
            notes.append("outside conservative envelope")
        points.append(
            {
                "pose_id": row.get("pose_id", ""),
                "X_m": _float(row.get("X_m")),
                "Y_m": _float(row.get("Y_m")),
                "Z_m": _float(row.get("Z_m")),
                "radius_m": radius,
                "step_m": step if math.isfinite(step) else 0.0,
                "speed_m_s": _float(row.get("speed_m_s")),
                "time_ok": time_ok,
                "quaternion_ok": q_ok,
                "within_envelope": within,
                "has_nan_or_inf": nonfinite,
                "notes": "; ".join(notes),
            }
        )
        previous = row
        previous_t = t if math.isfinite(t) else previous_t
    return points


def summarize(rows: Sequence[dict[str, Any]], fieldnames: Sequence[str], source_csv: Path | str, config: FeasibilityConfig) -> dict[str, Any]:
    warnings: list[str] = []
    required_ok, missing_fields = _required_fields_present(fieldnames)
    points = build_points(rows, config)

    source_xs: list[float] = []
    source_ys: list[float] = []
    source_zs: list[float] = []
    for row in rows:
        x, y = _source_xy_values(row)
        source_xs.append(x)
        source_ys.append(y)
        source_zs.append(_source_z_value(row))

    xy_ok = all(
        math.isfinite(x)
        and math.isfinite(y)
        and -config.paper_half_width_m <= x <= config.paper_half_width_m
        and -config.paper_half_height_m <= y <= config.paper_half_height_m
        for x, y in zip(source_xs, source_ys)
    )
    z_ok = all(math.isfinite(z) and config.z_min_m <= z <= config.z_max_m for z in source_zs)
    max_step = _max_step(rows)
    max_speed = _max_speed(rows)
    has_nonfinite = any(point["has_nan_or_inf"] for point in points)
    time_ok = _time_monotonic(rows)
    quaternion_ok = all(point["quaternion_ok"] for point in points)
    envelope_ok = all(point["within_envelope"] for point in points)

    if not required_ok:
        warnings.append(f"missing required fields: {', '.join(missing_fields)}")
    if not xy_ok:
        warnings.append("XY source path exceeds configured paper range")
    if not z_ok:
        warnings.append("Z source path exceeds configured expected range")
    if max_step > config.max_step_m:
        warnings.append(f"max step {max_step:.6f}m exceeds limit {config.max_step_m:.6f}m")
    if max_speed > config.max_speed_m_s:
        warnings.append(f"max speed {max_speed:.6f}m/s exceeds limit {config.max_speed_m_s:.6f}m/s")
    if not time_ok:
        warnings.append("target pose time is not monotonic")
    if not quaternion_ok:
        warnings.append("target pose quaternion is not normalized")
    if has_nonfinite:
        warnings.append("target pose rows contain NaN or inf")
    if not envelope_ok:
        warnings.append("target pose is outside conservative reachability envelope")

    radii = [point["radius_m"] for point in points]
    return {
        "point_count": len(rows),
        "source_csv": str(source_csv),
        "source_target_pose_csv": str(source_csv),
        "source_target_pose_kind": target_pose_kind(source_csv),
        **retiming_metadata(source_csv),
        "xy_range_m": {"x": _range(source_xs), "y": _range(source_ys)},
        "z_range_m": _range(source_zs),
        "radius_range_m": _range(radii),
        "max_step_m": round(max_step, 6),
        "max_speed_m_s": round(max_speed, 6),
        "time_monotonic": time_ok,
        "quaternion_normalized": quaternion_ok,
        "has_nan_or_inf": has_nonfinite,
        "required_fields_present": required_ok,
        "missing_fields": missing_fields,
        "within_conservative_envelope": envelope_ok,
        "recommended_for_real_ik_check": not warnings,
        "warnings": warnings,
        "scope": "AUBO i5 IK feasibility dry-run only; not real IK, not SDK, not robot control",
        "envelope_hint": {
            "origin_m": [config.origin_x_m, config.origin_y_m, config.origin_z_m],
            "min_radius_m": config.envelope_min_radius_m,
            "max_radius_m": config.envelope_max_radius_m,
            "note": "Conservative radius envelope only; not joint-level IK, collision, singularity, or joint-limit checking.",
        },
    }


def _write_points(points: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=POINT_FIELDS)
        writer.writeheader()
        for point in points:
            writer.writerow(
                {
                    field: (
                        f"{_float(point[field]):.9f}"
                        if field in {"X_m", "Y_m", "Z_m", "radius_m", "step_m", "speed_m_s"}
                        else point.get(field, "")
                    )
                    for field in POINT_FIELDS
                }
            )


def _report_text(summary: dict[str, Any], points_csv: Path, config: FeasibilityConfig) -> str:
    lines = [
        "# AUBO i5 IK Feasibility Dry-Run Report",
        "",
        "This report is an IK feasibility dry-run. It is not real IK, does not connect to a real robot arm, does not import or call the AUBO SDK, and does not send robot control commands.",
        "",
        "It also does not check joint limits, collisions, singular configurations, dynamics, or calibrated AUBO i5 reachability. The radius envelope is only a conservative pre-check hint.",
        "",
        "## Outputs",
        "",
        f"- points_csv: `{points_csv}`",
        f"- source_target_pose_csv: `{summary.get('source_target_pose_csv')}`",
        f"- source_retiming_summary: `{summary.get('source_retiming_summary')}`",
        f"- source_retimming_summary: `{summary.get('source_retimming_summary')}`",
        f"- source_motion_continuity_after_retiming: `{summary.get('source_motion_continuity_after_retiming')}`",
        "",
        "When `source_target_pose_kind` is `smoothed`, this report is based on target poses that already passed the conservative motion-continuity after-retiming gate.",
        "",
        "## Config",
        "",
        f"- paper_half_width_m: `{config.paper_half_width_m}`",
        f"- paper_half_height_m: `{config.paper_half_height_m}`",
        f"- z_range_m: `{config.z_min_m}..{config.z_max_m}`",
        f"- max_step_m: `{config.max_step_m}`",
        f"- max_speed_m_s: `{config.max_speed_m_s}`",
        f"- conservative_radius_envelope_m: `{config.envelope_min_radius_m}..{config.envelope_max_radius_m}`",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for key in [
        "point_count",
        "source_csv",
        "source_target_pose_csv",
        "source_target_pose_kind",
        "source_retiming_summary",
        "source_retimming_summary",
        "source_motion_continuity_after_retiming",
        "xy_range_m",
        "z_range_m",
        "radius_range_m",
        "max_step_m",
        "max_speed_m_s",
        "time_monotonic",
        "quaternion_normalized",
        "has_nan_or_inf",
        "required_fields_present",
        "within_conservative_envelope",
        "recommended_for_real_ik_check",
        "warnings",
        "scope",
    ]:
        value: Any = summary.get(key, "")
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "Next step before true IK: confirm TCP, base coordinate frame, paper pose, robot IP, emergency stop, workspace safety boundary, tool fixture, speed limits, and on-site supervision.",
            "",
        ]
    )
    return "\n".join(lines)


def process_csv(csv_path: Path | str, config: FeasibilityConfig | None = None, out_dir: Path | str | None = None) -> dict[str, Any]:
    source = Path(csv_path)
    cfg = config or FeasibilityConfig()
    rows, fieldnames = _read_csv(source)
    target_dir = Path(out_dir) if out_dir else source.parent
    suffix = target_pose_output_suffix(source)
    summary_json = target_dir / f"aubo_i5_ik_feasibility{suffix}_summary.json"
    report_md = target_dir / f"aubo_i5_ik_feasibility{suffix}_report.md"
    points_csv = target_dir / f"aubo_i5_ik_feasibility{suffix}_points.csv"
    points = build_points(rows, cfg)
    summary = summarize(rows, fieldnames, source, cfg)
    _write_points(points, points_csv)
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_report_text(summary, points_csv, cfg), encoding="utf-8")
    return {
        "source_csv": str(source),
        "summary_json": str(summary_json),
        "report_md": str(report_md),
        "points_csv": str(points_csv),
        "summary": summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an offline AUBO i5 IK feasibility pre-check")
    parser.add_argument(
        "--csv",
        default=None,
        help="robot_target_poses.csv path. If omitted, smoothed target poses are preferred when present.",
    )
    parser.add_argument("--out-dir", default=None, help="Output directory; defaults to source CSV directory")
    parser.add_argument("--paper-half-width-m", type=float, default=0.060)
    parser.add_argument("--paper-half-height-m", type=float, default=0.060)
    parser.add_argument("--z-min-m", type=float, default=0.0)
    parser.add_argument("--z-max-m", type=float, default=0.008)
    parser.add_argument("--max-step-m", type=float, default=0.015)
    parser.add_argument("--max-speed-m-s", type=float, default=0.10)
    parser.add_argument("--origin-x-m", type=float, default=0.0)
    parser.add_argument("--origin-y-m", type=float, default=0.0)
    parser.add_argument("--origin-z-m", type=float, default=0.0)
    parser.add_argument("--envelope-min-radius-m", type=float, default=0.0)
    parser.add_argument("--envelope-max-radius-m", type=float, default=0.90)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = FeasibilityConfig(
        paper_half_width_m=args.paper_half_width_m,
        paper_half_height_m=args.paper_half_height_m,
        z_min_m=args.z_min_m,
        z_max_m=args.z_max_m,
        max_step_m=args.max_step_m,
        max_speed_m_s=args.max_speed_m_s,
        origin_x_m=args.origin_x_m,
        origin_y_m=args.origin_y_m,
        origin_z_m=args.origin_z_m,
        envelope_min_radius_m=args.envelope_min_radius_m,
        envelope_max_radius_m=args.envelope_max_radius_m,
    )
    csv_path = args.csv if args.csv else select_default_target_pose_csv()
    result = process_csv(csv_path, config=config, out_dir=args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
