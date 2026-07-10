"""Generate a stroke instance segmentation dataset from makemeahanzi.

This script is an independent data-preparation tool. It does not modify or
call the original image-to-trajectory pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import cv2
import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import numpy as np

from import_makemeahanzi import svg_path_to_mpl


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_GRAPHICS = SCRIPT_DIR / "data" / "makemeahanzi" / "graphics.txt"
DEFAULT_CHARS_FILE = SCRIPT_DIR / "makemeahanzi_chars_extended.txt"
DEFAULT_OUT_DIR = SCRIPT_DIR / "stroke_seg_dataset"


@dataclass
class GlyphRecord:
    char: str
    char_id: str
    strokes: List[str]
    medians: List[np.ndarray]


def safe_char_id(char: str) -> str:
    if char.isascii() and re.match(r"^[A-Za-z0-9_-]+$", char):
        return char
    if len(char) == 1:
        return f"u{ord(char):04x}"
    return "u" + "_".join(f"{ord(ch):04x}" for ch in char)


def read_chars_file(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    chars: List[str] = []
    seen = set()
    for ch in text:
        if ch.isspace() or ch == ",":
            continue
        if ch not in seen:
            chars.append(ch)
            seen.add(ch)
    return chars


def iter_graphics(path: Path) -> Iterable[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"skip invalid JSON line {line_no}: {exc}")


def as_median_array(median: object) -> np.ndarray:
    pts = np.asarray(median, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        return np.empty((0, 2), dtype=float)
    return pts


def load_glyphs(graphics: Path, chars: Sequence[str], limit: int | None = None) -> Tuple[List[GlyphRecord], List[str]]:
    wanted = list(dict.fromkeys(chars))
    wanted_set = set(wanted)
    found: Dict[str, GlyphRecord] = {}

    for item in iter_graphics(graphics):
        char = item.get("character")
        if not isinstance(char, str) or char not in wanted_set or char in found:
            continue
        strokes = item.get("strokes") or []
        medians = item.get("medians") or []
        if not isinstance(strokes, list) or not isinstance(medians, list):
            continue
        if not strokes or len(strokes) != len(medians):
            continue
        found[char] = GlyphRecord(
            char=char,
            char_id=safe_char_id(char),
            strokes=[str(path_text) for path_text in strokes],
            medians=[as_median_array(median) for median in medians],
        )
        if limit is not None and len(found) >= limit:
            break
        if len(found) == len(wanted):
            break

    ordered_chars = wanted[:limit] if limit is not None else wanted
    glyphs = [found[ch] for ch in ordered_chars if ch in found]
    missing = [ch for ch in ordered_chars if ch not in found]
    return glyphs, missing


def path_extents(paths: Sequence[MplPath], medians: Sequence[np.ndarray]) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for path in paths:
        vertices = np.asarray(path.vertices, dtype=float)
        if len(vertices):
            xs.extend(vertices[:, 0].tolist())
            ys.extend(vertices[:, 1].tolist())
    for median in medians:
        if len(median):
            xs.extend(median[:, 0].tolist())
            ys.extend(median[:, 1].tolist())
    if not xs or not ys:
        return 0.0, 1024.0, 0.0, 1024.0
    return min(xs), max(xs), min(ys), max(ys)


def build_transform(paths: Sequence[MplPath], medians: Sequence[np.ndarray], image_size: int, margin_ratio: float = 0.08):
    x0, x1, y0, y1 = path_extents(paths, medians)
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    span = max(width, height)
    margin = image_size * margin_ratio
    scale = (image_size - 2.0 * margin) / span
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    def transform(points_xy: np.ndarray) -> np.ndarray:
        pts = np.asarray(points_xy, dtype=float)
        if pts.size == 0:
            return np.empty((0, 2), dtype=float)
        out = np.empty_like(pts, dtype=float)
        out[:, 0] = (pts[:, 0] - cx) * scale + image_size / 2.0
        out[:, 1] = image_size / 2.0 - (pts[:, 1] - cy) * scale
        return out

    return transform


def transform_path(path: MplPath, transform) -> MplPath:
    vertices = np.asarray(path.vertices, dtype=float)
    if len(vertices) == 0:
        return path
    return MplPath(transform(vertices), path.codes)


def render_paths(paths: Sequence[MplPath], out_path: Path, image_size: int, active_index: int | None = None) -> None:
    fig = Figure(figsize=(image_size / 100.0, image_size / 100.0), dpi=100)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("white")
    for idx, path in enumerate(paths):
        if active_index is None:
            color = "black"
        else:
            color = "black" if idx == active_index else "white"
        ax.add_patch(PathPatch(path, facecolor=color, edgecolor=color, lw=0.4, antialiased=False))
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def png_to_binary_mask(path: Path) -> None:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"rendered image not readable: {path}")
    mask = np.where(image < 250, 255, 0).astype(np.uint8)
    cv2.imwrite(str(path), mask)


def write_median_csv(points_yx: np.ndarray, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["y", "x"])
        for y, x in points_yx:
            writer.writerow([f"{float(y):.3f}", f"{float(x):.3f}"])


def split_for_index(index: int, total: int) -> str:
    train_cut = int(total * 0.8)
    val_cut = int(total * 0.9)
    if index < train_cut:
        return "train"
    if index < val_cut:
        return "val"
    return "test"


def render_preview(
    glyph: GlyphRecord,
    paths: Sequence[MplPath],
    medians_yx: Sequence[np.ndarray],
    out_path: Path,
    image_size: int,
) -> None:
    fig = Figure(figsize=(6.0, 6.0), dpi=140)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0.04, 0.04, 0.92, 0.92])
    ax.set_facecolor("white")

    for path in paths:
        ax.add_patch(PathPatch(path, facecolor="#eeeeee", edgecolor="#c8c8c8", lw=0.6, zorder=1))

    colors = matplotlib.colormaps["tab20"].colors
    for idx, path in enumerate(paths):
        color = colors[idx % len(colors)]
        ax.add_patch(PathPatch(path, facecolor=color, edgecolor=color, lw=0.4, alpha=0.58, zorder=2))
        if idx < len(medians_yx) and len(medians_yx[idx]):
            median = medians_yx[idx]
            ax.plot(median[:, 1], median[:, 0], "-", color=color, lw=2.0, zorder=3)
            ax.scatter(median[0, 1], median[0, 0], s=24, color=color, edgecolor="black", zorder=4)
            ax.scatter(median[-1, 1], median[-1, 0], s=30, marker="x", color=color, zorder=4)
            ax.text(median[0, 1], median[0, 0], str(idx + 1), fontsize=9, weight="bold", zorder=5)

    codepoints = "_".join(f"U+{ord(ch):04X}" for ch in glyph.char)
    ax.set_title(f"{glyph.char_id} {codepoints} strokes={len(paths)}", fontsize=11)
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def generate_dataset(graphics: Path, chars_file: Path, out_dir: Path, image_size: int = 256, limit: int | None = None) -> Dict[str, int]:
    chars = read_chars_file(chars_file)
    glyphs, missing = load_glyphs(graphics, chars, limit=limit)

    images_dir = out_dir / "images"
    masks_root = out_dir / "masks"
    medians_root = out_dir / "medians"
    preview_dir = out_dir / "preview"
    for path in [images_dir, masks_root, medians_root, preview_dir]:
        path.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    total_strokes = 0
    split_counts = {"train": 0, "val": 0, "test": 0}

    for index, glyph in enumerate(glyphs):
        split = split_for_index(index, len(glyphs))
        split_counts[split] += 1
        paths = [svg_path_to_mpl(path_text) for path_text in glyph.strokes]
        transform = build_transform(paths, glyph.medians, image_size)
        image_paths = [transform_path(path, transform) for path in paths]
        medians_xy = [transform(median) for median in glyph.medians]
        medians_yx = [pts[:, [1, 0]] for pts in medians_xy]

        char_id = glyph.char_id
        image_rel = Path("images") / f"{char_id}.png"
        mask_rel_dir = Path("masks") / char_id
        median_rel_dir = Path("medians") / char_id
        preview_rel = Path("preview") / f"{char_id}_preview.png"

        render_paths(image_paths, out_dir / image_rel, image_size)
        mask_dir = out_dir / mask_rel_dir
        median_dir = out_dir / median_rel_dir
        mask_dir.mkdir(parents=True, exist_ok=True)
        median_dir.mkdir(parents=True, exist_ok=True)

        for stroke_idx, path in enumerate(image_paths, start=1):
            mask_path = mask_dir / f"{stroke_idx:02d}.png"
            render_paths([path], mask_path, image_size, active_index=0)
            png_to_binary_mask(mask_path)
            median = medians_yx[stroke_idx - 1] if stroke_idx - 1 < len(medians_yx) else np.empty((0, 2))
            write_median_csv(median, median_dir / f"{stroke_idx:02d}.csv")

        render_preview(glyph, image_paths, medians_yx, out_dir / preview_rel, image_size)

        stroke_count = len(image_paths)
        total_strokes += stroke_count
        rows.append(
            {
                "char_id": char_id,
                "char": glyph.char,
                "split": split,
                "image_path": str(image_rel).replace("\\", "/"),
                "mask_dir": str(mask_rel_dir).replace("\\", "/"),
                "median_dir": str(median_rel_dir).replace("\\", "/"),
                "stroke_count": str(stroke_count),
                "width": str(image_size),
                "height": str(image_size),
                "source": str(graphics),
            }
        )

    manifest = out_dir / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "char_id",
            "char",
            "split",
            "image_path",
            "mask_dir",
            "median_dir",
            "stroke_count",
            "width",
            "height",
            "source",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote manifest: {manifest}")
    print(f"glyphs={len(glyphs)}, total_strokes={total_strokes}, missing={len(missing)}")
    print(f"split train={split_counts['train']} val={split_counts['val']} test={split_counts['test']}")
    if missing:
        print("missing chars:", "".join(missing))
    return {
        "glyphs": len(glyphs),
        "total_strokes": total_strokes,
        "train": split_counts["train"],
        "val": split_counts["val"],
        "test": split_counts["test"],
        "missing": len(missing),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate makemeahanzi stroke segmentation dataset")
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS))
    parser.add_argument("--chars-file", default=str(DEFAULT_CHARS_FILE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    graphics = Path(args.graphics)
    chars_file = Path(args.chars_file)
    if not graphics.exists():
        print(f"graphics.txt not found: {graphics}")
        return 2
    if not chars_file.exists():
        print(f"chars file not found: {chars_file}")
        return 2

    generate_dataset(
        graphics=graphics,
        chars_file=chars_file,
        out_dir=Path(args.out_dir),
        image_size=args.image_size,
        limit=args.limit,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
