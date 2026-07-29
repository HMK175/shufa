"""Create human-review pages for P1 image preprocessing decisions."""

import csv
import json
from collections import defaultdict
from pathlib import Path
import random

from PIL import Image, ImageDraw

from .render import normalize_glyph_canvas


_REVIEW_COLUMNS = (
    "review_id",
    "character",
    "character_split",
    "source_path",
    "processed_path",
    "image_preprocess",
    "page",
    "row",
    "column",
    "review_status",
    "review_notes",
)
_GRID_COLUMNS = 3
_GRID_ROWS = 4
_TILE_WIDTH = 544
_TILE_HEIGHT = 292


def create_p1_htj_mask_review(
    samples_csv: Path, output_dir: Path, sample_count: int, seed: int
) -> dict[str, int]:
    """Write deterministic before/after pages for flagged Huang Tingjian samples."""
    if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
        raise ValueError("sample_count must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    samples_csv = Path(samples_csv)
    dataset_root = samples_csv.parent.parent
    candidates = _load_candidates(samples_csv, dataset_root)
    if sample_count > len(candidates):
        raise ValueError(f"requested {sample_count} review samples but only {len(candidates)} are available")

    selected = _select_stratified(candidates, sample_count, seed)
    output_dir = Path(output_dir)
    pages_dir = output_dir / "review_pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    records = _create_review_pages(selected, dataset_root, pages_dir)
    _write_csv(output_dir / "review_manifest.csv", _REVIEW_COLUMNS, records)
    summary = {
        "candidate_count": len(candidates),
        "review_count": len(records),
        "page_count": (len(records) + _GRID_COLUMNS * _GRID_ROWS - 1) // (_GRID_COLUMNS * _GRID_ROWS),
        "seed": seed,
    }
    (output_dir / "review_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def _load_candidates(samples_csv: Path, dataset_root: Path) -> list[dict[str, str]]:
    required = {
        "source_kind",
        "style_id",
        "character",
        "character_split",
        "target_path",
        "source_path",
        "image_preprocess",
    }
    try:
        with samples_csv.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise ValueError(f"missing required fields in samples manifest: {samples_csv}")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"unable to read samples manifest: {samples_csv}") from error

    candidates = []
    for row in rows:
        if not (
            row["source_kind"] == "external"
            and row["style_id"] == "htj"
            and row["image_preprocess"] == "mask_isolated_right_border_line"
        ):
            continue
        source_path = Path(row["source_path"])
        processed_path = dataset_root / row["target_path"]
        if not source_path.is_file() or not processed_path.is_file():
            raise ValueError(f"review image is missing for {row['character']}")
        candidates.append(row)
    if not candidates:
        raise ValueError("no flagged Huang Tingjian samples were found")
    return candidates


def _select_stratified(
    candidates: list[dict[str, str]], sample_count: int, seed: int
) -> list[dict[str, str]]:
    by_split: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        by_split[row["character_split"]].append(row)
    for rows in by_split.values():
        rows.sort(key=lambda row: (row["character"], row["source_path"]))

    total = len(candidates)
    allocation: dict[str, int] = {}
    remainders = []
    for split, rows in sorted(by_split.items()):
        exact = sample_count * len(rows) / total
        allocation[split] = min(len(rows), int(exact))
        remainders.append((exact - int(exact), split))
    remaining = sample_count - sum(allocation.values())
    for _, split in sorted(remainders, key=lambda item: (-item[0], item[1])):
        if remaining == 0:
            break
        if allocation[split] < len(by_split[split]):
            allocation[split] += 1
            remaining -= 1

    generator = random.Random(seed)
    selected = []
    for split in sorted(by_split):
        selected.extend(generator.sample(by_split[split], allocation[split]))
    return sorted(selected, key=lambda row: (row["character_split"], row["character"], row["source_path"]))


def _create_review_pages(
    selected: list[dict[str, str]], dataset_root: Path, pages_dir: Path
) -> list[dict[str, str]]:
    per_page = _GRID_COLUMNS * _GRID_ROWS
    records = []
    for start in range(0, len(selected), per_page):
        page_index = start // per_page + 1
        page = Image.new("RGB", (_GRID_COLUMNS * _TILE_WIDTH, _GRID_ROWS * _TILE_HEIGHT), color="white")
        for position, sample in enumerate(selected[start : start + per_page]):
            row_index, column_index = divmod(position, _GRID_COLUMNS)
            review_id = start + position + 1
            tile = _create_before_after_tile(sample, dataset_root, review_id)
            page.paste(tile, (column_index * _TILE_WIDTH, row_index * _TILE_HEIGHT))
            records.append(
                {
                    "review_id": str(review_id),
                    "character": sample["character"],
                    "character_split": sample["character_split"],
                    "source_path": sample["source_path"],
                    "processed_path": sample["target_path"],
                    "image_preprocess": sample["image_preprocess"],
                    "page": str(page_index),
                    "row": str(row_index + 1),
                    "column": str(column_index + 1),
                    "review_status": "pending",
                    "review_notes": "",
                }
            )
        page.save(pages_dir / f"page_{page_index:03d}.png", format="PNG")
    return records


def _create_before_after_tile(sample: dict[str, str], dataset_root: Path, review_id: int) -> Image.Image:
    with Image.open(sample["source_path"]) as source:
        before = normalize_glyph_canvas(source.copy(), 256).convert("RGB")
    with Image.open(dataset_root / sample["target_path"]) as processed:
        after = processed.convert("RGB").resize((256, 256), Image.Resampling.LANCZOS)

    tile = Image.new("RGB", (_TILE_WIDTH, _TILE_HEIGHT), color="white")
    tile.paste(before, (8, 28))
    tile.paste(after, (280, 28))
    draw = ImageDraw.Draw(tile)
    draw.line((272, 28, 272, 284), fill="black", width=1)
    draw.rectangle((0, 0, _TILE_WIDTH - 1, _TILE_HEIGHT - 1), outline="black", width=1)
    draw.text((8, 7), f"#{review_id}  before", fill="black")
    draw.text((280, 7), f"after  split={sample['character_split']}", fill="black")
    return tile


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
