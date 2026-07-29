"""Command-line entry point for P1-extended character partitioning."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.p1_partition import build_p1_extended_partition


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 P1-extended 字符划分清单")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    summary = build_p1_extended_partition(arguments.config, arguments.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
