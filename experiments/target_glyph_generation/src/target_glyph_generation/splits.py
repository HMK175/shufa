"""固定且无泄漏的字符划分。"""

import random


def split_characters(characters: list[str], seed: int) -> dict[str, list[str]]:
    """以固定随机种子将 1,000 个字符划分为 800/100/100。"""
    if len(characters) != 1000 or len(set(characters)) != 1000:
        raise ValueError("字符池必须恰好包含 1,000 个不重复字符")
    ordered = sorted(characters)
    random.Random(seed).shuffle(ordered)
    return {
        "train": ordered[:800],
        "validation": ordered[800:900],
        "test": ordered[900:],
    }


def split_styles(style_ids: list[str], seed: int) -> dict[str, list[str]]:
    """以固定随机种子将 28 个有效风格划分为 20/3/5。"""
    if len(style_ids) != 28 or len(set(style_ids)) != 28:
        raise ValueError("风格池必须恰好包含 28 个不重复风格")
    ordered = sorted(style_ids)
    random.Random(seed).shuffle(ordered)
    return {
        "train": ordered[:20],
        "validation": ordered[20:23],
        "test": ordered[23:],
    }
