import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

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

    escaped_ecosystem_id = "生态".encode("unicode_escape").decode("ascii")
    assert labels == [f"font_a/{escaped_ecosystem_id}/regular/display"]
    assert labels[0].isascii()
    assert output_path.is_file()
    assert result["style_count"] == 1


def test_audit_font_candidates_rejects_font_with_missing_characters(tmp_path):
    from test_font_files import _build_test_font

    font_path = tmp_path / "fonts" / "present.ttf"
    font_path.parent.mkdir()
    _build_test_font(font_path)

    summary = candidate_audit.audit_font_candidates(
        [_source("present", "example", "regular")],
        tmp_path,
        ["A", "B"],
        tmp_path / "audit",
        preview_characters=["A"] * 8,
    )

    assert summary["candidate_count"] == 1
    assert summary["accepted_count"] == 0
    assert summary["records"][0]["missing_characters"] == ["B"]
    assert summary["records"][0]["accepted"] is False


def test_audit_font_candidates_rejects_missing_font_file(tmp_path):
    summary = candidate_audit.audit_font_candidates(
        [_source("absent", "example", "regular")],
        tmp_path,
        ["A"],
        tmp_path / "audit",
        preview_characters=["A"] * 8,
    )

    record = summary["records"][0]
    assert summary["rejected_count"] == 1
    assert record["accepted"] is False
    assert record["file_error"]
    assert record["font_sha256"] is None


def test_audit_font_candidates_writes_summary_and_preview_for_renderable_font(tmp_path):
    from test_font_files import _build_test_font

    font_path = tmp_path / "fonts" / "present.ttf"
    font_path.parent.mkdir()
    _build_test_font(font_path)
    output_dir = tmp_path / "audit"

    summary = candidate_audit.audit_font_candidates(
        [_source("present", "example", "regular", ecosystem_id="example")],
        tmp_path,
        ["A"],
        output_dir,
        preview_characters=["A"] * 8,
    )

    assert summary["accepted_count"] == 1
    assert summary["rejected_count"] == 0
    record = summary["records"][0]
    assert len(record["font_sha256"]) == 64
    assert record["missing_count"] == 0
    assert record["render_error"] is None
    assert record["accepted"] is True
    assert (output_dir / "candidate_preview_grid.png").is_file()
    assert json.loads((output_dir / "candidate_audit_summary.json").read_text(encoding="utf-8")) == summary


def test_audit_font_candidates_omits_preview_grid_when_every_candidate_fails(tmp_path):
    output_dir = tmp_path / "audit"
    output_dir.mkdir()
    stale_grid = output_dir / "candidate_preview_grid.png"
    stale_grid.write_bytes(b"stale preview")

    summary = candidate_audit.audit_font_candidates(
        [_source("absent", "example", "regular")],
        tmp_path,
        ["A"],
        output_dir,
        preview_characters=["A"] * 8,
    )

    assert summary["accepted_count"] == 0
    assert not stale_grid.exists()
    failures = json.loads((output_dir / "candidate_audit_failures.json").read_text(encoding="utf-8"))
    assert failures == summary["records"]


def test_audit_font_candidates_rejects_non_string_local_path_without_stopping(tmp_path):
    invalid_source = FontSource(
        font_id="invalid_path",
        display_name="Invalid path",
        version="1.0",
        source_url="https://example.com/font.ttf",
        license_id="OFL-1.1",
        license_url="https://example.com/OFL.txt",
        local_path=None,
        family_id="example",
        category="regular",
        variant_role="regular",
        ecosystem_id="example",
        script_class="regular",
        style_role="text",
    )

    summary = candidate_audit.audit_font_candidates(
        [invalid_source],
        tmp_path,
        ["A"],
        tmp_path / "audit",
        preview_characters=["A"] * 8,
    )

    assert summary["rejected_count"] == 1
    assert summary["records"][0]["file_error"]
    assert summary["records"][0]["accepted"] is False


def test_audit_font_candidates_rejects_invalid_preview_character_list(tmp_path):
    with pytest.raises(ValueError, match="8"):
        candidate_audit.audit_font_candidates(
            [],
            tmp_path,
            ["A"],
            tmp_path / "audit",
            preview_characters=["A"] * 7,
        )


def test_audit_font_candidates_cli_writes_auditable_outputs(tmp_path):
    from test_font_files import _build_test_font

    font_path = tmp_path / "fonts" / "present.ttf"
    font_path.parent.mkdir()
    _build_test_font(font_path)
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """fonts:
  - font_id: present
    display_name: Present
    version: '1.0'
    source_url: https://example.com/present.ttf
    license_id: OFL-1.1
    license_url: https://example.com/OFL.txt
    local_path: fonts/present.ttf
    family_id: example
    category: regular
    variant_role: regular
    ecosystem_id: example
    script_class: regular
    style_role: text
""",
        encoding="utf-8",
    )
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("A\n", encoding="utf-8")
    output_dir = tmp_path / "audit"
    script_path = Path(__file__).parents[1] / "scripts" / "audit_font_candidates.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--sources",
            str(sources_path),
            "--characters",
            str(characters_path),
            "--font-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--preview-characters",
            "AAAAAAAA",
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    assert completed.returncode == 0, completed.stderr
    assert "accepted=1" in completed.stdout
    assert (output_dir / "candidate_audit_summary.json").is_file()


def test_audit_font_candidates_cli_returns_zero_for_rejected_candidate(tmp_path, monkeypatch, capsys):
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        """fonts:
  - font_id: absent
    display_name: Absent
    version: '1.0'
    source_url: https://example.com/absent.ttf
    license_id: OFL-1.1
    license_url: https://example.com/OFL.txt
    local_path: fonts/absent.ttf
    family_id: example
    category: regular
    variant_role: regular
    ecosystem_id: example
    script_class: regular
    style_role: text
""",
        encoding="utf-8",
    )
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("A\n", encoding="utf-8")
    output_dir = tmp_path / "audit"
    script_path = Path(__file__).parents[1] / "scripts" / "audit_font_candidates.py"
    spec = importlib.util.spec_from_file_location("audit_font_candidates_cli", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script_path),
            "--sources",
            str(sources_path),
            "--characters",
            str(characters_path),
            "--font-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
            "--preview-characters",
            "AAAAAAAA",
        ],
    )

    module.main()

    assert "accepted=0" in capsys.readouterr().out
    assert (output_dir / "candidate_audit_failures.json").is_file()
