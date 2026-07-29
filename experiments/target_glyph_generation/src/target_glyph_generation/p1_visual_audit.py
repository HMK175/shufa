"""Pure-Python utilities for P1 fixed-checkpoint visual audits."""

import csv
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo


REQUIRED_MANIFEST_FIELDS = (
    "evaluation_id",
    "style_id",
    "character",
    "content_path",
    "reference_path",
    "target_path",
)
REQUIRED_CHECKPOINT_FILES = (
    "unet.pth",
    "style_encoder.pth",
    "content_encoder.pth",
    "total_model.pth",
)
GENERATED_MANIFEST_FIELDS = (
    "checkpoint_step",
    "sample_index",
    "evaluation_id",
    "style_id",
    "character",
    "content_path",
    "reference_path",
    "target_path",
    "generated_path",
)


def stable_generated_filename(index: int, evaluation_id: str) -> str:
    """Return a stable generated-image filename for a one-based sample index."""
    if index <= 0:
        raise ValueError("generated-image index must be positive")
    digest = hashlib.sha256(evaluation_id.encode("utf-8")).hexdigest()[:12]
    return f"sample_{index:04d}_{digest}.png"


def load_and_validate_visual_manifest(
    manifest_path: Path,
    dataset_root: Path,
    expected_record_count: int,
    expected_style_count: int,
) -> list[dict[str, str]]:
    """Load a BOM-safe CSV manifest and verify its fixed visual-audit contract."""
    manifest_path, dataset_root = Path(manifest_path), Path(dataset_root).resolve()
    try:
        with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not set(REQUIRED_MANIFEST_FIELDS).issubset(reader.fieldnames):
                raise ValueError(f"visual manifest misses required columns: {manifest_path}")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"unable to read visual manifest: {manifest_path}") from error

    if len(rows) != expected_record_count:
        raise ValueError(f"expected {expected_record_count} visual records, found {len(rows)}")

    seen_ids: set[str] = set()
    for row in rows:
        if any(not (row[field] or "").strip() for field in REQUIRED_MANIFEST_FIELDS):
            raise ValueError(f"visual manifest has an empty required field: {row}")
        if row["evaluation_id"] in seen_ids:
            raise ValueError(f"visual manifest has duplicate evaluation_id: {row['evaluation_id']}")
        seen_ids.add(row["evaluation_id"])
        for field in ("content_path", "reference_path", "target_path"):
            image_path = _resolve_dataset_image_path(dataset_root, row[field])
            if not image_path.is_file():
                raise ValueError(f"visual manifest image is missing: {image_path}")

    style_count = len({row["style_id"] for row in rows})
    if style_count != expected_style_count:
        raise ValueError(f"expected {expected_style_count} styles, found {style_count}")
    return sorted(rows, key=lambda row: (row["style_id"], row["character"], row["evaluation_id"]))


def validate_checkpoint_directory(checkpoint_dir: Path) -> None:
    """Ensure the checkpoint has every required FontDiffuser weight file."""
    checkpoint_dir = Path(checkpoint_dir)
    for filename in REQUIRED_CHECKPOINT_FILES:
        weight_path = checkpoint_dir / filename
        if not weight_path.is_file():
            raise ValueError(f"missing checkpoint weight: {weight_path}")


def build_generated_rows(
    records: list[dict[str, str]], generated_dir: Path, checkpoint_step: int | str
) -> list[dict[str, str]]:
    """Attach deterministic generated-image locations to visual manifest records."""
    generated_dir = Path(generated_dir)
    rows: list[dict[str, str]] = []
    for sample_index, record in enumerate(records, start=1):
        filename = stable_generated_filename(sample_index, record["evaluation_id"])
        generated_image = generated_dir / filename
        if not generated_image.is_file():
            raise ValueError(f"generated image is missing: {generated_image}")
        rows.append(
            {
                "checkpoint_step": str(checkpoint_step),
                "sample_index": str(sample_index),
                "evaluation_id": record["evaluation_id"],
                "style_id": record["style_id"],
                "character": record["character"],
                "content_path": record["content_path"],
                "reference_path": record["reference_path"],
                "target_path": record["target_path"],
                "generated_path": f"generated/{filename}",
            }
        )
    return rows


def write_generated_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    """Write a BOM-safe generated manifest with the fixed P1 field order."""
    if not rows:
        raise ValueError("generated manifest rows must not be empty")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GENERATED_MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_run_summary(path: Path, payload: dict[str, object]) -> None:
    """Write a readable, Unicode-preserving visual-audit run summary."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def ascii_character_trace(sample_index: int | str, character: str) -> str:
    """Format a font-independent sample and character trace for an audit tile."""
    tokens = [char if ord(char) < 128 else f"U+{ord(char):04X}" for char in character]
    return f"{int(sample_index):03d} {' '.join(tokens)}"


def write_audit_pages(
    rows: list[dict[str, str]],
    dataset_root: Path,
    checkpoint_dir: Path,
    audit_dir: Path,
    tile_size: int = 96,
    samples_per_style: int = 20,
) -> list[Path]:
    """Render one fixed 4-by-5 sample audit sheet for each style."""
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")
    if not 0 < samples_per_style <= 20:
        raise ValueError("samples_per_style must be between 1 and 20")

    dataset_root = Path(dataset_root).resolve()
    checkpoint_dir = Path(checkpoint_dir).resolve()
    audit_dir = Path(audit_dir)
    rows_by_style: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        rows_by_style.setdefault(row["style_id"], []).append(row)
    if not rows_by_style:
        raise ValueError("audit rows must not be empty")

    for style_id, style_rows in rows_by_style.items():
        if len(style_rows) != samples_per_style:
            raise ValueError(
                f"style {style_id!r}: expected {samples_per_style} records, found {len(style_rows)}"
            )

    audit_dir.mkdir(parents=True, exist_ok=True)
    pages: list[Path] = []
    for style_id, style_rows in sorted(rows_by_style.items()):
        style_rows = sorted(style_rows, key=lambda row: int(row["sample_index"]))
        _validate_style_id_for_filename(style_id)
        page = Image.new("RGB", (8 * tile_size, 10 * tile_size + 24), "white")
        draw = ImageDraw.Draw(page)
        draw.text(
            (2, 2),
            f"{_ascii_label(style_id)} | C content R reference T target G generated",
            fill="black",
        )
        for position, row in enumerate(style_rows):
            row_index, column_index = divmod(position, 4)
            left = column_index * 2 * tile_size
            top = 24 + row_index * 2 * tile_size
            panel_paths = (
                ("content_path", left, top),
                ("reference_path", left + tile_size, top),
                ("target_path", left, top + tile_size),
                ("generated_path", left + tile_size, top + tile_size),
            )
            for field, x, y in panel_paths:
                image_path = (
                    _resolve_checkpoint_generated_path(checkpoint_dir, row[field])
                    if field == "generated_path"
                    else _resolve_dataset_image_path(dataset_root, row[field])
                )
                if not image_path.is_file():
                    raise ValueError(f"audit image is missing: {image_path}")
                page.paste(_load_rgb_tile(image_path, tile_size), (x, y))
            draw.text(
                (left + 2, top + 2 * tile_size - 12),
                ascii_character_trace(row["sample_index"], row["character"]),
                fill="red",
            )
        page_path = audit_dir / f"{style_id}.png"
        traceability = {
            "style_id": style_id,
            "rows": [
                {
                    "style_id": row["style_id"],
                    "character": row["character"],
                    "evaluation_id": row["evaluation_id"],
                    "sample_index": row["sample_index"],
                }
                for row in style_rows
            ],
        }
        pnginfo = PngInfo()
        pnginfo.add_text("p1_visual_audit", json.dumps(traceability, ensure_ascii=False))
        page.save(page_path, pnginfo=pnginfo)
        pages.append(page_path)
    return pages


def _resolve_dataset_image_path(dataset_root: Path, manifest_path: str) -> Path:
    relative_path = Path(manifest_path)
    if relative_path.is_absolute():
        raise ValueError(f"visual manifest image path escapes dataset root: {manifest_path}")
    image_path = (dataset_root / relative_path).resolve()
    try:
        image_path.relative_to(dataset_root)
    except ValueError as error:
        raise ValueError(f"visual manifest image path escapes dataset root: {manifest_path}") from error
    return image_path


def _resolve_checkpoint_generated_path(checkpoint_dir: Path, generated_path: str) -> Path:
    relative_path = Path(generated_path)
    if relative_path.is_absolute():
        raise ValueError(f"generated image path escapes checkpoint directory: {generated_path}")
    image_path = (checkpoint_dir / relative_path).resolve()
    try:
        image_path.relative_to(checkpoint_dir)
    except ValueError as error:
        raise ValueError(
            f"generated image path escapes checkpoint directory: {generated_path}"
        ) from error
    return image_path


def _load_rgb_tile(image_path: Path, tile_size: int) -> Image.Image:
    with Image.open(image_path) as image:
        return image.convert("RGB").resize((tile_size, tile_size), Image.Resampling.NEAREST)


def _ascii_label(value: str) -> str:
    return value.encode("ascii", "backslashreplace").decode("ascii")


def _validate_style_id_for_filename(style_id: str) -> None:
    if not style_id or Path(style_id).name != style_id:
        raise ValueError(f"style_id is not a safe audit filename: {style_id}")
