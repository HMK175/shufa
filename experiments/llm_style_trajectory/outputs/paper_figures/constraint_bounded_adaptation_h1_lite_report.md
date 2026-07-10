# H1-lite constraint-bounded median adaptation prototype

H1-lite uses Route A median strokes plus H2 usable font-reference constraints. It is a trial-only diagnostic layer and is not used by default.

## Boundary

- 只使用 H2 中 `usable_for_adaptation` 的 bounded constraints。
- 不使用 raw skeleton path，不使用 unordered skeleton segments，不做最近点吸附。
- 保留 MakeMeAHanzi stroke_count、stroke order、stroke breaks 和点顺序。
- 不生成正式 trajectory.csv，不生成 execution/workspace/robot 文件，不接 run_demo 默认流程。

- output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\constraint_bounded_adaptation_h1_lite_20260619_231903`

## Results

| char | style | median aspect | target aspect | cons aspect | balanced aspect | median lower | target lower | cons lower | balanced lower | max shift cons | max shift balanced | path ratio cons | path ratio balanced | compare |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 人 | kaishu | 1.414861 | 1.345588 | 1.402621 | 1.392189 | 215.04 | 215.04 | 214.046706 | 213.207647 | 1.056528 | 1.776407 | 1.000038 | 1.000135 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\constraint_bounded_adaptation_h1_lite_20260619_231903\u4eba_kaishu\h1_lite_compare.png` |
| 山 | lishu | 0.945007 | 1.375 | 0.99887 | 1.048676 | 187.343097 | 203.214356 | 193.898937 | 199.553901 | 5.461121 | 9.845336 | 0.994134 | 0.989006 | `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\constraint_bounded_adaptation_h1_lite_20260619_231903\u5c71_lishu\h1_lite_compare.png` |

## Questions for manual visual audit

- H1-lite balanced 是否自然？
- conservative 是否太弱？
- 山/lishu 是否有更稳定的隶书宽底感，同时没有触达过高 shift cap？
- 人/kaishu 是否仍可写、没有过度变形？

## Interpretation

If H1-lite improves bbox/lower-half/spread metrics without large point shifts, it supports using H2 constraints as safer inputs for future B adaptation than raw skeleton pulling. Visual audit still decides whether the result is worth expanding.
