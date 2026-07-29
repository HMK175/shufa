"""Build fixed P1-extended Phase 1 evaluation manifests."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.p1_evaluation import build_p1_fixed_test_manifests


def main() -> None:
    parser = argparse.ArgumentParser(description="Build fixed P1 Phase 1 evaluation manifests")
    parser.add_argument("--samples-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260716)
    parser.add_argument("--visual-per-style", type=int, default=20)
    arguments = parser.parse_args()
    summary = build_p1_fixed_test_manifests(
        arguments.samples_csv,
        arguments.output_dir,
        arguments.seed,
        arguments.visual_per_style,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
