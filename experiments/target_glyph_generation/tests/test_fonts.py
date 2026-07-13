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


def test_load_font_sources_requires_family_id_for_v2_metadata(tmp_path: Path):
    path = tmp_path / "fonts.yaml"
    path.write_text(
        "fonts:\n"
        "  - font_id: example_regular\n"
        "    display_name: Example Regular\n"
        "    version: 1.0\n"
        "    source_url: https://example.com/font\n"
        "    license_id: OFL-1.1\n"
        "    license_url: https://openfontlicense.org\n"
        "    local_path: fonts/example_regular.ttf\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="family_id"):
        load_font_sources(path, require_v2_metadata=True)


def test_load_font_sources_rejects_invalid_category_for_v2_metadata(tmp_path: Path):
    path = tmp_path / "fonts.yaml"
    path.write_text(
        "fonts:\n"
        "  - font_id: example_regular\n"
        "    display_name: Example Regular\n"
        "    version: 1.0\n"
        "    source_url: https://example.com/font\n"
        "    license_id: OFL-1.1\n"
        "    license_url: https://openfontlicense.org\n"
        "    local_path: fonts/example_regular.ttf\n"
        "    family_id: example\n"
        "    category: display\n"
        "    variant_role: regular\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="category"):
        load_font_sources(path, require_v2_metadata=True)


def test_load_font_sources_rejects_non_string_category_for_v2_metadata(tmp_path: Path):
    path = tmp_path / "fonts.yaml"
    path.write_text(
        "fonts:\n"
        "  - font_id: example_regular\n"
        "    display_name: Example Regular\n"
        "    version: 1.0\n"
        "    source_url: https://example.com/font\n"
        "    license_id: OFL-1.1\n"
        "    license_url: https://openfontlicense.org\n"
        "    local_path: fonts/example_regular.ttf\n"
        "    family_id: example\n"
        "    category: []\n"
        "    variant_role: regular\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="字体记录 category 必须是 regular 或 writing"):
        load_font_sources(path, require_v2_metadata=True)
