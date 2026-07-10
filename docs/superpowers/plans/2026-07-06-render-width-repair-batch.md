# Render Width Repair Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the fourth-chapter offline render quality by fixing anchored frame-corner overshoot, variable-width dropout artifacts, and missing render-subpath reuse in the current hybrid visualizer.

**Architecture:** Keep the position layer mostly unchanged and repair the render layer in place. Extend `visualize.py` so anchored corners can render controlled tangential overshoot, add width-profile repair for short dropouts and attached-start spikes, and reuse existing source-id subpaths more consistently from `callirewrite_hybrid.py`.

**Tech Stack:** Python, pytest, numpy, PIL

---

### Task 1: Add failing tests for corner extension and width-profile repair

**Files:**
- Modify: `offline_stroke_recovery_mvp/tests/test_visualize.py`
- Test: `offline_stroke_recovery_mvp/tests/test_visualize.py`

- [ ] Add one synthetic test for anchored orthogonal frame corners that expects nonzero endpoint extension metadata.
- [ ] Add one synthetic test for repairing a short internal width dropout between two stable thick runs.
- [ ] Add one synthetic test for clamping an attached endpoint spike without flattening the whole profile.
- [ ] Run the targeted visualize tests and confirm they fail first.

### Task 2: Implement anchored-corner extension and width repair helpers

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/visualize.py`
- Test: `offline_stroke_recovery_mvp/tests/test_visualize.py`

- [ ] Extend endpoint-cap policy records with per-end tangential extension lengths.
- [ ] Add a helper that detects anchored orthogonal corners and assigns small outward extension.
- [ ] Apply endpoint extension before rendering both constant-width and variable-width execution polylines.
- [ ] Add a helper that fills short interior width dropouts.
- [ ] Add a helper that clamps attached-start width spikes more aggressively than the current anchored taper.
- [ ] Run the targeted visualize tests and confirm they pass.

### Task 3: Restore render subpaths for more candidate families

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/callirewrite_hybrid.py`
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`
- Test: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] Reuse the existing source-id render-subpath map for `makemeahanzi` and `raw_light_repair` candidate segment families before candidate rendering.
- [ ] Add a regression test that confirms merged candidate segments can carry reconstructed render subpaths.
- [ ] Run the targeted hybrid tests and confirm they pass.

### Task 4: Full verification and visual rerun

**Files:**
- Verify: `offline_stroke_recovery_mvp/tests`
- Verify: `offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/*`

- [ ] Run the full offline test suite.
- [ ] Rerun `callirewrite_hybrid_probe.py` on `yi,shi,kou,xin,yong,zhong`.
- [ ] Manually inspect the new contact sheet plus single-sample renders for `kou`, `shi`, `xin`, `yong`, and `zhong`.
