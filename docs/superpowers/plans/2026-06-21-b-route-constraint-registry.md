# B Route Constraint Registry & Gated Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a trial-only B-route constraint registry that unifies H2 font constraints, section constraints, and prior B-route evidence into a single gating entry point, then run a very small registry-gated probe for 山/lishu and 风/lishu.

**Architecture:** The registry is a read-only evidence pack: it classifies constraints into usable, reference-only, and blocked buckets, then records a strategy selection per sample. The probe does not invent a new adaptation algorithm; it only demonstrates how registry-gated selection can choose between component-first safe adaptation and fallback-first section guidance, using existing trial evidence as comparison material.

**Tech Stack:** Python, JSON/CSV/Markdown reports, matplotlib, pytest.

---

### Task 1: Write the registry and probe tests first

**Files:**
- Create: `experiments/llm_style_trajectory/tests/test_b_route_constraint_registry.py`
- Create: `experiments/llm_style_trajectory/tests/test_b_route_registry_gated_probe.py`

- [x] **Step 1: Write the failing test**

```python
from pathlib import Path
import json
import csv


def test_b_route_constraint_registry_builds_expected_samples(tmp_path):
    from b_route_constraint_registry import run_b_route_constraint_registry

    result = run_b_route_constraint_registry(output_dir=tmp_path / "b_route_registry", copy_to_paper=False)

    out_dir = Path(result["output_dir"])
    assert out_dir.exists()
    assert Path(result["summary_json"]).exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
    assert summary["status"] == "trial_only_not_used_by_default"
    assert summary["default_policy"] == "registry_gated_adaptation_only"
    assert len(summary["entries"]) == 2

    entries = {(item["char"], item["style"]): item for item in summary["entries"]}
    assert ("山", "lishu") in entries
    assert ("风", "lishu") in entries
    assert entries[("山", "lishu")]["strategy_selected"] == "component_first_safe"
    assert entries[("风", "lishu")]["strategy_selected"] == "fallback_first_reference_only"
    assert entries[("山", "lishu")]["human_review_required"] is True
    assert entries[("风", "lishu")]["fallback_used"] is True
    assert "bbox_aspect" in entries[("山", "lishu")]["usable_constraints"]
    assert "raw_skeleton_path" in entries[("山", "lishu")]["blocked_constraints"]


def test_b_route_registry_gated_probe_outputs_trial_only_comparisons(tmp_path):
    from b_route_registry_gated_probe import run_b_route_registry_gated_probe

    result = run_b_route_registry_gated_probe(output_dir=tmp_path / "b_route_probe", copy_to_paper=False)

    out_dir = Path(result["output_dir"])
    assert out_dir.exists()
    assert Path(result["summary_csv"]).exists()
    assert Path(result["report_md"]).exists()
    assert Path(result["manifest_csv"]).exists()

    rows = list(csv.DictReader(Path(result["summary_csv"]).open(encoding="utf-8-sig")))
    assert len(rows) == 2
    keys = {(row["char"], row["style"]): row for row in rows}
    assert ("山", "lishu") in keys
    assert ("风", "lishu") in keys
    assert all(row["stroke_count_preserved"] == "True" for row in rows)
    assert all(row["recommended_for_visual_followup"] == "True" for row in rows)
    assert all(float(row["max_point_shift_px"]) >= 0.0 for row in rows)
    assert all(row["registry_strategy"] in {"component_first_safe", "fallback_first_reference_only"} for row in rows)
    report = Path(result["report_md"]).read_text(encoding="utf-8")
    assert "registry-gated" in report
    assert "trial-only" in report
    assert "not_used_by_default" in report
    assert "山/lishu" in report
    assert "风/lishu" in report
```

- [x] **Step 2: Run the tests and confirm they fail for missing implementation**

Run: `python -m pytest experiments\\llm_style_trajectory\\tests\\test_b_route_constraint_registry.py experiments\\llm_style_trajectory\\tests\\test_b_route_registry_gated_probe.py -q`
Expected: FAIL with missing module errors.

- [x] **Step 3: Do not implement code yet until failure is observed**

---

### Task 2: Implement the B-route registry package

**Files:**
- Create: `experiments/llm_style_trajectory/src/b_route_constraint_registry.py`
- Modify: `experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`
- Modify: `CURRENT_PROJECT_GUIDE.md`
- Modify: `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`
- Modify: `EXPERIMENT_RECORD.md`
- Modify: `PROJECT_LOG.md`
- Create: `experiments/llm_style_trajectory/outputs/paper_figures/b_route_constraint_registry_index.md`

- [ ] **Step 1: Write the minimal implementation**

```python
# implement run_b_route_constraint_registry() to:
# - load existing H2 font reference constraints JSON
# - load existing section constraints package JSON
# - synthesize a registry for only 山/lishu and 风/lishu
# - classify constraints into usable / reference-only / blocked
# - assign strategy_selected, section_strategy, fallback_used, max_shift_cap,
#   human_review_required, recommended_next_use
# - write JSON, CSV, report, manifest, and optional figures
```

- [ ] **Step 2: Add the paper index entry and project note**

```markdown
- B-route constraint registry / gating rule: trial-only registry-gated adaptation entry point. Unifies H2 font constraints and section constraints into a read-only evidence pack; no point movement by default.
```

- [ ] **Step 3: Run the registry test until green**

Run: `python -m pytest experiments\\llm_style_trajectory\\tests\\test_b_route_constraint_registry.py -q`
Expected: PASS.

---

### Task 3: Implement the registry-gated probe

**Files:**
- Create: `experiments/llm_style_trajectory/src/b_route_registry_gated_probe.py`
- Create: `experiments/llm_style_trajectory/outputs/paper_figures/b_route_constraint_registry_index.md`
- Modify: `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`
- Modify: `EXPERIMENT_RECORD.md`
- Modify: `PROJECT_LOG.md`
- Modify: `experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`

- [ ] **Step 1: Write the minimal implementation**

```python
# implement run_b_route_registry_gated_probe() to:
# - read the registry JSON
# - for 山/lishu and 风/lishu, select the registry strategy
# - reuse existing trial evidence only for comparison
# - emit a tiny summary CSV / report / manifest / figures
# - keep stroke_count preserved and trial-only flags explicit
```

- [ ] **Step 2: Run the probe test until green**

Run: `python -m pytest experiments\\llm_style_trajectory\\tests\\test_b_route_registry_gated_probe.py -q`
Expected: PASS.

---

### Task 4: Wire up docs and publish the index files

**Files:**
- Modify: `experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`
- Modify: `CURRENT_PROJECT_GUIDE.md`
- Modify: `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`
- Modify: `EXPERIMENT_RECORD.md`
- Modify: `PROJECT_LOG.md`

- [ ] **Step 1: Add concise summary entries for the new registry layer**

```markdown
The B route now uses a registry-gated adaptation entry point. Constraint sources are unified into a read-only registry; raw skeleton paths remain blocked. The default route is still A, and B/C stay trial-only unless manually promoted.
```

- [ ] **Step 2: Ensure no default pipeline behavior changes**

Run: `rg -n "registry-gated|trial_only_not_used_by_default|not_used_by_default" CURRENT_PROJECT_GUIDE.md experiments\\llm_style_trajectory\\outputs\\paper_figures\\paper_experiment_index.md`
Expected: entries present in docs only.

---

### Task 5: Final verification and protection checks

**Files:**
- None

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest experiments\\llm_style_trajectory\\tests -q`
Expected: all tests pass.

- [ ] **Step 2: Verify registry JSON is valid**

Run: `python -m json.tool experiments\\llm_style_trajectory\\outputs\\b_route_constraint_registry_<timestamp>\\b_route_constraint_registry.json`
Expected: pretty-printed JSON, exit 0.

- [ ] **Step 3: Check shared data and legacy are untouched**

Run:
```powershell
Test-Path code\data\makemeahanzi\graphics.txt
Test-Path code\legacy_image_skeleton_rl_route\scripts\stroke.py
Test-Path code\legacy_image_skeleton_rl_route\scripts\pipeline.py

git diff --name-only -- code\data code\legacy_image_skeleton_rl_route
```
Expected: all Test-Path commands return `True`; git diff prints nothing.

- [ ] **Step 4: Commit the registry layer once green**

```bash
git add experiments/llm_style_trajectory/src/b_route_constraint_registry.py experiments/llm_style_trajectory/src/b_route_registry_gated_probe.py experiments/llm_style_trajectory/tests/test_b_route_constraint_registry.py experiments/llm_style_trajectory/tests/test_b_route_registry_gated_probe.py experiments/llm_style_trajectory/outputs/paper_figures/b_route_constraint_registry_index.md experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md CURRENT_PROJECT_GUIDE.md LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md EXPERIMENT_RECORD.md PROJECT_LOG.md
git commit -m "feat: add b-route constraint registry and gated probe"
```
