# 论文实验图表索引

记录日期：2026-06-13

本目录收集当前 `experiments/llm_style_trajectory` 阶段最适合用于论文或汇报的固定命名图表。源输出仍保留在各自 batch 目录中，本目录只作为论文整理入口。

## 1. 建议论文结构对应关系

| 论文位置 | 建议标题 | 使用图表 |
|---|---|---|
| 第 3 章 系统总体方案 | LLM planner 与本地确定性轨迹工具流程 | 方法流程图可根据 `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md` 重画 |
| 第 4 章 风格参数构建 | 三字体基础风格对比 | `fig_style_profile_compare_grid.png` |
| 第 5 章 自然语言约束驱动的轨迹生成 | style modifier 受控映射 | `fig_modifier_connection_shan.png`, `fig_modifier_shape_zhong.png`, `fig_modifier_smoothness_yong.png` |
| 第 5 章 二维执行层 | 中心线轨迹到执行轨迹 | `fig_execution_ablation_shan.png`, `execution_ablation_table.md` |
| 第 6 章 仿真前检查 | 工作空间映射、重采样与 CoppeliaSim dry-run | `fig_workspace_ablation_shan.png`, `fig_workspace_resampling_shan.png`, `fig_coppeliasim_standard_scene_shan.png` |
| 第 6 章 实验分析 | 基础风格、modifier、执行层、工作空间检查 | 本目录全部图表 |

## 2. 基础 Style Profile 对比

源目录：

```text
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/
```

固定图表：

| 文件 | 内容 |
|---|---|
| `fig_style_profile_compare_grid.png` | 5 字 x 3 风格总览 |
| `fig_style_profile_compare_shan.png` | 山：kaishu / xingkai / lishu |
| `fig_style_profile_compare_zhong.png` | 中：kaishu / xingkai / lishu |
| `fig_style_profile_compare_yong.png` | 永：kaishu / xingkai / lishu |
| `fig_style_profile_compare_fu.png` | 福：kaishu / xingkai / lishu |
| `fig_style_profile_compare_ming.png` | 明：kaishu / xingkai / lishu |

平均指标：

| style | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 0.920111 | 772.899 | 0.000 | 0.000 | 9.000000 | 602.907 | 0 |
| xingkai | 0.966550 | 863.159 | 5.600 | 90.279 | 8.991667 | 404.606 | 0 |
| lishu | 1.322317 | 758.556 | 0.000 | 0.000 | 10.000000 | 588.240 | 0 |

可写结论：

- `lishu` 的平均 aspect ratio 最高，体现宽扁趋势。
- `xingkai` 默认产生弱连接，`avg_connection_count` 与 `avg_connector_draw_length` 均高于 kaishu/lishu。
- `kaishu` 无跨笔连接，表现为保守基础风格。
- 三种风格均未超出工作空间范围。

注意：`path_length` 与 `workspace_path_length_mm` 属于不同坐标层指标，论文中不要混作同一个指标解释。

## 3. Style Modifier Ablation

### 3.1 连笔语义：山

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
```

固定图表：

```text
fig_modifier_connection_shan.png
```

| task | connection_preference | connection_strength | connection_count | path_length | pen_up_count | connector_mean_pressure | connector_mean_width |
|---|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 0.000 | 0 | 578.070 | 2 | 0.000 | 0.000 |
| 默认行楷山 | weak | 0.176 | 2 | 766.999 | 0 | 0.338 | 4.245 |
| 更连贯行楷山 | normal | 0.320 | 2 | 766.999 | 0 | 0.678 | 6.897 |

可写结论：自然语言中的“不要连笔 / 默认 / 更连贯”形成 `none -> weak -> normal` 梯度。修复后，`weak` 与 `normal` 都完整连接上一笔终点和下一笔起点，几何路径不再被 `connection_strength` 截断；二者主要差异体现在连接段压力和宽度上。

### 3.2 宽扁语义：中

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_085440/
```

固定图表：

```text
fig_modifier_shape_zhong.png
```

| task | shape_emphasis | horizontal_scale | vertical_scale | bbox_width | bbox_height | aspect_ratio |
|---|---:|---:|---:|---:|---:|---:|
| 隶书中 | normal | 1.1800 | 0.8200 | 175.851 | 176.333 | 0.997268 |
| 宽扁一点隶书中 | flatter | 1.2980 | 0.7544 | 193.446 | 162.226 | 1.192443 |
| 更宽隶书中 | wider | 1.2744 | 0.8200 | 190.540 | 176.333 | 1.080569 |

可写结论：`flatter` 同时增宽并压低高度，aspect ratio 提升最大；`wider` 主要增宽并保留原高度。

### 3.3 圆滑语义：永

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_085440/
```

固定图表：

```text
fig_modifier_smoothness_yong.png
```

| task | smoothness_level | smoothness | path_length | mean_turning | total_turning_angle | max_turning_angle | connection_preference | connection_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 楷书永 | medium | 0.180 | 649.156 | 0.099365 | 10.632062 | 0.971813 | weak | 0 |
| 更圆滑楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 更平滑楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 更保守行楷永 | low | 0.231 | 653.408 | 0.081651 | 10.696220 | 1.048066 | none | 0 |

可写结论：`mean_turning` 变化较小，应优先使用 `total_turning_angle` 与 `max_turning_angle` 展示圆滑度变化。

## 4. 二维执行层

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
```

固定图表：

| 文件 | 内容 |
|---|---|
| `fig_execution_ablation_shan.png` | none / weak / normal 执行层总览 |
| `fig_execution_none_render.png` | 不连笔 render |
| `fig_execution_weak_render.png` | weak connector render |
| `fig_execution_normal_render.png` | normal connector render |
| `fig_execution_none_debug.png` | 不连笔 debug |
| `fig_execution_weak_debug.png` | weak connector debug |
| `fig_execution_normal_debug.png` | normal connector debug |
| `execution_ablation_table.md` | 执行层指标表 |

关键指标：

| task | connection_preference | connector_draw_length | pen_up_move_length | connector_mean_pressure | connector_mean_width | mean_width | mean_pressure |
|---|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 0.000 | 188.929 | 0.000 | 0.000 | 9.500000 | 1.000000 |
| 默认行楷山 | weak | 188.929 | 0.000 | 0.338 | 4.245 | 8.205479 | 0.836935 |
| 更连贯行楷山 | normal | 188.929 | 0.000 | 0.678 | 6.897 | 8.858823 | 0.920684 |

可写结论：execution layer 比中心线轨迹更能表达连笔差异，因为它显式记录 `pressure`、`width`、`pen_down`、`is_connector` 和 `segment_type`。修复后，连笔几何完整性由 connector 负责，`connection_strength` 主要体现在连接段执行属性上。

## 5. 工作空间映射、重采样与 CoppeliaSim Dry-Run

源目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
```

固定图表：

```text
fig_workspace_ablation_shan.png
fig_workspace_resampling_shan.png
fig_coppeliasim_standard_scene_shan.png
coppeliasim_standard_scene_result.md
coppeliasim_standard_scene_result.json
```

CoppeliaSim dry-run 关键指标：

| task | connection_preference | point_count | max_step_3d_mm | max_xy_step_mm | max_z_step_mm | stroke_count | connector_count | pen_up_move_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 258 | 8.000 | 4.749 | 8.000 | 237 | 0 | 21 |
| 默认行楷山 | weak | 275 | 2.488 | 2.488 | 0.000 | 237 | 38 | 0 |
| 更连贯行楷山 | normal | 275 | 2.488 | 2.488 | 0.000 | 237 | 38 | 0 |

可写结论：三组轨迹均未越出纸面工作空间。`none` 的最大 3D 跳变来自 8mm Z 轴抬笔，XY 最大步长仍小于 5mm；`weak/normal` 在修复后不再出现 35mm / 43mm 的 XY 段间跳变，重采样后最大 XY 步长约 2.488mm，满足进入 CoppeliaSim 笔尖路径播放的基本连续性要求。

### 5.1 标准书写场景真实播放结果

源任务：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `fig_coppeliasim_standard_scene_shan.png` | 120mm x 120mm 纸面、坐标轴、边界和 weak 行楷山路径示意图 |
| `coppeliasim_standard_scene_result.md` | 真实播放结果表 |
| `coppeliasim_standard_scene_result.json` | 真实播放结果原始 JSON |
| `coppeliasim_standard_scene_index.md` | 标准场景资料索引 |

关键结果：

| status | simulation_stopped | recommended_playback | point_count | max_xy_step_mm | max_z_step_mm | paper_size_mm |
|---|---|---|---:|---:|---:|---:|
| finished | true | true | 275 | 2.487672 | 0.0 | 120.0 |

可写结论：标准 CoppeliaSim 纸面场景已能自动创建并完成 weak 行楷山的真实播放。轨迹位于 `120mm x 120mm` 纸面范围内，播放结束后自动停止仿真。当前仍是 pen-tip/sphere scene，不包含机械臂 IK。

## 6. 当前推荐使用顺序

论文或汇报中建议按以下顺序展示：

1. `fig_style_profile_compare_grid.png`：先证明三种基础风格不同。
2. `fig_modifier_connection_shan.png`：证明自然语言可控制连笔。
3. `fig_modifier_shape_zhong.png`：证明自然语言可控制宽扁。
4. `fig_modifier_smoothness_yong.png`：证明自然语言可控制圆滑。
5. `fig_execution_ablation_shan.png`：证明 execution layer 能表达笔压/笔宽/抬笔状态。
6. `fig_workspace_ablation_shan.png`：证明轨迹已能映射到机器人纸面坐标。
7. `fig_workspace_resampling_shan.png`：证明重采样与 playback dry-run 能发现并消除段间跳变风险。
8. `fig_coppeliasim_standard_scene_shan.png`：证明轨迹进入固定 CoppeliaSim 书写工作空间并完成标准场景播放。

## 7. 边界说明

- 当前图表展示的是参数化 style profile 与受控 modifier 的效果。
- 当前尚不是完整真实书法风格学习。
- 当前已完成 CoppeliaSim pen-tip/sphere 最小路径播放和 dry-run 检查，但尚未接入真实机械臂模型、IK、真实动力学或控制器。
- LLM/API planner 不直接输出 CSV 或轨迹点，仍由本地确定性工具生成。
