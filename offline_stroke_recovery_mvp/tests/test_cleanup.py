from pathlib import Path
import sys

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from cleanup import remove_small_components, prune_short_spurs


def test_remove_small_components_keeps_main_component():
    skel = np.zeros((20, 20), dtype=bool)
    skel[10, 5:15] = True
    skel[1, 1] = True
    cleaned, removed = remove_small_components(skel, min_component_pixels=3)
    assert removed == 1
    assert cleaned[10, 8]
    assert not cleaned[1, 1]


def test_prune_short_spurs_removes_branch_stub():
    skel = np.zeros((20, 20), dtype=bool)
    skel[10, 4:16] = True
    skel[8:11, 10] = True
    cleaned, pruned = prune_short_spurs(skel, max_length=2)
    assert pruned >= 1
    assert cleaned[10, 10]
    assert not cleaned[8, 10]


def test_prune_short_spurs_removes_staircase_side_stub():
    skel = np.zeros((8, 8), dtype=bool)
    skel[0:5, 2] = True
    skel[2, 1] = True

    cleaned, pruned = prune_short_spurs(skel, max_length=1)

    assert pruned >= 1
    assert cleaned[0, 2]
    assert cleaned[1, 2]
    assert cleaned[2, 2]
    assert cleaned[3, 2]
    assert cleaned[4, 2]
    assert not cleaned[2, 1]


def test_remove_small_components_keeps_one_tied_largest_component():
    skel = np.zeros((12, 12), dtype=bool)
    skel[1, 1:3] = True
    skel[7, 7:9] = True
    cleaned, removed = remove_small_components(skel, min_component_pixels=3)
    assert removed == 1
    assert cleaned[1, 1]
    assert cleaned[1, 2]
    assert not cleaned[7, 7]
    assert not cleaned[7, 8]
