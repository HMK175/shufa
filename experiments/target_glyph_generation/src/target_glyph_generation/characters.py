"""字符池文件的读取与验证。"""

from pathlib import Path


def load_characters(path: Path) -> list[str]:
    """读取每行一个的字符池，拒绝空行、多字符行和重复字符。"""
    characters = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not characters or any(len(character) != 1 for character in characters):
        raise ValueError("字符池必须每行恰好一个非空字符")
    if len(characters) != len(set(characters)):
        raise ValueError("字符池不可包含重复字符")
    return characters
