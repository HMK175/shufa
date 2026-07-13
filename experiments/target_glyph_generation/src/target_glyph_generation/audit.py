"""数据集摘要与人工审计网格。"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def summarize_dataset(style_ids, character_ids, failures):
    """返回适合记录在审计报告中的最小统计摘要。"""
    return {
        "accepted_style_count": len(set(style_ids)),
        "rendered_target_count": len(style_ids),
        "unique_character_count": len(set(character_ids)),
        "failure_count": len(failures),
    }


def create_audit_grid(dataset_root: Path, output_path: Path, samples_per_style: int = 8) -> dict:
    """从每个风格固定抽样字符，生成供人工目检的黑字白底网格。"""
    target_root = dataset_root / "rendered" / "TargetImage"
    style_dirs = sorted(path for path in target_root.iterdir() if path.is_dir())
    content_chars = sorted(path.stem for path in (dataset_root / "rendered" / "ContentImage").glob("*.png"))
    indices = [round(index * (len(content_chars) - 1) / (samples_per_style - 1)) for index in range(samples_per_style)]
    sampled_chars = [content_chars[index] for index in indices]
    tile = 112
    label_height = 20
    grid = Image.new("L", (samples_per_style * tile, len(style_dirs) * (tile + label_height)), color=255)
    draw = ImageDraw.Draw(grid)
    font = ImageFont.load_default()
    rendered = 0
    for row, style_dir in enumerate(style_dirs):
        y = row * (tile + label_height)
        draw.text((2, y + 2), style_dir.name, font=font, fill=0)
        for column, character in enumerate(sampled_chars):
            image_path = style_dir / f"{style_dir.name}+{character}.png"
            with Image.open(image_path) as image:
                grid.paste(image.convert("L").resize((tile, tile)), (column * tile, y + label_height))
            rendered += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(output_path)
    return {"style_count": len(style_dirs), "sampled_characters": sampled_chars, "grid_cells": rendered}


def write_audit_summary(dataset_root: Path, output_dir: Path) -> dict:
    """写入包含原始构建摘要及网格抽样信息的审计摘要。"""
    manifest_summary = json.loads((dataset_root / "manifests" / "dataset_summary.json").read_text(encoding="utf-8"))
    grid_summary = create_audit_grid(dataset_root, output_dir / "font_audit_grid.png")
    summary = {**manifest_summary, **grid_summary}
    (output_dir / "dataset_audit_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
