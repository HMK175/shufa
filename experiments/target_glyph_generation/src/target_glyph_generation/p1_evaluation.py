"""Build deterministic held-out evaluation manifests for P1-extended Phase 1."""

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


_REQUIRED_FIELDS = {
    "source_kind",
    "style_id",
    "character",
    "character_split",
    "target_path",
    "tier",
    "paper_eligible",
}
_OUTPUT_FIELDS = (
    "evaluation_id",
    "source_kind",
    "style_id",
    "tier",
    "paper_eligible",
    "character",
    "character_split",
    "content_path",
    "target_path",
    "reference_style_id",
    "reference_character",
    "reference_path",
)


def build_p1_fixed_test_manifests(
    samples_csv: Path, output_dir: Path, seed: int, visual_per_style: int
) -> dict[str, int]:
    """Pair every test target with one deterministic same-style training reference."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if isinstance(visual_per_style, bool) or not isinstance(visual_per_style, int) or visual_per_style <= 0:
        raise ValueError("visual_per_style must be a positive integer")

    samples_csv = Path(samples_csv)
    dataset_root = samples_csv.parent.parent
    rows = _load_samples(samples_csv)
    references = _select_style_references(rows, dataset_root, seed)
    paired_records = _build_paired_records(rows, references, dataset_root)
    visual_records = _select_visual_records(paired_records, seed, visual_per_style)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "paired_test_manifest.csv", paired_records)
    _write_csv(output_dir / "visual_test_manifest.csv", visual_records)
    summary = {
        "paired_test_count": len(paired_records),
        "visual_test_count": len(visual_records),
        "style_count": len(references),
        "seed": seed,
        "visual_per_style": visual_per_style,
    }
    (output_dir / "evaluation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def _load_samples(samples_csv: Path) -> list[dict[str, str]]:
    try:
        with samples_csv.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not _REQUIRED_FIELDS.issubset(reader.fieldnames):
                raise ValueError(f"samples manifest misses required fields: {samples_csv}")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"unable to read samples manifest: {samples_csv}") from error
    if not rows:
        raise ValueError("samples manifest cannot be empty")
    if any(row["character_split"] not in {"train", "validation", "test"} for row in rows):
        raise ValueError("samples manifest contains an unsupported character split")
    return rows


def _select_style_references(
    rows: list[dict[str, str]], dataset_root: Path, seed: int
) -> dict[str, dict[str, str]]:
    by_style: dict[str, list[dict[str, str]]] = defaultdict(list)
    test_styles = {row["style_id"] for row in rows if row["character_split"] == "test"}
    for row in rows:
        if row["character_split"] == "train":
            reference_path = dataset_root / row["target_path"]
            if not reference_path.is_file():
                raise ValueError(f"training reference image is missing: {reference_path}")
            by_style[row["style_id"]].append(row)

    references = {}
    for style_id in sorted(test_styles):
        candidates = sorted(by_style.get(style_id, []), key=lambda row: (row["character"], row["target_path"]))
        if not candidates:
            raise ValueError(f"test style has no training reference image: {style_id}")
        references[style_id] = candidates[_stable_index(seed, style_id, len(candidates))]
    return references


def _build_paired_records(
    rows: list[dict[str, str]], references: dict[str, dict[str, str]], dataset_root: Path
) -> list[dict[str, str]]:
    records = []
    for row in sorted(
        (row for row in rows if row["character_split"] == "test"),
        key=lambda item: (item["style_id"], item["character"], item["target_path"]),
    ):
        target_path = dataset_root / row["target_path"]
        content_path = dataset_root / "test" / "ContentImage" / f"{row['character']}.jpg"
        if not target_path.is_file() or not content_path.is_file():
            raise ValueError(f"held-out target or content image is missing for {row['style_id']}+{row['character']}")
        reference = references[row["style_id"]]
        if reference["character"] == row["character"]:
            raise ValueError("training and test characters must be disjoint")
        records.append(
            {
                "evaluation_id": f"{row['style_id']}+{row['character']}",
                "source_kind": row["source_kind"],
                "style_id": row["style_id"],
                "tier": row["tier"],
                "paper_eligible": row["paper_eligible"],
                "character": row["character"],
                "character_split": "test",
                "content_path": content_path.relative_to(dataset_root).as_posix(),
                "target_path": row["target_path"],
                "reference_style_id": reference["style_id"],
                "reference_character": reference["character"],
                "reference_path": reference["target_path"],
            }
        )
    if not records:
        raise ValueError("samples manifest contains no test targets")
    return records


def _select_visual_records(
    records: list[dict[str, str]], seed: int, visual_per_style: int
) -> list[dict[str, str]]:
    by_style: dict[str, list[dict[str, str]]] = defaultdict(list)
    for record in records:
        by_style[record["style_id"]].append(record)
    selected = []
    for style_id, style_records in sorted(by_style.items()):
        ranked = sorted(
            style_records,
            key=lambda record: _stable_rank(seed, style_id, record["evaluation_id"]),
        )
        selected.extend(ranked[:visual_per_style])
    return sorted(selected, key=lambda record: (record["style_id"], record["character"]))


def _stable_index(seed: int, style_id: str, length: int) -> int:
    return int(_stable_rank(seed, style_id, "reference"), 16) % length


def _stable_rank(seed: int, style_id: str, value: str) -> str:
    return hashlib.sha256(f"{seed}|{style_id}|{value}".encode("utf-8")).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
