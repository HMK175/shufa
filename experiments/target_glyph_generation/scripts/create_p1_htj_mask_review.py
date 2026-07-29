"""Create before/after review pages for Huang Tingjian right-border masking."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.p1_review import create_p1_htj_mask_review


def main() -> None:
    parser = argparse.ArgumentParser(description="Create P1 Huang Tingjian mask review pages")
    parser.add_argument("--samples-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-count", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260716)
    arguments = parser.parse_args()
    summary = create_p1_htj_mask_review(
        arguments.samples_csv,
        arguments.output_dir,
        arguments.sample_count,
        arguments.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
