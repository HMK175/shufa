"""Offline AUBO i5 command-plan adapter.

This module converts robot target poses into a dry-run command plan that
documents how a future SDK adapter might call AUBO i5 APIs. It intentionally
does not import libpyauboi5, connect to a robot, solve IK, or issue commands.
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

from target_pose_defaults import (
    select_default_target_pose_csv,
    retiming_metadata,
    target_pose_kind,
    target_pose_output_suffix,
)


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CSV = select_default_target_pose_csv()

COMMAND_FIELDS = [
    "command_id",
    "command_type",
    "pose_id",
    "t_s",
    "X_m",
    "Y_m",
    "Z_m",
    "qw",
    "qx",
    "qy",
    "qz",
    "speed_m_s",
    "accel_m_s2",
    "pen_down",
    "segment_type",
    "dry_run_only",
    "sdk_hint",
    "notes",
]


@dataclass(frozen=True)
class AdapterConfig:
    max_step_m: float = 0.015
    max_speed_m_s: float = 0.10
    max_accel_m_s2: float = 0.50
    quaternion_tolerance: float = 1e-6
    paper_half_width_m: float = 0.060
    paper_half_height_m: float = 0.060
    z_min_m: float = 0.0
    z_max_m: float = 0.008
    approach_lift_m: float = 0.030
    retract_lift_m: float = 0.030
    approach_speed_m_s: float = 0.05
    default_accel_m_s2: float = 0.20


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


def _finite(value: float) -> bool:
    return math.isfinite(value)


def _has_nonfinite(rows: Sequence[dict[str, Any]]) -> bool:
    fields = ["t_s", "X_m", "Y_m", "Z_m", "qw", "qx", "qy", "qz", "speed_m_s"]
    for row in rows:
        for field in fields:
            if not _finite(_float(row.get(field))):
                return True
    return False


def _distance_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = _float(b.get("X_m")) - _float(a.get("X_m"))
    dy = _float(b.get("Y_m")) - _float(a.get("Y_m"))
    dz = _float(b.get("Z_m")) - _float(a.get("Z_m"))
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    return distance if math.isfinite(distance) else float("nan")


def _finite_distances(rows: Sequence[dict[str, Any]]) -> list[float]:
    distances = [_distance_m(a, b) for a, b in zip(rows, rows[1:])]
    return [value for value in distances if math.isfinite(value)]


def _max_step_m(rows: Sequence[dict[str, Any]]) -> float:
    distances = _finite_distances(rows)
    return max(distances) if distances else 0.0


def _time_monotonic(rows: Sequence[dict[str, Any]]) -> bool:
    times = [_float(row.get("t_s")) for row in rows]
    return all(math.isfinite(value) for value in times) and all(b >= a for a, b in zip(times, times[1:]))


def _quaternion_norm(row: dict[str, Any]) -> float:
    return math.sqrt(
        _float(row.get("qw")) ** 2
        + _float(row.get("qx")) ** 2
        + _float(row.get("qy")) ** 2
        + _float(row.get("qz")) ** 2
    )


def _quaternions_normalized(rows: Sequence[dict[str, Any]], tolerance: float) -> bool:
    for row in rows:
        norm = _quaternion_norm(row)
        if not math.isfinite(norm) or abs(norm - 1.0) > tolerance:
            return False
    return True


def _max_speed_m_s(rows: Sequence[dict[str, Any]]) -> float:
    speeds = [_float(row.get("speed_m_s")) for row in rows]
    finite = [value for value in speeds if math.isfinite(value)]
    return max(finite) if finite else 0.0


def _max_accel_m_s2_estimate(rows: Sequence[dict[str, Any]]) -> float:
    max_accel = 0.0
    for prev, cur in zip(rows, rows[1:]):
        dt = _float(cur.get("t_s")) - _float(prev.get("t_s"))
        if not math.isfinite(dt) or dt <= 0:
            continue
        dv = _float(cur.get("speed_m_s")) - _float(prev.get("speed_m_s"))
        accel = abs(dv) / dt
        if math.isfinite(accel):
            max_accel = max(max_accel, accel)
    return max_accel


def _range(values: Sequence[float]) -> list[float]:
    finite = [value for value in values if math.isfinite(value)]
    if not finite:
        return [0.0, 0.0]
    return [round(min(finite), 6), round(max(finite), 6)]


def build_command_plan(rows: Sequence[dict[str, Any]], config: AdapterConfig) -> list[dict[str, Any]]:
    if not rows:
        return []

    commands: list[dict[str, Any]] = []
    first = rows[0]
    last = rows[-1]

    def command(
        *,
        command_id: int,
        command_type: str,
        source: dict[str, Any],
        z_override: float | None = None,
        speed_override: float | None = None,
        pen_down_override: int | None = None,
        segment_type_override: str | None = None,
        sdk_hint: str,
        notes: str,
    ) -> dict[str, Any]:
        return {
            "command_id": command_id,
            "command_type": command_type,
            "pose_id": _int(source.get("pose_id")),
            "t_s": _float(source.get("t_s")),
            "X_m": _float(source.get("X_m")),
            "Y_m": _float(source.get("Y_m")),
            "Z_m": _float(source.get("Z_m")) if z_override is None else z_override,
            "qw": _float(source.get("qw")),
            "qx": _float(source.get("qx")),
            "qy": _float(source.get("qy")),
            "qz": _float(source.get("qz")),
            "speed_m_s": _float(source.get("speed_m_s")) if speed_override is None else speed_override,
            "accel_m_s2": config.default_accel_m_s2,
            "pen_down": _int(source.get("pen_down")) if pen_down_override is None else pen_down_override,
            "segment_type": str(source.get("segment_type", "")) if segment_type_override is None else segment_type_override,
            "dry_run_only": "true",
            "sdk_hint": sdk_hint,
            "notes": notes,
        }

    commands.append(
        command(
            command_id=0,
            command_type="move_joint_approach",
            source=first,
            z_override=_float(first.get("Z_m")) + config.approach_lift_m,
            speed_override=config.approach_speed_m_s,
            pen_down_override=0,
            segment_type_override="approach",
            sdk_hint="future: inverse_kin + move_joint",
            notes="Safe approach pose above first target; dry-run only; IK is not solved.",
        )
    )

    for row in rows:
        segment_type = str(row.get("segment_type", ""))
        notes = "Target pose follow segment; dry-run only; no SDK call is made."
        if _int(row.get("pen_down")) == 0 or segment_type == "pen_up_move":
            notes = "pen-up segment; keep as move_line in future adapter, but pen_down=0."
        commands.append(
            command(
                command_id=len(commands),
                command_type="move_line",
                source=row,
                sdk_hint="future: move_line",
                notes=notes,
            )
        )

    commands.append(
        command(
            command_id=len(commands),
            command_type="move_line_retract",
            source=last,
            z_override=_float(last.get("Z_m")) + config.retract_lift_m,
            speed_override=config.approach_speed_m_s,
            pen_down_override=0,
            segment_type_override="retract",
            sdk_hint="future: move_line",
            notes="Safe retract pose after final target; dry-run only; no SDK call is made.",
        )
    )
    return commands


def safety_check(
    rows: Sequence[dict[str, Any]],
    commands: Sequence[dict[str, Any]],
    source_csv: Path | str,
    config: AdapterConfig,
) -> dict[str, Any]:
    warnings: list[str] = []
    max_step = _max_step_m(rows)
    max_speed = _max_speed_m_s(rows)
    max_accel = _max_accel_m_s2_estimate(rows)
    has_nonfinite = _has_nonfinite(rows)
    time_monotonic = _time_monotonic(rows)
    quaternion_normalized = _quaternions_normalized(rows, config.quaternion_tolerance)

    xs = [_float(row.get("X_m")) for row in rows]
    ys = [_float(row.get("Y_m")) for row in rows]
    zs = [_float(row.get("Z_m")) for row in rows]
    xy_range_m = {"x": _range(xs), "y": _range(ys)}
    z_range_m = _range(zs)

    if has_nonfinite:
        warnings.append("target pose rows contain NaN or inf")
    if not time_monotonic:
        warnings.append("target pose time is not monotonic")
    if not quaternion_normalized:
        warnings.append("target pose quaternion is not normalized")
    if max_step > config.max_step_m:
        warnings.append(f"max step {max_step:.6f}m exceeds dry-run limit {config.max_step_m:.6f}m")
    if max_speed > config.max_speed_m_s:
        warnings.append(f"max speed {max_speed:.6f}m/s exceeds dry-run limit {config.max_speed_m_s:.6f}m/s")
    if max_accel > config.max_accel_m_s2:
        warnings.append(f"max acceleration estimate {max_accel:.6f}m/s^2 exceeds limit {config.max_accel_m_s2:.6f}m/s^2")

    workspace_hint = (
        "Conservative paper-workspace hint only: expected XY near +/-60mm paper frame "
        "and Z near 0..8mm. This is not an AUBO i5 reachability or collision check."
    )

    return {
        "point_count": len(rows),
        "command_count": len(commands),
        "source_csv": str(source_csv),
        "source_target_pose_csv": str(source_csv),
        "source_target_pose_kind": target_pose_kind(source_csv),
        **retiming_metadata(source_csv),
        "max_step_m": round(max_step, 6),
        "max_speed_m_s": round(max_speed, 6),
        "max_accel_m_s2_estimate": round(max_accel, 6),
        "xy_range_m": xy_range_m,
        "z_range_m": z_range_m,
        "quaternion_normalized": quaternion_normalized,
        "time_monotonic": time_monotonic,
        "has_nan_or_inf": has_nonfinite,
        "workspace_hint": workspace_hint,
        "segment_counts": dict(sorted(Counter(str(row.get("segment_type", "")) for row in rows).items())),
        "recommended_for_sdk_dry_run": not warnings,
        "warnings": warnings,
        "scope": "AUBO i5 dry-run command plan only; no IK, no SDK import, no connection, no real robot control",
    }


def _write_command_plan(commands: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMMAND_FIELDS)
        writer.writeheader()
        for command in commands:
            writer.writerow(
                {
                    field: (
                        f"{_float(command[field]):.9f}"
                        if field
                        in {
                            "t_s",
                            "X_m",
                            "Y_m",
                            "Z_m",
                            "qw",
                            "qx",
                            "qy",
                            "qz",
                            "speed_m_s",
                            "accel_m_s2",
                        }
                        else command.get(field, "")
                    )
                    for field in COMMAND_FIELDS
                }
            )


def _write_report(path: Path, plan_csv: Path, safety: dict[str, Any], config: AdapterConfig) -> None:
    lines = [
        "# AUBO i5 Command Adapter Dry-Run Plan",
        "",
        "This is an offline AUBO i5 command adapter dry-run.",
        "",
        "It does not run IK, does not connect to a real AUBO i5, does not import or execute `libpyauboi5`, and does not call `move_joint` or `move_line`. The command rows are a future SDK-call plan only.",
        "",
        "Historical AUBO IP addresses, ports, and SDK paths are documentation clues only. They are not defaults and are not used by this script.",
        "",
        "## Outputs",
        "",
        f"- command_plan_csv: `{plan_csv}`",
        f"- safety_check_json: `{path.with_name('aubo_i5_safety_check_smoothed.json' if safety.get('source_target_pose_kind') == 'smoothed' else 'aubo_i5_safety_check.json')}`",
        f"- source_target_pose_csv: `{safety.get('source_target_pose_csv')}`",
        f"- source_retiming_summary: `{safety.get('source_retiming_summary')}`",
        f"- source_retimming_summary: `{safety.get('source_retimming_summary')}`",
        f"- source_motion_continuity_after_retiming: `{safety.get('source_motion_continuity_after_retiming')}`",
        "",
        "This result is based on the listed target-pose CSV. When `source_target_pose_kind` is `smoothed`, it uses target poses that already passed the conservative motion-continuity after-retiming gate.",
        "",
        "## Future SDK Hints",
        "",
        "- `move_joint_approach`: future adapter may call `inverse_kin` followed by `move_joint`.",
        "- `move_line`: future adapter may call `move_line` for target-pose following.",
        "- `move_line_retract`: future adapter may call `move_line` to leave the paper safely.",
        "",
        "## Safety Summary",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for key in [
        "point_count",
        "command_count",
        "max_step_m",
        "max_speed_m_s",
        "max_accel_m_s2_estimate",
        "xy_range_m",
        "z_range_m",
        "quaternion_normalized",
        "time_monotonic",
        "has_nan_or_inf",
        "recommended_for_sdk_dry_run",
        "source_target_pose_csv",
        "source_target_pose_kind",
        "source_retiming_summary",
        "source_retimming_summary",
        "source_motion_continuity_after_retiming",
        "warnings",
        "scope",
    ]:
        value: Any = safety.get(key, "")
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "Before any real AUBO i5 experiment, confirm robot IP, emergency stop, tool TCP, fixture, paper coordinate frame, speed and acceleration limits, reachability, collision margins, and on-site safety.",
            "",
            f"Dry-run thresholds: max_step_m <= `{config.max_step_m}`, max_speed_m_s <= `{config.max_speed_m_s}`, max_accel_m_s2 <= `{config.max_accel_m_s2}`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def process_csv(csv_path: Path | str, config: AdapterConfig | None = None, out_dir: Path | str | None = None) -> dict[str, Any]:
    source = Path(csv_path)
    cfg = config or AdapterConfig()
    rows = _read_csv(source)
    target_dir = Path(out_dir) if out_dir else source.parent
    suffix = target_pose_output_suffix(source)
    plan_csv = target_dir / f"aubo_i5_command_plan{suffix}.csv"
    safety_json = target_dir / f"aubo_i5_safety_check{suffix}.json"
    report_md = target_dir / f"aubo_i5_command_plan{suffix}.md"

    commands = build_command_plan(rows, cfg)
    safety = safety_check(rows, commands, source, cfg)
    _write_command_plan(commands, plan_csv)
    safety_json.write_text(json.dumps(safety, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(report_md, plan_csv, safety, cfg)
    return {
        "source_csv": str(source),
        "command_plan_csv": str(plan_csv),
        "safety_check_json": str(safety_json),
        "command_plan_md": str(report_md),
        "safety": safety,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an offline AUBO i5 SDK dry-run command plan")
    parser.add_argument(
        "--csv",
        default=None,
        help="robot_target_poses.csv path. If omitted, smoothed target poses are preferred when present.",
    )
    parser.add_argument("--out-dir", default=None, help="Output directory; defaults to the source CSV directory")
    parser.add_argument("--max-step-m", type=float, default=0.015)
    parser.add_argument("--max-speed-m-s", type=float, default=0.10)
    parser.add_argument("--max-accel-m-s2", type=float, default=0.50)
    parser.add_argument("--approach-lift-m", type=float, default=0.030)
    parser.add_argument("--retract-lift-m", type=float, default=0.030)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config = AdapterConfig(
        max_step_m=args.max_step_m,
        max_speed_m_s=args.max_speed_m_s,
        max_accel_m_s2=args.max_accel_m_s2,
        approach_lift_m=args.approach_lift_m,
        retract_lift_m=args.retract_lift_m,
    )
    csv_path = args.csv if args.csv else select_default_target_pose_csv()
    result = process_csv(csv_path, config=config, out_dir=args.out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
