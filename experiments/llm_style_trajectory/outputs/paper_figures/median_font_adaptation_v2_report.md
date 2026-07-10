# Median-font adaptation v2 prototype

This is a diagnostic-only B-route prototype using global bbox alignment plus stroke-level anchor alignment.

## Boundary

- 保留 MakeMeAHanzi stroke order 和 stroke_count。
- 不恢复真实笔顺，不跨 stroke 合并，不重排笔顺。
- 不生成正式 `trajectory.csv`，只输出 `adapted_v2_*.csv`。
- 不接默认 pipeline，不接 execution/workspace/CoppeliaSim/AUBO/SDK。
- projection distance 不能作为唯一标准，必须同时看 aspect gap 和人工图像效果。

## Output

`D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\median_font_adaptation_v2_20260619_154351`

## Results

| char | style | before_dist | v1_dist | v2_cons_dist | v2_strong_dist | aspect_gap_before | aspect_gap_v1 | aspect_gap_v2_cons | aspect_gap_v2_strong | warning | compare |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 人 | kaishu | 6.55752 | 4.91814 | 4.521372 | 3.73909 | 0.066713 | 0.06241 | 0.061491 | 0.053279 |  | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\median_font_adaptation_v2_20260619_154351\u4eba_kaishu\median_font_adaptation_v2_compare.png` |
| 山 | lishu | 36.000849 | 29.389616 | 24.474754 | 20.563365 | 0.433371 | 0.495398 | 0.435363 | 0.441557 |  | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\median_font_adaptation_v2_20260619_154351\u5c71_lishu\median_font_adaptation_v2_compare.png` |

## Manual visual questions

- v2 是否比 v1 更接近 font aspect / font skeleton？
- 人/kaishu 是否没有被过度扭曲？
- 山/lishu 是否比 v1 更有隶书宽底/结构特征？
- conservative 是否比 stronger 更适合作为下一阶段默认候选？
