# Prior-Guided Geometry Regularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a MakeMeAHanzi-guided geometry regularization pass to the offline `CalliRewrite + MMH regroup` route so real-sample `zhong / yong` trajectories become visually straighter without collapsing lead-in splits.

**Architecture:** Keep the existing `CalliRewrite coarse segments -> ordering -> MMH regroup -> consolidation -> visualization` stack intact. Insert one small pass inside the MMH-prior layer that reparameterizes each already-assigned grouped segment along its matched prior subpath, using the input foreground as a support gate and preserving per-segment boundaries.

**Tech Stack:** Python 3, NumPy, Pillow, existing `offline_stroke_recovery_mvp` pytest suite

---

## File Structure

- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py`
  - Add the prior-guided geometry regularization helper
  - Apply it after regrouping while preserving segment splits
  - Expose compact metadata about how many grouped segments were regularized
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
  - Carry the new prior-geometry metadata into `recovery_summary.json`
- Modify: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`
  - Add a synthetic failing test for single-segment wobble cleanup
  - Add a real `zhong` regression test for the bent top-right grouped segment
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`
  - Lock the new summary metadata at probe level

---

### Task 1: Add Prior-Guided Segment Geometry Regularization

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py`
- Test: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_regroup_ordered_segments_by_prior_strokes_regularizes_single_supported_wobbly_segment():
    ordered = [
        {
            "component_id": 1,
            "points": [(2.0, 2.0), (2.8, 4.0), (1.3, 6.0), (2.7, 8.0)],
            "source_segment_ids": (1,),
        }
    ]
    prior_strokes = [np.asarray([(2.0, 2.0), (2.0, 8.0)], dtype=float)]
    foreground_mask = np.zeros((12, 12), dtype=bool)
    foreground_mask[1:4, 2:9] = True

    regrouped, meta = regroup_ordered_segments_by_prior_strokes(
        ordered,
        prior_strokes,
        foreground_mask=foreground_mask,
    )

    xs = [point[0] for point in regrouped[0]["points"]]
    assert max(xs) - min(xs) < 0.75
    assert meta["geometry_regularized_segment_count"] == 1


def test_regroup_ordered_segments_by_makemeahanzi_reduces_zhong_top_right_foldback():
    ...
    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(...)
    target = next(
        segment for segment in regrouped if tuple(segment.get("source_segment_ids", ())) == (7, 8, 4)
    )
    pts = np.asarray(target["points"], dtype=float)
    centered = pts - pts.mean(axis=0)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    residual = float(np.mean(np.abs(centered @ vh[-1])))

    assert residual < 2.5
    assert meta["makemeahanzi_geometry_regularized_segment_count"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\\.venvs\\callirewrite-seq\\Scripts\\python.exe -m pytest offline_stroke_recovery_mvp\\tests\\test_makemeahanzi_prior.py -q
```

Expected:

```text
FAIL ... geometry_regularized_segment_count
FAIL ... residual < 2.5
```

- [ ] **Step 3: Write minimal implementation**

```python
def _regularize_grouped_segments_to_prior_geometry(...):
    regularized = []
    regularized_count = 0
    for segment in grouped_segments:
        component_id = int(segment.get("component_id", 0) or 0)
        if component_id <= 0:
            regularized.append(_copy_segment(segment))
            continue
        prior = prior_strokes[component_id - 1]
        updated = _regularize_segment_to_prior_subpath(...)
        if updated is not None:
            regularized.append(updated)
            regularized_count += 1
        else:
            regularized.append(_copy_segment(segment))
    return regularized, {"geometry_regularized_segment_count": regularized_count}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
.\\.venvs\\callirewrite-seq\\Scripts\\python.exe -m pytest offline_stroke_recovery_mvp\\tests\\test_makemeahanzi_prior.py -q
```

Expected:

```text
all tests passed
```

---

### Task 2: Thread Geometry Metadata Through the Hybrid Probe

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] **Step 1: Write the failing integration test**

```python
assert summary["makemeahanzi_geometry_regularized_segment_count"] >= 0
assert "makemeahanzi_geometry_regularized_segment_count" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\\.venvs\\callirewrite-seq\\Scripts\\python.exe -m pytest offline_stroke_recovery_mvp\\tests\\test_callirewrite_hybrid.py -q
```

Expected:

```text
FAIL ... key not present
```

- [ ] **Step 3: Write minimal implementation**

```python
return {
    **base_meta,
    ...,
    "makemeahanzi_geometry_regularized_segment_count": regularization_meta["geometry_regularized_segment_count"],
}
```

- [ ] **Step 4: Run targeted tests and the real visual probe**

Run:

```powershell
.\\.venvs\\callirewrite-seq\\Scripts\\python.exe -m pytest offline_stroke_recovery_mvp\\tests\\test_makemeahanzi_prior.py offline_stroke_recovery_mvp\\tests\\test_callirewrite_hybrid.py -q
.\\.venvs\\callirewrite-seq\\Scripts\\python.exe .\\offline_stroke_recovery_mvp\\scripts\\callirewrite_hybrid_probe.py --samples zhong,yong --postprocess-mode makemeahanzi_regroup
```

Expected:

```text
tests pass
probe status ok
```

---

## Self-Review

- Spec coverage: The plan covers the geometry correction layer, metadata plumb-through, and both synthetic and real-sample regression checks.
- Placeholder scan: The `zhong` real-sample test still needs the existing fixture-loading boilerplate copied from current tests during implementation, but the behavior and target grouped segment are explicit.
- Type consistency: New metadata should stay integer-valued and be folded into the existing `prior_meta` dictionary so `callirewrite_hybrid.py` can pass it through unchanged.
