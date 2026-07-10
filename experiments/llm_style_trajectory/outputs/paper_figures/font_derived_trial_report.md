# Font-derived trajectory trial

本轮只处理 3 个低风险样本，把 extracted path segments 转成 font-derived candidate trajectory。它不是正式轨迹，不含真实笔顺，不含执行层 width/pressure，不接机器人，也不接默认 pipeline。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_derived_trajectory_trial_20260619_125428`
- samples: 山/kaishu, 人/kaishu, 山/lishu
- excluded: xingkai, 中/kaishu, 永/lishu, 德/福/国/风, other complex chars
- CSV name is intentionally `font_derived_trial_trajectory.csv`; no formal `trajectory.csv` is written.

## Trial samples

| char | style | segments | points | total_path_px | median_path_px | recommended | warning | compare_png |
|---|---|---:|---:|---:|---:|---|---|---|
| 山 | kaishu | 7 | 19 | 355.296465 | 585.008418 | True | short_segments_filtered:10 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_derived_trajectory_trial_20260619_125428\u5c71_kaishu\font_derived_trial_compare.png` |
| 人 | kaishu | 4 | 19 | 318.788888 | 352.462819 | True | short_segments_filtered:2 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_derived_trajectory_trial_20260619_125428\u4eba_kaishu\font_derived_trial_compare.png` |
| 山 | lishu | 4 | 16 | 335.526912 | 585.008418 | True | short_segments_filtered:4 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_derived_trajectory_trial_20260619_125428\u5c71_lishu\font_derived_trial_compare.png` |

## Manual visual questions

- trial trajectory 是否比 MakeMeAHanzi median 更有字体风格？
- 路径是否过碎，是否还需要 simplification？
- segment order 是否看起来严重不合理？
- 是否适合作为下一步 stroke ordering / simplification 的输入？

## Boundary

这不是正式轨迹，不含真实笔顺，不含执行层 width/pressure，不生成 execution_trajectory、robot_workspace、CoppeliaSim 或 AUBO 文件。当前只用于判断 font-outline basis 是否值得继续。
