# B-route constraint registry

This registry is a trial-only gating entry point for the B route.
It is registry-gated adaptation, not direct pulling.
It unifies H2 font-reference constraints and section constraints into a read-only evidence pack.

## Boundary

- trial-only / not_used_by_default
- no point movement by default
- no default pipeline integration
- raw skeleton paths remain blocked

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\b_route_constraint_registry_20260621_011822`
- h2_source_status: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_reference_constraints_20260619_230426\font_reference_constraints.json`
- section_source_status: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\section_constraints_package_20260621_003023\section_constraints_package.json`

## Gate policy

- usable_for_adaptation: bbox_aspect, lower_half_width_ratio, left_right_spread, bbox_center_shift_x, bbox_center_shift_y
- reference_only: component_count, endpoint_count, branch_count, connectedness_hint, skeleton_complexity_score
- blocked: raw_skeleton_path, unordered_skeleton_segments
- 山/lishu uses component_first_safe with a 15 px shift cap.
- 风/lishu uses fallback_first_reference_only with a 12 px shift cap.

## Entries

| sample | strategy | section | fallback | usable | reference | blocked | shift cap | next use |
|---|---|---|---|---:|---:|---:|---:|---|
| 山/lishu | component_first_safe | hybrid_component_first | False | 5 | 5 | 2 | 15 | B_safe_input |
| 风/lishu | fallback_first_reference_only | hybrid_component_first | True | 5 | 5 | 2 | 12 | fallback_first_reference_only |

## Interpretation

The registry does not replace trajectory generation. It only decides which evidence is safe enough to feed into a bounded B prototype.
If a sample is unstable, the registry forces fallback-first section guidance instead of raw point pulling.
