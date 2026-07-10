"""Build an A-route showcase pack for paper-ready visual evidence.

This module only repackages existing A-route outputs into a larger visual
audit bundle. It does not change the underlying generation logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from run_demo import DEFAULT_BRUSH_PROFILES, DEFAULT_GRAPHICS, DEFAULT_OUTPUT, DEFAULT_PROFILES, run_batch


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = EXP_DIR / "configs" / "a_route_showcase_chars.json"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

STYLE_CN = {"kaishu": "楷书", "xingkai": "行楷", "lishu": "隶书"}
CONNECTION_LABELS_CN = ["抬笔过渡", "弱连续过渡", "连续带笔过渡"]
CONNECTION_VARIANTS = [
    ("none", "抬笔过渡", "写一个不要连笔的行楷{char}"),
    ("weak", "弱连续过渡", "写一个行楷风格的{char}"),
    ("normal", "连续带笔过渡", "写一个更连贯的行楷{char}"),
]
SHAPE_VARIANTS = [
    ("normal", "正常", "写一个隶书风格的{char}"),
    ("flatter", "宽扁", "写一个宽扁一点的隶书{char}"),
    ("wider", "更宽", "写一个更宽的隶书{char}"),
]
SMOOTHNESS_VARIANTS = [
    ("medium", "楷书基线", "写一个楷书风格的{char}"),
    ("high", "更圆滑", "写一个更圆滑的楷书{char}"),
    ("low", "更保守", "写一个更保守的行楷{char}"),
]

MANIFEST_FIELDS = [
    "sample_id",
    "category",
    "role",
    "char",
    "style",
    "variant",
    "label_cn",
    "source_path",
    "copied_path",
    "manual_check_focus",
]


@dataclass(frozen=True)
class ShowcaseSpec:
    task: str
    char: str
    style: str
    category: str
    variant: str
    label_cn: str
    role: str
    manual_check_focus: str


def _font(size: int) -> ImageFont.ImageFont:
    for font_path in [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/Deng.ttf"),
    ]:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _safe_char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else "sample"


def _existing_path(*candidates: Path | str | None) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return str(path)
    return ""


def load_showcase_config(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    data = _read_json(Path(path))
    data.setdefault("simple_chars", [])
    data.setdefault("medium_chars", [])
    data.setdefault("complex_chars", [])
    data.setdefault("styles", ["kaishu", "xingkai", "lishu"])
    data.setdefault("behavior_control_labels_cn", CONNECTION_LABELS_CN)
    data.setdefault("style_overview_chars", data["simple_chars"] + data["medium_chars"] + data["complex_chars"])
    data.setdefault("style_overview_grid_chars", data["style_overview_chars"][:8])
    data.setdefault("connection_control_chars", ["国", "德", "福", "和"])
    data.setdefault("behavior_control_chars", ["国", "德", "福"])
    data.setdefault("execution_display_chars", ["国", "德", "福", "和", "山", "中"])
    data.setdefault("shape_control_chars", ["中", "山"])
    data.setdefault("smoothness_supplementary_chars", ["永"])
    return data


def _style_task(char: str, style: str) -> str:
    return f"写一个{STYLE_CN.get(style, style)}风格的{char}"


def compose_showcase_task_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for char in config["style_overview_chars"]:
        for style in config["styles"]:
            role = "main_paper_candidate"
            if char in {"国", "福", "风", "德"}:
                role = "boundary_risk"
            specs.append(
                {
                    "task": _style_task(char, style),
                    "char": char,
                    "style": style,
                    "category": "style_overview",
                    "variant": style,
                    "label_cn": STYLE_CN.get(style, style),
                    "role": role,
                    "manual_check_focus": "看三风格是否能肉眼分开；这里只作为风格总览，不是 connector 证据。",
                }
            )

    for char in config["connection_control_chars"]:
        for variant, label_cn, template in CONNECTION_VARIANTS:
            specs.append(
                {
                    "task": template.format(char=char),
                    "char": char,
                    "style": "xingkai",
                    "category": "connection_control",
                    "variant": variant,
                    "label_cn": label_cn,
                    "role": "main_paper_candidate",
                    "manual_check_focus": "看跨笔过渡是否只是 execution 行为控制，不要写成真行楷风格迁移。",
                }
            )

    for char in config["shape_control_chars"]:
        for variant, label_cn, template in SHAPE_VARIANTS:
            specs.append(
                {
                    "task": template.format(char=char),
                    "char": char,
                    "style": "lishu",
                    "category": "shape_control",
                    "variant": variant,
                    "label_cn": label_cn,
                    "role": "supplementary_candidate",
                    "manual_check_focus": "看宽扁是否主要体现在外形，不是 connector 变化。",
                }
            )

    for char in config["smoothness_supplementary_chars"]:
        for variant, label_cn, template in SMOOTHNESS_VARIANTS:
            specs.append(
                {
                    "task": template.format(char=char),
                    "char": char,
                    "style": "kaishu" if variant != "low" else "xingkai",
                    "category": "smoothness_control",
                    "variant": variant,
                    "label_cn": label_cn,
                    "role": "supplementary_candidate",
                    "manual_check_focus": "smoothness 只作辅助，不作为主结果。",
                }
            )

    return specs


def _load_records_from_batch(batch_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for summary_path in sorted(batch_dir.rglob("summary.json")):
        if summary_path.parent == batch_dir:
            continue
        plan_path = summary_path.parent / "plan.json"
        if not plan_path.exists():
            continue
        summary = _read_json(summary_path)
        plan = _read_json(plan_path)
        char = str(summary.get("char", plan.get("char", "")))
        char_id = _safe_char_id(char)
        records.append(
            {
                "task": str(summary.get("task", plan.get("task", ""))),
                "char": char,
                "style": str(summary.get("style", plan.get("style", ""))),
                "style_modifiers": summary.get("style_modifiers", plan.get("style_modifiers", {})),
                "output_dir": str(summary_path.parent),
                "summary_path": str(summary_path),
                "plan_path": str(plan_path),
                "compare_png": _existing_path(batch_dir / f"compare_{char_id}.png", summary_path.parent / "compare.png", summary.get("compare_png"), summary.get("preview_png"), summary.get("execution_render_png")),
                "modifier_png": _existing_path(batch_dir / f"modifier_ablation_{char_id}.png", summary_path.parent / "modifier_ablation.png", summary.get("modifier_ablation_png"), summary.get("preview_png"), summary.get("execution_render_png")),
                "shape_png": _existing_path(batch_dir / f"modifier_ablation_shape_{char_id}.png", summary_path.parent / "modifier_ablation_shape.png", summary.get("modifier_shape_png"), summary.get("modifier_ablation_shape_png"), summary.get("modifier_ablation.png"), summary.get("preview_png")),
                "smoothness_png": _existing_path(batch_dir / f"modifier_ablation_smoothness_{char_id}.png", summary_path.parent / "modifier_ablation_smoothness.png", summary.get("modifier_smoothness_png"), summary.get("modifier_ablation_smoothness_png"), summary.get("modifier_ablation.png"), summary.get("preview_png")),
                "execution_render_png": _existing_path(summary_path.parent / "execution_render.png", summary.get("execution_render_png"), summary.get("preview_png")),
                "execution_debug_png": _existing_path(summary_path.parent / "execution_debug.png", summary.get("execution_debug_png"), summary.get("execution_render_png"), summary.get("preview_png")),
                "preview_png": _existing_path(summary_path.parent / "preview.png", summary.get("preview_png"), summary.get("execution_render_png")),
                "execution_ablation_png": _existing_path(batch_dir / f"execution_ablation_{char_id}.png", summary_path.parent / f"execution_ablation_{char_id}.png", summary.get("execution_ablation_png"), summary.get("execution_debug_png"), summary.get("execution_render_png")),
            }
        )
    return records


def _match_records_by_task(records: list[dict[str, Any]], specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task = {record["task"]: record for record in records}
    matched: list[dict[str, Any]] = []
    for spec in specs:
        record = by_task.get(spec["task"])
        if record:
            merged = dict(spec)
            merged.update(record)
            matched.append(merged)
    return matched


def _compose_card_grid(
    cards: list[dict[str, Any]],
    out_path: Path,
    *,
    title: str,
    columns: int,
    card_size: tuple[int, int] = (280, 280),
    title_height: int = 56,
    label_height: int = 40,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not cards:
        out_path.touch()
        return

    font_title = _font(28)
    font_label = _font(20)
    font_small = _font(16)
    images: list[tuple[dict[str, Any], Image.Image]] = []
    for card in cards:
        image_path = Path(str(card["image_path"]))
        if not image_path.exists():
            continue
        img = Image.open(image_path).convert("RGB")
        if img.size != card_size:
            img = img.resize(card_size, Image.Resampling.LANCZOS)
        images.append((card, img))
    if not images:
        out_path.touch()
        return

    rows = (len(images) + columns - 1) // columns
    width = columns * card_size[0]
    height = title_height + rows * (card_size[1] + label_height)
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    title_bbox = draw.textbbox((0, 0), title, font=font_title)
    draw.text(((width - (title_bbox[2] - title_bbox[0])) / 2, 10), title, fill="#111111", font=font_title)

    for idx, (card, img) in enumerate(images):
        row = idx // columns
        col = idx % columns
        x0 = col * card_size[0]
        y0 = title_height + row * (card_size[1] + label_height)
        label = str(card.get("label", card.get("char", "")))
        bbox = draw.textbbox((0, 0), label, font=font_label)
        draw.text((x0 + (card_size[0] - (bbox[2] - bbox[0])) / 2, y0 + 4), label, fill="#222222", font=font_label)
        canvas.paste(img, (x0, y0 + label_height))
        subtitle = str(card.get("subtitle", ""))
        if subtitle:
            draw.text((x0 + 6, y0 + label_height + card_size[1] - 20), subtitle, fill="#555555", font=font_small)

    canvas.save(out_path)


def _compose_matrix(
    matrix: list[list[dict[str, Any]]],
    out_path: Path,
    *,
    title: str,
    row_labels: list[str],
    col_labels: list[str],
    cell_size: tuple[int, int] = (250, 250),
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not matrix:
        out_path.touch()
        return

    font_title = _font(28)
    font_head = _font(20)
    left_w = 84
    top_h = 54
    width = left_w + len(col_labels) * cell_size[0]
    height = top_h + len(row_labels) * cell_size[1]
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    title_bbox = draw.textbbox((0, 0), title, font=font_title)
    draw.text(((width - (title_bbox[2] - title_bbox[0])) / 2, 8), title, fill="#111111", font=font_title)

    for col, label in enumerate(col_labels):
        bbox = draw.textbbox((0, 0), label, font=font_head)
        x = left_w + col * cell_size[0] + (cell_size[0] - (bbox[2] - bbox[0])) / 2
        draw.text((x, 26), label, fill="#222222", font=font_head)
    for row, label in enumerate(row_labels):
        bbox = draw.textbbox((0, 0), label, font=font_head)
        y = top_h + row * cell_size[1] + (cell_size[1] - (bbox[3] - bbox[1])) / 2 - 6
        draw.text((12, y), label, fill="#222222", font=font_head)

    for r, row in enumerate(matrix):
        for c, cell in enumerate(row):
            image_path = Path(str(cell["image_path"]))
            if not image_path.exists():
                continue
            img = Image.open(image_path).convert("RGB")
            if img.size != cell_size:
                img = img.resize(cell_size, Image.Resampling.LANCZOS)
            canvas.paste(img, (left_w + c * cell_size[0], top_h + r * cell_size[1]))

    canvas.save(out_path)


def _build_style_overview(records: list[dict[str, Any]], config: dict[str, Any], out_path: Path) -> None:
    lookup = {record["task"]: record for record in records}
    cards = []
    for char in config["style_overview_grid_chars"]:
        record = lookup.get(_style_task(char, "kaishu"))
        if record and record.get("compare_png"):
            cards.append({"label": char, "image_path": record["compare_png"], "subtitle": "楷/行楷/隶"})
    _compose_card_grid(cards, out_path, title="A-route 风格总览图（楷书 / 行楷 / 隶书）", columns=3, card_size=(320, 320))


def _build_modifier_overview(records: list[dict[str, Any]], config: dict[str, Any], out_path: Path) -> None:
    lookup = {record["task"]: record for record in records}
    cards = []
    for char in config["connection_control_chars"]:
        record = lookup.get(f"写一个行楷风格的{char}")
        if record and record.get("modifier_png"):
            cards.append({"label": f"跨笔过渡：{char}", "image_path": record["modifier_png"], "subtitle": "抬笔 / 弱连续 / 连续带笔"})
    for char in config["shape_control_chars"]:
        record = lookup.get(f"写一个隶书风格的{char}")
        if record and record.get("shape_png"):
            cards.append({"label": f"宽扁形态：{char}", "image_path": record["shape_png"], "subtitle": "正常 / 宽扁 / 更宽"})
    for char in config["smoothness_supplementary_chars"]:
        record = lookup.get(f"写一个楷书风格的{char}")
        if record and record.get("smoothness_png"):
            cards.append({"label": f"圆滑辅助：{char}", "image_path": record["smoothness_png"], "subtitle": "辅助结果"})
    _compose_card_grid(cards, out_path, title="A-route modifier 总览图（跨笔过渡 / 宽扁 / 圆滑辅助）", columns=4, card_size=(320, 320))


def _build_execution_display(records: list[dict[str, Any]], config: dict[str, Any], out_path: Path) -> None:
    lookup = {record["task"]: record for record in records}
    cards = []
    for char in list(config["execution_display_chars"])[:6]:
        record = lookup.get(f"写一个行楷风格的{char}") or lookup.get(f"写一个楷书风格的{char}") or lookup.get(f"写一个隶书风格的{char}")
        if not record:
            continue
        image_path = record.get("execution_ablation_png") or record.get("execution_debug_png") or record.get("execution_render_png")
        if image_path:
            cards.append({"label": char, "image_path": image_path, "subtitle": "width / pressure / connector"})
    _compose_card_grid(cards, out_path, title="A-route execution layer display（width / pressure / connector）", columns=3, card_size=(320, 220))


def _build_behavior_compare(records: list[dict[str, Any]], config: dict[str, Any], out_path: Path) -> None:
    lookup = {record["task"]: record for record in records}
    row_chars = list(config["behavior_control_chars"])[:3]
    col_labels = list(config["behavior_control_labels_cn"])[:3]
    matrix: list[list[dict[str, Any]]] = []
    for char in row_chars:
        row: list[dict[str, Any]] = []
        for _, label_cn, template in CONNECTION_VARIANTS:
            record = lookup.get(template.format(char=char))
            if not record:
                continue
            image_path = record.get("execution_debug_png") or record.get("execution_render_png") or record.get("preview_png")
            if image_path:
                row.append({"image_path": image_path, "label": label_cn})
        matrix.append(row)
    _compose_matrix(matrix, out_path, title="跨笔过渡行为对比：抬笔过渡 / 弱连续过渡 / 连续带笔过渡", row_labels=row_chars, col_labels=col_labels)


def _build_smoothness_panel(records: list[dict[str, Any]], config: dict[str, Any], out_path: Path) -> None:
    lookup = {record["task"]: record for record in records}
    cards = []
    for char in config["smoothness_supplementary_chars"]:
        for variant, label_cn, template in SMOOTHNESS_VARIANTS:
            record = lookup.get(template.format(char=char))
            if not record:
                continue
            image_path = record.get("smoothness_png") or record.get("modifier_png") or record.get("execution_debug_png")
            if image_path:
                cards.append({"label": f"{char} / {label_cn}", "image_path": image_path, "subtitle": "smoothness 补充"})
    _compose_card_grid(cards, out_path, title="A-route smoothness supplementary（补充）", columns=3, card_size=(280, 280))


def _build_manifest_rows(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in selected:
        rows.append(
            {
                "sample_id": item["sample_id"],
                "category": item["category"],
                "role": item["role"],
                "char": item.get("char", ""),
                "style": item.get("style", ""),
                "variant": item.get("variant", ""),
                "label_cn": item.get("label_cn", ""),
                "source_path": item.get("source_path", ""),
                "copied_path": item.get("copied_path", ""),
                "manual_check_focus": item.get("manual_check_focus", ""),
            }
        )
    return rows


def _copy_selected(items: list[dict[str, Any]], selected_dir: Path) -> list[dict[str, Any]]:
    selected_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        source = Path(str(item["image_path"]))
        if not source.exists():
            continue
        dest = selected_dir / f"{idx:02d}_{item['sample_id']}{source.suffix or '.png'}"
        shutil.copy2(source, dest)
        row = dict(item)
        row["source_path"] = str(source)
        row["copied_path"] = str(dest)
        copied.append(row)
    return copied


def _write_report(path: Path, *, records: list[dict[str, Any]], selected_rows: list[dict[str, Any]], output_dir: Path, batch_dir: Path) -> None:
    main_count = sum(1 for row in selected_rows if row["role"] == "main_paper_candidate")
    supp_count = sum(1 for row in selected_rows if row["role"] == "supplementary_candidate")
    risk_count = sum(1 for row in selected_rows if row["role"] == "boundary_risk")
    styles = sorted({row["style"] for row in records if row.get("style")})
    lines = [
        "# A-route showcase pack",
        "",
        "## 目的",
        "",
        "本展示包只重排已有 A-route 结果，不改算法、不调参数、不接 API / CoppeliaSim / AUBO。",
        "其中 `connector` 在本论文叙事里只表示**跨笔过渡控制 / execution 行为控制**，不是“真行楷风格迁移成功”的证据。",
        "",
        "## 批次信息",
        "",
        f"- source batch: `{batch_dir}`",
        f"- output dir: `{output_dir}`",
        f"- total source samples: `{len(records)}`",
        f"- styles covered: `{', '.join(styles)}`",
        "",
        "## 正文候选图",
        "",
        "- `a_route_style_overview_grid.png`: 楷书 / 行楷 / 隶书三风格总览。",
        "- `a_route_modifier_control_overview.png`: connection / shape / smoothness 的统一展示。",
        "- `a_route_execution_display_grid.png`: width / pressure / connector / pen-up 的 execution 层展示。",
        "- `a_route_behavior_control_compare.png`: 抬笔过渡 / 弱连续过渡 / 连续带笔过渡对比。",
        "",
        "## 人工审图清单",
        "",
        "| role | count | focus |",
        "|---|---:|---|",
        f"| main_paper_candidate | {main_count} | 看跨笔过渡控制、execution 表达力和风格总览 |",
        f"| supplementary_candidate | {supp_count} | 看宽扁和圆滑是否只是辅助变化 |",
        f"| boundary_risk | {risk_count} | 看哪些样本差异仍弱，不要过度声称风格迁移 |",
        "",
        "## 结论提醒",
        "",
        "- 连笔在本论文里只证明**跨笔过渡控制 / execution 行为控制**。",
        "- 它不证明真实行楷风格学习成功。",
        "- 正文应优先使用 execution 层与 modifier 总览图，风格强弱对比只作辅助证据。",
        "",
        "## 建议阅读顺序",
        "",
        "1. 先看 style overview。",
        "2. 再看 behavior compare。",
        "3. 再看 execution display。",
        "4. 最后看 shape / smoothness supplementary。",
        "",
        "## 边界",
        "",
        "- 本页不是新算法。",
        "- 不生成新 trajectory。",
        "- 不接默认 pipeline。",
        "- 不修改 shared data 或 legacy 代码。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checklist(path: Path, selected_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# A-route visual audit checklist",
        "",
        "请按下面清单先看主图，再看补充图，最后看边界样本。",
        "",
        "| role | label | file | focus |",
        "|---|---|---|---|",
    ]
    for row in selected_rows:
        lines.append(
            "| {role} | {label} | `{file}` | {focus} |".format(
                role=row["role"],
                label=row["label_cn"] or row["char"] or row["sample_id"],
                file=row["copied_path"],
                focus=row["manual_check_focus"],
            )
        )
    lines.append("")
    lines.append("重点是看图上是否真的出现了可解释的跨笔过渡控制、宽扁变化和 execution 层差异。")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_a_route_showcase_pack(
    *,
    output_root: Path | str = DEFAULT_OUTPUT,
    config_path: Path | str = DEFAULT_CONFIG,
    source_batch_dir: Path | str | None = None,
    run_generation: bool = True,
    paper_figures_dir: Path | str = DEFAULT_PAPER_DIR,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
    image_size: int = 256,
) -> dict[str, Any]:
    config = load_showcase_config(config_path)
    specs = compose_showcase_task_specs(config)
    output_root = Path(output_root)
    pack_dir = output_root / f"a_route_showcase_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    pack_dir.mkdir(parents=True, exist_ok=True)
    selected_dir = pack_dir / "selected_images"

    if run_generation:
        generated_root = pack_dir / "generated"
        run_result = run_batch(
            tasks=[spec["task"] for spec in specs],
            output_root=generated_root,
            graphics_path=graphics_path,
            style_profiles_path=style_profiles_path,
            image_size=image_size,
            planner_mode="mock",
            brush_profiles_path=brush_profiles_path,
        )
        batch_dir = Path(run_result["batch_dir"])
        records = _match_records_by_task(_load_records_from_batch(batch_dir), specs)
    else:
        if source_batch_dir is None:
            raise ValueError("source_batch_dir is required when run_generation=False")
        batch_dir = Path(source_batch_dir)
        records = _match_records_by_task(_load_records_from_batch(batch_dir), specs)

    if not records:
        raise ValueError(f"no matching records found in {batch_dir}")

    lookup = {record["task"]: record for record in records}

    style_overview_path = pack_dir / "a_route_style_overview_grid.png"
    modifier_overview_path = pack_dir / "a_route_modifier_control_overview.png"
    execution_display_path = pack_dir / "a_route_execution_display_grid.png"
    behavior_compare_path = pack_dir / "a_route_behavior_control_compare.png"
    smoothness_path = pack_dir / "a_route_smoothness_supplementary.png"

    _build_style_overview(records, config, style_overview_path)
    _build_modifier_overview(records, config, modifier_overview_path)
    _build_execution_display(records, config, execution_display_path)
    _build_behavior_compare(records, config, behavior_compare_path)
    _build_smoothness_panel(records, config, smoothness_path)

    # Selected booklet: 4 composite figures + representative single-character evidence.
    selected_items = [
        {
            "sample_id": "style_overview_grid",
            "category": "style_overview",
            "role": "main_paper_candidate",
            "char": "",
            "style": "",
            "variant": "",
            "label_cn": "风格总览图",
            "image_path": style_overview_path,
            "manual_check_focus": "先看楷书 / 行楷 / 隶书整体差异。",
        },
        {
            "sample_id": "modifier_control_overview",
            "category": "modifier_control",
            "role": "main_paper_candidate",
            "char": "",
            "style": "",
            "variant": "",
            "label_cn": "modifier 总览图",
            "image_path": modifier_overview_path,
            "manual_check_focus": "看跨笔过渡、宽扁与圆滑的统一展示。",
        },
        {
            "sample_id": "execution_display_grid",
            "category": "execution_display",
            "role": "main_paper_candidate",
            "char": "",
            "style": "",
            "variant": "",
            "label_cn": "execution 表达图",
            "image_path": execution_display_path,
            "manual_check_focus": "看 width / pressure / connector / pen-up 是否更直观。",
        },
        {
            "sample_id": "behavior_control_compare",
            "category": "behavior_control",
            "role": "main_paper_candidate",
            "char": "",
            "style": "",
            "variant": "",
            "label_cn": "行为控制对比图",
            "image_path": behavior_compare_path,
            "manual_check_focus": "看抬笔过渡 / 弱连续过渡 / 连续带笔过渡。",
        },
        {
            "sample_id": "smoothness_supplementary",
            "category": "smoothness_control",
            "role": "supplementary_candidate",
            "char": "",
            "style": "",
            "variant": "",
            "label_cn": "圆滑补充图",
            "image_path": smoothness_path,
            "manual_check_focus": "smoothness 只是补充，不是主结果。",
        },
    ]

    for char in ["人", "山", "中", "永", "明", "和", "林", "国", "福"]:
        record = lookup.get(_style_task(char, "kaishu"))
        if not record or not record.get("compare_png"):
            continue
        role = "boundary_risk" if char in {"国", "福"} else "main_paper_candidate"
        selected_items.append(
            {
                "sample_id": f"{_safe_char_id(char)}_style_compare",
                "category": "style_overview",
                "role": role,
                "char": char,
                "style": "kaishu",
                "variant": "style_compare",
                "label_cn": char,
                "image_path": record["compare_png"],
                "manual_check_focus": "只看三风格是否肉眼可分，不要把它当 connector 证据。",
            }
        )

    for char in ["国", "和"]:
        record = lookup.get(f"写一个行楷风格的{char}")
        if not record:
            continue
        image_path = record.get("modifier_png") or record.get("execution_debug_png") or record.get("preview_png")
        if image_path:
            selected_items.append(
                {
                    "sample_id": f"{_safe_char_id(char)}_connection",
                    "category": "connection_control",
                    "role": "main_paper_candidate",
                    "char": char,
                    "style": "xingkai",
                    "variant": "weak",
                    "label_cn": f"跨笔：{char}",
                    "image_path": image_path,
                    "manual_check_focus": "看跨笔过渡控制，不要写成风格迁移成功。",
                }
            )

    record = lookup.get("写一个隶书风格的中")
    if record:
        image_path = record.get("shape_png") or record.get("modifier_png") or record.get("preview_png")
        if image_path:
            selected_items.append(
                {
                    "sample_id": "u4e2d_shape",
                    "category": "shape_control",
                    "role": "supplementary_candidate",
                    "char": "中",
                    "style": "lishu",
                    "variant": "normal",
                    "label_cn": "宽扁：中",
                    "image_path": image_path,
                    "manual_check_focus": "看宽扁变化是否主要来自外形。",
                }
            )

    record = lookup.get("写一个更圆滑的楷书永") or lookup.get("写一个楷书风格的永")
    if record:
        image_path = record.get("smoothness_png") or record.get("modifier_png") or record.get("preview_png")
        if image_path:
            selected_items.append(
                {
                    "sample_id": "u6c38_smoothness",
                    "category": "smoothness_control",
                    "role": "supplementary_candidate",
                    "char": "永",
                    "style": "kaishu",
                    "variant": "high",
                    "label_cn": "圆滑：永",
                    "image_path": image_path,
                    "manual_check_focus": "smoothness 只做辅助，不作为主结论。",
                }
            )

    selected_rows = _copy_selected(selected_items, selected_dir)
    manifest_rows = _build_manifest_rows(selected_rows)
    _write_csv(pack_dir / "a_route_showcase_manifest.csv", manifest_rows, MANIFEST_FIELDS)
    _write_checklist(pack_dir / "a_route_visual_audit_checklist.md", selected_rows)
    report_path = pack_dir / "a_route_showcase_report.md"
    _write_report(report_path, records=records, selected_rows=selected_rows, output_dir=pack_dir, batch_dir=batch_dir)

    paper_figures_dir = Path(paper_figures_dir)
    paper_figures_dir.mkdir(parents=True, exist_ok=True)
    paper_index = paper_figures_dir / "a_route_showcase_index.md"
    paper_index.write_text(
        "\n".join(
            [
                "# A-route showcase index",
                "",
                f"- output_dir: `{pack_dir}`",
                f"- source_batch_dir: `{batch_dir}`",
                "",
                "| file | role |",
                "|---|---|",
                "| `a_route_style_overview_grid.png` | main paper candidate |",
                "| `a_route_modifier_control_overview.png` | main paper candidate |",
                "| `a_route_execution_display_grid.png` | main paper candidate |",
                "| `a_route_behavior_control_compare.png` | main paper candidate |",
                "| `a_route_smoothness_supplementary.png` | supplementary candidate |",
                "| `a_route_showcase_report.md` | report |",
                "| `a_route_showcase_manifest.csv` | manifest |",
                "| `a_route_visual_audit_checklist.md` | checklist |",
                "",
                "连笔在这里仅表示跨笔过渡控制 / execution 行为控制，不代表真实行楷风格迁移完成。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (pack_dir / "paper_index.md").write_text(paper_index.read_text(encoding="utf-8"), encoding="utf-8")

    summary = {
        "output_dir": str(pack_dir),
        "source_batch_dir": str(batch_dir),
        "selected_count": len(selected_rows),
        "manifest_csv": str(pack_dir / "a_route_showcase_manifest.csv"),
        "report_md": str(report_path),
        "checklist_md": str(pack_dir / "a_route_visual_audit_checklist.md"),
        "paper_index": str(paper_index),
        "figures": {
            "style_overview": str(style_overview_path),
            "modifier_overview": str(modifier_overview_path),
            "execution_display": str(execution_display_path),
            "behavior_compare": str(behavior_compare_path),
            "smoothness_supplementary": str(smoothness_path),
        },
    }
    _write_json(pack_dir / "a_route_showcase_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the A-route showcase pack.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--paper-figures-dir", default=str(DEFAULT_PAPER_DIR))
    parser.add_argument("--source-batch-dir", default=None)
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS))
    parser.add_argument("--style-profiles", default=str(DEFAULT_PROFILES))
    parser.add_argument("--brush-profiles", default=str(DEFAULT_BRUSH_PROFILES))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--no-generate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = build_a_route_showcase_pack(
        output_root=args.out_dir,
        config_path=args.config,
        source_batch_dir=args.source_batch_dir,
        run_generation=not args.no_generate and args.source_batch_dir is None,
        paper_figures_dir=args.paper_figures_dir,
        graphics_path=args.graphics,
        style_profiles_path=args.style_profiles,
        brush_profiles_path=args.brush_profiles,
        image_size=args.image_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
