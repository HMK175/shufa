"""Offline motion continuity checks for workspace and target-pose CSV files.

This module is a dry-run gate only. It does not solve IK, connect to a robot,
load a vendor SDK, or send motion commands.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CSV = (
    EXP_DIR
    / "outputs"
    / "batch_20260613_154131"
    / "u5c71_xingkai_20260613_154132_009898"
    / "robot_target_poses.csv"
)

POINT_FIELDS = [
    "point_id",
    "t_s",
    "dt_s",
    "X_m",
    "Y_m",
    "Z_m",
    "step_3d_m",
    "speed_m_s",
    "speed_jump_m_s",
    "accel_m_s2",
    "jerk_m_s3",
    "quaternion_norm",
    "segment_type",
    "speed_over_limit",
    "accel_over_limit",
    "jerk_over_limit",
]


@dataclass(frozen=True)
class MotionThresholds:
    max_speed_m_s: float = 0.10
    max_accel_m_s2: float = 0.50
    max_jerk_m_s3: float = 5.0
    max_speed_jump_m_s: float = 0.05
    quaternion_tolerance: float = 1e-6


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def _float(value: Any, default: float = math.nan) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


def _first_present(row: dict[str, Any], names: Sequence[str], default: Any = "") -> Any:
    for name in names:
        if name in row and row.get(name) not in {None, ""}:
            return row.get(name)
    return default


def detect_input_kind(fieldnames: Sequence[str], requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    fields = set(fieldnames)
    if {"X_m", "Y_m", "Z_m"}.issubset(fields):
        return "target_pose"
    if {"X_mm", "Y_mm", "Z_mm"}.issubset(fields) or {"x_mm", "y_mm", "z_mm"}.issubset(fields):
        return "workspace"
    return "unknown"


def _target_required_fields_present(fieldnames: Sequence[str]) -> tuple[bool, list[str]]:
    fields = set(fieldnames)
    missing = []
    if not ({"t_s"} & fields or {"t"} & fields or {"time"} & fields):
        missing.append("t_s|t|time")
    for field in ["X_m", "Y_m", "Z_m", "qw", "qx", "qy", "qz", "segment_type"]:
        if field not in fields:
            missing.append(field)
    return not missing, missing


def _workspace_required_fields_present(fieldnames: Sequence[str]) -> tuple[bool, list[str]]:
    fields = set(fieldnames)
    missing = []
    has_xyz_upper = {"X_mm", "Y_mm", "Z_mm"}.issubset(fields)
    has_xyz_lower = {"x_mm", "y_mm", "z_mm"}.issubset(fields)
    if not (has_xyz_upper or has_xyz_lower):
        missing.append("X_mm/Y_mm/Z_mm")
    if "segment_type" not in fields:
        missing.append("segment_type")
    if not ({"t_s", "t", "time"} & fields or "speed_mm_s" in fields or "speed_m_s" in fields):
        missing.append("t_s|t|time or speed_mm_s")
    return not missing, missing


def _distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = b["X_m"] - a["X_m"]
    dy = b["Y_m"] - a["Y_m"]
    dz = b["Z_m"] - a["Z_m"]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _quaternion_norm(row: dict[str, Any]) -> float:
    return math.sqrt(row["qw"] ** 2 + row["qx"] ** 2 + row["qy"] ** 2 + row["qz"] ** 2)


def _normalize_target_rows(rows: Sequence[dict[str, str]]) -> tuple[list[dict[str, Any]], str]:
    normalized = []
    for idx, row in enumerate(rows):
        normalized.append(
            {
                "point_id": int(_float(row.get("pose_id"), idx)),
                "t_s": _float(_first_present(row, ["t_s", "t", "time"])),
                "X_m": _float(row.get("X_m")),
                "Y_m": _float(row.get("Y_m")),
                "Z_m": _float(row.get("Z_m")),
                "qw": _float(row.get("qw")),
                "qx": _float(row.get("qx")),
                "qy": _float(row.get("qy")),
                "qz": _float(row.get("qz")),
                "segment_type": str(row.get("segment_type", "")),
                "declared_speed_m_s": _float(row.get("speed_m_s"), 0.0),
            }
        )
    return normalized, "provided"


def _normalize_workspace_rows(rows: Sequence[dict[str, str]]) -> tuple[list[dict[str, Any]], str]:
    normalized: list[dict[str, Any]] = []
    has_time = any(_first_present(row, ["t_s", "t", "time"], "") != "" for row in rows)
    time_source = "provided" if has_time else "derived_from_speed"
    current_t = 0.0
    for idx, row in enumerate(rows):
        point = {
            "point_id": int(_float(row.get("point_id"), idx)),
            "t_s": _float(_first_present(row, ["t_s", "t", "time"])) if has_time else current_t,
            "X_m": _float(_first_present(row, ["X_mm", "x_mm"])) / 1000.0,
            "Y_m": _float(_first_present(row, ["Y_mm", "y_mm"])) / 1000.0,
            "Z_m": _float(_first_present(row, ["Z_mm", "z_mm"])) / 1000.0,
            "qw": 0.0,
            "qx": 1.0,
            "qy": 0.0,
            "qz": 0.0,
            "segment_type": str(row.get("segment_type", "")),
            "declared_speed_m_s": _float(row.get("speed_m_s"), 0.0) or (_float(row.get("speed_mm_s"), 0.0) / 1000.0),
        }
        if not has_time and normalized:
            speed = max(point["declared_speed_m_s"] or normalized[-1]["declared_speed_m_s"], 1e-9)
            current_t += _distance_m(normalized[-1], point) / speed
            point["t_s"] = current_t
        normalized.append(point)
    return normalized, time_source


def _point_metrics(rows: Sequence[dict[str, Any]], thresholds: MotionThresholds) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    previous_speed = 0.0
    previous_accel = 0.0
    for idx, row in enumerate(rows):
        if idx == 0:
            dt = 0.0
            step = 0.0
            speed = 0.0
            speed_jump = 0.0
            accel = 0.0
            jerk = 0.0
        else:
            prev = rows[idx - 1]
            dt = row["t_s"] - prev["t_s"]
            step = _distance_m(prev, row)
            if dt > 0:
                speed = step / dt
                speed_jump = abs(speed - previous_speed)
                accel = (speed - previous_speed) / dt
                jerk = (accel - previous_accel) / dt
            elif step <= 1e-12:
                speed = previous_speed
                speed_jump = 0.0
                accel = 0.0
                jerk = 0.0
            else:
                speed = math.inf
                speed_jump = math.inf
                accel = math.inf
                jerk = math.inf
        q_norm = _quaternion_norm(row)
        item = {
            "point_id": row["point_id"],
            "t_s": row["t_s"],
            "dt_s": dt,
            "X_m": row["X_m"],
            "Y_m": row["Y_m"],
            "Z_m": row["Z_m"],
            "step_3d_m": step,
            "speed_m_s": speed,
            "speed_jump_m_s": speed_jump,
            "accel_m_s2": accel,
            "jerk_m_s3": jerk,
            "quaternion_norm": q_norm,
            "segment_type": row["segment_type"],
            "speed_over_limit": speed > thresholds.max_speed_m_s,
            "accel_over_limit": abs(accel) > thresholds.max_accel_m_s2,
            "jerk_over_limit": abs(jerk) > thresholds.max_jerk_m_s3,
        }
        metrics.append(item)
        previous_speed = speed if _finite(speed) else previous_speed
        previous_accel = accel if _finite(accel) else previous_accel
    return metrics


def _max_abs(values: Sequence[float]) -> float:
    finite = [abs(value) for value in values if _finite(value)]
    return max(finite) if finite else math.inf if values else 0.0


def _range(values: Sequence[float]) -> list[float]:
    finite = [value for value in values if _finite(value)]
    if not finite:
        return [math.nan, math.nan]
    return [round(min(finite), 9), round(max(finite), 9)]


def _segment_stats(points: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in points:
        grouped[str(row.get("segment_type", ""))].append(row)
    stats = {}
    for segment_type, rows in grouped.items():
        stats[segment_type] = {
            "point_count": len(rows),
            "max_speed_m_s": round(_max_abs([row["speed_m_s"] for row in rows]), 9),
            "max_accel_m_s2": round(_max_abs([row["accel_m_s2"] for row in rows]), 9),
            "max_jerk_m_s3": round(_max_abs([row["jerk_m_s3"] for row in rows]), 9),
        }
    return dict(sorted(stats.items()))


def summarize_motion(
    rows: Sequence[dict[str, Any]],
    points: Sequence[dict[str, Any]],
    *,
    csv_path: Path,
    input_kind: str,
    required_fields_present: bool,
    missing_fields: Sequence[str],
    time_source: str,
    thresholds: MotionThresholds,
) -> dict[str, Any]:
    failure_reasons: list[str] = []
    warnings: list[str] = []
    has_nan_or_inf = False
    for row in rows:
        for field in ["t_s", "X_m", "Y_m", "Z_m", "qw", "qx", "qy", "qz"]:
            if not _finite(row[field]):
                has_nan_or_inf = True
    for point in points:
        for field in ["dt_s", "step_3d_m", "speed_m_s", "accel_m_s2", "jerk_m_s3", "quaternion_norm"]:
            if not _finite(point[field]):
                has_nan_or_inf = True

    dts = [point["dt_s"] for point in points[1:]]
    dt_positive = all(dt > 0 for dt in dts)
    time_monotonic = dt_positive and all(b["t_s"] > a["t_s"] for a, b in zip(rows, rows[1:]))
    if not required_fields_present:
        failure_reasons.append(f"missing required fields: {', '.join(missing_fields)}")
    if has_nan_or_inf:
        failure_reasons.append("input or derived motion values contain NaN or inf")
    if not time_monotonic:
        failure_reasons.append("time is not strictly increasing or contains dt <= 0")

    q_norms = [_quaternion_norm(row) for row in rows]
    q_ok = all(abs(norm - 1.0) <= thresholds.quaternion_tolerance for norm in q_norms if _finite(norm))
    if not q_ok:
        failure_reasons.append("quaternion is not normalized")

    max_speed = _max_abs([point["speed_m_s"] for point in points])
    max_speed_jump = _max_abs([point["speed_jump_m_s"] for point in points])
    max_accel = _max_abs([point["accel_m_s2"] for point in points])
    max_jerk = _max_abs([point["jerk_m_s3"] for point in points])
    if max_speed > thresholds.max_speed_m_s:
        failure_reasons.append(f"max_speed_m_s {max_speed:.6f} exceeds threshold {thresholds.max_speed_m_s:.6f}")
    if max_speed_jump > thresholds.max_speed_jump_m_s:
        failure_reasons.append(
            f"max_speed_jump_m_s {max_speed_jump:.6f} exceeds threshold {thresholds.max_speed_jump_m_s:.6f}"
        )
    if max_accel > thresholds.max_accel_m_s2:
        failure_reasons.append(f"max_accel_m_s2 {max_accel:.6f} exceeds threshold {thresholds.max_accel_m_s2:.6f}")
    if max_jerk > thresholds.max_jerk_m_s3:
        failure_reasons.append(f"max_jerk_m_s3 {max_jerk:.6f} exceeds threshold {thresholds.max_jerk_m_s3:.6f}")

    if time_source == "derived_from_speed":
        warnings.append("time was derived from point distance and speed because the workspace CSV has no explicit time field")

    finite_dts = [dt for dt in dts if _finite(dt)]
    total_duration = rows[-1]["t_s"] - rows[0]["t_s"] if len(rows) >= 2 and _finite(rows[-1]["t_s"]) else 0.0
    path_length = sum(point["step_3d_m"] for point in points if _finite(point["step_3d_m"]))
    jerk_peak_count = sum(1 for point in points if abs(point["jerk_m_s3"]) > thresholds.max_jerk_m_s3 if _finite(point["jerk_m_s3"]))
    recommended = required_fields_present and not failure_reasons
    return {
        "source_csv": str(csv_path),
        "input_kind": input_kind,
        "required_fields_present": required_fields_present,
        "missing_fields": list(missing_fields),
        "point_count": len(rows),
        "duration_s": round(total_duration, 9),
        "path_length_m": round(path_length, 9),
        "dt_min_s": round(min(finite_dts), 9) if finite_dts else 0.0,
        "dt_max_s": round(max(finite_dts), 9) if finite_dts else 0.0,
        "dt_mean_s": round(sum(finite_dts) / len(finite_dts), 9) if finite_dts else 0.0,
        "dt_nonpositive_count": sum(1 for dt in dts if not (dt > 0)),
        "time_source": time_source,
        "time_monotonic": time_monotonic,
        "max_step_3d_m": round(_max_abs([point["step_3d_m"] for point in points]), 9),
        "max_speed_m_s": round(max_speed, 9),
        "max_speed_jump_m_s": round(max_speed_jump, 9),
        "max_accel_m_s2": round(max_accel, 9),
        "max_jerk_m_s3": round(max_jerk, 9),
        "jerk_peak_count": jerk_peak_count,
        "quaternion_norm_min": round(min(q_norms), 9) if q_norms else 0.0,
        "quaternion_norm_max": round(max(q_norms), 9) if q_norms else 0.0,
        "quaternion_normalized": q_ok,
        "orientation_fixed_or_smooth": q_ok and (max(q_norms) - min(q_norms) <= thresholds.quaternion_tolerance if q_norms else True),
        "has_nan_or_inf": has_nan_or_inf,
        "segment_counts": dict(sorted(Counter(row["segment_type"] for row in rows).items())),
        "segment_stats": _segment_stats(points),
        "x_m_range": _range([row["X_m"] for row in rows]),
        "y_m_range": _range([row["Y_m"] for row in rows]),
        "z_m_range": _range([row["Z_m"] for row in rows]),
        "thresholds": {
            "max_speed_m_s": thresholds.max_speed_m_s,
            "max_accel_m_s2": thresholds.max_accel_m_s2,
            "max_jerk_m_s3": thresholds.max_jerk_m_s3,
            "max_speed_jump_m_s": thresholds.max_speed_jump_m_s,
        },
        "recommended_for_coppeliasim_playback": recommended,
        "recommended_for_ik_dry_run": recommended,
        "warnings": warnings,
        "failure_reasons": failure_reasons,
        "scope": (
            "motion continuity dry-run only; not real robot dynamics, not IK, "
            "not joint-space velocity/acceleration/torque checking, and not real robot control"
        ),
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
                        f"{float(point.get(field, 0.0)):.9f}"
                        if field not in {"point_id", "segment_type", "speed_over_limit", "accel_over_limit", "jerk_over_limit"}
                        else point.get(field, "")
                    )
                    for field in POINT_FIELDS
                }
            )


def _report_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Motion Continuity Dry-Run Report",
        "",
        "Scope: motion continuity dry-run only; not real robot dynamics, not IK, not joint-space velocity/acceleration/torque checking, and not real robot control.",
        "",
        f"- input: `{summary['source_csv']}`",
        f"- input_kind: `{summary['input_kind']}`",
        f"- time_source: `{summary['time_source']}`",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    keys = [
        "point_count",
        "duration_s",
        "path_length_m",
        "dt_min_s",
        "dt_max_s",
        "dt_mean_s",
        "dt_nonpositive_count",
        "max_step_3d_m",
        "max_speed_m_s",
        "max_speed_jump_m_s",
        "max_accel_m_s2",
        "max_jerk_m_s3",
        "jerk_peak_count",
        "quaternion_norm_min",
        "quaternion_norm_max",
        "quaternion_normalized",
        "orientation_fixed_or_smooth",
        "segment_counts",
        "segment_stats",
        "recommended_for_coppeliasim_playback",
        "recommended_for_ik_dry_run",
        "warnings",
        "failure_reasons",
    ]
    for key in keys:
        value = summary.get(key, "")
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "These thresholds are conservative dry-run gates for simulation and future IK preparation. They are not claimed to be real AUBO i5 controller limits. This report does not check joint-space velocity, joint acceleration, torque, collision, singularity, or true reachability.",
            "",
        ]
    )
    return "\n".join(lines)


def process_csv(
    csv_path: Path | str,
    *,
    input_kind: str = "auto",
    thresholds: MotionThresholds | None = None,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    source = Path(csv_path)
    cfg = thresholds or MotionThresholds()
    raw_rows, fieldnames = _read_csv(source)
    kind = detect_input_kind(fieldnames, input_kind)
    if kind == "target_pose":
        required_present, missing = _target_required_fields_present(fieldnames)
        rows, time_source = _normalize_target_rows(raw_rows)
    elif kind == "workspace":
        required_present, missing = _workspace_required_fields_present(fieldnames)
        rows, time_source = _normalize_workspace_rows(raw_rows)
    else:
        required_present, missing = False, ["unknown input kind"]
        rows, time_source = [], "unknown"
    points = _point_metrics(rows, cfg)
    summary = summarize_motion(
        rows,
        points,
        csv_path=source,
        input_kind=kind,
        required_fields_present=required_present,
        missing_fields=missing,
        time_source=time_source,
        thresholds=cfg,
    )
    target_dir = Path(out_dir) if out_dir else source.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    summary_json = target_dir / "motion_continuity_summary.json"
    report_md = target_dir / "motion_continuity_report.md"
    points_csv = target_dir / "motion_continuity_points.csv"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_report_markdown(summary), encoding="utf-8")
    _write_points(points, points_csv)
    return {
        "summary_json": str(summary_json),
        "report_md": str(report_md),
        "points_csv": str(points_csv),
        "summary": summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline motion continuity dry-run check")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="robot_target_poses.csv or robot_workspace_trajectory_resampled.csv")
    parser.add_argument("--input-kind", choices=["auto", "workspace", "target_pose"], default="auto")
    parser.add_argument("--max-speed-m-s", type=float, default=MotionThresholds.max_speed_m_s)
    parser.add_argument("--max-accel-m-s2", type=float, default=MotionThresholds.max_accel_m_s2)
    parser.add_argument("--max-jerk-m-s3", type=float, default=MotionThresholds.max_jerk_m_s3)
    parser.add_argument("--max-speed-jump-m-s", type=float, default=MotionThresholds.max_speed_jump_m_s)
    parser.add_argument("--out-dir", default=None)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    thresholds = MotionThresholds(
        max_speed_m_s=args.max_speed_m_s,
        max_accel_m_s2=args.max_accel_m_s2,
        max_jerk_m_s3=args.max_jerk_m_s3,
        max_speed_jump_m_s=args.max_speed_jump_m_s,
    )
    result = process_csv(args.csv, input_kind=args.input_kind, thresholds=thresholds, out_dir=args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
