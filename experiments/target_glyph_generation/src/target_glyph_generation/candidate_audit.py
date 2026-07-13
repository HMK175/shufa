"""v2 字体候选的家族配额校验与人工预览。"""

from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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
        draw.text((2, y + 2), label.encode("ascii", "replace").decode("ascii"), fill=0, font=font)
        for column, character in enumerate(characters):
            image = render_glyph(font_root / source.local_path, character, canvas_size)
            grid.paste(image, (column * canvas_size, y + label_height))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output_path)
    return {"style_count": len(sources), "sampled_characters": characters, "grid_cells": len(sources) * len(characters)}
