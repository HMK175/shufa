# Kou Skeleton B-Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the real `kou` top-right overlap loop, smooth each centerline leg within the target foreground, and export skeleton-first review artifacts without changing width or brush-tip behavior.

**Architecture:** Keep the repair in `makemeahanzi_prior.py`, before primitive width transfer and rendering. First trim the redundant prefix of the right-wall member using stable downward-progress evidence, then smooth fixed-anchor legs with a second-difference penalty, validate displacement and foreground support, and finally reapply the existing overshoots. Existing candidates remain fallbacks.

**Tech Stack:** Python 3.12, NumPy, Pillow, pytest, existing MakeMeAHanzi medians and CalliRewrite converted outputs.

---

## Execution boundary

The current repository is a dirty normal checkout on `main`, and the entire
MVP directory is untracked. Per the user's earlier authorization, execution is
in place and must preserve unrelated files. Do not stage or commit in this
workspace unless the user separately requests it. The commit commands shown
below are for a clean isolated worktree only.

## File map

- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py`
  - overlap-prefix detection and trimming
  - fixed-anchor second-difference smoothing
  - `kou` validation, fallback, and metadata
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
  - pass the foreground mask to the `kou` builder
  - export skeleton-first images and summary paths
- Modify: `offline_stroke_recovery_mvp/src/visualize.py`
  - add a thin-centerline playback contact-sheet writer
- Modify: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`
  - pure overlap/smoothing tests and real-`kou` skeleton tests
- Modify: `offline_stroke_recovery_mvp/tests/test_visualize.py`
  - skeleton playback writer test
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`
  - route integration, metadata, artifact, and non-`kou` regression tests
- Modify: `offline_stroke_recovery_mvp/README.md`
  - record the focused skeleton batch and manual audit

## Task 1: Detect and trim the redundant `hengzhe` overlap prefix

**Files:**

- Modify: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`
- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py:259-386`

- [ ] **Step 1: Add imports and a synthetic failing overlap test**

Add these imports to `tests/test_makemeahanzi_prior.py`:

```python
_stable_downward_suffix_index,
trim_overlapping_hengzhe_corner_members,
```

Insert the two names into the module's existing
`from makemeahanzi_prior import (...)` tuple.

Add the test:

```python
def test_trim_overlapping_hengzhe_corner_members_removes_horizontal_return_before_downstroke():
    horizontal = np.asarray(
        [(10.0, 10.0), (9.5, 18.0), (9.0, 26.0)],
        dtype=float,
    )
    vertical_with_overlap = np.asarray(
        [
            (11.0, 18.0),
            (10.5, 22.0),
            (10.0, 26.0),
            (12.0, 26.0),
            (15.0, 25.5),
            (18.0, 25.0),
            (21.0, 24.5),
            (24.0, 24.0),
        ],
        dtype=float,
    )

    kept_horizontal, kept_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal,
        vertical_with_overlap,
        max_bridge_gap_px=10.0,
        stable_run_points=4,
    )

    assert np.array_equal(kept_horizontal, horizontal)
    assert np.allclose(kept_vertical[0], (10.0, 26.0))
    assert meta["trim_applied"] is True
    assert meta["trimmed_point_count"] == 2
    assert meta["bridge_gap_px"] == 1.0
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py::test_trim_overlapping_hengzhe_corner_members_removes_horizontal_return_before_downstroke -q
```

Expected: collection error because `_stable_downward_suffix_index` and
`trim_overlapping_hengzhe_corner_members` do not exist.

- [ ] **Step 3: Implement stable vertical-suffix detection**

Add above `build_prior_stroke_structure_candidate`:

```python
def _stable_downward_suffix_index(
    points: np.ndarray,
    *,
    stable_run_points: int = 6,
    max_upward_reversal_px: float = 0.5,
    max_lateral_reversal_px: float = 0.5,
) -> int | None:
    pts = np.asarray(points, dtype=float)
    run_points = max(int(stable_run_points), 3)
    if len(pts) < run_points:
        return None

    for index in range(0, len(pts) - run_points + 1):
        window = pts[index : index + run_points]
        deltas = np.diff(window, axis=0)
        downward = float(np.maximum(deltas[:, 0], 0.0).sum())
        upward = float(np.maximum(-deltas[:, 0], 0.0).sum())
        lateral = float(np.abs(deltas[:, 1]).sum())
        expected_lateral_sign = float(np.sign(pts[-1, 1] - pts[index, 1]))
        if expected_lateral_sign == 0.0:
            opposite_lateral = 0.0
        else:
            opposite_lateral = float(
                np.maximum(-expected_lateral_sign * deltas[:, 1], 0.0).sum()
            )
        if downward < 2.0:
            continue
        if downward < lateral * 1.25:
            continue
        if upward > float(max_upward_reversal_px):
            continue
        if opposite_lateral > float(max_lateral_reversal_px):
            continue
        return index
    return None
```

- [ ] **Step 4: Implement overlap trimming with explicit failure metadata**

Add immediately after `_stable_downward_suffix_index`:

```python
def trim_overlapping_hengzhe_corner_members(
    horizontal_member: np.ndarray,
    vertical_member: np.ndarray,
    *,
    max_bridge_gap_px: float = 10.0,
    stable_run_points: int = 6,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    horizontal = np.asarray(horizontal_member, dtype=float)
    vertical = np.asarray(vertical_member, dtype=float)
    base_meta = {
        "trim_applied": False,
        "trim_reason": "invalid_members",
        "trimmed_point_count": 0,
        "bridge_gap_px": float("inf"),
    }
    if len(horizontal) < 2 or len(vertical) < 2:
        return horizontal.copy(), vertical.copy(), base_meta

    suffix_index = _stable_downward_suffix_index(
        vertical,
        stable_run_points=stable_run_points,
    )
    if suffix_index is None:
        return horizontal.copy(), vertical.copy(), {
            **base_meta,
            "trim_reason": "stable_downward_suffix_not_found",
        }

    trimmed_vertical = vertical[suffix_index:].copy()
    bridge_gap_px = float(np.linalg.norm(trimmed_vertical[0] - horizontal[-1]))
    if bridge_gap_px > float(max_bridge_gap_px):
        return horizontal.copy(), vertical.copy(), {
            **base_meta,
            "trim_reason": "trimmed_bridge_gap_exceeds_limit",
            "bridge_gap_px": bridge_gap_px,
        }

    return horizontal.copy(), trimmed_vertical, {
        "trim_applied": suffix_index > 0,
        "trim_reason": "stable_downward_suffix",
        "trimmed_point_count": int(suffix_index),
        "bridge_gap_px": bridge_gap_px,
    }
```

- [ ] **Step 5: Run the focused test and verify GREEN**

Run the Step 2 command again.

Expected: `1 passed`.

- [ ] **Step 6: Add and run an excessive-gap rejection test**

Add:

```python
def test_trim_overlapping_hengzhe_corner_members_rejects_excessive_bridge_gap():
    horizontal = np.asarray([(0.0, 0.0), (0.0, 10.0)], dtype=float)
    vertical = np.asarray(
        [(1.0, 30.0), (4.0, 30.0), (7.0, 29.5), (10.0, 29.0)],
        dtype=float,
    )

    _, unchanged_vertical, meta = trim_overlapping_hengzhe_corner_members(
        horizontal,
        vertical,
        max_bridge_gap_px=10.0,
        stable_run_points=4,
    )

    assert np.array_equal(unchanged_vertical, vertical)
    assert meta["trim_applied"] is False
    assert meta["trim_reason"] == "trimmed_bridge_gap_exceeds_limit"
```

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py -q -k "trim_overlapping_hengzhe"
```

Expected: `2 passed`.

- [ ] **Step 7: Commit only in a clean isolated worktree**

```powershell
git add offline_stroke_recovery_mvp/src/makemeahanzi_prior.py offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py
git commit -m "fix: trim kou hengzhe overlap"
```

Skip this step in the current dirty `main` checkout.

## Task 2: Add fixed-anchor second-difference leg smoothing

**Files:**

- Modify: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`
- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py`

- [ ] **Step 1: Write failing smoothing tests**

Add:

```python
def _second_difference_energy(points: np.ndarray) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return 0.0
    second = pts[:-2] - 2.0 * pts[1:-1] + pts[2:]
    return float(np.square(second).sum())


def test_smooth_polyline_leg_bounded_preserves_fixed_endpoints_and_reduces_stair_steps():
    points = np.asarray(
        [(0.0, 0.0), (0.8, 2.0), (0.1, 4.0), (0.9, 6.0), (0.0, 8.0)],
        dtype=float,
    )

    smoothed = smooth_polyline_leg_bounded(
        points,
        fixed_indices=(0, len(points) - 1),
        smoothing_strength=4.0,
    )

    assert np.allclose(smoothed[0], points[0])
    assert np.allclose(smoothed[-1], points[-1])
    assert _second_difference_energy(smoothed) < _second_difference_energy(points)


def test_smooth_polyline_leg_bounded_preserves_explicit_corner_anchor():
    points = np.asarray(
        [(0.0, 0.0), (0.2, 2.0), (0.0, 4.0), (2.0, 4.2), (4.0, 4.0)],
        dtype=float,
    )

    smoothed = smooth_polyline_leg_bounded(
        points,
        fixed_indices=(0, 2, 4),
        smoothing_strength=4.0,
    )

    assert np.allclose(smoothed[0], points[0])
    assert np.allclose(smoothed[2], points[2])
    assert np.allclose(smoothed[4], points[4])
```

Import `smooth_polyline_leg_bounded` from `makemeahanzi_prior`.

- [ ] **Step 2: Run both tests and verify RED**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py -q -k "smooth_polyline_leg_bounded"
```

Expected: collection error because `smooth_polyline_leg_bounded` is missing.

- [ ] **Step 3: Implement the pure smoother**

Add below the overlap helpers:

```python
def smooth_polyline_leg_bounded(
    points: np.ndarray,
    *,
    fixed_indices: Sequence[int],
    smoothing_strength: float = 4.0,
) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3 or float(smoothing_strength) <= 0.0:
        return pts.copy()

    resampled = _resample_polyline_to_count(pts, len(pts))
    count = len(resampled)
    second_difference = np.zeros((count - 2, count), dtype=float)
    for row in range(count - 2):
        second_difference[row, row : row + 3] = (1.0, -2.0, 1.0)

    matrix = np.eye(count, dtype=float) + float(smoothing_strength) * (
        second_difference.T @ second_difference
    )
    target = resampled.copy()
    normalized_fixed = sorted(
        {
            index if index >= 0 else count + index
            for index in (int(value) for value in fixed_indices)
            if -count <= index < count
        }
    )
    for index in normalized_fixed:
        matrix[index, :] = 0.0
        matrix[index, index] = 1.0
        target[index] = pts[index]

    y = np.linalg.solve(matrix, target[:, 0])
    x = np.linalg.solve(matrix, target[:, 1])
    smoothed = np.column_stack([y, x])
    for index in normalized_fixed:
        smoothed[index] = pts[index]
    return smoothed
```

- [ ] **Step 4: Run the smoothing tests and verify GREEN**

Run the Step 2 command again.

Expected: `2 passed`.

- [ ] **Step 5: Commit only in a clean isolated worktree**

```powershell
git add offline_stroke_recovery_mvp/src/makemeahanzi_prior.py offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py
git commit -m "feat: add bounded skeleton leg smoothing"
```

Skip in the current checkout.

## Task 3: Integrate overlap trimming, smoothing, support validation, and overshoot reapplication

**Files:**

- Modify: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`
- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py:259-430`

- [ ] **Step 1: Add a real-route fixture that matches the current production source**

Extend imports from `trajectory_consolidation`:

```python
from trajectory_consolidation import (
    consolidate_ordered_segments,
    light_repair_ordered_segments_geometry,
    light_repair_raw_segments,
)
```

Add:

```python
def _load_real_kou_light_repair_labelled_segments():
    repo_root = Path(__file__).resolve().parents[2]
    converted_dir = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / "kou"
    input_path = repo_root / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / "kou.png"
    graphics_path = repo_root / "code" / "data" / "makemeahanzi" / "graphics.txt"
    raw_segments, _ = load_callirewrite_segments(converted_dir)
    foreground_mask = _load_input_foreground_mask(input_path)
    assert foreground_mask is not None
    light_raw, _ = light_repair_raw_segments(raw_segments, foreground_mask=foreground_mask)
    ordered = order_segments(
        light_raw,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    ordered, _ = light_repair_ordered_segments_geometry(
        ordered,
        foreground_mask=foreground_mask,
    )
    labelled, _ = label_segments_by_makemeahanzi_components(
        ordered,
        sample_name="kou",
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        graphics_path=graphics_path,
    )
    return labelled, foreground_mask, graphics_path
```

- [ ] **Step 2: Add the real failing skeleton test**

Add helpers and test:

```python
def _axis_reversal_px(points: Sequence[tuple[float, float]], *, axis: str) -> float:
    pts = np.asarray(points, dtype=float)
    deltas = np.diff(pts, axis=0)
    values = deltas[:, 1] if axis == "horizontal" else deltas[:, 0]
    return float(np.maximum(-values, 0.0).sum())


def test_build_kou_three_stroke_candidate_trims_real_hengzhe_loop_and_regularizes_skeleton():
    labelled, foreground_mask, graphics_path = _load_real_kou_light_repair_labelled_segments()

    structured, meta = build_kou_three_stroke_candidate(
        labelled,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        graphics_path=graphics_path,
        foreground_mask=foreground_mask,
    )

    hengzhe = structured[1]
    corner_index = int(hengzhe["structure_corner_index"])
    top_leg = hengzhe["points"][: corner_index + 1]
    right_leg = hengzhe["points"][corner_index:]
    assert meta["kou_skeleton_regularization_applied"] is True
    assert meta["kou_hengzhe_overlap_trimmed_point_count"] >= 10
    assert meta["kou_hengzhe_axis_transition_count"] == 1
    assert _axis_reversal_px(top_leg, axis="horizontal") <= 0.5
    assert _axis_reversal_px(right_leg, axis="vertical") <= 0.5
    assert meta["kou_skeleton_max_displacement_px"] <= 2.5
    assert meta["kou_skeleton_foreground_support_ratio"] >= 0.90
```

Also import `regularize_kou_structure_skeleton` and add metadata/fallback
coverage:

```python
def _synthetic_three_stroke_kou_structure():
    return [
        {
            "component_id": 1,
            "primitive_kind": "shu",
            "primitive_relative_widths": (1.0, 0.9),
            "points": [(2.0, 2.0), (10.0, 2.2)],
        },
        {
            "component_id": 2,
            "primitive_kind": "hengzhe",
            "primitive_relative_widths": (0.8, 1.1, 1.0),
            "structure_corner_index": 1,
            "points": [(2.0, 2.0), (2.0, 10.0), (10.0, 10.0)],
        },
        {
            "component_id": 3,
            "primitive_kind": "heng",
            "primitive_relative_widths": (0.9, 1.0),
            "points": [(10.0, 2.0), (10.0, 10.0)],
        },
    ]


def test_regularize_kou_structure_skeleton_preserves_primitive_metadata():
    segments = _synthetic_three_stroke_kou_structure()
    foreground_mask = np.ones((16, 16), dtype=bool)

    regularized, meta = regularize_kou_structure_skeleton(
        segments,
        foreground_mask=foreground_mask,
    )

    assert meta["kou_skeleton_regularization_applied"] is True
    assert [segment["primitive_kind"] for segment in regularized] == ["shu", "hengzhe", "heng"]
    assert [segment["primitive_relative_widths"] for segment in regularized] == [
        (1.0, 0.9),
        (0.8, 1.1, 1.0),
        (0.9, 1.0),
    ]


def test_regularize_kou_structure_skeleton_rejects_unsupported_geometry():
    segments = _synthetic_three_stroke_kou_structure()
    foreground_mask = np.zeros((16, 16), dtype=bool)

    regularized, meta = regularize_kou_structure_skeleton(
        segments,
        foreground_mask=foreground_mask,
    )

    assert meta["kou_skeleton_regularization_applied"] is False
    assert meta["kou_skeleton_regularization_reason"] == "foreground_support_too_low"
    assert [segment["points"] for segment in regularized] == [segment["points"] for segment in segments]
```

- [ ] **Step 3: Run the real test and verify RED**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py::test_build_kou_three_stroke_candidate_trims_real_hengzhe_loop_and_regularizes_skeleton -q
```

Expected: collection error because `regularize_kou_structure_skeleton` is
missing, or `TypeError` because `build_kou_three_stroke_candidate` does not
accept `foreground_mask`.

- [ ] **Step 4: Extend the generic builder with an opt-in `hengzhe` trim**

Change the signature to:

```python
def build_prior_stroke_structure_candidate(
    labelled_segments: Sequence[dict[str, Any]],
    prior_strokes: Sequence[np.ndarray],
    *,
    primitive_kinds: Sequence[str],
    max_bridge_gap_px: float = 10.0,
    endpoint_overshoots: dict[int, dict[str, float]] | None = None,
    trim_hengzhe_overlap: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
```

Add these fields to `base_meta`:

```python
"hengzhe_overlap_trim_applied": False,
"hengzhe_overlap_trim_reason": "not_requested",
"hengzhe_overlap_trimmed_point_count": 0,
```

Before the component loop, initialize the aggregate values:

```python
    hengzhe_trim_applied = False
    hengzhe_trim_reason = "not_requested"
    hengzhe_trimmed_point_count = 0
```

After `members.sort(...)` and before `merged_points` is assigned, add:

```python
        corner_index: int | None = None
        component_trim_meta = {
            "trim_applied": False,
            "trim_reason": "not_requested",
            "trimmed_point_count": 0,
            "bridge_gap_px": 0.0,
        }
        if trim_hengzhe_overlap and str(primitive_kind) == "hengzhe" and len(members) == 2:
            horizontal, vertical, component_trim_meta = trim_overlapping_hengzhe_corner_members(
                members[0][2],
                members[1][2],
                max_bridge_gap_px=max_bridge_gap_px,
                stable_run_points=6,
            )
            if component_trim_meta["trim_applied"]:
                members[0] = (members[0][0], members[0][1], horizontal, members[0][3])
                members[1] = (members[1][0], members[1][1], vertical, members[1][3])
            hengzhe_trim_applied = bool(component_trim_meta["trim_applied"])
            hengzhe_trim_reason = str(component_trim_meta["trim_reason"])
            hengzhe_trimmed_point_count = int(component_trim_meta["trimmed_point_count"])
```

Immediately after `merged_points = members[0][2].copy()`, add:

```python
        if str(primitive_kind) == "hengzhe":
            corner_index = len(merged_points) - 1
```

Before appending the template, add:

```python
        if corner_index is not None:
            template["structure_corner_index"] = int(corner_index)
```

Aggregate the trim metadata into the returned dictionary:

```python
"hengzhe_overlap_trim_applied": hengzhe_trim_applied,
"hengzhe_overlap_trim_reason": hengzhe_trim_reason,
"hengzhe_overlap_trimmed_point_count": hengzhe_trimmed_point_count,
```

- [ ] **Step 5: Add complete bounded regularization helpers**

Add after the generic builder:

```python
def _apply_structure_endpoint_overshoots(
    segments: Sequence[dict[str, Any]],
    endpoint_overshoots: dict[int, dict[str, float]],
) -> tuple[list[dict[str, Any]], int]:
    updated: list[dict[str, Any]] = []
    count = 0
    for segment in segments:
        copied = _copy_segment(segment)
        component_id = int(copied.get("component_id", 0) or 0)
        rules = endpoint_overshoots.get(component_id, {})
        points = np.asarray(copied.get("points", ()), dtype=float)
        if float(rules.get("start", 0.0)) > 0.0:
            points = _extend_polyline_endpoint(
                points,
                distance_px=float(rules["start"]),
                at_end=False,
            )
            if "structure_corner_index" in copied:
                copied["structure_corner_index"] = int(copied["structure_corner_index"]) + 1
            count += 1
        if float(rules.get("end", 0.0)) > 0.0:
            points = _extend_polyline_endpoint(
                points,
                distance_px=float(rules["end"]),
                at_end=True,
            )
            count += 1
        copied["points"] = [tuple(float(value) for value in point) for point in points]
        updated.append(copied)
    return updated, count


def _axis_transition_count(points: np.ndarray) -> int:
    pts = np.asarray(points, dtype=float)
    labels: list[str] = []
    for delta in np.diff(pts, axis=0):
        if float(np.linalg.norm(delta)) <= 1e-6:
            continue
        label = "horizontal" if abs(float(delta[1])) >= abs(float(delta[0])) else "vertical"
        if not labels or labels[-1] != label:
            labels.append(label)
    return max(len(labels) - 1, 0)


def regularize_kou_structure_skeleton(
    structured_segments: Sequence[dict[str, Any]],
    *,
    foreground_mask: np.ndarray,
    support_radius_px: int = 2,
    min_support_ratio: float = 0.90,
    max_displacement_px: float = 2.5,
    smoothing_strength: float = 4.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    original = [_copy_segment(segment) for segment in structured_segments]
    base_meta = {
        "kou_skeleton_regularization_applied": False,
        "kou_skeleton_regularization_reason": "invalid_structure",
        "kou_hengzhe_axis_transition_count": 0,
        "kou_skeleton_max_displacement_px": 0.0,
        "kou_skeleton_foreground_support_ratio": 0.0,
    }
    if len(original) != 3:
        return original, base_meta

    regularized: list[dict[str, Any]] = []
    max_displacement = 0.0
    all_points: list[np.ndarray] = []
    for index, segment in enumerate(original):
        copied = _copy_segment(segment)
        points = np.asarray(copied.get("points", ()), dtype=float)
        if len(points) < 2:
            return original, {**base_meta, "kou_skeleton_regularization_reason": "empty_leg"}
        if index == 1:
            corner_index = int(copied.get("structure_corner_index", -1))
            if not 1 <= corner_index < len(points) - 1:
                return original, {**base_meta, "kou_skeleton_regularization_reason": "missing_corner_index"}
            top = smooth_polyline_leg_bounded(
                points[: corner_index + 1],
                fixed_indices=(0, corner_index),
                smoothing_strength=smoothing_strength,
            )
            right = smooth_polyline_leg_bounded(
                points[corner_index:],
                fixed_indices=(0, len(points) - 1 - corner_index),
                smoothing_strength=smoothing_strength,
            )
            candidate = np.vstack([top, right[1:]])
        else:
            candidate = smooth_polyline_leg_bounded(
                points,
                fixed_indices=(0, len(points) - 1),
                smoothing_strength=smoothing_strength,
            )
        displacement = np.linalg.norm(candidate - points, axis=1)
        max_displacement = max(max_displacement, float(displacement.max(initial=0.0)))
        copied["points"] = [tuple(float(value) for value in point) for point in candidate]
        regularized.append(copied)
        all_points.append(candidate)

    combined = np.vstack(all_points)
    support_ratio = _support_ratio_in_radius(
        combined,
        np.asarray(foreground_mask, dtype=bool),
        radius_px=int(support_radius_px),
    )
    transition_count = _axis_transition_count(
        np.asarray(regularized[1]["points"], dtype=float)
    )
    if max_displacement > float(max_displacement_px):
        return original, {
            **base_meta,
            "kou_skeleton_regularization_reason": "max_displacement_exceeded",
            "kou_hengzhe_axis_transition_count": transition_count,
            "kou_skeleton_max_displacement_px": max_displacement,
            "kou_skeleton_foreground_support_ratio": support_ratio,
        }
    if support_ratio < float(min_support_ratio):
        return original, {
            **base_meta,
            "kou_skeleton_regularization_reason": "foreground_support_too_low",
            "kou_hengzhe_axis_transition_count": transition_count,
            "kou_skeleton_max_displacement_px": max_displacement,
            "kou_skeleton_foreground_support_ratio": support_ratio,
        }
    if transition_count != 1:
        return original, {
            **base_meta,
            "kou_skeleton_regularization_reason": "unexpected_axis_transition_count",
            "kou_hengzhe_axis_transition_count": transition_count,
            "kou_skeleton_max_displacement_px": max_displacement,
            "kou_skeleton_foreground_support_ratio": support_ratio,
        }
    return regularized, {
        **base_meta,
        "kou_skeleton_regularization_applied": True,
        "kou_skeleton_regularization_reason": "overlap_trimmed_and_legs_smoothed",
        "kou_hengzhe_axis_transition_count": transition_count,
        "kou_skeleton_max_displacement_px": max_displacement,
        "kou_skeleton_foreground_support_ratio": support_ratio,
    }
```

- [ ] **Step 6: Update `build_kou_three_stroke_candidate` in one bounded flow**

Change the signature:

```python
def build_kou_three_stroke_candidate(
    labelled_segments: Sequence[dict[str, Any]],
    *,
    canvas_shape: tuple[int, int],
    graphics_path: Path | str = DEFAULT_GRAPHICS_PATH,
    max_bridge_gap_px: float = 10.0,
    foreground_mask: np.ndarray | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
```

Replace the final direct return with:

```python
    structured, structure_meta = build_prior_stroke_structure_candidate(
        labelled_segments,
        prior_strokes,
        primitive_kinds=("shu", "hengzhe", "heng"),
        max_bridge_gap_px=max_bridge_gap_px,
        endpoint_overshoots=None,
        trim_hengzhe_overlap=True,
    )
    if not structured:
        return structured, structure_meta

    regularization_meta = {
        "kou_skeleton_regularization_applied": False,
        "kou_skeleton_regularization_reason": "foreground_mask_unavailable",
        "kou_hengzhe_axis_transition_count": 0,
        "kou_skeleton_max_displacement_px": 0.0,
        "kou_skeleton_foreground_support_ratio": 0.0,
    }
    regularized = structured
    if foreground_mask is not None:
        regularized, regularization_meta = regularize_kou_structure_skeleton(
            structured,
            foreground_mask=np.asarray(foreground_mask, dtype=bool),
        )

    overshoot_rules = {1: {"end": 4.0}, 2: {"start": 2.0}, 3: {"end": 4.0}}
    final_segments, overshoot_count = _apply_structure_endpoint_overshoots(
        regularized,
        overshoot_rules,
    )
    return final_segments, {
        **structure_meta,
        **regularization_meta,
        "structure_overshoot_count": overshoot_count,
        "kou_hengzhe_overlap_trimmed_point_count": int(
            structure_meta.get("hengzhe_overlap_trimmed_point_count", 0)
        ),
    }
```

- [ ] **Step 7: Run the real test and adjust only the algorithm, not the assertion**

Run the Step 3 command.

Then run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py -q -k "regularize_kou_structure_skeleton"
```

Expected: the real test and both pure regularization tests pass. If the real
test fails, inspect the actual stable suffix, maximum
displacement, and support ratio. Do not relax the `0.5 px`, `2.5 px`, or `0.90`
acceptance bounds without returning to the design decision.

- [ ] **Step 8: Tighten the existing overshoot test**

In
`test_build_kou_three_stroke_candidate_joins_hengzhe_and_preserves_intersection_overshoots`,
pass `foreground_mask=foreground_mask` and add:

```python
assert meta["kou_skeleton_regularization_applied"] is True
assert meta["kou_hengzhe_overlap_trimmed_point_count"] >= 10
assert meta["structure_overshoot_count"] == 3
```

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py -q
```

Expected: all MakeMeAHanzi tests pass.

- [ ] **Step 9: Commit only in a clean isolated worktree**

```powershell
git add offline_stroke_recovery_mvp/src/makemeahanzi_prior.py offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py
git commit -m "feat: regularize kou structure skeleton"
```

Skip in the current checkout.

## Task 4: Pass the real foreground mask through the hybrid route and preserve primitive metadata

**Files:**

- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py:619-668`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py:891-930`

- [ ] **Step 1: Extend the real `kou` route test and verify RED**

Add these assertions to
`test_run_callirewrite_hybrid_probe_auto_mode_exports_and_selects_real_kou_three_stroke_primitive_candidate`:

```python
assert summary["kou_skeleton_regularization_applied"] is True
assert summary["kou_hengzhe_overlap_trimmed_point_count"] >= 10
assert summary["kou_hengzhe_axis_transition_count"] == 1
assert summary["kou_skeleton_max_displacement_px"] <= 2.5
assert summary["kou_skeleton_foreground_support_ratio"] >= 0.90
assert summary["primitive_transfer_segment_count"] == 3
assert summary["primitive_transfer_kinds"] == ["shu", "hengzhe", "heng"]
```

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_callirewrite_hybrid.py::test_run_callirewrite_hybrid_probe_auto_mode_exports_and_selects_real_kou_three_stroke_primitive_candidate -q
```

Expected: FAIL because the route does not pass `foreground_mask`, so
regularization remains unavailable.

- [ ] **Step 2: Pass the mask into the builder**

In `_run_single_sample`, update the call:

```python
        structure_primitive_segments, structure_meta = build_kou_three_stroke_candidate(
            structure_source_segments,
            canvas_shape=source_canvas_shape,
            graphics_path=(
                makemeahanzi_graphics_path
                if makemeahanzi_graphics_path is not None
                else Path("code/data/makemeahanzi/graphics.txt")
            ),
            foreground_mask=foreground_mask,
        )
```

Do not change `_attach_primitive_width_profiles`; it must run after skeleton
regularization and continue to attach the same three primitive profiles.

- [ ] **Step 3: Run the real route test and verify GREEN**

Run the Step 1 command again.

Expected: `1 passed`.

- [ ] **Step 4: Verify non-`kou` route selection remains unchanged**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_callirewrite_hybrid.py -q -k "promotes_xin_component_mix or prefers_real_zhong_light_repair"
```

Expected: both tests pass; `xin` remains `component_mix` and `zhong` remains
`raw_light_repair`.

- [ ] **Step 5: Commit only in a clean isolated worktree**

```powershell
git add offline_stroke_recovery_mvp/src/callirewrite_hybrid.py offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py
git commit -m "feat: apply kou skeleton regularization in hybrid route"
```

Skip in the current checkout.

## Task 5: Export skeleton-first trajectory, overlay, and playback artifacts

**Files:**

- Modify: `offline_stroke_recovery_mvp/src/visualize.py:140-250`
- Modify: `offline_stroke_recovery_mvp/tests/test_visualize.py`
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py:900-1065`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] **Step 1: Write a failing skeleton-playback writer test**

Import `write_trajectory_playback_contact_sheet` in `test_visualize.py` and add:

```python
def test_write_trajectory_playback_contact_sheet_draws_thin_centerline_steps(tmp_path: Path):
    skeleton = np.zeros((32, 32), dtype=bool)
    segments = [
        {"component_id": 1, "points": [(4.0, 4.0), (24.0, 6.0)]},
        {"component_id": 2, "points": [(6.0, 8.0), (6.0, 24.0), (24.0, 22.0)]},
        {"component_id": 3, "points": [(24.0, 7.0), (23.0, 25.0)]},
    ]
    output_path = tmp_path / "skeleton_playback.png"

    write_trajectory_playback_contact_sheet(
        output_path,
        skeleton,
        segments,
        scale=3,
        panel_size=(120, 120),
    )

    assert output_path.exists()
    image = Image.open(output_path).convert("RGB")
    pixels = np.asarray(image, dtype=np.uint8)
    assert image.width > 0 and image.height > 0
    assert int(np.count_nonzero(np.any(pixels < 220, axis=2))) > 50
```

Add `Image` to the Pillow import if the test module does not already import it.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_visualize.py::test_write_trajectory_playback_contact_sheet_draws_thin_centerline_steps -q
```

Expected: import error because the writer does not exist.

- [ ] **Step 3: Implement the skeleton playback writer**

Add after `write_execution_playback_contact_sheet` in `visualize.py`:

```python
def write_trajectory_playback_contact_sheet(
    path: Path,
    skeleton: np.ndarray,
    ordered_segments: Sequence[dict[str, Any]],
    *,
    scale: int = 3,
    panel_size: tuple[int, int] = (180, 180),
    padding: int = 10,
    header_height: int = 18,
    max_columns: int = 4,
) -> None:
    segment_count = max(len(ordered_segments), 1)
    columns = max(1, min(max_columns, segment_count))
    rows = max(int(np.ceil(segment_count / float(columns))), 1)
    width = padding + columns * (panel_size[0] + padding)
    height = padding + rows * (header_height + panel_size[1] + padding)
    canvas = Image.new("RGB", (max(width, 1), max(height, 1)), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for step in range(segment_count):
        row = step // columns
        column = step % columns
        left = padding + column * (panel_size[0] + padding)
        top = padding + row * (header_height + panel_size[1] + padding)
        draw.text((left, top), f"step {step + 1}", fill=(30, 30, 30))
        panel_canvas = _base(skeleton, scale=scale)
        panel_draw = ImageDraw.Draw(panel_canvas)
        for index, segment in enumerate(ordered_segments[: step + 1]):
            _draw_polyline(
                panel_draw,
                segment.get("points", ()),
                scale,
                PALETTE[index % len(PALETTE)],
            )
        panel = _fit_image_to_panel(panel_canvas, panel_size)
        panel_top = top + header_height
        canvas.paste(panel, (left, panel_top))
        draw.rectangle(
            (left, panel_top, left + panel_size[0] - 1, panel_top + panel_size[1] - 1),
            outline=(200, 200, 200),
        )
    _save(canvas, path)
```

- [ ] **Step 4: Run the writer test and verify GREEN**

Run the Step 2 command again.

Expected: `1 passed`.

- [ ] **Step 5: Add failing route artifact assertions**

Extend the real `kou` route test:

```python
assert Path(summary["structure_skeleton_trajectory_image"]).exists()
assert Path(summary["structure_skeleton_overlay_image"]).exists()
assert Path(summary["structure_skeleton_playback_contact_sheet"]).exists()
```

Run the focused route test.

Expected: FAIL because the summary keys and files do not exist.

- [ ] **Step 6: Export the three skeleton-first artifacts**

Import the new writer in `callirewrite_hybrid.py`:

```python
write_trajectory_playback_contact_sheet,
```

Insert the name into the existing `from visualize import (...)` tuple.

After `cropped_input_image` is available and before the width renders, add:

```python
    if structure_primitive_visual_segments:
        write_trajectory_png(
            sample_dir / "structure_skeleton_trajectory.png",
            blank_skeleton,
            structure_primitive_visual_segments,
            show_pen_up_connectors=False,
        )
        _write_overlay_png(
            sample_dir / "structure_skeleton_overlay.png",
            cropped_input_image,
            structure_primitive_visual_segments,
            color_by_component=True,
        )
        write_trajectory_playback_contact_sheet(
            sample_dir / "structure_skeleton_playback_contact_sheet.png",
            blank_skeleton,
            structure_primitive_visual_segments,
        )
```

Add summary fields:

```python
"structure_skeleton_trajectory_image": (
    str(sample_dir / "structure_skeleton_trajectory.png")
    if structure_primitive_segments
    else "n/a"
),
"structure_skeleton_overlay_image": (
    str(sample_dir / "structure_skeleton_overlay.png")
    if structure_primitive_segments
    else "n/a"
),
"structure_skeleton_playback_contact_sheet": (
    str(sample_dir / "structure_skeleton_playback_contact_sheet.png")
    if structure_primitive_segments
    else "n/a"
),
```

- [ ] **Step 7: Run focused writer and route tests**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_visualize.py::test_write_trajectory_playback_contact_sheet_draws_thin_centerline_steps -q
python -m pytest offline_stroke_recovery_mvp\tests\test_callirewrite_hybrid.py::test_run_callirewrite_hybrid_probe_auto_mode_exports_and_selects_real_kou_three_stroke_primitive_candidate -q
```

Expected: both pass.

- [ ] **Step 8: Commit only in a clean isolated worktree**

```powershell
git add offline_stroke_recovery_mvp/src/visualize.py offline_stroke_recovery_mvp/src/callirewrite_hybrid.py offline_stroke_recovery_mvp/tests/test_visualize.py offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py
git commit -m "feat: export kou skeleton review artifacts"
```

Skip in the current checkout.

## Task 6: Focused visual audit, regression verification, and README update

**Files:**

- Modify: `offline_stroke_recovery_mvp/README.md`

- [ ] **Step 1: Run focused unit suites**

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py -q
python -m pytest offline_stroke_recovery_mvp\tests\test_visualize.py -q
python -m pytest offline_stroke_recovery_mvp\tests\test_callirewrite_hybrid.py -q
```

Expected: all three suites pass with no warnings or errors.

- [ ] **Step 2: Generate a focused `kou` batch**

Run:

```powershell
python .\offline_stroke_recovery_mvp\scripts\callirewrite_hybrid_probe.py --samples kou --postprocess-mode auto --output-dir offline_stroke_recovery_mvp\outputs\kou_skeleton_b_plan
```

Expected: status `ok`, selected mode `structure_primitive`, and one timestamped
batch under `outputs/kou_skeleton_b_plan/`.

- [ ] **Step 3: Inspect skeleton-first artifacts before the filled render**

Open and compare:

```text
kou/input_image.png
kou/structure_skeleton_trajectory.png
kou/structure_skeleton_overlay.png
kou/structure_skeleton_playback_contact_sheet.png
kou/structure_primitive_rendered_execution.png
```

Manual acceptance checklist:

- no right-left-right loop at the top-right corner;
- exactly one horizontal-to-vertical turn in stroke 2;
- left, top, right, and bottom legs no longer show staircase sampling;
- target lean and shallow curvature remain visible;
- three approved overshoots remain visible;
- filled width is not used to hide a centerline defect.

- [ ] **Step 4: Run the full MVP suite**

```powershell
python -m pytest offline_stroke_recovery_mvp\tests -q
```

Expected: every test passes. Record the exact final count and elapsed time in
the README.

- [ ] **Step 5: Update the README with measured and visual results**

Append a dated section that records:

```text
- root cause: untrimmed overlap prefix in the second stroke
- number of trimmed points
- axis transition count after repair
- maximum smoothing displacement
- foreground support ratio
- focused batch path
- focused and full test counts
- manual visual status
- explicit statement that width and xin fixes were deferred
```

Do not claim that the filled `kou` is final merely because the skeleton gate
passes.

- [ ] **Step 6: Commit only in a clean isolated worktree**

```powershell
git add offline_stroke_recovery_mvp/README.md
git commit -m "docs: record kou skeleton repair audit"
```

Skip in the current checkout.

## Plan self-review

- Spec coverage: overlap trimming, leg smoothing, foreground validation,
  overshoot preservation, fallback metadata, skeleton-first outputs, route
  isolation, manual audit, and full regression are each assigned to a task.
- Scope: no width tuning, `xin` change, held-out-character evaluation, robot,
  or API behavior is included.
- Type consistency: the plan consistently uses
  `structure_corner_index`, `kou_skeleton_regularization_applied`,
  `kou_hengzhe_overlap_trimmed_point_count`,
  `kou_hengzhe_axis_transition_count`,
  `kou_skeleton_max_displacement_px`, and
  `kou_skeleton_foreground_support_ratio`.
- Fallback: missing stable suffix, excessive bridge gap, excessive smoothing
  displacement, weak foreground support, or unexpected transition count all
  keep the pre-regularized three-stroke candidate and record a reason.
- TDD: every production behavior is preceded by a focused failing test and an
  explicit RED command.
