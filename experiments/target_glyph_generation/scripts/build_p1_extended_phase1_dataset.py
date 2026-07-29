"""Build the sparse P1-extended image directory for FontDiffuser Phase 1."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.p1_dataset import build_p1_extended_phase1_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 P1-extended Phase 1 图像数据集")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    summary = build_p1_extended_phase1_dataset(arguments.config, arguments.output_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
