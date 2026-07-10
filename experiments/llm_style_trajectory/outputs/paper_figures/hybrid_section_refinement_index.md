# Hybrid section refinement v1 index

- source_output_dir: `experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/`
- status: `trial-only`, `not_used_by_default`
- sample: `风 / lishu`
- boundary: no formal `trajectory.csv`, no execution/workspace/robot outputs, no default pipeline integration

## Main artifacts

- summary: `experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/hybrid_section_refinement_summary.csv`
- report: `experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/hybrid_section_refinement_report.md`
- compare: `experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/u98ce_lishu/hybrid_section_compare.png`
- summary json: `experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/u98ce_lishu/hybrid_section_summary.json`

## Key results

- section_source: `top_mid_bottom_fallback`
- section_names: `top_band`, `mid_band`, `bottom_band`
- bbox_aspect: `1.188427 -> 1.259425 / 1.306963`
- lower_half_width: `215.040000 -> 219.856896 / 223.297536`
- max_point_shift_px: `5.543559 / 8.824495`
- path_length_ratio: `0.982155 / 0.973699`

## Interpretation

This round shows that hybrid section refinement can keep `风/lishu` within a
small-shift, trial-only regime while still pushing the shape slightly toward a
broader lishu bottom structure. However, the current font component extraction
was not stable enough for component-first grouping, so the actual run relied on
`top/mid/bottom` fallback. That means the next step should prioritize section
constraint packaging or a repeat on a more stable sample such as `山/lishu`
before any wider expansion.
