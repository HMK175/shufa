"""Non-default comparison of current style profiles against Phase 1 estimates.

This module is intentionally explicit and isolated: it creates a temporary
comparison-only profile from readonly font-outline estimates, runs current vs
candidate demos, and writes figures/reports. It never replaces the default
style_profiles.json or changes run_demo.py behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont

from run_demo import DEFAULT_BRUSH_PROFILES, DEFAULT_GRAPHICS, DEFAULT_OUTPUT, DEFAULT_PROFILES, run_task


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ESTIMATES = (
    EXP_DIR
    / "outputs"
    / "style_profile_phase1_estimates_20260618_152952"
    / "style_profile_phase1_estimates.json"
)
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
STYLE_ORDER = ["kaishu", "xingkai", "lishu"]
DEFAULT_SAMPLES = [
    {"char": "人", "styles": ["kaishu", "xingkai", "lishu"]},
    {"char": "中", "styles": ["kaishu", "xingkai", "lishu"]},
    {"char": "好", "styles": ["lishu"]},
    {"char": "风", "styles": ["lishu"]},
    {"char": "国", "styles": ["xingkai"]},
    {"char": "德", "styles": ["xingkai"]},
    {"char": "福", "styles": ["xingkai"]},
    {"char": "永", "styles": ["kaishu"]},
]
SUMMARY_FIELDS = [
    "char",
    "style",
    "variant",
    "profile_source",
    "horizontal_scale",
    "vertical_scale",
    "base_width",
    "aspect_ratio",
    "bbox_width",
    "bbox_height",
    "path_length",
    "connection_count",
    "connector_draw_length",
    "mean_width",
    "stroke_width_range",
    "visual_change_expected",
    "needs_user_review",
    "aspect_ratio_delta",
    "bbox_width_delta",
    "bbox_height_delta",
    "path_length_delta",
    "mean_width_delta",
    "note",
    "output_dir",
    "preview_png",
    "execution_render_png",
    "execution_debug_png",
    "summary_json",
]
MANIFEST_FIELDS = [
    "char",
    "style",
    "figure_path",
    "current_output_dir",
    "phase1_output_dir",
    "current_preview_png",
    "phase1_preview_png",
    "current_execution_render_png",
    "phase1_execution_render_png",
    "manual_check_focus",
    "priority",
]


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_csv(rows: Sequence[dict[str, Any]], path: Path, fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _hint_value(estimates: dict[str, Any], style: str, key: str, default: float) -> float:
    hint = estimates.get("styles", {}).get(style, {}).get(key, {})
    if isinstance(hint, dict):
        return _float(hint.get("value"), default)
    return default


def build_phase1_candidate_profile(
    *,
    current_profile_path: Path | str = DEFAULT_PROFILES,
    estimates_path: Path | str = DEFAULT_ESTIMATES,
    output_path: Path | str,
) -> dict[str, Any]:
    """Write a comparison-only candidate profile without touching defaults."""
    current = _load_json(current_profile_path)
    estimates = _load_json(estimates_path)
    candidate: dict[str, Any] = {
        "_status": "comparison_only_not_default",
        "_source_estimates": str(Path(estimates_path)),
        "_source_current_profile": str(Path(current_profile_path)),
        "_warning": "explicit comparison profile only; do not wire into default generation",
        "_notes": (
            "Only Phase 1 supported global scale hints are applied. Unsupported "
            "connector, pressure, speed, and pen-up parameters are preserved from current profile."
        ),
        "_phase1_base_width_hints": {},
    }
    for style, params in current.items():
        if not isinstance(params, dict) or str(style).startswith("_"):
            continue
        copied = dict(params)
        copied["horizontal_scale"] = _hint_value(estimates, style, "horizontal_scale_hint", _float(params.get("horizontal_scale"), 1.0))
        copied["vertical_scale"] = _hint_value(estimates, style, "vertical_scale_hint", _float(params.get("vertical_scale"), 1.0))
        candidate[style] = copied
        candidate["_phase1_base_width_hints"][style] = _hint_value(estimates, style, "base_width_hint", 0.0)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "candidate_profile_path": str(out_path),
        "styles": [style for style in candidate if not str(style).startswith("_")],
    }


def _task_text(char: str, style: str) -> str:
    # Keep the task parser deterministic by using the ASCII style alias and only
    # one Chinese character.
    return f"{style} {char}"


def _stroke_width_range(execution_csv: Path | str) -> float:
    widths: list[float] = []
    with Path(execution_csv).open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if str(row.get("pen_down", "")) in {"1", "1.0", "True", "true"}:
                widths.append(_float(row.get("width")))
    if not widths:
        return 0.0
    return round(max(widths) - min(widths), 6)


def _summary_row(
    *,
    char: str,
    style: str,
    variant: str,
    profile_source: str,
    result: dict[str, str],
    base_width_hint: float,
) -> dict[str, Any]:
    summary_path = Path(result["summary_json"])
    summary = _load_json(summary_path)
    style_params = summary.get("style_params", {}) if isinstance(summary.get("style_params"), dict) else {}
    brush_params = summary.get("brush_params", {}) if isinstance(summary.get("brush_params"), dict) else {}
    base_width = base_width_hint if variant == "phase1" and base_width_hint else _float(brush_params.get("base_width"))
    return {
        "char": char,
        "style": style,
        "variant": variant,
        "profile_source": profile_source,
        "horizontal_scale": style_params.get("horizontal_scale", ""),
        "vertical_scale": style_params.get("vertical_scale", ""),
        "base_width": round(base_width, 6),
        "aspect_ratio": summary.get("aspect_ratio", ""),
        "bbox_width": summary.get("bounding_box_width", ""),
        "bbox_height": summary.get("bounding_box_height", ""),
        "path_length": summary.get("path_length", ""),
        "connection_count": summary.get("connection_count", ""),
        "connector_draw_length": summary.get("connector_draw_length", ""),
        "mean_width": summary.get("mean_width", ""),
        "stroke_width_range": _stroke_width_range(summary.get("execution_trajectory_csv", "")),
        "visual_change_expected": "",
        "needs_user_review": True,
        "aspect_ratio_delta": "",
        "bbox_width_delta": "",
        "bbox_height_delta": "",
        "path_length_delta": "",
        "mean_width_delta": "",
        "note": "",
        "output_dir": result["output_dir"],
        "preview_png": result["preview_png"],
        "execution_render_png": result["execution_render_png"],
        "execution_debug_png": result["execution_debug_png"],
        "summary_json": result["summary_json"],
    }


def _change_level(row_current: dict[str, Any], row_phase1: dict[str, Any]) -> tuple[str, dict[str, float]]:
    deltas = {
        "aspect_ratio_delta": round(_float(row_phase1["aspect_ratio"]) - _float(row_current["aspect_ratio"]), 6),
        "bbox_width_delta": round(_float(row_phase1["bbox_width"]) - _float(row_current["bbox_width"]), 3),
        "bbox_height_delta": round(_float(row_phase1["bbox_height"]) - _float(row_current["bbox_height"]), 3),
        "path_length_delta": round(_float(row_phase1["path_length"]) - _float(row_current["path_length"]), 3),
        "mean_width_delta": round(_float(row_phase1["mean_width"]) - _float(row_current["mean_width"]), 6),
    }
    if abs(deltas["aspect_ratio_delta"]) >= 0.08 or abs(deltas["path_length_delta"]) >= 25:
        return "high", deltas
    if abs(deltas["aspect_ratio_delta"]) >= 0.025 or abs(deltas["path_length_delta"]) >= 8:
        return "medium", deltas
    return "low", deltas


def _annotate_pairwise(rows: list[dict[str, Any]]) -> None:
    pairs: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        pairs.setdefault((str(row["char"]), str(row["style"])), {})[str(row["variant"])] = row
    for (char, style), pair in pairs.items():
        if "current" not in pair or "phase1" not in pair:
            continue
        level, deltas = _change_level(pair["current"], pair["phase1"])
        if style == "xingkai":
            note = "Phase 1 only changes global scale; connector behavior is preserved from current profile."
        elif style == "lishu":
            note = "Check whether lishu still looks like a globally flattened kaishu; Phase 1 is only a scale test."
        else:
            note = "Kaishu is expected to remain almost unchanged."
        for variant in ["current", "phase1"]:
            pair[variant]["visual_change_expected"] = level
            pair[variant]["note"] = note
            pair[variant]["needs_user_review"] = True
            for key, value in deltas.items():
                pair[variant][key] = value


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


def _load_image(path: Path, size: tuple[int, int]) -> Image.Image:
    if not path.exists():
        return Image.new("RGB", size, "#f7f7f7")
    return Image.open(path).convert("RGB").resize(size, Image.Resampling.LANCZOS)


def _write_compare_figure(
    *,
    char: str,
    styles: Sequence[str],
    pairs: dict[tuple[str, str], dict[str, dict[str, Any]]],
    out_path: Path,
) -> None:
    cell_w, cell_h = 300, 300
    header_h = 44
    left_w = 76
    rows = len(styles)
    out = Image.new("RGB", (left_w + 2 * cell_w, header_h + rows * cell_h), "white")
    draw = ImageDraw.Draw(out)
    title_font = _font(22)
    label_font = _font(18)
    draw.text((left_w + 70, 10), f"{char} current profile", fill="#222222", font=label_font)
    draw.text((left_w + cell_w + 56, 10), "phase1 candidate", fill="#222222", font=label_font)
    for row_idx, style in enumerate(styles):
        y0 = header_h + row_idx * cell_h
        draw.text((8, y0 + cell_h // 2 - 12), style, fill="#222222", font=title_font)
        pair = pairs.get((char, style), {})
        for col_idx, variant in enumerate(["current", "phase1"]):
            item = pair.get(variant)
            image_path = Path(str(item.get("execution_render_png", ""))) if item else Path()
            image = _load_image(image_path, (cell_w, cell_h))
            out.paste(image, (left_w + col_idx * cell_w, y0))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)


def _figure_name(char: str, styles: Sequence[str]) -> str:
    char_id = f"u{ord(char):04x}"
    if len(styles) > 1:
        return f"compare_current_phase1_{char_id}_all_styles.png"
    return f"compare_current_phase1_{char_id}_{styles[0]}.png"


def _manual_focus(char: str, style: str) -> str:
    if style == "lishu":
        return "人工看图：隶书是否仍像压扁楷书，是否缺少笔画级隶书特征。"
    if style == "xingkai":
        return "人工看图：行楷味是否仍主要由 connector 决定，全局 scale 是否几乎无帮助。"
    return "人工看图：楷书是否基本不变，作为 Phase 1 对照。"


def _write_figures_and_manifest(rows: Sequence[dict[str, Any]], samples: Sequence[dict[str, Any]], figures_dir: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    pairs: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for row in rows:
        pairs.setdefault((str(row["char"]), str(row["style"])), {})[str(row["variant"])] = row
    figures: dict[str, str] = {}
    manifest: list[dict[str, Any]] = []
    for sample in samples:
        char = str(sample["char"])
        styles = [str(style) for style in sample.get("styles", []) if (char, str(style)) in pairs]
        if not styles:
            continue
        fig_path = figures_dir / _figure_name(char, styles)
        _write_compare_figure(char=char, styles=styles, pairs=pairs, out_path=fig_path)
        figures[fig_path.stem] = str(fig_path)
        for style in styles:
            pair = pairs[(char, style)]
            manifest.append(
                {
                    "char": char,
                    "style": style,
                    "figure_path": str(fig_path),
                    "current_output_dir": pair.get("current", {}).get("output_dir", ""),
                    "phase1_output_dir": pair.get("phase1", {}).get("output_dir", ""),
                    "current_preview_png": pair.get("current", {}).get("preview_png", ""),
                    "phase1_preview_png": pair.get("phase1", {}).get("preview_png", ""),
                    "current_execution_render_png": pair.get("current", {}).get("execution_render_png", ""),
                    "phase1_execution_render_png": pair.get("phase1", {}).get("execution_render_png", ""),
                    "manual_check_focus": _manual_focus(char, style),
                    "priority": "high" if style in {"lishu", "xingkai"} else "medium",
                }
            )
    return figures, manifest


def _style_delta_means(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for style in STYLE_ORDER:
        phase_rows = [row for row in rows if row.get("style") == style and row.get("variant") == "phase1"]
        if not phase_rows:
            continue
        out.append(
            {
                "style": style,
                "sample_count": len(phase_rows),
                "mean_abs_aspect_ratio_delta": round(sum(abs(_float(row.get("aspect_ratio_delta"))) for row in phase_rows) / len(phase_rows), 6),
                "mean_abs_path_length_delta": round(sum(abs(_float(row.get("path_length_delta"))) for row in phase_rows) / len(phase_rows), 3),
                "mean_abs_mean_width_delta": round(sum(abs(_float(row.get("mean_width_delta"))) for row in phase_rows) / len(phase_rows), 6),
            }
        )
    return out


def _write_report(
    *,
    path: Path,
    output_dir: Path,
    estimates_path: Path,
    current_profile_path: Path,
    candidate_profile_path: Path,
    rows: Sequence[dict[str, Any]],
    manifest: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
) -> None:
    success_pairs = len({(row["char"], row["style"]) for row in rows})
    style_delta_means = _style_delta_means(rows)
    lines = [
        "# Phase 1 readonly estimates 非默认对比图验证",
        "",
        "## 本轮目的",
        "",
        "本轮只验证 `style_profile_phase1_estimates.json` 的全局 scale hints 对可视效果和指标的影响。输出是 comparison-only，不接默认流程，不替换 `style_profiles.json`，不改变 `run_demo.py` 默认行为。",
        "",
        "## 输入与候选 profile",
        "",
        f"- estimates: `{estimates_path}`",
        f"- current profile: `{current_profile_path}`",
        f"- phase1 candidate profile: `{candidate_profile_path}`",
        "- candidate `_status`: `comparison_only_not_default`",
        "",
        "## 样本统计",
        "",
        f"- sample_pairs_success: `{success_pairs}`",
        f"- row_count_current_plus_phase1: `{len(rows)}`",
        f"- failure_count: `{len(failures)}`",
        "",
        "## current vs phase1 平均变化",
        "",
        "| style | samples | mean_abs_aspect_ratio_delta | mean_abs_path_length_delta | mean_abs_mean_width_delta |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in style_delta_means:
        lines.append(
            f"| {row['style']} | {row['sample_count']} | {row['mean_abs_aspect_ratio_delta']} | {row['mean_abs_path_length_delta']} | {row['mean_abs_mean_width_delta']} |"
        )
    lines.extend(
        [
            "",
            "## 初步结论",
            "",
            "- kaishu：Phase 1 scale 与当前 profile 基本一致，预期视觉变化很小。",
            "- lishu：全局宽扁 scale 只会带来小幅变化；如果图像仍像“压扁版楷书”，问题不在全局 scale，而在结构/笔画级特征。",
            "- xingkai：Phase 1 只改变全局 scale，保留当前 connector 规则，因此不能据此宣称行楷味已经改善。",
            "- Phase 1 的作用是确认全局比例是否值得接入；如果变化有限，Phase 2 应转向 component/stroke-level style modeling。",
            "",
            "## 人工看图优先级",
            "",
            "不要只看指标。优先查看以下图和单样本目录：",
            "",
            "| priority | char | style | figure | focus |",
            "|---|---|---|---|---|",
        ]
    )
    for item in manifest[:12]:
        lines.append(
            f"| {item['priority']} | {item['char']} | {item['style']} | `{item['figure_path']}` | {item['manual_check_focus']} |"
        )
    lines.extend(
        [
            "",
            "## 失败样本",
            "",
        ]
    )
    if failures:
        lines.extend(["| char | style | reason |", "|---|---|---|"])
        for failure in failures:
            lines.append(f"| {failure.get('char')} | {failure.get('style')} | {failure.get('reason')} |")
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 字体轮廓不等于真实书写轨迹。",
            "- 本轮不生成真实风格学习结果。",
            "- 本轮不接默认、不调用 API、不连接 CoppeliaSim/AUBO i5、不做 IK、不发送机器人命令。",
            "- Phase 1 未覆盖 connector_trigger、connector_shape、pressure_curve、speed_scale、pen_up_height 等过程参数。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_to_paper_figures(result: dict[str, Any], paper_dir: Path | str = DEFAULT_PAPER_DIR) -> str:
    paper_path = Path(paper_dir)
    paper_path.mkdir(parents=True, exist_ok=True)
    copies = [
        Path(result["report_md"]),
        Path(result["summary_csv"]),
        Path(result["candidate_profile"]),
    ]
    for src in copies:
        if src.exists():
            shutil.copy2(src, paper_path / src.name)
    figure_copies = []
    for _, fig in list(result.get("figures", {}).items())[:5]:
        src = Path(fig)
        if src.exists():
            dst = paper_path / src.name
            shutil.copy2(src, dst)
            figure_copies.append(dst.name)
    index_path = paper_path / "phase1_profile_comparison_index.md"
    lines = [
        "# Phase 1 Profile Comparison Index",
        "",
        f"- source_output_dir: `{result['output_dir']}`",
        "- scope: explicit comparison only; not default; style_profiles.json unchanged.",
        "",
        "| File | Content |",
        "|---|---|",
        "| `phase1_profile_comparison_report.md` | 非默认对比报告 |",
        "| `phase1_profile_comparison_summary.csv` | current vs phase1 指标 |",
        "| `style_profile_phase1_candidate.json` | comparison-only candidate profile |",
    ]
    for name in figure_copies:
        lines.append(f"| `{name}` | representative current vs phase1 figure |")
    lines.extend(
        [
            "",
            "人工看图重点：lishu 是否仍像压扁楷书；xingkai 是否仍主要由 connector 决定；不要只看指标。",
        ]
    )
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(index_path)


def run_phase1_profile_comparison(
    *,
    estimates_path: Path | str = DEFAULT_ESTIMATES,
    current_profile_path: Path | str = DEFAULT_PROFILES,
    output_dir: Path | str | None = None,
    samples: Sequence[dict[str, Any]] | None = None,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
    image_size: int = 256,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"phase1_profile_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = out_dir / "style_profile_phase1_candidate.json"
    candidate_result = build_phase1_candidate_profile(
        current_profile_path=current_profile_path,
        estimates_path=estimates_path,
        output_path=candidate_path,
    )
    candidate_payload = _load_json(candidate_path)
    base_width_hints = candidate_payload.get("_phase1_base_width_hints", {})
    run_root = out_dir / "runs"
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    sample_list = list(samples or DEFAULT_SAMPLES)

    for sample in sample_list:
        char = str(sample["char"])
        for style in [str(item) for item in sample.get("styles", [])]:
            try:
                current_result = run_task(
                    task_text=_task_text(char, style),
                    output_root=run_root / "current",
                    graphics_path=graphics_path,
                    style_profiles_path=current_profile_path,
                    image_size=image_size,
                    planner_mode="mock",
                    brush_profiles_path=brush_profiles_path,
                )
                phase1_result = run_task(
                    task_text=_task_text(char, style),
                    output_root=run_root / "phase1",
                    graphics_path=graphics_path,
                    style_profiles_path=candidate_path,
                    image_size=image_size,
                    planner_mode="mock",
                    brush_profiles_path=brush_profiles_path,
                )
                rows.append(
                    _summary_row(
                        char=char,
                        style=style,
                        variant="current",
                        profile_source="current_style_profiles",
                        result=current_result,
                        base_width_hint=_float(base_width_hints.get(style)),
                    )
                )
                rows.append(
                    _summary_row(
                        char=char,
                        style=style,
                        variant="phase1",
                        profile_source="phase1_candidate_comparison_only",
                        result=phase1_result,
                        base_width_hint=_float(base_width_hints.get(style)),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - experiment should record per-sample failures.
                failures.append({"char": char, "style": style, "reason": f"{type(exc).__name__}: {exc}"})

    _annotate_pairwise(rows)
    figures, manifest = _write_figures_and_manifest(rows, sample_list, out_dir / "figures")

    summary_csv = out_dir / "phase1_profile_comparison_summary.csv"
    manifest_csv = out_dir / "phase1_profile_comparison_manifest.csv"
    report_md = out_dir / "phase1_profile_comparison_report.md"
    failures_csv = out_dir / "phase1_profile_comparison_failures.csv"
    _write_csv(rows, summary_csv, SUMMARY_FIELDS)
    _write_csv(manifest, manifest_csv, MANIFEST_FIELDS)
    _write_csv(failures, failures_csv, ["char", "style", "reason"])
    _write_report(
        path=report_md,
        output_dir=out_dir,
        estimates_path=Path(estimates_path),
        current_profile_path=Path(current_profile_path),
        candidate_profile_path=candidate_path,
        rows=rows,
        manifest=manifest,
        failures=failures,
    )

    result: dict[str, Any] = {
        "output_dir": str(out_dir),
        "candidate_profile": candidate_result["candidate_profile_path"],
        "summary_csv": str(summary_csv),
        "manifest_csv": str(manifest_csv),
        "report_md": str(report_md),
        "failures_csv": str(failures_csv),
        "figures": figures,
        "success_pair_count": len({(row["char"], row["style"]) for row in rows}),
        "failure_count": len(failures),
        "style_delta_means": _style_delta_means(rows),
    }
    if copy_to_paper:
        result["paper_index"] = copy_to_paper_figures(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 1 readonly profile comparison without changing defaults.")
    parser.add_argument("--estimates", default=str(DEFAULT_ESTIMATES))
    parser.add_argument("--current-profile", default=str(DEFAULT_PROFILES))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS))
    parser.add_argument("--brush-profiles", default=str(DEFAULT_BRUSH_PROFILES))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--no-paper-copy", action="store_true")
    args = parser.parse_args()
    result = run_phase1_profile_comparison(
        estimates_path=args.estimates,
        current_profile_path=args.current_profile,
        output_dir=args.out_dir,
        graphics_path=args.graphics,
        brush_profiles_path=args.brush_profiles,
        image_size=args.image_size,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "figures"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
