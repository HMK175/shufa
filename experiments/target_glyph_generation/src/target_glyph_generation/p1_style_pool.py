"""Build a traceable P1 style registry from previously audited glyph labels."""

import csv
import json
from pathlib import Path
from typing import Any

import yaml


_STYLE_FIELDS = (
    "style_id",
    "display_name",
    "source_kind",
    "dataset_id",
    "license_status",
    "paper_eligible",
)
_CANDIDATE_FIELDS = (
    "tier",
    "dataset_id",
    "style_id",
    "style_display_name",
    "character",
    "source_split",
    "raw_filename",
    "target_path",
    "review_state",
    "ocr_score",
    "selection_rule",
    "audit_source",
    "paper_eligible",
    "paper_use_basis",
)


def build_style_pool(config_path: Path, output_dir: Path) -> dict[str, object]:
    """Write P1 core/extended manifests without copying source glyph images."""
    config_path = Path(config_path)
    config = _load_config(config_path)
    core_styles = _load_styles(config, "core_styles", expected_count=17)
    extended_styles = _load_styles(config, "extended_styles", expected_count=2)
    _validate_style_tiers(core_styles, extended_styles)

    core_candidates = _load_candidates(core_styles, "core", config_path.parent)
    extended_candidates = _load_candidates(extended_styles, "extended", config_path.parent)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "style_pool.csv", (*_STYLE_FIELDS, "paper_use_basis", "tier", "candidate_count"), _style_rows(core_styles, extended_styles, core_candidates, extended_candidates))
    _write_csv(output_dir / "core_calligrapher_candidates.csv", _CANDIDATE_FIELDS, core_candidates)
    _write_csv(output_dir / "extended_chinese_style_candidates.csv", _CANDIDATE_FIELDS, extended_candidates)

    summary = {
        "core_style_count": len(core_styles),
        "extended_style_count": len(extended_styles),
        "core_calligrapher_candidate_count": len(core_candidates),
        "extended_candidate_count": len(extended_candidates),
        "paper_core_ready": all(style["paper_eligible"] and style["license_status"] != "unverified" for style in core_styles),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(_readme_text(summary), encoding="utf-8")
    return summary


def _load_config(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"无法读取 P1 风格池配置：{path}") from error
    if not isinstance(payload, dict):
        raise ValueError("P1 风格池配置必须是 YAML 对象")
    return payload


def _load_styles(config: dict[str, Any], key: str, expected_count: int) -> list[dict[str, Any]]:
    payload = config.get(key)
    if not isinstance(payload, list) or len(payload) != expected_count:
        raise ValueError(f"{key} 必须恰好包含 {expected_count} 个风格")
    styles: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError(f"{key} 的每个风格必须是对象")
        style = dict(item)
        for field in _STYLE_FIELDS:
            value = style.get(field)
            if field == "paper_eligible":
                if not isinstance(value, bool):
                    raise ValueError(f"{key}.{field} 必须是布尔值")
            elif not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key}.{field} 必须是非空字符串")
        styles.append(style)
    if len({style["style_id"] for style in styles}) != len(styles):
        raise ValueError(f"{key} 中的 style_id 不可重复")
    return styles


def _validate_style_tiers(core_styles: list[dict[str, Any]], extended_styles: list[dict[str, Any]]) -> None:
    if {style["style_id"] for style in extended_styles} != {"lishu", "xingkai"}:
        raise ValueError("P1-extended 必须恰好包含 ChineseStyle 的 lishu 和 xingkai")
    if {style["style_id"] for style in core_styles} & {style["style_id"] for style in extended_styles}:
        raise ValueError("P1-core 与 P1-extended 不可包含同名风格")
    if any(not style["paper_eligible"] or style["license_status"] == "unverified" for style in core_styles):
        raise ValueError("P1-core 不能包含未许可或不可用于论文的风格")
    if any(
        not style["paper_eligible"]
        or style["license_status"] != "unverified"
        or style.get("paper_use_basis") != "user_confirmed_unverified_source"
        for style in extended_styles
    ):
        raise ValueError("P1-extended 必须记录用户确认的未核实来源状态")


def _load_candidates(styles: list[dict[str, Any]], tier: str, config_dir: Path) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for style in styles:
        source = style.get("candidate_source")
        if source is None:
            continue
        if not isinstance(source, dict):
            raise ValueError(f"{style['style_id']} 的 candidate_source 必须是对象")
        path_value = source.get("path")
        path_column = source.get("path_column")
        if not isinstance(path_value, str) or not path_value or not isinstance(path_column, str) or not path_column:
            raise ValueError(f"{style['style_id']} 的 candidate_source 必须包含 path 和 path_column")
        source_path = Path(path_value)
        if not source_path.is_absolute():
            source_path = config_dir / source_path
        rows = _read_csv(source_path)
        selection_rule = _selection_rule(source.get("filters"))
        for row in rows:
            if row.get("dataset_id") != style["dataset_id"] or row.get("style_id") != style["style_id"]:
                continue
            if not _matches_filters(row, source.get("filters")):
                continue
            character = row.get("character", "")
            if not _is_single_cjk_character(character):
                raise ValueError(f"{style['style_id']} 包含非单个 CJK 字符：{character!r}")
            image_path = row.get(path_column, "")
            if not image_path or not Path(image_path).is_file():
                raise ValueError(f"{style['style_id']} 的原始字图不存在：{image_path}")
            source_split = row.get("source_split", "")
            raw_filename = row.get("raw_filename", "")
            key = (style["style_id"], source_split, raw_filename)
            if not source_split or not raw_filename or key in seen_keys:
                raise ValueError(f"{style['style_id']} 存在重复或不完整的原图键：{key}")
            seen_keys.add(key)
            candidates.append(
                {
                    "tier": tier,
                    "dataset_id": style["dataset_id"],
                    "style_id": style["style_id"],
                    "style_display_name": row.get("style_display_name") or style["display_name"],
                    "character": character,
                    "source_split": source_split,
                    "raw_filename": raw_filename,
                    "target_path": image_path,
                    "review_state": row.get("review_state", ""),
                    "ocr_score": row.get("ocr_score", ""),
                    "selection_rule": selection_rule,
                    "audit_source": str(source_path),
                    "paper_eligible": str(style["paper_eligible"]),
                    "paper_use_basis": style.get("paper_use_basis", "license_verified"),
                }
            )
    return sorted(candidates, key=lambda row: (row["style_id"], row["source_split"], row["raw_filename"]))


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"候选清单没有表头：{path}")
            return list(reader)
    except OSError as error:
        raise ValueError(f"无法读取候选清单：{path}") from error


def _matches_filters(row: dict[str, str], filters: Any) -> bool:
    if filters is None:
        return True
    if not isinstance(filters, dict):
        raise ValueError("candidate_source.filters 必须是对象")
    for field, expected in filters.items():
        if field == "minimum_ocr_score":
            try:
                if float(row.get("ocr_score", "")) < float(expected):
                    return False
            except (TypeError, ValueError):
                return False
        elif field == "allowed_review_states":
            if not isinstance(expected, list) or row.get("review_state") not in expected:
                return False
        elif row.get(field) != str(expected):
            return False
    return True


def _selection_rule(filters: Any) -> str:
    if not filters:
        return "all_finalized_rows"
    if not isinstance(filters, dict):
        raise ValueError("candidate_source.filters 必须是对象")
    return "; ".join(f"{key}={value}" for key, value in filters.items())


def _is_single_cjk_character(value: str) -> bool:
    if len(value) != 1:
        return False
    codepoint = ord(value)
    return 0x3400 <= codepoint <= 0x9FFF or 0xF900 <= codepoint <= 0xFAFF


def _style_rows(
    core_styles: list[dict[str, Any]],
    extended_styles: list[dict[str, Any]],
    core_candidates: list[dict[str, str]],
    extended_candidates: list[dict[str, str]],
) -> list[dict[str, object]]:
    candidate_counts: dict[tuple[str, str], int] = {}
    for candidate in [*core_candidates, *extended_candidates]:
        key = (candidate["tier"], candidate["style_id"])
        candidate_counts[key] = candidate_counts.get(key, 0) + 1
    rows: list[dict[str, object]] = []
    for tier, styles in (("core", core_styles), ("extended", extended_styles)):
        for style in styles:
            rows.append(
                {
                    **{field: style[field] for field in _STYLE_FIELDS},
                    "paper_use_basis": style.get("paper_use_basis", "license_verified"),
                    "tier": tier,
                    "candidate_count": candidate_counts.get((tier, style["style_id"]), 0),
                }
            )
    return rows


def _write_csv(path: Path, fieldnames: tuple[str, ...], rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _readme_text(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# P1 风格池整合结果",
            "",
            f"- P1-core：{summary['core_style_count']} 种，允许作为论文正式结果的取数范围。",
            f"- P1-extended：{summary['extended_style_count']} 种，仅用于工程扩展实验。",
            f"- core 书法家候选：{summary['core_calligrapher_candidate_count']} 张。",
            f"- ChineseStyle 扩展候选：{summary['extended_candidate_count']} 张。",
            "",
            "ChineseStyle 已按用户确认纳入论文实验；其原始训练许可状态仍记录为 unverified。",
        ]
    ) + "\n"
