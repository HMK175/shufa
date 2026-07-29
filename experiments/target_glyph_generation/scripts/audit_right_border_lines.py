"""Create a manifest for detached right-border line artifacts."""

import argparse
import json
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from target_glyph_generation.glyph_artifacts import audit_right_border_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="审计字图中的孤立右边界黑线")
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    parser.add_argument("--path-column", default="target_path")
    arguments = parser.parse_args()
    summary = audit_right_border_lines(
        arguments.input_csv, arguments.output_csv, arguments.path_column
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
