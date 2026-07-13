import pytest

from target_glyph_generation.candidate_audit import validate_v2_style_pool
from target_glyph_generation.models import FontSource


def _source(font_id: str, family_id: str, category: str) -> FontSource:
    return FontSource(
        font_id=font_id,
        display_name=font_id,
        version="1.0",
        source_url="https://example.com/font.ttf",
        license_id="OFL-1.1",
        license_url="https://example.com/OFL.txt",
        local_path=f"fonts/{font_id}.ttf",
        family_id=family_id,
        category=category,
        variant_role="regular",
    )


def test_validate_v2_style_pool_rejects_more_than_three_regular_styles_per_family():
    sources = [_source(f"noto_{index}", "noto", "regular") for index in range(4)]

    with pytest.raises(ValueError, match="家族上限"):
        validate_v2_style_pool(
            sources,
            regular_style_count=4,
            writing_style_count=0,
            minimum_regular_families=1,
            maximum_styles_per_family=3,
            maximum_writing_styles_per_family=1,
        )


def test_validate_v2_style_pool_rejects_more_than_three_lxgw_ecosystem_styles():
    sources = [
        _source(f"lxgw_{index}", f"family_{index}", "regular")
        for index in range(4)
    ]
    for source in sources:
        object.__setattr__(source, "ecosystem_id", "lxgw")

    with pytest.raises(ValueError, match="LXGW 生态上限"):
        validate_v2_style_pool(
            sources,
            regular_style_count=4,
            writing_style_count=0,
            minimum_regular_families=4,
            maximum_styles_per_family=3,
            maximum_writing_styles_per_family=1,
        )


def test_validate_v2_style_pool_rejects_wrong_writing_script_quota():
    sources = [_source(f"regular_{index}", f"family_{index}", "regular") for index in range(8)]
    sources += [_source(f"writing_{index}", f"writing_{index}", "writing") for index in range(7)]
    for source in sources:
        object.__setattr__(source, "script_class", "regular" if source.category == "regular" else "kaishu")

    with pytest.raises(ValueError, match="书体配额"):
        validate_v2_style_pool(
            sources,
            regular_style_count=8,
            writing_style_count=7,
            minimum_regular_families=8,
            maximum_styles_per_family=3,
            maximum_writing_styles_per_family=1,
        )
