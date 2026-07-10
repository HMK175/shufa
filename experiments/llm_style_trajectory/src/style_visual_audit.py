from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - optional plotting dependency fallback
    plt = None
    Image = None
    ImageDraw = None
    ImageFont = None


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIAGNOSTIC_DIR = (
    ROOT
    / "experiments"
    / "llm_style_trajectory"
    / "outputs"
    / "style_diagnostics_20260617_200746"
)
DEFAULT_PAPER_DIR = ROOT / "experiments" / "llm_style_trajectory" / "outputs" / "paper_figures"

STYLE_DISPLAY = {
    "kaishu": "楷书",
    "xingkai": "行楷",
    "lishu": "隶书",
}

CSV_FIELDS = [
    "char",
    "style",
    "case_type",
    "reason",
    "priority",
    "image_path",
    "summary_row_ref",
    "output_dir",
    "aspect_ratio",
    "path_length",
    "connection_count",
    "connector_draw_length",
    "mean_width",
    "workspace_path_length_mm",
    "manual_check_focus",
]

MANIFEST_FIELDS = [
    "char",
    "style",
    "case_type",
    "priority",
    "image_path",
    "copied_image_path",
    "output_dir",
    "fallback_ref",
    "manual_check_focus",
]


@dataclass(frozen=True)
class Candidate:
    char: str
    style: str
    case_type: str
    reason: str
    priority: int
    row: dict[str, str]
    manual_check_focus: str


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _to_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _read_summary(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if _to_bool(row.get("success", "True"))]


def _group_by_char(rows: Iterable[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("char", "")].append(row)
    return dict(grouped)


def _style_row(rows: list[dict[str, str]], style: str) -> dict[str, str] | None:
    return next((row for row in rows if row.get("style") == style), None)


def _add_candidate(
    candidates: dict[tuple[str, str, str], Candidate],
    row: dict[str, str],
    case_type: str,
    reason: str,
    priority: int,
    focus: str,
) -> None:
    key = (row.get("char", ""), row.get("style", ""), case_type)
    if not key[0] or not key[1]:
        return
    existing = candidates.get(key)
    if existing is None or priority < existing.priority:
        candidates[key] = Candidate(
            char=key[0],
            style=key[1],
            case_type=case_type,
            reason=reason,
            priority=priority,
            row=row,
            manual_check_focus=focus,
        )


def select_candidates(rows: list[dict[str, str]], target_count: int = 18) -> list[Candidate]:
    candidates: dict[tuple[str, str, str], Candidate] = {}
    by_char = _group_by_char(rows)

    aspect_spreads: list[tuple[float, str, list[dict[str, str]]]] = []
    connector_diffs: list[tuple[float, str, dict[str, str]]] = []
    for char, char_rows in by_char.items():
        aspects = [_to_float(row.get("aspect_ratio")) for row in char_rows]
        if aspects:
            aspect_spreads.append((max(aspects) - min(aspects), char, char_rows))
        xingkai = _style_row(char_rows, "xingkai")
        if xingkai is not None:
            other_connector = [
                _to_float(row.get("connector_draw_length"))
                for row in char_rows
                if row.get("style") != "xingkai"
            ]
            baseline = sum(other_connector) / len(other_connector) if other_connector else 0.0
            connector_diffs.append(
                (_to_float(xingkai.get("connector_draw_length")) - baseline, char, xingkai)
            )

    for spread, char, char_rows in sorted(aspect_spreads, reverse=True)[:3]:
        for row in char_rows:
            _add_candidate(
                candidates,
                row,
                "high_aspect_spread",
                f"{char} 的三风格 aspect_ratio 差异较强，spread={spread:.3f}",
                1,
                "看三风格是否肉眼可分；重点判断 lishu 是否只是横向拉宽，还是有真实隶书笔画特征。",
            )

    for spread, char, char_rows in sorted(aspect_spreads, key=lambda item: item[0])[:3]:
        for row in char_rows:
            _add_candidate(
                candidates,
                row,
                "low_aspect_spread",
                f"{char} 的三风格 aspect_ratio 差异较弱，spread={spread:.3f}",
                2,
                "看三风格是否肉眼难分；若难分，后续可能需要重新估计部件比例和笔画风格参数。",
            )

    for diff, char, row in sorted(connector_diffs, reverse=True)[:4]:
        _add_candidate(
            candidates,
            row,
            "strong_xingkai_connector",
            f"{char} 的行楷 connector_draw_length 相对其他风格差异较强，diff={diff:.3f}",
            2,
            "看行楷连接是否自然，是否形成合理连贯感，而不是跨笔硬连。",
        )

    for diff, char, row in sorted(connector_diffs, key=lambda item: item[0])[:4]:
        _add_candidate(
            candidates,
            row,
            "weak_xingkai_connector",
            f"{char} 的行楷 connector 指标不明显，diff={diff:.3f}",
            3,
            "看行楷是否仍能与楷书区分；若连接弱且形态接近，后续需调 connector 或平滑策略。",
        )

    numeric_fields = [
        ("path_length", "path_length_outlier", "看路径是否异常绕行或过长，是否出现机械化中线轨迹。"),
        (
            "workspace_path_length_mm",
            "workspace_path_length_outlier",
            "看 workspace 映射后路径是否异常拉长，布局是否挤压或比例失真。",
        ),
        ("mean_width", "mean_width_outlier", "看笔画宽度是否明显偏粗/偏细，是否需要笔画级宽度估计。"),
    ]
    for field, case_type, focus in numeric_fields:
        values = [_to_float(row.get(field)) for row in rows]
        if not values:
            continue
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        std = math.sqrt(variance)
        if std <= 1e-9:
            continue
        scored = sorted(
            ((abs(_to_float(row.get(field)) - mean) / std, row) for row in rows),
            reverse=True,
            key=lambda item: item[0],
        )
        for zscore, row in scored[:2]:
            if zscore < 1.5:
                continue
            _add_candidate(
                candidates,
                row,
                case_type,
                f"{field} 离群，z={zscore:.2f}",
                4,
                focus,
            )

    for row in sorted(rows, key=lambda item: _to_float(item.get("connector_draw_length")), reverse=True)[:3]:
        if row.get("style") == "xingkai" and _to_float(row.get("connector_draw_length")) > 0:
            _add_candidate(
                candidates,
                row,
                "long_xingkai_connector",
                f"行楷 connector_draw_length 较长：{_to_float(row.get('connector_draw_length')):.3f}",
                1,
                "优先看连接段是否过长、过直或穿越部件；判断是否需要限制 connector 规则。",
            )

    for row in sorted(
        [row for row in rows if row.get("style") == "lishu"],
        key=lambda item: _to_float(item.get("aspect_ratio")),
        reverse=True,
    )[:3]:
        _add_candidate(
            candidates,
            row,
            "high_lishu_aspect",
            f"隶书 aspect_ratio 较高：{_to_float(row.get('aspect_ratio')):.3f}",
            2,
            "看 lishu 是否宽扁过度；是否只是全局横向拉伸而缺少隶书笔意。",
        )

    style_means: dict[str, dict[str, float]] = {}
    for style in sorted({row.get("style", "") for row in rows}):
        style_rows = [row for row in rows if row.get("style") == style]
        style_means[style] = {
            "aspect_ratio": sum(_to_float(row.get("aspect_ratio")) for row in style_rows)
            / max(1, len(style_rows)),
            "connector_draw_length": sum(
                _to_float(row.get("connector_draw_length")) for row in style_rows
            )
            / max(1, len(style_rows)),
            "path_length": sum(_to_float(row.get("path_length")) for row in style_rows)
            / max(1, len(style_rows)),
        }
    for style, means in style_means.items():
        style_rows = [row for row in rows if row.get("style") == style]
        ranked = sorted(
            style_rows,
            key=lambda row: abs(_to_float(row.get("aspect_ratio")) - means["aspect_ratio"])
            + 0.001 * abs(_to_float(row.get("path_length")) - means["path_length"])
            + 0.001
            * abs(_to_float(row.get("connector_draw_length")) - means["connector_draw_length"]),
        )
        for row in ranked[:3]:
            _add_candidate(
                candidates,
                row,
                "representative",
                f"{STYLE_DISPLAY.get(style, style)} 接近当前风格均值，可作异常样本对照。",
                5,
                "作为对照样本看该风格的平均视觉效果是否可接受。",
            )

    ordered = sorted(candidates.values(), key=lambda c: (c.priority, c.case_type, c.char, c.style))
    if len(ordered) <= target_count:
        return ordered

    quotas = {
        "high_aspect_spread": max(1, target_count // 5),
        "low_aspect_spread": max(1, target_count // 5),
        "long_xingkai_connector": max(1, target_count // 6),
        "high_lishu_aspect": max(1, target_count // 6),
        "representative": max(3, target_count // 4),
    }
    selected: list[Candidate] = []
    selected_keys: set[tuple[str, str, str]] = set()

    for case_type, quota in quotas.items():
        for candidate in [item for item in ordered if item.case_type == case_type][:quota]:
            key = _candidate_key(candidate)
            if key not in selected_keys and len(selected) < target_count:
                selected.append(candidate)
                selected_keys.add(key)

    for candidate in ordered:
        key = _candidate_key(candidate)
        if key not in selected_keys and len(selected) < target_count:
            selected.append(candidate)
            selected_keys.add(key)

    return sorted(selected, key=lambda c: (c.priority, c.case_type, c.char, c.style))


def _choose_image(row: dict[str, str]) -> Path | None:
    for field in (
        "execution_render_png",
        "preview_png",
        "workspace_resampled_preview_png",
        "workspace_preview_png",
    ):
        value = row.get(field, "")
        if value:
            path = Path(value)
            if path.exists():
                return path
    output_dir = row.get("output_dir", "")
    if output_dir:
        for name in ("execution_render.png", "preview.png", "workspace_resampled_preview.png"):
            path = Path(output_dir) / name
            if path.exists():
                return path
    return None


def _candidate_to_row(candidate: Candidate, copied_image: Path | None = None) -> dict[str, str]:
    source_image = _choose_image(candidate.row)
    return {
        "char": candidate.char,
        "style": candidate.style,
        "case_type": candidate.case_type,
        "reason": candidate.reason,
        "priority": str(candidate.priority),
        "image_path": str(copied_image or source_image or ""),
        "summary_row_ref": f"{candidate.char}-{candidate.style}",
        "output_dir": candidate.row.get("output_dir", ""),
        "aspect_ratio": str(candidate.row.get("aspect_ratio", "")),
        "path_length": str(candidate.row.get("path_length", "")),
        "connection_count": str(candidate.row.get("connection_count", "")),
        "connector_draw_length": str(candidate.row.get("connector_draw_length", "")),
        "mean_width": str(candidate.row.get("mean_width", "")),
        "workspace_path_length_mm": str(candidate.row.get("workspace_path_length_mm", "")),
        "manual_check_focus": candidate.manual_check_focus,
    }


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _candidate_key(candidate: Candidate) -> tuple[str, str, str]:
    return candidate.char, candidate.style, candidate.case_type


def _copy_candidate_images(
    candidates: list[Candidate], selected_dir: Path
) -> dict[tuple[str, str, str], Path | None]:
    selected_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[tuple[str, str, str], Path | None] = {}
    for index, candidate in enumerate(candidates, start=1):
        source = _choose_image(candidate.row)
        if source is None:
            copied[_candidate_key(candidate)] = None
            continue
        suffix = source.suffix or ".png"
        filename = f"{index:02d}_{candidate.char}_{candidate.style}_{candidate.case_type}{suffix}"
        dest = selected_dir / filename
        shutil.copy2(source, dest)
        copied[_candidate_key(candidate)] = dest
    return copied


def _write_checklist(
    path: Path, candidates: list[Candidate], copied: dict[tuple[str, str, str], Path | None]
) -> None:
    lines = [
        "# 风格诊断人工看图校验清单",
        "",
        "本清单用于人工视觉校验。不能只看指标得出最终视觉效果结论。",
        "请逐项打开图片，记录是否自然、是否可区分、是否需要后续调参。",
        "",
    ]
    for index, candidate in enumerate(candidates, start=1):
        image = copied.get(_candidate_key(candidate)) or _choose_image(candidate.row)
        lines.extend(
            [
                f"## {index}. {candidate.char} / {STYLE_DISPLAY.get(candidate.style, candidate.style)}",
                "",
                f"- case_type: `{candidate.case_type}`",
                f"- priority: `{candidate.priority}`",
                f"- image: `{image or ''}`",
                f"- output_dir: `{candidate.row.get('output_dir', '')}`",
                f"- reason: {candidate.reason}",
                f"- 人工看图重点: {candidate.manual_check_focus}",
                f"- 指标: aspect_ratio={candidate.row.get('aspect_ratio', '')}, "
                f"path_length={candidate.row.get('path_length', '')}, "
                f"connection_count={candidate.row.get('connection_count', '')}, "
                f"connector_draw_length={candidate.row.get('connector_draw_length', '')}, "
                f"mean_width={candidate.row.get('mean_width', '')}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_report(
    path: Path,
    diagnostic_dir: Path,
    candidates: list[Candidate],
    case_counts: Counter,
    top_rows: list[dict[str, str]],
) -> None:
    lines = [
        "# 风格诊断 v2：异常样本定位与人工看图校验包",
        "",
        "## 本轮目的",
        "",
        "本轮从数据诊断转向人工视觉校验准备：自动挑出最值得人工看图的样本和最需要后续调参的问题。",
        "本轮没有替用户完成视觉判断，也没有调整 style profile 参数。不能只看指标判断最终视觉效果。",
        "",
        "## 输入诊断目录",
        "",
        f"`{diagnostic_dir}`",
        "",
        "## 候选样本统计",
        "",
        f"- candidate_count: `{len(candidates)}`",
        "",
        "| case_type | count |",
        "|---|---:|",
    ]
    for case_type, count in sorted(case_counts.items()):
        lines.append(f"| `{case_type}` | {count} |")
    lines.extend(["", "## Top Cases", "", "| char | style | case_type | priority | reason |", "|---|---|---|---:|---|"])
    for row in top_rows[:10]:
        lines.append(
            f"| {row['char']} | {row['style']} | `{row['case_type']}` | {row['priority']} | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "## 问题解释",
            "",
            "- lishu 宽扁是否过度：优先看 `high_lishu_aspect` 与 `high_aspect_spread` 样本，判断是否只是横向拉宽。",
            "- xingkai 连接是否过长/不自然：优先看 `long_xingkai_connector` 与 `strong_xingkai_connector` 样本。",
            "- kaishu 是否只是保守但缺少笔画风格：看 `representative` 与 `low_aspect_spread` 中的楷书样本。",
            "- 三风格是否在部分字上肉眼难分：看 `low_aspect_spread` 与 `weak_xingkai_connector` 样本。",
            "",
            "## 人工校验说明",
            "",
            "本轮只是生成候选包和校验清单，没有替用户完成视觉判断。请打开 `selected_images/` 或 "
            "`visual_audit_image_manifest.csv` 中的图，按 `visual_audit_checklist.md` 记录人工反馈。",
            "后续是否调参，应等待人工看图反馈后再决定。",
            "",
            "## 下一步建议",
            "",
            "- 对每个候选样本标注：可接受 / 连接过长 / 宽扁过度 / 风格难分 / 过于机械。",
            "- 根据标注结果再决定是否重新估计 style profile 中的宽扁、连接、笔画宽度或转折圆滑参数。",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _make_top_cases_image(
    path: Path, candidates: list[Candidate], copied: dict[tuple[str, str, str], Path | None]
) -> None:
    if Image is None:
        return
    items = candidates[:12]
    thumbs = []
    for candidate in items:
        image_path = copied.get(_candidate_key(candidate)) or _choose_image(candidate.row)
        if image_path and Path(image_path).exists():
            try:
                image = Image.open(image_path).convert("RGB").resize((180, 180))
            except Exception:
                image = Image.new("RGB", (180, 180), "white")
        else:
            image = Image.new("RGB", (180, 180), "white")
        thumbs.append((candidate, image))
    cols = 4
    rows = math.ceil(len(thumbs) / cols) or 1
    canvas = Image.new("RGB", (cols * 220, rows * 230), "white")
    draw = ImageDraw.Draw(canvas)
    for idx, (candidate, image) in enumerate(thumbs):
        x = (idx % cols) * 220
        y = (idx // cols) * 230
        canvas.paste(image, (x + 20, y + 10))
        draw.text((x + 20, y + 195), f"{candidate.char} {candidate.style}", fill="black")
        draw.text((x + 20, y + 212), candidate.case_type[:24], fill="black")
    canvas.save(path)


def run_visual_audit(
    diagnostic_dir: Path = DEFAULT_DIAGNOSTIC_DIR,
    output_dir: Path | None = None,
    target_count: int = 18,
) -> dict[str, object]:
    diagnostic_dir = Path(diagnostic_dir)
    summary_csv = diagnostic_dir / "style_diagnostic_summary.csv"
    if not summary_csv.exists():
        raise FileNotFoundError(f"style diagnostic summary not found: {summary_csv}")
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = diagnostic_dir.parent / f"style_visual_audit_{timestamp}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = _read_summary(summary_csv)
    candidates = select_candidates(rows, target_count=target_count)
    selected_dir = output_dir / "selected_images"
    copied = _copy_candidate_images(candidates, selected_dir)

    candidate_rows = [
        _candidate_to_row(candidate, copied.get(_candidate_key(candidate))) for candidate in candidates
    ]
    manifest_rows = []
    for candidate in candidates:
        source_image = _choose_image(candidate.row)
        copied_image = copied.get(_candidate_key(candidate))
        manifest_rows.append(
            {
                "char": candidate.char,
                "style": candidate.style,
                "case_type": candidate.case_type,
                "priority": str(candidate.priority),
                "image_path": str(source_image or ""),
                "copied_image_path": str(copied_image or ""),
                "output_dir": candidate.row.get("output_dir", ""),
                "fallback_ref": candidate.row.get("output_dir", "") or f"{candidate.char}-{candidate.style}",
                "manual_check_focus": candidate.manual_check_focus,
            }
        )

    candidates_csv = output_dir / "visual_audit_candidates.csv"
    manifest_csv = output_dir / "visual_audit_image_manifest.csv"
    report_md = output_dir / "visual_audit_report.md"
    checklist_md = output_dir / "visual_audit_checklist.md"
    top_cases_png = output_dir / "visual_audit_top_cases.png"
    metrics_json = output_dir / "visual_audit_metrics.json"

    _write_csv(candidates_csv, CSV_FIELDS, candidate_rows)
    _write_csv(manifest_csv, MANIFEST_FIELDS, manifest_rows)
    _write_checklist(checklist_md, candidates, copied)
    case_counts = Counter(candidate.case_type for candidate in candidates)
    _write_report(report_md, diagnostic_dir, candidates, case_counts, candidate_rows)
    _make_top_cases_image(top_cases_png, candidates, copied)

    metrics = {
        "diagnostic_dir": str(diagnostic_dir),
        "output_dir": str(output_dir),
        "candidate_count": len(candidates),
        "case_type_counts": dict(sorted(case_counts.items())),
        "selected_image_count": sum(1 for value in copied.values() if value is not None),
        "scope": "visual audit only; no parameter tuning, no API, no CoppeliaSim, no AUBO SDK",
    }
    metrics_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        **metrics,
        "outputs": {
            "candidates_csv": candidates_csv,
            "manifest_csv": manifest_csv,
            "report_md": report_md,
            "checklist_md": checklist_md,
            "top_cases_png": top_cases_png,
            "metrics_json": metrics_json,
            "selected_images_dir": selected_dir,
        },
    }


def _copy_to_paper_figures(result: dict[str, object], paper_dir: Path = DEFAULT_PAPER_DIR) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    outputs = result["outputs"]  # type: ignore[index]
    for key in ("candidates_csv", "report_md", "checklist_md"):
        path = outputs[key]  # type: ignore[index]
        shutil.copy2(path, paper_dir / Path(path).name)
    index = paper_dir / "style_visual_audit_index.md"
    index.write_text(
        "\n".join(
            [
                "# Style Visual Audit Index",
                "",
                f"源输出目录：`{result['output_dir']}`",
                "",
                "| 文件 | 内容 |",
                "|---|---|",
                "| `visual_audit_report.md` | 异常/代表样本人工看图校验报告 |",
                "| `visual_audit_checklist.md` | 可逐项人工标注的看图清单 |",
                "| `visual_audit_candidates.csv` | 候选样本、指标与选择理由 |",
                "",
                f"- candidate_count: `{result['candidate_count']}`",
                f"- case_type_counts: `{result['case_type_counts']}`",
                "",
                "边界：该索引只整理人工视觉校验包。本轮不调参、不调用 API、不连接仿真器或机器人。",
            ]
        ),
        encoding="utf-8",
    )
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a visual audit package from style diagnostics.")
    parser.add_argument("--diagnostic-dir", type=Path, default=DEFAULT_DIAGNOSTIC_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--target-count", type=int, default=18)
    parser.add_argument("--copy-to-paper-figures", action="store_true")
    args = parser.parse_args()

    result = run_visual_audit(
        diagnostic_dir=args.diagnostic_dir,
        output_dir=args.out_dir,
        target_count=args.target_count,
    )
    index = None
    if args.copy_to_paper_figures:
        index = _copy_to_paper_figures(result)
    printable = {
        "output_dir": result["output_dir"],
        "candidate_count": result["candidate_count"],
        "case_type_counts": result["case_type_counts"],
        "report_md": str(result["outputs"]["report_md"]),  # type: ignore[index]
        "checklist_md": str(result["outputs"]["checklist_md"]),  # type: ignore[index]
        "manifest_csv": str(result["outputs"]["manifest_csv"]),  # type: ignore[index]
        "paper_index": str(index) if index else "",
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
