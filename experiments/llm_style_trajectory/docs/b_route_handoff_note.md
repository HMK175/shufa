# B-route Handoff Note

## Current Route Map

- A: MakeMeAHanzi median + style profile. This is the stable backbone for writeability, execution, workspace mapping, CoppeliaSim pen-tip playback, and robot dry-run / IK precheck.
- B: registry-gated adaptation. This is trial-only and not used by default.
- C: font reference / candidate basis. This is a read-only evidence pack for visual reference and gating, not a direct execution path.

Do not return to raw skeleton pulling, and do not treat font skeleton paths as a default replacement for MakeMeAHanzi medians.

## B-route Formal Entry Points

Read these in order when you continue B-route work:

1. `experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md`
2. `experiments/llm_style_trajectory/outputs/paper_figures/b_route_constraint_registry_index.md`
3. `experiments/llm_style_trajectory/outputs/paper_figures/section_constraints_package_index.md`
4. `experiments/llm_style_trajectory/outputs/paper_figures/font_reference_constraints_index.md`

Supporting modules:

- `experiments/llm_style_trajectory/src/b_route_constraint_registry.py`
- `experiments/llm_style_trajectory/src/b_route_registry_gated_probe.py`
- `experiments/llm_style_trajectory/src/section_constraints_package.py`
- `experiments/llm_style_trajectory/src/font_reference_constraints_package.py`

Relation to earlier B-route work:

- H1-lite: constraint-bounded median adaptation, still trial-only.
- hybrid section refinement: section-level bounded adaptation with component-first / fallback logic.
- B-route registry: the gate that decides which constraints may enter adaptation, and which must stay reference-only or blocked.

## Constraint Levels

### usable_for_adaptation

Use these only for bounded movement, not hard pulling:

- `bbox_aspect`
- `lower_half_width_ratio`
- `left_right_spread`
- `bbox_center_shift_x`
- `bbox_center_shift_y`

### reference_only

Use these to judge complexity or risk, but not to move points directly:

- `component_count`
- `endpoint_count`
- `branch_count`
- `connectedness_hint`

### blocked

Keep these out of the default adaptation path:

- `raw_skeleton_path`
- `unordered_skeleton_segments`
- high-complexity skeleton graphs

## Recommended Reading Order for New Threads

1. `CURRENT_PROJECT_GUIDE.md`
2. `experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md`
3. `experiments/llm_style_trajectory/outputs/paper_figures/b_route_constraint_registry_index.md`
4. `experiments/llm_style_trajectory/outputs/paper_figures/section_constraints_package_index.md` and `experiments/llm_style_trajectory/outputs/paper_figures/font_reference_constraints_index.md`

## What To Do Next

- Do not go back to direct point-level pulling.
- Do not route font skeleton paths into the default pipeline.
- If you continue B-route, go through the registry-gated adaptation path or the section-constraints package first.
- Robot-related work still stays at dry-run / precheck only.

## Boundary Statement

This page is not a new algorithm. It does not generate trajectories. It does not change the default pipeline. It does not call an API. It does not connect CoppeliaSim, AUBO, or any SDK. It does not modify `code/data` or `code/legacy_image_skeleton_rl_route`.
