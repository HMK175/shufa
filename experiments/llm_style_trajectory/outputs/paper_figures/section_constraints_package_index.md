# Section constraints package / fallback guide index

- source_output_dir: `experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/`
- status: `trial-only`, `not_used_by_default`
- boundary: no formal trajectory.csv, no execution/workspace/robot outputs, no default pipeline integration

## Main artifacts

- summary json: `experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/section_constraints_package.json`
- summary csv: `experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/section_constraints_package.csv`
- report: `experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/section_constraints_package_report.md`
- manifest: `experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/section_constraints_package_manifest.csv`

## Recommended use

- Safe B input: `山/kaishu`, `山/lishu`
- Fallback-first reference-only: `风/lishu`

## Section rules

- component bbox stable -> component-first + light bbox / anchor alignment
- component bbox unstable -> top/mid/bottom fallback
- usable constraints: bbox_aspect, lower_half_width_ratio, left_right_spread, bbox_center_shift_x/y
- reference-only: component_count, endpoint_count, branch_count
- unsafe: raw_skeleton_path, unordered_skeleton_segments
