# Hybrid Style Trajectory Design Spec

Date: 2026-06-19

Scope: design and interface boundary only. This document does not implement a new algorithm, does not tune parameters, does not change the default pipeline, and does not connect API, CoppeliaSim, AUBO i5, SDK, or robot control.

Related decision report:

```text
experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md
experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json
```

## 1. Design Motivation

The previous route decision compared three directions:

- Route A: MakeMeAHanzi median + style profile.
- Route B: median + font skeleton / font mask adaptation.
- Route C: font skeleton derived path.

The evidence suggests that no single route should replace the others right now.

Route A is stable and robot-ready, but visual style strength is limited. It can produce deterministic `trajectory.csv`, execution trajectory, workspace trajectory, resampled workspace trajectory, CoppeliaSim pen-tip playback, robot target poses, AUBO i5 dry-run command plan, and IK feasibility dry-run. Its weakness is that `xingkai` can look like a kaishu centerline plus connectors, and `lishu` can look like a widened and flattened kaishu skeleton.

Route B is safer than pure skeleton extraction because it preserves MakeMeAHanzi stroke order. It works for light morphology adaptation, especially `人/kaishu`, but repeated `山/lishu` attempts show that point attraction, global bbox alignment, structure constraints, and component-level pulls only produce small improvements and quickly hit shift caps.

Route C has the strongest visible font-style signal, but it also has the highest risk. Font skeleton paths raise the old hard problems again: stroke-order recovery, fragmented segments, branch points, disconnected components, and complex-character generalization.

Therefore, the recommended next direction is a hybrid route:

```text
Route A supplies stable stroke order, writability, execution semantics, and robot precheck chain.
Route C supplies manually screened font-outline style reference.
Route B supplies bounded adaptation rules that may use C-derived references without replacing A.
```

## 2. Hybrid Architecture

The default pipeline remains Route A.

```text
natural language / planner
-> request boundary validation
-> Route A stable median trajectory
-> style profile / style_modifiers
-> optional Route C font-reference layer
-> optional Route B bounded adaptation layer
-> human visual audit gate
-> execution layer
-> workspace mapping / resampling
-> CoppeliaSim pen-tip playback dry-run
-> robot target pose / AUBO i5 dry-run precheck
```

Important constraints:

- Route C does not directly replace Route A.
- Route B and Route C are optional style enhancement modules.
- The default `run_demo.py` behavior remains Route A.
- Font-derived paths do not directly enter execution or robot precheck.
- A human visual audit gate is required before any B/C-derived result can be considered for further prototype integration.

## 3. Module Responsibilities

| module_id | module_name | input | output | allowed_to_modify | not_allowed_to_modify | current_status | risk_level |
|---|---|---|---|---|---|---|---|
| A | Stable trajectory backbone | planner plan, MakeMeAHanzi median, style profile, modifiers | median-based trial or default trajectory with `stroke_id`, stroke order, breaks, bbox/path metrics | style parameters through existing white-list mapping; execution attributes downstream | cannot use LLM to output CSV points; should not infer font skeleton paths | default baseline | low |
| B | Bounded adaptation module | A trajectory, font mask/skeleton reference, constraints, alpha/bbox/anchor limits | `adapted_trial_*.csv`, adaptation metrics, compare figures | point positions within caps; trial-only CSV names | stroke_count, stroke order, stroke breaks, formal `trajectory.csv`, default pipeline | diagnostic prototypes completed | medium |
| C | Font reference / candidate basis module | local font file, glyph mask, skeleton, cleanup/path diagnostics | skeleton candidates, mask metrics, selected style references, path extraction diagnostics | diagnostic references, visual audit packages, shape hints | direct execution input, direct A replacement, robot input | diagnostic prototypes completed | high |
| H | Human visual audit gate | modifier figures, font skeleton candidates, B/C compare figures, metrics | manual decision, issue tags, accepted/rejected reference list | decision records and recommended next experiments | cannot be bypassed by metrics alone | required process rule | medium |
| R | Execution and robot precheck module | approved stable Route A trajectory or future explicitly promoted trajectory | execution/workspace/resampled/target-pose/dry-run reports | execution width/pressure/speed, workspace mapping, retiming/precheck | real robot command, real SDK/IK, direct B/C experimental outputs | stable dry-run chain | medium |

## 4. Interface Contract

### A Output Contract

Route A may output:

- median trajectory points,
- `stroke_id`,
- stroke order,
- stroke breaks,
- bbox metrics,
- aspect ratio,
- path length,
- turning metrics,
- connection and execution metrics after downstream processing.

Route A is the only route currently allowed to feed the default execution and robot dry-run chain.

### B Input Contract

Route B may read:

- A route trial trajectory,
- stroke ids and stroke breaks,
- font mask / skeleton references,
- bbox / aspect hints,
- anchor constraints,
- alpha and shift caps,
- visual audit decisions from prior B/C outputs.

### B Output Contract

Route B may output only trial files, such as:

```text
adapted_trial_*.csv
adapted_v2_*.csv
lishu_structure_v3_*.csv
lishu_component_alignment_*.csv
```

It must also output:

- adaptation metrics,
- compare figures,
- warning fields,
- recommended-for-followup flags.

Route B restrictions:

- stroke_count must stay unchanged,
- stroke order must stay unchanged,
- stroke breaks must stay unchanged,
- no formal `trajectory.csv`,
- no execution/workspace/robot files,
- no default pipeline integration.

### C Input Contract

Route C may read:

- local font files,
- glyph masks,
- skeletons,
- MakeMeAHanzi median for comparison,
- manual audit results.

### C Output Contract

Route C may output:

- font mask and skeleton candidates,
- cleanup diagnostics,
- path extraction diagnostics,
- selected style references,
- trial-only path overlays,
- visual audit manifests.

Route C restrictions:

- must not directly feed execution,
- must not directly replace A,
- must not claim real stroke order,
- must pass human visual audit before influencing any B prototype,
- must remain small-sample until skeleton fragmentation and ordering risks are controlled.

## 5. Human Audit Gate

Visual judgment must not be replaced by a single numeric metric.

The following artifacts require human visual audit before being used as evidence for the next method step:

| artifact_type | examples | audit_focus |
|---|---|---|
| modifier figures | connection / shape / smoothness figures | whether visual change is actually visible and natural |
| font skeleton candidates | `basis_compare_uXXXX.png`, cleanup compare figures | style signal, noise, branches, disconnections |
| B adaptation compare | median-font v1/v2/v3/component figures | whether adaptation keeps writability and avoids distortion |
| C path extraction compare | path segment and ordering overlays | whether paths are too fragmented or order is unreasonable |
| execution render | execution render/debug figures | connector naturalness, width/pressure visibility |

Recommended audit record fields:

- sample id,
- style,
- artifact path,
- visual decision: accept / reject / needs revision,
- reason,
- risk tag,
- next action.

## 6. Safety and Boundary Rules

- LLM planners must not generate CSV, trajectory points, robot poses, or robot commands.
- Route B and Route C must not directly enter the robot chain.
- Robot dry-run accepts only stable, explicitly approved trajectories that have passed continuity and workspace checks.
- AUBO i5 work remains offline dry-run / feasibility precheck only.
- CoppeliaSim work remains pen-tip/tool visual playback unless a future task explicitly scopes a robot model.
- Historical AUBO IP or SDK information is documentation-only and must not become default connection config.
- `code/data/makemeahanzi/` is shared data and must not be moved.
- `code/legacy_image_skeleton_rl_route/` is historical archive and must not be used as the current method basis unless a future task explicitly asks for legacy comparison.

## 7. Candidate Minimal Hybrid Prototypes

### Prototype H1: A Median + B Bounded Adaptation

Goal: test whether a carefully bounded B layer can improve low-risk style morphology while preserving Route A writability.

Inputs:

- Route A median trajectory,
- font mask/skeleton reference,
- existing B constraints,
- manually selected samples such as `人/kaishu` and `山/lishu`.

Outputs:

- trial-only adapted CSV files,
- compare figures,
- projection/aspect/shift/path metrics,
- manual audit checklist.

Success criteria:

- stroke_count unchanged,
- stroke order unchanged,
- no formal `trajectory.csv`,
- no execution or robot files,
- visual improvement accepted by manual audit,
- no repeated shift-cap failure.

Risk:

- medium. Existing evidence shows `人/kaishu` is promising, but `山/lishu` remains hard and can hit caps.

Recommendation:

- useful after H2 clarifies which font references should constrain which median structures.

### Prototype H2: A Median + C Font Reference Constraints Only

Goal: use Route C as a style reference provider without moving trajectory points yet.

Inputs:

- Route A median trajectory,
- C route font mask / skeleton diagnostics,
- selected visual audit results,
- feature summaries such as bbox, lower-half width, component spread, stroke-width distribution hints.

Outputs:

- reference constraint package,
- per-sample style reference summary,
- allowed / rejected reference fields,
- comparison report linking each constraint to visual evidence.

Success criteria:

- no trajectory point modification,
- no formal `trajectory.csv`,
- no default pipeline integration,
- clear mapping from font evidence to allowed future B constraints,
- manual audit confirms selected references are visually meaningful.

Risk:

- low-to-medium. It avoids another round of potentially distorted point pulling and gives the project a cleaner design basis.

Recommendation:

- recommended next prototype.

### Prototype H3: A Baseline + C-Derived Style Exemplar Visualization

Goal: keep Route A output unchanged, but show C-derived font evidence beside A output as a planner/style-profile reference.

Inputs:

- Route A output,
- font mask/skeleton selected images,
- style diagnostics.

Outputs:

- side-by-side figures,
- style gap labels,
- human evaluation templates,
- paper-ready limitation evidence.

Success criteria:

- useful for paper explanation,
- no trajectory modification,
- clear visual evidence for why style basis improvement is needed.

Risk:

- low. It is mostly documentation and evidence packaging.

Recommendation:

- useful for paper writing, but less method-forward than H2.

## 8. Recommended Next Step

Recommended next step: Prototype H2.

Reasoning:

- H1 has already been partially explored by B v1/v2/v3/component experiments. It can improve light cases, but strong lishu adaptation quickly hits shift caps.
- H2 is safer because it does not move trajectory points yet. It first defines which C-derived font references are trustworthy and how they may constrain a future B layer.
- H2 creates a clean interface between C evidence and B adaptation rules, reducing the risk of arbitrary point pulling.
- H2 also provides a stronger paper method framing: the system can be described as a stable trajectory backbone plus audited font-derived style constraints.

Concrete H2 deliverable for a future task:

```text
font_reference_constraint_package.json
font_reference_constraint_report.md
sample_reference_manifest.csv
```

These would remain diagnostic and not enter the default pipeline.

## 9. Paper Framing

Recommended method framing:

> We propose a hybrid style-aware trajectory generation framework. A stable median-stroke backbone preserves writability and supports execution/robot precheck. Font-outline analysis provides interpretable style references, and bounded adaptation modules can optionally test how selected references influence the median trajectory under strict safety and visual-audit gates.

Recommended boundaries:

- Do not write that high-quality real calligraphy style learning is complete.
- Do not write that font skeleton paths are official trajectories.
- Do not write that AUBO i5 real robot writing has been validated.
- Route A is the stable execution backbone.
- Route B/C are style enhancement explorations and interpretable constraint sources.
- Manual visual audit remains essential because metrics alone cannot determine calligraphic quality.

## 10. Decision

The hybrid route should be developed in this order:

1. H2: define and audit font-reference constraints without changing trajectories.
2. H1: apply bounded adaptation only to selected low-risk samples after H2 clarifies constraints.
3. H3: package visual evidence for paper framing and limitation discussion as needed.

The default pipeline remains Route A until a future prototype passes visual audit, stability checks, and explicit promotion criteria.
