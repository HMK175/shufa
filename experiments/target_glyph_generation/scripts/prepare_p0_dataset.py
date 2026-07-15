"""构建用于 FontDiffuser 流程验证的 P0 探索性数据集。"""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.p0_dataset import build_p0_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 P0 外部书写风格与开源字体混合数据集")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--chinese-manifest", type=Path, required=True)
    parser.add_argument("--calligrapher-manifest", type=Path, required=True)
    parser.add_argument("--open-dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    summary = build_p0_dataset(
        config_path=arguments.config,
        chinese_manifest_path=arguments.chinese_manifest,
        calligrapher_manifest_path=arguments.calligrapher_manifest,
        open_dataset_root=arguments.open_dataset_root,
        output_root=arguments.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
