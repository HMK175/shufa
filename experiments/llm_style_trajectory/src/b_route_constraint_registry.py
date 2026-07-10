"""B-route constraint registry.

This module unifies H2 font-reference constraints, section constraints, and
prior B-route evidence into a trial-only gating registry. It does not move any
trajectory points and does not integrate with the default pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_H2_CONSTRAINTS_JSON = EXP_DIR / "outputs" / "font_reference_constraints_20260619_230426" / "font_reference_constraints.json"
DEFAULT_SECTION_PACKAGE_JSON = EXP_DIR / "outputs" / "section_constraints_package_20260621_003023" / "section_constraints_package.json"

SAMPLES: list[tuple[str, str]] = [(chr(0x5C71), "lishu"), (chr(0x98CE), "lishu")]
USABLE_CONSTRAINTS = [
    "bbox_aspect",
    "lower_half_width_ratio",
    "left_right_spread",
    "bbox_center_shift_x",
    "bbox_center_shift_y",
]
REFERENCE_ONLY_CONSTRAINTS = [
    "component_count",
    "endpoint_count",
    "branch_count",
    "connectedness_hint",
    "skeleton_complexity_score",
]
BLOCKED_CONSTRAINTS = ["raw_skeleton_path", "unordered_skeleton_segments"]
REGISTRY_JSON = "b_route_constraint_registry.json"
REGISTRY_CSV = "b_route_constraint_registry.csv"
REPORT_MD = "b_route_constraint_registry_report.md"
MANIFEST_CSV = "b_route_constraint_registry_manifest.csv"
INDEX_MD = "b_route_constraint_registry_index.md"


@dataclass
class RegistryEntry:
    char: str
    style: str
    strategy_selected: str
    section_strategy: str
    fallback_used: bool
    usable_constraints: list[str]
    reference_only_constraints: list[str]
    blocked_constraints: list[str]
    max_shift_cap: int
    human_review_required: bool
    recommended_next_use: str
    source_h2_status: str = ""
    source_section_status: str = ""
    note: str = ""

    def as_json(self) -> dict[str, Any]:
        return {
            "char": self.char,
            "style": self.style,
            "strategy_selected": self.strategy_selected,
            "section_strategy": self.section_strategy,
            "fallback_used": self.fallback_used,
            "usable_constraints": self.usable_constraints,
            "reference_only_constraints": self.reference_only_constraints,
            "blocked_constraints": self.blocked_constraints,
            "max_shift_cap": self.max_shift_cap,
            "human_review_required": self.human_review_required,
            "recommended_next_use": self.recommended_next_use,
            "source_h2_status": self.source_h2_status,
            "source_section_status": self.source_section_status,
            "note": self.note,
        }

    def as_csv(self) -> dict[str, Any]:
        return {
            "char": self.char,
            "char_id": f"u{ord(self.char):04x}",
            "style": self.style,
            "strategy_selected": self.strategy_selected,
            "section_strategy": self.section_strategy,
            "fallback_used": self.fallback_used,
            "usable_constraint_count": len(self.usable_constraints),
            "reference_only_constraint_count": len(self.reference_only_constraints),
            "blocked_constraint_count": len(self.blocked_constraints),
            "max_shift_cap": self.max_shift_cap,
            "human_review_required": self.human_review_required,
            "recommended_next_use": self.recommended_next_use,
            "note": self.note,
        }


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_h2_samples(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    data = _read_json(path)
    return {(sample.get("char", ""), sample.get("style", "")): sample for sample in data.get("samples", [])}


def _extract_section_samples(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    data = _read_json(path)
    return {(sample.get("char", ""), sample.get("style", "")): sample for sample in data.get("samples", [])}


def _load_registry_entry(char: str, style: str, h2_sample: dict[str, Any], section_sample: dict[str, Any]) -> RegistryEntry:
    if (char, style) == (chr(0x5C71), "lishu"):
        return RegistryEntry(
            char=char,
            style=style,
            strategy_selected="component_first_safe",
            section_strategy=section_sample.get("section_strategy", "hybrid_component_first"),
            fallback_used=bool(section_sample.get("fallback_used", False)),
            usable_constraints=list(USABLE_CONSTRAINTS),
            reference_only_constraints=list(REFERENCE_ONLY_CONSTRAINTS),
            blocked_constraints=list(BLOCKED_CONSTRAINTS),
            max_shift_cap=15,
            human_review_required=True,
            recommended_next_use="B_safe_input",
            source_h2_status=h2_sample.get("overall_recommendation", ""),
            source_section_status=section_sample.get("recommended_next_use", ""),
            note="Best candidate for bounded B adaptation using component bbox first and safe constraints only.",
        )

    return RegistryEntry(
        char=char,
        style=style,
        strategy_selected="fallback_first_reference_only",
        section_strategy=section_sample.get("section_strategy", "hybrid_component_first"),
        fallback_used=True,
        usable_constraints=list(USABLE_CONSTRAINTS),
        reference_only_constraints=list(REFERENCE_ONLY_CONSTRAINTS),
        blocked_constraints=list(BLOCKED_CONSTRAINTS),
        max_shift_cap=12,
        human_review_required=True,
        recommended_next_use="fallback_first_reference_only",
        source_h2_status=h2_sample.get("overall_recommendation", ""),
        source_section_status=section_sample.get("recommended_next_use", ""),
        note="Use fallback-first section guidance and keep as conservative reference-only input.",
    )


def _render_figure(path: Path, entry: RegistryEntry, source_hint: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(4.8, 4.2), dpi=150)
    ax.set_title(f"{entry.char}/{entry.style} registry gate", fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    rects = [
        (0.08, 0.66, 0.84, 0.20, "usable", "#2ca02c"),
        (0.08, 0.40, 0.84, 0.18, "reference-only", "#1f77b4"),
        (0.08, 0.14, 0.84, 0.18, "blocked", "#d62728"),
    ]
    for x, y, w, h, label, color in rects:
        ax.add_patch(plt.Rectangle((x, y), w, h, fill=False, edgecolor=color, linewidth=1.6))
        ax.text(x + 0.03, y + h / 2.0, label, va="center", fontsize=8, color=color)
    ax.text(0.12, 0.90, f"strategy: {entry.strategy_selected}", fontsize=8)
    ax.text(0.12, 0.83, f"section: {entry.section_strategy}", fontsize=8)
    ax.text(0.12, 0.58, f"max_shift_cap: {entry.max_shift_cap}px", fontsize=8)
    ax.text(0.12, 0.02, f"source: {source_hint}", fontsize=7, color="#444444")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, entries: Sequence[RegistryEntry], h2_status: str, section_status: str) -> None:
    lines = [
        "# B-route constraint registry",
        "",
        "This registry is a trial-only gating entry point for the B route.",
        "It is registry-gated adaptation, not direct pulling.",
        "It unifies H2 font-reference constraints and section constraints into a read-only evidence pack.",
        "",
        "## Boundary",
        "",
        "- trial-only / not_used_by_default",
        "- no point movement by default",
        "- no default pipeline integration",
        "- raw skeleton paths remain blocked",
        "",
        f"- output_dir: `{output_dir}`",
        f"- h2_source_status: `{h2_status}`",
        f"- section_source_status: `{section_status}`",
        "",
        "## Gate policy",
        "",
        "- usable_for_adaptation: bbox_aspect, lower_half_width_ratio, left_right_spread, bbox_center_shift_x, bbox_center_shift_y",
        "- reference_only: component_count, endpoint_count, branch_count, connectedness_hint, skeleton_complexity_score",
        "- blocked: raw_skeleton_path, unordered_skeleton_segments",
        "- 山/lishu uses component_first_safe with a 15 px shift cap.",
        "- 风/lishu uses fallback_first_reference_only with a 12 px shift cap.",
        "",
        "## Entries",
        "",
        "| sample | strategy | section | fallback | usable | reference | blocked | shift cap | next use |",
        "|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for entry in entries:
        lines.append(
            f"| {entry.char}/{entry.style} | {entry.strategy_selected} | {entry.section_strategy} | {entry.fallback_used} | "
            f"{len(entry.usable_constraints)} | {len(entry.reference_only_constraints)} | {len(entry.blocked_constraints)} | {entry.max_shift_cap} | {entry.recommended_next_use} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The registry does not replace trajectory generation. It only decides which evidence is safe enough to feed into a bounded B prototype.",
            "If a sample is unstable, the registry forces fallback-first section guidance instead of raw point pulling.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_index(path: Path, output_dir: Path, summary_json: Path, summary_csv: Path, report_md: Path, manifest_csv: Path) -> None:
    lines = [
        "# B-route constraint registry index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- status: `trial_only_not_used_by_default`",
        "",
        "## Artifacts",
        "",
        f"- registry json: `{summary_json}`",
        f"- registry csv: `{summary_csv}`",
        f"- report: `{report_md}`",
        f"- manifest: `{manifest_csv}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_b_route_constraint_registry(output_dir: Path | str | None = None, copy_to_paper: bool = True) -> dict[str, Any]:
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT / f"b_route_constraint_registry_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = Path(output_dir)
    figures_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    h2_samples = _extract_h2_samples(DEFAULT_H2_CONSTRAINTS_JSON)
    section_samples = _extract_section_samples(DEFAULT_SECTION_PACKAGE_JSON)
    entries: list[RegistryEntry] = []
    for char, style in SAMPLES:
        h2_sample = h2_samples[(char, style)]
        section_sample = section_samples[(char, style)]
        entries.append(_load_registry_entry(char, style, h2_sample, section_sample))

    summary_json = {
        "status": "trial_only_not_used_by_default",
        "default_policy": "registry_gated_adaptation_only",
        "entries": [entry.as_json() for entry in entries],
        "usable_constraints": USABLE_CONSTRAINTS,
        "reference_only_constraints": REFERENCE_ONLY_CONSTRAINTS,
        "blocked_constraints": BLOCKED_CONSTRAINTS,
        "source_h2": str(DEFAULT_H2_CONSTRAINTS_JSON),
        "source_section_package": str(DEFAULT_SECTION_PACKAGE_JSON),
    }
    summary_json_path = out_dir / REGISTRY_JSON
    summary_json_path.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_csv_path = out_dir / REGISTRY_CSV
    _write_csv(
        summary_csv_path,
        [entry.as_csv() for entry in entries],
        [
            "char",
            "char_id",
            "style",
            "strategy_selected",
            "section_strategy",
            "fallback_used",
            "usable_constraint_count",
            "reference_only_constraint_count",
            "blocked_constraint_count",
            "max_shift_cap",
            "human_review_required",
            "recommended_next_use",
            "note",
        ],
    )

    manifest_rows: list[dict[str, Any]] = []
    for entry in entries:
        figure_path = figures_dir / f"registry_probe_u{ord(entry.char):04x}_{entry.style}.png"
        _render_figure(figure_path, entry, source_hint=f"{entry.source_h2_status};{entry.source_section_status}")
        manifest_rows.append(
            {
                "char": entry.char,
                "char_id": f"u{ord(entry.char):04x}",
                "style": entry.style,
                "artifact_type": "figure",
                "path": str(figure_path),
                "note": entry.strategy_selected,
            }
        )
    manifest_rows.extend(
        [
            {
                "char": "",
                "char_id": "",
                "style": "",
                "artifact_type": "summary_json",
                "path": str(summary_json_path),
                "note": "registry json",
            },
            {
                "char": "",
                "char_id": "",
                "style": "",
                "artifact_type": "summary_csv",
                "path": str(summary_csv_path),
                "note": "registry csv",
            },
        ]
    )
    manifest_csv_path = out_dir / MANIFEST_CSV
    _write_csv(manifest_csv_path, manifest_rows, ["char", "char_id", "style", "artifact_type", "path", "note"])

    report_md_path = out_dir / REPORT_MD
    _write_report(report_md_path, out_dir, entries, h2_status=summary_json["source_h2"], section_status=summary_json["source_section_package"])

    index_path = DEFAULT_PAPER_DIR / INDEX_MD
    _write_index(index_path, out_dir, summary_json_path, summary_csv_path, report_md_path, manifest_csv_path)

    if copy_to_paper:
        paper_dir = DEFAULT_PAPER_DIR
        paper_dir.mkdir(parents=True, exist_ok=True)
        for src in [summary_json_path, summary_csv_path, report_md_path, manifest_csv_path]:
            shutil.copy2(src, paper_dir / src.name)
        for figure in figures_dir.glob("*.png"):
            shutil.copy2(figure, paper_dir / figure.name)

    return {
        "output_dir": str(out_dir),
        "summary_json": str(summary_json_path),
        "summary_csv": str(summary_csv_path),
        "report_md": str(report_md_path),
        "manifest_csv": str(manifest_csv_path),
        "index_md": str(index_path),
    }


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a trial-only B-route constraint registry.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main() -> int:
    args = _build_argparser().parse_args()
    result = run_b_route_constraint_registry(output_dir=args.output_dir, copy_to_paper=not args.no_paper_copy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
