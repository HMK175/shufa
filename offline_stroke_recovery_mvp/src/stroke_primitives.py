"""Normalized stroke geometry and relative-width transfer helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


VALID_ENDPOINT_ROLES = {"free", "attached", "pointed", "turn"}
VALID_PRIMITIVE_KINDS = {"heng", "shu", "hengzhe", "gou"}


@dataclass(frozen=True)
class StrokePrimitive:
    kind: str
    normalized_points: tuple[tuple[float, float], ...]
    relative_widths: tuple[float, ...]
    start_role: str
    end_role: str
    corner_fraction: float | None = None
    source_sample: str = ""


class StrokePrimitiveLibrary:
    def __init__(self) -> None:
        self._items: dict[str, StrokePrimitive] = {}

    def register(self, primitive: StrokePrimitive) -> None:
        self._items[str(primitive.kind)] = primitive

    def get(self, kind: str) -> StrokePrimitive | None:
        return self._items.get(str(kind))

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._items))


def normalize_stroke_primitive(
    points: Sequence[tuple[float, float]],
    widths: Sequence[float],
    *,
    kind: str,
    start_role: str,
    end_role: str,
    corner_fraction: float | None = None,
    source_sample: str = "",
) -> StrokePrimitive:
    _validate_kind_and_roles(kind, start_role, end_role)
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2 or len(arr) < 2:
        raise ValueError("A stroke primitive needs at least two 2D points")

    deltas = np.diff(arr, axis=0)
    step_lengths = np.linalg.norm(deltas, axis=1)
    path_length = float(step_lengths.sum())
    if path_length <= 1e-9:
        raise ValueError("A stroke primitive needs non-zero path length")
    normalized = (arr - arr[0]) / path_length

    width_values = resample_relative_widths(widths, len(arr))
    width_arr = np.asarray([max(float(value), 0.0) for value in width_values], dtype=float)
    positive = width_arr[width_arr > 1e-9]
    reference = float(np.median(positive)) if positive.size else 1.0
    relative = width_arr / max(reference, 1e-9)

    return StrokePrimitive(
        kind=str(kind),
        normalized_points=tuple((float(y), float(x)) for y, x in normalized),
        relative_widths=tuple(float(value) for value in relative),
        start_role=str(start_role),
        end_role=str(end_role),
        corner_fraction=None if corner_fraction is None else float(corner_fraction),
        source_sample=str(source_sample),
    )


def resample_relative_widths(relative_widths: Sequence[float], count: int) -> list[float]:
    target_count = max(int(count), 0)
    if target_count == 0:
        return []
    values = np.asarray(list(relative_widths), dtype=float)
    if values.size == 0:
        return [1.0 for _ in range(target_count)]
    if values.size == 1:
        return [float(values[0]) for _ in range(target_count)]
    if target_count == 1:
        return [float(values[0])]
    source_positions = np.linspace(0.0, 1.0, int(values.size))
    target_positions = np.linspace(0.0, 1.0, target_count)
    return np.interp(target_positions, source_positions, values).astype(float).tolist()


def reverse_stroke_primitive(primitive: StrokePrimitive) -> StrokePrimitive:
    points = np.asarray(list(reversed(primitive.normalized_points)), dtype=float)
    points = points - points[0]
    return StrokePrimitive(
        kind=primitive.kind,
        normalized_points=tuple((float(y), float(x)) for y, x in points),
        relative_widths=tuple(reversed(primitive.relative_widths)),
        start_role=primitive.end_role,
        end_role=primitive.start_role,
        corner_fraction=(
            None
            if primitive.corner_fraction is None
            else float(1.0 - primitive.corner_fraction)
        ),
        source_sample=primitive.source_sample,
    )


def compose_hengzhe_primitive(
    heng: StrokePrimitive,
    shu: StrokePrimitive,
    *,
    corner_fraction: float,
    sample_count: int = 21,
) -> StrokePrimitive:
    if heng.kind != "heng" or shu.kind != "shu":
        raise ValueError("hengzhe composition requires heng and shu primitives")
    fraction = min(max(float(corner_fraction), 0.1), 0.9)
    count = max(int(sample_count), 5)
    corner_index = min(max(int(round((count - 1) * fraction)), 1), count - 2)
    horizontal_count = corner_index + 1
    vertical_count = count - corner_index

    horizontal_points = [(0.0, float(value)) for value in np.linspace(0.0, 1.0, horizontal_count)]
    vertical_points = [(float(value), 1.0) for value in np.linspace(0.0, 1.0, vertical_count)]
    points = horizontal_points + vertical_points[1:]

    horizontal_widths = resample_relative_widths(heng.relative_widths, horizontal_count)
    vertical_widths = resample_relative_widths(shu.relative_widths, vertical_count)
    corner_width = float(np.median([horizontal_widths[-1], vertical_widths[0]]))
    horizontal_widths[-1] = corner_width
    vertical_widths[0] = corner_width
    widths = horizontal_widths + vertical_widths[1:]
    width_reference = float(np.median(np.asarray(widths, dtype=float)))
    normalized_widths = [float(value) / max(width_reference, 1e-9) for value in widths]

    return StrokePrimitive(
        kind="hengzhe",
        normalized_points=tuple(points),
        relative_widths=tuple(normalized_widths),
        start_role=heng.start_role,
        end_role=shu.end_role,
        corner_fraction=fraction,
        source_sample="+".join(filter(None, (heng.source_sample, shu.source_sample))),
    )


def transfer_relative_width_profile(
    diameters: Sequence[float],
    primitive: StrokePrimitive,
    *,
    blend: float = 0.7,
) -> list[float]:
    return transfer_relative_width_factors(
        diameters,
        primitive.relative_widths,
        blend=blend,
    )


def transfer_relative_width_factors(
    diameters: Sequence[float],
    relative_widths: Sequence[float],
    *,
    blend: float = 0.7,
) -> list[float]:
    arr = np.asarray([max(float(value), 0.0) for value in diameters], dtype=float)
    if arr.size == 0:
        return []
    factors = np.asarray(resample_relative_widths(relative_widths, int(arr.size)), dtype=float)
    factor_positive = factors[factors > 1e-9]
    factor_reference = float(np.median(factor_positive)) if factor_positive.size else 1.0
    factors = factors / max(factor_reference, 1e-9)
    target_reference = float(np.median(arr))
    desired = factors * target_reference
    weight = min(max(float(blend), 0.0), 1.0)
    transferred = arr * (1.0 - weight) + desired * weight
    result_reference = float(np.median(transferred))
    if result_reference > 1e-9:
        transferred *= target_reference / result_reference
    return np.maximum(transferred, 0.0).astype(float).tolist()


def _validate_kind_and_roles(kind: str, start_role: str, end_role: str) -> None:
    if str(kind) not in VALID_PRIMITIVE_KINDS:
        raise ValueError(f"Unsupported primitive kind: {kind}")
    for role in (start_role, end_role):
        if str(role) not in VALID_ENDPOINT_ROLES:
            raise ValueError(f"Unsupported endpoint role: {role}")
