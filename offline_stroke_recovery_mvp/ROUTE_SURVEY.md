# Route Survey: Papers, Code Availability, and MVP Choice

## Goal

Choose a practical starting route for:

```text
single-character binary image
-> skeleton / stroke recovery
-> candidate writable trajectory
-> offline visualization
```

The user preference is explicit:

- prefer routes with existing public code
- GitHub availability is a strong positive
- avoid rebuilding everything from scratch

## Shortlist

### 1. CalliRewrite (ICRA 2024)

- Paper:
  [arXiv 2405.15776](https://arxiv.org/abs/2405.15776)
- Project page:
  [luoprojectpage.github.io/callirewrite](https://luoprojectpage.github.io/callirewrite/)
- Code:
  [github.com/LoYuXr/CalliRewrite](https://github.com/LoYuXr/CalliRewrite)

What it gives:

- direct "image to writing behavior" framing
- public code and checkpoints workflow
- explicit coarse sequence extraction stage
- explicit fine control stage

Why it is attractive:

- best confirmed open-source availability among the shortlisted routes
- conceptually closest to "recover plausible writing order from image"

Why it is not the first implementation backbone:

- heavy dependency stack
- two-environment setup
- training/checkpoint assumptions
- includes RL/tool-control logic that is outside this thread's MVP boundary

MVP role:

- first external benchmark to inspect and possibly adapt at the `coarse sequence
  extraction` level
- not the first codebase to wire directly into the offline MVP

### 1b. StrokeExtraction (AAAI 2023 public-code candidate)

- Code:
  [github.com/MengLi-l1/StrokeExtraction](https://github.com/MengLi-l1/StrokeExtraction)

What it may give:

- Chinese-character stroke extraction / stroke-instance segmentation style
  outputs
- a second public-code candidate that is less tied to robot control than
  CalliRewrite

Why it is attractive:

- likely closer to "separate the character image into stroke regions" than a
  generic SVG/vectorization project
- could provide per-stroke masks that our local code can skeletonize and export
  as candidate paths

Current limitation:

- not yet locally cloned in this workspace because network approval failed
- expected to require PyTorch-era dependencies and manually downloaded weights
- likely does not directly solve true stroke order or pen-up sequencing

MVP role:

- second external candidate after CalliRewrite
- evaluate as a stroke-region source, then decide whether mask-to-centerline
  conversion is worth doing

### 2. Wu et al. Stroke Extraction and Trajectory Planning (ICIRA 2024 / LNCS 2025)

- Local summary:
  `references/summaries/stroke_extraction_trajectory_planning_icira2024.md`
- Local reference list:
  `references/REFERENCE_LIST.md`
- DOI:
  `10.1007/978-981-96-0774-7_23`

What it gives:

- the closest classical pipeline to this thread
- corner/connected-component preprocessing
- skeleton feature-point classification
- dynamic path planning over skeleton topology

Why it is attractive:

- most suitable conceptual backbone for a geometry-first offline MVP
- easier to trim down into a deterministic prototype

Current limitation:

- no public GitHub implementation was confirmed in this scan

MVP role:

- primary algorithmic reference for the first standalone prototype

### 3. Robotic Writing of Arbitrary Unicode Characters Using Paintbrushes (Robotics 2023)

- Local summary:
  `references/summaries/arbitrary_unicode_2023.md`
- Local reference list:
  `references/REFERENCE_LIST.md`
- DOI:
  `10.3390/robotics12030072`

What it gives:

- medial-axis / centerline style thinking from glyph outlines
- explicit stroke extraction stage before trajectory generation

Why it is attractive:

- useful for strengthening the skeleton extraction stage
- good reference when the plain pixel skeleton becomes unstable

Current limitation:

- no public GitHub implementation was confirmed in this scan
- paper scope is broader than this MVP and includes brush-model concerns we do
  not need yet

MVP role:

- secondary reference for the skeleton and stroke-extraction stage

### 4. Image-Based Imitation Learning Framework for Robotic Writing Tasks (M2VIP 2024)

- Local reference list:
  `references/REFERENCE_LIST.md`
- local PDF status entry:
  `references/PDF_STATUS.md`
- DOI:
  `10.1109/M2VIP62491.2024.10746145`

What it gives:

- image-to-trajectory imitation framing
- dynamic representation rather than pure graph heuristics

Why it is not first:

- weaker fit for a small deterministic MVP
- no confirmed public GitHub implementation from this scan

MVP role:

- later comparison route only

## Local code already worth reusing

Even though the old archived route is not a good baseline, the repository
already contains useful recent diagnostic prototypes:

- `experiments/llm_style_trajectory/src/font_outline_basis_feasibility.py`
- `experiments/llm_style_trajectory/src/font_skeleton_cleanup_prototype.py`
- `experiments/llm_style_trajectory/src/font_skeleton_path_extraction_prototype.py`
- `experiments/llm_style_trajectory/src/font_skeleton_stroke_ordering_prototype.py`

These are the strongest near-term assets for building the standalone offline
MVP because they already match this repository's output style and testing style.

## Decision

### Recommended primary route

Use a `Wu-style deterministic graph pipeline` as the implementation backbone,
but build it by refactoring and consolidating the local recent prototypes rather
than reviving `legacy_image_skeleton_rl_route`.

### Recommended external open-source reference

Use `CalliRewrite` as the first external public-code reference:

- inspect its coarse sequence extraction stage
- compare its output representation with the local path-segment prototypes
- do not pull in RL/tool-control logic during MVP phase 1

## External benchmark hook

Phase 1 keeps external code out of the local MVP. `CalliRewrite` should be
treated as a reproducibility and visual-comparison benchmark, not as a vendored
dependency.

### Benchmark rule

- `CalliRewrite` is the first public-code route to evaluate.
- Do not copy, vendor, or modify its repository inside
  `offline_stroke_recovery_mvp/` during phase 1.
- Run any external reproduction in a separate checkout/environment.
- Compare it against the same small sample set used by the deterministic local
  route.
- Judge outputs by side-by-side PNG inspection and the batch audit report, not
  by scalar metrics alone.

### Checkpoints

1. Can the CalliRewrite coarse extraction stage run locally on the small sample
   set without training a new model?
2. Does its recovered sequence/order look more writable than the deterministic
   local output on the same input images?
3. Are its dependencies, checkpoints, and runtime assumptions practical enough
   for repeatable local reproduction?
4. Are the resulting figures easy to interpret next to
   `candidate_order.png` and `final_trajectory.png` from this MVP?

### Go / no-go criteria

Go:

- the external route is locally reproducible
- dependencies and checkpoints are documented enough to rerun
- small-sample outputs are visually better or expose a concrete local weakness
- output representation can be mapped to a coarse stroke-like sequence for
  comparison

No-go:

- environment setup is too heavy for repeated local experiments
- checkpoints or preprocessing assumptions are missing
- outputs are hard to interpret
- visual quality is not clearly better than the deterministic MVP
- the route requires RL, robot control, or training work outside this thread's
  offline boundary

### Practical interpretation

The best near-term route is not:

- "copy one paper fully"

It is:

- implement a small deterministic offline pipeline locally
- keep it compatible with this repository's figure/report habits
- use `CalliRewrite` as the first public-code comparison target
- use `Wu 2024` and `VMA 2023` as algorithmic references when refining the
  skeleton-to-path logic
