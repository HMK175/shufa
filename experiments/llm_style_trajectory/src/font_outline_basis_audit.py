"""Manual audit pack for font-outline basis feasibility outputs.

This module only reads existing feasibility CSVs/images and prepares a manual
visual screening package. It does not alter the trajectory pipeline or defaults.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_FEASIBILITY_DIR = EXP_DIR / "outputs" / "font_outline_basis_feasibility_20260619_115008"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
PRIORITY_CHARS = ["山", "德", "福", "国", "中", "风"]
STYLE_ORDER = ["kaishu", "xingkai", "lishu"]

CANDIDATE_FIELDS = [
    "char",
    "char_id",
    "style",
    "basis_image",
    "endpoint_count",
    "branch_point_count",
    "skeleton_pixel_count",
    "connected_component_count",
    "aspect_ratio",
    "median_aspect_ratio",
    "aspect_gap",
    "issue_tags",
    "audit_priority",
    "manual_decision",
    "manual_comment",
]

IMAGE_MANIFEST_FIELDS = [
    "char",
    "char_id",
    "image_path",
    "source_image_path",
    "selected_styles",
    "selection_reasons",
    "max_audit_priority",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _quantile(values: Sequence[float], q: float) -> float:
    vals = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not vals:
        return 0.0
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def _build_thresholds(rows: Sequence[dict[str, str]]) -> dict[str, float]:
    endpoints = [_safe_float(row.get("endpoint_count")) for row in rows]
    branches = [_safe_float(row.get("branch_point_count")) for row in rows]
    pixels = [_safe_float(row.get("skeleton_pixel_count")) for row in rows]
    aspect_gaps = [abs(_safe_float(row.get("bbox_aspect_delta_vs_median"))) for row in rows]
    return {
        "endpoint": max(10.0, _quantile(endpoints, 0.75)),
        "branch": max(20.0, _quantile(branches, 0.75)),
        "complex": max(650.0, _quantile(pixels, 0.75)),
        "aspect_gap": max(0.25, _quantile(aspect_gaps, 0.75)),
    }


def classify_issue_tags(row: dict[str, str], thresholds: dict[str, float]) -> list[str]:
    tags: list[str] = []
    endpoints = _safe_float(row.get("endpoint_count"))
    branches = _safe_float(row.get("branch_point_count"))
    pixels = _safe_float(row.get("skeleton_pixel_count"))
    components = _safe_int(row.get("connected_component_count"))
    aspect_gap = abs(_safe_float(row.get("bbox_aspect_delta_vs_median")))
    skeleton_ok = str(row.get("skeleton_success", "")).lower() == "true"

    if endpoints >= thresholds["endpoint"]:
        tags.append("high_endpoint_count")
    if branches >= thresholds["branch"]:
        tags.append("high_branch_count")
    if components > 1:
        tags.append("disconnected_skeleton")
    if aspect_gap >= thresholds["aspect_gap"]:
        tags.append("high_aspect_gap")
    if pixels >= thresholds["complex"]:
        tags.append("complex_skeleton")
    if not skeleton_ok:
        tags.append("skeleton_failed")
    if skeleton_ok and not tags:
        tags.append("promising_candidate")
    return tags


def _priority_for(row: dict[str, str], tags: Sequence[str]) -> int:
    priority = 1
    if row.get("char") in PRIORITY_CHARS:
        priority += 2
    priority += min(4, len([tag for tag in tags if tag != "promising_candidate"]))
    if "high_aspect_gap" in tags:
        priority += 1
    if "high_branch_count" in tags or "high_endpoint_count" in tags:
        priority += 1
    if "promising_candidate" in tags:
        priority += 1
    return min(priority, 9)


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _manifest_by_char(rows: Sequence[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("char", ""): row for row in rows if row.get("char")}


def build_audit_candidates(
    summary_rows: Sequence[dict[str, str]],
    manifest_rows: Sequence[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    thresholds = _build_thresholds(summary_rows)
    images = _manifest_by_char(manifest_rows)
    candidates: list[dict[str, Any]] = []
    for row in summary_rows:
        char = row.get("char", "")
        tags = classify_issue_tags(row, thresholds)
        priority = _priority_for(row, tags)
        image = images.get(char, {}).get("image_path", "")
        candidates.append(
            {
                "char": char,
                "char_id": _char_id(char),
                "style": row.get("style", ""),
                "basis_image": image,
                "endpoint_count": _safe_int(row.get("endpoint_count")),
                "branch_point_count": _safe_int(row.get("branch_point_count")),
                "skeleton_pixel_count": _safe_int(row.get("skeleton_pixel_count")),
                "connected_component_count": _safe_int(row.get("connected_component_count")),
                "aspect_ratio": row.get("aspect_ratio", ""),
                "median_aspect_ratio": row.get("median_aspect_ratio", ""),
                "aspect_gap": row.get("bbox_aspect_delta_vs_median", ""),
                "issue_tags": ";".join(tags),
                "audit_priority": priority,
                "manual_decision": "",
                "manual_comment": "",
            }
        )
    candidates.sort(key=lambda item: (-int(item["audit_priority"]), item["char_id"], item["style"]))
    return candidates, thresholds


def _select_images(
    candidates: Sequence[dict[str, Any]],
    selected_dir: Path,
    max_images: int = 18,
) -> list[dict[str, Any]]:
    selected_dir.mkdir(parents=True, exist_ok=True)
    by_char: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_char[str(row["char"])].append(dict(row))

    selected_chars: set[str] = set()
    for char in PRIORITY_CHARS:
        if char in by_char:
            selected_chars.add(char)
    for style in STYLE_ORDER:
        style_rows = [row for row in candidates if row.get("style") == style]
        for row in sorted(style_rows, key=lambda item: -int(item["audit_priority"]))[:3]:
            selected_chars.add(str(row["char"]))
    for row in sorted(candidates, key=lambda item: -int(item["audit_priority"])):
        selected_chars.add(str(row["char"]))
        if len(selected_chars) >= max_images:
            break

    image_rows: list[dict[str, Any]] = []
    for char in sorted(selected_chars, key=lambda c: (-max(int(row["audit_priority"]) for row in by_char[c]), _char_id(c))):
        rows = by_char[char]
        source_image = next((str(row.get("basis_image", "")) for row in rows if row.get("basis_image")), "")
        if not source_image or not Path(source_image).exists():
            continue
        target = selected_dir / Path(source_image).name
        shutil.copy2(source_image, target)
        reasons = sorted({tag for row in rows for tag in str(row["issue_tags"]).split(";") if tag})
        styles = sorted({str(row["style"]) for row in rows if row.get("style")})
        image_rows.append(
            {
                "char": char,
                "char_id": _char_id(char),
                "image_path": str(target),
                "source_image_path": source_image,
                "selected_styles": ",".join(styles),
                "selection_reasons": ";".join(reasons),
                "max_audit_priority": max(int(row["audit_priority"]) for row in rows),
            }
        )
    return image_rows


def _issue_counts(candidates: Sequence[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in candidates:
        for tag in str(row.get("issue_tags", "")).split(";"):
            if tag:
                counter[tag] += 1
    return counter


def _style_issue_counts(candidates: Sequence[dict[str, Any]]) -> dict[str, Counter[str]]:
    counts: dict[str, Counter[str]] = {style: Counter() for style in STYLE_ORDER}
    for row in candidates:
        style = str(row.get("style", ""))
        counts.setdefault(style, Counter())
        for tag in str(row.get("issue_tags", "")).split(";"):
            if tag:
                counts[style][tag] += 1
    return counts


def _write_report(
    path: Path,
    feasibility_dir: Path,
    candidates: Sequence[dict[str, Any]],
    image_rows: Sequence[dict[str, Any]],
    thresholds: dict[str, float],
) -> None:
    total = len(candidates)
    tag_counts = _issue_counts(candidates)
    style_counts = _style_issue_counts(candidates)
    top_endpoint_branch = sorted(
        candidates,
        key=lambda row: int(row.get("endpoint_count", 0)) + int(row.get("branch_point_count", 0)),
        reverse=True,
    )[:10]
    top_aspect = sorted(
        candidates,
        key=lambda row: abs(_safe_float(row.get("aspect_gap"))),
        reverse=True,
    )[:10]
    top_priority = sorted(candidates, key=lambda row: -int(row.get("audit_priority", 0)))[:10]

    lines = [
        "# Font outline basis manual audit pack",
        "",
        "本轮目的：从 font-outline feasibility 结果中筛出最值得人工看图的样本，并把 skeleton 问题分成 endpoint 多、branch 多、断裂/多连通分量、aspect gap 大、skeleton 复杂等类别。",
        "",
        f"- input_feasibility_dir: `{feasibility_dir.resolve()}`",
        f"- total_candidates: {total}",
        f"- selected_images: {len(image_rows)}",
        "- 说明：以下阈值是 diagnostic threshold，不是最终判据；当前 skeleton 不能直接作为轨迹，需人工判断和后处理。",
        "",
        "## Diagnostic thresholds",
        "",
        "| metric | threshold |",
        "|---|---:|",
        f"| endpoint_count | {thresholds['endpoint']:.3f} |",
        f"| branch_point_count | {thresholds['branch']:.3f} |",
        f"| skeleton_pixel_count | {thresholds['complex']:.3f} |",
        f"| abs(aspect_gap) | {thresholds['aspect_gap']:.3f} |",
        "",
        "## Issue tag counts",
        "",
        "| issue_tag | count |",
        "|---|---:|",
    ]
    for tag, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {tag} | {count} |")

    lines.extend(["", "## Issue counts by style", "", "| style | high_endpoint | high_branch | disconnected | high_aspect | complex | promising |", "|---|---:|---:|---:|---:|---:|---:|"])
    for style in STYLE_ORDER:
        c = style_counts.get(style, Counter())
        lines.append(
            f"| {style} | {c.get('high_endpoint_count', 0)} | {c.get('high_branch_count', 0)} | "
            f"{c.get('disconnected_skeleton', 0)} | {c.get('high_aspect_gap', 0)} | "
            f"{c.get('complex_skeleton', 0)} | {c.get('promising_candidate', 0)} |"
        )

    lines.extend(["", "## Endpoint/branch top samples", "", "| char | style | endpoints | branches | issue_tags | image |", "|---|---|---:|---:|---|---|"])
    for row in top_endpoint_branch:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['endpoint_count']} | {row['branch_point_count']} | "
            f"{row['issue_tags']} | `{row['basis_image']}` |"
        )

    lines.extend(["", "## Aspect gap top samples", "", "| char | style | aspect | median_aspect | aspect_gap | issue_tags |", "|---|---|---:|---:|---:|---|"])
    for row in top_aspect:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['aspect_ratio']} | {row['median_aspect_ratio']} | "
            f"{row['aspect_gap']} | {row['issue_tags']} |"
        )

    lines.extend(["", "## Recommended first-look samples", "", "| char | style | priority | issue_tags | focus |", "|---|---|---:|---|---|"])
    for row in top_priority:
        focus = "看是否更有字体风格，同时确认 skeleton 是否过度分叉或断裂"
        if "promising_candidate" in str(row["issue_tags"]):
            focus = "看是否可作为低风险轨迹基底候选"
        elif "high_aspect_gap" in str(row["issue_tags"]):
            focus = "看 aspect 差异是否是真实风格信号还是形变过度"
        lines.append(f"| {row['char']} | {row['style']} | {row['audit_priority']} | {row['issue_tags']} | {focus} |")

    lines.extend(
        [
            "",
            "## Manual audit boundary",
            "",
            "- 本轮没有替用户完成视觉判断。",
            "- 数值分类只用于挑图和标注风险，不能替代人工看图。",
            "- 当前 skeleton 不能直接作为轨迹；若人工认为有价值，下一步还需要去噪、连通性修复、主路径提取和笔画顺序恢复。",
            "- 本轮不改默认 pipeline、不改 style profiles、不改 run_demo 默认行为、不调用 API、不连接 CoppeliaSim/AUBO/SDK、不做机器人控制。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_checklist(path: Path, candidates: Sequence[dict[str, Any]], image_rows: Sequence[dict[str, Any]]) -> None:
    top = sorted(candidates, key=lambda row: -int(row.get("audit_priority", 0)))[:18]
    image_by_char = {row["char"]: row["image_path"] for row in image_rows}
    lines = [
        "# Font outline basis visual audit checklist",
        "",
        "请人工看图后填写 `font_outline_basis_audit_candidates.csv` 里的 `manual_decision` 和 `manual_comment`。",
        "",
        "每张图重点判断：",
        "- 是否比 MakeMeAHanzi median 更有风格？",
        "- skeleton 是否连续？",
        "- 是否分叉过多？",
        "- 是否有明显噪点？",
        "- 是否保留了可写的主路径？",
        "- 是否适合继续做轨迹基底？",
        "- 若不适合，是适合作为风格参考，还是应舍弃？",
        "",
        "## Priority cases",
        "",
    ]
    for row in top:
        lines.extend(
            [
                f"### {row['char']} / {row['style']} / priority {row['audit_priority']}",
                "",
                f"- image: `{image_by_char.get(row['char'], row['basis_image'])}`",
                f"- issue_tags: `{row['issue_tags']}`",
                f"- endpoint_count: {row['endpoint_count']}",
                f"- branch_point_count: {row['branch_point_count']}",
                f"- connected_component_count: {row['connected_component_count']}",
                f"- aspect_gap: {row['aspect_gap']}",
                "- manual_decision: ",
                "- manual_comment: ",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_font_outline_basis_audit(
    feasibility_dir: Path | str = DEFAULT_FEASIBILITY_DIR,
    output_dir: Path | str | None = None,
    copy_to_paper: bool = True,
) -> dict[str, str]:
    feasibility_dir = Path(feasibility_dir)
    summary_csv = feasibility_dir / "font_outline_basis_summary.csv"
    manifest_csv = feasibility_dir / "font_outline_basis_manifest.csv"
    if not summary_csv.exists():
        raise FileNotFoundError(f"missing summary csv: {summary_csv}")
    if not manifest_csv.exists():
        raise FileNotFoundError(f"missing manifest csv: {manifest_csv}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"font_outline_basis_audit_{timestamp}"
    selected_dir = out_dir / "selected_images"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = _read_csv(summary_csv)
    manifest_rows = _read_csv(manifest_csv)
    candidates, thresholds = build_audit_candidates(summary_rows, manifest_rows)
    image_rows = _select_images(candidates, selected_dir)

    candidates_csv = out_dir / "font_outline_basis_audit_candidates.csv"
    report_md = out_dir / "font_outline_basis_audit_report.md"
    checklist_md = out_dir / "visual_audit_checklist.md"
    image_manifest_csv = out_dir / "font_outline_basis_image_manifest.csv"
    _write_csv(candidates_csv, candidates, CANDIDATE_FIELDS)
    _write_csv(image_manifest_csv, image_rows, IMAGE_MANIFEST_FIELDS)
    _write_report(report_md, feasibility_dir, candidates, image_rows, thresholds)
    _write_checklist(checklist_md, candidates, image_rows)

    paper_index = ""
    if copy_to_paper:
        paper_subdir = DEFAULT_PAPER_DIR / "font_outline_basis_audit"
        paper_subdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidates_csv, DEFAULT_PAPER_DIR / "font_outline_basis_audit_candidates.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "font_outline_basis_audit_report.md")
        shutil.copy2(checklist_md, DEFAULT_PAPER_DIR / "font_outline_basis_visual_audit_checklist.md")
        shutil.copy2(image_manifest_csv, DEFAULT_PAPER_DIR / "font_outline_basis_image_manifest.csv")
        for row in image_rows:
            source = Path(row["image_path"])
            if source.exists():
                shutil.copy2(source, paper_subdir / source.name)
        index_path = DEFAULT_PAPER_DIR / "font_outline_basis_audit_index.md"
        copied = sorted(paper_subdir.glob("basis_compare_*.png"))
        lines = [
            "# Font outline basis audit index",
            "",
            f"- source_feasibility_dir: `{feasibility_dir.resolve()}`",
            f"- source_audit_dir: `{out_dir.resolve()}`",
            "- This is a manual visual audit package and skeleton issue taxonomy.",
            "- It does not connect font skeletons to the default pipeline.",
            "",
            "| file | content |",
            "|---|---|",
            "| `font_outline_basis_audit_report.md` | issue statistics and first-look samples |",
            "| `font_outline_basis_audit_candidates.csv` | per char/style audit candidates with blank manual fields |",
            "| `font_outline_basis_visual_audit_checklist.md` | manual checklist |",
            "| `font_outline_basis_image_manifest.csv` | selected image manifest |",
        ]
        for image in copied:
            lines.append(f"| `font_outline_basis_audit/{image.name}` | selected basis comparison image |")
        index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "candidates_csv": str(candidates_csv),
        "report_md": str(report_md),
        "checklist_md": str(checklist_md),
        "image_manifest_csv": str(image_manifest_csv),
        "selected_images_dir": str(selected_dir),
        "paper_index": paper_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a manual audit pack for font-outline basis feasibility")
    parser.add_argument("--feasibility-dir", default=str(DEFAULT_FEASIBILITY_DIR))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_font_outline_basis_audit(
        feasibility_dir=Path(args.feasibility_dir),
        output_dir=Path(args.out_dir) if args.out_dir else None,
        copy_to_paper=not args.no_copy_to_paper,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
