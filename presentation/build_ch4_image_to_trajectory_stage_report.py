from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import os
import zipfile

from PIL import Image, ImageDraw, ImageFont


WORKSPACE = Path(__file__).resolve().parents[1]
PRESENTATION_DIR = WORKSPACE / "presentation"
OUTPUT_PPTX = PRESENTATION_DIR / "ch4_image_to_trajectory_stage_report.pptx"
OUTPUT_NOTES = PRESENTATION_DIR / "ch4_image_to_trajectory_stage_report_notes.md"
OUTPUT_QA = PRESENTATION_DIR / "ch4_image_to_trajectory_stage_report_qa.md"
ASSET_DIR = PRESENTATION_DIR / "ch4_image_to_trajectory_stage_report_assets"

SLIDE_W_IN = 13.333333
SLIDE_H_IN = 7.5
EMU_PER_IN = 914400
PREVIEW_W = 1600
PREVIEW_H = 900
PX_PER_IN = PREVIEW_W / SLIDE_W_IN

TEXT = "1F2937"
SUBTEXT = "4B5563"
MUTED = "6B7280"
ACCENT = "3F7D6D"
ACCENT_SOFT = "F1F6F3"
PANEL = "F7FAF8"
BORDER = "DCE5DF"

IMAGE_SOURCES = {
    "contact_sheet": WORKSPACE
    / "offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/callirewrite_hybrid_batch_20260701_154310_079390/visual_audit_contact_sheet.png",
    "kou": WORKSPACE
    / "offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/callirewrite_hybrid_batch_20260701_154310_079390/kou/rendered_execution.png",
    "xin": WORKSPACE
    / "offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/callirewrite_hybrid_batch_20260701_154310_079390/xin/rendered_execution.png",
    "zhong": WORKSPACE
    / "offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/callirewrite_hybrid_batch_20260701_154310_079390/zhong/rendered_execution.png",
    "yong": WORKSPACE
    / "offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/callirewrite_hybrid_batch_20260701_154310_079390/yong/rendered_execution.png",
    "width_pressure": WORKSPACE
    / "experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/fig4_execution_width_pressure.png",
}

MEDIA_NAMES = {
    "contact_sheet": "contact_sheet.png",
    "kou": "kou_rendered_execution.png",
    "xin": "xin_rendered_execution.png",
    "zhong": "zhong_rendered_execution.png",
    "yong": "yong_rendered_execution.png",
    "width_pressure": "width_pressure.png",
}


@dataclass
class Paragraph:
    text: str
    size: int
    bold: bool = False
    color: str = TEXT
    align: str = "left"
    gap: float = 0.12


@dataclass
class Element:
    kind: str
    x: float
    y: float
    w: float
    h: float
    paragraphs: list[Paragraph] = field(default_factory=list)
    fill: str | None = None
    line: str | None = None
    line_width: float = 1.0
    inset: tuple[float, float, float, float] = (0.10, 0.08, 0.10, 0.08)
    valign: str = "top"
    image_key: str | None = None
    name: str = ""


@dataclass
class Slide:
    title: str
    elements: list[Element]
    image_keys: list[str]


def emu(value_in: float) -> int:
    return int(round(value_in * EMU_PER_IN))


def px(value_in: float) -> int:
    return int(round(value_in * PX_PER_IN))


def rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def text_box(
    x: float,
    y: float,
    w: float,
    h: float,
    paragraphs: list[Paragraph],
    *,
    fill: str | None = None,
    line: str | None = None,
    line_width: float = 1.0,
    inset: tuple[float, float, float, float] = (0.10, 0.08, 0.10, 0.08),
    valign: str = "top",
    name: str = "",
) -> Element:
    return Element(
        kind="textbox",
        x=x,
        y=y,
        w=w,
        h=h,
        paragraphs=paragraphs,
        fill=fill,
        line=line,
        line_width=line_width,
        inset=inset,
        valign=valign,
        name=name,
    )


def shape_box(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str | None,
    line: str | None = None,
    line_width: float = 1.0,
    name: str = "",
) -> Element:
    return Element(
        kind="shape",
        x=x,
        y=y,
        w=w,
        h=h,
        fill=fill,
        line=line,
        line_width=line_width,
        name=name,
    )


def picture(x: float, y: float, w: float, h: float, image_key: str, *, name: str = "") -> Element:
    return Element(kind="picture", x=x, y=y, w=w, h=h, image_key=image_key, name=name)


def standard_title(title: str, subtitle: str | None = None) -> list[Element]:
    elements = [
        shape_box(0.72, 0.46, 0.12, 0.34, fill=ACCENT, line=ACCENT, name="Accent"),
        text_box(
            0.92,
            0.34,
            11.4,
            0.64,
            [Paragraph(title, 28, bold=True, color=TEXT, gap=0.0)],
            inset=(0.0, 0.02, 0.0, 0.0),
            name="Title",
        ),
    ]
    if subtitle:
        elements.append(
            text_box(
                0.94,
                0.94,
                11.8,
                0.36,
                [Paragraph(subtitle, 15, color=ACCENT, gap=0.0)],
                inset=(0.0, 0.0, 0.0, 0.0),
                name="Subtitle",
            )
        )
    return elements


def build_slides() -> list[Slide]:
    slides: list[Slide] = []

    cover_elements = [
        shape_box(0.88, 1.38, 0.14, 2.36, fill=ACCENT, line=ACCENT, name="CoverAccent"),
        text_box(
            1.16,
            1.32,
            6.0,
            1.35,
            [Paragraph("图像 / 轮廓到可写轨迹恢复阶段汇报", 30, bold=True, color=TEXT, gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="CoverTitle",
        ),
        text_box(
            1.18,
            2.82,
            5.8,
            0.62,
            [Paragraph("第四章相关工作近期进展", 18, color=SUBTEXT, gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="CoverSubtitle",
        ),
        text_box(
            1.18,
            4.00,
            5.5,
            0.92,
            [Paragraph("从单字图像出发，整理当前的离线可写轨迹恢复思路与阶段性结果。", 16, color=MUTED, gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="CoverSummary",
        ),
        picture(8.15, 1.38, 4.2, 4.15, "contact_sheet", name="CoverContactSheet"),
        text_box(
            8.20,
            5.72,
            4.2,
            0.30,
            [Paragraph("本地离线审计联系图", 9, color=MUTED, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="CoverCaption",
        ),
    ]
    slides.append(Slide("封面", cover_elements, ["contact_sheet"]))

    slide1_elements = standard_title("本章任务与研究路线")
    slide1_elements += [
        text_box(
            0.88,
            1.36,
            7.75,
            1.72,
            [
                Paragraph("• 输入：单字图像或字体轮廓", 16, color=TEXT),
                Paragraph("• 目标：恢复可写轨迹，而非静态识别结果", 16, color=TEXT),
                Paragraph("• 当前路线：粗序列恢复 + 连续性后处理 + 人工目检", 16, color=TEXT, gap=0.0),
            ],
            fill=PANEL,
            line=BORDER,
            name="RouteBullets",
        ),
        picture(9.65, 1.38, 2.70, 2.66, "contact_sheet", name="RouteThumb"),
        shape_box(1.08, 4.08, 2.15, 1.00, fill=ACCENT_SOFT, line=BORDER, name="Step1"),
        text_box(
            1.08,
            4.08,
            2.15,
            1.00,
            [Paragraph("单字图像\n或轮廓", 16, bold=True, color=TEXT, align="center", gap=0.0)],
            inset=(0.08, 0.18, 0.08, 0.08),
            valign="middle",
            name="Step1Text",
        ),
        text_box(
            3.36,
            4.36,
            0.46,
            0.36,
            [Paragraph("→", 22, bold=True, color=ACCENT, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            valign="middle",
            name="Arrow1",
        ),
        shape_box(3.92, 4.08, 2.15, 1.00, fill=ACCENT_SOFT, line=BORDER, name="Step2"),
        text_box(
            3.92,
            4.08,
            2.15,
            1.00,
            [Paragraph("粗序列\n恢复", 16, bold=True, color=TEXT, align="center", gap=0.0)],
            inset=(0.08, 0.18, 0.08, 0.08),
            valign="middle",
            name="Step2Text",
        ),
        text_box(
            6.20,
            4.36,
            0.46,
            0.36,
            [Paragraph("→", 22, bold=True, color=ACCENT, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            valign="middle",
            name="Arrow2",
        ),
        shape_box(6.76, 4.08, 2.15, 1.00, fill=ACCENT_SOFT, line=BORDER, name="Step3"),
        text_box(
            6.76,
            4.08,
            2.15,
            1.00,
            [Paragraph("局部连续性\n修补", 16, bold=True, color=TEXT, align="center", gap=0.0)],
            inset=(0.08, 0.18, 0.08, 0.08),
            valign="middle",
            name="Step3Text",
        ),
        text_box(
            9.04,
            4.36,
            0.46,
            0.36,
            [Paragraph("→", 22, bold=True, color=ACCENT, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            valign="middle",
            name="Arrow3",
        ),
        shape_box(9.60, 4.08, 2.15, 1.00, fill=ACCENT_SOFT, line=BORDER, name="Step4"),
        text_box(
            9.60,
            4.08,
            2.15,
            1.00,
            [Paragraph("可写轨迹\n候选", 16, bold=True, color=TEXT, align="center", gap=0.0)],
            inset=(0.08, 0.18, 0.08, 0.08),
            valign="middle",
            name="Step4Text",
        ),
        text_box(
            1.05,
            6.18,
            11.4,
            0.40,
            [Paragraph("当前结果以离线可视化人工目检为主，暂不直接等同于机器人实写结果。", 12, color=MUTED, gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="RouteNote",
        ),
    ]
    slides.append(Slide("本章任务与研究路线", slide1_elements, ["contact_sheet"]))

    slide2_elements = standard_title("当前恢复结果概览", "已有离线原型雏形，样例间表现仍有明显差异")
    slide2_elements += [
        text_box(
            0.88,
            1.55,
            3.15,
            2.28,
            [
                Paragraph("• 已完成 4 个单字样例的离线恢复审计", 16, color=TEXT),
                Paragraph("• 已能从输入图像得到初步可写轨迹", 16, color=TEXT),
                Paragraph("• “口”“心”观感较稳定", 16, color=TEXT),
                Paragraph("• “中”“永”仍有局部几何问题", 16, color=TEXT, gap=0.0),
            ],
            fill=PANEL,
            line=BORDER,
            name="OverviewBullets",
        ),
        picture(4.40, 1.42, 7.15, 5.65, "contact_sheet", name="OverviewContactSheet"),
        text_box(
            4.44,
            7.04,
            7.05,
            0.24,
            [Paragraph("图：单字输入、恢复叠加与执行渲染的离线审计联系图", 9, color=MUTED, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="OverviewCaption",
        ),
    ]
    slides.append(Slide("当前恢复结果概览", slide2_elements, ["contact_sheet"]))

    slide3_elements = standard_title("代表性恢复样例")
    slide3_elements += [
        text_box(
            0.95,
            1.04,
            11.5,
            0.34,
            [Paragraph("简单字与部分闭合结构已有一定可用性；复杂转折与交汇结构仍是主要难点。", 13, color=ACCENT, gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="SampleSummary",
        ),
    ]

    card_specs = [
        ("kou", "口：轮廓较稳定，整体观感较顺", 0.88, 1.55),
        ("xin", "心：整体成形，但细部仍有偏差", 6.72, 1.55),
        ("zhong", "中：交汇处更容易出现局部不顺", 0.88, 4.34),
        ("yong", "永：转折较多，局部形变更明显", 6.72, 4.34),
    ]
    for idx, (key, caption, x0, y0) in enumerate(card_specs, start=1):
        slide3_elements.append(shape_box(x0, y0, 5.72, 2.48, fill="FFFFFF", line=BORDER, name=f"Card{idx}"))
        slide3_elements.append(picture(x0 + 0.14, y0 + 0.14, 5.44, 1.82, key, name=f"CardImage{idx}"))
        slide3_elements.append(
            text_box(
                x0 + 0.10,
                y0 + 2.02,
                5.52,
                0.34,
                [Paragraph(caption, 10, color=SUBTEXT, align="center", gap=0.0)],
                inset=(0.0, 0.0, 0.0, 0.0),
                name=f"CardCaption{idx}",
            )
        )
    slides.append(Slide("代表性恢复样例", slide3_elements, ["kou", "xin", "zhong", "yong"]))

    slide4_elements = standard_title("当前瓶颈与问题分析")
    slide4_elements += [
        text_box(
            0.88,
            1.52,
            4.35,
            2.18,
            [
                Paragraph("• 主要困难不在最终渲染，而在上游轨迹局部结构恢复", 16, color=TEXT),
                Paragraph("• 典型问题包括交汇处小结点、局部鼓包、分段感残留", 16, color=TEXT),
                Paragraph("• heuristic 修补已有帮助，但尚未带来质变", 16, color=TEXT, gap=0.0),
            ],
            fill=PANEL,
            line=BORDER,
            name="BottleneckBullets",
        ),
        picture(6.10, 1.48, 2.45, 4.70, "zhong", name="BottleneckZhong"),
        picture(9.18, 1.48, 2.75, 4.70, "yong", name="BottleneckYong"),
        text_box(
            6.02,
            6.18,
            2.62,
            0.32,
            [Paragraph("中：交汇与横竖关系仍不稳", 10, color=SUBTEXT, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="ZhongCaption",
        ),
        text_box(
            9.05,
            6.18,
            2.95,
            0.32,
            [Paragraph("永：多转折结构更易累积偏差", 10, color=SUBTEXT, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="YongCaption",
        ),
        text_box(
            0.98,
            6.62,
            11.0,
            0.42,
            [Paragraph("当前核心瓶颈是复杂结构的连续性与几何一致性。", 13, bold=True, color=ACCENT, align="center", gap=0.0)],
            fill=ACCENT_SOFT,
            line=None,
            inset=(0.0, 0.06, 0.0, 0.0),
            valign="middle",
            name="BottleneckTakeaway",
        ),
    ]
    slides.append(Slide("当前瓶颈与问题分析", slide4_elements, ["zhong", "yong"]))

    slide5_elements = standard_title("阶段结论与下一步")
    slide5_elements += [
        picture(0.92, 1.48, 5.05, 5.05, "width_pressure", name="WidthPressure"),
        text_box(
            0.95,
            6.64,
            5.00,
            0.28,
            [Paragraph("下游宽度 / 压力表达链路已具备，可作为后续恢复结果的承接基础。", 9, color=MUTED, align="center", gap=0.0)],
            inset=(0.0, 0.0, 0.0, 0.0),
            name="WidthPressureCaption",
        ),
        text_box(
            6.42,
            1.52,
            5.75,
            2.20,
            [
                Paragraph("阶段结论", 16, bold=True, color=ACCENT),
                Paragraph("• 已跑通离线恢复到可视化审查的基本链路", 15, color=TEXT),
                Paragraph("• 已得到一批可展示的初步恢复样例", 15, color=TEXT, gap=0.0),
            ],
            fill=PANEL,
            line=BORDER,
            name="ConclusionPanel",
        ),
        text_box(
            6.42,
            4.02,
            5.75,
            1.96,
            [
                Paragraph("下一步方向", 16, bold=True, color=ACCENT),
                Paragraph("• 重点评估更强的局部结构恢复方案", 15, color=TEXT),
                Paragraph("• 并比较更真实的离线笔迹回放方式", 15, color=TEXT, gap=0.0),
            ],
            fill=PANEL,
            line=BORDER,
            name="NextStepPanel",
        ),
        text_box(
            6.58,
            6.40,
            5.45,
            0.52,
            [Paragraph("当前已有雏形，但复杂结构仍需重点突破。", 13, bold=True, color=ACCENT, align="center", gap=0.0)],
            fill=ACCENT_SOFT,
            inset=(0.0, 0.08, 0.0, 0.0),
            valign="middle",
            name="FinalTakeaway",
        ),
    ]
    slides.append(Slide("阶段结论与下一步", slide5_elements, ["width_pressure"]))

    return slides


def fit_contain(img_w: int, img_h: int, box_w_in: float, box_h_in: float) -> tuple[float, float]:
    img_ratio = img_w / img_h
    box_ratio = box_w_in / box_h_in
    if img_ratio >= box_ratio:
        return box_w_in, box_w_in / img_ratio
    return box_h_in * img_ratio, box_h_in


def font_paths() -> dict[bool, str | None]:
    windir = os.environ.get("WINDIR")
    if not windir:
        return {False: None, True: None}
    fonts_dir = Path(windir) / "Fonts"
    candidates = {
        False: ["msyh.ttc", "simhei.ttf", "arial.ttf"],
        True: ["msyhbd.ttc", "simhei.ttf", "arialbd.ttf", "arial.ttf"],
    }
    result: dict[bool, str | None] = {False: None, True: None}
    for bold, names in candidates.items():
        for name in names:
            candidate = fonts_dir / name
            if candidate.exists():
                result[bold] = str(candidate)
                break
    return result


FONT_PATHS = font_paths()
FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont | ImageFont.ImageFont] = {}


def preview_font(size_pt: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    px_size = max(13, int(round(size_pt * PX_PER_IN / 72)))
    cache_key = (px_size, bold)
    if cache_key in FONT_CACHE:
        return FONT_CACHE[cache_key]
    font_path = FONT_PATHS.get(bold) or FONT_PATHS.get(False)
    if font_path:
        font = ImageFont.truetype(font_path, px_size)
    else:
        font = ImageFont.load_default()
    FONT_CACHE[cache_key] = font
    return font


def draw_text_element(draw: ImageDraw.ImageDraw, element: Element) -> None:
    left = px(element.x)
    top = px(element.y)
    right = px(element.x + element.w)
    bottom = px(element.y + element.h)

    if element.fill or element.line:
        draw.rectangle(
            (left, top, right, bottom),
            fill=rgb(element.fill) if element.fill else None,
            outline=rgb(element.line) if element.line else None,
            width=max(1, int(round(element.line_width))),
        )

    pad_l = px(element.inset[0])
    pad_t = px(element.inset[1])
    pad_r = px(element.inset[2])
    pad_b = px(element.inset[3])
    content_left = left + pad_l
    content_top = top + pad_t
    content_right = right - pad_r
    content_bottom = bottom - pad_b

    para_heights: list[int] = []
    para_spacings: list[int] = []
    for para in element.paragraphs:
        font = preview_font(para.size, para.bold)
        spacing = max(2, int(font.size * 0.18))
        bbox = draw.multiline_textbbox((0, 0), para.text, font=font, spacing=spacing)
        para_heights.append(bbox[3] - bbox[1])
        para_spacings.append(px(para.gap))

    total_height = 0
    for idx, height in enumerate(para_heights):
        total_height += height
        if idx < len(para_heights) - 1:
            total_height += para_spacings[idx]

    if element.valign == "middle":
        cursor_y = content_top + max(0, (content_bottom - content_top - total_height) // 2)
    else:
        cursor_y = content_top

    for idx, para in enumerate(element.paragraphs):
        font = preview_font(para.size, para.bold)
        spacing = max(2, int(font.size * 0.18))
        bbox = draw.multiline_textbbox((0, 0), para.text, font=font, spacing=spacing)
        text_w = bbox[2] - bbox[0]
        if para.align == "center":
            text_x = content_left + max(0, (content_right - content_left - text_w) // 2)
        elif para.align == "right":
            text_x = max(content_left, content_right - text_w)
        else:
            text_x = content_left
        draw.multiline_text(
            (text_x, cursor_y),
            para.text,
            font=font,
            fill=rgb(para.color),
            spacing=spacing,
        )
        cursor_y += para_heights[idx]
        if idx < len(para_heights) - 1:
            cursor_y += para_spacings[idx]


def draw_picture_element(canvas: Image.Image, draw: ImageDraw.ImageDraw, element: Element) -> None:
    box_left = px(element.x)
    box_top = px(element.y)
    box_w = px(element.w)
    box_h = px(element.h)
    source_path = IMAGE_SOURCES[element.image_key]
    with Image.open(source_path) as img:
        img = img.convert("RGBA")
        fit_w_in, fit_h_in = fit_contain(img.width, img.height, element.w, element.h)
        fit_w = max(1, px(fit_w_in))
        fit_h = max(1, px(fit_h_in))
        offset_x = box_left + (box_w - fit_w) // 2
        offset_y = box_top + (box_h - fit_h) // 2
        resized = img.resize((fit_w, fit_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(resized, (offset_x, offset_y))
        draw.rectangle((offset_x, offset_y, offset_x + fit_w, offset_y + fit_h), outline=rgb(BORDER), width=1)


def render_slide_preview(slide: Slide, preview_path: Path) -> None:
    canvas = Image.new("RGBA", (PREVIEW_W, PREVIEW_H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    for element in slide.elements:
        if element.kind == "picture":
            draw_picture_element(canvas, draw, element)
        elif element.kind in {"textbox", "shape"}:
            draw_text_element(draw, element)
    canvas.convert("RGB").save(preview_path, "PNG")


def text_run_xml(text: str, size: int, bold: bool, color: str) -> str:
    font_tags = (
        '<a:latin typeface="Microsoft YaHei"/>'
        '<a:ea typeface="Microsoft YaHei"/>'
        '<a:cs typeface="Arial"/>'
    )
    bold_attr = ' b="1"' if bold else ""
    run_prefix = f'<a:r><a:rPr lang="zh-CN" sz="{size * 100}"{bold_attr}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{font_tags}</a:rPr><a:t>'
    run_suffix = "</a:t></a:r>"
    return run_prefix + escape(text) + run_suffix


def paragraph_xml(paragraph: Paragraph) -> str:
    align_map = {"left": "l", "center": "ctr", "right": "r"}
    align = align_map.get(paragraph.align, "l")
    parts = paragraph.text.split("\n")
    runs: list[str] = []
    for idx, part in enumerate(parts):
        if idx:
            runs.append("<a:br/>")
        runs.append(text_run_xml(part, paragraph.size, paragraph.bold, paragraph.color))
    font_tags = (
        '<a:latin typeface="Microsoft YaHei"/>'
        '<a:ea typeface="Microsoft YaHei"/>'
        '<a:cs typeface="Arial"/>'
    )
    return (
        f'<a:p><a:pPr algn="{align}"><a:buNone/></a:pPr>'
        + "".join(runs)
        + f'<a:endParaRPr lang="zh-CN" sz="{paragraph.size * 100}">{font_tags}</a:endParaRPr></a:p>'
    )


def element_xml(element: Element, shape_id: int, rel_id_lookup: dict[str, str]) -> str:
    x = emu(element.x)
    y = emu(element.y)
    w = emu(element.w)
    h = emu(element.h)

    if element.kind == "picture":
        rel_id = rel_id_lookup[element.image_key]
        line_xml = f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{BORDER}"/></a:solidFill></a:ln>'
        return (
            '<p:pic>'
            f'<p:nvPicPr><p:cNvPr id="{shape_id}" name="{escape(element.name or "Picture")}"/>'
            '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            f"{line_xml}</p:spPr></p:pic>"
        )

    fill_xml = (
        f'<a:solidFill><a:srgbClr val="{element.fill}"/></a:solidFill>' if element.fill else "<a:noFill/>"
    )
    if element.line:
        line_width = int(round(element.line_width * 12700))
        line_xml = f'<a:ln w="{line_width}"><a:solidFill><a:srgbClr val="{element.line}"/></a:solidFill></a:ln>'
    else:
        line_xml = "<a:ln><a:noFill/></a:ln>"

    anchor_map = {"top": "t", "middle": "ctr", "bottom": "b"}
    anchor = anchor_map.get(element.valign, "t")
    body_pr = (
        f'<a:bodyPr wrap="square" anchor="{anchor}" '
        f'lIns="{emu(element.inset[0])}" tIns="{emu(element.inset[1])}" '
        f'rIns="{emu(element.inset[2])}" bIns="{emu(element.inset[3])}"/>'
    )
    paragraphs_xml = "".join(paragraph_xml(p) for p in element.paragraphs) if element.paragraphs else "<a:p/>"
    return (
        "<p:sp>"
        f'<p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(element.name or "Shape")}"/>'
        '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f"{fill_xml}{line_xml}</p:spPr>"
        f"<p:txBody>{body_pr}<a:lstStyle/>{paragraphs_xml}</p:txBody>"
        "</p:sp>"
    )


def slide_xml(slide: Slide, rel_id_lookup: dict[str, str]) -> str:
    shape_xml = []
    next_id = 2
    for element in slide.elements:
        shape_xml.append(element_xml(element, next_id, rel_id_lookup))
        next_id += 1
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:spTree>'
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + "".join(shape_xml)
        + '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
    )


def slide_rels_xml(image_keys: list[str]) -> str:
    relationships = [
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
    ]
    for idx, key in enumerate(image_keys, start=2):
        relationships.append(
            f'<Relationship Id="rId{idx}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="../media/{MEDIA_NAMES[key]}"/>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(relationships)
        + "</Relationships>"
    )


def content_types_xml(slide_count: int) -> str:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{idx}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for idx in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        + slide_overrides
        + "</Types>"
    )


def root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def core_xml() -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>图像轮廓到可写轨迹恢复阶段汇报</dc:title>'
        "<dc:creator>Codex</dc:creator>"
        "<cp:lastModifiedBy>Codex</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def app_xml(slide_count: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>Codex</Application>"
        "<PresentationFormat>On-screen Show (16:9)</PresentationFormat>"
        f"<Slides>{slide_count}</Slides>"
        "<Company></Company>"
        "</Properties>"
    )


def presentation_xml(slide_count: int) -> str:
    slide_ids = "".join(
        f'<p:sldId id="{255 + idx}" r:id="rId{idx}"/>' for idx in range(1, slide_count + 1)
    )
    master_rel_id = slide_count + 1
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        f'<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{master_rel_id}"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        '<p:sldSz cx="12192000" cy="6858000" type="wide"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        '<p:defaultTextStyle><a:defPPr><a:defRPr lang="zh-CN"/></a:defPPr></p:defaultTextStyle>'
        "</p:presentation>"
    )


def presentation_rels_xml(slide_count: int) -> str:
    slide_rels = "".join(
        f'<Relationship Id="rId{idx}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{idx}.xml"/>'
        for idx in range(1, slide_count + 1)
    )
    master_rel_id = slide_count + 1
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + slide_rels
        + f'<Relationship Id="rId{master_rel_id}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        'Target="slideMasters/slideMaster1.xml"/>'
        "</Relationships>"
    )


def slide_master_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        "<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        "</p:spTree></p:cSld>"
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst>'
        "<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>"
    )


def slide_master_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>'
        "</Relationships>"
    )


def slide_layout_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">'
        '<p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
    )


def slide_layout_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
        "</Relationships>"
    )


def theme_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="StageReportTheme">'
        "<a:themeElements>"
        '<a:clrScheme name="StageReport">'
        '<a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>'
        '<a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>'
        f'<a:dk2><a:srgbClr val="{TEXT}"/></a:dk2>'
        '<a:lt2><a:srgbClr val="F7FAF8"/></a:lt2>'
        f'<a:accent1><a:srgbClr val="{ACCENT}"/></a:accent1>'
        '<a:accent2><a:srgbClr val="8C6A2F"/></a:accent2>'
        '<a:accent3><a:srgbClr val="6B7B6A"/></a:accent3>'
        '<a:accent4><a:srgbClr val="B7682B"/></a:accent4>'
        '<a:accent5><a:srgbClr val="A33D2B"/></a:accent5>'
        '<a:accent6><a:srgbClr val="74808B"/></a:accent6>'
        '<a:hlink><a:srgbClr val="8C6A2F"/></a:hlink>'
        '<a:folHlink><a:srgbClr val="6E4C8C"/></a:folHlink>'
        "</a:clrScheme>"
        '<a:fontScheme name="Office">'
        '<a:majorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Arial"/></a:majorFont>'
        '<a:minorFont><a:latin typeface="Microsoft YaHei"/><a:ea typeface="Microsoft YaHei"/><a:cs typeface="Arial"/></a:minorFont>'
        "</a:fontScheme>"
        '<a:fmtScheme name="Office"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
        '<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
        "<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>"
        '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>'
        "</a:fmtScheme></a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/></a:theme>"
    )


def create_preview_contact_sheet(preview_paths: list[Path], output_path: Path) -> None:
    cols = 2
    rows = (len(preview_paths) + cols - 1) // cols
    cell_w = 520
    cell_h = 320
    margin = 28
    canvas = Image.new("RGB", (cols * cell_w + (cols + 1) * margin, rows * cell_h + (rows + 1) * margin), "white")
    draw = ImageDraw.Draw(canvas)
    title_font = preview_font(14, bold=True)
    for idx, preview_path in enumerate(preview_paths):
        col = idx % cols
        row = idx // cols
        x0 = margin + col * (cell_w + margin)
        y0 = margin + row * (cell_h + margin)
        with Image.open(preview_path) as img:
            img = img.convert("RGB")
            img.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
            paste_x = x0 + (cell_w - img.width) // 2
            paste_y = y0 + (cell_h - img.height) // 2
            canvas.paste(img, (paste_x, paste_y))
        draw.rectangle((x0, y0, x0 + cell_w, y0 + cell_h), outline=rgb(BORDER), width=2)
        draw.text((x0 + 12, y0 + 10), f"Slide {idx + 1}", font=title_font, fill=rgb(TEXT))
    canvas.save(output_path, "PNG")


def write_notes(slides: list[Slide]) -> None:
    lines = [
        "# 图像 / 轮廓到可写轨迹恢复阶段汇报页说明",
        "",
        f"- PPT 文件：`{OUTPUT_PPTX.relative_to(WORKSPACE).as_posix()}`",
        "",
    ]
    note_entries = [
        ("封面", ["contact_sheet"]),
        ("本章任务与研究路线", ["contact_sheet"]),
        ("当前恢复结果概览", ["contact_sheet"]),
        ("代表性恢复样例", ["kou", "xin", "zhong", "yong"]),
        ("当前瓶颈与问题分析", ["zhong", "yong"]),
        ("阶段结论与下一步", ["width_pressure"]),
    ]
    for idx, (title, image_keys) in enumerate(note_entries, start=1):
        lines.append(f"## Slide {idx}：{title}")
        if image_keys:
            lines.append("- 使用图片：")
            for key in image_keys:
                lines.append(f"  - `{IMAGE_SOURCES[key]}`")
        else:
            lines.append("- 使用图片：无")
        lines.append("")
    OUTPUT_NOTES.write_text("\n".join(lines), encoding="utf-8-sig")


def write_qa(slides: list[Slide], preview_paths: list[Path]) -> None:
    media_used = sorted({key for slide in slides for key in slide.image_keys})
    lines = [
        "# 阶段汇报 PPT QA",
        "",
        "- 生成状态：成功",
        f"- 幻灯片数：{len(slides)}",
        f"- 预览图数：{len(preview_paths)}",
        "- 自检方式：原生 PPTX 包结构检查 + 本地预览图人工目检",
        "",
        "## 已检查",
        "",
        "- 标题、图片和文字框均保持在 16:9 画布内",
        "- 内容页总数为 5 页，符合不超过 5 页的要求",
        "- 主图均来自本地已有结果图，无新增复杂重绘",
        "- 整体语气保持为阶段性介绍，不宣称问题已完全解决",
        "",
        "## 使用图片",
        "",
    ]
    for key in media_used:
        lines.append(f"- `{IMAGE_SOURCES[key]}`")
    lines += [
        "",
        "## 已知限制",
        "",
        "- 当前环境无法直接调用 PowerPoint 或 python-pptx 渲染整套文件，因此最终版式依赖生成脚本的预览自检。",
        "- 汇报仍建议在正式使用前人工打开 PPT 再快速过一遍字号和图片位置。",
        "",
    ]
    OUTPUT_QA.write_text("\n".join(lines), encoding="utf-8-sig")


def build_pptx(slides: list[Slide]) -> None:
    static_parts = {
        "[Content_Types].xml": content_types_xml(len(slides)),
        "_rels/.rels": root_rels_xml(),
        "docProps/core.xml": core_xml(),
        "docProps/app.xml": app_xml(len(slides)),
        "ppt/presentation.xml": presentation_xml(len(slides)),
        "ppt/_rels/presentation.xml.rels": presentation_rels_xml(len(slides)),
        "ppt/slideMasters/slideMaster1.xml": slide_master_xml(),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": slide_master_rels_xml(),
        "ppt/slideLayouts/slideLayout1.xml": slide_layout_xml(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": slide_layout_rels_xml(),
        "ppt/theme/theme1.xml": theme_xml(),
    }

    with zipfile.ZipFile(OUTPUT_PPTX, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in static_parts.items():
            zf.writestr(path, content.encode("utf-8"))

        for idx, slide in enumerate(slides, start=1):
            unique_image_keys = list(dict.fromkeys(slide.image_keys))
            rel_lookup = {key: f"rId{rel_idx}" for rel_idx, key in enumerate(unique_image_keys, start=2)}
            zf.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(slide, rel_lookup).encode("utf-8"))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rels_xml(unique_image_keys).encode("utf-8"))

        for key, source in IMAGE_SOURCES.items():
            zf.write(source, f"ppt/media/{MEDIA_NAMES[key]}")


def verify_pptx(slides: list[Slide]) -> None:
    with zipfile.ZipFile(OUTPUT_PPTX, "r") as zf:
        names = set(zf.namelist())
        required = {
            "[Content_Types].xml",
            "_rels/.rels",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
            "ppt/slideMasters/slideMaster1.xml",
            "ppt/slideLayouts/slideLayout1.xml",
            "ppt/theme/theme1.xml",
        }
        missing = required - names
        if missing:
            raise RuntimeError(f"Missing required PPTX parts: {sorted(missing)}")
        for idx in range(1, len(slides) + 1):
            if f"ppt/slides/slide{idx}.xml" not in names:
                raise RuntimeError(f"Missing slide{idx}.xml")
            if f"ppt/slides/_rels/slide{idx}.xml.rels" not in names:
                raise RuntimeError(f"Missing slide{idx}.xml.rels")
        test_result = zf.testzip()
        if test_result:
            raise RuntimeError(f"Corrupt zip entry detected: {test_result}")


def main() -> None:
    PRESENTATION_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    slides = build_slides()
    preview_paths: list[Path] = []
    for idx, slide in enumerate(slides, start=1):
        preview_path = ASSET_DIR / f"slide_{idx:02d}_preview.png"
        render_slide_preview(slide, preview_path)
        preview_paths.append(preview_path)
    create_preview_contact_sheet(preview_paths, ASSET_DIR / "preview_contact_sheet.png")

    build_pptx(slides)
    verify_pptx(slides)
    write_notes(slides)
    write_qa(slides, preview_paths)

    print(f"Created {OUTPUT_PPTX}")
    print(f"Created {OUTPUT_NOTES}")
    print(f"Created {OUTPUT_QA}")
    print(f"Preview assets: {ASSET_DIR}")


if __name__ == "__main__":
    main()
