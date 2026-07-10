# Font skeleton path extraction prototype

本轮只把 cleaned font skeleton 转成候选 path segments，作为 very small-sample diagnostic。它不是正式轨迹，不生成 `trajectory.csv`，不含真实笔顺，也不接入默认 pipeline。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_path_extraction_20260619_123527`
- samples: 山/kaishu, 人/kaishu, 中/kaishu, 山/lishu, 永/lishu
- excluded: xingkai, 德, 福, 国, 风, other complex chars
- candidate_order_method: `component_order_longest_first`

## Recommendation counts

| style | recommended | total |
|---|---:|---:|
| kaishu | 3 | 3 |
| lishu | 2 | 2 |

## Sample results

| char | style | components | endpoints | branches | segments | total_length_px | recommended | warning | figure |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| 山 | kaishu | 1 | 4 | 10 | 7 | 355.296465 | True | short_segments_filtered:10 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_path_extraction_20260619_123527\figures\path_extraction_u5c71_kaishu.png` |
| 人 | kaishu | 1 | 3 | 3 | 4 | 318.788888 | True | short_segments_filtered:2 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_path_extraction_20260619_123527\figures\path_extraction_u4eba_kaishu.png` |
| 中 | kaishu | 1 | 6 | 28 | 14 | 496.681241 | True | high_branch_count;short_segments_filtered:36 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_path_extraction_20260619_123527\figures\path_extraction_u4e2d_kaishu.png` |
| 山 | lishu | 1 | 3 | 4 | 4 | 335.526912 | True | short_segments_filtered:4 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_path_extraction_20260619_123527\figures\path_extraction_u5c71_lishu.png` |
| 永 | lishu | 3 | 8 | 10 | 8 | 505.232539 | True | multi_component_skeleton;short_segments_filtered:12 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_path_extraction_20260619_123527\figures\path_extraction_u6c38_lishu.png` |

## Manual visual audit focus

- path 是否连续，还是仍有明显断裂？
- path 是否过碎，候选 segment 是否太多？
- 是否能看出可写主路径，而不是只是一团图像骨架？
- candidate order 是否明显不合理？
- 是否值得进入 font-derived trajectory trial？

## Boundary

本轮不是正式轨迹生成，不恢复真实笔顺，不替换 MakeMeAHanzi median，不修改 `style_profiles.json` 或 `run_demo.py`，也不调用 API、CoppeliaSim、AUBO 或 SDK。若人工看图认为 3 个以上样本可用，下一步才建议做 font-derived trajectory trial。
