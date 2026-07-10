"""Import makemeahanzi graphics.txt into a coarse stroke-class dataset."""

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "stroke_cls_dataset"
CLASSES = ["heng", "shu", "pie", "na", "dian", "zhe", "unknown"]
SVG_COMMAND_RE = re.compile(r"[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def parse_graphics_line(line: str) -> Dict[str, object]:
    data = json.loads(line)
    return {
        "character": data.get("character"),
        "strokes": data.get("strokes") or [],
        "medians": data.get("medians") or [],
    }


def _as_points(median: Sequence[Sequence[float]]) -> np.ndarray:
    pts = np.array(median, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        return np.empty((0, 2), dtype=float)
    return pts


def _font_median_to_image_points(median: Sequence[Sequence[float]]) -> np.ndarray:
    pts = _as_points(median)
    if len(pts) == 0:
        return pts
    converted = pts.copy()
    converted[:, 1] = -converted[:, 1]
    return converted


def _angle_deg(dx: float, dy: float) -> float:
    return math.degrees(math.atan2(dy, dx))


def classify_stroke(median: Sequence[Sequence[float]]) -> str:
    """Coarsely classify a stroke from makemeahanzi median geometry.

    The first version intentionally uses simple geometry:
    short strokes -> dian; mostly horizontal -> heng; mostly vertical -> shu;
    down-left -> pie; down-right -> na; strong direction changes -> zhe;
    hook-like ending turns and obvious bends -> zhe; otherwise unknown.
    """
    pts = _font_median_to_image_points(median)
    if len(pts) < 2:
        return "unknown"

    deltas = np.diff(pts, axis=0)
    seg_lengths = np.linalg.norm(deltas, axis=1)
    path_len = float(seg_lengths.sum())
    if path_len < 70:
        return "dian"

    total_dx = float(pts[-1, 0] - pts[0, 0])
    total_dy = float(pts[-1, 1] - pts[0, 1])
    end_dist = math.hypot(total_dx, total_dy)
    if end_dist < 1:
        return "unknown"

    angles = []
    for delta, length in zip(deltas, seg_lengths):
        if length >= 1:
            angles.append(_angle_deg(float(delta[0]), float(delta[1])))

    if len(angles) >= 2:
        changes = []
        for a, b in zip(angles[:-1], angles[1:]):
            diff = abs((b - a + 180) % 360 - 180)
            changes.append(diff)
        max_change = max(changes) if changes else 0.0
        if max_change > 45 or path_len / end_dist > 1.25:
            return "zhe"

    abs_dx = abs(total_dx)
    abs_dy = abs(total_dy)
    if abs_dx >= abs_dy * 2.2:
        return "heng"
    if abs_dy >= abs_dx * 3.0:
        return "shu"
    if total_dx < 0 and total_dy > 0:
        return "pie"
    if total_dx > 0 and total_dy > 0:
        return "na"
    return "unknown"


def _tokenize_path(path_text: str) -> List[str]:
    return SVG_COMMAND_RE.findall(path_text.replace(",", " "))


def svg_path_to_mpl(path_text: str) -> MplPath:
    tokens = _tokenize_path(path_text)
    vertices: List[Tuple[float, float]] = []
    codes: List[int] = []
    i = 0
    cmd = None
    current = (0.0, 0.0)
    start = (0.0, 0.0)

    def is_cmd(token: str) -> bool:
        return len(token) == 1 and token.isalpha()

    def read_float() -> float:
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    while i < len(tokens):
        if is_cmd(tokens[i]):
            cmd = tokens[i]
            i += 1
        if cmd is None:
            break

        lower = cmd.lower()
        relative = cmd.islower()

        if lower == "m":
            x, y = read_float(), read_float()
            if relative:
                x += current[0]
                y += current[1]
            current = (x, y)
            start = current
            vertices.append(current)
            codes.append(MplPath.MOVETO)
            cmd = "l" if relative else "L"
        elif lower == "l":
            x, y = read_float(), read_float()
            if relative:
                x += current[0]
                y += current[1]
            current = (x, y)
            vertices.append(current)
            codes.append(MplPath.LINETO)
        elif lower == "h":
            x = read_float()
            if relative:
                x += current[0]
            current = (x, current[1])
            vertices.append(current)
            codes.append(MplPath.LINETO)
        elif lower == "v":
            y = read_float()
            if relative:
                y += current[1]
            current = (current[0], y)
            vertices.append(current)
            codes.append(MplPath.LINETO)
        elif lower == "c":
            vals = [read_float() for _ in range(6)]
            pts = [(vals[0], vals[1]), (vals[2], vals[3]), (vals[4], vals[5])]
            if relative:
                pts = [(x + current[0], y + current[1]) for x, y in pts]
            vertices.extend(pts)
            codes.extend([MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4])
            current = pts[-1]
        elif lower == "q":
            vals = [read_float() for _ in range(4)]
            pts = [(vals[0], vals[1]), (vals[2], vals[3])]
            if relative:
                pts = [(x + current[0], y + current[1]) for x, y in pts]
            vertices.extend(pts)
            codes.extend([MplPath.CURVE3, MplPath.CURVE3])
            current = pts[-1]
        elif lower == "z":
            vertices.append(start)
            codes.append(MplPath.CLOSEPOLY)
            current = start
        else:
            # Unsupported SVG commands are rare in makemeahanzi strokes; stop safely.
            break

    if not vertices:
        vertices = [(0.0, 0.0)]
        codes = [MplPath.MOVETO]
    return MplPath(vertices, codes)


def _safe_name(char: str, fallback: str) -> str:
    if char.isascii() and re.match(r"^[A-Za-z0-9_-]+$", char):
        return char
    return f"u{ord(char):04x}" if char else fallback


def render_stroke(path_text: str, out_path: Path, image_size: int) -> None:
    mpl_path = svg_path_to_mpl(path_text)
    bbox = mpl_path.get_extents()
    width = max(float(bbox.width), 1.0)
    height = max(float(bbox.height), 1.0)
    cx = float((bbox.x0 + bbox.x1) / 2.0)
    cy = float((bbox.y0 + bbox.y1) / 2.0)
    span = max(width, height)
    margin = span * 0.22 + 1.0

    fig = Figure(figsize=(image_size / 100.0, image_size / 100.0), dpi=100)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("white")
    ax.add_patch(PathPatch(mpl_path, facecolor="black", edgecolor="black", lw=1.0))
    ax.set_xlim(cx - span / 2.0 - margin, cx + span / 2.0 + margin)
    ax.set_ylim(cy - span / 2.0 - margin, cy + span / 2.0 + margin)
    ax.set_aspect("equal")
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def render_review(
    strokes: Sequence[str],
    current_index: int,
    stroke_image_path: Path,
    out_path: Path,
    char: str,
    sample_id: str,
    auto_class: str,
) -> None:
    current_path = svg_path_to_mpl(str(strokes[current_index]))
    all_paths = [svg_path_to_mpl(str(path_text)) for path_text in strokes]
    bboxes = [path.get_extents() for path in all_paths if len(path.vertices) > 0]
    if bboxes:
        x0 = min(float(b.x0) for b in bboxes)
        x1 = max(float(b.x1) for b in bboxes)
        y0 = min(float(b.y0) for b in bboxes)
        y1 = max(float(b.y1) for b in bboxes)
    else:
        x0, x1, y0, y1 = 0.0, 1024.0, 0.0, 1024.0

    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    margin = max(width, height) * 0.08 + 1.0
    crop = None
    try:
        import cv2
        crop = cv2.imread(str(stroke_image_path))
    except Exception:
        crop = None

    fig = Figure(figsize=(8.0, 4.0), dpi=120)
    canvas = FigureCanvas(fig)
    ax_full = fig.add_axes([0.04, 0.12, 0.48, 0.78])
    ax_crop = fig.add_axes([0.58, 0.20, 0.34, 0.64])
    fig.text(
        0.04,
        0.95,
        f"char={char}  sample_id={sample_id}  stroke_index={current_index + 1}  auto_class={auto_class}",
        fontsize=10,
    )

    ax_full.set_facecolor("white")
    for i, path in enumerate(all_paths):
        color = "#d0d0d0"
        zorder = 1
        if i == current_index:
            color = "#d7191c"
            zorder = 2
        ax_full.add_patch(PathPatch(path, facecolor=color, edgecolor=color, lw=1.0, zorder=zorder))
    ax_full.set_xlim(x0 - margin, x1 + margin)
    ax_full.set_ylim(y0 - margin, y1 + margin)
    ax_full.set_aspect("equal")
    ax_full.set_title("Full glyph context")
    ax_full.axis("off")

    if crop is not None:
        ax_crop.imshow(crop)
    ax_crop.set_title("Single stroke crop")
    ax_crop.axis("off")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def _iter_graphics(path: Path) -> Iterable[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield parse_graphics_line(line)
            except json.JSONDecodeError:
                print(f"Skip invalid JSON at line {line_no}")


def import_graphics(
    graphics: Path,
    out_dir: Path,
    limit: Optional[int] = None,
    chars: Optional[Sequence[str]] = None,
    image_size: int = 128,
) -> Dict[str, object]:
    if not graphics.exists():
        print(f"makemeahanzi graphics.txt not found: {graphics}")
        print("Download from https://github.com/skishore/makemeahanzi and pass --graphics path\\to\\graphics.txt")
        print("Suggested local placement: code\\data\\makemeahanzi\\graphics.txt")
        return {"total_samples": 0, "class_counts": Counter(), "unknown_ratio": 0.0}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "review").mkdir(parents=True, exist_ok=True)

    char_filter = set(chars) if chars else None
    rows = []
    counts = Counter()
    glyph_count = 0
    sample_count = 0

    for item in _iter_graphics(graphics):
        char = item.get("character")
        if not isinstance(char, str) or not char:
            continue
        if char_filter is not None and char not in char_filter:
            continue

        strokes = item.get("strokes") or []
        medians = item.get("medians") or []
        if not isinstance(strokes, list) or not isinstance(medians, list):
            continue

        glyph_count += 1
        safe_char = _safe_name(char, f"char{glyph_count:05d}")
        for idx, path_text in enumerate(strokes, start=1):
            median = medians[idx - 1] if idx - 1 < len(medians) else []
            auto_class = classify_stroke(median)
            class_name = auto_class
            sample_id = f"{safe_char}_{idx:02d}"
            rel_path = Path("images") / f"{sample_id}.png"
            review_path = Path("review") / f"{sample_id}_review.png"
            render_stroke(str(path_text), out_dir / rel_path, image_size)
            render_review(
                strokes,
                idx - 1,
                out_dir / rel_path,
                out_dir / review_path,
                char,
                sample_id,
                auto_class,
            )
            rows.append(
                {
                    "sample_id": sample_id,
                    "char": char,
                    "stroke_index": idx,
                    "auto_class": auto_class,
                    "class_name": class_name,
                    "image_path": str(rel_path).replace("\\", "/"),
                    "review_path": str(review_path).replace("\\", "/"),
                    "median_points": json.dumps(median, ensure_ascii=False),
                    "source": str(graphics),
                }
            )
            counts[class_name] += 1
            sample_count += 1

        if limit is not None and glyph_count >= limit:
            break

    metadata = out_dir / "metadata.csv"
    with metadata.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "sample_id",
            "char",
            "stroke_index",
            "auto_class",
            "class_name",
            "image_path",
            "review_path",
            "median_points",
            "source",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    unknown_ratio = counts["unknown"] / sample_count if sample_count else 0.0
    print(f"Wrote metadata: {metadata}")
    print(f"Imported glyphs={glyph_count}, samples={sample_count}")
    for class_name in CLASSES:
        print(f"  {class_name}: {counts[class_name]}")
    print(f"unknown_ratio={unknown_ratio:.2%}")
    return {"total_samples": sample_count, "class_counts": counts, "unknown_ratio": unknown_ratio}


def _parse_chars(chars_text: Optional[str]) -> Optional[List[str]]:
    if not chars_text:
        return None
    path = Path(chars_text)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        return [ch for ch in text if not ch.isspace()]
    return [ch for ch in chars_text if not ch.isspace() and ch != ","]


def main() -> None:
    parser = argparse.ArgumentParser(description="Import makemeahanzi graphics.txt into stroke class images")
    parser.add_argument("--graphics", required=True, help="Path to makemeahanzi graphics.txt")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of glyphs to import")
    parser.add_argument("--chars", default=None, help="Characters string or a text file containing characters")
    parser.add_argument("--image-size", type=int, default=128)
    args = parser.parse_args()

    import_graphics(
        Path(args.graphics).resolve(),
        Path(args.out_dir).resolve(),
        limit=args.limit,
        chars=_parse_chars(args.chars),
        image_size=args.image_size,
    )


if __name__ == "__main__":
    main()
