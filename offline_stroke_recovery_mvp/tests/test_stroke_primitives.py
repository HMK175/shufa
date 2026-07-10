from pathlib import Path
import sys

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from stroke_primitives import (
    StrokePrimitive,
    StrokePrimitiveLibrary,
    compose_hengzhe_primitive,
    normalize_stroke_primitive,
    resample_relative_widths,
    reverse_stroke_primitive,
    transfer_relative_width_profile,
)


def test_normalize_stroke_primitive_is_translation_and_scale_invariant():
    first = normalize_stroke_primitive(
        [(0.0, 0.0), (0.0, 5.0), (0.0, 10.0)],
        [2.0, 4.0, 2.0],
        kind="heng",
        start_role="free",
        end_role="free",
        source_sample="yi",
    )
    second = normalize_stroke_primitive(
        [(7.0, 3.0), (7.0, 13.0), (7.0, 23.0)],
        [4.0, 8.0, 4.0],
        kind="heng",
        start_role="free",
        end_role="free",
        source_sample="yi_scaled",
    )

    assert np.allclose(first.normalized_points, second.normalized_points)
    assert np.allclose(first.relative_widths, second.relative_widths)


def test_resample_relative_widths_preserves_endpoint_order():
    result = resample_relative_widths([0.5, 1.0, 1.5], 7)

    assert len(result) == 7
    assert result[0] == 0.5
    assert result[-1] == 1.5
    assert all(left <= right for left, right in zip(result, result[1:]))


def test_reverse_stroke_primitive_swaps_endpoint_roles():
    primitive = StrokePrimitive(
        kind="gou",
        normalized_points=((0.0, 0.0), (0.5, 0.6), (1.0, 0.3)),
        relative_widths=(1.2, 1.0, 0.0),
        start_role="attached",
        end_role="pointed",
        corner_fraction=0.7,
        source_sample="xin",
    )

    reversed_primitive = reverse_stroke_primitive(primitive)

    assert reversed_primitive.start_role == "pointed"
    assert reversed_primitive.end_role == "attached"
    assert reversed_primitive.relative_widths == (0.0, 1.0, 1.2)
    assert np.isclose(reversed_primitive.corner_fraction, 0.3)


def test_compose_hengzhe_primitive_contains_one_corner():
    heng = normalize_stroke_primitive(
        [(0.0, 0.0), (0.0, 10.0)],
        [0.8, 1.2],
        kind="heng",
        start_role="free",
        end_role="turn",
        source_sample="yi",
    )
    shu = normalize_stroke_primitive(
        [(0.0, 0.0), (10.0, 0.0)],
        [1.1, 0.9],
        kind="shu",
        start_role="turn",
        end_role="attached",
        source_sample="shi",
    )

    primitive = compose_hengzhe_primitive(heng, shu, corner_fraction=0.6)

    assert primitive.kind == "hengzhe"
    assert primitive.start_role == "free"
    assert primitive.end_role == "attached"
    assert primitive.corner_fraction == 0.6
    assert primitive.normalized_points[0] == (0.0, 0.0)
    assert primitive.normalized_points[-1] == (1.0, 1.0)
    corner_index = int(round((len(primitive.normalized_points) - 1) * 0.6))
    corner = primitive.normalized_points[corner_index]
    assert corner[0] <= 0.05
    assert corner[1] >= 0.95


def test_transfer_relative_width_profile_preserves_target_median_width():
    primitive = StrokePrimitive(
        kind="heng",
        normalized_points=((0.0, 0.0), (0.0, 0.5), (0.0, 1.0)),
        relative_widths=(0.5, 1.0, 1.5),
        start_role="free",
        end_role="free",
        source_sample="yi",
    )

    transferred = transfer_relative_width_profile(
        [10.0, 10.0, 10.0, 10.0, 10.0],
        primitive,
        blend=1.0,
    )

    assert np.isclose(np.median(transferred), 10.0)
    assert transferred[0] < transferred[len(transferred) // 2] < transferred[-1]


def test_stroke_primitive_library_registers_by_kind():
    library = StrokePrimitiveLibrary()
    primitive = StrokePrimitive(
        kind="heng",
        normalized_points=((0.0, 0.0), (0.0, 1.0)),
        relative_widths=(1.0, 1.0),
        start_role="free",
        end_role="free",
        source_sample="yi",
    )

    library.register(primitive)

    assert library.get("heng") == primitive
    assert library.get("missing") is None
