# balanced 行楷 refinement 人工反馈与 candidate_default_v2 记录

记录日期：2026-06-18

## 背景

上一轮 `candidate_default_v1` 使用 `conservative connector + simple_taper`。
用户人工看图后认为 v1 的 connector 更自然，但整体偏保守，行楷仍容易像
“楷书骨架 + 少量连笔 + taper”。因此本轮做了一个介于旧 `baseline/all_adjacent`
和 v1 `conservative` 之间的 balanced 诊断实验：

```text
experiments/llm_style_trajectory/outputs/xingkai_balanced_experiment_20260618_141424/
```

本轮收口只做人工反馈归档和候选默认标记，不继续调参数，不替换全局默认，
不扩大实验，不进入仿真书写，不连接 CoppeliaSim/AUBO i5，也不调用 API 或 SDK。

## balanced 指标

| metric | baseline | conservative v1 | balanced |
|---|---:|---:|---:|
| xingkai connection_count sum | 58 | 5 | 10 |
| xingkai connector_draw_length sum | 4938.116 | 349.252 | 586.339 |

行楷样本中，balanced 没有回到 baseline 的全连状态，也比 conservative 多保留了一些连接。
`福` 的连接数量仍为 1，但 connector 位置发生变化。`中/人` 仍然清零，说明 balanced
对简单结构字仍偏谨慎。

## 用户人工反馈

用户对 balanced 版本的人工反馈摘要：

- 每个字基本只多了一笔连笔，变化不激进。
- `福` 的连笔数量仍然是 1，但换了个位置。
- 目前 balanced 效果可以接受。
- 曲线 connector 更像“带过去”，都是曲线而不是直线。
- 仍不直接进入仿真书写，继续作为候选执行层。

## 决策

将当前 balanced 版本标记为：

```text
candidate_default_v2
```

配置位置：

```text
experiments/llm_style_trajectory/configs/execution_refinement_profiles.json
```

对应关系：

- `connector_rule`: `balanced`
- `connector_shape`: `slight_curve`
- `stroke_width_profile`: `xingkai_expressive_taper`
- `status`: `accepted_for_next_round_candidate`

`candidate_default_v2` 暂不替换全局默认。当前默认 execution 行为仍保持兼容；
只有显式选择 refinement 配置时才会使用 v2。

`candidate_default_v1` 继续保留为 conservative refined baseline：

- `connector_rule`: `conservative`
- `stroke_width_profile`: `simple_taper`
- `status`: `accepted_for_next_round_candidate`

后续更多样本或论文图可以优先使用 v2 作为行楷 refinement 候选，但不应把它描述为最终模型。

## 边界

- 这不是最终行楷模型。
- 这不是真实书法学习。
- 这不解决隶书真实风格来源问题。
- 这不代表真实机器人书写效果。
- 当前不进入仿真书写，不连接 CoppeliaSim，不连接 AUBO i5。
- 当前不调用 DeepSeek/API，不 import 或执行 `libpyauboi5`，不发送机器人命令。

## 下一步建议

- 如果后续更多样本人工看图也接受 v2，可考虑把它作为论文中的 refined execution baseline。
- 如果 v2 仍偏保守，可再设计更温和放宽的 connector gate，但应另开实验，不能在本轮继续调参。
- 如果 v2 视觉过连，则回到 v1 conservative baseline。
