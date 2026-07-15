"""Build the fixed directory layout required by the unmodified FontDiffuser loader."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.fontdiffuser_adapter import build_fontdiffuser_training_adapter


def main() -> None:
    parser = argparse.ArgumentParser(description="将 P0 训练子集适配为 FontDiffuser 官方数据目录")
    parser.add_argument("--p0-dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--style-ids", nargs="+")
    parser.add_argument("--character-limit", type=int)
    parser.add_argument("--selection-seed", type=int, default=20260715)
    arguments = parser.parse_args()
    summary = build_fontdiffuser_training_adapter(
        p0_dataset_root=arguments.p0_dataset_root,
        output_root=arguments.output_root,
        style_ids=arguments.style_ids,
        character_limit=arguments.character_limit,
        selection_seed=arguments.selection_seed,
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
