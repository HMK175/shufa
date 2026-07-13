"""命令行入口：审计候选字体的文件、覆盖率与固定字符预览。"""

import argparse
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.candidate_audit import audit_font_candidates
from target_glyph_generation.characters import load_characters
from target_glyph_generation.fonts import load_font_sources


CANDIDATE_PREVIEW_CHARACTERS = list("一二三人口心中天")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"审计 FontDiffuser v2 候选字体（固定预览字：{''.join(CANDIDATE_PREVIEW_CHARACTERS)}）"
    )
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--characters", type=Path, required=True)
    parser.add_argument("--font-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--canvas-size", type=int, default=128)
    arguments = parser.parse_args()

    summary = audit_font_candidates(
        load_font_sources(arguments.sources, require_v2_metadata=True),
        arguments.font_root,
        load_characters(arguments.characters),
        arguments.output_dir,
        CANDIDATE_PREVIEW_CHARACTERS,
        arguments.canvas_size,
    )
    print(f"候选字体审计完成：accepted={summary['accepted_count']}, rejected={summary['rejected_count']}")


if __name__ == "__main__":
    main()
