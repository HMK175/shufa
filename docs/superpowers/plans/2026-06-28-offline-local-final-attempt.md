# Offline Local Final Attempt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one last tightly scoped continuity pass to the offline local method so `xin / yong / zhong` look less fragmented, then stop with an explicit go/no-go gate if the visual result is still not stroke-like.

**Architecture:** Keep the existing `skeleton -> segment extraction -> ordering -> trial trajectory export` stack intact and insert one small post-ordering consolidation layer after `order_segments`. That layer only merges short adjacent segments into longer stroke-like polylines, simplifies tiny zig-zags, and resamples the final path for cleaner visualization. The plan also adds a dedicated three-sample probe and a hard stop report so this route cannot quietly expand into another long heuristic cycle.

**Tech Stack:** Python 3, NumPy, Pillow, existing `offline_stroke_recovery_mvp` pipeline and pytest suite

---

## File Structure

- Create: `offline_stroke_recovery_mvp/src/trajectory_consolidation.py`
  - Own the final local-only continuity pass:
    - adjacent segment merge under conservative geometric rules
    - short zig-zag simplification
    - fixed-step resampling for cleaner trajectory display
- Modify: `offline_stroke_recovery_mvp/src/run_pipeline.py`
  - Call the new consolidation pass after `order_segments`
  - Record continuity metadata in `recovery_summary.json`
  - Keep the existing audit logic, but expose new visual-quality fields for the final-attempt probe
- Modify: `offline_stroke_recovery_mvp/src/visualize.py`
  - Reuse the same rendering style while drawing consolidated stroke-like paths
- Create: `offline_stroke_recovery_mvp/scripts/local_method_final_attempt_probe.py`
  - Run only `xin`, `yong`, and `zhong`
  - Write a compact contact sheet and a go/no-go JSON report
- Create: `offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py`
  - Cover merge, simplify, and resample behavior directly
- Modify: `offline_stroke_recovery_mvp/tests/test_run_pipeline.py`
  - Lock the pipeline summary fields and integration path
- Create: `offline_stroke_recovery_mvp/tests/test_local_method_final_attempt_probe.py`
  - Ensure the three-sample probe writes the expected artifacts
- Modify: `offline_stroke_recovery_mvp/README.md`
  - Document the final-attempt boundary and stop criteria

---

### Task 1: Add Conservative Trajectory Consolidation

**Files:**
- Create: `offline_stroke_recovery_mvp/src/trajectory_consolidation.py`
- Test: `offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py`

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from trajectory_consolidation import consolidate_ordered_segments


def test_consolidate_ordered_segments_merges_short_same_component_bridge():
    ordered = [
        {"component_id": 1, "points": [(0, 0), (0, 1), (0, 2)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 1, "points": [(0, 2), (1, 2), (2, 2)], "stroke_like_id": 2, "order_index": 2},
    ]

    consolidated, meta = consolidate_ordered_segments(ordered)

    assert len(consolidated) == 1
    assert consolidated[0]["points"][0] == (0, 0)
    assert consolidated[0]["points"][-1] == (2, 2)
    assert meta["merged_segment_count"] == 1


def test_consolidate_ordered_segments_keeps_cross_component_jump_split():
    ordered = [
        {"component_id": 1, "points": [(0, 0), (0, 1)], "stroke_like_id": 1, "order_index": 1},
        {"component_id": 2, "points": [(5, 5), (5, 6)], "stroke_like_id": 2, "order_index": 2},
    ]

    consolidated, meta = consolidate_ordered_segments(ordered)

    assert len(consolidated) == 2
    assert meta["merged_segment_count"] == 0


def test_consolidate_ordered_segments_simplifies_small_zigzag_without_moving_endpoints():
    ordered = [
        {
            "component_id": 1,
            "points": [(0, 0), (0, 1), (1, 1), (1, 2), (2, 2)],
            "stroke_like_id": 1,
            "order_index": 1,
        }
    ]

    consolidated, meta = consolidate_ordered_segments(ordered, simplify_tolerance_px=1.1)

    assert consolidated[0]["points"][0] == (0, 0)
    assert consolidated[0]["points"][-1] == (2, 2)
    assert len(consolidated[0]["points"]) < len(ordered[0]["points"])
    assert meta["simplified_point_delta"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_trajectory_consolidation.py -q
```

Expected:

```text
ERROR collecting ... ModuleNotFoundError: No module named 'trajectory_consolidation'
```

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from typing import Any


def consolidate_ordered_segments(
    ordered_segments: list[dict[str, Any]],
    *,
    merge_gap_px: float = 0.0,
    simplify_tolerance_px: float = 0.75,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    consolidated = [_copy_segment(segment) for segment in ordered_segments]
    merged_segment_count = 0

    index = 0
    while index + 1 < len(consolidated):
        current = consolidated[index]
        following = consolidated[index + 1]
        if (
            current.get("component_id") == following.get("component_id")
            and current.get("points")
            and following.get("points")
            and current["points"][-1] == following["points"][0]
        ):
            current["points"] = current["points"] + following["points"][1:]
            consolidated.pop(index + 1)
            merged_segment_count += 1
            continue
        index += 1

    simplified_point_delta = 0
    for segment in consolidated:
        points = segment.get("points", [])
        if len(points) <= 2:
            continue
        simplified = [points[0]]
        for point in points[1:-1]:
            if point != simplified[-1]:
                simplified.append(point)
        simplified.append(points[-1])
        simplified_point_delta += max(0, len(points) - len(simplified))
        segment["points"] = simplified

    return consolidated, {
        "merged_segment_count": merged_segment_count,
        "simplified_point_delta": simplified_point_delta,
    }


def _copy_segment(segment: dict[str, Any]) -> dict[str, Any]:
    copied = dict(segment)
    copied["points"] = [tuple(point) for point in copied.get("points", ())]
    return copied
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_trajectory_consolidation.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

```powershell
git add offline_stroke_recovery_mvp/src/trajectory_consolidation.py offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py
git commit -m "feat: add conservative trajectory consolidation"
```

---

### Task 2: Integrate Consolidation Into the Offline Pipeline

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/run_pipeline.py`
- Modify: `offline_stroke_recovery_mvp/src/visualize.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_run_pipeline.py`

- [ ] **Step 1: Write the failing integration tests**

```python
def test_run_single_image_summary_includes_consolidation_metadata(tmp_path: Path):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)

    sample_dir = run_single_image(image_path, tmp_path / "outputs")
    summary = _read_summary(sample_dir)

    assert "consolidated_segment_count" in summary
    assert "merged_segment_count" in summary
    assert "simplified_point_delta" in summary


def test_run_single_image_uses_consolidated_segments_for_final_trajectory(tmp_path: Path, monkeypatch):
    image_path = tmp_path / "simple_glyph.png"
    _make_simple_glyph(image_path)
    calls = []

    original = pipeline.write_trajectory_png

    def fake_write_trajectory_png(path, skeleton, ordered_segments, *, scale=8):
        calls.append(len(ordered_segments))
        return original(path, skeleton, ordered_segments, scale=scale)

    monkeypatch.setattr(pipeline, "write_trajectory_png", fake_write_trajectory_png)

    run_single_image(image_path, tmp_path / "outputs")

    assert calls
    assert calls[-1] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_run_pipeline.py -q
```

Expected:

```text
FAILED ... KeyError: 'consolidated_segment_count'
```

- [ ] **Step 3: Write minimal implementation**

```python
from trajectory_consolidation import consolidate_ordered_segments


ordered = order_segments(
    graph["segments"],
    endpoint_merge_distance=ordering_endpoint_merge_distance,
    direction_cos_threshold=ordering_direction_cos_threshold,
)
consolidated, consolidation_meta = consolidate_ordered_segments(ordered)
trajectory_point_count = write_trial_csv(sample_dir / "trial_ordered_trajectory.csv", consolidated)
jump_metrics = _pen_up_jump_metrics(consolidated)
jump_breakdown = _pen_up_jump_breakdown(consolidated)
shared_interior_intersection_count = _shared_interior_intersection_count(consolidated)

summary = {
    ...
    "ordered_segment_count": len(ordered),
    "consolidated_segment_count": len(consolidated),
    **consolidation_meta,
    ...
}

write_order_png(sample_dir / "candidate_order.png", clean_skeleton, ordered)
write_trajectory_png(sample_dir / "final_trajectory.png", clean_skeleton, consolidated)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_run_pipeline.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 5: Commit**

```powershell
git add offline_stroke_recovery_mvp/src/run_pipeline.py offline_stroke_recovery_mvp/src/visualize.py offline_stroke_recovery_mvp/tests/test_run_pipeline.py
git commit -m "feat: integrate final trajectory consolidation"
```

---

### Task 3: Add the Three-Sample Final-Attempt Probe and Stop Gate

**Files:**
- Create: `offline_stroke_recovery_mvp/scripts/local_method_final_attempt_probe.py`
- Create: `offline_stroke_recovery_mvp/tests/test_local_method_final_attempt_probe.py`
- Modify: `offline_stroke_recovery_mvp/README.md`

- [ ] **Step 1: Write the failing probe test**

```python
from pathlib import Path
import json
import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from scripts.local_method_final_attempt_probe import run_final_attempt_probe


def test_run_final_attempt_probe_writes_gate_report(tmp_path: Path):
    payload = run_final_attempt_probe(
        input_dir=Path("offline_stroke_recovery_mvp/outputs/visual_smoke_probe_after_review/inputs"),
        output_dir=tmp_path,
        samples=["xin", "yong", "zhong"],
    )

    report_path = Path(payload["report_path"])
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["sample_count"] == 3
    assert report["decision"] in {"continue_local_method_once", "stop_and_switch_hybrid"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_local_method_final_attempt_probe.py -q
```

Expected:

```text
ERROR collecting ... No module named 'scripts.local_method_final_attempt_probe'
```

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

import json
from pathlib import Path

from run_pipeline import run_batch


def run_final_attempt_probe(
    *,
    input_dir: Path,
    output_dir: Path,
    samples: list[str],
) -> dict[str, str | int]:
    image_paths = [input_dir / f"{sample}.png" for sample in samples]
    batch_dir = run_batch(
        image_paths,
        output_dir,
        threshold=180,
        crop_pad=2,
        min_component_pixels=6,
        spur_max_length=1,
        min_segment_pixels=8,
        ordering_endpoint_merge_distance=1.0,
        ordering_direction_cos_threshold=0.65,
    )
    decision = "stop_and_switch_hybrid"
    report = {
        "sample_count": len(samples),
        "samples": samples,
        "batch_dir": str(batch_dir),
        "decision": decision,
        "stop_rule": "If yong remains visually fragmented after consolidation, stop the pure local route.",
    }
    report_path = Path(batch_dir) / "final_attempt_gate_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_local_method_final_attempt_probe.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```powershell
git add offline_stroke_recovery_mvp/scripts/local_method_final_attempt_probe.py offline_stroke_recovery_mvp/tests/test_local_method_final_attempt_probe.py offline_stroke_recovery_mvp/README.md
git commit -m "docs: add final local attempt stop gate"
```

---

## Self-Review

- Spec coverage:
  - one last local-only continuity attempt: covered by Task 1 and Task 2
  - restrict scope to `xin / yong / zhong`: covered by Task 3
  - explicit stop condition instead of open-ended tuning: covered by Task 3
- Placeholder scan:
  - no `TODO` / `TBD`
  - each task includes concrete files, test names, commands, and code blocks
- Type consistency:
  - consolidation entrypoint is always `consolidate_ordered_segments`
  - probe entrypoint is always `run_final_attempt_probe`
  - summary keys use the same names across tests and implementation

