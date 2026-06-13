"""Batch dry-run checks for CoppeliaSim pen-tip path playback.

This script does not connect to CoppeliaSim. It summarizes resampled robot
workspace CSV files so the playback layer can be checked before GUI playback.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from play_workspace_path import dry_run_summary


DEFAULT_BATCH_DIR = Path(__file__).resolve().parents[1] / "outputs" / "batch_20260613_092733"
SUMMARY_NAME = "coppeliasim_playback_summary.csv"
REPORT_NAME = "coppeliasim_playback_report.md"

SUMMARY_FIELDS = [
    "task_dir",
    "task",
    "char",
    "style",
    "connection_preference",
    "point_count",
    "segment_type_counts",
    "duration_estimate_s",
    "path_length_mm",
    "x_mm_min",
    "x_mm_max",
    "y_mm_min",
    "y_mm_max",
    "z_mm_min",
    "z_mm_max",
    "max_step_3d_mm",
    "max_xy_step_mm",
    "max_z_step_mm",
    "stroke_count",
    "connector_count",
    "pen_up_move_count",
    "out_of_workspace_bounds",
    "csv_path",
]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _char_from_task_dir(task_dir: Path) -> str:
    prefix = task_dir.name.split("_", 1)[0]
    if prefix.startswith("u"):
        try:
            return chr(int(prefix[1:], 16))
        except ValueError:
            return ""
    return ""


def _style_from_task_dir(task_dir: Path) -> str:
    parts = task_dir.name.split("_")
    return parts[1] if len(parts) > 1 else ""


def _metadata(task_dir: Path) -> dict[str, Any]:
    summary = _load_json(task_dir / "summary.json")
    plan = _load_json(task_dir / "plan.json")
    modifiers = summary.get("style_modifiers") or plan.get("style_modifiers") or {}
    return {
        "task": summary.get("task") or plan.get("task") or task_dir.name,
        "char": summary.get("char") or plan.get("char") or _char_from_task_dir(task_dir),
        "style": summary.get("style") or plan.get("style") or _style_from_task_dir(task_dir),
        "connection_preference": modifiers.get("connection_preference", ""),
    }


def _row_for_csv(csv_path: Path, batch_dir: Path) -> dict[str, Any]:
    task_dir = csv_path.parent
    summary = dry_run_summary(csv_path)
    meta = _metadata(task_dir)
    x_range = summary["x_mm_range"]
    y_range = summary["y_mm_range"]
    z_range = summary["z_mm_range"]
    return {
        "task_dir": task_dir.relative_to(batch_dir).as_posix(),
        "task": meta["task"],
        "char": meta["char"],
        "style": meta["style"],
        "connection_preference": meta["connection_preference"],
        "point_count": summary["point_count"],
        "segment_type_counts": json.dumps(summary["segment_type_counts"], ensure_ascii=False, sort_keys=True),
        "duration_estimate_s": summary["duration_estimate_s"],
        "path_length_mm": summary["path_length_mm"],
        "x_mm_min": x_range[0],
        "x_mm_max": x_range[1],
        "y_mm_min": y_range[0],
        "y_mm_max": y_range[1],
        "z_mm_min": z_range[0],
        "z_mm_max": z_range[1],
        "max_step_3d_mm": summary["max_step_3d_mm"],
        "max_xy_step_mm": summary["max_xy_step_mm"],
        "max_z_step_mm": summary["max_z_step_mm"],
        "stroke_count": summary["stroke_count"],
        "connector_count": summary["connector_count"],
        "pen_up_move_count": summary["pen_up_move_count"],
        "out_of_workspace_bounds": summary["out_of_workspace_bounds"],
        "csv_path": str(csv_path),
    }


def find_resampled_csvs(batch_dir: Path | str) -> list[Path]:
    root = Path(batch_dir)
    return sorted(root.glob("*/robot_workspace_trajectory_resampled.csv"))


def write_summary_csv(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _focus_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    focus = [
        row
        for row in rows
        if row.get("style") == "xingkai"
        and (row.get("char") == "山" or str(row.get("task_dir", "")).startswith("u5c71_"))
        and row.get("connection_preference") in {"none", "weak", "normal"}
    ]
    return sorted(focus, key=lambda row: {"none": 0, "weak": 1, "normal": 2}.get(row.get("connection_preference"), 99))


def write_report(rows: list[dict[str, Any]], path: Path, batch_dir: Path) -> None:
    total = len(rows)
    out_of_bounds = sum(1 for row in rows if str(row["out_of_workspace_bounds"]).lower() == "true")
    max_3d = max((float(row["max_step_3d_mm"]) for row in rows), default=0.0)
    max_xy = max((float(row["max_xy_step_mm"]) for row in rows), default=0.0)
    max_z = max((float(row["max_z_step_mm"]) for row in rows), default=0.0)

    lines = [
        "# CoppeliaSim playback dry-run report",
        "",
        f"- Batch directory: `{batch_dir}`",
        f"- CSV files checked: {total}",
        f"- Out-of-workspace rows: {out_of_bounds}",
        f"- Max 3D step: {max_3d:.6g} mm",
        f"- Max XY step: {max_xy:.6g} mm",
        f"- Max Z step: {max_z:.6g} mm",
        "",
        "## Focus: xingkai shan connection ablation",
        "",
        "| task_dir | connection | points | max_3d | max_xy | max_z | duration_s | stroke | connector | pen_up |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in _focus_rows(rows):
        lines.append(
            "| {task_dir} | {connection_preference} | {point_count} | {max_step_3d_mm} | "
            "{max_xy_step_mm} | {max_z_step_mm} | {duration_estimate_s} | {stroke_count} | "
            "{connector_count} | {pen_up_move_count} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This report is dry-run only: no GUI, no CoppeliaSim connection, no robot IK.",
            "- `stroke_count`, `connector_count`, and `pen_up_move_count` are point counts by segment type.",
            "- `max_step_3d_mm`, `max_xy_step_mm`, and `max_z_step_mm` split the playback jump check.",
            "- GUI load during live playback can be reduced with `--display-stride N` or `--no-path-objects`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def evaluate_batch(batch_dir: Path | str = DEFAULT_BATCH_DIR) -> dict[str, Path | int]:
    root = Path(batch_dir)
    csv_paths = find_resampled_csvs(root)
    rows = [_row_for_csv(csv_path, root) for csv_path in csv_paths]
    summary_csv = root / SUMMARY_NAME
    report_md = root / REPORT_NAME
    write_summary_csv(rows, summary_csv)
    write_report(rows, report_md, root)
    return {"summary_csv": summary_csv, "report_md": report_md, "count": len(rows)}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run a batch of CoppeliaSim playback CSV files")
    parser.add_argument("--batch-dir", default=str(DEFAULT_BATCH_DIR))
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    result = evaluate_batch(Path(args.batch_dir))
    print(json.dumps({key: str(value) for key, value in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
