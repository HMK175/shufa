# Median-to-font skeleton alignment / adaptation prototype

本轮是 B 路线：`median + font skeleton` 融合，而不是纯 skeleton -> trajectory。

## 边界说明

- 保留 MakeMeAHanzi stroke order 和 stroke break。
- 不恢复真实笔顺，不重排笔顺，不改变 stroke 数量。
- 不生成正式 `trajectory.csv`，只输出 `adapted_trial_alpha_*.csv`。
- 不接机器人，不生成 execution/workspace/CoppeliaSim/AUBO 文件。
- 只用于判断字体参考能否改善风格形态。

## 输出目录

`experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307`

## 样本结果

| char | style | stroke_count | alpha=0.25 distance | alpha=0.5 distance | max_shift_0.25 | max_shift_0.5 | warning | recommended | compare |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| 人 | kaishu | 2 | 4.91814 | 3.27876 | 5.748356 | 11.496712 |  | True | `experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307\u4eba_kaishu\median_font_alignment_compare.png` |
| 山 | lishu | 3 | 29.389616 | 23.972679 | 10.532784 | 15.0 |  | True | `experiments\llm_style_trajectory\outputs\median_font_alignment_20260619_145307\u5c71_lishu\median_font_alignment_compare.png` |

## 人工看图问题

- adapted 轨迹是否比原 median 更接近字体风格？
- 是否仍保留可写性和笔顺结构？
- alpha=0.25 是否比 alpha=0.5 更稳？
- 山/lishu 是否比单纯横向压扁更有隶书感？
- 人/kaishu 是否没有被过度扭曲？

## 初步建议

如果人工看图确认 alpha=0.25 在保持可写性的同时提升字体贴近度，可以进入 median-font adaptation v2；
alpha=0.5 仅作为更强吸附对照，若出现过度扭曲，应优先保守使用更小 alpha 或 stroke-aware 限制。

## Visual QA note

- `人/kaishu`: alpha=0.25 and alpha=0.5 keep the two-stroke structure; the adaptation improves local skeleton proximity without obvious over-warping.
- `山/lishu`: projection distance decreases, but the global form still follows the MakeMeAHanzi three-stroke median more than the wide-bottom lishu font outline. A v2 should add stroke-level bbox or anchor alignment, not only nearest-neighbor point attraction.
