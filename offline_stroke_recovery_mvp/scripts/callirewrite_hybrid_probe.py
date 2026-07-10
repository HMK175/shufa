"""Run the offline CalliRewrite-hybrid visual probe."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_hybrid import DEFAULT_SAMPLE_SET, run_callirewrite_hybrid_probe


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--converted-dir",
        type=Path,
        default=Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "callirewrite_runtime_probe"
        / "converted",
        help="Directory containing converted CalliRewrite per-sample folders.",
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
        default=",".join(DEFAULT_SAMPLE_SET),
        help="Comma-separated sample names to include.",
    )
    parser.add_argument(
        "--postprocess-mode",
        choices=["local", "raw_light_repair", "makemeahanzi_regroup", "auto"],
        default="local",
        help="Offline postprocess mode for the ordered segments.",
    )
    parser.add_argument(
        "--makemeahanzi-graphics",
        type=Path,
        default=Path("code") / "data" / "makemeahanzi" / "graphics.txt",
        help="Path to MakeMeAHanzi graphics.txt when using makemeahanzi_regroup mode.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    samples = [sample.strip() for sample in args.samples.split(",") if sample.strip()]
    payload = run_callirewrite_hybrid_probe(
        converted_dir=args.converted_dir,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        samples=samples,
        postprocess_mode=args.postprocess_mode,
        makemeahanzi_graphics_path=args.makemeahanzi_graphics,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
