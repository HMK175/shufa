# Font skeleton stroke ordering prototype index

本索引固定 font-outline basis 主线中极小样本 stroke ordering / simplification prototype 的结果。

## Source

- Output directory: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543`
- Summary: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543\font_skeleton_ordering_summary.csv`
- Report: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543\font_skeleton_ordering_report.md`

## Samples

| char | style | raw -> simplified | ordered_stroke_like_count | compare |
|---|---|---:|---:|---|
| 人 | kaishu | 4 -> 2 | 2 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543\u4eba_kaishu\font_skeleton_ordering_compare.png` |
| 山 | lishu | 4 -> 4 | 4 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543\u5c71_lishu\font_skeleton_ordering_compare.png` |

## Boundary

该结果不是正式轨迹，不是真实笔顺恢复，也不接机器人；仅用于人工判断字体骨架是否能整理成更可写的候选路径。
