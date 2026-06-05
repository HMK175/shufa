"""Run the isolated LLM/planner style trajectory demo."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from knowledge import MakeMeAHanziKnowledge
from planner import RuleBasedPlanner, load_style_profiles
from trajectory_tools import (
    build_styled_trajectory,
    normalize_medians,
    trajectory_metrics,
    write_preview,
    write_style_compare,
    write_trajectory_csv,
)


EXP_DIR = Path(__file__).resolve().parents[1]
ROOT = EXP_DIR.parents[1]
DEFAULT_GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
DEFAULT_PROFILES = EXP_DIR / "configs" / "style_profiles.json"
DEFAULT_TASKS = EXP_DIR / "configs" / "demo_tasks.json"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
SUMMARY_FIELDS = [
    "task",
    "char",
    "style",
    "stroke_count",
    "raw_points",
    "point_count",
    "path_length",
    "pen_up_count",
    "bounding_box_width",
    "bounding_box_height",
    "aspect_ratio",
    "mean_turning",
    "connection_count",
    "out_of_bounds",
    "trajectory_csv",
    "preview_png",
    "plan_json",
]


def safe_task_id(char: str, style: str) -> str:
    return f"u{ord(char):04x}_{style}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def safe_char_id(char: str) -> str:
    return f"u{ord(char):04x}"


def run_task(
    task_text: str,
    output_root: Path | str = DEFAULT_OUTPUT,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    image_size: int = 256,
) -> dict[str, str]:
    profiles = load_style_profiles(style_profiles_path)
    planner = RuleBasedPlanner(profiles)
    plan = planner.plan(task_text)
    knowledge = MakeMeAHanziKnowledge(graphics_path)
    glyph = knowledge.get_glyph(plan["char"])

    raw_strokes = normalize_medians(glyph.medians, image_size=image_size)
    styled_strokes = build_styled_trajectory(raw_strokes, plan["style_params"], image_size=image_size)

    out_dir = Path(output_root) / safe_task_id(plan["char"], plan["style"])
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "plan.json"
    csv_path = out_dir / "trajectory.csv"
    preview_path = out_dir / "preview.png"
    summary_path = out_dir / "summary.json"

    plan_payload = dict(plan)
    plan_payload["stroke_plan"] = dict(plan_payload["stroke_plan"])
    plan_payload["stroke_plan"]["stroke_count"] = glyph.stroke_count
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_trajectory_csv(styled_strokes, csv_path)
    write_preview(raw_strokes, styled_strokes, preview_path, f"{plan['char']} {plan['style']}", image_size)

    metrics = trajectory_metrics(
        styled_strokes,
        image_size=image_size,
        stroke_count=glyph.stroke_count,
        connection_strength=float(plan["style_params"].get("connection_strength", 0.0)),
        allow_interstroke_connections=bool(plan["style_params"].get("allow_interstroke_connections", False)),
    )
    summary = {
        "task": task_text,
        "char": plan["char"],
        "style": plan["style"],
        "stroke_count": glyph.stroke_count,
        "raw_points": sum(len(stroke) for stroke in raw_strokes),
        "styled_points": metrics["point_count"],
        **metrics,
        "style_params": plan["style_params"],
        "trajectory_csv": str(csv_path),
        "preview_png": str(preview_path),
        "plan_json": str(plan_path)
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "plan_json": str(plan_path),
        "trajectory_csv": str(csv_path),
        "preview_png": str(preview_path),
        "summary_json": str(summary_path),
        "output_dir": str(out_dir)
    }


def _batch_id() -> str:
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _write_batch_summary(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})


def run_batch(
    tasks: list[str],
    output_root: Path | str = DEFAULT_OUTPUT,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    image_size: int = 256,
) -> dict[str, object]:
    batch_dir = Path(output_root) / _batch_id()
    batch_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, str]] = []
    summaries: list[dict] = []
    by_char_style: dict[str, dict[str, list]] = {}
    raw_by_char: dict[str, list] = {}

    profiles = load_style_profiles(style_profiles_path)
    knowledge = MakeMeAHanziKnowledge(graphics_path)

    for task in tasks:
        result = run_task(
            task_text=task,
            output_root=batch_dir,
            graphics_path=graphics_path,
            style_profiles_path=style_profiles_path,
            image_size=image_size,
        )
        results.append(result)
        summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
        summaries.append(summary)

        char = str(summary["char"])
        style = str(summary["style"])
        if char not in raw_by_char:
            glyph = knowledge.get_glyph(char)
            raw_by_char[char] = normalize_medians(glyph.medians, image_size=image_size)
        styled = build_styled_trajectory(raw_by_char[char], profiles[style], image_size=image_size)
        by_char_style.setdefault(char, {})[style] = styled

    summary_csv = batch_dir / "batch_summary.csv"
    _write_batch_summary(summaries, summary_csv)

    compare_paths: dict[str, str] = {}
    for char, style_map in by_char_style.items():
        if len(style_map) < 2:
            continue
        compare_path = batch_dir / f"compare_{safe_char_id(char)}.png"
        write_style_compare(raw_by_char[char], style_map, compare_path, image_size=image_size)
        compare_paths[char] = str(compare_path)

    return {
        "batch_dir": str(batch_dir),
        "batch_summary_csv": str(summary_csv),
        "compare_images": compare_paths,
        "results": results,
    }


def _load_tasks(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [str(item["task"]) for item in data]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LLM-style trajectory demo")
    parser.add_argument("--task", default=None)
    parser.add_argument("--tasks-file", default=None)
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS))
    parser.add_argument("--style-profiles", default=str(DEFAULT_PROFILES))
    parser.add_argument("--style-profile", dest="style_profile", default=None)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--image-size", type=int, default=256)
    args = parser.parse_args()
    style_profile_path = args.style_profile or args.style_profiles

    if args.tasks_file:
        tasks = _load_tasks(Path(args.tasks_file))
    elif args.task:
        tasks = [args.task]
    else:
        tasks = _load_tasks(DEFAULT_TASKS)

    if args.task and not args.tasks_file:
        result = run_task(
            task_text=tasks[0],
            output_root=args.out_dir,
            graphics_path=args.graphics,
            style_profiles_path=style_profile_path,
            image_size=args.image_size,
        )
    else:
        result = run_batch(
            tasks=tasks,
            output_root=args.out_dir,
            graphics_path=args.graphics,
            style_profiles_path=style_profile_path,
            image_size=args.image_size,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
