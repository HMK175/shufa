"""Visual smoke benchmark helpers for offline recovery batches."""

from __future__ import annotations

import csv
from collections import Counter
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


MANUAL_AUDIT_FIELDNAMES = [
    "sample",
    "status",
    "audit_status",
    "failure_reason",
    "mask_ok",
    "skeleton_ok",
    "segments_ok",
    "order_ok",
    "trajectory_ok",
    "failure_type",
    "notes",
    "summary_path",
    "candidate_order_image",
    "final_trajectory_image",
]

AUDIT_CONTACT_PANELS = [
    ("input", "input_image.png"),
    ("skeleton", "clean_skeleton.png"),
    ("trajectory", "final_trajectory.png"),
]


def collect_batch_summaries(batch_dir: Path) -> list[dict[str, str]]:
    """Collect one manual-audit row per sample summary in a batch directory."""
    batch_dir = Path(batch_dir)
    rows: list[dict[str, str]] = []
    sample_dirs = sorted((path for path in batch_dir.iterdir() if path.is_dir()), key=lambda path: path.name)
    for sample_dir in sample_dirs:
        summary_path = sample_dir / "recovery_summary.json"
        rows.append(_audit_row_for_sample_dir(sample_dir, summary_path))
    return rows


def write_manual_audit_sheet(batch_dir: Path, output_path: Path | None = None) -> Path:
    """Write a CSV template for human visual inspection of a batch."""
    batch_dir = Path(batch_dir)
    if output_path is None:
        output_path = batch_dir / "manual_audit_sheet.csv"
    output_path = Path(output_path)
    rows = collect_batch_summaries(batch_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANUAL_AUDIT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def create_smoke_benchmark_report(batch_dir: Path) -> dict[str, Any]:
    """Return status counts for a visual smoke benchmark batch."""
    batch_dir = Path(batch_dir)
    rows = collect_batch_summaries(batch_dir)
    status_counts = Counter(row["status"] for row in rows)
    audit_status_counts = Counter(row["audit_status"] for row in rows)
    return {
        "batch_dir": str(batch_dir),
        "total_samples": len(rows),
        "status_counts": _sorted_counts(status_counts),
        "audit_status_counts": _sorted_counts(audit_status_counts),
        "manual_audit_sheet": str(batch_dir / "manual_audit_sheet.csv"),
        "visual_audit_contact_sheet": _existing_path(batch_dir / "visual_audit_contact_sheet.png"),
    }


def write_visual_audit_contact_sheet(
    batch_dir: Path,
    output_path: Path | None = None,
    *,
    panel_size: tuple[int, int] = (160, 160),
    padding: int = 12,
    sample_label_width: int = 120,
    header_height: int = 22,
    sample_height: int = 22,
) -> Path:
    """Write a contact sheet that lines up key debug images per sample."""
    batch_dir = Path(batch_dir)
    if output_path is None:
        output_path = batch_dir / "visual_audit_contact_sheet.png"
    output_path = Path(output_path)

    rows = collect_batch_summaries(batch_dir)
    width = (
        padding
        + sample_label_width
        + len(AUDIT_CONTACT_PANELS) * (panel_size[0] + padding)
    )
    height = padding + header_height
    if rows:
        height += len(rows) * (sample_height + panel_size[1] + padding)
    else:
        height += sample_height + panel_size[1] + padding

    canvas = Image.new("RGB", (max(width, 1), max(height, 1)), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((padding, padding), "sample", fill=(30, 30, 30))
    for index, (label, _) in enumerate(AUDIT_CONTACT_PANELS):
        x = padding + sample_label_width + index * (panel_size[0] + padding)
        draw.text((x, padding), label, fill=(30, 30, 30))

    if not rows:
        draw.text((padding, padding + header_height), "no samples", fill=(120, 120, 120))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_path)
        return output_path

    for row_index, row in enumerate(rows):
        sample_dir = batch_dir / row["sample"]
        top = padding + header_height + row_index * (sample_height + panel_size[1] + padding)
        sample_label = row["sample"]
        audit_label = row["audit_status"]
        draw.text((padding, top), sample_label, fill=(20, 20, 20))
        draw.text((padding, top + 10), audit_label, fill=(120, 120, 120))
        panel_top = top + sample_height
        for panel_index, (_, filename) in enumerate(AUDIT_CONTACT_PANELS):
            left = padding + sample_label_width + panel_index * (panel_size[0] + padding)
            panel_image = _load_contact_panel(sample_dir / filename, panel_size)
            canvas.paste(panel_image, (left, panel_top))
            draw.rectangle(
                (
                    left,
                    panel_top,
                    left + panel_size[0] - 1,
                    panel_top + panel_size[1] - 1,
                ),
                outline=(200, 200, 200),
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return output_path


def _existing_path(path: Path) -> str:
    if path.exists():
        return str(path)
    return "n/a"


def _load_contact_panel(path: Path, panel_size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", panel_size, (248, 248, 248))
    draw = ImageDraw.Draw(panel)
    if not path.exists():
        draw.rectangle((0, 0, panel_size[0] - 1, panel_size[1] - 1), outline=(210, 210, 210))
        draw.text((8, 8), "missing", fill=(140, 140, 140))
        return panel
    try:
        image = Image.open(path).convert("RGB")
    except OSError:
        draw.rectangle((0, 0, panel_size[0] - 1, panel_size[1] - 1), outline=(210, 210, 210))
        draw.text((8, 8), "invalid", fill=(140, 140, 140))
        return panel

    image.thumbnail((panel_size[0] - 8, panel_size[1] - 8))
    offset_x = (panel_size[0] - image.width) // 2
    offset_y = (panel_size[1] - image.height) // 2
    panel.paste(image, (offset_x, offset_y))
    return panel


def _audit_row_for_sample_dir(sample_dir: Path, summary_path: Path) -> dict[str, str]:
    summary: dict[str, Any] = {}
    summary_path_value = str(summary_path)
    if not summary_path.exists():
        summary_path_value = "n/a"
        failure_reason = "missing_summary"
        status = "failed"
        audit_status = "failed"
        sample = sample_dir.name
    else:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            failure_reason = _string_value(summary.get("failure_reason", ""))
            status = _string_value(summary.get("status", ""))
            audit_status = _string_value(summary.get("audit_status", ""))
            sample = _string_value(summary.get("sample") or sample_dir.name)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            failure_reason = "invalid_summary"
            status = "failed"
            audit_status = "failed"
            sample = sample_dir.name

    return {
        "sample": sample,
        "status": status,
        "audit_status": audit_status,
        "failure_reason": failure_reason,
        "mask_ok": "",
        "skeleton_ok": "",
        "segments_ok": "",
        "order_ok": "",
        "trajectory_ok": "",
        "failure_type": "",
        "notes": "",
        "summary_path": summary_path_value,
        "candidate_order_image": _existing_path(sample_dir / "candidate_order.png"),
        "final_trajectory_image": _existing_path(sample_dir / "final_trajectory.png"),
    }


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
