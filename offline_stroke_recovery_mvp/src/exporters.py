"""Small file exporters for offline stroke recovery trials."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


TRIAL_FIELDNAMES = [
    "y",
    "x",
    "stroke_like_id",
    "point_index",
    "is_break",
    "order_index",
    "source",
]


def write_trial_csv(path: Path, ordered_segments: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    point_count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRIAL_FIELDNAMES)
        writer.writeheader()
        segments = list(ordered_segments)
        for segment_index, segment in enumerate(segments):
            if segment_index > 0:
                writer.writerow(
                    {
                        "y": "",
                        "x": "",
                        "stroke_like_id": "",
                        "point_index": "",
                        "is_break": "true",
                        "order_index": "",
                        "source": "segment_break",
                    }
                )
            source = _format_source(segment)
            for point_index, point in enumerate(segment.get("points", ()), start=1):
                y, x = point
                writer.writerow(
                    {
                        "y": _format_number(y),
                        "x": _format_number(x),
                        "stroke_like_id": segment.get("stroke_like_id", segment_index + 1),
                        "point_index": point_index,
                        "is_break": "false",
                        "order_index": segment.get("order_index", segment_index + 1),
                        "source": source,
                    }
                )
                point_count += 1
    return point_count


def write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_manifest_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_batch_report(
    path: Path,
    rows: Iterable[dict[str, Any]],
    *,
    manual_audit_sheet_path: Path | str | None = None,
) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Offline Stroke Recovery Batch Report",
        "",
        "## Samples processed",
        "",
        f"Total samples processed: {len(rows)}",
        "",
        "## Topology / Audit Summary",
        "",
        "| sample | status | failure_reason | audit_status | skeleton backend | components | branches | max pen-up jump px | points |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {sample} | {status} | {failure_reason} | {audit_status} | {skeleton_backend} | {component_count} | "
            "{branch_point_count} | {max_pen_up_jump_px} | {trajectory_point_count} |".format(
                sample=_md_cell(row.get("sample", "")),
                status=_md_cell(row.get("status", "")),
                failure_reason=_md_cell(_report_value(row.get("failure_reason", "n/a"))),
                audit_status=_md_cell(row.get("audit_status", "")),
                skeleton_backend=_md_cell(_report_value(row.get("skeleton_backend", "n/a"))),
                component_count=_report_value(row.get("component_count", "n/a")),
                branch_point_count=_report_value(row.get("branch_point_count", "n/a")),
                max_pen_up_jump_px=_format_report_number(row.get("max_pen_up_jump_px", "n/a")),
                trajectory_point_count=_report_value(row.get("trajectory_point_count", "n/a")),
            )
        )
    lines.extend(
        [
            "",
            "## Output File Locations",
            "",
            "| sample | sample directory | summary | trajectory | final trajectory image |",
            "|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| {sample} | {sample_dir} | {summary} | {trajectory} | {image} |".format(
                sample=_md_cell(row.get("sample", "")),
                sample_dir=_md_cell(row.get("sample_dir", "n/a")),
                summary=_md_cell(row.get("summary_path", "n/a")),
                trajectory=_md_cell(row.get("trajectory_path", "n/a")),
                image=_md_cell(row.get("final_trajectory_image", "n/a")),
            )
        )
    lines.extend(
        [
            "",
            "## Manual Audit Sheet",
            "",
            "Use the manual audit sheet for human visual inspection; it is not an automatic quality judgement.",
            "",
            f"Path: {_report_value(manual_audit_sheet_path)}",
            "",
            "## Manual audit reminder",
            "",
            "Manual visual inspection is required for every sample before making quality claims.",
            "",
            "Boundary note: these outputs are offline recovery debug outputs only; candidate ordering is not real stroke order and this is not robot output.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_source(segment: dict[str, Any]) -> str:
    source_ids = segment.get("source_segment_ids") or (segment.get("segment_id"),)
    return "segment:" + "+".join(str(source_id) for source_id in source_ids if source_id is not None)


def _format_number(value: Any) -> str:
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _format_report_number(value: Any) -> str:
    if value in {"", None, "n/a"}:
        return "n/a"
    return _format_number(value)


def _report_value(value: Any) -> Any:
    if value in {"", None}:
        return "n/a"
    return value


def _md_cell(value: Any) -> str:
    return (
        str(value)
        .replace("\r\n", "<br>")
        .replace("\r", "<br>")
        .replace("\n", "<br>")
        .replace("|", "\\|")
    )
