"""Access Make Me a Hanzi structured glyph medians for the experiment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class GlyphKnowledge:
    char: str
    strokes: list[str]
    medians: list[np.ndarray]

    @property
    def stroke_count(self) -> int:
        return len(self.medians)


class MakeMeAHanziKnowledge:
    def __init__(self, graphics_path: Path | str):
        self.graphics_path = Path(graphics_path)
        if not self.graphics_path.exists():
            raise FileNotFoundError(f"makemeahanzi graphics.txt not found: {self.graphics_path}")

    def get_glyph(self, char: str) -> GlyphKnowledge:
        for line in self.graphics_path.open(encoding="utf-8"):
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("character") != char:
                continue
            medians = [np.asarray(points, dtype=float) for points in item.get("medians", [])]
            medians = [points for points in medians if points.ndim == 2 and points.shape[1] == 2 and len(points) > 0]
            return GlyphKnowledge(
                char=char,
                strokes=[str(path_text) for path_text in item.get("strokes", [])],
                medians=medians,
            )
        raise KeyError(f"Character not found in makemeahanzi graphics: {char}")
