# H1-lite single-sample risk trial: 风/lishu

This is a trial-only diagnostic for a more complex lishu character.

## Boundary

- trial-only / not_used_by_default。
- 只使用 H2 中 `usable_for_adaptation` 的 bounded constraints。
- 不使用 raw skeleton path，不使用 unordered skeleton segments，不做最近点吸附。
- 保留 stroke_count / stroke_order / stroke_breaks。
- 不生成正式 trajectory.csv，不生成 execution/workspace/robot 文件，不接默认 pipeline。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\h1_lite_feng_lishu_risk_trial_20260620_212829`
- contrast_png: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\h1_lite_feng_lishu_risk_trial_20260620_212829\contrast\h1_lite_u98ce_lishu_risk_contrast.png`

## Results

- 风/lishu bbox aspect: 1.188427 -> 1.249587 / 1.305703
- 风/lishu lower-half width: 215.04 -> 220.805168 / 225.873828
- 风/lishu max shift: 4.38826 / 8.007583 px
- 风/lishu path ratio: 0.992053 / 0.985405

## Reference compare

- known positive reference compare: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\constraint_bounded_adaptation_h1_lite_20260619_231903\u5c71_lishu\h1_lite_compare.png`
- 山/lishu reference source: existing_h1_lite_positive_reference

## Manual visual audit questions

- 风/lishu 是否仍保持可写性？
- H1-lite 是否还能保持隶书宽底感？
- 与山/lishu 相比是否明显更难处理？
- 是否说明 H1-lite 适合简单/中等复杂度 lishu，但对复杂字开始接近边界？
- 是否仍建议继续扩展，还是应优先做 component-level / section-level constraint refinement？

## Interpretation

If 风/lishu stays readable and the balanced variant preserves a visible lishu broad-bottom cue without large point shifts, H1-lite remains viable for some complex lishu samples. If the shape gets visibly fragile, that is a sign to stop expanding and return to component-level refinement instead of pushing stronger bounded adaptation.
