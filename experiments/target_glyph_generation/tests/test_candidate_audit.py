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
