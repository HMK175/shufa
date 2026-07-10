# Lishu component-level alignment prototype

This diagnostic prototype only handles 山/lishu and applies component-level alignment.

## Boundary

- 保留 MakeMeAHanzi stroke order 和 stroke_count。
- 不恢复真实笔顺，不跨 stroke 合并，不重排笔顺。
- 不生成正式 `trajectory.csv`，只输出 `lishu_component_alignment_*.csv`。
- 不接默认 pipeline，不接 execution/workspace/CoppeliaSim/AUBO/SDK。
- component-level alignment 是诊断性启发式，不等同真实隶书生成。

## Output

`D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\lishu_component_alignment_20260619_160805`

## Main comparison

| sample | v3_dist | comp_cons_dist | comp_strong_dist | v3_aspect | comp_cons_aspect | comp_strong_aspect | lower_v3 | lower_comp_cons | lower_comp_strong | warning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 山/lishu | 20.090813 | 19.949109 | 20.215119 | 0.958299 | 0.970717 | 0.971593 | 159.569313 | 160.028913 | 160.743366 | conservative_reaches_shift_cap;stronger_reaches_shift_cap |

## Diagnostic answers

- component-level alignment 是否比 v3 更有效：请同时看 lower_half_width、aspect gap 和 compare 图。
- 是否避免纯全局拉扯：本轮按 left/center/right/lower support 点级 group 分别移动。
- 是否保留 stroke_count / stroke order：输出仍沿用 MakeMeAHanzi stroke 顺序和断笔。
- 是否出现不自然变形：重点看 stronger 的 shift cap、path_length_ratio 和人工图像效果。

## Manual visual questions

- 山/lishu 是否更像隶书宽底结构？
- component groups 是否合理？
- component stronger 是否过度拉扯？
- conservative 是否更自然？
