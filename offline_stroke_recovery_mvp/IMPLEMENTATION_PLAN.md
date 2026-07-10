# Offline Stroke Recovery MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone offline pipeline that turns a single-character binary image into a candidate writable trajectory with debug figures and manual-audit outputs.

**Architecture:** The implementation starts from a deterministic graph pipeline. It reuses local prototype logic for skeletonization, cleanup, segment extraction, and candidate ordering, but moves them into a clean standalone package under `offline_stroke_recovery_mvp/`. An external comparison hook for CalliRewrite is deferred until the deterministic route is stable.

**Tech Stack:** Python, NumPy, Matplotlib, Pillow, pytest, optional `scikit-image`

---

## File map

- Create: `offline_stroke_recovery_mvp/configs/sample_chars.json`
- Create: `offline_stroke_recovery_mvp/src/preprocess.py`
- Create: `offline_stroke_recovery_mvp/src/skeleton.py`
- Create: `offline_stroke_recovery_mvp/src/cleanup.py`
- Create: `offline_stroke_recovery_mvp/src/graph_extract.py`
- Create: `offline_stroke_recovery_mvp/src/ordering.py`
- Create: `offline_stroke_recovery_mvp/src/exporters.py`
- Create: `offline_stroke_recovery_mvp/src/visualize.py`
- Create: `offline_stroke_recovery_mvp/src/run_pipeline.py`
- Create: `offline_stroke_recovery_mvp/tests/test_preprocess.py`
- Create: `offline_stroke_recovery_mvp/tests/test_skeleton.py`
- Create: `offline_stroke_recovery_mvp/tests/test_cleanup.py`
- Create: `offline_stroke_recovery_mvp/tests/test_graph_extract.py`
- Create: `offline_stroke_recovery_mvp/tests/test_ordering.py`
- Create: `offline_stroke_recovery_mvp/tests/test_run_pipeline.py`

## External references to reuse during implementation

- Read and selectively port from:
  - `experiments/llm_style_trajectory/src/font_outline_basis_feasibility.py`
  - `experiments/llm_style_trajectory/src/font_skeleton_cleanup_prototype.py`
  - `experiments/llm_style_trajectory/src/font_skeleton_path_extraction_prototype.py`
  - `experiments/llm_style_trajectory/src/font_skeleton_stroke_ordering_prototype.py`

Do not modify:

- `code/legacy_image_skeleton_rl_route/scripts/stroke.py`
- `code/legacy_image_skeleton_rl_route/scripts/pipeline.py`

---

### Task 1: Scaffold the standalone package

**Files:**
- Create: `offline_stroke_recovery_mvp/configs/sample_chars.json`
- Create: `offline_stroke_recovery_mvp/src/run_pipeline.py`
- Create: `offline_stroke_recovery_mvp/tests/test_run_pipeline.py`

- [ ] **Step 1: Write the failing smoke test**

```python
from pathlib import Path

from run_pipeline import build_output_dir


def test_build_output_dir_uses_timestamped_batch_name(tmp_path: Path):
    out_dir = build_output_dir(tmp_path, prefix="batch")
    assert out_dir.parent == tmp_path
    assert out_dir.name.startswith("batch_")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_run_pipeline.py::test_build_output_dir_uses_timestamped_batch_name -q
```

Expected:

- import failure because `run_pipeline.py` does not exist yet

- [ ] **Step 3: Write the minimal implementation**

```python
from datetime import datetime
from pathlib import Path


def build_output_dir(base_dir: Path, prefix: str = "batch") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"{prefix}_{stamp}"
```

- [ ] **Step 4: Add a small sample config**

```json
{
  "samples": [
    {"char": "人"},
    {"char": "山"},
    {"char": "中"},
    {"char": "永"}
  ]
}
```

- [ ] **Step 5: Run the smoke test**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_run_pipeline.py::test_build_output_dir_uses_timestamped_batch_name -q
```

Expected:

- `1 passed`

---

### Task 2: Implement image loading and binary normalization

**Files:**
- Create: `offline_stroke_recovery_mvp/src/preprocess.py`
- Create: `offline_stroke_recovery_mvp/tests/test_preprocess.py`

- [ ] **Step 1: Write the failing preprocess tests**

```python
import numpy as np

from preprocess import ensure_foreground_is_true, crop_to_foreground


def test_ensure_foreground_is_true_converts_dark_pixels_to_true():
    arr = np.array([[255, 0], [255, 255]], dtype=np.uint8)
    mask = ensure_foreground_is_true(arr, threshold=200)
    assert mask.dtype == np.bool_
    assert mask[0, 1]
    assert not mask[0, 0]


def test_crop_to_foreground_returns_tight_bbox():
    mask = np.zeros((8, 8), dtype=bool)
    mask[2:6, 3:5] = True
    cropped, bbox = crop_to_foreground(mask, pad=0)
    assert cropped.shape == (4, 2)
    assert bbox == (2, 3, 5, 4)
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_preprocess.py -q
```

- [ ] **Step 3: Write minimal preprocessing code**

```python
import numpy as np


def ensure_foreground_is_true(image: np.ndarray, threshold: int = 200) -> np.ndarray:
    arr = np.asarray(image)
    return arr < threshold


def crop_to_foreground(mask: np.ndarray, pad: int = 2):
    ys, xs = np.nonzero(mask)
    y0 = max(int(ys.min()) - pad, 0)
    y1 = min(int(ys.max()) + pad + 1, mask.shape[0])
    x0 = max(int(xs.min()) - pad, 0)
    x1 = min(int(xs.max()) + pad + 1, mask.shape[1])
    return mask[y0:y1, x0:x1], (y0, x0, y1 - 1, x1 - 1)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_preprocess.py -q
```

Expected:

- preprocess tests pass

---

### Task 3: Implement skeleton extraction with optional `skimage`

**Files:**
- Create: `offline_stroke_recovery_mvp/src/skeleton.py`
- Create: `offline_stroke_recovery_mvp/tests/test_skeleton.py`

- [ ] **Step 1: Write the failing skeleton tests**

```python
import numpy as np

from skeleton import ridge_skeleton, topology_metrics


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
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_skeleton.py -q
```

- [ ] **Step 3: Implement minimal skeleton helpers**

```python
import numpy as np


def ridge_skeleton(mask: np.ndarray) -> np.ndarray:
    grid = np.asarray(mask, dtype=bool)
    out = np.zeros_like(grid)
    for y in range(grid.shape[0]):
        xs = np.flatnonzero(grid[y])
        if len(xs):
            out[y, int(xs[len(xs) // 2])] = True
    return out & grid


def topology_metrics(skeleton: np.ndarray) -> dict[str, int]:
    skel = np.asarray(skeleton, dtype=bool)

    def neighbors(y: int, x: int) -> int:
        count = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < skel.shape[0] and 0 <= nx < skel.shape[1] and skel[ny, nx]:
                    count += 1
        return count

    endpoint_count = 0
    branch_count = 0
    for y, x in zip(*np.nonzero(skel)):
        deg = neighbors(int(y), int(x))
        if deg == 1:
            endpoint_count += 1
        elif deg >= 3:
            branch_count += 1
    return {
        "skeleton_pixel_count": int(skel.sum()),
        "endpoint_count": endpoint_count,
        "branch_point_count": branch_count,
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_skeleton.py -q
```

---

### Task 4: Port cleanup operators from the local prototypes

**Files:**
- Create: `offline_stroke_recovery_mvp/src/cleanup.py`
- Create: `offline_stroke_recovery_mvp/tests/test_cleanup.py`
- Read for reuse:
  `experiments/llm_style_trajectory/src/font_skeleton_cleanup_prototype.py`

- [ ] **Step 1: Write failing cleanup tests**

```python
import numpy as np

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
```

- [ ] **Step 2: Run tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_cleanup.py -q
```

- [ ] **Step 3: Port the minimal cleanup subset**

Implementation target:

- connected-component enumeration
- removal of tiny components
- endpoint tracing
- short-spur pruning

Keep function names simple:

```python
def remove_small_components(skeleton: np.ndarray, min_component_pixels: int): ...
def prune_short_spurs(skeleton: np.ndarray, max_length: int): ...
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_cleanup.py -q
```

Expected:

- cleanup tests pass

---

### Task 5: Extract graph segments from the cleaned skeleton

**Files:**
- Create: `offline_stroke_recovery_mvp/src/graph_extract.py`
- Create: `offline_stroke_recovery_mvp/tests/test_graph_extract.py`
- Read for reuse:
  `experiments/llm_style_trajectory/src/font_skeleton_path_extraction_prototype.py`

- [ ] **Step 1: Write the failing graph tests**

```python
import numpy as np

from graph_extract import extract_segments


def test_extract_segments_from_t_shape_returns_multiple_segments():
    skel = np.zeros((32, 32), dtype=bool)
    skel[16, 8:24] = True
    skel[8:17, 16] = True
    result = extract_segments(skel, min_segment_pixels=3)
    assert result["segment_count"] >= 2
    assert result["endpoint_count"] >= 3
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_graph_extract.py -q
```

- [ ] **Step 3: Port the segment extraction core**

Implementation target:

- identify nodes where degree is not 2
- trace paths between nodes
- drop very short segments
- record per-segment polyline length

Core shape:

```python
def extract_segments(skeleton: np.ndarray, min_segment_pixels: int = 4) -> dict:
    return {
        "segments": segments,
        "segment_count": len(segments),
        "endpoint_count": endpoint_count,
        "branch_point_count": branch_count,
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_graph_extract.py -q
```

---

### Task 6: Recover a conservative candidate writable order

**Files:**
- Create: `offline_stroke_recovery_mvp/src/ordering.py`
- Create: `offline_stroke_recovery_mvp/tests/test_ordering.py`
- Read for reuse:
  `experiments/llm_style_trajectory/src/font_skeleton_stroke_ordering_prototype.py`

- [ ] **Step 1: Write the failing ordering tests**

```python
from ordering import order_segments


def test_order_segments_prefers_longer_segment_first():
    segments = [
        {"segment_id": 1, "length_px": 5.0, "points": [(0, 0), (0, 5)]},
        {"segment_id": 2, "length_px": 12.0, "points": [(5, 0), (5, 12)]},
    ]
    ordered = order_segments(segments)
    assert ordered[0]["segment_id"] == 2
```

- [ ] **Step 2: Run tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_ordering.py -q
```

- [ ] **Step 3: Implement the first conservative ordering heuristic**

```python
def order_segments(segments):
    return sorted(
        segments,
        key=lambda item: (-float(item["length_px"]), item["points"][0][0], item["points"][0][1]),
    )
```

Then expand it with:

- component grouping
- endpoint-distance-based merge candidate selection
- direction compatibility check

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_ordering.py -q
```

---

### Task 7: Export trial outputs and debug figures

**Files:**
- Create: `offline_stroke_recovery_mvp/src/exporters.py`
- Create: `offline_stroke_recovery_mvp/src/visualize.py`
- Modify: `offline_stroke_recovery_mvp/src/run_pipeline.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_run_pipeline.py`

- [ ] **Step 1: Extend the failing pipeline test**

```python
from pathlib import Path

import numpy as np
from PIL import Image

from run_pipeline import run_single_image


def test_run_single_image_writes_trial_outputs(tmp_path: Path):
    img = np.full((64, 64), 255, dtype=np.uint8)
    img[16:48, 28:36] = 0
    image_path = tmp_path / "ren.png"
    Image.fromarray(img).save(image_path)

    sample_dir = run_single_image(image_path, tmp_path)
    assert (sample_dir / "trial_ordered_trajectory.csv").exists()
    assert (sample_dir / "recovery_summary.json").exists()
    assert (sample_dir / "candidate_order.png").exists()
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_run_pipeline.py::test_run_single_image_writes_trial_outputs -q
```

- [ ] **Step 3: Implement exporters**

Implementation target:

- `write_trial_csv(...)`
- `write_summary_json(...)`
- `write_manifest_csv(...)`

CSV rows should use fields like:

```python
["y", "x", "stroke_like_id", "point_index", "is_break", "order_index", "source"]
```

- [ ] **Step 4: Implement visual outputs**

Minimum files:

- `raw_skeleton.png`
- `clean_skeleton.png`
- `segments.png`
- `candidate_order.png`
- `final_trajectory.png`

- [ ] **Step 5: Run pipeline tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_run_pipeline.py -q
```

---

### Task 8: Add manual-audit labels and batch reporting

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/run_pipeline.py`
- Modify: `offline_stroke_recovery_mvp/src/exporters.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_run_pipeline.py`

- [ ] **Step 1: Add a failing audit-label test**

```python
def test_summary_contains_audit_status(tmp_path: Path):
    ...
    summary = json.loads((sample_dir / "recovery_summary.json").read_text(encoding="utf-8"))
    assert summary["audit_status"] in {
        "promising",
        "risky_needs_manual_check",
        "failed",
    }
```

- [ ] **Step 2: Implement deterministic first-pass status logic**

Suggested rule:

- `failed`
  - no segments
  - no trajectory points
- `risky_needs_manual_check`
  - multiple components
  - high branch count
  - many short segments
- `promising`
  - simple topology and non-empty ordered trajectory

- [ ] **Step 3: Emit a batch markdown report**

Minimum sections:

- samples processed
- topology summary table
- output file locations
- explicit reminder that visual inspection is required

- [ ] **Step 4: Run full MVP test subset**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests -q
```

Expected:

- all standalone MVP tests pass

---

### Task 9: Add external comparison hooks without wiring external code into the MVP

**Files:**
- Modify: `offline_stroke_recovery_mvp/ROUTE_SURVEY.md`
- Modify: `offline_stroke_recovery_mvp/DESIGN.md`
- Optional create later: `offline_stroke_recovery_mvp/callirewrite_notes.md`

- [ ] **Step 1: Document the external benchmark rule**

Document:

- `CalliRewrite` is the first public-code route to evaluate
- phase 1 does not vendor or modify its code
- comparison should happen on the same small sample set

- [ ] **Step 2: Capture concrete checkpoints**

Comparison questions:

1. Can CalliRewrite coarse extraction run on the four-sample set?
2. Does its stroke order look more plausible than the deterministic local route?
3. Are its dependencies practical enough for local reproduction?

- [ ] **Step 3: Record go / no-go decision criteria**

Go:

- reproducible locally
- small-sample outputs are visually better

No-go:

- environment too heavy
- checkpoints missing
- outputs hard to interpret or not clearly better

---

## Self-review

### Spec coverage

- standalone folder: covered
- geometry-first offline MVP: covered
- single-character binary input: covered
- skeleton / path / order / export / visualization: covered
- human visual audit gate: covered
- open-source-code preference: covered in Task 9 and `ROUTE_SURVEY.md`

### Placeholder scan

- no `TODO`
- no `TBD`
- no unnamed files
- no ambiguous output names

### Type consistency

Planned names stay consistent across tasks:

- `trial_ordered_trajectory.csv`
- `recovery_summary.json`
- `candidate_order.png`
- `order_segments`
- `extract_segments`

