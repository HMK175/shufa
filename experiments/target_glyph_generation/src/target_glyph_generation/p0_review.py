"""Create deterministic, stratified manual-review packs for the P0 dataset."""

import csv
import json
import math
from pathlib import Path
import random
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


_SAMPLE_COLUMNS = {
    "style_id",
    "style_split",
    "source_kind",
    "source_dataset",
    "character",
    "character_split",
    "content_path",
    "target_path",
    "source_path",
    "source_split",
    "license_status",
}
_STYLE_COLUMNS = {"style_id", "style_split", "source_kind", "dataset_id", "license_status"}
_CHARACTER_SPLITS = ("train", "validation", "test")


def write_p0_review_pack(
    dataset_root: Path,
    output_dir: Path,
    priority_style_ids: set[str],
    external_samples_per_style: int = 20,
    priority_samples_per_style: int = 100,
    open_font_samples_per_style: int = 10,
    seed: int = 20260715,
) -> dict[str, object]:
    """Write a review queue and labelled image pages from a P0 dataset manifest."""
    _validate_sample_count(external_samples_per_style, "external_samples_per_style")
    _validate_sample_count(priority_samples_per_style, "priority_samples_per_style")
    _validate_sample_count(open_font_samples_per_style, "open_font_samples_per_style")
    dataset_root = Path(dataset_root)
    styles = _read_csv(dataset_root / "manifests" / "styles.csv", _STYLE_COLUMNS)
    samples = _read_csv(dataset_root / "manifests" / "samples.csv", _SAMPLE_COLUMNS)
    style_ids = {row["style_id"] for row in styles}
    if not priority_style_ids.issubset(style_ids):
        unknown = sorted(priority_style_ids - style_ids)
        raise ValueError(f"优先复核风格不在 P0 清单中：{unknown}")

    samples_by_style: dict[str, list[dict[str, str]]] = {style_id: [] for style_id in style_ids}
    for sample in samples:
        if sample["style_id"] not in samples_by_style:
            raise ValueError(f"样本清单引用未知风格：{sample['style_id']}")
        samples_by_style[sample["style_id"]].append(sample)

    queue = []
    for style in sorted(styles, key=lambda row: row["style_id"]):
        style_id = style["style_id"]
        count, reason = _review_requirement(
            style,
            priority_style_ids,
            external_samples_per_style,
            priority_samples_per_style,
            open_font_samples_per_style,
        )
        selected = _stratified_sample(samples_by_style[style_id], count, seed, style_id)
        for index, sample in enumerate(selected, start=1):
            image_path = dataset_root / sample["target_path"]
            if not image_path.is_file():
                raise ValueError(f"复核目标图不存在：{image_path}")
            queue.append(
                {
                    **sample,
                    "review_reason": reason,
                    "review_label": _review_label(reason),
                    "review_index_within_style": str(index),
                }
            )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "style_id",
        "style_split",
        "source_kind",
        "source_dataset",
        "character",
        "character_split",
        "target_path",
        "source_path",
        "source_split",
        "license_status",
        "review_reason",
        "review_label",
        "review_index_within_style",
    ]
    _write_csv(output_dir / "review_queue.csv", fieldnames, queue)
    page_count = _write_review_pages(dataset_root, queue, output_dir / "review_pages")
    per_style_counts = {style_id: sum(row["style_id"] == style_id for row in queue) for style_id in sorted(style_ids)}
    summary = {
        "review_count": len(queue),
        "page_count": page_count,
        "per_style_counts": per_style_counts,
    }
    (output_dir / "review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def _validate_sample_count(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} 必须是正整数")


def _read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    try:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
                raise ValueError(f"复核输入缺少必要列：{path}")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"无法读取复核输入：{path}") from error
    if not rows:
        raise ValueError(f"复核输入为空：{path}")
    return rows


def _review_requirement(
    style: dict[str, str],
    priority_style_ids: set[str],
    external_samples_per_style: int,
    priority_samples_per_style: int,
    open_font_samples_per_style: int,
) -> tuple[int, str]:
    if style["style_id"] in priority_style_ids:
        return priority_samples_per_style, "ocr_label_and_preprocessing"
    if style["source_kind"] == "external":
        return external_samples_per_style, "external_preprocessing"
    if style["source_kind"] == "open_font":
        return open_font_samples_per_style, "open_font_render"
    raise ValueError(f"未知 P0 风格来源：{style['style_id']}")


def _review_label(reason: str) -> str:
    labels = {
        "ocr_label_and_preprocessing": "核对 OCR+预处理",
        "external_preprocessing": "核对外部图预处理",
        "open_font_render": "核对字体渲染",
    }
    try:
        return labels[reason]
    except KeyError as error:
        raise ValueError(f"未知复核原因：{reason}") from error


def _stratified_sample(
    rows: list[dict[str, str]], count: int, seed: int, style_id: str
) -> list[dict[str, str]]:
    if count > len(rows):
        raise ValueError(f"风格 {style_id} 的可抽检样本不足：需要 {count}，当前 {len(rows)}")
    groups = {
        split_name: sorted(
            (row for row in rows if row["character_split"] == split_name),
            key=lambda row: row["character"],
        )
        for split_name in _CHARACTER_SPLITS
    }
    if any(not rows_for_split for rows_for_split in groups.values()):
        raise ValueError(f"风格 {style_id} 缺少字符划分层，无法分层抽检")
    randomizer = random.Random(f"{seed}:{style_id}")
    selected = []
    if count >= len(_CHARACTER_SPLITS):
        for split_name in _CHARACTER_SPLITS:
            choice = randomizer.choice(groups[split_name])
            groups[split_name].remove(choice)
            selected.append(choice)
    remaining = [row for split_rows in groups.values() for row in split_rows]
    randomizer.shuffle(remaining)
    selected.extend(remaining[: count - len(selected)])
    randomizer.shuffle(selected)
    return selected


def _write_review_pages(dataset_root: Path, queue: Iterable[dict[str, str]], output_dir: Path) -> int:
    queue = list(queue)
    output_dir.mkdir(parents=True, exist_ok=True)
    font = _load_font(16)
    columns = 5
    page_size = 25
    tile_width = 210
    tile_height = 265
    for page_number, start in enumerate(range(0, len(queue), page_size), start=1):
        page_rows = queue[start : start + page_size]
        rows = math.ceil(len(page_rows) / columns)
        page = Image.new("L", (columns * tile_width, rows * tile_height), color=255)
        draw = ImageDraw.Draw(page)
        for index, row in enumerate(page_rows):
            column = index % columns
            grid_row = index // columns
            x = column * tile_width
            y = grid_row * tile_height
            draw.rectangle((x, y, x + tile_width - 1, y + tile_height - 1), outline=0, width=1)
            image_path = dataset_root / row["target_path"]
            with Image.open(image_path) as image:
                preview = image.convert("L").resize((190, 190), Image.Resampling.LANCZOS)
            page.paste(preview, (x + 10, y + 5))
            draw.text((x + 6, y + 198), f"style: {row['style_id']}", font=font, fill=0)
            draw.text((x + 6, y + 219), f"char: {row['character']}  split: {row['character_split']}", font=font, fill=0)
            draw.text((x + 6, y + 240), row["review_label"], font=font, fill=0)
        page.save(output_dir / f"review_page_{page_number:03d}.png")
    return math.ceil(len(queue) / page_size)


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/msyh.ttf")):
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
