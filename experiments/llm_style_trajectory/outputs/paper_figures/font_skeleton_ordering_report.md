# Font skeleton stroke ordering / simplification prototype

本轮只处理 `人/kaishu` 和 `山/lishu` 两个极小样本。

## 边界说明

- 这仍不是正式轨迹，不生成正式 `trajectory.csv`。
- 这不是真实笔顺恢复，只是一个 `candidate writable order`。
- 本轮不接默认 pipeline，不替换 MakeMeAHanzi median。
- 本轮不接机器人，不生成 execution/workspace/CoppeliaSim/AUBO 文件。

## 输出目录

`D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543`

## 样本结果

| char | style | raw_segment_count | simplified_segment_count | ordered_stroke_like_count | warning | recommended_for_next_stage | compare |
|---|---|---:|---:|---:|---|---|---|
| 人 | kaishu | 4 | 2 | 2 |  | True | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543\u4eba_kaishu\font_skeleton_ordering_compare.png` |
| 山 | lishu | 4 | 4 | 4 | segment_count_unchanged | True | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\font_skeleton_stroke_ordering_20260619_132543\u5c71_lishu\font_skeleton_ordering_compare.png` |

## 人工看图问题

- segment 是否明显少了？
- 顺序是否比 raw trial 更像可写？
- 是否保留字体风格？
- 是否还过碎？
- 是否值得进入下一步 font-derived execution mock？

## 初步建议

如果人工看图认为两个样本的候选顺序比 raw trial 更可写，可以进入一个仍然离线的 font-derived execution mock；
如果仍然过碎或顺序明显不自然，应先继续做 graph simplification 与人工 stroke grouping。
