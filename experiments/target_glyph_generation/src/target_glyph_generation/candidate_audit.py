"""v2 字体候选的家族配额校验、可审计检查与人工预览。"""

from collections import Counter
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .font_files import find_missing_characters, sha256_file
from .models import FontSource
from .render import render_glyph


def validate_v2_style_pool(
    sources: list[FontSource],
    regular_style_count: int,
    writing_style_count: int,
    minimum_regular_families: int,
    maximum_styles_per_family: int,
    maximum_writing_styles_per_family: int,
) -> None:
    """验证 v2 风格池的类别、家族数量和每家族样式上限。"""
    if len({source.font_id for source in sources}) != len(sources):
        raise ValueError("v2 风格池 font_id 不可重复")
    regular = [source for source in sources if source.category == "regular"]
    writing = [source for source in sources if source.category == "writing"]
    if len(regular) != regular_style_count or len(writing) != writing_style_count:
        raise ValueError("v2 风格池的常规/书写数量不符合配额")
    if len({source.family_id for source in regular}) < minimum_regular_families:
        raise ValueError("v2 常规字体家族数量不足")
    regular_counts = Counter(source.family_id for source in regular)
    writing_counts = Counter(source.family_id for source in writing)
    ecosystem_counts = Counter(source.ecosystem_id for source in sources if source.ecosystem_id)
    display_count = sum(source.style_role == "display" for source in regular)
    if any(count > maximum_styles_per_family for count in regular_counts.values()):
        raise ValueError("常规字体家族上限被突破")
    if any(count > maximum_writing_styles_per_family for count in writing_counts.values()):
        raise ValueError("书写字体家族上限被突破")
    if ecosystem_counts["lxgw"] > 3:
        raise ValueError("LXGW 生态上限被突破")
    if display_count > 3:
        raise ValueError("展示字体上限被突破")
    if writing_style_count == 7:
        script_counts = Counter(source.script_class for source in writing)
        expected_script_counts = {"kaishu": 2, "xingkai": 2, "lishu": 1, "caoshu": 1, "transitional": 1}
        if script_counts != expected_script_counts:
            raise ValueError("书体配额不符合楷书2、行楷2、隶书1、草书1、过渡书体1")


def create_candidate_preview_grid(
    sources: list[FontSource],
    font_root: Path,
    characters: list[str],
    output_path: Path,
    canvas_size: int = 128,
) -> dict:
    """输出每个候选字体使用相同固定字符的预览网格。"""
    if len(characters) != 8:
        raise ValueError("候选预览必须使用 8 个固定字符")
    label_height = 20
    grid = Image.new("L", (canvas_size * len(characters), (canvas_size + label_height) * len(sources)), color=255)
    draw = ImageDraw.Draw(grid)
    font = ImageFont.load_default()
    for row, source in enumerate(sources):
        y = row * (canvas_size + label_height)
        label = "/".join(
            (source.font_id, source.ecosystem_id, source.script_class, source.style_role)
        )
        draw.text((2, y + 2), label.encode("unicode_escape").decode("ascii"), fill=0, font=font)
        for column, character in enumerate(characters):
            image = render_glyph(font_root / source.local_path, character, canvas_size)
            grid.paste(image, (column * canvas_size, y + label_height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output_path)
    return {"style_count": len(sources), "sampled_characters": characters, "grid_cells": len(sources) * len(characters)}


def _validate_preview_characters(preview_characters: list[str]) -> None:
    if len(preview_characters) != 8:
        raise ValueError("候选预览必须使用 8 个固定字符")
    if any(not isinstance(character, str) or len(character) != 1 for character in preview_characters):
        raise ValueError("候选预览字符必须均为单个字符")


def _resolve_candidate_relative_file_path(
    font_root: Path,
    relative_file_path: str,
    field_name: str,
    file_label: str,
) -> tuple[Path | None, str | None]:
    if not isinstance(relative_file_path, str) or not relative_file_path.strip():
        return None, f"{field_name} 必须是非空字符串相对路径"
    relative_path = Path(relative_file_path)
    if relative_path.is_absolute():
        return None, f"{field_name} 必须是非空相对路径"

    resolved_root = font_root.resolve()
    resolved_path = (resolved_root / relative_path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        return None, f"{field_name} 不可越出字体根目录"
    if not resolved_path.is_file():
        return None, f"{file_label}不存在"
    if resolved_path.stat().st_size == 0:
        return None, f"{file_label}为空"
    return resolved_path, None


def _resolve_candidate_font_path(font_root: Path, local_path: str) -> tuple[Path | None, str | None]:
    return _resolve_candidate_relative_file_path(font_root, local_path, "local_path", "字体文件")


def _resolve_candidate_license_path(font_root: Path, license_path: str) -> tuple[Path | None, str | None]:
    return _resolve_candidate_relative_file_path(font_root, license_path, "license_path", "许可证文件")


def audit_font_candidates(
    sources: list[FontSource],
    font_root: Path,
    characters: list[str],
    output_dir: Path,
    preview_characters: list[str],
    canvas_size: int = 128,
) -> dict:
    """审计候选字体的文件、字符覆盖和固定预览字符的可渲染性。"""
    _validate_preview_characters(preview_characters)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    accepted_sources = []

    for source in sources:
        record = {
            "font_id": source.font_id,
            "family_id": source.family_id,
            "category": source.category,
            "ecosystem_id": source.ecosystem_id,
            "script_class": source.script_class,
            "style_role": source.style_role,
            "font_sha256": None,
            "license_sha256": None,
            "missing_count": 0,
            "missing_characters": [],
            "preview_missing_characters": [],
            "file_error": None,
            "license_error": None,
            "render_error": None,
            "accepted": False,
        }
        font_path, file_error = _resolve_candidate_font_path(font_root, source.local_path)
        license_path, license_error = _resolve_candidate_license_path(font_root, source.license_path)
        if file_error is not None:
            record["file_error"] = file_error
        if license_error is not None:
            record["license_error"] = license_error
        else:
            try:
                record["license_sha256"] = sha256_file(license_path)
            except Exception as error:
                record["license_error"] = f"许可证文件读取失败：{error}"

        if record["file_error"] is None:
            try:
                record["font_sha256"] = sha256_file(font_path)
                missing_characters = find_missing_characters(font_path, characters)
                record["missing_characters"] = missing_characters
                record["missing_count"] = len(missing_characters)
                record["preview_missing_characters"] = find_missing_characters(
                    font_path, preview_characters
                )
            except Exception as error:
                record["file_error"] = f"字体文件读取失败：{error}"

            if record["file_error"] is None:
                try:
                    for character in preview_characters:
                        render_glyph(font_path, character, canvas_size)
                except Exception as error:
                    record["render_error"] = f"预览字符渲染失败：{error}"

        record["accepted"] = (
            record["file_error"] is None
            and record["license_error"] is None
            and record["missing_count"] == 0
            and not record["preview_missing_characters"]
            and record["render_error"] is None
        )
        records.append(record)
        if record["accepted"]:
            accepted_sources.append(source)

    summary = {
        "candidate_count": len(records),
        "accepted_count": len(accepted_sources),
        "rejected_count": len(records) - len(accepted_sources),
        "preview_characters": preview_characters,
        "records": records,
    }
    (output_dir / "candidate_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failures = [record for record in records if not record["accepted"]]
    (output_dir / "candidate_audit_failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    preview_grid_path = output_dir / "candidate_preview_grid.png"
    if accepted_sources:
        create_candidate_preview_grid(
            accepted_sources,
            font_root,
            preview_characters,
            preview_grid_path,
            canvas_size,
        )
    else:
        preview_grid_path.unlink(missing_ok=True)
    return summary
