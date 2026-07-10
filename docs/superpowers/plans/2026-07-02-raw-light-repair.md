# Raw Light Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative `raw_light_repair` path that only repairs small false splits in raw recovered skeletons without changing the main glyph geometry.

**Architecture:** Put the repair rule in `trajectory_consolidation.py` as a small standalone utility that merges only high-confidence collinear endpoint pairs. Wire that repaired raw candidate into `callirewrite_hybrid.py` as a new manual probe mode and add a dedicated visual output so raw vs repaired geometry can be inspected side by side.

**Tech Stack:** Python, NumPy, PIL, pytest

---

### Task 1: Define the repair unit and its contract

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/trajectory_consolidation.py`
- Test: `offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py`

- [ ] Add a public helper for light repair that returns `(segments, meta)` and does not simplify, resample, or snap to foreground.
- [ ] Keep the rule limited to high-confidence merges: exact-touch or tiny-gap, near-collinear, foreground-supported when a bridge is needed.
- [ ] Record merge count in metadata so downstream summaries can report what happened.

### Task 2: Write the failing regression tests first

**Files:**
- Modify: `offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] Add a synthetic test where two collinear split segments should merge into one repaired segment.
- [ ] Add a synthetic test where an orthogonal corner contact must stay split.
- [ ] Add a hybrid-probe test for `postprocess_mode="raw_light_repair"` that checks summary mode, output files, and repaired segment count.
- [ ] Run only the new tests first and verify they fail for the expected missing-behavior reason.

### Task 3: Implement the minimal repair logic

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/trajectory_consolidation.py`

- [ ] Implement iterative best-candidate merging over raw segments with strict geometric thresholds.
- [ ] Reuse existing geometry helpers in the module so the new function shares distance/direction/foreground-support logic with existing consolidation code.
- [ ] Refresh geometry metadata after every accepted merge and preserve original point geometry otherwise.

### Task 4: Wire the repaired raw candidate into the probe

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/scripts/callirewrite_hybrid_probe.py`

- [ ] Add `raw_light_repair` as a supported `postprocess_mode`.
- [ ] Build repaired raw segments before ordering, then order the repaired candidate separately from the untouched raw candidate.
- [ ] Write `light_repair_rendered_execution.png` and include it in the contact-sheet comparison panel.
- [ ] Store repair metadata and candidate paths in `recovery_summary.json`.

### Task 5: Verify and generate a fresh batch for visual review

**Files:**
- Verify only

- [ ] Run: `python -m pytest offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py -q`
- [ ] Run: `python -m pytest offline_stroke_recovery_mvp/tests -q`
- [ ] Run: `python offline_stroke_recovery_mvp/scripts/callirewrite_hybrid_probe.py --postprocess-mode raw_light_repair`
- [ ] Inspect the new `visual_audit_contact_sheet.png` and compare `raw_rendered_execution` vs `light_repair_rendered_execution` directly before concluding whether the light repair helps.
