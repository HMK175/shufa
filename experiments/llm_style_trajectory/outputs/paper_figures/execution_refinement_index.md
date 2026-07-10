# Execution Refinement Index

- source_output_dir: `experiments\llm_style_trajectory\outputs\execution_refinement_20260618_104837`
- scope: connector trigger and stroke taper diagnostics only; no API, no CoppeliaSim, no robot SDK, no IK.
- decision_doc: `experiments\llm_style_trajectory\docs\execution_refinement_decision.md`
- candidate marker: `candidate_default_v1 = conservative connector + simple_taper`
- status: accepted as next-round candidate only; not promoted to global default.

| File | Content |
|---|---|
| `execution_refinement_report.md` | 实验报告 |
| `execution_refinement_summary.csv` | before/after 指标 |
| `execution_refinement_before_after_connector_u56fd_xingkai.png` | 代表性 before/after 或 width/pressure 图 |
| `execution_refinement_before_after_connector_u5fb7_xingkai.png` | 代表性 before/after 或 width/pressure 图 |
| `execution_refinement_before_after_connector_u798f_xingkai.png` | 代表性 before/after 或 width/pressure 图 |
| `execution_refinement_width_pressure_refined_u56fd_xingkai.png` | 代表性 before/after 或 width/pressure 图 |
| `execution_refinement_width_pressure_refined_u5fb7_xingkai.png` | 代表性 before/after 或 width/pressure 图 |

这些图需要人工看图确认，不能只看指标判断最终书法效果。

## Human Feedback Archive

用户人工看图反馈已经归档：

- 行楷 connector 自然度改善，但当前偏保守，基本只有一两笔连笔；暂时接受。
- simple_taper 的 stroke 粗细变化可见，效果不错。
- lishu 两张图未观察到连笔。
- `人/lishu` 可疑字段已核查：refined execution 中 `segment_type=connector` 和 `is_connector=1` 均为 0；summary 中 `after_connector_draw_length=0.0`，`3.3998` 是 `after_stroke_width_range`。

后续建议不是继续盲调，而是扩大样本或设计 `balanced` connector 档位后再看图比较。
