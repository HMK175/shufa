"""Font-outline-derived trajectory-basis feasibility diagnostics.

This module is intentionally read-only with respect to the main trajectory
pipeline. It compares MakeMeAHanzi medians against skeleton candidates extracted
from rendered font outlines, and writes visual/metric diagnostics only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from knowledge import MakeMeAHanziKnowledge
from trajectory_tools import normalize_medians


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_CONFIG = EXP_DIR / "configs" / "font_outline_basis_chars.json"
DEFAULT_GRAPHICS = ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
STYLE_ORDER = ["kaishu", "xingkai", "lishu"]

SUMMARY_FIELDS = [
    "char",
    "style",
    "font_available",
    "rendered_ok",
    "skeleton_success",
    "skeleton_method",
    "font_path",
    "basis_compare_png",
    "font_mask_png",
    "connected_component_count",
    "skeleton_pixel_count",
    "aspect_ratio",
    "bbox_width",
    "bbox_height",
    "branch_point_count",
    "endpoint_count",
    "median_available",
    "median_bbox_width",
    "median_bbox_height",
    "median_aspect_ratio",
    "bbox_aspect_delta_vs_median",
    "warnings",
]

MANIFEST_FIELDS = ["char", "image_path", "styles_rendered", "warnings"]


@dataclass(frozen=True)
class SkeletonResult:
    skeleton: np.ndarray
    method: str
    skeleton_success: bool
    warnings: list[str]


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_path(path_text: str, base_dir: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _font_candidates(style_sources: dict[str, Any], style: str, config_dir: Path) -> list[Path]:
    spec = style_sources.get(style, {})
    return [_resolve_path(str(item), config_dir) for item in spec.get("font_paths", [])]


def first_existing_font(style_sources: dict[str, Any], style: str, config_dir: Path) -> Path | None:
    for path in _font_candidates(style_sources, style, config_dir):
        if path.exists():
            return path
    return None


def render_char_with_font(char: str, font_path: Path, image_size: int = 256) -> np.ndarray:
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
    return arr < 200


def _component_count(mask: np.ndarray) -> int:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return 0
    seen = np.zeros(grid.shape, dtype=bool)
    count = 0
    height, width = grid.shape
    for y, x in zip(*np.nonzero(grid)):
        if seen[y, x]:
            continue
        count += 1
        queue: deque[tuple[int, int]] = deque([(int(y), int(x))])
        seen[y, x] = True
        while queue:
            cy, cx = queue.popleft()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < height and 0 <= nx < width and grid[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        queue.append((ny, nx))
    return count


def _bbox_metrics(mask: np.ndarray) -> dict[str, float | int]:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return {"bbox_width": 0, "bbox_height": 0, "aspect_ratio": 0.0}
    ys, xs = np.nonzero(grid)
    width = int(xs.max() - xs.min() + 1)
    height = int(ys.max() - ys.min() + 1)
    return {
        "bbox_width": width,
        "bbox_height": height,
        "aspect_ratio": round(width / height if height else 0.0, 6),
    }


def _median_metrics(strokes: Sequence[np.ndarray]) -> dict[str, float | int | bool]:
    pts = [np.asarray(stroke, dtype=float) for stroke in strokes if len(stroke)]
    if not pts:
        return {
            "median_available": False,
            "median_bbox_width": 0,
            "median_bbox_height": 0,
            "median_aspect_ratio": 0.0,
        }
    all_pts = np.vstack(pts)
    y0, x0 = np.min(all_pts, axis=0)
    y1, x1 = np.max(all_pts, axis=0)
    width = float(x1 - x0)
    height = float(y1 - y0)
    return {
        "median_available": True,
        "median_bbox_width": round(width, 6),
        "median_bbox_height": round(height, 6),
        "median_aspect_ratio": round(width / height if height > 1e-9 else 0.0, 6),
    }


def _ridge_skeleton(mask: np.ndarray) -> np.ndarray:
    grid = np.asarray(mask, dtype=bool)
    skeleton = np.zeros(grid.shape, dtype=bool)
    for y in range(grid.shape[0]):
        xs = np.flatnonzero(grid[y])
        if len(xs) == 0:
            continue
        breaks = np.where(np.diff(xs) > 1)[0] + 1
        for run in np.split(xs, breaks):
            if len(run):
                skeleton[y, int(run[len(run) // 2])] = True
    for x in range(grid.shape[1]):
        ys = np.flatnonzero(grid[:, x])
        if len(ys) == 0:
            continue
        breaks = np.where(np.diff(ys) > 1)[0] + 1
        for run in np.split(ys, breaks):
            if len(run):
                skeleton[int(run[len(run) // 2]), x] = True
    return skeleton & grid


def skeletonize_font_mask(mask: np.ndarray, method: str = "auto") -> SkeletonResult:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return SkeletonResult(np.zeros_like(grid, dtype=bool), "none", False, ["empty_mask"])

    warnings: list[str] = []
    if method in {"auto", "skimage"}:
        try:
            from skimage.morphology import skeletonize  # type: ignore

            skeleton = np.asarray(skeletonize(grid), dtype=bool)
            if np.any(skeleton):
                return SkeletonResult(skeleton, "skimage", True, warnings)
            warnings.append("skimage_empty_skeleton")
        except Exception as exc:  # pragma: no cover - depends on optional package state
            warnings.append(f"skimage_unavailable:{type(exc).__name__}")
            if method == "skimage":
                return SkeletonResult(np.zeros_like(grid, dtype=bool), "skimage", False, warnings)

    if method in {"auto", "opencv"}:
        try:
            import cv2  # type: ignore

            thinning = getattr(getattr(cv2, "ximgproc", None), "thinning", None)
            if thinning is not None:
                skeleton = thinning((grid.astype(np.uint8) * 255)) > 0
                if np.any(skeleton):
                    return SkeletonResult(skeleton, "opencv_ximgproc", True, warnings)
                warnings.append("opencv_empty_skeleton")
            else:
                warnings.append("opencv_ximgproc_missing")
        except Exception as exc:  # pragma: no cover - depends on optional package state
            warnings.append(f"opencv_unavailable:{type(exc).__name__}")
            if method == "opencv":
                return SkeletonResult(np.zeros_like(grid, dtype=bool), "opencv", False, warnings)

    skeleton = _ridge_skeleton(grid)
    ok = bool(np.any(skeleton))
    fallback_warnings = warnings + ["ridge_fallback_approx"]
    return SkeletonResult(skeleton, "ridge", ok, fallback_warnings if method != "ridge" else ["ridge_approx"])


def skeleton_topology_metrics(skeleton: np.ndarray) -> dict[str, int]:
    skel = np.asarray(skeleton, dtype=bool)
    pixel_count = int(skel.sum())
    endpoints = 0
    branches = 0
    ys, xs = np.nonzero(skel)
    for y, x in zip(ys, xs):
        y0 = max(0, y - 1)
        y1 = min(skel.shape[0], y + 2)
        x0 = max(0, x - 1)
        x1 = min(skel.shape[1], x + 2)
        neighbors = int(skel[y0:y1, x0:x1].sum()) - 1
        if neighbors == 1:
            endpoints += 1
        elif neighbors >= 3:
            branches += 1
    return {
        "skeleton_pixel_count": pixel_count,
        "endpoint_count": int(endpoints),
        "branch_point_count": int(branches),
    }


def _save_mask_png(mask: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.where(np.asarray(mask, dtype=bool), 0, 255).astype(np.uint8)
    Image.fromarray(image).save(path)


def _write_basis_compare(
    char: str,
    median_strokes: Sequence[np.ndarray],
    style_items: dict[str, dict[str, Any]],
    path: Path,
    image_size: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.2), dpi=150)
    axes[0].set_title("MakeMeAHanzi median", fontsize=8)
    axes[0].set_xlim(0, image_size)
    axes[0].set_ylim(image_size, 0)
    axes[0].set_aspect("equal")
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    axes[0].grid(True, color="#eeeeee", linewidth=0.5)
    for stroke in median_strokes:
        pts = np.asarray(stroke, dtype=float)
        if len(pts):
            axes[0].plot(pts[:, 1], pts[:, 0], color="#333333", linewidth=1.8)
            axes[0].scatter([pts[0, 1]], [pts[0, 0]], color="#333333", marker="o", s=8)
            axes[0].scatter([pts[-1, 1]], [pts[-1, 0]], color="#333333", marker="x", s=12)

    colors = {"kaishu": "#1f77b4", "xingkai": "#d62728", "lishu": "#2ca02c"}
    for idx, style in enumerate(STYLE_ORDER, start=1):
        ax = axes[idx]
        item = style_items.get(style, {})
        ax.set_title(style, fontsize=8)
        ax.set_xlim(0, image_size)
        ax.set_ylim(image_size, 0)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(True, color="#eeeeee", linewidth=0.5)
        mask = np.asarray(item.get("mask", np.zeros((image_size, image_size), dtype=bool)), dtype=bool)
        skeleton = np.asarray(item.get("skeleton", np.zeros_like(mask)), dtype=bool)
        if np.any(mask):
            ax.imshow(np.where(mask, 0.86, 1.0), cmap="gray", vmin=0, vmax=1, extent=[0, image_size, image_size, 0])
        if np.any(skeleton):
            ys, xs = np.nonzero(skeleton)
            ax.scatter(xs, ys, s=0.7, color=colors.get(style, "#333333"), alpha=0.85)
        if not np.any(mask):
            ax.text(image_size / 2, image_size / 2, "missing font", ha="center", va="center", fontsize=8, color="#777777")
    fig.suptitle(f"basis feasibility {char} / u{ord(char):04x}", fontsize=10)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.92])
    fig.savefig(path)
    plt.close(fig)


def _render_style_item(
    char: str,
    style: str,
    font_path: Path | None,
    image_size: int,
    figures_dir: Path,
    skeleton_method: str,
) -> dict[str, Any]:
    mask_path = figures_dir / f"font_mask_u{ord(char):04x}_{style}.png"
    if font_path is None:
        empty = np.zeros((image_size, image_size), dtype=bool)
        return {
            "mask": empty,
            "skeleton": empty,
            "font_available": False,
            "rendered_ok": False,
            "skeleton_success": False,
            "skeleton_method": "none",
            "font_path": "",
            "font_mask_png": "",
            "warnings": ["missing_font"],
            "connected_component_count": 0,
            **_bbox_metrics(empty),
            **skeleton_topology_metrics(empty),
        }
    try:
        mask = render_char_with_font(char, font_path, image_size=image_size)
        _save_mask_png(mask, mask_path)
        skeleton_result = skeletonize_font_mask(mask, method=skeleton_method)
        return {
            "mask": mask,
            "skeleton": skeleton_result.skeleton,
            "font_available": True,
            "rendered_ok": bool(np.any(mask)),
            "skeleton_success": skeleton_result.skeleton_success,
            "skeleton_method": skeleton_result.method,
            "font_path": str(font_path),
            "font_mask_png": str(mask_path),
            "warnings": skeleton_result.warnings,
            "connected_component_count": _component_count(mask),
            **_bbox_metrics(mask),
            **skeleton_topology_metrics(skeleton_result.skeleton),
        }
    except Exception as exc:  # pragma: no cover - defensive around font engines
        empty = np.zeros((image_size, image_size), dtype=bool)
        return {
            "mask": empty,
            "skeleton": empty,
            "font_available": True,
            "rendered_ok": False,
            "skeleton_success": False,
            "skeleton_method": "none",
            "font_path": str(font_path),
            "font_mask_png": "",
            "warnings": [f"render_failed:{type(exc).__name__}"],
            "connected_component_count": 0,
            **_bbox_metrics(empty),
            **skeleton_topology_metrics(empty),
        }


def _style_success_rates(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for style in STYLE_ORDER:
        style_rows = [row for row in rows if row.get("style") == style]
        total = len(style_rows)
        success = sum(1 for row in style_rows if row.get("skeleton_success") is True)
        out[style] = {
            "total": total,
            "success": success,
            "success_rate": round(success / total if total else 0.0, 6),
        }
    return out


def _write_report(
    path: Path,
    out_dir: Path,
    rows: Sequence[dict[str, Any]],
    manifest_rows: Sequence[dict[str, Any]],
    skeleton_method: str,
) -> None:
    rates = _style_success_rates(rows)
    missing_fonts = [row for row in rows if row.get("font_available") is False]
    failed_skeletons = [row for row in rows if row.get("skeleton_success") is not True]
    aspect_candidates = sorted(
        [row for row in rows if row.get("median_available") is True and row.get("skeleton_success") is True],
        key=lambda row: abs(float(row.get("bbox_aspect_delta_vs_median", 0.0))),
        reverse=True,
    )[:8]
    noisy_candidates = sorted(
        [row for row in rows if row.get("skeleton_success") is True],
        key=lambda row: int(row.get("branch_point_count", 0)) + int(row.get("endpoint_count", 0)),
        reverse=True,
    )[:8]

    lines = [
        "# Font-outline-derived trajectory basis feasibility",
        "",
        "本轮目的：只读比较 MakeMeAHanzi median 基底与字体轮廓提取的风格化骨架/中心线候选，判断是否值得继续探索 font-outline-derived trajectory basis。",
        "",
        f"- output_dir: `{out_dir.resolve()}`",
        f"- skeleton_method request: `{skeleton_method}`",
        "- 边界：不替换默认 pipeline，不改 `style_profiles.json`，不改 `run_demo.py` 默认行为，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不做机器人控制。",
        "",
        "## Skeleton success rate by style",
        "",
        "| style | success | total | success_rate |",
        "|---|---:|---:|---:|",
    ]
    for style in STYLE_ORDER:
        item = rates[style]
        lines.append(f"| {style} | {item['success']} | {item['total']} | {item['success_rate']:.3f} |")
    lines.extend(
        [
            "",
            "## Manual visual audit questions",
            "",
            "- xingkai 字体骨架是否比 MakeMeAHanzi median 更有行楷结构，而不是“楷书中心线 + 少量连接”？",
            "- lishu 字体骨架是否不仅是横向拉宽/纵向压扁，而是有笔形或结构差异？",
            "- skeleton 是否太噪声、断裂，或者端点/分叉过多，导致不可直接用于轨迹？",
            "- 是否值得把字体轮廓骨架作为下一阶段轨迹基底，还是只把它当作参数估计来源？",
            "",
            "## Aspect-difference candidates",
            "",
            "| char | style | font_aspect | median_aspect | delta | image |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    image_by_char = {row["char"]: row["image_path"] for row in manifest_rows}
    for row in aspect_candidates:
        lines.append(
            f"| {row['char']} | {row['style']} | {float(row.get('aspect_ratio', 0.0)):.3f} | "
            f"{float(row.get('median_aspect_ratio', 0.0)):.3f} | {float(row.get('bbox_aspect_delta_vs_median', 0.0)):.3f} | "
            f"`{image_by_char.get(str(row['char']), '')}` |"
        )
    lines.extend(
        [
            "",
            "## Potentially noisy or fragmented skeleton candidates",
            "",
            "| char | style | components | skeleton_pixels | endpoints | branches | warnings |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in noisy_candidates:
        lines.append(
            f"| {row['char']} | {row['style']} | {row.get('connected_component_count', 0)} | "
            f"{row.get('skeleton_pixel_count', 0)} | {row.get('endpoint_count', 0)} | "
            f"{row.get('branch_point_count', 0)} | {row.get('warnings', '')} |"
        )
    lines.extend(
        [
            "",
            "## Failure summary",
            "",
            f"- missing_font_rows: {len(missing_fonts)}",
            f"- failed_skeleton_rows: {len(failed_skeletons)}",
            "",
            "## Interpretation boundary",
            "",
            "这些指标不能代替人工看图。本轮只说明字体轮廓骨架候选是否值得继续探索；不承诺它能直接变成稳定书写轨迹，也不代表真实书法风格学习已经完成。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_font_outline_basis_feasibility(
    config_path: Path | str = DEFAULT_CONFIG,
    output_dir: Path | str | None = None,
    copy_to_paper: bool = True,
    skeleton_method: str = "auto",
) -> dict[str, str]:
    config_path = Path(config_path)
    config = _load_json(config_path)
    config_dir = config_path.parent
    chars = [str(item) for item in config.get("chars", [])]
    styles = [str(item) for item in config.get("styles", STYLE_ORDER)]
    image_size = int(config.get("image_size", 256))
    font_sources_path = _resolve_path(str(config.get("font_sources", "style_sources.json")), config_dir)
    style_sources = _load_json(font_sources_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"font_outline_basis_feasibility_{timestamp}"
    figures_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    knowledge = MakeMeAHanziKnowledge(DEFAULT_GRAPHICS)
    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []

    for char in chars:
        warnings: list[str] = []
        try:
            glyph = knowledge.get_glyph(char)
            median_strokes = normalize_medians(glyph.medians, image_size=image_size)
            median_metrics = _median_metrics(median_strokes)
        except Exception:
            median_strokes = []
            median_metrics = _median_metrics([])
            warnings.append("missing_makemeahanzi_median")

        style_items: dict[str, dict[str, Any]] = {}
        for style in styles:
            font_path = first_existing_font(style_sources, style, font_sources_path.parent)
            item = _render_style_item(char, style, font_path, image_size, figures_dir, skeleton_method)
            style_items[style] = item
            aspect_delta = float(item.get("aspect_ratio", 0.0)) - float(median_metrics.get("median_aspect_ratio", 0.0))
            row_warnings = warnings + list(item.get("warnings", []))
            rows.append(
                {
                    "char": char,
                    "style": style,
                    **{key: value for key, value in item.items() if key not in {"mask", "skeleton"}},
                    **median_metrics,
                    "bbox_aspect_delta_vs_median": round(aspect_delta, 6),
                    "warnings": ";".join(row_warnings),
                }
            )

        compare_path = figures_dir / f"basis_compare_u{ord(char):04x}.png"
        _write_basis_compare(char, median_strokes, style_items, compare_path, image_size=image_size)
        manifest_rows.append(
            {
                "char": char,
                "image_path": str(compare_path),
                "styles_rendered": ",".join(styles),
                "warnings": ";".join(warnings),
            }
        )

    summary_csv = out_dir / "font_outline_basis_summary.csv"
    manifest_csv = out_dir / "font_outline_basis_manifest.csv"
    report_md = out_dir / "font_outline_basis_report.md"
    _write_csv(summary_csv, rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, out_dir, rows, manifest_rows, skeleton_method=skeleton_method)

    paper_index = ""
    if copy_to_paper:
        paper_subdir = DEFAULT_PAPER_DIR / "font_outline_basis_feasibility"
        paper_subdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "font_outline_basis_summary.csv")
        shutil.copy2(manifest_csv, DEFAULT_PAPER_DIR / "font_outline_basis_manifest.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "font_outline_basis_report.md")
        for manifest in manifest_rows[: min(10, len(manifest_rows))]:
            src = Path(manifest["image_path"])
            if src.exists():
                shutil.copy2(src, paper_subdir / src.name)
        index_path = DEFAULT_PAPER_DIR / "font_outline_basis_feasibility_index.md"
        copied_images = sorted(paper_subdir.glob("basis_compare_*.png"))
        index_lines = [
            "# Font-outline-derived trajectory basis feasibility index",
            "",
            f"- source_output_dir: `{out_dir.resolve()}`",
            "- This is a readonly feasibility/diagnostic experiment.",
            "- It does not replace MakeMeAHanzi median as the default basis.",
            "- It does not modify style profiles, run_demo defaults, code/data, or legacy route code.",
            "",
            "| file | content |",
            "|---|---|",
            "| `font_outline_basis_report.md` | feasibility report and manual visual audit questions |",
            "| `font_outline_basis_summary.csv` | per char/style skeleton metrics |",
            "| `font_outline_basis_manifest.csv` | compare-image manifest |",
        ]
        for image_path in copied_images:
            index_lines.append(f"| `font_outline_basis_feasibility/{image_path.name}` | copied basis compare image |")
        index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "manifest_csv": str(manifest_csv),
        "report_md": str(report_md),
        "figures_dir": str(figures_dir),
        "paper_index": paper_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run font-outline basis feasibility diagnostics")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--skeleton-method", choices=["auto", "skimage", "opencv", "ridge"], default="auto")
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_font_outline_basis_feasibility(
        config_path=Path(args.config),
        output_dir=Path(args.out_dir) if args.out_dir else None,
        copy_to_paper=not args.no_copy_to_paper,
        skeleton_method=args.skeleton_method,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
