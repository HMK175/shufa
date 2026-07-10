# Font skeleton cleanup prototype

本轮只针对 kaishu / lishu 的字体轮廓 skeleton 做轻量后处理诊断，不生成正式 trajectory.csv，不替换默认 pipeline。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355`
- scope: kaishu / lishu only; xingkai is intentionally excluded.
- cleanup operations: remove small connected components, prune short endpoint branches, optionally merge very close endpoints.

## Success rate

| style | success | total | success_rate |
|---|---:|---:|---:|
| kaishu | 5 | 5 | 1.000 |
| lishu | 5 | 5 | 1.000 |

## Mean cleanup deltas

| style | endpoint_delta | branch_delta | component_delta | skeleton_pixel_delta |
|---|---:|---:|---:|---:|
| kaishu | -1.8 | -1.8 | 0.0 | -8.6 |
| lishu | -0.8 | -0.8 | 0.0 | -2.0 |

## Cleaner after cleanup

| char | style | raw_endpoints | clean_endpoints | raw_branches | clean_branches | figure |
|---|---|---:|---:|---:|---:|---|
| 永 | kaishu | 12 | 9 | 22 | 19 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u6c38_kaishu.png` |
| 山 | kaishu | 6 | 4 | 12 | 10 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u5c71_kaishu.png` |
| 永 | lishu | 10 | 8 | 12 | 10 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u6c38_lishu.png` |
| 风 | kaishu | 9 | 7 | 16 | 14 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u98ce_kaishu.png` |
| 山 | lishu | 4 | 3 | 5 | 4 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u5c71_lishu.png` |
| 中 | kaishu | 7 | 6 | 29 | 28 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u4e2d_kaishu.png` |
| 中 | lishu | 3 | 2 | 17 | 16 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u4e2d_lishu.png` |
| 人 | kaishu | 4 | 3 | 4 | 3 | `experiments\llm_style_trajectory\outputs\font_skeleton_cleanup_prototype_20260619_122355\figures\cleanup_compare_u4eba_kaishu.png` |

## Still noisy or fragmented after cleanup

| char | style | clean_components | clean_endpoints | clean_branches | warning |
|---|---|---:|---:|---:|---|
| 中 | kaishu | 1 | 6 | 28 |  |
| 永 | kaishu | 3 | 9 | 19 | cleaned_skeleton_disconnected |
| 风 | kaishu | 2 | 7 | 14 | cleaned_skeleton_disconnected |
| 中 | lishu | 1 | 2 | 16 |  |
| 永 | lishu | 3 | 8 | 10 | cleaned_skeleton_disconnected |
| 风 | lishu | 1 | 5 | 11 |  |
| 山 | kaishu | 1 | 4 | 10 |  |
| 山 | lishu | 1 | 3 | 4 |  |

## 人工看图重点

- cleaned skeleton 是否比 raw skeleton 更连续、更少噪声？
- 是否保留了楷书/隶书的字体风格，而不是被清理成过于普通的中心线？
- 是否出现过度清理，导致隶书横向笔形或楷书关键结构丢失？
- 是否已经接近可提取 path 的程度，还是仍需要图结构级主路径提取？

## Diagnostic boundary

当前仍不是正式书写轨迹，也不是真实书法风格学习结果。本轮只回答：轻量 cleanup 是否能让 kaishu / lishu 的 font skeleton 更接近可写轨迹候选。若人工看图认为有价值，下一步才应进入 path extraction prototype。
