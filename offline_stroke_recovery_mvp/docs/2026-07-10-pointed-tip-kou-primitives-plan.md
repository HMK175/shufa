# Pointed Tip, Three-Stroke Kou, and Stroke Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a true pointed wogou terminal, a three-stroke `kou` structural candidate with visible intersection overshoot, and reusable normalized `heng`/`shu`/`hengzhe`/`gou` primitives.

**Architecture:** Extend the renderer with explicit pointed endpoint policies, add a pure `stroke_primitives.py` module for geometry and relative-width transfer, and build a bounded MakeMeAHanzi-guided structure candidate before route selection. Existing raw, light-repair, local, MakeMeAHanzi, and component-mix candidates remain fallbacks.

**Tech Stack:** Python 3.12, NumPy, Pillow, pytest, existing MakeMeAHanzi medians and CalliRewrite converted outputs.

---

## File map

- Create: `offline_stroke_recovery_mvp/src/stroke_primitives.py`
- Create: `offline_stroke_recovery_mvp/tests/test_stroke_primitives.py`
- Modify: `offline_stroke_recovery_mvp/src/visualize.py`
- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py`
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_visualize.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/README.md`

The repository is currently a dirty normal checkout on `main`, and the entire
MVP directory is untracked. Per the user's explicit instruction, implementation
is performed in place. This plan does not stage, commit, merge, push, or clean
the user's existing work.

## Task 1: Add true pointed endpoint rendering for long foldback hooks

**Files:**

- Modify: `offline_stroke_recovery_mvp/tests/test_visualize.py`
- Modify: `offline_stroke_recovery_mvp/src/visualize.py`

- [ ] **Step 1: Add a failing real-profile test**

Add:

```python
def test_build_variable_width_profile_makes_real_xin_component_mix_wogou_terminal_zero_width():
    mixed_segments, foreground_mask = _load_real_xin_component_mix_segments()
    policies = _build_endpoint_cap_policies(mixed_segments)
    index = _select_segment_index_by_source_ids(mixed_segments, (3, 2, 10))
    points = [tuple(point) for point in mixed_segments[index]["points"]]
    profile = _build_variable_width_profile(
        points,
        foreground_mask,
        cap_start=policies[index]["cap_start"],
        cap_end=policies[index]["cap_end"],
        source_segment_ids=(3, 2, 10),
    )
    assert profile is not None
    _, diameters, _, _ = profile
    tail = np.asarray(diameters[-18:], dtype=float)
    assert diameters[-1] == 0.0
    assert np.all(np.diff(tail) <= 1e-9)
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_visualize.py::test_build_variable_width_profile_makes_real_xin_component_mix_wogou_terminal_zero_width -q
```

Expected: FAIL because the current terminal remains above zero.

- [ ] **Step 3: Add a failing renderer test**

Render a synthetic pointed polyline at `scale=6`, then assert the final
cross-section contains at most two dark pixels while the preceding body remains
wider than six pixels.

- [ ] **Step 4: Implement pointed profile and endpoint flags**

Add to `visualize.py`:

```python
def _pointed_foldback_terminal_flags(
    points,
    *,
    source_segment_ids,
    cap_start,
    cap_end,
) -> tuple[bool, bool]: ...

def _taper_pointed_foldback_terminal_diameters_px(
    points,
    diameters,
    *,
    source_segment_ids,
    cap_start,
    cap_end,
    taper_fraction=0.25,
    min_taper_points=18,
) -> list[float]: ...
```

The taper must run after straight-body regularization, be monotonic over the
terminal window, and set the designated terminal diameter to `0.0`.

Extend `_draw_variable_width_polyline` with:

```python
pointed_start: bool = False,
pointed_end: bool = False,
```

For a pointed endpoint only, bypass the normal minimum radius and converge the
polygon sides to the center point. Do not draw a round cap there.

- [ ] **Step 5: Verify GREEN and regression behavior**

Run the two new pointed tests plus the existing real `xin` foldback and render
tests. Then regenerate `xin` in `auto` mode and inspect
`rendered_execution.png` and `playback_contact_sheet.png`.

## Task 2: Create the normalized stroke primitive module

**Files:**

- Create: `offline_stroke_recovery_mvp/src/stroke_primitives.py`
- Create: `offline_stroke_recovery_mvp/tests/test_stroke_primitives.py`

- [ ] **Step 1: Write failing normalization tests**

Tests must assert:

```python
def test_normalize_stroke_primitive_is_translation_and_scale_invariant(): ...
def test_resample_relative_widths_preserves_endpoint_order(): ...
def test_reverse_stroke_primitive_swaps_endpoint_roles(): ...
def test_compose_hengzhe_primitive_contains_one_corner(): ...
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_stroke_primitives.py -q
```

Expected: import failure because the module does not exist.

- [ ] **Step 3: Implement the pure primitive API**

Create:

```python
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
    def register(self, primitive: StrokePrimitive) -> None: ...
    def get(self, kind: str) -> StrokePrimitive | None: ...


def normalize_stroke_primitive(... ) -> StrokePrimitive: ...
def resample_relative_widths(relative_widths, count: int) -> list[float]: ...
def reverse_stroke_primitive(primitive: StrokePrimitive) -> StrokePrimitive: ...
def compose_hengzhe_primitive(heng, shu, *, corner_fraction: float) -> StrokePrimitive: ...
def transfer_relative_width_profile(diameters, primitive, *, blend: float = 0.7) -> list[float]: ...
```

Normalization uses cumulative arc length for profile sampling and preserves a
median relative width of `1.0`.

- [ ] **Step 4: Verify GREEN**

Run the complete new test module.

## Task 3: Build reference primitives from the existing development samples

**Files:**

- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] **Step 1: Add failing reference-selection tests**

Add tests for:

```python
def test_select_reference_heng_uses_longest_horizontal_yi_segment(): ...
def test_select_reference_shu_uses_longest_vertical_shi_segment(): ...
def test_build_reference_primitive_library_contains_heng_shu_and_hengzhe(): ...
```

- [ ] **Step 2: Verify RED**

Run only the three new tests and confirm missing-helper failures.

- [ ] **Step 3: Implement reference extraction**

Add private helpers to `callirewrite_hybrid.py`:

```python
def _select_axis_reference_segment(segments, *, axis: str) -> dict[str, Any] | None: ...
def _build_reference_stroke_primitive_library(converted_dir, input_dir) -> StrokePrimitiveLibrary: ...
```

Use `yi` for `heng`, `shi` for `shu`, and compose `hengzhe`. If either
reference is missing, return a partial library and record the missing kinds.

- [ ] **Step 4: Verify GREEN**

Run the new tests and the existing CalliRewrite loading tests.

## Task 4: Build a generic prior-stroke structure candidate and apply it to `kou`

**Files:**

- Modify: `offline_stroke_recovery_mvp/src/makemeahanzi_prior.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_makemeahanzi_prior.py`

- [ ] **Step 1: Add a failing real-`kou` structure test**

The test must load the existing real `kou` segments, apply component labels,
and assert:

```python
assert len(structured) == 3
assert [segment["primitive_kind"] for segment in structured] == ["shu", "hengzhe", "heng"]
assert structured[1]["component_id"] == 2
assert _count_sharp_turns(structured[1]["points"]) == 1
```

Also assert the left vertical extends below the bottom horizontal intersection
and the closing horizontal extends beyond the right intersection.

- [ ] **Step 2: Verify RED**

Run the new real-`kou` test and confirm the four-segment current output fails.

- [ ] **Step 3: Implement the structure builder**

Add:

```python
def build_prior_stroke_structure_candidate(
    labelled_segments,
    prior_strokes,
    *,
    primitive_kinds,
    max_bridge_gap_px=10.0,
    endpoint_overshoots=None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...

def build_kou_three_stroke_candidate(
    labelled_segments,
    *,
    canvas_shape,
    graphics_path=DEFAULT_GRAPHICS_PATH,
) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...
```

Members are ordered by prior-median arc position. Short missing runs are
sampled from the prior median. A gap above `max_bridge_gap_px` rejects the
candidate. The output carries `primitive_kind`, endpoint roles, source ids,
and structure metadata.

- [ ] **Step 4: Verify GREEN**

Run the new structure tests plus the existing MakeMeAHanzi test module.

## Task 5: Transfer primitive width profiles to structured `kou`

**Files:**

- Modify: `offline_stroke_recovery_mvp/src/visualize.py`
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_visualize.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] **Step 1: Add a failing width-transfer test**

Attach the `yi` `heng` relative profile to a target horizontal segment with a
different length and median width. Assert that the transferred profile keeps
the target median width while matching the normalized start/body/end ratios of
the reference.

- [ ] **Step 2: Verify RED**

Run the new test and confirm the current foreground-only profile ignores the
primitive metadata.

- [ ] **Step 3: Add optional primitive metadata to rendering**

Pass these optional segment fields through `_draw_execution_polyline` and
`_build_variable_width_profile`:

```python
primitive_relative_widths
primitive_width_blend
primitive_kind
pointed_start
pointed_end
```

Apply `transfer_relative_width_profile` after foreground-width stabilization
and before endpoint-role tapering.

- [ ] **Step 4: Apply primitives to `kou` strokes**

Use:

- `shu` primitive for stroke 1;
- composed `hengzhe` primitive for stroke 2;
- `heng` primitive for stroke 3.

The target centerlines and anchors remain from the structure candidate; only
normalized relative width behavior and endpoint roles transfer.

- [ ] **Step 5: Verify GREEN**

Run the new primitive rendering tests and regenerate `kou` for manual
inspection.

## Task 6: Integrate and select the `structure_primitive` candidate

**Files:**

- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] **Step 1: Add failing real-route tests**

Assert that the real `kou` auto probe:

- emits `structure_primitive_rendered_execution.png`;
- records `structure_prior_applied=true`;
- records `primitive_transfer_applied=true`;
- produces three strokes;
- selects `structure_primitive` when its similarity is within `0.05` of the
  best existing route.

Assert that non-`kou` samples retain their previous selected modes.

- [ ] **Step 2: Verify RED**

Run the new real-route tests and confirm the candidate/output are absent.

- [ ] **Step 3: Implement candidate generation and bounded selection**

Add the candidate alongside existing routes, include it in the review contact
sheet, summary JSON, and review recommendation logic. Do not remove or mutate
existing candidate outputs.

- [ ] **Step 4: Verify GREEN**

Run the full `test_callirewrite_hybrid.py` module.

## Task 7: Register the selected `xin` hook primitive

**Files:**

- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] **Step 1: Add a failing hook-registration test**

Run the real `xin` component-mix route and assert that the selected long
foldback is exported as a `gou` primitive whose end role is `pointed` and whose
last relative width is zero.

- [ ] **Step 2: Verify RED**

Confirm that no `gou` primitive metadata currently exists.

- [ ] **Step 3: Register and summarize the primitive**

Normalize the selected `xin` segment after pointed profile generation and add
summary fields:

```text
registered_primitive_kinds
gou_primitive_source_sample
gou_primitive_pointed_end
```

- [ ] **Step 4: Verify GREEN**

Run the hook-registration test and the existing real `xin` auto-selection
test.

## Task 8: Visual verification, documentation, and full regression

**Files:**

- Modify: `offline_stroke_recovery_mvp/README.md`

- [ ] **Step 1: Regenerate focused samples**

Run:

```powershell
python .\offline_stroke_recovery_mvp\scripts\callirewrite_hybrid_probe.py --samples xin,kou --postprocess-mode auto --output-dir offline_stroke_recovery_mvp\outputs\pointed_tip_kou_primitives
```

- [ ] **Step 2: Perform manual visual inspection**

Inspect input, rendered execution, playback contact sheet, candidate order,
and structure-prior comparison. Record that visual acceptance is manual.

- [ ] **Step 3: Run focused suites**

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_stroke_primitives.py -q
python -m pytest offline_stroke_recovery_mvp\tests\test_visualize.py -q
python -m pytest offline_stroke_recovery_mvp\tests\test_makemeahanzi_prior.py -q
python -m pytest offline_stroke_recovery_mvp\tests\test_callirewrite_hybrid.py -q
```

- [ ] **Step 4: Run the full MVP suite**

```powershell
python -m pytest offline_stroke_recovery_mvp\tests -q
```

- [ ] **Step 5: Update README**

Document the final output batch, test counts, pointed-tip behavior, three-stroke
`kou` structure, primitive reference sources, and the explicit deferral of the
held-out character evaluation.

## Plan self-review

- Spec coverage: all three approved items have independent tests and an
  integration task.
- Deferred scope: the unseen-character evaluation is not included.
- Placeholder scan: no `TBD`, `TODO`, or unnamed implementation step remains.
- Type consistency: primitive field names and endpoint-role names are stable
  across tasks.
- Safety: no robot, CoppeliaSim, AUBO, SDK, network, or API-key behavior is
  introduced.
