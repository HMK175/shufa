"""Rebuild converted CalliRewrite outputs and rerun the offline hybrid probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_refresh import run_callirewrite_refresh_probe


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seq-data-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "callirewrite_runtime_probe"
        / "__new_train_phase_2"
        / "seq_data",
        help="Directory containing CalliRewrite seq_extract .npz files.",
    )
    parser.add_argument(
        "--converted-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted",
        help="Directory where refreshed converted per-sample folders will be written.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "visual_smoke_probe_after_review"
        / "inputs",
        help="Directory containing original single-glyph PNG inputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "callirewrite_hybrid_probe",
        help="Parent directory for the timestamped hybrid batch output.",
    )
    parser.add_argument(
        "--samples",
        type=str,
        default="",
        help="Comma-separated sample names to refresh; empty means every .npz in seq-data-dir.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    samples = [sample.strip() for sample in args.samples.split(",") if sample.strip()]
    payload = run_callirewrite_refresh_probe(
        seq_data_dir=args.seq_data_dir,
        converted_dir=args.converted_dir,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        samples=samples,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
