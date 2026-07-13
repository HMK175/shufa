"""本地字体文件的完整性与字符覆盖率校验。"""

from hashlib import sha256
from pathlib import Path

from fontTools.ttLib import TTFont


def sha256_file(path: Path) -> str:
    """返回文件的 SHA-256 十六进制摘要。"""
    digest = sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_missing_characters(font_path: Path, characters: list[str]) -> list[str]:
    """返回未出现在字体 Unicode cmap 中的字符，顺序与输入一致。"""
    with TTFont(font_path, lazy=True) as font:
        cmap = font.getBestCmap() or {}
    return [character for character in characters if ord(character) not in cmap]
