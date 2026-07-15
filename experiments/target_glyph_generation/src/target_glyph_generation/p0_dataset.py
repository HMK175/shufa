"""Build the exploratory P0 dataset from audited external glyphs and open-font renders."""

import csv
import json
from pathlib import Path
import random
import shutil
from typing import Any

import yaml
from PIL import Image

from .render import normalize_glyph_canvas


_SPLIT_NAMES = ("train", "validation", "test")
_CANDIDATE_COLUMNS = {
    "dataset_id",
    "style_id",
    "character",
    "source_split",
    "target_path",
    "raw_filename",
    "review_state",
}


def build_p0_dataset(
    config_path: Path,
    chinese_manifest_path: Path,
    calligrapher_manifest_path: Path,
    open_dataset_root: Path,
    output_root: Path,
) -> dict[str, object]:
    """Create a reproducible P0 image directory and its character/style manifests."""
    config = _load_config(config_path)
    canvas_size = _positive_int(config, "canvas_size")
    character_count = _positive_int(config, "character_count")
    selection_seed = _positive_int(config, "selection_seed", allow_zero=True)
    split_seed = _positive_int(config, "split_seed", allow_zero=True)
    character_splits = _load_character_split_counts(config, character_count)
    external_styles = _load_external_styles(config)
    open_style_ids = _load_open_style_ids(config)
    style_splits = _load_style_splits(config, external_styles, open_style_ids)

    manifest_rows = [
        *_read_candidate_manifest(chinese_manifest_path),
        *_read_candidate_manifest(calligrapher_manifest_path),
    ]
    external_by_style = _index_external_rows(manifest_rows, external_styles)
    common_characters = set.intersection(*(set(rows) for rows in external_by_style.values()))
    if len(common_characters) < character_count:
        raise ValueError(
            f"外部风格的公共字符不足：需要 {character_count} 个，当前只有 {len(common_characters)} 个"
        )
    selected_characters = _select_characters(common_characters, character_count, selection_seed)
    character_split_map = _split_characters(selected_characters, character_splits, split_seed)

    output_root = Path(output_root)
    content_dir = output_root / "rendered" / "ContentImage"
    target_root = output_root / "rendered" / "TargetImage"
    manifest_dir = output_root / "manifests"
    for directory in (content_dir, target_root, manifest_dir):
        directory.mkdir(parents=True, exist_ok=True)

    content_paths = _copy_content_images(open_dataset_root, content_dir, selected_characters, canvas_size)
    style_records = _style_records(external_styles, open_style_ids, style_splits)
    sample_rows: list[dict[str, str]] = []
    for style in style_records:
        target_dir = target_root / style["style_id"]
        target_dir.mkdir(parents=True, exist_ok=True)
        for character in selected_characters:
            relative_target_path = Path("rendered") / "TargetImage" / style["style_id"] / (
                f"{style['style_id']}+{character}.png"
            )
            target_path = output_root / relative_target_path
            if style["source_kind"] == "external":
                source_row = external_by_style[(style["dataset_id"], style["style_id"])][character]
                source_path = Path(source_row["target_path"])
                _normalize_external_image(source_path, target_path, canvas_size)
                source_split = source_row["source_split"]
            else:
                source_path = (
                    Path(open_dataset_root)
                    / "rendered"
                    / "TargetImage"
                    / style["style_id"]
                    / f"{style['style_id']}+{character}.png"
                )
                _copy_open_image(source_path, target_path, canvas_size)
                source_split = "open_font"
            sample_rows.append(
                {
                    "style_id": style["style_id"],
                    "style_split": style["style_split"],
                    "source_kind": style["source_kind"],
                    "source_dataset": style["dataset_id"],
                    "character": character,
                    "character_split": character_split_map[character],
                    "content_path": content_paths[character],
                    "target_path": relative_target_path.as_posix(),
                    "source_path": str(source_path),
                    "source_split": source_split,
                    "license_status": style["license_status"],
                }
            )

    _write_csv(
        manifest_dir / "characters.csv",
        ("character", "split"),
        (
            {"character": character, "split": character_split_map[character]}
            for character in sorted(selected_characters)
        ),
    )
    _write_csv(
        manifest_dir / "styles.csv",
        ("style_id", "style_split", "source_kind", "dataset_id", "license_status"),
        style_records,
    )
    _write_csv(
        manifest_dir / "samples.csv",
        (
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
        ),
        sample_rows,
    )

    paper_ready = config["dataset_tier"] == "paper" and all(
        record["license_status"] != "unverified" for record in style_records
    )
    summary = {
        "character_count": len(selected_characters),
        "style_count": len(style_records),
        "target_image_count": len(sample_rows),
        "dataset_tier": config["dataset_tier"],
        "paper_ready": paper_ready,
    }
    (manifest_dir / "dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def _load_config(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError(f"P0 配置不是有效 YAML：{path}") from error
    if not isinstance(payload, dict):
        raise ValueError("P0 配置必须是对象")
    dataset_tier = payload.get("dataset_tier")
    if dataset_tier not in {"exploratory", "paper"}:
        raise ValueError("dataset_tier 必须为 exploratory 或 paper")
    return payload


def _positive_int(config: dict[str, Any], key: str, allow_zero: bool = False) -> int:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if allow_zero else 1):
        raise ValueError(f"{key} 必须是{'非负' if allow_zero else '正'}整数")
    return value


def _load_character_split_counts(config: dict[str, Any], character_count: int) -> dict[str, int]:
    payload = config.get("character_splits")
    if not isinstance(payload, dict) or set(payload) != set(_SPLIT_NAMES):
        raise ValueError("character_splits 必须恰好包含 train、validation、test")
    result = {name: _positive_int(payload, name) for name in _SPLIT_NAMES}
    if sum(result.values()) != character_count:
        raise ValueError("character_splits 之和必须等于 character_count")
    return result


def _load_external_styles(config: dict[str, Any]) -> list[dict[str, str]]:
    payload = config.get("external_styles")
    if not isinstance(payload, list) or not payload:
        raise ValueError("external_styles 必须是非空列表")
    styles = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("external_styles 的每项必须是对象")
        dataset_id = item.get("dataset_id")
        style_id = item.get("style_id")
        license_status = item.get("license_status")
        if not all(isinstance(value, str) and value.strip() for value in (dataset_id, style_id, license_status)):
            raise ValueError("external_styles 必须包含非空 dataset_id、style_id、license_status")
        styles.append(
            {
                "dataset_id": dataset_id.strip(),
                "style_id": style_id.strip(),
                "license_status": license_status.strip(),
            }
        )
    if len({(item["dataset_id"], item["style_id"]) for item in styles}) != len(styles):
        raise ValueError("external_styles 不可重复")
    return styles


def _load_open_style_ids(config: dict[str, Any]) -> list[str]:
    payload = config.get("open_style_ids")
    if not isinstance(payload, list) or not payload:
        raise ValueError("open_style_ids 必须是非空列表")
    if any(not isinstance(item, str) or not item.strip() for item in payload):
        raise ValueError("open_style_ids 必须全部是非空字符串")
    style_ids = [item.strip() for item in payload]
    if len(set(style_ids)) != len(style_ids):
        raise ValueError("open_style_ids 不可重复")
    return style_ids


def _load_style_splits(
    config: dict[str, Any], external_styles: list[dict[str, str]], open_style_ids: list[str]
) -> dict[str, str]:
    payload = config.get("style_splits")
    if not isinstance(payload, dict) or set(payload) != set(_SPLIT_NAMES):
        raise ValueError("style_splits 必须恰好包含 train、validation、test")
    expected = [*(style["style_id"] for style in external_styles), *open_style_ids]
    if len(set(expected)) != len(expected):
        raise ValueError("外部风格与开源字体的 style_id 不可重名")
    result: dict[str, str] = {}
    for split_name in _SPLIT_NAMES:
        style_ids = payload[split_name]
        if not isinstance(style_ids, list) or not style_ids:
            raise ValueError(f"style_splits.{split_name} 必须是非空列表")
        for style_id in style_ids:
            if not isinstance(style_id, str) or style_id not in expected or style_id in result:
                raise ValueError("style_splits 必须不重不漏地覆盖全部风格")
            result[style_id] = split_name
    if set(result) != set(expected):
        raise ValueError("style_splits 必须不重不漏地覆盖全部风格")
    return result


def _read_candidate_manifest(path: Path) -> list[dict[str, str]]:
    try:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not _CANDIDATE_COLUMNS.issubset(reader.fieldnames):
                raise ValueError(f"候选清单缺少必要列：{path}")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"无法读取候选清单：{path}") from error
    return rows


def _index_external_rows(
    rows: list[dict[str, str]], external_styles: list[dict[str, str]]
) -> dict[tuple[str, str], dict[str, dict[str, str]]]:
    expected = {(style["dataset_id"], style["style_id"]) for style in external_styles}
    result = {key: {} for key in expected}
    for row in rows:
        key = (row.get("dataset_id", ""), row.get("style_id", ""))
        if key not in expected:
            continue
        character = row.get("character", "")
        source_path = row.get("target_path", "")
        if len(character) != 1 or not source_path:
            raise ValueError(f"候选清单包含无效字符或路径：{key}")
        if character in result[key]:
            raise ValueError(f"候选清单在同一风格内含重复字符：{key} / {character}")
        result[key][character] = row
    missing_styles = [key for key, values in result.items() if not values]
    if missing_styles:
        raise ValueError(f"候选清单缺少所选风格：{missing_styles}")
    return result


def _select_characters(characters: set[str], count: int, seed: int) -> list[str]:
    ordered = sorted(characters)
    random.Random(seed).shuffle(ordered)
    return ordered[:count]


def _split_characters(
    characters: list[str], split_counts: dict[str, int], seed: int
) -> dict[str, str]:
    ordered = sorted(characters)
    random.Random(seed).shuffle(ordered)
    result: dict[str, str] = {}
    index = 0
    for split_name in _SPLIT_NAMES:
        for character in ordered[index : index + split_counts[split_name]]:
            result[character] = split_name
        index += split_counts[split_name]
    return result


def _copy_content_images(
    open_dataset_root: Path, content_dir: Path, characters: list[str], canvas_size: int
) -> dict[str, str]:
    result = {}
    for character in characters:
        source_path = Path(open_dataset_root) / "rendered" / "ContentImage" / f"{character}.png"
        target_path = content_dir / f"{character}.png"
        _copy_open_image(source_path, target_path, canvas_size)
        result[character] = (Path("rendered") / "ContentImage" / f"{character}.png").as_posix()
    return result


def _style_records(
    external_styles: list[dict[str, str]], open_style_ids: list[str], style_splits: dict[str, str]
) -> list[dict[str, str]]:
    records = [
        {
            "style_id": style["style_id"],
            "style_split": style_splits[style["style_id"]],
            "source_kind": "external",
            "dataset_id": style["dataset_id"],
            "license_status": style["license_status"],
        }
        for style in external_styles
    ]
    records.extend(
        {
            "style_id": style_id,
            "style_split": style_splits[style_id],
            "source_kind": "open_font",
            "dataset_id": "open_font",
            "license_status": "OFL-1.1",
        }
        for style_id in open_style_ids
    )
    return records


def _normalize_external_image(source_path: Path, target_path: Path, canvas_size: int) -> None:
    if not source_path.is_file():
        raise ValueError(f"外部字图不存在：{source_path}")
    try:
        with Image.open(source_path) as image:
            normalized = normalize_glyph_canvas(image, canvas_size)
    except OSError as error:
        raise ValueError(f"无法读取外部字图：{source_path}") from error
    _validate_image(normalized, canvas_size)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(target_path)


def _copy_open_image(source_path: Path, target_path: Path, canvas_size: int) -> None:
    if not source_path.is_file():
        raise ValueError(f"开源字体图不存在：{source_path}")
    try:
        with Image.open(source_path) as image:
            normalized = image.copy()
    except OSError as error:
        raise ValueError(f"无法读取开源字体图：{source_path}") from error
    _validate_image(normalized, canvas_size)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)


def _validate_image(image: Image.Image, canvas_size: int) -> None:
    foreground = image.convert("L").point(lambda pixel: 255 if pixel < 250 else 0).getbbox()
    if image.mode != "L" or image.size != (canvas_size, canvas_size) or foreground is None:
        raise ValueError(f"字图必须是非空的 {canvas_size}×{canvas_size} 灰度图")


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
