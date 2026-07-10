# Xingkai Balanced Experiment Index

- source_output_dir: `D:\sw data\vscode\shufa\experiments\llm_style_trajectory\outputs\xingkai_balanced_experiment_20260618_141424`
- scope: balanced connector + local xingkai execution diagnostics only; no API, no CoppeliaSim, no AUBO i5.

| File | Content |
|---|---|
| `xingkai_balanced_report.md` | balanced 实验报告 |
| `xingkai_balanced_summary.csv` | baseline/conservative/balanced 指标汇总 |
| `experiments/llm_style_trajectory/docs/xingkai_balanced_decision.md` | 用户人工反馈归档与 `candidate_default_v2` 决策 |
| `xingkai_balanced_compare_connector_levels_u56fd_xingkai.png` | 国 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u5fb7_xingkai.png` | 德 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u798f_xingkai.png` | 福 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u548c_xingkai.png` | 和 / 行楷三档对比图 |
| `xingkai_balanced_compare_connector_levels_u4e2d_xingkai.png` | 中 / 行楷三档对比图 |

这些图需要人工看图判断 balanced 是否比 conservative 更像行楷，同时不过度连笔。

人工反馈已归档：balanced 变化不激进、曲线 connector 更像“带过去”，当前可接受为
`candidate_default_v2`，但暂不替换全局默认，也不直接进入仿真书写。
