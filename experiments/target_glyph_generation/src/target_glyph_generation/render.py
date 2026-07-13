"""统一输出 FontDiffuser 所需的黑字白底字形图。"""

from pathlib import Path
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=64)
def _load_font(font_path: str, size: int):
    return ImageFont.truetype(font_path, size=size)


def normalize_glyph_canvas(image: Image.Image, canvas_size: int) -> Image.Image:
    """裁去空白边缘后等比缩放并居中到固定方形画布。"""
    grayscale = image.convert("L")
    foreground = grayscale.point(lambda pixel: 255 if pixel < 250 else 0)
    bbox = foreground.getbbox()
    if bbox is None:
        raise ValueError("空白字形不可渲染")

    crop = grayscale.crop(bbox)
    padding = 16
    scale = min((canvas_size - padding) / crop.width, (canvas_size - padding) / crop.height)
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        resample=Image.Resampling.LANCZOS,
    )
    canvas = Image.new("L", (canvas_size, canvas_size), color=255)
    offset = ((canvas_size - resized.width) // 2, (canvas_size - resized.height) // 2)
    canvas.paste(resized, offset)
    return canvas


def render_glyph(font_path: Path, character: str, canvas_size: int) -> Image.Image:
    """将字体中的单个字符渲染成已归一化的黑字白底图像。"""
    if len(character) != 1:
        raise ValueError("一次只能渲染一个字符")

    font = _load_font(str(font_path), canvas_size * 3)
    bbox = font.getbbox(character)
    if bbox is None or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        raise ValueError(f"字体中无法渲染字符：{character}")

    padding = 32
    source = Image.new("L", (bbox[2] - bbox[0] + 2 * padding, bbox[3] - bbox[1] + 2 * padding), color=255)
    ImageDraw.Draw(source).text((padding - bbox[0], padding - bbox[1]), character, font=font, fill=0)
    return normalize_glyph_canvas(source, canvas_size)
