# Trajectory Style Route Decision Report

Date: 2026-06-19

Scope: this report is evidence consolidation only. It does not add a generation algorithm, does not tune parameters, does not change the default pipeline, and does not connect CoppeliaSim, AUBO i5, SDK, API, or robot control.

## 1. Current Problem Background

The current `experiments/llm_style_trajectory` route has already built a complete deterministic system chain:

```text
natural-language task
-> mock/API/local planner schema
-> style_modifiers and white-list mapping
-> MakeMeAHanzi median strokes
-> trajectory.csv
-> execution_trajectory.csv
-> robot_workspace_trajectory.csv
-> robot_workspace_trajectory_resampled.csv
-> CoppeliaSim pen-tip/sphere playback
-> robot_target_poses.csv
-> AUBO i5 dry-run command plan
-> IK feasibility dry-run
```

This chain is stable and useful as a robotics-oriented baseline. The limitation is visual style quality. Manual review has repeatedly indicated that:

- `xingkai` still tends to look like "kaishu centerline + some connectors".
- `lishu` still tends to look like "kaishu skeleton scaled wider and flatter".
- The modifier figures for connection, shape, and smoothness are controllable but not visually strong enough to claim high-quality calligraphic style.
- Continuing to tune connector count, taper, or pressure alone is unlikely to solve the core style-basis problem.

For that reason, the project explored font-outline-derived evidence. The goal was not to replace the current pipeline immediately, but to test whether the source trajectory basis itself should remain only MakeMeAHanzi median.

## 2. Route A: MakeMeAHanzi Median + Style Profile

Route A is the current stable baseline.

### Completed Capability

- Mock/API/local planner framework and schema validation.
- Controlled `style_modifiers`: connection, shape, smoothness, and width.
- Estimated style profiles for `kaishu`, `xingkai`, and `lishu`.
- Deterministic centerline trajectory generation from MakeMeAHanzi median strokes.
- Execution layer with width, pressure, speed, connector, and pen-up semantics.
- Workspace mapping and resampling.
- CoppeliaSim standard pen-tip/sphere playback.
- Robot target pose generation.
- AUBO i5 command adapter dry-run.
- IK feasibility dry-run and motion continuity / retiming prechecks.

### Key Evidence Paths

- `experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`
- `experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/`
- `experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/`
- `experiments/llm_style_trajectory/outputs/batch_20260613_154131/`
- `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_adapter_smoothed_index.md`
- `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_smoothed_index.md`

### Strengths

- Stable and reproducible.
- Preserves MakeMeAHanzi stroke order and stroke count.
- Supports the complete execution and robot precheck chain.
- Suitable for demonstrating system architecture, natural-language request boundaries, deterministic tool orchestration, execution-layer semantics, and dry-run robotics preparation.
- Safe to use as the paper's system backbone.

### Limitations

- Style strength is limited.
- `xingkai` connector rules remain visibly procedural.
- `lishu` shape control is mostly global scaling and does not fully model component-level or stroke-shape structure.
- Smoothness metrics are subtle and do not always correspond to strong visual differences.
- It should not be presented as mature high-quality calligraphic style learning.

### Paper Role

Route A is appropriate as:

- the main system pipeline,
- a deterministic baseline,
- a controlled natural-language-to-trajectory demonstration,
- the robotics precheck backbone.

It should not be overclaimed as:

- real calligraphy style generation,
- learned style transfer,
- true brush modeling,
- real robot writing validation.

## 3. Route B: Median + Font Skeleton / Font Mask Adaptation

Route B keeps MakeMeAHanzi stroke order and uses font skeleton or font mask as a style morphology reference.

### Attempts Completed

Evidence paths:

- `experiments/llm_style_trajectory/outputs/median_font_alignment_20260619_145307/`
- `experiments/llm_style_trajectory/outputs/median_font_adaptation_v2_20260619_154351/`
- `experiments/llm_style_trajectory/outputs/lishu_structure_adaptation_v3_20260619_155525/`
- `experiments/llm_style_trajectory/outputs/lishu_component_alignment_20260619_160805/`

Summary:

- v1 alpha-only nearest-point projection:
  - `人/kaishu`: stable positive case; projection distance dropped and stroke count stayed 2.
  - `山/lishu`: projection distance dropped, but bbox aspect did not move toward the lishu font shape.
- v2 global bbox + stroke-level anchor alignment:
  - `人/kaishu`: projection distance and aspect gap improved slightly.
  - `山/lishu`: projection distance improved, but aspect gap still did not approach the lishu font aspect.
- v3 lishu structure constraint:
  - `山/lishu`: lower-half width and aspect improved slightly, but variants hit the shift cap.
- component-level alignment:
  - `山/lishu`: conservative variant gave a small signal, but stronger was not better and both variants hit the 24 px shift cap.

### Strengths

- Preserves MakeMeAHanzi stroke order and stroke breaks.
- Avoids the hardest part of pure skeleton route: full stroke-order recovery.
- Works for light morphology adaptation, especially `人/kaishu`.
- Good research direction for local or component-aware style adaptation.

### Limitations

- Point projection alone is not enough for strong style transfer.
- For `山/lishu`, repeated attempts improved projection distance but did not strongly solve the wide-bottom lishu structure.
- More forceful alignment quickly hits movement caps and risks visual distortion.
- Component targets need better definitions before broader use.

### Recommended Direction

Route B should continue only as a safe style adaptation research direction. It is promising for light adaptation and for preserving writability, but it should not be expected to solve strong `lishu` style migration by itself.

Do not continue by simply increasing alpha, shift caps, or global pulling strength. If Route B continues, the next useful step is a design-level hybrid specification: which components of font reference should influence which median strokes, and under what safety limits.

## 4. Route C: Font Skeleton Derived Path

Route C attempts to derive candidate paths directly from font outlines and skeletons.

### Attempts Completed

Evidence paths:

- `experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/`
- `experiments/llm_style_trajectory/outputs/font_outline_basis_audit_20260619_120211/`
- `experiments/llm_style_trajectory/outputs/font_skeleton_cleanup_prototype_20260619_122355/`
- `experiments/llm_style_trajectory/outputs/font_skeleton_path_extraction_20260619_123527/`
- `experiments/llm_style_trajectory/outputs/font_derived_trajectory_trial_20260619_125428/`
- `experiments/llm_style_trajectory/outputs/font_skeleton_stroke_ordering_20260619_132543/`

Findings:

- Font skeleton extraction succeeded for tested `kaishu`, `xingkai`, and `lishu` samples in the feasibility run.
- Font skeletons visibly contain stronger style signals than MakeMeAHanzi median for some cases, especially `山`, `德`, `福`, and `山/lishu`.
- `kaishu` skeletons are cleaner than `lishu`.
- `lishu` skeletons are valuable but noisier because style shape is stronger.
- `人/kaishu` is the cleanest path-ordering candidate.
- `山/lishu` preserves visible lishu style signal.

### Strengths

- Strongest style signal among the three routes.
- Can reveal glyph-structure differences that global scaling cannot express.
- Useful as a style-basis diagnostic and future morphology reference.

### Risks

- Stroke order recovery is difficult.
- Extracted path segments can be fragmented.
- Branches, endpoints, and disconnected components become severe for complex characters.
- Complex character generalization is uncertain.
- This route is close to the old image-skeleton route; it must avoid re-entering a full skeleton recovery problem without strong constraints.

### Recommended Direction

Route C should remain a small-sample, manually screened style-basis research route. It should not be connected to the default pipeline now.

It is best used to:

- identify which glyphs and styles contain useful skeleton signals,
- provide style reference for future hybrid design,
- support limitation analysis in the paper.

It is not ready to become the official trajectory source.

## 5. Route Comparison Table

| route_id | route_name | stability | style_strength | robot_pipeline_readiness | implementation_risk | paper_writing_value | main_evidence | main_limitation | recommended_status |
|---|---|---|---|---|---|---|---|---|---|
| A | MakeMeAHanzi median + style profile | high | low-to-medium | high | low | high as system baseline | style diagnostics, execution/workspace/CoppeliaSim/AUBO dry-run chain | style looks too parameterized | stable_baseline_and_robot_backbone |
| B | Median + font skeleton/mask adaptation | medium | medium for light cases | low-to-medium | medium | medium-to-high as research direction | median-font v1/v2, lishu v3, component alignment | strong style transfer still weak; caps reached | safe_adaptation_research_direction |
| C | Font skeleton derived path | low-to-medium | high in selected samples | low | high | high as diagnostic/future-work evidence | feasibility, audit, cleanup, path extraction, ordering | stroke order, fragmentation, branch/disconnect risk | style_basis_research_only |

## 6. Current Recommendation

The recommended near-term route is a hybrid strategy, not a single-route replacement.

1. Keep Route A as the stable baseline and robot pipeline backbone.
2. Treat Route B as a safe adaptation research layer: it can preserve MakeMeAHanzi writability while accepting limited font-derived morphology hints.
3. Treat Route C as a style-basis diagnostic route: it provides stronger style evidence but must remain manually screened and small-sample until stroke ordering and simplification become reliable.

In other words:

```text
A provides stroke order, execution semantics, and robot precheck chain.
B provides conservative morphology adaptation candidates.
C provides font-outline style evidence and future basis candidates.
```

The next phase should design a hybrid route rather than blindly tuning connector/taper or directly replacing the trajectory basis with skeleton paths.

## 7. Recommended Next Options

### Option 1: Hybrid Route Design Spec

Write a design-only specification for how A, B, and C could be combined:

- A keeps MakeMeAHanzi stroke order and execution chain.
- C supplies style reference candidates from manually selected font skeleton/mask features.
- B supplies bounded adaptation rules between them.

This option is the safest next step because it clarifies the architecture before adding more prototypes.

### Option 2: Small Route C Expansion

Expand only simple `kaishu/lishu` samples, not `xingkai`, and continue manual screening:

- simple independent characters,
- no complex component structures,
- no default pipeline integration.

This option helps gather more evidence but risks spending time on skeleton repair.

### Option 3: Paper Minimum Mainline

Freeze Route A as the system framework and write B/C as limitation-driven improvement explorations:

- Route A demonstrates end-to-end natural language control and dry-run robotics readiness.
- B/C explain why stronger style modeling is needed.

This option is best if the immediate priority is a coherent paper draft.

## 8. Paper Boundary Statements

Recommended wording:

- The current system demonstrates a deterministic natural-language-to-trajectory-and-precheck pipeline, not mature high-quality calligraphic style generation.
- Route A proves request validation, controlled modifiers, execution semantics, workspace mapping, and dry-run robot-interface preparation.
- Route A does not prove that `xingkai` or `lishu` visual quality is sufficient.
- Route B and Route C are exploratory evidence for future style-basis improvement.
- Font skeleton paths are not yet reliable enough to replace MakeMeAHanzi median.
- The current AUBO i5 chain is dry-run / feasibility precheck only. It is not real IK, not real robot control, and not a physical writing experiment.

## 9. Decision

Current decision:

- Do not continue blind connector/taper tuning as the main path.
- Do not connect font skeleton derived paths to the default pipeline.
- Keep Route A as the default system and robot backbone.
- Keep Route B/C as exploratory style-basis evidence.
- Prioritize a hybrid route design spec before adding more generation algorithms.
