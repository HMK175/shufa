"""Adapt the audited P0 manifest to FontDiffuser's fixed training layout."""

import csv
import json
import os
from pathlib import Path
import random
import shutil
from typing import Iterable, Sequence


_REQUIRED_COLUMNS = {
    "style_id",
    "style_split",
    "character",
    "character_split",
    "content_path",
    "target_path",
}


def build_fontdiffuser_training_adapter(
    p0_dataset_root: Path,
    output_root: Path,
    style_ids: Sequence[str] | None,
    character_limit: int | None,
    selection_seed: int,
) -> dict[str, object]:
    """Create the official ``train/ContentImage`` and ``train/TargetImage`` layout."""
    if isinstance(selection_seed, bool) or not isinstance(selection_seed, int):
        raise ValueError("selection_seed 必须是整数")
    if character_limit is not None and (
        isinstance(character_limit, bool) or not isinstance(character_limit, int) or character_limit < 1
    ):
        raise ValueError("character_limit 必须是正整数或 None")

    p0_dataset_root = Path(p0_dataset_root)
    rows = _read_samples(p0_dataset_root / "manifests" / "samples.csv")
    all_style_ids = {row["style_id"] for row in rows}
    train_rows = [
        row for row in rows if row["style_split"] == "train" and row["character_split"] == "train"
    ]
    available_style_ids = {row["style_id"] for row in train_rows}
    selected_style_ids = _select_styles(style_ids, available_style_ids)
    selected_rows = [row for row in train_rows if row["style_id"] in selected_style_ids]
    rows_by_style = _index_rows_by_style(selected_rows, selected_style_ids)
    selected_characters = _select_common_characters(rows_by_style, character_limit, selection_seed)
    if len(selected_characters) < 2:
        raise ValueError("FontDiffuser requires at least two training characters per style for style-reference sampling")

    output_root = Path(output_root)
    content_root = output_root / "train" / "ContentImage"
    target_root = output_root / "train" / "TargetImage"
    manifest_root = output_root / "manifests"
    for directory in (content_root, target_root, manifest_root):
        directory.mkdir(parents=True, exist_ok=True)

    content_rows = _index_content_rows(rows_by_style, selected_characters)
    link_modes: dict[str, int] = {}
    for character, row in content_rows.items():
        source_path = p0_dataset_root / row["content_path"]
        target_path = content_root / f"{character}.jpg"
        link_mode = _materialize_file(source_path, target_path)
        link_modes[link_mode] = link_modes.get(link_mode, 0) + 1

    adapter_rows = []
    for style_id in selected_style_ids:
        style_dir = target_root / style_id
        style_dir.mkdir(parents=True, exist_ok=True)
        for character in selected_characters:
            row = rows_by_style[style_id][character]
            source_path = p0_dataset_root / row["target_path"]
            target_path = style_dir / f"{style_id}+{character}.jpg"
            link_mode = _materialize_file(source_path, target_path)
            link_modes[link_mode] = link_modes.get(link_mode, 0) + 1
            adapter_rows.append(
                {
                    "style_id": style_id,
                    "character": character,
                    "style_split": row["style_split"],
                    "character_split": row["character_split"],
                    "p0_content_path": row["content_path"],
                    "p0_target_path": row["target_path"],
                    "adapter_content_path": (Path("train") / "ContentImage" / f"{character}.jpg").as_posix(),
                    "adapter_target_path": (Path("train") / "TargetImage" / style_id / f"{style_id}+{character}.jpg").as_posix(),
                    "materialization": link_mode,
                }
            )

    _write_csv(
        manifest_root / "adapter_samples.csv",
        (
            "style_id",
            "character",
            "style_split",
            "character_split",
            "p0_content_path",
            "p0_target_path",
            "adapter_content_path",
            "adapter_target_path",
            "materialization",
        ),
        adapter_rows,
    )
    summary = {
        "style_count": len(selected_style_ids),
        "character_count": len(selected_characters),
        "target_image_count": len(adapter_rows),
        "excluded_style_count": len(all_style_ids - set(selected_style_ids)),
        "link_mode_counts": link_modes,
    }
    (manifest_root / "adapter_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def _read_samples(path: Path) -> list[dict[str, str]]:
    try:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not _REQUIRED_COLUMNS.issubset(reader.fieldnames):
                raise ValueError(f"P0 样本清单缺少必要列：{path}")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"无法读取 P0 样本清单：{path}") from error
    if not rows:
        raise ValueError("P0 样本清单为空")
    return rows


def _select_styles(style_ids: Sequence[str] | None, available_style_ids: set[str]) -> list[str]:
    if style_ids is None:
        selected = sorted(available_style_ids)
    else:
        if not style_ids or any(not isinstance(style_id, str) or not style_id for style_id in style_ids):
            raise ValueError("style_ids 必须是非空风格 ID 序列或 None")
        selected = list(style_ids)
        if len(set(selected)) != len(selected):
            raise ValueError("style_ids 不可重复")
        missing = sorted(set(selected) - available_style_ids)
        if missing:
            raise ValueError(f"所选风格不含训练样本：{missing}")
    if not selected:
        raise ValueError("P0 中没有可用训练风格")
    return selected


def _index_rows_by_style(
    rows: Iterable[dict[str, str]], selected_style_ids: Sequence[str]
) -> dict[str, dict[str, dict[str, str]]]:
    result = {style_id: {} for style_id in selected_style_ids}
    for row in rows:
        style_id = row["style_id"]
        character = row["character"]
        if len(character) != 1:
            raise ValueError(f"P0 样本含无效字符：{style_id} / {character}")
        if character in result[style_id]:
            raise ValueError(f"P0 样本在同一风格内重复：{style_id} / {character}")
        result[style_id][character] = row
    return result


def _select_common_characters(
    rows_by_style: dict[str, dict[str, dict[str, str]]], character_limit: int | None, selection_seed: int
) -> list[str]:
    common = set.intersection(*(set(rows) for rows in rows_by_style.values()))
    if character_limit is not None and len(common) < character_limit:
        raise ValueError(f"所选训练风格的公共训练字符不足：需要 {character_limit}，当前 {len(common)}")
    characters = sorted(common)
    random.Random(selection_seed).shuffle(characters)
    return characters if character_limit is None else characters[:character_limit]


def _index_content_rows(
    rows_by_style: dict[str, dict[str, dict[str, str]]], characters: Sequence[str]
) -> dict[str, dict[str, str]]:
    first_style_rows = next(iter(rows_by_style.values()))
    result = {}
    for character in characters:
        first_row = first_style_rows[character]
        content_path = first_row["content_path"]
        if any(style_rows[character]["content_path"] != content_path for style_rows in rows_by_style.values()):
            raise ValueError(f"P0 同一字符的内容图路径不一致：{character}")
        result[character] = first_row
    return result


def _materialize_file(source_path: Path, target_path: Path) -> str:
    if not source_path.is_file():
        raise ValueError(f"P0 源图不存在：{source_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        if target_path.samefile(source_path):
            return "hardlink"
        raise ValueError(f"适配输出路径已被不同文件占用：{target_path}")
    try:
        os.link(source_path, target_path)
        return "hardlink"
    except OSError:
        shutil.copy2(source_path, target_path)
        return "copy"


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
