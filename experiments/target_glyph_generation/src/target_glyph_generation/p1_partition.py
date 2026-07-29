"""Create a character-disjoint P1-extended partition from audited glyph manifests."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
import random
from typing import Any

import yaml


_SPLITS = ("train", "validation", "test")
_REQUIRED_CANDIDATE_FIELDS = {
    "tier",
    "dataset_id",
    "style_id",
    "style_display_name",
    "character",
    "source_split",
    "raw_filename",
    "target_path",
    "paper_eligible",
}


def build_p1_extended_partition(config_path: Path, output_dir: Path) -> dict[str, object]:
    """Write a content-disjoint partition and open-font render plan for P1-extended."""
    config_path = Path(config_path)
    config = _load_config(config_path)
    rows = [
        *_read_candidates(_resolve_path(config_path.parent, config["core_candidates_path"]), "core"),
        *_read_candidates(_resolve_path(config_path.parent, config["extended_candidates_path"]), "extended"),
    ]
    _validate_rows(rows, config["paper_use_basis"])
    artifact_actions = _load_artifact_actions(config, config_path.parent, rows)
    character_splits, coverage = _split_characters(rows, config["seed"], config["ratios"])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_outputs(output_dir, rows, character_splits, coverage, artifact_actions, config)
    return _summary(rows, character_splits, config)


def _load_config(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"无法读取 P1-extended 划分配置：{path}") from error
    if not isinstance(payload, dict) or payload.get("dataset_scope") != "p1_extended":
        raise ValueError("dataset_scope 必须为 p1_extended")
    seed = payload.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed 必须是整数")
    ratios = payload.get("ratios")
    if not isinstance(ratios, dict) or set(ratios) != set(_SPLITS):
        raise ValueError("ratios 必须恰好包含 train、validation、test")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0 for value in ratios.values()):
        raise ValueError("ratios 必须为正数")
    if abs(sum(ratios.values()) - 1.0) > 1e-9:
        raise ValueError("ratios 之和必须为 1")
    for key in ("core_candidates_path", "extended_candidates_path"):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ValueError(f"{key} 必须是非空路径")
    open_font_style_ids = payload.get("open_font_style_ids")
    if not isinstance(open_font_style_ids, list) or not open_font_style_ids:
        raise ValueError("open_font_style_ids 必须是非空列表")
    if any(not isinstance(style_id, str) or not style_id.strip() for style_id in open_font_style_ids):
        raise ValueError("open_font_style_ids 必须全部为非空字符串")
    if len(set(open_font_style_ids)) != len(open_font_style_ids):
        raise ValueError("open_font_style_ids 不可重复")
    if payload.get("paper_use_basis") != "user_confirmed_unverified_source":
        raise ValueError("paper_use_basis 必须为 user_confirmed_unverified_source")
    artifact_actions_path = payload.get("artifact_actions_path")
    if artifact_actions_path is not None and (
        not isinstance(artifact_actions_path, str) or not artifact_actions_path.strip()
    ):
        raise ValueError("artifact_actions_path 必须是非空路径")
    return payload


def _resolve_path(config_dir: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else config_dir / path


def _read_candidates(path: Path, expected_tier: str) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or not _REQUIRED_CANDIDATE_FIELDS.issubset(reader.fieldnames):
                raise ValueError(f"候选清单缺少必要列：{path}")
            rows = list(reader)
    except OSError as error:
        raise ValueError(f"无法读取候选清单：{path}") from error
    if any(row["tier"] != expected_tier for row in rows):
        raise ValueError(f"候选清单 tier 与输入不匹配：{path}")
    return rows


def _validate_rows(rows: list[dict[str, str]], paper_use_basis: str) -> None:
    if not rows:
        raise ValueError("P1-extended 候选清单不能为空")
    seen_keys: set[tuple[str, str, str]] = set()
    for row in rows:
        character = row["character"]
        if not _is_single_cjk_character(character):
            raise ValueError(f"存在非单个 CJK 字符：{character!r}")
        target_path = Path(row["target_path"])
        if not target_path.is_file():
            raise ValueError(f"候选原图不存在：{target_path}")
        key = (row["style_id"], row["source_split"], row["raw_filename"])
        if not all(key) or key in seen_keys:
            raise ValueError(f"候选原图键重复或不完整：{key}")
        seen_keys.add(key)
        if row["tier"] == "extended" and (
            row["paper_eligible"] != "True"
            or row.get("paper_use_basis") != paper_use_basis
        ):
            raise ValueError("P1-extended 样本必须记录用户确认的未核实来源状态")


def _load_artifact_actions(
    config: dict[str, Any], config_dir: Path, rows: list[dict[str, str]]
) -> dict[tuple[str, str, str], str]:
    path_value = config.get("artifact_actions_path")
    if path_value is None:
        return {}
    path = _resolve_path(config_dir, path_value)
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"style_id", "source_split", "raw_filename", "image_preprocess"}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise ValueError(f"伪影动作清单缺少必要列：{path}")
            action_rows = list(reader)
    except OSError as error:
        raise ValueError(f"无法读取伪影动作清单：{path}") from error
    sample_keys = {(row["style_id"], row["source_split"], row["raw_filename"]) for row in rows}
    result: dict[tuple[str, str, str], str] = {}
    for row in action_rows:
        key = (row["style_id"], row["source_split"], row["raw_filename"])
        if key not in sample_keys or key in result:
            raise ValueError(f"伪影动作清单包含未知或重复原图键：{key}")
        if row["image_preprocess"] != "mask_isolated_right_border_line":
            raise ValueError("伪影动作必须为 mask_isolated_right_border_line")
        result[key] = row["image_preprocess"]
    return result


def _is_single_cjk_character(value: str) -> bool:
    if len(value) != 1:
        return False
    codepoint = ord(value)
    return 0x3400 <= codepoint <= 0x9FFF or 0xF900 <= codepoint <= 0xFAFF


def _split_characters(
    rows: list[dict[str, str]], seed: int, ratios: dict[str, float]
) -> tuple[dict[str, str], dict[str, int]]:
    styles_by_character: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        styles_by_character[row["character"]].add(row["style_id"])
    groups: dict[int, list[str]] = defaultdict(list)
    for character, styles in styles_by_character.items():
        groups[len(styles)].append(character)

    rng = random.Random(seed)
    assignments: dict[str, str] = {}
    for _, characters in sorted(groups.items()):
        characters.sort()
        rng.shuffle(characters)
        train_end = round(len(characters) * ratios["train"])
        validation_end = round(len(characters) * (ratios["train"] + ratios["validation"]))
        for index, character in enumerate(characters):
            assignments[character] = (
                "train" if index < train_end else "validation" if index < validation_end else "test"
            )
    coverage = {character: len(styles) for character, styles in styles_by_character.items()}
    return assignments, coverage


def _write_outputs(
    output_dir: Path,
    rows: list[dict[str, str]],
    character_splits: dict[str, str],
    coverage: dict[str, int],
    artifact_actions: dict[tuple[str, str, str], str],
    config: dict[str, Any],
) -> None:
    character_rows = [
        {"character": character, "split": character_splits[character], "external_style_coverage": coverage[character]}
        for character in sorted(character_splits)
    ]
    _write_csv(output_dir / "characters.csv", ("character", "split", "external_style_coverage"), character_rows)

    external_rows = []
    for row in rows:
        key = (row["style_id"], row["source_split"], row["raw_filename"])
        external_rows.append(
            {
                **row,
                "image_preprocess": artifact_actions.get(key, "none"),
                "dataset_scope": config["dataset_scope"],
                "character_split": character_splits[row["character"]],
            }
        )
    external_rows.sort(key=lambda row: (row["style_id"], row["source_split"], row["raw_filename"]))
    fieldnames = tuple([*dict.fromkeys(key for row in external_rows for key in row)])
    _write_csv(output_dir / "external_samples.csv", fieldnames, external_rows)

    render_plan = [
        {
            "style_id": style_id,
            "character": character,
            "character_split": character_splits[character],
            "source_kind": "open_font",
            "license_status": "OFL-1.1",
            "paper_eligible": "True",
            "dataset_scope": config["dataset_scope"],
        }
        for style_id in config["open_font_style_ids"]
        for character in sorted(character_splits)
    ]
    _write_csv(
        output_dir / "open_font_render_plan.csv",
        ("style_id", "character", "character_split", "source_kind", "license_status", "paper_eligible", "dataset_scope"),
        render_plan,
    )

    style_counts: dict[tuple[str, str, str, str], int] = Counter(
        (row["tier"], row["style_id"], row["paper_eligible"], row["character_split"])
        for row in external_rows
    )
    _write_csv(
        output_dir / "external_style_split_counts.csv",
        ("tier", "style_id", "paper_eligible", "character_split", "sample_count"),
        (
            {"tier": tier, "style_id": style_id, "paper_eligible": paper_eligible, "character_split": split, "sample_count": count}
            for (tier, style_id, paper_eligible, split), count in sorted(style_counts.items())
        ),
    )

    summary = _summary(rows, character_splits, config)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(_readme_text(summary), encoding="utf-8")


def _summary(rows: list[dict[str, str]], character_splits: dict[str, str], config: dict[str, Any]) -> dict[str, object]:
    return {
        "dataset_scope": config["dataset_scope"],
        "character_count": len(character_splits),
        "external_sample_count": len(rows),
        "external_style_count": len({row["style_id"] for row in rows}),
        "open_font_style_count": len(config["open_font_style_ids"]),
        "open_font_render_plan_count": len(config["open_font_style_ids"]) * len(character_splits),
        "paper_ready": all(row["paper_eligible"] == "True" for row in rows),
    }


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _readme_text(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# P1-extended 字符划分",
            "",
            "本清单按字符切分，不允许同一 Unicode 字符跨 train、validation、test。",
            f"- 外部字图：{summary['external_sample_count']} 张，{summary['external_style_count']} 种风格。",
            f"- 字符：{summary['character_count']} 个。",
            f"- 开源字体渲染计划：{summary['open_font_render_plan_count']} 条。",
            "",
            "ChineseStyle 已按用户确认纳入论文实验；其原始许可状态仍记录为 unverified。",
        ]
    ) + "\n"
