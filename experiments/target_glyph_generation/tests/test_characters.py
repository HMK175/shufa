from pathlib import Path

from target_glyph_generation.characters import load_characters


def test_load_characters_returns_one_unique_character_per_nonempty_line(tmp_path: Path):
    path = tmp_path / "characters.txt"
    path.write_text("一\n乙\n二\n", encoding="utf-8")

    assert load_characters(path) == ["一", "乙", "二"]


def test_load_characters_ignores_comment_lines(tmp_path: Path):
    path = tmp_path / "characters.txt"
    path.write_text("# 来源说明\n一\n乙\n", encoding="utf-8")

    assert load_characters(path) == ["一", "乙"]
