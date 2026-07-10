"""Retiming and conservative speed smoothing for robot target poses.

This is an offline post-processing layer. It only removes adjacent static
duplicate points and rewrites target-pose timestamps/speeds; it does not solve
IK, connect to any robot, load an SDK, or send motion commands.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import motion_continuity_check as motion
from motion_continuity_check import MotionThresholds


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CSV = (
    EXP_DIR
    / "outputs"
    / "batch_20260613_154131"
    / "u5c71_xingkai_20260613_154132_009898"
    / "robot_target_poses.csv"
)

SMOOTHED_CSV_NAME = "robot_target_poses_smoothed.csv"
SUMMARY_JSON_NAME = "target_pose_retiming_summary.json"
REPORT_MD_NAME = "target_pose_retiming_report.md"
AFTER_SUMMARY_JSON_NAME = "motion_continuity_after_retiming_summary.json"
AFTER_REPORT_MD_NAME = "motion_continuity_after_retiming_report.md"
AFTER_POINTS_CSV_NAME = "motion_continuity_after_retiming_points.csv"


@dataclass(frozen=True)
class RetimingConfig:
    stroke_speed_m_s: float = 0.035
    connector_speed_m_s: float = 0.025
    pen_up_speed_m_s: float = 0.060
    min_dt_s: float = 0.03
    duplicate_epsilon_m: float = 1e-9
    max_speed_m_s: float = 0.10
    max_accel_m_s2: float = 0.50
    max_jerk_m_s3: float = 5.0
    max_speed_jump_m_s: float = 0.05
    max_iterations: int = 8
    time_scale_step: float = 1.25

    @property
    def motion_thresholds(self) -> MotionThresholds:
        return MotionThresholds(
            max_speed_m_s=self.max_speed_m_s,
            max_accel_m_s2=self.max_accel_m_s2,
            max_jerk_m_s3=self.max_jerk_m_s3,
            max_speed_jump_m_s=self.max_speed_jump_m_s,
        )


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def _float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = _float(b.get("X_m")) - _float(a.get("X_m"))
    dy = _float(b.get("Y_m")) - _float(a.get("Y_m"))
    dz = _float(b.get("Z_m")) - _float(a.get("Z_m"))
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _path_length(rows: Sequence[dict[str, Any]]) -> float:
    return sum(_distance_m(a, b) for a, b in zip(rows, rows[1:]))


def _segment_speed(segment_type: str, config: RetimingConfig) -> float:
    if segment_type == "connector":
        return config.connector_speed_m_s
    if segment_type == "pen_up_move":
        return config.pen_up_speed_m_s
    return config.stroke_speed_m_s


def _deduplicate_adjacent_static_points(
    rows: Sequence[dict[str, Any]],
    *,
    epsilon_m: float,
) -> tuple[list[dict[str, Any]], int]:
    if not rows:
        return [], 0
    kept: list[dict[str, Any]] = [dict(rows[0])]
    removed = 0
    for row in rows[1:]:
        if _distance_m(kept[-1], row) <= epsilon_m:
            removed += 1
            continue
        kept.append(dict(row))
    return kept, removed


def _retime_rows(rows: Sequence[dict[str, Any]], config: RetimingConfig, *, time_scale: float) -> list[dict[str, Any]]:
    if not rows:
        return []
    retimed = [dict(rows[0])]
    retimed[0]["pose_id"] = 0
    retimed[0]["t_s"] = 0.0
    retimed[0]["speed_m_s"] = 0.0
    current_t = 0.0

    actual_speeds: list[float] = [0.0]
    for idx, row in enumerate(rows[1:], start=1):
        prev = retimed[-1]
        current = dict(row)
        segment_type = str(current.get("segment_type") or prev.get("segment_type") or "stroke")
        distance = _distance_m(prev, current)
        planned_speed = max(_segment_speed(segment_type, config), 1e-9)
        base_dt = max(distance / planned_speed, config.min_dt_s)
        dt = base_dt * max(time_scale, 1e-9)
        current_t += dt
        current["pose_id"] = idx
        current["t_s"] = current_t
        current["speed_m_s"] = distance / dt if dt > 0 else 0.0
        actual_speeds.append(float(current["speed_m_s"]))
        retimed.append(current)

    if len(retimed) > 1:
        retimed[0]["speed_m_s"] = actual_speeds[1]
    return retimed


def _write_pose_csv(rows: Sequence[dict[str, Any]], fieldnames: Sequence[str], path: Path) -> None:
    fields = list(fieldnames)
    for required in ["pose_id", "t_s", "speed_m_s"]:
        if required not in fields:
            fields.append(required)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out: dict[str, Any] = {}
            for field in fields:
                value = row.get(field, "")
                if field in {"pose_id", "pen_down", "segment_type"}:
                    out[field] = value
                elif field in row:
                    out[field] = f"{_float(value):.9f}"
                else:
                    out[field] = value
            writer.writerow(out)


def _motion_check_for_csv(
    csv_path: Path,
    *,
    thresholds: MotionThresholds,
    out_dir: Path | None = None,
    write_files: bool = False,
) -> dict[str, Any]:
    raw_rows, fieldnames = motion._read_csv(csv_path)
    kind = motion.detect_input_kind(fieldnames, "target_pose")
    required_present, missing = motion._target_required_fields_present(fieldnames)
    rows, time_source = motion._normalize_target_rows(raw_rows)
    points = motion._point_metrics(rows, thresholds)
    summary = motion.summarize_motion(
        rows,
        points,
        csv_path=csv_path,
        input_kind=kind,
        required_fields_present=required_present,
        missing_fields=missing,
        time_source=time_source,
        thresholds=thresholds,
    )
    if write_files:
        target_dir = out_dir or csv_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        summary_path = target_dir / AFTER_SUMMARY_JSON_NAME
        report_path = target_dir / AFTER_REPORT_MD_NAME
        points_path = target_dir / AFTER_POINTS_CSV_NAME
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(motion._report_markdown(summary), encoding="utf-8")
        motion._write_points(points, points_path)
        return {
            "summary": summary,
            "summary_json": str(summary_path),
            "report_md": str(report_path),
            "points_csv": str(points_path),
        }
    return {"summary": summary}


def _report_markdown(summary: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> str:
    lines = [
        "# Target Pose Retiming Report",
        "",
        "Scope: offline target-pose retiming only. This is not real robot dynamics optimization, not joint-space planning, not IK, and not AUBO i5 control.",
        "",
        f"- source_csv: `{summary['source_csv']}`",
        f"- smoothed_csv: `{summary['smoothed_csv']}`",
        "",
        "## Before / After",
        "",
        "| metric | before | after |",
        "|---|---:|---:|",
    ]
    for key in [
        "point_count",
        "duration_s",
        "dt_nonpositive_count",
        "max_speed_m_s",
        "max_accel_m_s2",
        "max_jerk_m_s3",
        "recommended_for_coppeliasim_playback",
        "recommended_for_ik_dry_run",
    ]:
        lines.append(f"| `{key}` | `{before.get(key, '')}` | `{after.get(key, '')}` |")
    lines.extend(
        [
            "",
            "## Retiming Summary",
            "",
            "| field | value |",
            "|---|---|",
        ]
    )
    for key in [
        "original_point_count",
        "retimed_point_count",
        "removed_duplicate_count",
        "geometry_path_length_before_m",
        "geometry_path_length_after_m",
        "path_length_delta_m",
        "iterations_used",
        "final_time_scale",
        "retiming_success",
        "failure_reasons",
    ]:
        value = summary.get(key, "")
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "Only adjacent static duplicate points may be removed. The remaining `X_m/Y_m/Z_m` coordinates and quaternion fields are preserved; this layer rewrites time and speed fields only.",
            "",
        ]
    )
    return "\n".join(lines)


def process_csv(
    csv_path: Path | str,
    *,
    config: RetimingConfig | None = None,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    source = Path(csv_path)
    cfg = config or RetimingConfig()
    target_dir = Path(out_dir) if out_dir else source.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    rows, fieldnames = _read_csv(source)
    original_rows = [dict(row) for row in rows]
    deduped_rows, removed_count = _deduplicate_adjacent_static_points(original_rows, epsilon_m=cfg.duplicate_epsilon_m)
    before_check = _motion_check_for_csv(source, thresholds=cfg.motion_thresholds)["summary"]

    smoothed_csv = target_dir / SMOOTHED_CSV_NAME
    final_rows: list[dict[str, Any]] = []
    after_summary: dict[str, Any] = {}
    final_scale = 1.0
    iterations_used = 0
    for iteration in range(max(0, cfg.max_iterations) + 1):
        iterations_used = iteration
        final_rows = _retime_rows(deduped_rows, cfg, time_scale=final_scale)
        _write_pose_csv(final_rows, fieldnames, smoothed_csv)
        after_summary = _motion_check_for_csv(smoothed_csv, thresholds=cfg.motion_thresholds)["summary"]
        if after_summary.get("recommended_for_ik_dry_run"):
            break
        final_scale *= cfg.time_scale_step

    after_check = _motion_check_for_csv(
        smoothed_csv,
        thresholds=cfg.motion_thresholds,
        out_dir=target_dir,
        write_files=True,
    )
    after_summary = after_check["summary"]

    before_length = _path_length(original_rows)
    after_length = _path_length(final_rows)
    summary = {
        "source_csv": str(source),
        "smoothed_csv": str(smoothed_csv),
        "original_point_count": len(original_rows),
        "retimed_point_count": len(final_rows),
        "removed_duplicate_count": removed_count,
        "geometry_path_length_before_m": round(before_length, 12),
        "geometry_path_length_after_m": round(after_length, 12),
        "path_length_delta_m": round(after_length - before_length, 12),
        "iterations_used": iterations_used,
        "final_time_scale": round(final_scale, 9),
        "retiming_success": bool(after_summary.get("recommended_for_ik_dry_run")),
        "before_motion_summary": before_check,
        "after_motion_summary": after_summary,
        "failure_reasons": after_summary.get("failure_reasons", []),
        "scope": "offline target-pose retiming only; no IK, no SDK, no robot connection, no robot command",
    }
    summary_json = target_dir / SUMMARY_JSON_NAME
    report_md = target_dir / REPORT_MD_NAME
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_md.write_text(_report_markdown(summary, before_check, after_summary), encoding="utf-8")
    return {
        "smoothed_csv": str(smoothed_csv),
        "summary_json": str(summary_json),
        "report_md": str(report_md),
        "after_motion_summary_json": after_check["summary_json"],
        "after_motion_report_md": after_check["report_md"],
        "after_motion_points_csv": after_check["points_csv"],
        "summary": summary,
        "before_motion_summary": before_check,
        "after_motion_summary": after_summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Retiming and conservative smoothing for robot target poses")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="robot_target_poses.csv path")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--stroke-speed-m-s", type=float, default=RetimingConfig.stroke_speed_m_s)
    parser.add_argument("--connector-speed-m-s", type=float, default=RetimingConfig.connector_speed_m_s)
    parser.add_argument("--pen-up-speed-m-s", type=float, default=RetimingConfig.pen_up_speed_m_s)
    parser.add_argument("--min-dt-s", type=float, default=RetimingConfig.min_dt_s)
    parser.add_argument("--max-speed-m-s", type=float, default=RetimingConfig.max_speed_m_s)
    parser.add_argument("--max-accel-m-s2", type=float, default=RetimingConfig.max_accel_m_s2)
    parser.add_argument("--max-jerk-m-s3", type=float, default=RetimingConfig.max_jerk_m_s3)
    parser.add_argument("--max-speed-jump-m-s", type=float, default=RetimingConfig.max_speed_jump_m_s)
    parser.add_argument("--max-iterations", type=int, default=RetimingConfig.max_iterations)
    parser.add_argument("--time-scale-step", type=float, default=RetimingConfig.time_scale_step)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = RetimingConfig(
        stroke_speed_m_s=args.stroke_speed_m_s,
        connector_speed_m_s=args.connector_speed_m_s,
        pen_up_speed_m_s=args.pen_up_speed_m_s,
        min_dt_s=args.min_dt_s,
        max_speed_m_s=args.max_speed_m_s,
        max_accel_m_s2=args.max_accel_m_s2,
        max_jerk_m_s3=args.max_jerk_m_s3,
        max_speed_jump_m_s=args.max_speed_jump_m_s,
        max_iterations=args.max_iterations,
        time_scale_step=args.time_scale_step,
    )
    result = process_csv(args.csv, config=config, out_dir=args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
