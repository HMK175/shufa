"""Materialize the sparse P1-extended Phase 1 FontDiffuser image dataset."""

import csv
import json
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

from .glyph_artifacts import mask_isolated_right_border_lines
from .render import normalize_glyph_canvas, render_glyph


_SPLITS = ("train", "validation", "test")


def build_p1_extended_phase1_dataset(config_path: Path, output_root: Path) -> dict[str, object]:
    """Create FontDiffuser-compatible images without mutating external source glyphs."""
    config_path = Path(config_path)
    config = _load_config(config_path)
    characters = _load_characters(_resolve_path(config_path.parent, config["characters_path"]))
    external_rows = _load_external_samples(
        _resolve_path(config_path.parent, config["external_samples_path"]), characters
    )
    open_rows = _load_open_font_plan(
        _resolve_path(config_path.parent, config["open_font_render_plan_path"]),
        _resolve_path(config_path.parent, config["open_font_coverage_summary"]),
        characters,
    )
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    content_count = _render_content_images(
        characters,
        _resolve_path(config_path.parent, config["content_font_path"]),
        output_root,
        config["canvas_size"],
    )
    external_records, masked_count = _materialize_external_targets(
        external_rows, output_root, config["canvas_size"]
    )
    open_records = _render_open_font_targets(
        open_rows,
        {style_id: str(_resolve_path(config_path.parent, font_path)) for style_id, font_path in config["open_font_paths"].items()},
        output_root,
        config["canvas_size"],
    )
    records = [*external_records, *open_records]
    _write_manifests(output_root, characters, records)
    summary = {
        "dataset_scope": config["dataset_scope"],
        "content_image_count": content_count,
        "external_target_count": len(external_records),
        "open_font_target_count": len(open_records),
        "masked_external_count": masked_count,
        "target_image_count": len(records),
        "scr": config["scr"],
    }
    manifests = output_root / "manifests"
    (manifests / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def _load_config(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"无法读取 P1 Phase 1 配置：{path}") from error
    if not isinstance(payload, dict) or payload.get("dataset_scope") != "p1_extended":
        raise ValueError("dataset_scope 必须为 p1_extended")
    if payload.get("scr") is not False:
        raise ValueError("P1 Phase 1 数据集必须声明 scr=false")
    canvas_size = payload.get("canvas_size")
    if isinstance(canvas_size, bool) or not isinstance(canvas_size, int) or canvas_size != 256:
        raise ValueError("canvas_size 必须为 256")
    for key in (
        "characters_path",
        "external_samples_path",
        "open_font_render_plan_path",
        "open_font_coverage_summary",
        "content_font_path",
    ):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ValueError(f"{key} 必须是非空路径")
    open_font_paths = payload.get("open_font_paths")
    if not isinstance(open_font_paths, dict) or not open_font_paths:
        raise ValueError("open_font_paths 必须是非空映射")
    if any(not isinstance(style_id, str) or not isinstance(font_path, str) for style_id, font_path in open_font_paths.items()):
        raise ValueError("open_font_paths 必须是风格 ID 到字体路径的字符串映射")
    payload["canvas_size"] = canvas_size
    return payload


def _resolve_path(config_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else config_dir / path


def _load_characters(path: Path) -> dict[str, str]:
    rows = _read_csv(path, {"character", "split"})
    result = {}
    for row in rows:
        character, split = row["character"], row["split"]
        if len(character) != 1 or split not in _SPLITS or character in result:
            raise ValueError(f"字符划分清单无效：{path}")
        result[character] = split
    if not result:
        raise ValueError("字符划分清单不能为空")
    return result


def _load_external_samples(path: Path, characters: dict[str, str]) -> list[dict[str, str]]:
    required = {"style_id", "character", "character_split", "target_path", "image_preprocess", "tier", "paper_eligible"}
    rows = _read_csv(path, required)
    seen = set()
    for row in rows:
        key = (row["style_id"], row["character"])
        if key in seen or characters.get(row["character"]) != row["character_split"]:
            raise ValueError(f"外部样本出现重复目标或字符划分不一致：{key}")
        if row["image_preprocess"] not in {"none", "mask_isolated_right_border_line"}:
            raise ValueError(f"不支持的外部图像预处理：{row['image_preprocess']}")
        if not Path(row["target_path"]).is_file():
            raise ValueError(f"外部字图不存在：{row['target_path']}")
        seen.add(key)
    return rows


def _load_open_font_plan(
    path: Path, coverage_summary_path: Path, characters: dict[str, str]
) -> list[dict[str, str]]:
    rows = _read_csv(path, {"style_id", "character", "character_split"})
    missing_by_font = _load_missing_characters(coverage_summary_path)
    seen = set()
    accepted = []
    for row in rows:
        key = (row["style_id"], row["character"])
        if key in seen or characters.get(row["character"]) != row["character_split"]:
            raise ValueError(f"开源字体渲染计划重复或字符划分不一致：{key}")
        if row["style_id"] not in missing_by_font:
            raise ValueError(f"开源字体计划缺少覆盖审计记录：{row['style_id']}")
        seen.add(key)
        if row["character"] not in missing_by_font[row["style_id"]]:
            accepted.append(row)
    return accepted


def _load_missing_characters(coverage_summary_path: Path) -> dict[str, set[str]]:
    summary_rows = _read_csv(coverage_summary_path, {"font_id", "missing_count"})
    result = {}
    for row in summary_rows:
        try:
            missing_count = int(row["missing_count"])
        except ValueError as error:
            raise ValueError(f"字体覆盖审计缺字数无效：{row['font_id']}") from error
        missing_path = coverage_summary_path.parent / f"{row['font_id']}_missing_characters.txt"
        if missing_count == 0:
            result[row["font_id"]] = set()
            continue
        try:
            missing = set(missing_path.read_text(encoding="utf-8").rstrip("\r\n"))
        except OSError as error:
            raise ValueError(f"缺少字体缺字清单：{missing_path}") from error
        if len(missing) != missing_count:
            raise ValueError(f"字体缺字清单数量不一致：{row['font_id']}")
        result[row["font_id"]] = missing
    return result


def _read_csv(path: Path, required_fields: set[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not required_fields.issubset(reader.fieldnames):
                raise ValueError(f"清单缺少必要列：{path}")
            return list(reader)
    except OSError as error:
        raise ValueError(f"无法读取清单：{path}") from error


def _render_content_images(
    characters: dict[str, str], content_font_path: Path, output_root: Path, canvas_size: int
) -> int:
    if not content_font_path.is_file():
        raise ValueError(f"内容字体不存在：{content_font_path}")
    for character, split in characters.items():
        image = render_glyph(content_font_path, character, canvas_size)
        _save_jpeg(image, output_root / split / "ContentImage" / f"{character}.jpg")
    return len(characters)


def _materialize_external_targets(
    rows: list[dict[str, str]], output_root: Path, canvas_size: int
) -> tuple[list[dict[str, str]], int]:
    records = []
    masked_count = 0
    for row in rows:
        with Image.open(row["target_path"]) as source:
            image = source.copy()
        if row["image_preprocess"] == "mask_isolated_right_border_line":
            image, actions = mask_isolated_right_border_lines(image)
            if not actions:
                raise ValueError(f"预处理标记与图像伪影不一致：{row['target_path']}")
            masked_count += 1
        target_path = _target_output_path(output_root, row["character_split"], row["style_id"], row["character"])
        _save_jpeg(normalize_glyph_canvas(image, canvas_size), target_path)
        records.append(
            {
                "source_kind": "external",
                "style_id": row["style_id"],
                "character": row["character"],
                "character_split": row["character_split"],
                "target_path": target_path.relative_to(output_root).as_posix(),
                "source_path": row["target_path"],
                "image_preprocess": row["image_preprocess"],
                "tier": row["tier"],
                "paper_eligible": row["paper_eligible"],
            }
        )
    return records, masked_count


def _render_open_font_targets(
    rows: list[dict[str, str]], open_font_paths: dict[str, str], output_root: Path, canvas_size: int
) -> list[dict[str, str]]:
    records = []
    for row in rows:
        font_path_value = open_font_paths.get(row["style_id"])
        font_path = Path(font_path_value) if font_path_value else None
        if font_path is None or not font_path.is_file():
            raise ValueError(f"开源字体路径缺失：{row['style_id']}")
        image = render_glyph(font_path, row["character"], canvas_size)
        target_path = _target_output_path(output_root, row["character_split"], row["style_id"], row["character"])
        _save_jpeg(image, target_path)
        records.append(
            {
                "source_kind": "open_font",
                "style_id": row["style_id"],
                "character": row["character"],
                "character_split": row["character_split"],
                "target_path": target_path.relative_to(output_root).as_posix(),
                "source_path": str(font_path),
                "image_preprocess": "none",
                "tier": "core",
                "paper_eligible": "True",
            }
        )
    return records


def _target_output_path(output_root: Path, split: str, style_id: str, character: str) -> Path:
    return output_root / split / "TargetImage" / style_id / f"{style_id}+{character}.jpg"


def _save_jpeg(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, format="JPEG", quality=95)


def _write_manifests(
    output_root: Path, characters: dict[str, str], records: list[dict[str, str]]
) -> None:
    manifests = output_root / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    _write_csv(
        manifests / "characters.csv",
        ("character", "split"),
        ({"character": character, "split": split} for character, split in sorted(characters.items())),
    )
    fieldnames = (
        "source_kind",
        "style_id",
        "character",
        "character_split",
        "target_path",
        "source_path",
        "image_preprocess",
        "tier",
        "paper_eligible",
    )
    _write_csv(manifests / "samples.csv", fieldnames, records)
    style_counts: dict[tuple[str, str], int] = {}
    for record in records:
        key = (record["source_kind"], record["style_id"])
        style_counts[key] = style_counts.get(key, 0) + 1
    _write_csv(
        manifests / "styles.csv",
        ("source_kind", "style_id", "target_count"),
        (
            {"source_kind": source_kind, "style_id": style_id, "target_count": count}
            for (source_kind, style_id), count in sorted(style_counts.items())
        ),
    )


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
