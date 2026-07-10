# 小论文人工视觉评价模板

## 目的

本模板用于对 `mini_paper_figures` 固定图表包做人工看图评价。当前数值指标只能说明参数和几何层面的变化，不能替代对图像直观效果的判断。尤其是风格差异、行楷连笔自然度、笔画粗细变化、隶书宽扁形态和布局自然度，都需要人工目检后再决定是否适合作为论文主图。

固定图表包目录：

```text
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/
```

配套 CSV 模板：

```text
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/human_visual_evaluation_template.csv
```

## 评分规则

`score_1_to_5` 建议按以下标准填写：

| 分数 | 含义 |
|---:|---|
| 1 | 不适合作为论文图，视觉问题明显 |
| 2 | 可作为诊断图，但不适合作为正文主图 |
| 3 | 可用，但需要图注中明确局限 |
| 4 | 适合作为正文图，仍可小幅润色 |
| 5 | 非常适合作为正文主图，效果清楚 |

`accept_for_paper` 建议填写：

- `yes`：可作为正文主图。
- `supplementary`：适合作为补充材料。
- `revise`：需要重新制图或换样本。
- `no`：不建议使用。

## 人工评价重点

### Figure 2 modifier 可控性

- `fig2_modifier_control_connection.png`：看“不要连笔 / 默认 weak / 更连贯 normal”的差异是否直观，weak/normal connector 是否自然。
- `fig2_modifier_control_shape.png`：看宽扁和更宽是否肉眼可分，隶书是否只是横向拉宽/纵向压扁。
- `fig2_modifier_control_smoothness.png`：看圆滑/平滑是否能通过转折和整体曲线感看出来，不要只依赖 `mean_turning`。

### Figure 3 行楷 connector rule

- `fig3_xingkai_connector_levels_u56fd.png`、`fig3_xingkai_connector_levels_u5fb7.png`、`fig3_xingkai_connector_levels_u660e.png`：看 all-adjacent 是否过多、conservative 是否偏少、balanced 是否是可接受折中。
- 注意 `candidate_default_v2` 只能写作“折中候选规则”，不能写成真实行楷规则或最终默认。

### Figure 4 execution width / pressure

- `fig4_execution_width_pressure.png`：看 stroke taper 是否可见，connector 是否更细/低压，颜色和线宽编码是否容易读。
- 如果主体 stroke 粗细变化不明显，应在图注里写成“执行层字段可视化”而不是“真实笔刷效果”。

### Supplementary style gap

- `supplementary/supp_font_style_grid.png` 与 `supplementary/supp_lishu_flatness_gap.png`：看隶书是否仍偏“压扁楷书”，以及真实字体轮廓与当前轨迹之间的差距。
- 这些图适合支撑“限制与未来工作”，不建议写成主结果。

## 必须避免的过度表述

- 不写“实现真实书法风格学习”。
- 不写“隶书风格已经真实复现”。
- 不写“行楷 connector 来自真实书写学习”。
- 不写“CoppeliaSim/AUBO 真实机器人实验完成”。
- 不把外部方法功能对比表写成数值复现。

## 建议人工评价流程

1. 先打开 `mini_paper_figure_index.md`，确认所有图表位置。
2. 按 `human_visual_evaluation_template.csv` 逐行看图并填写分数。
3. 对评分低于 3 的图，在 `revision_suggestion` 中写明是“换样本”“重画图”“放补充材料”还是“暂不使用”。
4. 对 `accept_for_paper=yes` 的图，再把 `mini_paper_figure_captions_draft.md` 中的图注改成最终论文版本。
5. 对涉及风格真实性的图，优先把结论写保守：当前是参数化控制，不是真实风格学习。
