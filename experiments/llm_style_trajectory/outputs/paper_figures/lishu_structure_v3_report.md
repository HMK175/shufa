# Lishu structure adaptation v3 prototype

This diagnostic prototype only handles 山/lishu. It adds structure-level constraints after v2 stronger.

## Boundary

- 保留 MakeMeAHanzi stroke order 和 stroke_count。
- 不恢复真实笔顺，不跨 stroke 合并，不重排笔顺。
- 不生成正式 `trajectory.csv`，只输出 `lishu_structure_v3_*.csv`。
- 不接默认 pipeline，不接 execution/workspace/CoppeliaSim/AUBO/SDK。
- structure-level constraints 只是诊断性启发式，不等同真实隶书风格学习。

## Output

`D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\lishu_structure_adaptation_v3_20260619_155525`

## Main comparison

| sample | v2_dist | v3_cons_dist | v3_strong_dist | v2_aspect | v3_cons_aspect | v3_strong_aspect | lower_v2 | lower_v3_cons | lower_v3_strong | warning |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 山/lishu | 20.563365 | 20.157518 | 20.090813 | 0.936821 | 0.958776 | 0.958299 | 156.629793 | 158.148182 | 159.569313 | stronger_reaches_shift_cap |

## Diagnostic answers

- v3 是否改善 lower-half width / aspect gap：请同时看 summary 数值和 compare 图。
- v3 是否比 v2 更像隶书宽底结构：本轮只给结构约束候选，不替代人工看图。
- 是否过度扭曲：重点看 stronger 是否接近 22 px shift cap，以及 path_length_ratio 是否异常。
- 本轮结果用于判断隶书是否需要 structure-level constraints，而不是继续 point-level projection。

## Manual visual questions

- 山/lishu 是否比 v2 更有隶书结构？
- 底部是否更展开？
- 是否仍保持可写性？
- 是否有不自然拉扯、断裂或折笔？
