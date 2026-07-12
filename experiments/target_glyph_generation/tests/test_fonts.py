from pathlib import Path

import pytest

from target_glyph_generation.fonts import load_font_sources


def test_load_font_sources_rejects_unapproved_license(tmp_path: Path):
    path = tmp_path / "fonts.yaml"
    path.write_text(
        "fonts:\n  - font_id: blocked\n    license_id: Proprietary\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="未接受的许可证"):
        load_font_sources(path)
