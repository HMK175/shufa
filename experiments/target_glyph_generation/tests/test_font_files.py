from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from target_glyph_generation.font_files import find_missing_characters, sha256_file


def _build_test_font(path: Path) -> None:
    font_builder = FontBuilder(1000, isTTF=True)
    glyph_order = [".notdef", "A", "uni4E00"]
    pen = TTGlyphPen(None)
    pen.moveTo((100, 100))
    pen.lineTo((900, 100))
    pen.lineTo((900, 900))
    pen.lineTo((100, 900))
    pen.closePath()
    glyphs = {".notdef": TTGlyphPen(None).glyph(), "A": pen.glyph(), "uni4E00": pen.glyph()}
    font_builder.setupGlyphOrder(glyph_order)
    font_builder.setupCharacterMap({ord("A"): "A", ord("一"): "uni4E00"})
    font_builder.setupGlyf(glyphs)
    font_builder.setupHorizontalMetrics({name: (600, 0) for name in glyph_order})
    font_builder.setupHorizontalHeader(ascent=800, descent=-200)
    font_builder.setupNameTable({"familyName": "Test Font", "styleName": "Regular"})
    font_builder.setupOS2()
    font_builder.setupPost()
    font_builder.setupMaxp()
    font_builder.save(path)


def test_find_missing_characters_uses_the_font_cmap(tmp_path: Path):
    font_path = tmp_path / "test.ttf"
    _build_test_font(font_path)

    assert find_missing_characters(font_path, ["A", "一", "二"]) == ["二"]


def test_sha256_file_is_deterministic_and_uses_hex_digest(tmp_path: Path):
    path = tmp_path / "payload.bin"
    path.write_bytes(b"font-provenance")

    assert sha256_file(path) == sha256_file(path)
    assert len(sha256_file(path)) == 64
