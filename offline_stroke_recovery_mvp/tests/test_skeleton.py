from pathlib import Path
import sys

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from skeleton import numpy_skeletonize, ridge_skeleton, topology_metrics


def test_ridge_skeleton_returns_nonempty_centerline():
    mask = np.zeros((16, 16), dtype=bool)
    mask[4:12, 6:10] = True
    skel = ridge_skeleton(mask)
    assert skel.dtype == np.bool_
    assert skel.sum() > 0


def test_topology_metrics_reports_endpoints():
    skel = np.zeros((16, 16), dtype=bool)
    skel[8, 3:13] = True
    metrics = topology_metrics(skel)
    assert metrics["endpoint_count"] == 2


def test_numpy_skeletonize_preserves_horizontal_stroke():
    mask = np.zeros((16, 16), dtype=bool)
    mask[7:10, 2:14] = True
    skel = numpy_skeletonize(mask)
    assert skel.dtype == np.bool_
    assert skel[8].sum() >= 6
    assert topology_metrics(skel)["endpoint_count"] == 2


def test_numpy_skeletonize_keeps_t_junction_branching():
    mask = np.zeros((16, 16), dtype=bool)
    mask[8, 3:13] = True
    mask[4:9, 8:11] = True
    skel = numpy_skeletonize(mask)
    metrics = topology_metrics(skel)
    assert metrics["branch_point_count"] >= 1
    assert metrics["endpoint_count"] >= 3
