# Offline Stroke Recovery MVP

This folder is a dedicated design package for the independent route:

```text
font image / binary glyph image
-> skeleton extraction
-> stroke-like path recovery
-> candidate writable order recovery
-> trial trajectory export
-> offline visualization + human audit
```

It is intentionally separate from:

- `experiments/llm_style_trajectory/` mainline
- `code/legacy_image_skeleton_rl_route/` archived route
- any CoppeliaSim / AUBO / SDK integration

## Scope

Current target:

1. single-character black/white input image
2. geometry-first recovery
3. candidate writable trajectory, not guaranteed true stroke order
4. offline figures and manual visual inspection only

Not in scope for this MVP:

- natural-language planner
- A-route / B-route hybrid expansion
- real robot
- CoppeliaSim
- SDK motion commands
- multi-character layout
- cursive-first recovery

## Why this folder exists

The repository already contains useful diagnostics and prototypes under
`experiments/llm_style_trajectory/src/`, but they are scattered and mixed with
the current planner-to-robot mainline. This folder defines a cleaner,
standalone MVP that can reuse the useful parts without re-entering the main
pipeline.

## Recommended route

The recommended MVP route is:

- use a `Wu-2024-style` graph-and-rules skeleton-to-path backbone
- borrow representation ideas from `CalliRewrite 2024`
- keep `CalliRewrite` as the first external open-source benchmark because its
  GitHub repository and project page are publicly available
- reuse local diagnostic prototypes for skeleton, cleanup, segment extraction,
  and stroke-like ordering

## Files

- `DESIGN.md`
  - final MVP design
- `ROUTE_SURVEY.md`
  - paper/code shortlist and route choice
- `IMPLEMENTATION_PLAN.md`
  - task-by-task build plan for the prototype
- `ENVIRONMENT_NOTES.md`
  - local runtime, sandbox, approval, and network troubleshooting notes

## Visual smoke benchmark

Batch runs write `manual_audit_sheet.csv` next to `batch_report.md`.
The sheet is a human visual inspection template for checking mask, skeleton,
segment, order, and trajectory images. Its manual fields are intentionally
blank by default; it is not an automatic quality judgement and should not be
used as a pass/fail score without looking at the images.

For a repeatable rerun on the existing clean single-glyph inputs plus a
side-by-side contact sheet:

```powershell
python .\offline_stroke_recovery_mvp\scripts\visual_smoke_probe.py
```

This writes a fresh timestamped batch under:

```text
offline_stroke_recovery_mvp/outputs/visual_smoke_probe_rerun/
```

Each batch includes:

- `batch_report.md`
- `manual_audit_sheet.csv`
- `visual_smoke_report.json`
- `visual_audit_contact_sheet.png`

The contact sheet is meant to make human review easier by lining up
`input_image.png`, `clean_skeleton.png`, and `final_trajectory.png` for each
sample in one place.

Important environment note:

- prefer a Python environment with `scikit-image` installed
- if `scikit-image` is missing, the local code falls back to a lightweight
  NumPy midpoint skeletonizer
- that fallback is useful for smoke coverage but can break crossing centers and
  over-fragment `shi` / `zhong`-like intersections

The active skeleton backend is written into each `recovery_summary.json` and
surfaced in `batch_report.md`.

If you want the visual smoke rerun to fail fast unless the proper skeleton
backend is active:

```powershell
python .\offline_stroke_recovery_mvp\scripts\visual_smoke_probe.py --min-segment-pixels 8 --require-skeleton-backend skimage_skeletonize
```

This is recommended when switching between environments, because the
`numpy_midpoint_fallback` can silently produce misleading crossing failures.

For the current low-complexity tuning pass, the most useful command is:

```powershell
python .\offline_stroke_recovery_mvp\scripts\visual_smoke_probe.py --min-segment-pixels 8
```

This keeps the same clean input set but asks the extractor to drop very short
segments before ordering while using the script's default endpoint-merge
ordering pass. On the current `yi/shi/kou/zhong/...` visual smoke set it
reduces obvious over-fragmentation, especially for `kou`.

The current graph extractor also applies a small pseudo-corner heuristic after
segment tracing. If thinning creates a uniquely short side stub at a box-like
corner, that point is treated as a pass-through bend instead of a true branch.
On the current visual smoke set this reduces false branch counts for `kou`
and `zhong`, while keeping short-spur `T` junctions as real branches.

The same graph stage now also folds a narrow hook-like case back into the main
path: if a branch has one short spur endpoint, one longer endpoint, and one
continuation arm toward another branch, the short spur is treated as local
thinning noise rather than a full branch split. On the current smoke set this
reduces over-segmentation around the lower trunk of `yong`.

The current ordering stage also handles one narrow junction case: if a merged
segment already forms a closed loop and its anchor point lies inside another
segment, the through-segment is split at that anchor so the loop can be placed
between the two halves. On the current smoke set this removes the long pen-up
jump for `zhong` without changing the global robot boundary of this MVP.

The current first-pass audit also distinguishes a second narrow case: if a
single-component result contains exactly two ordered open strokes that share an
interior crossing point, a large pen-up jump between their endpoints is treated
as structural rather than automatically risky. On the current smoke set this
keeps `shi` in the promising bucket without hiding the actual jump length in
the summary JSON or batch report.

The audit summary now also splits pen-up jumps into two buckets:

- `cross_component_*`
  - jumps caused by moving between disconnected components
- `internal_*`
  - jumps that happen inside one connected component after segmentation

For small component counts and small segment counts, the code also computes a
bounded exact lower bound for both cases. This lets the report distinguish
"large because the current topology is disconnected" from "large because the
ordering is still avoidably bad". On the current smoke set this promotes
`xin` to promising, because its large jumps are almost entirely structural
cross-component moves, while `yong` stays risky because it still has large
within-component jumps.

The last local-only continuation pass is intentionally bounded. It now inserts
one small `trajectory_consolidation` step after ordering:

- merge same-component segments only when they already share an endpoint or a
  very small gap
- simplify tiny zig-zags while preserving endpoints
- resample the final polyline at a fixed step for cleaner trajectory display

This is the final local-only attempt for the current MVP. If the difficult
three-sample probe still leaves `yong` visually fragmented, the route should
stop and switch to an external-visual-source plus local-writability hybrid
instead of adding more special-case local heuristics.

Run that bounded stop-gate probe with:

```powershell
python .\offline_stroke_recovery_mvp\scripts\local_method_final_attempt_probe.py
```

It writes a timestamped batch plus:

- `final_attempt_gate_report.json`
- `visual_audit_contact_sheet.png`

under:

```text
offline_stroke_recovery_mvp/outputs/local_method_final_attempt/
```

For small component counts and small within-component segment counts, the
ordering stage now also replaces purely greedy continuation with a bounded
exact path search that keeps the current lead seed fixed and optimizes the
remaining order and orientations by jump cost. On the current smoke set this
substantially reduces `xin` pen-up jumps and gives a smaller but real
improvement on `yong`, while keeping the older conservative seed preference.

## CalliRewrite external baseline

`src/callirewrite_adapter.py` adds a thin adapter for evaluating CalliRewrite as
an external baseline. It does not vendor CalliRewrite code and does not run its
RL, calibration, CoppeliaSim, AUBO, SDK, or robot execution stages.

Expected workflow:

1. keep a separate external checkout, for example
   `external_repos/CalliRewrite/`
2. use the adapter to inspect whether `seq_extract/test.py` and checkpoints are
   present
3. run CalliRewrite `seq_extract` manually in its own environment if ready
4. convert resulting `.npz` coarse sequences into:
   - `callirewrite_recovered_strokes.json`
   - `trial_ordered_trajectory.csv`
   - `callirewrite_summary.json`

See `CALLIREWRITE_ADAPTER.md` for the exact commands and boundaries.

After the workspace-local CalliRewrite environment is installed, the repeatable
offline commands are:

```powershell
.\offline_stroke_recovery_mvp\scripts\run_callirewrite_probe.ps1
.\offline_stroke_recovery_mvp\scripts\convert_callirewrite_outputs.ps1
```

After conversion, the smallest local hybrid postprocess can be run with:

```powershell
python .\offline_stroke_recovery_mvp\scripts\callirewrite_hybrid_probe.py
```

For a structure-prior comparison pass, the same probe also exposes a
MakeMeAHanzi-guided regroup mode. It keeps the CalliRewrite geometry as the
visual source and uses MakeMeAHanzi medians only to regroup over-split segments:

```powershell
python .\offline_stroke_recovery_mvp\scripts\callirewrite_hybrid_probe.py --postprocess-mode makemeahanzi_regroup
```

An `auto` mode is also available. It keeps `local` outputs when they are already
continuous enough, and only switches to the MakeMeAHanzi regroup branch when the
local result is still visibly over-segmented:

```powershell
python .\offline_stroke_recovery_mvp\scripts\callirewrite_hybrid_probe.py --postprocess-mode auto
```

To avoid accidentally reusing stale `converted/` artifacts, the recommended
repeatable command is now:

```powershell
python .\offline_stroke_recovery_mvp\scripts\callirewrite_refresh_probe.py
```

This one-shot refresh command:

- reads the latest CalliRewrite `seq_extract` `.npz` files
- rewrites `offline_stroke_recovery_mvp/outputs/callirewrite_runtime_probe/converted/`
- immediately runs the local hybrid visual probe on the refreshed conversion

Use the older two-step conversion plus hybrid commands only when you explicitly
want to inspect the intermediate converted files without launching a fresh
hybrid batch yet.

This keeps CalliRewrite as the external visual-recovery source, then applies
the local continuity-oriented postprocess and manual-audit outputs. A fresh
timestamped batch is written under:

```text
offline_stroke_recovery_mvp/outputs/callirewrite_hybrid_probe/
```

Each hybrid batch includes:

- `batch_report.md`
- `manual_audit_sheet.csv`
- `visual_audit_contact_sheet.png`
- `callirewrite_hybrid_probe_report.json`
- per-sample `candidate_order.png`
- per-sample `callirewrite_source_trajectory.png`
- per-sample `final_trajectory.png`
- per-sample `trial_ordered_trajectory.csv`

This hybrid route is still offline-only. It is for visual comparison and
candidate writability inspection, not for claiming true stroke order or robot
execution readiness.

### Recent CalliRewrite-hybrid tuning note (2026-07-10)

Recent work stayed on the `zhong` visual-cleanup branch before moving on to
`xin` and broader shared-render tuning. The main changes were:

- `src/visualize.py`
  - attached-endpoint width clamping now expands its taper window when the
    local peak sits one or two sampled points behind the endpoint instead of at
    the endpoint pixel itself
  - short attached single-source lead-in segments are slimmed more
    aggressively, which specifically reduces the fake blocky top lead-in on
    CalliRewrite `zhong`
- `src/callirewrite_hybrid.py`
  - `AUTO_LIGHT_REPAIR_LOCAL_VISUAL_ADVANTAGE_MIN` was relaxed from `0.03` to
    `0.025` so the `auto` selector still keeps `raw_light_repair` when the
    light-repair branch remains visibly cleaner than `local` but the gap falls
    just below the old margin after render cleanup

New regression coverage added in `tests/test_visualize.py`:

- `test_build_variable_width_profile_tames_real_zhong_light_repair_right_wall_tail_peak`
- `test_build_variable_width_profile_keeps_real_zhong_light_repair_top_lead_in_slender`

Verified after the above patch set:

```powershell
python -m pytest offline_stroke_recovery_mvp\tests\test_visualize.py -q
python -m pytest offline_stroke_recovery_mvp\tests\test_callirewrite_hybrid.py -q
```

Both suites passed in the final verification pass before this thread paused.

### Continuation result (2026-07-10)

The pending `zhong -> xin -> shared-render` pass was completed in the next
thread.

Additional shared-render changes in `src/visualize.py`:

- short attached single-source segments now use a target
  `path_length / diameter` ratio of `1.5`
- their minimum body scale can fall to `0.3`, which reduces false corner blobs
  such as the short `kou` closure bridge
- a visible short lead-in keeps its free cap when the path is long enough to
  read as a stroke, while a tiny near-dot lead-in still suppresses both caps
- the free tip of a short attached segment is tapered after straight-body
  regularization, so the taper is not accidentally flattened again
- long multi-source foldback strokes now clamp the local width peak around the
  strongest reversal before applying the existing tail taper; this reduces the
  oversized `xin` wogou turn without removing the hook

The `auto` selector margin for keeping a visibly better light-repair result was
relaxed from `0.025` to `0.02`. After the `zhong` tip cleanup, the measured
light-repair advantage over `local` was about `0.02499`; keeping the old
threshold would have selected the visibly rougher local branch because of a
very small metric-boundary change.

New or tightened regression coverage in `tests/test_visualize.py` includes:

- preserving the real `zhong` light-repair lead-in free cap
- tapering that lead-in's free tip while keeping its attached end substantial
- reducing the real `kou` short-corner-bridge body width
- clamping the real `xin` component-mix wogou width at the foldback turn

Final verification:

```text
test_visualize.py: 47 passed
test_callirewrite_hybrid.py: 40 passed
offline_stroke_recovery_mvp/tests: 246 passed
```

Final six-sample visual sweep:

```text
outputs/callirewrite_hybrid_shared_render_sweep_final/
  callirewrite_hybrid_batch_20260710_133353_434000/
```

The sweep reports five `promising` samples and one
`risky_needs_manual_check` sample (`zhong`). This is not an automatic quality
claim: the contact sheet and per-sample renders still require human inspection.

Current qualitative status:

- `zhong`
  - the fake blocky top lead-in is slimmer and has a tapered free tip
  - `auto` consistently keeps `raw_light_repair`
  - the mouth frame still contains CalliRewrite polygonal/corner artifacts, so
    it remains unsuitable as a frozen final figure without manual acceptance
- `xin`
  - the component-mix wogou turn peak is reduced from a large local blob to a
    smoother transition while preserving the terminal hook
  - the batch remains a candidate visual result, not recovered true stroke
    order
- shared rendering
  - the `kou` short closure bridge is less dominant
  - no further global endpoint/corner heuristic was added after the final
    sweep because the remaining peaks overlap genuine source-image serifs and
    need sample-specific human judgement

Recommended review artifact:

```text
outputs/callirewrite_hybrid_shared_render_sweep_final/
  callirewrite_hybrid_batch_20260710_133353_434000/
  visual_audit_contact_sheet.png
```

### Pointed `xin`, three-stroke `kou`, and reusable primitives (2026-07-10)

The next continuation completed the first three approved items. The held-out
unseen-character evaluation remains deferred until the visible results are
accepted.

Implemented changes:

- `src/visualize.py`
  - a designated long-foldback terminal can now taper monotonically to an
    exact zero-width endpoint
  - the raster renderer exempts only that pointed endpoint from the normal
    minimum-radius rule and sharpens its final cross-section instead of adding
    a round cap
  - serialized primitive relative-width profiles can be blended with the
    target image's foreground-derived width profile
- `src/makemeahanzi_prior.py`
  - `kou` is rebuilt as exactly three writable strokes:
    `shu`, continuous `hengzhe`, and closing `heng`
  - short gaps inside the second stroke are bridged only when the measured gap
    is at most `10 px`; larger gaps reject the candidate
  - intersection behavior is represented by bounded centerline overshoot:
    the top horizontal extends left through the first vertical, the first
    vertical extends below the closing horizontal, and the closing horizontal
    extends through the right wall
- `src/stroke_primitives.py`
  - adds normalized `heng`, `shu`, `hengzhe`, and `gou` representations
  - supports arc-length width resampling, reversal, `hengzhe` composition, and
    median-preserving width transfer
- `src/callirewrite_hybrid.py`
  - extracts the development `heng` reference from `yi` and `shu` from `shi`
  - removes intersection-induced width outliers before registering a reference
    primitive; for example, the crossing inside `shi` is not transferred as a
    false `3.5x` brush-width feature
  - registers the selected `xin` long foldback as a `gou` primitive whose end
    role is `pointed` and whose last relative width is `0.0`
  - adds and exports the `structure_primitive` candidate and prefers it for
    `kou` when it stays within `0.10` rendered IoU of the best existing route

The original design used a `0.05` similarity tolerance. The real `kou` probe
showed that the old light-repair route scored higher mainly because pixel IoU
rewards the source's closed-frame silhouette even though its stroke topology
is the behavior being corrected. Building the structure from the less
distorted light-repair centerlines and adding a `2 px` top-left overshoot raised
the structural candidate from about `0.589` to `0.762`; the best light-repair
score was about `0.820`. The final drop is about `0.058`, so the bounded
topology-aware tolerance is `0.10`. This is still subject to manual inspection,
not an automatic quality claim.

Final focused batch:

```text
outputs/pointed_tip_kou_primitives/
  callirewrite_hybrid_batch_20260710_152920_258973/
```

Recommended artifacts:

```text
visual_audit_contact_sheet.png
xin/rendered_execution.png
xin/playback_contact_sheet.png
kou/structure_primitive_rendered_execution.png
kou/playback_contact_sheet.png
```

Manual visual status:

- `xin`
  - the wogou terminal is now a visible point rather than a round terminal with
    measurable width
  - the hook height and overall source geometry still require human judgement
- `kou`
  - playback now clearly shows three strokes rather than four independent sides
  - the top horizontal crosses the left vertical and the lower endpoints remain
    visible past their intersections
  - the top-right pressure/corner remains visually heavy; the new result fixes
    the structural cause but should not yet be described as a final natural
    brush reconstruction
  - the filled silhouette is still visually enclosure-like because the glyph
    itself is enclosed; the topology improvement is verified from the ordered
    centerlines and playback panels, not from the black silhouette alone

Verification after the final patch set:

```text
test_stroke_primitives.py: 6 passed
test_makemeahanzi_prior.py: 15 passed
test_visualize.py: 50 passed
test_callirewrite_hybrid.py: 44 passed
offline_stroke_recovery_mvp/tests: 260 passed
```

The two focused samples both report `promising`, but every trajectory and
render still requires manual acceptance. These development characters are not
evidence of unseen-character generalization; that evaluation is deliberately
the deferred fourth item.

## StrokeExtraction external candidate

`src/stroke_extraction_adapter.py` adds a thin audit/report adapter for trying
StrokeExtraction as a second public-code candidate. It does not vendor or run
the external project by itself.

Expected workflow:

1. keep a separate external checkout, for example
   `external_repos/StrokeExtraction/`
2. generate a feasibility report with
   `.\offline_stroke_recovery_mvp\scripts\write_stroke_extraction_report.ps1`
3. inspect whether the upstream checkout exposes a runnable inference command
   and local checkpoint files
4. if runnable, use it only for offline stroke-region/mask comparison before
   any local mask-to-trajectory conversion

See `STROKE_EXTRACTION_ADAPTER.md` for the exact command and boundaries.

For a local GPU feasibility check that does not require RHSEDB or checkpoints:

```powershell
python .\offline_stroke_recovery_mvp\scripts\stroke_extraction_cuda_smoke.py --batch-sizes 1,2,4
```

After RHSEDB, ContentNet, and CharNet/VGG weights are in place, a guarded
real-data SDNet smoke plus limited intermediate-data export is available:

```powershell
.\.venvs\stroke-extraction-cuda\Scripts\python.exe .\offline_stroke_recovery_mvp\scripts\stroke_extraction_training_smoke.py --sdnet-steps 2 --train-intermediate-samples 2 --test-intermediate-samples 2 --batch-size 2
```

This command is intentionally small-scale. It writes only:

- a temporary `sdnet_model.pth`
- `train/` and `test/` intermediate folders with a few `.npy` samples each
- `training_smoke_report.json`
- `metadata.json`

under:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_training_smoke/
```

It is a feasibility probe for the upstream SDNet stage and SegNet/ExtractNet
data preparation, not evidence that the full upstream training recipe is
practical on the local machine.

After the SDNet smoke dataset is in place, a guarded SegNet smoke is also
available:

```powershell
.\.venvs\stroke-extraction-cuda\Scripts\python.exe .\offline_stroke_recovery_mvp\scripts\stroke_extraction_segnet_smoke.py --batch-size 2 --max-steps 2
```

This command consumes:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_training_smoke/dataset_forSegNet_ExtractNet_RHSEDB_smoke/
```

and writes:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_segnet_smoke/
```

including a temporary `model.pth` and `segnet_smoke_report.json`.

Manual visual review artifacts for the current smoke run are written to:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_manual_review/
```

These review images are for human inspection only. They are not automatic
quality scores.

The final-stage ExtractNet smoke also writes its own review images to:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_extractnet_smoke/review/
```

The next offline prototype turns the ExtractNet smoke output into local
trajectory debug artifacts with adaptive mask cleanup and the existing
`run_pipeline` stack:

```powershell
.\.venvs\stroke-extraction-cuda\Scripts\python.exe .\offline_stroke_recovery_mvp\scripts\stroke_extraction_trajectory_smoke.py
```

It writes a fresh batch under:

```text
offline_stroke_recovery_mvp/outputs/stroke_extraction_trajectory_smoke/
```

The generated trajectories are still for human inspection only. The current
smoke run is promising on the train sample and still risky on the test sample,
so the output should be treated as a noisy baseline, not a final recovery
method.

### `kou` skeleton B-plan audit (2026-07-10)

The focused B-plan audit traced the real top-right loop to an untrimmed overlap
prefix at the start of the second (`hengzhe`) stroke. The accepted focused run
trimmed `16` points from that prefix, then retained exactly `1`
horizontal-to-vertical axis transition. The bounded leg regularization reported
a maximum centerline displacement of `2.2692305557308856 px`, foreground support
ratio `1.0`, horizontal reversal `0.0 px`, and vertical reversal `0.0 px`. All
three approved centerline overshoots remained present.

Final focused batch:

```text
outputs/kou_skeleton_b_plan/
  callirewrite_hybrid_batch_20260710_224408_873803/
```

The probe completed with `status: ok` and selected
`structure_primitive`. Manual inspection of `input_image.png`,
`structure_skeleton_trajectory.png`, `structure_skeleton_overlay.png`,
`structure_skeleton_playback_contact_sheet.png`, and
`structure_primitive_rendered_execution.png` accepted the skeleton layer:

- the top-right right-left-right loop is absent;
- stroke 2 remains continuous with one horizontal-to-vertical turn;
- visible staircase artifacts are absent from the left, top, right, and bottom
  legs, while the target lean and shallow curvature remain visible;
- the top-left, left-bottom, and bottom-right overshoots remain clear; and
- the three separated strokes show that the centerline result is not merely a
  closed filled frame.

An earlier audit batch (`callirewrite_hybrid_batch_20260710_192150_856660`)
exposed apparent staircase artifacts caused by integer rounding in the review
image path. Preserving continuous coordinates in that display path removed the
false visual failure; the final acceptance above is based on the new `224408`
batch, not the earlier batch.

Focused and full regression results:

```text
test_makemeahanzi_prior.py: 84 passed in 22.56s
test_visualize.py: 54 passed in 204.98s (0:03:24)
test_callirewrite_hybrid.py: 47 passed in 136.80s (0:02:16)
offline_stroke_recovery_mvp/tests: 336 passed in 401.18s (0:06:41)
```

This is a skeleton-layer acceptance, not a claim that the filled `kou` is a
final natural brush reconstruction. The filled render remains marker-like and
visually heavy at the top-right corner. Width and brush-tip tuning, together
with any further `xin` repair, were explicitly deferred from this B-plan.
