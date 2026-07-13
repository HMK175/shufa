"""命令行入口：生成字体数据集人工审计结果。"""

import argparse
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.audit import write_audit_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="生成字体数据集审计网格")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(write_audit_summary(arguments.dataset_root, arguments.output_dir))


if __name__ == "__main__":
    main()
