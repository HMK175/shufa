from pathlib import Path

import pytest
import yaml

from target_glyph_generation.fonts import load_font_sources


def _write_v2_font_manifest(path: Path, **overrides) -> None:
    record = {
        "font_id": "example_regular",
        "display_name": "Example Regular",
        "version": "1.0",
        "source_url": "https://example.com/font",
        "license_id": "OFL-1.1",
        "license_url": "https://openfontlicense.org",
        "local_path": "fonts/example_regular.ttf",
        "family_id": "example",
        "category": "regular",
        "variant_role": "regular",
        "ecosystem_id": "example",
        "script_class": "regular",
        "style_role": "text",
    }
    record.update(overrides)
    path.write_text(
        yaml.safe_dump({"fonts": [record]}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


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


def test_load_font_sources_accepts_complete_v2_style_metadata(tmp_path: Path):
    path = tmp_path / "fonts.yaml"
    _write_v2_font_manifest(path)

    sources = load_font_sources(path, require_v2_metadata=True)

    assert sources[0].ecosystem_id == "example"
    assert sources[0].script_class == "regular"
    assert sources[0].style_role == "text"


@pytest.mark.parametrize("missing_field", ["ecosystem_id", "script_class", "style_role"])
def test_load_font_sources_requires_complete_string_v2_style_metadata(
    tmp_path: Path, missing_field: str
):
    path = tmp_path / "fonts.yaml"
    _write_v2_font_manifest(path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    del payload["fonts"][0][missing_field]
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match=missing_field):
        load_font_sources(path, require_v2_metadata=True)


@pytest.mark.parametrize("metadata_field", ["ecosystem_id", "script_class", "style_role"])
def test_load_font_sources_rejects_non_string_v2_style_metadata(
    tmp_path: Path, metadata_field: str
):
    path = tmp_path / "fonts.yaml"
    _write_v2_font_manifest(path, **{metadata_field: []})

    with pytest.raises(ValueError, match=metadata_field):
        load_font_sources(path, require_v2_metadata=True)


@pytest.mark.parametrize(
    ("category", "script_class", "style_role", "message"),
    [
        ("regular", "kaishu", "text", "script_class"),
        ("regular", "regular", "writing", "style_role"),
        ("writing", "regular", "writing", "script_class"),
        ("writing", "kaishu", "text", "style_role"),
    ],
)
def test_load_font_sources_rejects_style_role_incompatible_with_category(
    tmp_path: Path,
    category: str,
    script_class: str,
    style_role: str,
    message: str,
):
    path = tmp_path / "fonts.yaml"
    _write_v2_font_manifest(
        path,
        category=category,
        script_class=script_class,
        style_role=style_role,
    )

    with pytest.raises(ValueError, match=message):
        load_font_sources(path, require_v2_metadata=True)
