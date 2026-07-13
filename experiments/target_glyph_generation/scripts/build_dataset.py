"""命令行入口：构建 FontDiffuser 开放字体数据集。"""

import argparse
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.builder import build_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 FontDiffuser 开放字体数据集")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--characters", type=Path, default=PROJECT_DIR / "configs" / "characters_candidate_v1.txt")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--limit-fonts", type=int)
    parser.add_argument("--limit-characters", type=int)
    arguments = parser.parse_args()
    print(build_dataset(arguments.config, arguments.sources, arguments.characters, arguments.output_root, arguments.limit_fonts, arguments.limit_characters))


if __name__ == "__main__":
    main()
