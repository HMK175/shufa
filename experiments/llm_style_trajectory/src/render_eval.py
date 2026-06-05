"""Render generated trajectories and evaluate them against style font targets."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import cv2
import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PIL import Image

from build_style_profiles import load_style_sources, render_char_with_font


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STYLE_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_BRUSH_PROFILES = EXP_DIR / "configs" / "brush_profiles.json"
DEFAULT_BATCH = EXP_DIR / "outputs" / "batch_20260601_135226"
EVAL_FIELDS = [
    "demo_dir",
    "renderer",
    "char",
    "style",
    "target_render_success",
    "iou",
    "chamfer_distance",
    "bbox_width",
    "bbox_height",
    "aspect_ratio",
    "target_bbox_width",
    "target_bbox_height",
    "target_aspect_ratio",
    "aspect_ratio_error",
    "center_offset",
    "foreground_ratio_rendered",
    "foreground_ratio_target",
    "out_of_bounds",
    "stroke_count",
    "pen_up_count",
    "point_count",
    "rendered_trajectory_png",
    "target_style_png",
    "render_eval_overlay_png",
    "render_eval_summary_json",
    "note",
]
BRUSH_KEYS = [
    "base_width",
    "min_width",
    "max_width",
    "start_taper",
    "end_taper",
    "turn_width_gain",
    "horizontal_width_gain",
    "vertical_width_gain",
    "antialias_scale",
]


def _resolve_path(path_text: str, config_dir: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (config_dir / path).resolve()


def _first_existing_font(paths: list[str], config_dir: Path) -> tuple[Path | None, list[Path]]:
    resolved = [_resolve_path(path_text, config_dir) for path_text in paths]
    for path in resolved:
        if path.exists():
            return path, resolved
    return None, resolved


def load_trajectory_csv(path: Path | str) -> list[np.ndarray]:
    strokes: list[np.ndarray] = []
    current: list[tuple[float, float]] = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            y_text = str(row.get("y", "")).strip().lower()
            x_text = str(row.get("x", "")).strip().lower()
            if y_text == "nan" or x_text == "nan" or not y_text or not x_text:
                if current:
                    strokes.append(np.asarray(current, dtype=float))
                    current = []
                continue
            current.append((float(y_text), float(x_text)))
    if current:
        strokes.append(np.asarray(current, dtype=float))
    return strokes


def load_brush_profiles(path: Path | str = DEFAULT_BRUSH_PROFILES) -> dict[str, dict[str, float]]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    profiles: dict[str, dict[str, float]] = {}
    for style, params in data.items():
        profiles[style] = {key: float(params[key]) for key in BRUSH_KEYS if key in params}
    if "default" not in profiles:
        profiles["default"] = {
            "base_width": 8.0,
            "min_width": 3.0,
            "max_width": 14.0,
            "start_taper": 0.12,
            "end_taper": 0.12,
            "turn_width_gain": 0.22,
            "horizontal_width_gain": 0.0,
            "vertical_width_gain": 0.0,
            "antialias_scale": 3.0,
        }
    return profiles


def trajectory_point_stats(strokes: list[np.ndarray], canvas_size: int) -> dict[str, Any]:
    point_count = int(sum(len(stroke) for stroke in strokes))
    stroke_count = int(len(strokes))
    pen_up_count = max(0, stroke_count - 1)
    out_of_bounds = False
    for stroke in strokes:
        if len(stroke) == 0:
            continue
        pts = np.asarray(stroke, dtype=float)
        if (
            np.any(pts[:, 0] < 0.0)
            or np.any(pts[:, 1] < 0.0)
            or np.any(pts[:, 0] > canvas_size - 1)
            or np.any(pts[:, 1] > canvas_size - 1)
        ):
            out_of_bounds = True
            break
    return {
        "point_count": point_count,
        "stroke_count": stroke_count,
        "pen_up_count": pen_up_count,
        "trajectory_out_of_bounds": out_of_bounds,
    }


def render_trajectory_mask(
    strokes: list[np.ndarray],
    canvas_size: int = 256,
    stroke_width: int = 8,
    draw_mode: str = "line",
) -> np.ndarray:
    mask = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
    line_type = cv2.LINE_AA if draw_mode == "antialias" else cv2.LINE_8
    width = max(1, int(stroke_width))
    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float)
        if len(pts) == 0:
            continue
        rounded = np.rint(pts).astype(int)
        rounded[:, 0] = np.clip(rounded[:, 0], 0, canvas_size - 1)
        rounded[:, 1] = np.clip(rounded[:, 1], 0, canvas_size - 1)
        if len(rounded) == 1:
            y, x = rounded[0]
            cv2.circle(mask, (int(x), int(y)), max(1, width // 2), 255, thickness=-1, lineType=line_type)
            continue
        for p0, p1 in zip(rounded[:-1], rounded[1:]):
            y0, x0 = p0
            y1, x1 = p1
            cv2.line(mask, (int(x0), int(y0)), (int(x1), int(y1)), 255, thickness=width, lineType=line_type)
    return np.where(mask > 0, 255, 0).astype(np.uint8)


def _point_turning(stroke: np.ndarray) -> np.ndarray:
    pts = np.asarray(stroke, dtype=float)
    turns = np.zeros(len(pts), dtype=float)
    if len(pts) < 3:
        return turns
    prev_vec = pts[1:-1] - pts[:-2]
    next_vec = pts[2:] - pts[1:-1]
    prev_norm = np.linalg.norm(prev_vec, axis=1)
    next_norm = np.linalg.norm(next_vec, axis=1)
    keep = (prev_norm > 1e-9) & (next_norm > 1e-9)
    if not np.any(keep):
        return turns
    dots = np.sum(prev_vec[keep] * next_vec[keep], axis=1) / (prev_norm[keep] * next_norm[keep])
    angles = np.arccos(np.clip(dots, -1.0, 1.0))
    turns[1:-1][keep] = angles / math.pi
    return turns


def _point_tangent(stroke: np.ndarray) -> np.ndarray:
    pts = np.asarray(stroke, dtype=float)
    tangent = np.zeros_like(pts, dtype=float)
    if len(pts) == 1:
        return tangent
    tangent[0] = pts[1] - pts[0]
    tangent[-1] = pts[-1] - pts[-2]
    if len(pts) > 2:
        tangent[1:-1] = pts[2:] - pts[:-2]
    return tangent


def compute_brush_widths(stroke: np.ndarray, brush: dict[str, float]) -> np.ndarray:
    pts = np.asarray(stroke, dtype=float)
    if len(pts) == 0:
        return np.asarray([], dtype=float)
    base = float(brush.get("base_width", 8.0))
    min_w = float(brush.get("min_width", 3.0))
    max_w = float(brush.get("max_width", 14.0))
    widths = np.full(len(pts), base, dtype=float)

    tangent = _point_tangent(pts)
    denom = np.abs(tangent[:, 0]) + np.abs(tangent[:, 1]) + 1e-9
    vertical = np.abs(tangent[:, 0]) / denom
    horizontal = np.abs(tangent[:, 1]) / denom
    widths *= 1.0 + float(brush.get("horizontal_width_gain", 0.0)) * horizontal
    widths *= 1.0 + float(brush.get("vertical_width_gain", 0.0)) * vertical

    turns = _point_turning(pts)
    widths += base * float(brush.get("turn_width_gain", 0.0)) * turns

    if len(pts) > 1:
        progress = np.linspace(0.0, 1.0, len(pts))
        start_span = max(float(brush.get("start_taper", 0.0)), 1e-6)
        end_span = max(float(brush.get("end_taper", 0.0)), 1e-6)
        start_factor = np.minimum(1.0, progress / start_span)
        end_factor = np.minimum(1.0, (1.0 - progress) / end_span)
        taper = 0.52 + 0.48 * np.minimum(start_factor, end_factor)
        widths *= taper

    return np.clip(widths, min_w, max_w)


def render_style_brush_mask(
    strokes: list[np.ndarray],
    brush: dict[str, float],
    canvas_size: int = 256,
) -> np.ndarray:
    scale = max(1, int(round(float(brush.get("antialias_scale", 1.0)))))
    high_size = canvas_size * scale
    canvas = np.zeros((high_size, high_size), dtype=np.uint8)

    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float)
        if len(pts) == 0:
            continue
        widths = compute_brush_widths(pts, brush)
        pts_scaled = np.rint(pts * scale).astype(int)
        pts_scaled[:, 0] = np.clip(pts_scaled[:, 0], 0, high_size - 1)
        pts_scaled[:, 1] = np.clip(pts_scaled[:, 1], 0, high_size - 1)
        widths_scaled = np.maximum(1, np.rint(widths * scale).astype(int))
        for idx, (y, x) in enumerate(pts_scaled):
            radius = max(1, int(widths_scaled[idx] // 2))
            cv2.circle(canvas, (int(x), int(y)), radius, 255, thickness=-1, lineType=cv2.LINE_AA)
        for idx, (p0, p1) in enumerate(zip(pts_scaled[:-1], pts_scaled[1:])):
            y0, x0 = p0
            y1, x1 = p1
            width = max(1, int(round((widths_scaled[idx] + widths_scaled[idx + 1]) * 0.5)))
            cv2.line(canvas, (int(x0), int(y0)), (int(x1), int(y1)), 255, thickness=width, lineType=cv2.LINE_AA)

    if scale > 1:
        canvas = cv2.resize(canvas, (canvas_size, canvas_size), interpolation=cv2.INTER_AREA)
    return np.where(canvas >= 64, 255, 0).astype(np.uint8)


def render_strokes(
    strokes: list[np.ndarray],
    style: str,
    renderer: str,
    brush_profiles: dict[str, dict[str, float]],
    canvas_size: int,
    stroke_width: int,
    draw_mode: str,
) -> np.ndarray:
    if renderer == "fixed":
        return render_trajectory_mask(strokes, canvas_size=canvas_size, stroke_width=stroke_width, draw_mode=draw_mode)
    if renderer == "style_brush":
        brush = brush_profiles.get(style, brush_profiles.get("default", {}))
        return render_style_brush_mask(strokes, brush, canvas_size=canvas_size)
    raise ValueError(f"Unsupported renderer: {renderer}")


def _save_mask_png(mask: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(255 - np.where(mask > 0, 255, 0).astype(np.uint8)).save(path)


def mask_bbox_metrics(mask: np.ndarray) -> dict[str, Any]:
    binary = np.asarray(mask) > 0
    h, w = binary.shape[:2]
    if not np.any(binary):
        return {
            "bbox_width": 0,
            "bbox_height": 0,
            "aspect_ratio": 0.0,
            "center_x": 0.0,
            "center_y": 0.0,
            "foreground_ratio": 0.0,
            "out_of_bounds": False,
        }
    ys, xs = np.nonzero(binary)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    bbox_w = int(x1 - x0 + 1)
    bbox_h = int(y1 - y0 + 1)
    return {
        "bbox_width": bbox_w,
        "bbox_height": bbox_h,
        "aspect_ratio": round(bbox_w / bbox_h if bbox_h else 0.0, 6),
        "center_x": round(float(xs.mean() / max(w - 1, 1)), 6),
        "center_y": round(float(ys.mean() / max(h - 1, 1)), 6),
        "foreground_ratio": round(float(binary.mean()), 6),
        "out_of_bounds": bool(x0 <= 0 or y0 <= 0 or x1 >= w - 1 or y1 >= h - 1),
    }


def chamfer_distance(mask_a: np.ndarray, mask_b: np.ndarray) -> float | None:
    a = np.asarray(mask_a) > 0
    b = np.asarray(mask_b) > 0
    if not np.any(a) or not np.any(b):
        return None
    dist_to_b = cv2.distanceTransform((~b).astype(np.uint8), cv2.DIST_L2, 3)
    dist_to_a = cv2.distanceTransform((~a).astype(np.uint8), cv2.DIST_L2, 3)
    return round(float((dist_to_b[a].mean() + dist_to_a[b].mean()) * 0.5), 6)


def compute_render_eval_metrics(rendered: np.ndarray, target: np.ndarray) -> dict[str, Any]:
    rendered_mask = np.asarray(rendered) > 0
    target_mask = np.asarray(target) > 0
    union = np.logical_or(rendered_mask, target_mask).sum()
    inter = np.logical_and(rendered_mask, target_mask).sum()
    rendered_bbox = mask_bbox_metrics(rendered)
    target_bbox = mask_bbox_metrics(target)
    chamfer = chamfer_distance(rendered, target)
    center_offset = math.hypot(
        float(rendered_bbox["center_x"]) - float(target_bbox["center_x"]),
        float(rendered_bbox["center_y"]) - float(target_bbox["center_y"]),
    )
    return {
        "iou": round(float(inter / union), 6) if union else 0.0,
        "chamfer_distance": chamfer,
        "bbox_width": rendered_bbox["bbox_width"],
        "bbox_height": rendered_bbox["bbox_height"],
        "aspect_ratio": rendered_bbox["aspect_ratio"],
        "target_bbox_width": target_bbox["bbox_width"],
        "target_bbox_height": target_bbox["bbox_height"],
        "target_aspect_ratio": target_bbox["aspect_ratio"],
        "aspect_ratio_error": round(abs(float(rendered_bbox["aspect_ratio"]) - float(target_bbox["aspect_ratio"])), 6),
        "center_offset": round(float(center_offset), 6),
        "foreground_ratio_rendered": rendered_bbox["foreground_ratio"],
        "foreground_ratio_target": target_bbox["foreground_ratio"],
        "out_of_bounds": bool(rendered_bbox["out_of_bounds"]),
    }


def render_target_style(
    char: str,
    style: str,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    canvas_size: int = 256,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    sources_path = Path(style_sources_path)
    sources = load_style_sources(sources_path)
    style_spec = sources.get(style)
    if not style_spec:
        return None, {"target_render_success": False, "source_path": "", "note": f"style not configured: {style}"}
    font_path, checked = _first_existing_font(style_spec.get("font_paths", []), sources_path.parent)
    if font_path is None:
        return None, {
            "target_render_success": False,
            "source_path": "",
            "note": "missing fonts: " + "; ".join(str(path) for path in checked),
        }
    try:
        target = render_char_with_font(char, font_path, canvas_size)
    except Exception as exc:
        return None, {"target_render_success": False, "source_path": str(font_path), "note": f"render failed: {exc}"}
    return target, {"target_render_success": True, "source_path": str(font_path), "note": ""}


def write_overlay(rendered: np.ndarray, target: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    r = np.asarray(rendered) > 0
    t = np.asarray(target) > 0
    img = np.full((*r.shape, 3), 255, dtype=np.uint8)
    img[t] = np.array([120, 170, 235], dtype=np.uint8)
    img[r] = np.array([235, 70, 70], dtype=np.uint8)
    img[np.logical_and(r, t)] = np.array([65, 45, 105], dtype=np.uint8)
    Image.fromarray(img).save(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _blank_mask(canvas_size: int) -> np.ndarray:
    return np.zeros((canvas_size, canvas_size), dtype=np.uint8)


def evaluate_demo_dir(
    demo_dir: Path | str,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    canvas_size: int = 256,
    stroke_width: int = 8,
    draw_mode: str = "line",
    renderer: str = "fixed",
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
) -> dict[str, Any]:
    root = Path(demo_dir)
    plan = _load_json(root / "plan.json")
    summary = _load_json(root / "summary.json")
    char = str(plan.get("char", ""))
    style = str(plan.get("style", ""))

    strokes = load_trajectory_csv(root / "trajectory.csv")
    brush_profiles = load_brush_profiles(brush_profiles_path)
    rendered = render_strokes(
        strokes,
        style=style,
        renderer=renderer,
        brush_profiles=brush_profiles,
        canvas_size=canvas_size,
        stroke_width=stroke_width,
        draw_mode=draw_mode,
    )
    target, target_info = render_target_style(char, style, style_sources_path, canvas_size=canvas_size)
    if target is None:
        target = _blank_mask(canvas_size)

    suffix = "style_brush" if renderer == "style_brush" else "fixed"
    rendered_path = root / f"rendered_trajectory_{suffix}.png"
    target_path = root / "target_style.png"
    overlay_path = root / f"render_eval_{suffix}_overlay.png"
    summary_path = root / f"render_eval_{suffix}_summary.json"
    _save_mask_png(rendered, rendered_path)
    _save_mask_png(target, target_path)
    write_overlay(rendered, target, overlay_path)

    point_stats = trajectory_point_stats(strokes, canvas_size=canvas_size)
    metrics = compute_render_eval_metrics(rendered, target)
    metrics["out_of_bounds"] = bool(metrics["out_of_bounds"] or point_stats["trajectory_out_of_bounds"])
    stroke_count = int(summary.get("stroke_count") or plan.get("stroke_plan", {}).get("stroke_count") or point_stats["stroke_count"])
    pen_up_count = int(summary.get("pen_up_count") if summary.get("pen_up_count") is not None else max(0, stroke_count - 1))
    row = {
        "demo_dir": str(root),
        "renderer": renderer,
        "char": char,
        "style": style,
        "target_render_success": bool(target_info["target_render_success"]),
        **metrics,
        "stroke_count": stroke_count,
        "pen_up_count": pen_up_count,
        "point_count": int(summary.get("point_count") or summary.get("styled_points") or point_stats["point_count"]),
        "rendered_trajectory_png": str(rendered_path),
        "target_style_png": str(target_path),
        "render_eval_overlay_png": str(overlay_path),
        "render_eval_summary_json": str(summary_path),
        "note": target_info.get("note", ""),
    }
    summary_path.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    return row


def _write_eval_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EVAL_FIELDS)
        writer.writeheader()
        for row in rows:
            out = {field: row.get(field, "") for field in EVAL_FIELDS}
            if out["chamfer_distance"] is None:
                out["chamfer_distance"] = ""
            writer.writerow(out)


def write_render_compare(rows: list[dict[str, Any]], path: Path, canvas_size: int = 256) -> None:
    styles = [style for style in ["kaishu", "xingkai", "lishu"] if any(row["style"] == style for row in rows)]
    if not styles:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = Figure(figsize=(4.0 * len(styles), 4.2), dpi=140)
    canvas = FigureCanvas(fig)
    for idx, style in enumerate(styles):
        row = next(item for item in rows if item["style"] == style)
        left = 0.05 + idx * (0.9 / len(styles))
        ax = fig.add_axes([left, 0.08, 0.78 / len(styles), 0.78])
        ax.set_title(
            f"{style}\nIoU {float(row['iou']):.3f} / CD {row['chamfer_distance'] if row['chamfer_distance'] is not None else 'NA'}",
            fontsize=8,
        )
        ax.axis("off")
        overlay = Image.open(row["render_eval_overlay_png"]).convert("RGB")
        ax.imshow(overlay)
    canvas.print_png(str(path))


def write_fixed_brush_compare(fixed_rows: list[dict[str, Any]], brush_rows: list[dict[str, Any]], path: Path) -> None:
    styles = [style for style in ["kaishu", "xingkai", "lishu"] if any(row["style"] == style for row in brush_rows)]
    if not styles:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fixed_by_style = {row["style"]: row for row in fixed_rows}
    brush_by_style = {row["style"]: row for row in brush_rows}
    fig = Figure(figsize=(4.0 * len(styles), 7.0), dpi=140)
    canvas = FigureCanvas(fig)
    for col, style in enumerate(styles):
        for row_idx, renderer_name in enumerate(["fixed", "style_brush"]):
            source = fixed_by_style if renderer_name == "fixed" else brush_by_style
            row = source.get(style)
            left = 0.05 + col * (0.9 / len(styles))
            bottom = 0.53 if row_idx == 0 else 0.08
            ax = fig.add_axes([left, bottom, 0.78 / len(styles), 0.36])
            ax.axis("off")
            if row is None:
                ax.text(0.5, 0.5, f"{style}\n{renderer_name}\nmissing", ha="center", va="center")
                continue
            ax.set_title(
                f"{style} {renderer_name}\nIoU {float(row['iou']):.3f} / CD {row['chamfer_distance'] if row['chamfer_distance'] is not None else 'NA'}",
                fontsize=8,
            )
            overlay = Image.open(row["render_eval_overlay_png"]).convert("RGB")
            ax.imshow(overlay)
    canvas.print_png(str(path))


def evaluate_batch(
    batch_dir: Path | str,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    canvas_size: int = 256,
    stroke_width: int = 8,
    draw_mode: str = "line",
    renderer: str = "fixed",
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
) -> dict[str, Any]:
    root = Path(batch_dir)
    rows: list[dict[str, Any]] = []
    for demo_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if not (demo_dir / "trajectory.csv").exists():
            continue
        rows.append(
            evaluate_demo_dir(
                demo_dir,
                style_sources_path=style_sources_path,
                canvas_size=canvas_size,
                stroke_width=stroke_width,
                draw_mode=draw_mode,
                renderer=renderer,
                brush_profiles_path=brush_profiles_path,
            )
        )

    suffix = "style_brush" if renderer == "style_brush" else "fixed"
    summary_path = root / f"render_eval_{suffix}_summary.csv"
    _write_eval_csv(rows, summary_path)
    compare_paths: dict[str, str] = {}
    chars = sorted({str(row["char"]) for row in rows})
    for char in chars:
        char_rows = [row for row in rows if row["char"] == char]
        if len(char_rows) < 2:
            continue
        compare_path = root / f"render_compare_{suffix}_u{ord(char):04x}.png"
        write_render_compare(char_rows, compare_path, canvas_size=canvas_size)
        compare_paths[char] = str(compare_path)

    return {
        "batch_dir": str(root),
        "render_eval_summary_csv": str(summary_path),
        "render_compare_images": compare_paths,
        "rows": rows,
    }


def evaluate_batch_both(
    batch_dir: Path | str,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    canvas_size: int = 256,
    stroke_width: int = 8,
    draw_mode: str = "line",
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
) -> dict[str, Any]:
    fixed = evaluate_batch(
        batch_dir,
        style_sources_path=style_sources_path,
        canvas_size=canvas_size,
        stroke_width=stroke_width,
        draw_mode=draw_mode,
        renderer="fixed",
        brush_profiles_path=brush_profiles_path,
    )
    brush = evaluate_batch(
        batch_dir,
        style_sources_path=style_sources_path,
        canvas_size=canvas_size,
        stroke_width=stroke_width,
        draw_mode=draw_mode,
        renderer="style_brush",
        brush_profiles_path=brush_profiles_path,
    )
    root = Path(batch_dir)
    compare_paths: dict[str, str] = {}
    chars = sorted({str(row["char"]) for row in brush["rows"]})
    for char in chars:
        fixed_rows = [row for row in fixed["rows"] if row["char"] == char]
        brush_rows = [row for row in brush["rows"] if row["char"] == char]
        if not fixed_rows or not brush_rows:
            continue
        compare_path = root / f"render_compare_brush_u{ord(char):04x}.png"
        write_fixed_brush_compare(fixed_rows, brush_rows, compare_path)
        compare_paths[char] = str(compare_path)
    return {
        "batch_dir": str(root),
        "fixed": fixed,
        "style_brush": brush,
        "render_compare_brush_images": compare_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render/evaluate LLM-style trajectory batch outputs.")
    parser.add_argument("batch_dir", nargs="?", default=str(DEFAULT_BATCH))
    parser.add_argument("--style-sources", default=str(DEFAULT_STYLE_SOURCES))
    parser.add_argument("--canvas-size", type=int, default=256)
    parser.add_argument("--stroke-width", type=int, default=8)
    parser.add_argument("--draw-mode", choices=["line", "antialias"], default="line")
    parser.add_argument("--renderer", choices=["fixed", "style_brush", "both"], default="fixed")
    parser.add_argument("--brush-profiles", default=str(DEFAULT_BRUSH_PROFILES))
    args = parser.parse_args()

    if args.renderer == "both":
        result = evaluate_batch_both(
            args.batch_dir,
            style_sources_path=args.style_sources,
            canvas_size=args.canvas_size,
            stroke_width=args.stroke_width,
            draw_mode=args.draw_mode,
            brush_profiles_path=args.brush_profiles,
        )
    else:
        result = evaluate_batch(
            args.batch_dir,
            style_sources_path=args.style_sources,
            canvas_size=args.canvas_size,
            stroke_width=args.stroke_width,
            draw_mode=args.draw_mode,
            renderer=args.renderer,
            brush_profiles_path=args.brush_profiles,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
