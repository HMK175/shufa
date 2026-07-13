from PIL import Image
import pytest

import target_glyph_generation.candidate_audit as candidate_audit
from target_glyph_generation.candidate_audit import create_candidate_preview_grid, validate_v2_style_pool
from target_glyph_generation.models import FontSource


def _source(
    font_id: str,
    family_id: str,
    category: str,
    *,
    ecosystem_id: str = "",
    script_class: str | None = None,
    style_role: str | None = None,
) -> FontSource:
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
        ecosystem_id=ecosystem_id,
        script_class=(
            script_class if script_class is not None else ("regular" if category == "regular" else "kaishu")
        ),
        style_role=(
            style_role if style_role is not None else ("text" if category == "regular" else "writing")
        ),
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
        _source(f"lxgw_{index}", f"family_{index}", "regular", ecosystem_id="lxgw")
        for index in range(4)
    ]

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

    with pytest.raises(ValueError, match="书体配额"):
        validate_v2_style_pool(
            sources,
            regular_style_count=8,
            writing_style_count=7,
            minimum_regular_families=8,
            maximum_styles_per_family=3,
            maximum_writing_styles_per_family=1,
        )


def test_validate_v2_style_pool_rejects_more_than_three_display_fonts():
    sources = [
        _source(f"display_{index}", f"family_{index}", "regular", style_role="display")
        for index in range(4)
    ]

    with pytest.raises(ValueError, match="展示字体上限"):
        validate_v2_style_pool(
            sources,
            regular_style_count=4,
            writing_style_count=0,
            minimum_regular_families=4,
            maximum_styles_per_family=3,
            maximum_writing_styles_per_family=1,
        )


def test_create_candidate_preview_grid_labels_style_role_metadata(tmp_path):
    from test_font_files import _build_test_font

    font_path = tmp_path / "fonts" / "test.ttf"
    font_path.parent.mkdir()
    _build_test_font(font_path)
    characters = ["A"] * 8

    text_output = tmp_path / "text.png"
    display_output = tmp_path / "display.png"
    create_candidate_preview_grid(
        [_source("test", "example", "regular", ecosystem_id="example", style_role="text")],
        tmp_path,
        characters,
        text_output,
    )
    create_candidate_preview_grid(
        [_source("test", "example", "regular", ecosystem_id="example", style_role="display")],
        tmp_path,
        characters,
        display_output,
    )

    with Image.open(text_output) as text_image, Image.open(display_output) as display_image:
        assert text_image.crop((0, 0, text_image.width, 20)).tobytes() != display_image.crop(
            (0, 0, display_image.width, 20)
        ).tobytes()


def test_create_candidate_preview_grid_draws_all_ascii_safe_metadata_labels(tmp_path, monkeypatch):
    from test_font_files import _build_test_font

    font_path = tmp_path / "fonts" / "font_a.ttf"
    font_path.parent.mkdir()
    _build_test_font(font_path)
    labels = []
    original_draw = candidate_audit.ImageDraw.Draw

    class CapturingDraw:
        def __init__(self, draw):
            self._draw = draw

        def text(self, position, text, **kwargs):
            if position == (2, 2):
                labels.append(text)
            return self._draw.text(position, text, **kwargs)

    monkeypatch.setattr(
        candidate_audit.ImageDraw,
        "Draw",
        lambda image: CapturingDraw(original_draw(image)),
    )
    output_path = tmp_path / "candidate_preview.png"

    result = create_candidate_preview_grid(
        [
            _source(
                "font_a",
                "family_a",
                "regular",
                ecosystem_id="生态",
                script_class="regular",
                style_role="display",
            )
        ],
        tmp_path,
        ["A"] * 8,
        output_path,
    )

    assert labels == ["font_a/??/regular/display"]
    assert output_path.is_file()
    assert result["style_count"] == 1
