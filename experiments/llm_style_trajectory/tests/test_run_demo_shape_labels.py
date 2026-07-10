import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from run_demo import relabel_variants_for_modifier_context


def test_shape_compare_labels_use_shape_emphasis():
    summaries = [
        {"style_modifiers": {"connection_preference": "weak", "shape_emphasis": "normal"}},
        {"style_modifiers": {"connection_preference": "weak", "shape_emphasis": "flatter"}},
        {"style_modifiers": {"connection_preference": "weak", "shape_emphasis": "wider"}},
    ]
    variants = [("weak", object()), ("weak", object()), ("weak", object())]

    relabeled = relabel_variants_for_modifier_context(
        summaries,
        variants,
        modifier_key="shape_emphasis",
        default_label="normal",
    )

    assert [label for label, _ in relabeled] == ["normal", "flatter", "wider"]
