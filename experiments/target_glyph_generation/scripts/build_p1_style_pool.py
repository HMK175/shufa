"""Command-line entry point for the P1 style-pool registry."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.p1_style_pool import build_style_pool


def main() -> None:
    parser = argparse.ArgumentParser(description="整合已审计的 P1 风格池")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    summary = build_style_pool(arguments.config, arguments.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
