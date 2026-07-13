"""将已审计字体构建为 FontDiffuser 兼容的图像目录。"""

import csv
import json
from pathlib import Path

import yaml

from .characters import load_characters
from .font_files import find_missing_characters, sha256_file
from .fonts import load_font_sources
from .render import render_glyph
from .splits import split_characters, split_styles


def _validate_image(image) -> None:
    foreground = image.point(lambda pixel: 255 if pixel < 250 else 0).getbbox()
    if image.mode != "L" or image.size != (256, 256) or foreground is None:
        raise ValueError("渲染结果不是有效的 256×256 灰度字形图")
    if min(foreground[0], foreground[1], 256 - foreground[2], 256 - foreground[3]) < 4:
        raise ValueError("渲染结果距离画布边缘不足 4 像素")


def build_dataset(
    config_path: Path,
    sources_path: Path,
    characters_path: Path,
    output_root: Path,
    limit_fonts: int | None = None,
    limit_characters: int | None = None,
) -> dict:
    """构建可被 FontDiffuser 读取的内容图、目标图和可审计清单。"""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    canvas_size = int(config["canvas_size"])
    if canvas_size != 256:
        raise ValueError("当前 FontDiffuser 数据集固定使用 256×256 画布")

    characters = load_characters(characters_path)
    sources = load_font_sources(sources_path)
    failures: list[dict[str, str]] = []
    accepted = []
    for source in sources:
        font_path = output_root / source.local_path
        if not font_path.is_file() or font_path.stat().st_size == 0:
            failures.append({"font_id": source.font_id, "reason": "missing_font_file"})
            continue
        missing = find_missing_characters(font_path, characters)
        if missing:
            failures.append({"font_id": source.font_id, "reason": "missing_glyph", "count": str(len(missing))})
            continue
        accepted.append(source)

    if len(accepted) != 28:
        raise ValueError(f"有效字体数必须为 28，当前为 {len(accepted)}")
    style_splits = split_styles([source.font_id for source in accepted], int(config["character_seed"]))
    character_splits = split_characters(characters, int(config["character_seed"]))

    selected_fonts = accepted[:limit_fonts] if limit_fonts else accepted
    selected_characters = characters[:limit_characters] if limit_characters else characters
    content_source = next((source for source in accepted if source.font_id == "noto_sans_sc_400"), None)
    if content_source is None:
        raise ValueError("缺少规范内容字体 noto_sans_sc_400")

    content_dir = output_root / "rendered" / "ContentImage"
    target_dir = output_root / "rendered" / "TargetImage"
    manifest_dir = output_root / "manifests"
    for directory in (content_dir, target_dir, manifest_dir):
        directory.mkdir(parents=True, exist_ok=True)

    content_font_path = output_root / content_source.local_path
    for character in selected_characters:
        image = render_glyph(content_font_path, character, canvas_size)
        _validate_image(image)
        image.save(content_dir / f"{character}.png")

    rendered_targets = 0
    for source in selected_fonts:
        font_path = output_root / source.local_path
        style_dir = target_dir / source.font_id
        style_dir.mkdir(parents=True, exist_ok=True)
        for character in selected_characters:
            try:
                image = render_glyph(font_path, character, canvas_size)
                _validate_image(image)
                image.save(style_dir / f"{source.font_id}+{character}.png")
                rendered_targets += 1
            except (OSError, ValueError) as error:
                failures.append({"font_id": source.font_id, "character": character, "reason": str(error)})

    with (manifest_dir / "fonts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["font_id", "style_split", "display_name", "license_id", "license_url", "source_url", "local_path", "font_sha256"])
        writer.writeheader()
        for source in accepted:
            font_path = output_root / source.local_path
            writer.writerow({
                "font_id": source.font_id,
                "style_split": next(name for name, values in style_splits.items() if source.font_id in values),
                "display_name": source.display_name,
                "license_id": source.license_id,
                "license_url": source.license_url,
                "source_url": source.source_url,
                "local_path": source.local_path,
                "font_sha256": sha256_file(font_path),
            })
    with (manifest_dir / "characters.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["character", "split"])
        writer.writeheader()
        for split_name, values in character_splits.items():
            writer.writerows({"character": character, "split": split_name} for character in values)
    (manifest_dir / "splits.json").write_text(json.dumps({"characters": character_splits, "styles": style_splits}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (manifest_dir / "render_failures.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["font_id", "character", "reason", "count"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(failures)

    summary = {
        "candidate_font_count": len(sources),
        "accepted_font_count": len(accepted),
        "rendered_font_count": len(selected_fonts),
        "character_count": len(characters),
        "rendered_character_count": len(selected_characters),
        "content_image_count": len(selected_characters),
        "target_image_count": rendered_targets,
        "failure_count": len(failures),
        "smoke_build": bool(limit_fonts or limit_characters),
    }
    (manifest_dir / "dataset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
