"""Three-sample stop-gate probe for the final local-only continuity attempt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_SAMPLES = ("xin", "yong", "zhong")
STOP_INTERNAL_JUMP_PX = 16.0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "visual_smoke_probe_after_review"
        / "inputs",
        help="Directory containing the single-glyph PNG inputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "local_method_final_attempt",
        help="Parent directory for the timestamped final-attempt batch output.",
    )
    parser.add_argument(
        "--samples",
        type=str,
        default=",".join(DEFAULT_SAMPLES),
        help="Comma-separated sample names to include.",
    )
    return parser


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_final_attempt_probe(
    *,
    input_dir: Path,
    output_dir: Path,
    samples: list[str],
) -> dict[str, Any]:
    import sys

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    if not input_dir.exists():
        return {
            "status": "missing_input_dir",
            "stage": "local_method_final_attempt_probe",
            "input_dir": str(input_dir),
        }

    image_paths = [input_dir / f"{sample}.png" for sample in samples]
    missing = [str(path) for path in image_paths if not path.exists()]
    if missing:
        return {
            "status": "missing_input_images",
            "stage": "local_method_final_attempt_probe",
            "input_dir": str(input_dir),
            "missing_inputs": missing,
        }

    src_dir = Path(__file__).resolve().parents[1] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from run_pipeline import run_batch
    from smoke_benchmark import create_smoke_benchmark_report, write_visual_audit_contact_sheet

    batch_dir = run_batch(
        image_paths,
        output_dir,
        threshold=180,
        crop_pad=2,
        min_component_pixels=6,
        spur_max_length=1,
        min_segment_pixels=8,
        ordering_endpoint_merge_distance=1.0,
        ordering_direction_cos_threshold=0.65,
    )
    contact_sheet_path = write_visual_audit_contact_sheet(batch_dir)
    benchmark = create_smoke_benchmark_report(batch_dir)
    sample_summaries = _load_sample_summaries(batch_dir, samples)
    decision, reasons = _gate_decision(sample_summaries)
    payload = {
        "status": "ok",
        "stage": "local_method_final_attempt_probe",
        "input_dir": str(input_dir),
        "batch_dir": str(batch_dir),
        "sample_count": len(samples),
        "samples": samples,
        "visual_audit_contact_sheet": str(contact_sheet_path),
        "manual_audit_sheet": benchmark["manual_audit_sheet"],
        "status_counts": benchmark["status_counts"],
        "audit_status_counts": benchmark["audit_status_counts"],
        "decision": decision,
        "decision_reasons": reasons,
        "stop_rule": (
            "If yong remains audit-risky or its internal pen-up jump stays above "
            f"{STOP_INTERNAL_JUMP_PX:.1f}px after consolidation, stop the pure local route."
        ),
        "sample_summaries": sample_summaries,
    }
    report_path = Path(batch_dir) / "final_attempt_gate_report.json"
    write_report(report_path, payload)
    payload["report_path"] = str(report_path)
    return payload


def _load_sample_summaries(batch_dir: Path, samples: list[str]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for sample in samples:
        summary_path = Path(batch_dir) / sample / "recovery_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summaries.append(
            {
                "sample": sample,
                "status": summary.get("status", ""),
                "audit_status": summary.get("audit_status", ""),
                "component_count": int(summary.get("component_count", 0)),
                "branch_point_count": int(summary.get("branch_point_count", 0)),
                "ordered_segment_count": int(summary.get("ordered_segment_count", 0)),
                "consolidated_segment_count": int(summary.get("consolidated_segment_count", 0)),
                "internal_max_pen_up_jump_px": float(summary.get("internal_max_pen_up_jump_px", 0.0)),
                "cross_component_max_pen_up_jump_px": float(summary.get("cross_component_max_pen_up_jump_px", 0.0)),
                "merged_segment_count": int(summary.get("merged_segment_count", 0)),
                "simplified_point_delta": int(summary.get("simplified_point_delta", 0)),
                "resampled_point_delta": int(summary.get("resampled_point_delta", 0)),
                "summary_path": str(summary_path),
            }
        )
    return summaries


def _gate_decision(sample_summaries: list[dict[str, Any]]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    by_sample = {row["sample"]: row for row in sample_summaries}

    failing = [row["sample"] for row in sample_summaries if row.get("status") != "ok"]
    if failing:
        reasons.append("failed samples: " + ", ".join(failing))

    risky = [row["sample"] for row in sample_summaries if row.get("audit_status") != "promising"]
    if risky:
        reasons.append("audit-risky samples: " + ", ".join(risky))

    yong = by_sample.get("yong")
    if yong is not None:
        if float(yong.get("internal_max_pen_up_jump_px", 0.0)) > STOP_INTERNAL_JUMP_PX:
            reasons.append(
                "yong internal jump remains above stop threshold "
                f"({float(yong['internal_max_pen_up_jump_px']):.2f}px > {STOP_INTERNAL_JUMP_PX:.2f}px)"
            )
        if int(yong.get("merged_segment_count", 0)) == 0:
            reasons.append("yong did not gain any same-component consolidation merges")

    if reasons:
        return "stop_and_switch_hybrid", reasons
    return "continue_local_method_once", ["all three samples remained visually plausible under the local route"]


def main() -> int:
    args = build_arg_parser().parse_args()
    samples = [sample.strip() for sample in args.samples.split(",") if sample.strip()]
    payload = run_final_attempt_probe(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        samples=samples,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
