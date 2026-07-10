# Font Reference Constraints Package

H2 purpose: extract interpretable font mask / skeleton constraints as a reference package only. 本轮不移动轨迹点，不生成 adapted trajectory，不生成正式 trajectory.csv，不接默认 pipeline。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_reference_constraints_20260619_230426`
- status: `reference_constraints_only_not_used_by_default`
- scope: kaishu / lishu representative samples only; xingkai and complex broad samples are excluded.

## Constraint use counts

| recommended_use | count |
|---|---:|
| usable_for_adaptation | 25 |
| visual_reference_only | 25 |
| unsafe_for_direct_use | 34 |

## Summary by sample

| char | style | aspect | lower_half_width_ratio | complexity | usable | visual | unsafe | recommendation |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 山 | kaishu | 1.088 | 0.973 | 0.579 | 5 | 5 | 2 | candidate_for_bounded_B_adaptation |
| 人 | kaishu | 1.346 | 1.000 | 0.294 | 5 | 5 | 2 | candidate_for_bounded_B_adaptation |
| 中 | kaishu | 0.744 | 0.806 | 1.000 | 0 | 0 | 12 | visual_reference_only_high_risk |
| 山 | lishu | 1.375 | 1.000 | 0.351 | 5 | 5 | 2 | candidate_for_bounded_B_adaptation |
| 中 | lishu | 1.195 | 0.967 | 0.688 | 5 | 5 | 2 | visual_reference_with_limited_constraints |
| 永 | lishu | 1.561 | 1.000 | 1.000 | 0 | 0 | 12 | visual_reference_only_high_risk |
| 风 | lishu | 1.632 | 1.000 | 0.582 | 5 | 5 | 2 | candidate_for_bounded_B_adaptation |

## Style-level notes

- `kaishu`: samples=3, avg_complexity=0.625, usable_constraints=10, unsafe_constraints=16.
- `lishu`: samples=4, avg_complexity=0.655, usable_constraints=15, unsafe_constraints=18.

## Usable for future B adaptation

- `bbox_aspect`: usable only as bounded low-weight width/height hint.
- `lower_half_width_ratio`: useful for lishu lower support diagnostics, especially simple characters such as 山.
- `left_right_spread`: useful as a soft spread hint; must not hard-pull points.
- `bbox_center_shift_x/y`: only safe for tiny centering adjustments.

## Visual reference only

- `skeleton_component_count`, `skeleton_endpoint_count`, `skeleton_branch_count`, `skeleton_complexity_score`, and `connectedness_hint` are complexity and audit signals.
- These fields should guide manual review and future constraint selection, not direct point movement.

## Unsafe for direct use

- `raw_skeleton_path` and `unordered_skeleton_segments` are explicitly marked unsafe.
- High-branch, disconnected, or complex skeleton graphs must not drive trajectory deformation without cleanup, ordering, and manual audit.

## Next B adaptation suggestion

Use this package to choose a small set of low-risk constraints before any future B prototype. Prefer bounded `bbox_aspect`, `lower_half_width_ratio`, and `left_right_spread` over raw skeleton paths. Do not connect these constraints to `run_demo.py` or execution/robot files until a future explicit promotion task.

## Boundary

This package is reference-only and not used by default. It does not alter `style_profiles.json`, does not change `run_demo.py`, does not create adapted or formal trajectory files, and does not call API/CoppeliaSim/AUBO/SDK.
