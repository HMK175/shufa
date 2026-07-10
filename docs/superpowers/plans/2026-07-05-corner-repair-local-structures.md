# Corner Repair Local Structures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative corner-repair rule for near-closed frame structures so `zhong/kou` corner junctions improve without regressing already-good samples.

**Architecture:** Keep the fix in the geometry layer by extending local structure repair inside `trajectory_consolidation.py`, limited to short endpoint neighborhoods with foreground support and tangent checks. Validate with real-sample tests for `zhong/kou`, then rerun hybrid visual output for manual inspection.

**Tech Stack:** Python, pytest, numpy, PIL

---

### Task 1: Reproduce and pin the frame-corner failure

**Files:**
- Modify: `offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py`
- Test: `offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py`

- [ ] Add a failing real-sample test for `zhong` or `kou` that captures the current near-closure corner defect in the local candidate path.
- [ ] Run the targeted pytest command and verify it fails for the expected geometric reason.

### Task 2: Implement conservative corner repair

**Files:**
- Modify: `offline_stroke_recovery_mvp/src/trajectory_consolidation.py`
- Test: `offline_stroke_recovery_mvp/tests/test_trajectory_consolidation.py`

- [ ] Implement the minimal corner-repair helper and wire it into the existing local repair flow.
- [ ] Keep the rule local: endpoint neighborhood only, same-component only, tangent-compatible only, foreground-supported only.
- [ ] Run the targeted test and verify it passes.

### Task 3: Regression protection and visual rerun

**Files:**
- Modify: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`
- Test: `offline_stroke_recovery_mvp/tests/test_callirewrite_hybrid.py`

- [ ] Add or adjust a hybrid-level regression check so `kou/yi/shi` do not regress while `zhong` corner repair becomes visible in candidate output.
- [ ] Run targeted hybrid tests and then the full offline suite.
- [ ] Rerun the hybrid probe batch for manual visual inspection.
