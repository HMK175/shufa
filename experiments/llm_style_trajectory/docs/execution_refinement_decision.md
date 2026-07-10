# Execution Refinement 人工反馈与候选默认记录

记录日期：2026-06-18

## 背景

上一轮 `execution_refinement_20260618_104837` 针对三个问题做了执行层实验：

1. 行楷 connector 过多，旧逻辑接近“相邻笔画首尾依次相连”。
2. 主体 stroke 内部 width / pressure 几乎恒定，缺少起笔、中段、收笔变化。
3. width / pressure 渐变图浅色端接近白色，connector 在白底上不易看清。

本轮只做人工反馈归档、候选默认标记和可疑字段核查。本轮不继续调参数，不扩大实验，不接机器人接口，不调用 API，不连接 CoppeliaSim 或 AUBO i5，不做 IK/SDK/实机控制。

## 人工反馈

用户人工看图反馈摘要：

- 行楷连笔确实变自然了，但现在基本只有一两笔连笔，略显偏少；暂时先接受。
- stroke 粗细变化可以看出来，效果不错。
- 隶书一共两张图，没有出现连笔。
- `人/lishu connector_draw_length: 0.0 -> 3.3998` 看起来可疑，需要核查。

## 决策

将当前 `conservative connector + simple_taper` 标记为：

```text
candidate_default_v1
```

配置位置：

```text
experiments/llm_style_trajectory/configs/execution_refinement_profiles.json
```

对应关系：

- `connector_rule`: `conservative`
- `stroke_width_profile`: `simple_taper`
- `status`: `accepted_for_next_round_candidate`

该候选配置暂不作为全局默认。当前 `execution_tools.py` 默认仍保持旧兼容行为：不显式传入 refinement 参数时，继续使用 baseline connector 行为和 flat stroke width profile。

## 可疑字段核查

核查对象：

```text
experiments/llm_style_trajectory/outputs/execution_refinement_20260618_104837/cases/u4eba_lishu/refined_execution_trajectory.csv
experiments/llm_style_trajectory/outputs/execution_refinement_20260618_104837/execution_refinement_summary.csv
```

核查结果：

- `人/lishu` refined execution 中 `segment_type=connector` 行数为 0。
- `人/lishu` refined execution 中 `is_connector=1` 行数为 0。
- `人/lishu` refined execution 中存在 `pen_up_move` 行，表示跨笔移动仍是抬笔移动。
- summary 中 `before_connector_draw_length = 0.0`。
- summary 中 `after_connector_draw_length = 0.0`。
- summary 中 `after_stroke_width_range = 3.3998`。

结论：`3.3998` 不是 connector_draw_length，而是 `after_stroke_width_range`。当前 summary/report 字段本身没有发现错位；用户看到的可疑值属于表格阅读时的字段混淆。lishu 仍不允许 connector，本轮核查没有发现隶书误连笔。

## 后续建议

- 暂时接受 `candidate_default_v1`，但只作为下一轮候选默认，不直接提升为全局默认。
- 后续可以设计一个介于当前 conservative 和旧 all-adjacent 之间的 `balanced` connector 档位，用来缓解“现在偏保守”的问题。
- 在调参前，先扩大样本做人工看图包，确认不同结构汉字中 connector 保留数量是否稳定。
- 若继续优化 stroke taper，下一步应从笔画级宽度模型入手，而不是只靠全局 scale。

## 边界

- 本轮不是最终行楷规则。
- 本轮不是真实笔刷模型。
- 本轮不解决 lishu 真实风格来源问题。
- 本轮不继续调参数。
- 本轮不调用 API、不连接 CoppeliaSim、不连接 AUBO i5、不 import 或执行 `libpyauboi5`、不发送机器人命令。
