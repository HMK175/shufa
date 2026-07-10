"""Run the isolated LLM/planner style trajectory demo."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from knowledge import MakeMeAHanziKnowledge
from execution_tools import (
    build_execution_trajectory,
    execution_metrics,
    render_execution,
    render_execution_debug,
    write_execution_compare,
    write_execution_csv,
)
from planner import load_style_profiles, plan_task
from style_modifiers import apply_style_modifiers_to_brush_params, load_brush_profiles
from trajectory_tools import (
    build_styled_trajectory,
    normalize_medians,
    trajectory_metrics,
    write_preview,
    write_labeled_compare,
    write_style_compare,
    write_trajectory_csv,
)


EXP_DIR = Path(__file__).resolve().parents[1]
ROOT = EXP_DIR.parents[1]
DEFAULT_GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
DEFAULT_PROFILES = EXP_DIR / "configs" / "style_profiles.json"
DEFAULT_TASKS = EXP_DIR / "configs" / "demo_tasks.json"
DEFAULT_MODIFIER_TASKS = EXP_DIR / "configs" / "modifier_demo_tasks.json"
DEFAULT_MODIFIER_ABLATION_TASKS = EXP_DIR / "configs" / "modifier_ablation_tasks.json"
DEFAULT_MODIFIER_SHAPE_SMOOTHNESS_TASKS = EXP_DIR / "configs" / "modifier_shape_smoothness_tasks.json"
DEFAULT_BRUSH_PROFILES = EXP_DIR / "configs" / "brush_profiles.json"
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
    "planner_mode",
    "trajectory_csv",
    "preview_png",
    "plan_json",
]
MODIFIER_SUMMARY_FIELDS = [
    "task",
    "char",
    "style",
    "style_modifiers",
    "connection_preference",
    "shape_emphasis",
    "smoothness_level",
    "stroke_width_level",
    "smoothness",
    "corner_rounding",
    "horizontal_scale",
    "vertical_scale",
    "connection_strength",
    "allow_interstroke_connections",
    "brush_base_width",
    "brush_min_width",
    "brush_max_width",
    "bbox_width",
    "bbox_height",
    "connection_count",
    "pen_up_count",
    "mean_turning",
    "total_turning_angle",
    "max_turning_angle",
    "aspect_ratio",
    "path_length",
    "stroke_draw_length",
    "connector_draw_length",
    "pen_up_move_length",
    "mean_pressure",
    "mean_width",
    "connector_mean_pressure",
    "connector_mean_width",
    "execution_trajectory_csv",
    "execution_render_png",
    "execution_debug_png",
    "trajectory_csv",
    "preview_png",
    "plan_json",
]


def safe_task_id(char: str, style: str) -> str:
    return f"u{ord(char):04x}_{style}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"


def safe_char_id(char: str) -> str:
    return f"u{ord(char):04x}"


def relabel_variants_for_modifier_context(
    summaries: list[dict],
    variants: list[tuple[str, list]],
    modifier_key: str,
    default_label: str,
) -> list[tuple[str, list]]:
    relabeled: list[tuple[str, list]] = []
    for summary, (_, styled) in zip(summaries, variants):
        modifiers = summary.get("style_modifiers", {}) if isinstance(summary.get("style_modifiers"), dict) else {}
        label = str(modifiers.get(modifier_key) or default_label)
        relabeled.append((label, styled))
    return relabeled


def run_task(
    task_text: str,
    output_root: Path | str = DEFAULT_OUTPUT,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    image_size: int = 256,
    planner_mode: str = "mock",
    fallback_to_mock: bool = False,
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
) -> dict[str, str]:
    profiles = load_style_profiles(style_profiles_path)
    brush_profiles = load_brush_profiles(brush_profiles_path)
    plan = plan_task(
        task_text,
        mode=planner_mode,
        style_profiles=profiles,
        graphics_path=graphics_path,
        fallback_to_mock=fallback_to_mock,
    )
    if not plan.get("validation", {}).get("ok", False):
        errors = "; ".join(str(item) for item in plan.get("validation", {}).get("errors", []))
        warnings = "; ".join(str(item) for item in plan.get("warnings", []))
        raise ValueError(errors or warnings or "planner validation failed")
    base_brush = brush_profiles.get(plan["style"], brush_profiles.get("default", {}))
    brush_params = apply_style_modifiers_to_brush_params(base_brush, plan.get("style_modifiers", {}))
    knowledge = MakeMeAHanziKnowledge(graphics_path)
    glyph = knowledge.get_glyph(plan["char"])

    raw_strokes = normalize_medians(glyph.medians, image_size=image_size)
    styled_strokes = build_styled_trajectory(raw_strokes, plan["style_params"], image_size=image_size)

    out_dir = Path(output_root) / safe_task_id(plan["char"], plan["style"])
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir / "plan.json"
    csv_path = out_dir / "trajectory.csv"
    execution_csv_path = out_dir / "execution_trajectory.csv"
    execution_render_path = out_dir / "execution_render.png"
    execution_debug_path = out_dir / "execution_debug.png"
    preview_path = out_dir / "preview.png"
    summary_path = out_dir / "summary.json"

    plan_payload = dict(plan)
    plan_payload["stroke_plan"] = dict(plan_payload["stroke_plan"])
    plan_payload["stroke_plan"]["stroke_count"] = glyph.stroke_count
    plan_payload["brush_params"] = brush_params
    plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_trajectory_csv(styled_strokes, csv_path)
    write_preview(raw_strokes, styled_strokes, preview_path, f"{plan['char']} {plan['style']}", image_size)
    execution_rows = build_execution_trajectory(
        raw_strokes,
        plan["style_params"],
        brush_params,
        plan.get("style_modifiers", {}),
        image_size=image_size,
    )
    write_execution_csv(execution_rows, execution_csv_path)
    render_execution(execution_rows, execution_render_path, image_size=image_size)
    render_execution_debug(execution_rows, execution_debug_path, image_size=image_size)

    metrics = trajectory_metrics(
        styled_strokes,
        image_size=image_size,
        stroke_count=glyph.stroke_count,
        connection_strength=float(plan["style_params"].get("connection_strength", 0.0)),
        allow_interstroke_connections=bool(plan["style_params"].get("allow_interstroke_connections", False)),
    )
    exec_metrics = execution_metrics(execution_rows)
    summary = {
        "task": task_text,
        "char": plan["char"],
        "style": plan["style"],
        "stroke_count": glyph.stroke_count,
        "raw_points": sum(len(stroke) for stroke in raw_strokes),
        "styled_points": metrics["point_count"],
        **metrics,
        **exec_metrics,
        "planner_mode": plan["planner_mode"],
        "style_modifiers": plan["style_modifiers"],
        "style_params": plan["style_params"],
        "brush_params": brush_params,
        "trajectory_csv": str(csv_path),
        "execution_trajectory_csv": str(execution_csv_path),
        "execution_render_png": str(execution_render_path),
        "execution_debug_png": str(execution_debug_path),
        "preview_png": str(preview_path),
        "plan_json": str(plan_path)
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "plan_json": str(plan_path),
        "trajectory_csv": str(csv_path),
        "execution_trajectory_csv": str(execution_csv_path),
        "execution_render_png": str(execution_render_path),
        "execution_debug_png": str(execution_debug_path),
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


def _write_modifier_summary(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MODIFIER_SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            style_params = row.get("style_params", {}) if isinstance(row.get("style_params"), dict) else {}
            brush_params = row.get("brush_params", {}) if isinstance(row.get("brush_params"), dict) else {}
            modifiers = row.get("style_modifiers", {}) if isinstance(row.get("style_modifiers"), dict) else {}
            writer.writerow(
                {
                    "task": row.get("task", ""),
                    "char": row.get("char", ""),
                    "style": row.get("style", ""),
                    "style_modifiers": json.dumps(modifiers, ensure_ascii=False, sort_keys=True),
                    "connection_preference": modifiers.get("connection_preference", ""),
                    "shape_emphasis": modifiers.get("shape_emphasis", ""),
                    "smoothness_level": modifiers.get("smoothness_level", ""),
                    "stroke_width_level": modifiers.get("stroke_width_level", ""),
                    "smoothness": style_params.get("smoothness", ""),
                    "corner_rounding": style_params.get("corner_rounding", ""),
                    "horizontal_scale": style_params.get("horizontal_scale", ""),
                    "vertical_scale": style_params.get("vertical_scale", ""),
                    "connection_strength": style_params.get("connection_strength", ""),
                    "allow_interstroke_connections": style_params.get("allow_interstroke_connections", ""),
                    "brush_base_width": brush_params.get("base_width", ""),
                    "brush_min_width": brush_params.get("min_width", ""),
                    "brush_max_width": brush_params.get("max_width", ""),
                    "bbox_width": row.get("bounding_box_width", ""),
                    "bbox_height": row.get("bounding_box_height", ""),
                    "connection_count": row.get("connection_count", ""),
                    "pen_up_count": row.get("pen_up_count", ""),
                    "mean_turning": row.get("mean_turning", ""),
                    "total_turning_angle": row.get("total_turning_angle", ""),
                    "max_turning_angle": row.get("max_turning_angle", ""),
                    "aspect_ratio": row.get("aspect_ratio", ""),
                    "path_length": row.get("path_length", ""),
                    "stroke_draw_length": row.get("stroke_draw_length", ""),
                    "connector_draw_length": row.get("connector_draw_length", ""),
                    "pen_up_move_length": row.get("pen_up_move_length", ""),
                    "mean_pressure": row.get("mean_pressure", ""),
                    "mean_width": row.get("mean_width", ""),
                    "connector_mean_pressure": row.get("connector_mean_pressure", ""),
                    "connector_mean_width": row.get("connector_mean_width", ""),
                    "execution_trajectory_csv": row.get("execution_trajectory_csv", ""),
                    "execution_render_png": row.get("execution_render_png", ""),
                    "execution_debug_png": row.get("execution_debug_png", ""),
                    "trajectory_csv": row.get("trajectory_csv", ""),
                    "preview_png": row.get("preview_png", ""),
                    "plan_json": row.get("plan_json", ""),
                }
            )


def run_batch(
    tasks: list[str],
    output_root: Path | str = DEFAULT_OUTPUT,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    image_size: int = 256,
    planner_mode: str = "mock",
    fallback_to_mock: bool = False,
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
) -> dict[str, object]:
    batch_dir = Path(output_root) / _batch_id()
    batch_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, str]] = []
    summaries: list[dict] = []
    by_char_style: dict[str, dict[str, list]] = {}
    by_char_variant: dict[str, list[tuple[str, list]]] = {}
    execution_by_char_variant: dict[str, list[tuple[str, Path]]] = {}
    raw_by_char: dict[str, list] = {}

    knowledge = MakeMeAHanziKnowledge(graphics_path)

    for task in tasks:
        result = run_task(
            task_text=task,
            output_root=batch_dir,
            graphics_path=graphics_path,
            style_profiles_path=style_profiles_path,
            image_size=image_size,
            planner_mode=planner_mode,
            fallback_to_mock=fallback_to_mock,
            brush_profiles_path=brush_profiles_path,
        )
        results.append(result)
        summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
        summaries.append(summary)

        char = str(summary["char"])
        style = str(summary["style"])
        if char not in raw_by_char:
            glyph = knowledge.get_glyph(char)
            raw_by_char[char] = normalize_medians(glyph.medians, image_size=image_size)
        plan_payload = json.loads(Path(result["plan_json"]).read_text(encoding="utf-8"))
        styled = build_styled_trajectory(raw_by_char[char], plan_payload["style_params"], image_size=image_size)
        by_char_style.setdefault(char, {})[style] = styled
        modifiers = summary.get("style_modifiers", {}) if isinstance(summary.get("style_modifiers"), dict) else {}
        label = str(modifiers.get("connection_preference") or style)
        if modifiers.get("smoothness_level") not in {None, "", "medium"}:
            label += f" / {modifiers.get('smoothness_level')}"
        by_char_variant.setdefault(char, []).append((label, styled))
        execution_by_char_variant.setdefault(char, []).append((label, Path(summary["execution_render_png"])))

    summary_csv = batch_dir / "batch_summary.csv"
    modifier_summary_csv = batch_dir / "modifier_summary.csv"
    _write_batch_summary(summaries, summary_csv)
    _write_modifier_summary(summaries, modifier_summary_csv)

    compare_paths: dict[str, str] = {}
    for char, style_map in by_char_style.items():
        if len(style_map) < 2:
            continue
        compare_path = batch_dir / f"compare_{safe_char_id(char)}.png"
        write_style_compare(raw_by_char[char], style_map, compare_path, image_size=image_size)
        compare_paths[char] = str(compare_path)

    ablation_compare_paths: dict[str, str] = {}
    execution_compare_paths: dict[str, str] = {}
    shape_compare_paths: dict[str, str] = {}
    smoothness_compare_paths: dict[str, str] = {}
    for char, variants in by_char_variant.items():
        if len(variants) < 2:
            continue
        compare_path = batch_dir / f"modifier_ablation_{safe_char_id(char)}.png"
        write_labeled_compare(raw_by_char[char], variants, compare_path, image_size=image_size)
        ablation_compare_paths[char] = str(compare_path)
        execution_path = batch_dir / f"execution_ablation_{safe_char_id(char)}.png"
        write_execution_compare(execution_by_char_variant.get(char, []), execution_path)
        execution_compare_paths[char] = str(execution_path)

        char_summaries = [row for row in summaries if str(row.get("char", "")) == char]
        if any(
            isinstance(row.get("style_modifiers"), dict)
            and row["style_modifiers"].get("shape_emphasis") in {"flatter", "wider"}
            for row in char_summaries
        ):
            shape_path = batch_dir / f"modifier_ablation_shape_{safe_char_id(char)}.png"
            shape_variants = relabel_variants_for_modifier_context(
                char_summaries,
                variants,
                modifier_key="shape_emphasis",
                default_label="normal",
            )
            write_labeled_compare(raw_by_char[char], shape_variants, shape_path, image_size=image_size)
            shape_compare_paths[char] = str(shape_path)
        if any(
            isinstance(row.get("style_modifiers"), dict)
            and row["style_modifiers"].get("smoothness_level") in {"low", "high"}
            for row in char_summaries
        ):
            smoothness_path = batch_dir / f"modifier_ablation_smoothness_{safe_char_id(char)}.png"
            write_labeled_compare(raw_by_char[char], variants, smoothness_path, image_size=image_size)
            smoothness_compare_paths[char] = str(smoothness_path)

    return {
        "batch_dir": str(batch_dir),
        "batch_summary_csv": str(summary_csv),
        "modifier_summary_csv": str(modifier_summary_csv),
        "compare_images": compare_paths,
        "ablation_compare_images": ablation_compare_paths,
        "execution_compare_images": execution_compare_paths,
        "shape_compare_images": shape_compare_paths,
        "smoothness_compare_images": smoothness_compare_paths,
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
    parser.add_argument("--brush-profiles", default=str(DEFAULT_BRUSH_PROFILES))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--planner-mode", choices=["mock", "api", "local"], default="mock")
    parser.add_argument("--fallback-to-mock", action="store_true")
    parser.add_argument("--modifier-demo", action="store_true")
    parser.add_argument("--modifier-ablation", action="store_true")
    parser.add_argument("--modifier-shape-smoothness", action="store_true")
    args = parser.parse_args()
    style_profile_path = args.style_profile or args.style_profiles

    if args.modifier_shape_smoothness and not args.tasks_file and not args.task:
        tasks = _load_tasks(DEFAULT_MODIFIER_SHAPE_SMOOTHNESS_TASKS)
    elif args.modifier_ablation and not args.tasks_file and not args.task:
        tasks = _load_tasks(DEFAULT_MODIFIER_ABLATION_TASKS)
    elif args.modifier_demo and not args.tasks_file and not args.task:
        tasks = _load_tasks(DEFAULT_MODIFIER_TASKS)
    elif args.tasks_file:
        tasks = _load_tasks(Path(args.tasks_file))
    elif args.task:
        tasks = [args.task]
    else:
        tasks = _load_tasks(DEFAULT_TASKS)

    try:
        if args.task and not args.tasks_file:
            result = run_task(
                task_text=tasks[0],
                output_root=args.out_dir,
                graphics_path=args.graphics,
                style_profiles_path=style_profile_path,
                image_size=args.image_size,
                planner_mode=args.planner_mode,
                fallback_to_mock=args.fallback_to_mock,
                brush_profiles_path=args.brush_profiles,
            )
        else:
            result = run_batch(
                tasks=tasks,
                output_root=args.out_dir,
                graphics_path=args.graphics,
                style_profiles_path=style_profile_path,
                image_size=args.image_size,
                planner_mode=args.planner_mode,
                fallback_to_mock=args.fallback_to_mock,
                brush_profiles_path=args.brush_profiles,
            )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
