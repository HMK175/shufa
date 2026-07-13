from PIL import Image

from target_glyph_generation.render import normalize_glyph_canvas, render_glyph


def test_normalize_glyph_canvas_returns_square_black_on_white_image():
    source = Image.new("L", (30, 10), color=255)
    source.putpixel((10, 4), 0)

    result = normalize_glyph_canvas(source, canvas_size=256)

    assert result.mode == "L"
    assert result.size == (256, 256)
    assert result.getpixel((0, 0)) == 255
    assert min(result.getdata()) == 0


def test_render_glyph_draws_a_nonempty_black_on_white_canvas(tmp_path):
    from test_font_files import _build_test_font

    font_path = tmp_path / "test.ttf"
    _build_test_font(font_path)

    result = render_glyph(font_path, "A", canvas_size=256)

    assert result.mode == "L"
    assert result.size == (256, 256)
    assert min(result.getdata()) == 0
