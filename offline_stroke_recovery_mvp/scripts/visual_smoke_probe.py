"""Repeatable visual smoke probe for clean single-glyph inputs.

This script reruns the local offline recovery batch on a small set of
human-readable glyph images and writes a contact sheet for manual inspection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _detect_skeleton_backend() -> str:
    import sys

    src_dir = Path(__file__).resolve().parents[1] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from skeleton import skeleton_backend_name

    return skeleton_backend_name()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "visual_smoke_probe_after_review"
        / "inputs",
        help="Directory containing clean single-glyph PNG inputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "visual_smoke_probe_rerun",
        help="Parent directory for the timestamped batch output.",
    )
    parser.add_argument("--threshold", type=int, default=180)
    parser.add_argument("--crop-pad", type=int, default=2)
    parser.add_argument("--min-component-pixels", type=int, default=6)
    parser.add_argument("--spur-max-length", type=int, default=1)
    parser.add_argument("--min-segment-pixels", type=int, default=2)
    parser.add_argument("--ordering-endpoint-merge-distance", type=float, default=1.0)
    parser.add_argument("--ordering-direction-cos-threshold", type=float, default=0.65)
    parser.add_argument(
        "--require-skeleton-backend",
        type=str,
        default=None,
        help="Optional backend gate, e.g. 'skimage_skeletonize'.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional extra JSON report path in addition to the batch-local report.",
    )
    return parser


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_visual_smoke_probe(
    *,
    input_dir: Path,
    output_root: Path,
    threshold: int,
    crop_pad: int,
    min_component_pixels: int,
    spur_max_length: int,
    min_segment_pixels: int,
    ordering_endpoint_merge_distance: float = 1.0,
    ordering_direction_cos_threshold: float = 0.65,
    required_skeleton_backend: str | None = None,
) -> dict[str, Any]:
    import sys

    input_dir = Path(input_dir)
    output_root = Path(output_root)
    detected_skeleton_backend = _detect_skeleton_backend()
    if not input_dir.exists():
        return {
            "status": "missing_input_dir",
            "stage": "visual_smoke_probe",
            "input_dir": str(input_dir),
        }

    image_paths = sorted(path for path in input_dir.glob("*.png") if path.is_file())
    if not image_paths:
        return {
            "status": "no_input_images",
            "stage": "visual_smoke_probe",
            "input_dir": str(input_dir),
        }
    if required_skeleton_backend is not None and detected_skeleton_backend != required_skeleton_backend:
        return {
            "status": "skeleton_backend_mismatch",
            "stage": "visual_smoke_probe",
            "input_dir": str(input_dir),
            "required_skeleton_backend": required_skeleton_backend,
            "detected_skeleton_backend": detected_skeleton_backend,
        }

    src_dir = Path(__file__).resolve().parents[1] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from run_pipeline import run_batch
    from smoke_benchmark import create_smoke_benchmark_report, write_visual_audit_contact_sheet

    batch_dir = run_batch(
        image_paths,
        output_root,
        threshold=threshold,
        crop_pad=crop_pad,
        min_component_pixels=min_component_pixels,
        spur_max_length=spur_max_length,
        min_segment_pixels=min_segment_pixels,
        ordering_endpoint_merge_distance=ordering_endpoint_merge_distance,
        ordering_direction_cos_threshold=ordering_direction_cos_threshold,
    )
    contact_sheet_path = write_visual_audit_contact_sheet(batch_dir)
    benchmark = create_smoke_benchmark_report(batch_dir)
    payload = {
        "status": "ok",
        "stage": "visual_smoke_probe",
        "input_dir": str(input_dir),
        "batch_dir": str(batch_dir),
        "sample_count": len(image_paths),
        "threshold": threshold,
        "crop_pad": crop_pad,
        "min_component_pixels": min_component_pixels,
        "spur_max_length": spur_max_length,
        "min_segment_pixels": min_segment_pixels,
        "detected_skeleton_backend": detected_skeleton_backend,
        "ordering_endpoint_merge_distance": ordering_endpoint_merge_distance,
        "ordering_direction_cos_threshold": ordering_direction_cos_threshold,
        "manual_audit_sheet": benchmark["manual_audit_sheet"],
        "visual_audit_contact_sheet": str(contact_sheet_path),
        "status_counts": benchmark["status_counts"],
        "audit_status_counts": benchmark["audit_status_counts"],
    }
    write_report(batch_dir / "visual_smoke_report.json", payload)
    return payload


def main() -> int:
    args = build_arg_parser().parse_args()
    payload = run_visual_smoke_probe(
        input_dir=args.input_dir,
        output_root=args.output_dir,
        threshold=args.threshold,
        crop_pad=args.crop_pad,
        min_component_pixels=args.min_component_pixels,
        spur_max_length=args.spur_max_length,
        min_segment_pixels=args.min_segment_pixels,
        ordering_endpoint_merge_distance=args.ordering_endpoint_merge_distance,
        ordering_direction_cos_threshold=args.ordering_direction_cos_threshold,
        required_skeleton_backend=args.require_skeleton_backend,
    )
    if args.report is not None:
        write_report(args.report, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
