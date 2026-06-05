"""Build data-informed style profiles from local font or image sources."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.morphology import skeletonize


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_MANUAL_PROFILE = EXP_DIR / "configs" / "style_profiles.json"
DEFAULT_OUTPUT_ROOT = EXP_DIR / "outputs"
DEFAULT_CHARS = ["山", "中", "永", "人", "大", "口", "田", "水", "心", "飞"]
DEFAULT_PROFILE_KEYS = [
    "horizontal_scale",
    "vertical_scale",
    "smoothness",
    "corner_rounding",
    "connection_strength",
    "allow_interstroke_connections",
    "speed_scale",
    "pen_up_height",
]


def load_style_sources(path: Path | str) -> dict[str, dict[str, list[str]]]:
    source_path = Path(path)
    with source_path.open(encoding="utf-8") as f:
        data = json.load(f)
    out: dict[str, dict[str, list[str]]] = {}
    for style, spec in data.items():
        out[style] = {
            "font_paths": [str(item) for item in spec.get("font_paths", [])],
            "image_dirs": [str(item) for item in spec.get("image_dirs", [])],
        }
    return out


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


def render_char_with_font(char: str, font_path: Path, image_size: int) -> np.ndarray:
    font_size = max(8, int(image_size * 0.78))
    font = ImageFont.truetype(str(font_path), font_size)
    image = Image.new("L", (image_size, image_size), 255)
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), char, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (image_size - text_w) / 2.0 - bbox[0]
    y = (image_size - text_h) / 2.0 - bbox[1]
    draw.text((x, y), char, font=font, fill=0)
    arr = np.asarray(image)
    return np.where(arr < 200, 255, 0).astype(np.uint8)


def _turning_from_skeleton(binary: np.ndarray) -> float:
    mask = binary > 0
    if mask.sum() < 3:
        return 0.0
    skel = skeletonize(mask)
    pts = np.column_stack(np.nonzero(skel))
    if len(pts) < 3:
        return 0.0
    center = pts.mean(axis=0)
    rel = pts - center
    angles = np.arctan2(rel[:, 0], rel[:, 1])
    order = np.argsort(angles)
    ordered = pts[order].astype(float)
    delta = np.diff(ordered, axis=0)
    lengths = np.linalg.norm(delta, axis=1)
    delta = delta[lengths > 1e-9]
    if len(delta) < 2:
        return 0.0
    segment_angles = np.arctan2(delta[:, 0], delta[:, 1])
    diff = np.diff(segment_angles)
    diff = (diff + math.pi) % (2.0 * math.pi) - math.pi
    return float(np.mean(np.abs(diff))) if len(diff) else 0.0


def compute_binary_metrics(binary: np.ndarray) -> dict[str, Any]:
    img = np.asarray(binary)
    if img.ndim == 3:
        img = img[:, :, 0]
    mask = img > 0
    h, w = mask.shape[:2]
    if not np.any(mask):
        return {
            "render_success": False,
            "bbox_width": 0,
            "bbox_height": 0,
            "aspect_ratio": 0.0,
            "foreground_ratio": 0.0,
            "center_x": 0.0,
            "center_y": 0.0,
            "center_offset": 0.0,
            "estimated_stroke_width": 0.0,
            "connected_components": 0,
            "turning": 0.0,
            "out_of_bounds": False,
        }

    ys, xs = np.nonzero(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    bbox_w = int(x1 - x0 + 1)
    bbox_h = int(y1 - y0 + 1)
    center_x = float(xs.mean() / max(w - 1, 1))
    center_y = float(ys.mean() / max(h - 1, 1))
    center_offset = float(math.hypot(center_x - 0.5, center_y - 0.5))
    foreground_ratio = float(mask.mean())
    components, _labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    stroke_width = float(2.0 * np.median(dist[dist > 0])) if np.any(dist > 0) else 0.0
    out_of_bounds = bool(x0 <= 0 or y0 <= 0 or x1 >= w - 1 or y1 >= h - 1)
    return {
        "render_success": True,
        "bbox_width": bbox_w,
        "bbox_height": bbox_h,
        "aspect_ratio": round(bbox_w / bbox_h if bbox_h else 0.0, 6),
        "foreground_ratio": round(foreground_ratio, 6),
        "center_x": round(center_x, 6),
        "center_y": round(center_y, 6),
        "center_offset": round(center_offset, 6),
        "estimated_stroke_width": round(stroke_width, 3),
        "connected_components": int(components - 1),
        "turning": round(_turning_from_skeleton(img.astype(np.uint8)), 6),
        "out_of_bounds": out_of_bounds,
    }


def render_style_samples(
    sources: dict[str, dict[str, list[str]]],
    chars: list[str],
    image_size: int,
    output_dir: Path | str,
    config_dir: Path | str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config_root = Path(config_dir)
    rows: list[dict[str, Any]] = []
    rendered: list[dict[str, Any]] = []

    for style, spec in sources.items():
        font_path, checked_paths = _first_existing_font(spec.get("font_paths", []), config_root)
        if font_path is None:
            note = "missing fonts: " + "; ".join(str(path) for path in checked_paths)
            for char in chars:
                row = {
                    "style": style,
                    "char": char,
                    "source_type": "font",
                    "source_path": "",
                    "sample_path": "",
                    "note": note,
                    **compute_binary_metrics(np.zeros((image_size, image_size), dtype=np.uint8)),
                }
                rows.append(row)
            continue

        style_dir = output / style
        style_dir.mkdir(parents=True, exist_ok=True)
        for char in chars:
            try:
                binary = render_char_with_font(char, font_path, image_size=image_size)
                sample_path = style_dir / f"u{ord(char):04x}.png"
                Image.fromarray(255 - binary).save(sample_path)
                metrics = compute_binary_metrics(binary)
                row = {
                    "style": style,
                    "char": char,
                    "source_type": "font",
                    "source_path": str(font_path),
                    "sample_path": str(sample_path),
                    "note": "",
                    **metrics,
                }
                rows.append(row)
                if metrics["render_success"]:
                    rendered.append({"style": style, "char": char, "path": str(sample_path), "binary": binary})
            except Exception as exc:
                rows.append(
                    {
                        "style": style,
                        "char": char,
                        "source_type": "font",
                        "source_path": str(font_path),
                        "sample_path": "",
                        "note": f"render failed: {exc}",
                        **compute_binary_metrics(np.zeros((image_size, image_size), dtype=np.uint8)),
                    }
                )
    return rows, rendered


def _mean(rows: list[dict[str, Any]], key: str, default: float = 0.0) -> float:
    vals = [float(row[key]) for row in rows if row.get("render_success") and row.get(key) not in (None, "")]
    return float(np.mean(vals)) if vals else default


def _clip(value: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, value)))


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _connection_prior(style: str, manual: dict[str, Any]) -> tuple[float, bool]:
    if style in {"kaishu", "lishu"}:
        return 0.0, False
    strength = float(manual.get("connection_strength", 0.0))
    allow = _as_bool(manual.get("allow_interstroke_connections", strength > 0.0), default=strength > 0.0)
    return strength, allow


def _default_prior_specs(style: str, manual: dict[str, Any]) -> dict[str, dict[str, Any]]:
    connection_strength, allow_connections = _connection_prior(style, manual)
    specs: dict[str, dict[str, Any]] = {}
    for key in DEFAULT_PROFILE_KEYS:
        if key == "connection_strength":
            value: float | bool = connection_strength
        elif key == "allow_interstroke_connections":
            value = allow_connections
        else:
            value = manual.get(key, False if key == "allow_interstroke_connections" else 0.0)
        specs[key] = {"value": value, "source": "default_prior"}
    return specs


def build_estimated_profiles(
    metrics_rows: list[dict[str, Any]],
    manual_profiles: dict[str, dict[str, float]],
) -> dict[str, dict[str, Any]]:
    successful = [row for row in metrics_rows if row.get("render_success")]
    global_aspect = _mean(successful, "aspect_ratio", 1.0)
    global_turning = _mean(successful, "turning", 0.1)
    global_width = _mean(successful, "estimated_stroke_width", 8.0)
    if global_aspect <= 1e-9:
        global_aspect = 1.0
    if global_turning <= 1e-9:
        global_turning = 0.1
    if global_width <= 1e-9:
        global_width = 8.0

    styles = list(manual_profiles.keys())
    profile: dict[str, dict[str, Any]] = {}
    for style in styles:
        style_rows = [row for row in successful if row.get("style") == style]
        manual = manual_profiles[style]
        connection_strength, allow_connections = _connection_prior(style, manual)
        if style_rows:
            aspect = _mean(style_rows, "aspect_ratio", global_aspect)
            turning = _mean(style_rows, "turning", global_turning)
            stroke_width = _mean(style_rows, "estimated_stroke_width", global_width)
            h_scale = _clip(math.sqrt(max(aspect / global_aspect, 0.2)), 0.75, 1.35)
            v_scale = _clip(1.0 / h_scale, 0.72, 1.28)
            smoothness = _clip(0.18 + (turning / global_turning - 1.0) * 0.08, 0.08, 0.55)
            corner = _clip(0.10 + (turning / global_turning - 1.0) * 0.10, 0.05, 0.45)
            speed = _clip(global_width / max(stroke_width, 1e-6), 0.75, 1.25)
            profile[style] = {
                "horizontal_scale": {"value": round(h_scale, 4), "source": "estimated"},
                "vertical_scale": {"value": round(v_scale, 4), "source": "estimated"},
                "smoothness": {"value": round(smoothness, 4), "source": "estimated"},
                "corner_rounding": {"value": round(corner, 4), "source": "estimated"},
                "connection_strength": {"value": connection_strength, "source": "default_prior"},
                "allow_interstroke_connections": {"value": allow_connections, "source": "default_prior"},
                "speed_scale": {"value": round(speed, 4), "source": "estimated"},
                "pen_up_height": {"value": float(manual.get("pen_up_height", 6.0)), "source": "default_prior"},
            }
        else:
            profile[style] = _default_prior_specs(style, manual)
    return profile


def flatten_profile(estimated_profiles: dict[str, dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, Any]] = {}
    for style, params in estimated_profiles.items():
        out[style] = {}
        for key, spec in params.items():
            if key not in DEFAULT_PROFILE_KEYS:
                continue
            value = spec["value"]
            out[style][key] = value if isinstance(value, bool) else float(value)
    return out


def parameter_sources(estimated_profiles: dict[str, dict[str, Any]]) -> dict[str, dict[str, str]]:
    return {
        style: {key: str(spec["source"]) for key, spec in params.items() if key in DEFAULT_PROFILE_KEYS}
        for style, params in estimated_profiles.items()
    }


def compare_profiles(
    manual_profiles: dict[str, dict[str, float]],
    estimated_profiles: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for style in manual_profiles:
        for key in DEFAULT_PROFILE_KEYS:
            estimated_spec = estimated_profiles.get(style, {}).get(
                key,
                {"value": manual_profiles[style].get(key, 0.0), "source": "default_prior"},
            )
            rows.append(
                {
                    "style": style,
                    "parameter": key,
                    "manual_value": manual_profiles[style].get(key, ""),
                    "estimated_value": estimated_spec["value"],
                    "source": estimated_spec["source"],
                }
            )
    return rows


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_compare_styles(rendered_samples: list[dict[str, Any]], output_path: Path, chars: list[str] | None = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = sorted({item["style"] for item in rendered_samples})
    shown_chars = chars or sorted({item["char"] for item in rendered_samples})[:3]
    if not styles or not shown_chars:
        fig = Figure(figsize=(5, 2), dpi=140)
        canvas = FigureCanvas(fig)
        ax = fig.add_axes([0.05, 0.2, 0.9, 0.6])
        ax.text(0.5, 0.5, "No rendered samples", ha="center", va="center")
        ax.axis("off")
        canvas.print_png(str(output_path))
        return

    lookup = {(item["style"], item["char"]): item["path"] for item in rendered_samples}
    fig = Figure(figsize=(2.4 * len(styles), 2.4 * len(shown_chars)), dpi=140)
    canvas = FigureCanvas(fig)
    for r, char in enumerate(shown_chars):
        for c, style in enumerate(styles):
            left = 0.04 + c * (0.92 / len(styles))
            bottom = 0.06 + (len(shown_chars) - 1 - r) * (0.88 / len(shown_chars))
            ax = fig.add_axes([left, bottom, 0.82 / len(styles), 0.78 / len(shown_chars)])
            ax.set_title(f"{style} u{ord(char):04x}", fontsize=8)
            ax.axis("off")
            sample = lookup.get((style, char))
            if sample:
                img = Image.open(sample).convert("L")
                ax.imshow(img, cmap="gray", vmin=0, vmax=255)
            else:
                ax.text(0.5, 0.5, "missing", ha="center", va="center")
    canvas.print_png(str(output_path))


def write_profile_report(
    path: Path,
    metrics_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    output_paths: dict[str, str],
) -> None:
    success_counts: dict[str, int] = {}
    for row in metrics_rows:
        if row.get("render_success"):
            success_counts[str(row["style"])] = success_counts.get(str(row["style"]), 0) + 1

    estimated = [row for row in comparison_rows if row["source"] == "estimated"]
    defaulted = [row for row in comparison_rows if row["source"] == "default_prior"]
    lines = [
        "# Style Profile Build Report",
        "",
        "## Outputs",
        "",
        f"- style_metrics.csv: `{output_paths['style_metrics']}`",
        f"- style_profile_estimated.json: `{output_paths['style_profile_estimated']}`",
        f"- comparison.csv: `{output_paths['comparison_csv']}`",
        f"- compare_styles.png: `{output_paths['compare_styles']}`",
        "",
        "## Render Success Counts",
        "",
    ]
    for style in sorted({row["style"] for row in metrics_rows}):
        lines.append(f"- {style}: {success_counts.get(style, 0)}")
    lines.extend(
        [
            "",
            "## Parameter Sources",
            "",
            f"- estimated: {', '.join(sorted({row['parameter'] for row in estimated})) or 'none'}",
            f"- default_prior: {', '.join(sorted({row['parameter'] for row in defaulted})) or 'none'}",
            "",
            "Static font images cannot reliably estimate inter-stroke connection or pen-up behavior.",
            "Connection strength, allow_interstroke_connections, and pen-up height remain priors in this version.",
            "Kaishu and lishu are forced to no inter-stroke connection; xingkai may keep a hand-set connection prior.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_profile_outputs(
    output_dir: Path | str,
    metrics_rows: list[dict[str, Any]],
    estimated_profiles: dict[str, dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    rendered_samples: list[dict[str, Any]],
) -> dict[str, str]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / "style_metrics.csv"
    profile_path = out_dir / "style_profile_estimated.json"
    comparison_path = out_dir / "style_profile_comparison.csv"
    compare_path = out_dir / "compare_styles.png"
    report_path = out_dir / "style_profile_report.md"

    _write_csv(metrics_rows, metrics_path)
    payload = flatten_profile(estimated_profiles)
    payload["_parameter_sources"] = parameter_sources(estimated_profiles)
    profile_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(comparison_rows, comparison_path)
    write_compare_styles(rendered_samples, compare_path)
    outputs = {
        "style_metrics": str(metrics_path),
        "style_profile_estimated": str(profile_path),
        "comparison_csv": str(comparison_path),
        "style_profile_report": str(report_path),
        "compare_styles": str(compare_path),
    }
    write_profile_report(report_path, metrics_rows, comparison_rows, outputs)
    return outputs


def _load_manual(path: Path | str) -> dict[str, dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        data = json.load(f)
    return {
        style: {key: (value if isinstance(value, bool) else float(value)) for key, value in params.items()}
        for style, params in data.items()
    }


def build_profiles(
    sources_path: Path | str,
    manual_profile_path: Path | str,
    output_root: Path | str,
    chars: list[str],
    image_size: int,
) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_root) / f"style_profile_build_{timestamp}"
    sources = load_style_sources(sources_path)
    manual = _load_manual(manual_profile_path)
    metrics_rows, rendered = render_style_samples(
        sources,
        chars=chars,
        image_size=image_size,
        output_dir=out_dir / "rendered_samples",
        config_dir=Path(sources_path).parent,
    )
    estimated = build_estimated_profiles(metrics_rows, manual)
    comparison = compare_profiles(manual, estimated)
    outputs = write_profile_outputs(out_dir, metrics_rows, estimated, comparison, rendered)
    return {"output_dir": str(out_dir), **outputs}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build data-informed style profiles from local sources.")
    parser.add_argument("--sources", default=str(DEFAULT_SOURCES))
    parser.add_argument("--manual-profile", default=str(DEFAULT_MANUAL_PROFILE))
    parser.add_argument("--out-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--chars", default="".join(DEFAULT_CHARS))
    parser.add_argument("--image-size", type=int, default=256)
    args = parser.parse_args()

    chars = [char for char in args.chars if char.strip()]
    result = build_profiles(
        sources_path=args.sources,
        manual_profile_path=args.manual_profile,
        output_root=args.out_root,
        chars=chars,
        image_size=args.image_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
