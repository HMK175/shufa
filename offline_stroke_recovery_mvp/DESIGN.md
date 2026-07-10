# Minimal Offline Prototype Design

## 1. Objective

Build a standalone offline prototype for:

```text
single-character black/white image
-> skeleton extraction
-> stroke-like path recovery
-> candidate writable order recovery
-> trial trajectory export
-> offline visualization
```

The first version is geometry-first. It should recover a trajectory that looks
draw-able and visually plausible, even if it is not yet the true historical
stroke order.

## 2. Design principles

1. Improve existing methods instead of inventing a brand-new route.
2. Prefer methods with public code when possible.
3. Prefer small deterministic modules over a training-heavy stack in phase 1.
4. Keep the route fully offline and independent from robot execution.
5. Treat image results as human-audit outputs, not metric-only outputs.

## 3. Scope and non-scope

### In scope

- single-character binary image input
- simple font glyphs and rendered black/white images
- skeleton extraction
- cleanup and topology repair
- graph path extraction
- candidate writable order
- trial CSV export
- debug figures and human-audit checklist

### Out of scope

- real stroke-width/pressure control
- robot workspace mapping
- CoppeliaSim
- AUBO
- SDK motion commands
- natural language planner
- multi-character writing layout
- full cursive / grass-script priority

## 4. Route choice

### Primary route

Use a deterministic graph pipeline inspired mainly by Wu 2024:

```text
image -> binary mask -> skeleton -> topology nodes -> segments -> candidate order
```

### External code preference

Use CalliRewrite as the first public-code comparison route:

- inspect its coarse sequence extraction representation
- compare whether its recovered order can be evaluated on the same small sample
  set
- do not integrate its RL finetuning stage in MVP phase 1

### Why not use the legacy route as the baseline

`code/legacy_image_skeleton_rl_route/` remains useful as failure evidence and
local inspiration, but not as the main baseline:

- repository history already judges its end-to-end effect as weak
- recent route decisions explicitly treat raw skeleton pulling as risky
- this thread needs a cleaner standalone design

## 5. Reuse plan inside this repository

The standalone MVP should reuse logic patterns from these local files:

- `experiments/llm_style_trajectory/src/font_outline_basis_feasibility.py`
  - image render / mask / lightweight skeleton fallback
- `experiments/llm_style_trajectory/src/font_skeleton_cleanup_prototype.py`
  - connected-component cleanup, spur pruning, endpoint merging
- `experiments/llm_style_trajectory/src/font_skeleton_path_extraction_prototype.py`
  - graph segment extraction
- `experiments/llm_style_trajectory/src/font_skeleton_stroke_ordering_prototype.py`
  - candidate writable ordering and merge heuristics

Reuse should happen by selective copying/refactoring into a new folder, not by
binding the standalone MVP back into the planner mainline.

## 6. Proposed folder structure

```text
offline_stroke_recovery_mvp/
  README.md
  ROUTE_SURVEY.md
  DESIGN.md
  IMPLEMENTATION_PLAN.md
  configs/
    sample_chars.json
  src/
    preprocess.py
    skeleton.py
    cleanup.py
    graph_extract.py
    ordering.py
    exporters.py
    visualize.py
    run_pipeline.py
  tests/
    test_preprocess.py
    test_skeleton.py
    test_cleanup.py
    test_graph_extract.py
    test_ordering.py
    test_run_pipeline.py
  outputs/
    .gitkeep
```

## 7. Module boundaries

### 7.1 `preprocess.py`

Responsibility:

- load a single image
- normalize foreground/background polarity
- resize/crop/pad to a stable internal resolution
- optional denoise and binarize

Output:

- boolean mask
- metadata about image size and bbox

### 7.2 `skeleton.py`

Responsibility:

- convert binary mask to a centerline skeleton
- expose multiple skeleton modes if needed:
  - `skimage`
  - local ridge fallback
- compute topology summary

Output:

- skeleton bitmap
- endpoint count
- branch count
- component count

### 7.3 `cleanup.py`

Responsibility:

- remove tiny components
- prune short spur branches
- optionally merge extremely near endpoints

Output:

- cleaned skeleton
- stats for what changed

### 7.4 `graph_extract.py`

Responsibility:

- convert skeleton pixels into graph segments
- identify node types:
  - endpoint
  - branch node
  - chain point
- extract stroke-like polyline candidates

Output:

- segment list
- segment lengths
- component grouping

### 7.5 `ordering.py`

Responsibility:

- recover a conservative `candidate writable order`
- minimize large jumps
- prefer longer, simpler segments first within a component
- use local merge heuristics when two segments are almost connected and their
  direction is compatible

Important:

- this is not yet claimed as the true calligraphic stroke order
- output naming should reflect that: `candidate`, `trial`, `stroke_like`

### 7.6 `exporters.py`

Responsibility:

- write a trial CSV
- write summary JSON
- write compact manifest CSV

Output filenames should avoid pretending to be mainline files such as
`trajectory.csv`.

Recommended names:

- `trial_ordered_trajectory.csv`
- `recovery_summary.json`
- `recovery_manifest.csv`

### 7.7 `visualize.py`

Responsibility:

- generate all figures needed for manual inspection

Minimum figures per sample:

1. original input image
2. raw skeleton
3. cleaned skeleton
4. segment-index overlay
5. candidate-order overlay
6. final trajectory figure

### 7.8 `run_pipeline.py`

Responsibility:

- command-line entry point for the whole standalone MVP
- one sample or a small batch
- writes one self-contained output folder

## 8. Input and output contract

### Input

- image path
- optional char label
- optional threshold / cleanup parameters

### Output

For each sample:

- raw + cleaned skeleton figures
- segment and order figures
- trial ordered trajectory CSV
- summary JSON

For batch run:

- manifest CSV
- batch report markdown
- visual audit checklist

## 9. Initial sample set

The first pass should stay intentionally small:

- `人`
- `山`
- `中`
- `永`

Reason:

- simple topology
- enough variation to expose branch and ordering problems
- manageable for repeated human visual audit

## 10. Success criteria

The MVP is considered successful if:

1. the full offline pipeline runs on the initial small sample set
2. each sample produces a non-empty trial trajectory
3. the order figure and trajectory figure are visually interpretable
4. obvious path jumps or catastrophic segment fragmentation are reduced
5. outputs are clearly labeled as `trial` or `candidate`

## 11. Human-audit gate

This route must preserve a visual gate.

Metrics help, but they are not enough for:

- naturalness
- whether a path still looks writable
- whether a merge looks forced
- whether a branch resolution looks visually wrong

Every batch report should include labels such as:

- `promising`
- `risky_needs_manual_check`
- `failed`

## 12. Planned route progression

### Phase 1

Deterministic offline pipeline only.

### Phase 2

Compare the local deterministic pipeline with CalliRewrite's public coarse
sequence extraction output on a very small sample.

Comparison protocol:

- keep CalliRewrite in a separate external checkout/environment
- do not vendor external code into this MVP folder
- run the same small binary glyph sample set through both routes
- compare local `candidate_order.png`, `final_trajectory.png`, and
  `batch_report.md` against CalliRewrite coarse extraction outputs
- require human visual inspection before claiming either route is better

Go criteria:

- the external route is reproducible locally
- dependencies and checkpoints are practical enough to rerun
- outputs are visually clearer or more writable on the same samples
- the coarse sequence can be mapped into a stroke-like path representation

No-go criteria:

- environment setup is too heavy for repeated offline experiments
- required checkpoints or preprocessing assumptions are missing
- outputs are not clearly better or are hard to interpret
- the comparison requires RL finetuning, robot control, or real execution

### Phase 3

If the local route is stable, improve branch handling and order heuristics using
Wu-style topology logic and VMA-inspired centerline refinements.

### Explicitly deferred

- true brush dynamics
- RL finetuning
- real robot control
