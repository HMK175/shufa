# LLM Style Trajectory 阶段总结

记录日期：2026-06-13

## 1. 当前主线

当前 `experiments/llm_style_trajectory` 已经形成一条独立于旧图像骨架流程的实验路线：

```text
用户自然语言
-> LLM / mock planner
-> request boundary validation
-> style_modifiers
-> style profile + whitelist mapping
-> Make Me a Hanzi median trajectory
-> trajectory CSV
-> execution trajectory
-> robot workspace trajectory
-> resampled workspace trajectory
-> CoppeliaSim pen-tip path playback
-> style-aware brush rendering
-> virtual metrics
```

这条路线的核心原则是：**LLM 不直接生成 CSV 或轨迹点**。LLM 只负责自然语言任务解析、风格选择、约束生成和 modifier 规划；轨迹仍由本地结构化知识和确定性工具生成。

## 2. 方法定位

本阶段可以支撑的论文表述：

> 本研究将自然语言书写意图转化为离散的风格修饰符，并通过本地白名单映射函数将其转化为可解释的轨迹参数变化。系统结合 Make Me a Hanzi 的笔顺/median 信息、字体统计得到的 style profile，以及 style-aware brush rendering，实现多风格书法机器人轨迹的参数化生成与虚拟评价。

需要避免的过度表述：

- 不应称为真实书法风格学习。
- 不应称为 LLM 直接生成机器人轨迹。
- 不应称为可以处理任意真实书法图像。
- 不应把 `connection_strength`、`pen_up_height` 等过程参数说成由静态字体图像可靠估计得到。

## 3. 关键模块

| 模块 | 作用 | 主要文件 |
|---|---|---|
| Planner | 解析自然语言任务，输出结构化 plan | `experiments/llm_style_trajectory/src/planner.py` |
| Request validation | 拒绝 unsupported style、多字输入、危险字段 | `experiments/llm_style_trajectory/src/planner.py` |
| Style modifiers | 离散语义修饰符到参数变化 | `experiments/llm_style_trajectory/src/style_modifiers.py` |
| Knowledge | 读取 Make Me a Hanzi 字形、笔顺、median | `experiments/llm_style_trajectory/src/knowledge.py` |
| Trajectory tools | 生成 styled trajectory、CSV、几何指标和预览 | `experiments/llm_style_trajectory/src/trajectory_tools.py` |
| Execution layer | 将中心线扩展为含压力、宽度、速度和抬笔状态的二维执行轨迹 | `experiments/llm_style_trajectory/src/execution_tools.py` |
| Workspace mapping | 将图像坐标执行轨迹映射到机器人纸面工作空间，并做仿真前检查 | `experiments/llm_style_trajectory/src/workspace_mapping.py` |
| Workspace resampling | 对机器人工作空间轨迹做分段重采样和速度规划，降低末端跳点风险 | `experiments/llm_style_trajectory/src/workspace_resampling.py` |
| CoppeliaSim bridge | 播放重采样后的纸面工作空间轨迹，验证笔尖路径可进入三维仿真环境 | `experiments/llm_style_trajectory/coppeliasim/play_workspace_path.py` |
| Style profile compare | 批量比较 kaishu / xingkai / lishu 基础风格在三层指标上的差异 | `experiments/llm_style_trajectory/src/style_profile_compare.py` |
| Render/eval | 虚拟书写渲染与评价 | `experiments/llm_style_trajectory/src/render_eval.py` |
| Batch runner | 批量 demo、summary 和对比图 | `experiments/llm_style_trajectory/src/run_demo.py` |

## 4. 已完成实验

### 4.1 DeepSeek API planner 鲁棒性

输出目录：

```text
experiments/llm_style_trajectory/outputs/planner_robustness_20260608_163557/
```

关键结果：

| 指标 | 结果 |
|---|---:|
| total | 12 |
| validation_ok_count | 9 |
| char_correct_count | 11 |
| style_correct_count | 10 |
| connection_constraint_correct_count | 12 |
| expected_invalid_rejected_count | 3 |
| dangerous_output_count | 0 |
| json_parse_success_count | 12 |
| average_latency | 10.3482 |

结论：DeepSeek-V4-Pro 可以作为文本 planner 基准继续使用，但必须保留本地 request boundary + schema validation。草书、火星文、多字输入等越界请求由本地校验拒绝，而不是依赖 prompt 自觉。

### 4.2 连笔语义 ablation

输出目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260611_210502/
experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_ablation_u5c71.png
```

| task | connection_preference | connection_strength | connection_count | path_length | pen_up_count | mean_turning |
|---|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 0.000 | 0 | 578.070 | 2 | 0.053843 |
| 默认行楷山 | weak | 0.176 | 2 | 611.321 | 0 | 0.053843 |
| 更连贯行楷山 | normal | 0.320 | 2 | 638.527 | 0 | 0.053843 |

结论：自然语言中的“不要连笔 / 默认 / 更连贯”可以形成 `none -> weak -> normal` 的语义梯度，并在连接强度、路径长度和抬笔次数上体现出来。

### 4.3 宽扁语义 ablation

输出目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_085440/
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_shape_u4e2d.png
```

| task | shape_emphasis | horizontal_scale | vertical_scale | bbox_width | bbox_height | aspect_ratio |
|---|---:|---:|---:|---:|---:|---:|
| 隶书中 | normal | 1.1800 | 0.8200 | 175.851 | 176.333 | 0.997268 |
| 宽扁一点隶书中 | flatter | 1.2980 | 0.7544 | 193.446 | 162.226 | 1.192443 |
| 更宽隶书中 | wider | 1.2744 | 0.8200 | 190.540 | 176.333 | 1.080569 |

结论：`flatter` 同时增宽并压低高度，aspect ratio 提升最大；`wider` 主要增宽并保留原高度，语义边界比 `flatter` 更温和。

### 4.4 圆滑语义 ablation

输出目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_085440/
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_smoothness_u6c38.png
```

| task | smoothness_level | smoothness | path_length | mean_turning | total_turning_angle | max_turning_angle | connection_preference | connection_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 楷书永 | medium | 0.180 | 649.156 | 0.099365 | 10.632062 | 0.971813 | weak | 0 |
| 更圆滑楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 更平滑楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 更保守行楷永 | low | 0.231 | 653.408 | 0.081651 | 10.696220 | 1.048066 | none | 0 |

结论：`mean_turning` 对圆滑度变化不够敏感，后续论文展示应优先使用 `total_turning_angle` 和 `max_turning_angle`。`high` smoothness 可以降低总转向量和最大转向角，说明转折有所减弱。

### 4.5 二维执行层增强

输出目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/
experiments/llm_style_trajectory/outputs/batch_20260613_092733/modifier_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/execution_ablation_u5c71.png
experiments/llm_style_trajectory/outputs/paper_figures/
```

`execution_trajectory.csv` 在保留旧 `trajectory.csv` 的基础上，增加面向虚拟书写和机器人执行准备的字段：

| 字段 | 含义 |
|---|---|
| `stroke_id` / `point_id` | 笔画编号和点编号 |
| `y` / `x` / `z` | 二维图像坐标和抬笔高度 |
| `speed` | 执行速度系数 |
| `pressure` | 笔压或落笔强度 |
| `width` | 渲染/执行笔宽 |
| `pen_down` | 是否落笔 |
| `is_connector` | 是否为连笔连接段 |
| `segment_type` | `stroke` / `connector` / `pen_up_move` |

| task | connection_preference | connector_draw_length | pen_up_move_length | connector_mean_pressure | connector_mean_width | mean_width | mean_pressure |
|---|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | none | 0.000 | 188.929 | 0.000 | 0.000 | 9.500000 | 1.000000 |
| 默认行楷山 | weak | 33.251 | 0.000 | 0.340 | 4.275 | 9.215798 | 0.964101 |
| 更连贯行楷山 | normal | 60.457 | 0.000 | 0.680 | 6.840 | 9.248145 | 0.969702 |

结论：二维执行层把中心线之外的执行状态显式化。`none` 保留抬笔移动但不留下连接痕迹；`weak` 产生低压细连接；`normal` 产生更长、更高压力、更宽的连接段。因此，execution layer 比单纯中心线轨迹更适合作为进入三维机械臂仿真前的中间表示。

### 4.6 机器人工作空间映射与仿真前检查

输出目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_mapping_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_mapping_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_ablation_u5c71.png
```

映射规则：

```text
X_mm = (x / image_size - 0.5) * paper_width_mm
Y_mm = (0.5 - y / image_size) * paper_height_mm
Z_mm = 0 for stroke/connector pen-down points
Z_mm = pen_up_height_mm for pen-up move points
speed_mm_s = base_speed_mm_s * execution_speed
```

默认参数为 `image_size=256`、`paper_width_mm=120`、`paper_height_mm=120`、`pen_up_height_mm=8`、`base_speed_mm_s=30`。

| task | segment_counts | workspace_path_length_mm | max_step_mm | out_of_bounds | z_range | pen_up_move_length_mm |
|---|---|---:|---:|---|---|---:|
| 不要连笔行楷山 | `{"pen_up_move": 2, "stroke": 3}` | 359.531 | 52.241 | False | 0.000..8.000 | 88.560 |
| 默认行楷山 | `{"connector": 2, "stroke": 3}` | 286.557 | 9.194 | False | 0.000..0.000 | 0.000 |
| 更连贯行楷山 | `{"connector": 2, "stroke": 3}` | 299.310 | 16.717 | False | 0.000..0.000 | 0.000 |

结论：三组山字均在 120mm x 120mm 纸面边界内。`none` 的最大步长来自抬笔移动，`normal` 的最大 connector step 略高于 15mm 阈值，后续进入 CoppeliaSim / RoboDK 前建议增加 connector/pen-up move 重采样或速度规划。本轮未接任何三维仿真器，只生成 `robot_workspace_trajectory.csv` 和检查报告。

### 4.7 三字体基础风格对比

输出目录：

```text
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_profile_compare_summary.csv
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_profile_compare_report.md
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_compare_grid.png
```

任务覆盖 `山 / 中 / 永 / 福 / 明` 五个字，每个字生成 `kaishu`、`xingkai`、`lishu` 三种基础风格，共 15 个任务。每个任务均生成 `trajectory.csv`、`execution_trajectory.csv`、`robot_workspace_trajectory.csv`、`preview.png`、`execution_render.png`、`execution_debug.png`、`workspace_path_preview.png` 和 `summary.json`。

| style | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 0.920111 | 772.899 | 0.000 | 0.000 | 9.000000 | 602.907 | 0 |
| xingkai | 0.966550 | 863.159 | 5.600 | 90.279 | 8.991667 | 404.606 | 0 |
| lishu | 1.322317 | 758.556 | 0.000 | 0.000 | 10.000000 | 588.240 | 0 |

结论：三种基础 style profile 已形成可解释差异。`lishu` 的平均 aspect ratio 最高，表现出宽扁倾向；`xingkai` 默认弱连接，`connection_count` 和 `connector_draw_length` 明显高于其他两种；`kaishu` 无跨笔连接，更适合作为保守基准。所有任务均未发生工作空间越界。

### 4.8 工作空间轨迹重采样与速度规划

输出目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_resampling_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_resampling_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_resampling_ablation_u5c71.png
```

重采样规则：

```text
stroke max step <= 2.0 mm
connector max step <= 2.5 mm
pen_up_move max step <= 5.0 mm
```

速度规划采用分段常数：

```text
stroke: 25 mm/s
weak connector: 40 mm/s
normal connector: 32 mm/s
pen_up_move: 70 mm/s
```

| task | original_points | resampled_points | original_max_step_mm | resampled_max_step_mm | stroke_max_step_mm | connector_max_step_mm | pen_up_move_max_step_mm | estimated_duration_s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 不要连笔行楷山 | 125 | 258 | 52.241 | 4.749 | 1.888 | 0.000 | 4.749 | 12.103962 |
| 默认行楷山 | 125 | 246 | 9.194 | 2.299 | 1.888 | 2.299 | 0.000 | 11.228480 |
| 更连贯行楷山 | 125 | 251 | 16.717 | 2.388 | 1.888 | 2.388 | 0.000 | 11.724427 |

结论：重采样后，none 的抬笔大跳点从 52.241mm 降到 4.749mm；normal connector 的超阈值点距从 16.717mm 降到 2.388mm，满足后续仿真前的分段点距约束。当前仍未接入三维仿真器，只生成 `robot_workspace_trajectory_resampled.csv`、速度规划报告和预览图。

### 4.9 CoppeliaSim 最小笔尖轨迹播放

验证对象：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/u5c71_xingkai_20260613_092733_979792/robot_workspace_trajectory_resampled.csv
```

本机 CoppeliaSim 路径：

```text
D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win
```

环境准备：

```powershell
$env:PYTHONPATH="D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win\programming\zmqRemoteApi\clients\python\src;$env:PYTHONPATH"
python -m pip install pyzmq cbor
python -c "from coppeliasim_zmqremoteapi_client import RemoteAPIClient; print('ok')"
```

dry-run 结果：

| 指标 | 结果 |
|---|---:|
| point_count | 258 |
| stroke points | 237 |
| pen_up_move points | 21 |
| X range | -49.057031..48.721406 mm |
| Y range | -49.392188..49.392188 mm |
| Z range | 0.0..8.0 mm |
| duration_estimate_s | 12.972534 |
| max_step_mm | 8.0 |

真实播放命令：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --speed-scale 1.0
```

结论：CoppeliaSim 最小接入已验证成功，重采样后的工作空间 CSV 能驱动仿真中的 paper plane、pen-tip sphere 和路径段可视化。当前仍只是笔尖/球体路径播放，不包含机械臂模型、逆运动学、末端工具标定、碰撞检测或控制器调参。dry-run 中 `max_step_mm=8.0` 是三维相邻点距离，可能包含 Z 轴从 0mm 到 8mm 的抬笔高度变化；后续更严谨的仿真报告应拆分 `max_step_3d_mm`、`max_xy_step_mm` 和 `max_z_step_mm`。

### 4.10 CoppeliaSim 播放评价层：低负载播放与 batch dry-run

本轮在 `experiments/llm_style_trajectory/coppeliasim/` 中把最小 CoppeliaSim
pen-tip 播放层从“单条路径能播放”扩展为“仿真前/仿真播放评价层”：

- `play_workspace_path.py` 新增 `--display-stride N`，可降低 colored path segment 的可视化密度，但笔尖仍按完整 CSV 播放。
- `play_workspace_path.py` 新增 `--no-path-objects`，可只播放 pen-tip sphere，不创建路径对象，用于降低 GUI/GPU 负载。
- `play_workspace_path.py` 新增 `--auto-stop`，播放完成后尝试自动停止仿真。
- dry-run summary 将旧的 `max_step_mm` 拆分为 `max_step_3d_mm`、`max_xy_step_mm` 和 `max_z_step_mm`；旧字段仍作为 3D 距离兼容保留。
- 新增 `evaluate_playback_batch.py`，可批量扫描 `robot_workspace_trajectory_resampled.csv` 并生成 dry-run CSV/Markdown 报告，不连接 CoppeliaSim。

输出位置：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/coppeliasim_playback_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/coppeliasim_playback_report.md
```

三组“山”任务的播放 dry-run 重点指标：

| connection | point_count | max_step_3d_mm | max_xy_step_mm | max_z_step_mm | stroke_count | connector_count | pen_up_move_count | out_of_workspace_bounds |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| none | 258 | 8.0 | 4.749192 | 8.0 | 237 | 0 | 21 | False |
| weak | 246 | 43.046802 | 43.046802 | 0.0 | 237 | 9 | 0 | False |
| normal | 251 | 35.523756 | 35.523756 | 0.0 | 237 | 14 | 0 | False |

结论：CoppeliaSim 播放层现在能在不启动 GUI 的情况下批量检查播放负载与跳点风险。`none` 的最大 3D 跳变主要来自 8mm 抬笔高度，拆分后能清楚看到 XY 最大步长为 4.749mm；`weak/normal` 的大跳变主要发生在 XY 连接路径中，后续若接入真实机械臂控制器，需要继续结合段边界、速度连续性或 jerk 限制做更严格检查。当前仍只是 pen-tip/sphere playback，不包含机械臂 IK、真实动力学或控制器。

### 4.11 weak/normal 连笔执行层几何连续性修复

根因：旧版 `connection_strength` 被用于 connector 几何插值，weak/normal connector 只从上一笔终点走向下一笔起点的一部分，随后下一段 stroke 直接跳到真实起点，导致 playback dry-run 中出现 35mm / 43mm 的 XY 段间跳变。

修复：

- `trajectory_tools.insert_connections()` 的 connector 几何改为完整 `prev_end -> next_start`。
- `execution_tools.build_execution_trajectory()` 的 connector 几何同样改为完整 `prev_end -> next_start`。
- `connection_strength` 不再缩短连接路径长度，只参与 connector 的 pressure / width / speed 映射。
- `connection_preference=none` 仍保持 pen-up move，Z 轴 8mm 抬笔跳变保留为允许行为。

新输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
experiments/llm_style_trajectory/outputs/batch_20260613_154131/coppeliasim_playback_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/coppeliasim_playback_report.md
```

三组“山”修复后 playback dry-run：

| connection | point_count | max_step_3d_mm | max_xy_step_mm | max_z_step_mm | connector_count | pen_up_move_count |
|---|---:|---:|---:|---:|---:|---:|
| none | 258 | 8.0 | 4.749192 | 8.0 | 0 | 21 |
| weak | 275 | 2.487672 | 2.487672 | 0.0 | 38 | 0 |
| normal | 275 | 2.487672 | 2.487672 | 0.0 | 38 | 0 |

结论：weak/normal 不再出现 35mm / 43mm 的 XY 段间跳变，connector 经过重采样后满足约 2.5mm 的阈值；none 的 8mm Z 抬笔保留，XY 最大步长仍小于 5mm。

### 4.12 CoppeliaSim 播放完成反馈与结果留痕

本轮继续完善 `play_workspace_path.py` 的单次播放反馈：

- dry-run 和真实播放都会在终端输出明确 JSON summary。
- dry-run 的 `status` 为 `dry_run`，真实播放完成后为 `finished`。
- JSON summary 记录 `point_count`、`duration_estimate_s`、`speed_scale`、`display_stride`、`path_objects_enabled`、`auto_stop`、`simulation_stopped`、`max_step_3d_mm`、`max_xy_step_mm` 和 `max_z_step_mm`。
- 每次 dry-run 或真实播放都会在 CSV 所在目录写入：
  - `coppeliasim_playback_result.json`
  - `coppeliasim_playback_result.md`
- 可用 `--result-out-dir` 指定单次 playback result 的输出目录。
- 真实播放如果没有使用 `--auto-stop`，会提示 CoppeliaSim 仿真可能仍在运行；使用 `--auto-stop` 时，`simulation_stopped` 记录 `stopSimulation()` 是否调用成功。

本轮 dry-run 对象：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

输出结果：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.md
```

关键 dry-run 指标：

| status | point_count | display_stride | auto_stop | path_objects_enabled | simulation_stopped | max_step_3d_mm | max_xy_step_mm | max_z_step_mm |
|---|---:|---:|---|---|---|---:|---:|---:|
| dry_run | 275 | 5 | True | True | False | 2.487672 | 2.487672 | 0.0 |

结论：用户现在可以通过终端 JSON 和任务目录中的 result JSON/Markdown 明确确认播放流程是否结束、播放了多少点、是否启用了 auto-stop，以及当前轨迹最大跳点情况，不再只能依靠观察 CoppeliaSim GUI 判断播放是否完成。当前仍只是 pen-tip/sphere playback，不包含机械臂 IK。

### 4.13 CoppeliaSim 标准书写场景自动创建

本轮将 CoppeliaSim 播放层从“笔尖路径能播放”进一步固定为可复用的标准书写场景。`play_workspace_path.py` 新增场景参数：

```text
--scene-setup standard
--clear-previous-scene
--paper-size-mm 120
--pen-tip-radius-mm 1.5
--show-axes
--show-boundary
```

标准场景自动创建对象包括：

| 对象 | 说明 |
|---|---|
| paper plane | 默认 `120mm x 120mm`，位于 `Z=0` |
| boundary | 纸面四边边界框，可用 `--show-boundary` 开启 |
| X/Y/Z axes | X 红色、Y 绿色、Z 蓝色，可用 `--show-axes` 开启 |
| pen-tip sphere | 半径由 `--pen-tip-radius-mm` 控制，默认 `1.5mm` |
| path segments | stroke / connector / pen_up_move 分色显示 |

脚本创建对象统一使用 `llm_style_trajectory_*` 前缀，并通过 `--clear-previous-scene` 清理上一次脚本创建的对象，避免多次播放后场景堆叠。

单次 playback result 现在追加记录：

```text
scene_setup
paper_size_mm
pen_tip_radius_mm
axes_enabled
boundary_enabled
clear_previous_scene
coordinate_mapping
workspace_bounds
scene_warnings
recommended_playback
```

坐标映射固定为：

```text
X_m = X_mm / 1000
Y_m = Y_mm / 1000
Z_m = Z_mm / 1000
```

dry-run 不连接 CoppeliaSim，但会根据 `paper_size_mm` 检查 XY 是否在纸面半宽范围内，并检查 Z 是否在 `0..8mm` 范围内。如果纸面过小导致越界，result 中会给出 `out_of_workspace_bounds=true`、`recommended_playback=false` 和 warning。

真实播放验证对象：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

运行参数：

```text
--scene-setup standard
--clear-previous-scene
--show-axes
--show-boundary
--display-stride 5
--auto-stop
--speed-scale 1.0
```

结果文件：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.md
```

关键结果：

| status | point_count | simulation_stopped | paper_size_mm | axes | boundary | recommended_playback | max_xy_step_mm |
|---|---:|---|---:|---|---|---|---:|
| finished | 275 | true | 120.0 | true | true | true | 2.487672 |

结论：标准纸面、边界框、坐标轴、笔尖球和路径段已能由脚本自动创建，播放结束后明确输出 `status=finished` 和 `simulation_stopped=true`。该层用于固定论文/汇报中的三维仿真工作空间定义。当前仍是 standard pen-tip/sphere scene only，不包含机械臂模型、IK、真实动力学或控制器。

### 4.14 AUBO i5 / 通用机械臂末端目标位姿准备层

本轮新增 `robot_target_poses.py`，将重采样后的工作空间轨迹进一步转换为面向 AUBO i5 或通用机械臂 IK dry-run 的末端目标位姿序列：

```text
robot_workspace_trajectory_resampled.csv
-> robot_target_poses.csv
-> robot_target_pose_report.md
-> robot_target_pose_summary.json
```

默认输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

输出位置：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_pose_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_pose_summary.json
```

位姿字段包括：

```text
pose_id, t_s, X_m, Y_m, Z_m,
roll_deg, pitch_deg, yaw_deg,
qw, qx, qy, qz,
pen_down, segment_type, speed_m_s,
source_X_mm, source_Y_mm, source_Z_mm
```

坐标转换：

```text
X_m = X_mm / 1000 + origin_x_m
Y_m = Y_mm / 1000 + origin_y_m
Z_m = Z_mm / 1000 + origin_z_m
```

默认姿态先固定为书写笔竖直向下：

```text
roll_deg = 180
pitch_deg = 0
yaw_deg = 0
quaternion ~= (qw=0, qx=1, qy=0, qz=0)
```

关键检查结果：

| field | value |
|---|---:|
| point_count | 275 |
| duration_s | 13.05282 |
| path_length_m | 0.359531 |
| max_step_m | 0.002488 |
| max_speed_m_s | 0.04 |
| recommended_for_ik_dry_run | true |
| warnings | [] |

该层会检查 120mm 纸面范围、Z 是否在 `0..8mm`、是否存在 NaN/inf、时间是否单调、quaternion 是否归一化。当前输出只是 target pose representation，不做真实 IK、不连接 AUBO i5、不发送任何真实控制命令。AUBO i5 接口说明已整理到：

```text
experiments/llm_style_trajectory/docs/aubo_i5_target_pose_notes.md
```

### 4.15 AUBO i5 IK dry-run 命令适配层

本轮新增 `aubo_i5_command_adapter.py`，把 `robot_target_poses.csv` 转换为离线 AUBO i5 command plan，用于说明后续如果接入 AUBO i5 SDK 时大致应如何组织调用。该层严格保持 dry-run：不 import `libpyauboi5`，不连接真实 AUBO i5，不使用历史 IP，不求真实 IK，不调用 `move_joint` / `move_line`，不发送任何控制命令。

默认输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

输出位置：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_safety_check.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan.md
```

命令计划类型：

| command_type | 含义 |
|---|---|
| `move_joint_approach` | 到第一个点上方的安全接近位姿，仅记录 future `inverse_kin + move_joint` hint |
| `move_line` | 沿目标位姿序列跟随；若为抬笔段则保留 `pen_down=0` |
| `move_line_retract` | 结束后抬高到安全高度，仅作为 future `move_line` hint |

关键 safety check：

| field | value |
|---|---:|
| point_count | 275 |
| command_count | 277 |
| max_step_m | 0.002488 |
| max_speed_m_s | 0.04 |
| max_accel_m_s2_estimate | 0.0 |
| quaternion_normalized | true |
| time_monotonic | true |
| has_nan_or_inf | false |
| recommended_for_sdk_dry_run | true |
| warnings | [] |

adapter 说明文档：

```text
experiments/llm_style_trajectory/docs/aubo_i5_command_adapter_notes.md
```

结论：系统已从 target pose representation 推进到 AUBO i5 SDK dry-run command plan。当前仍只是离线接口准备层，不包含真实 IK、真实可达性判断、碰撞检测、SDK 连接或机械臂控制。实机前必须重新确认机器人 IP、急停、工具 TCP、夹具、纸面坐标系、速度/加速度限制、可达性和现场安全。

### 4.16 AUBO i5 IK feasibility dry-run 可达性前检查层

本轮新增 `aubo_i5_ik_feasibility.py`，在 `robot_target_poses.csv` 和 AUBO i5 command plan 之后，增加进入真实 IK 前的离线 feasibility gate。该层仍然不求真实 IK、不 import `libpyauboi5`、不连接真实 AUBO i5、不使用历史 IP、不发送控制命令。

默认输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

输出位置：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_points.csv
```

检查内容：

| check | 说明 |
|---|---|
| required fields | 是否包含未来 IK 所需目标位姿字段 |
| XY/Z bounds | 是否仍在 120mm 纸面和 `0..8mm` Z 范围内 |
| max step / speed | 是否满足进入 IK 检查前的保守点距与速度阈值 |
| time monotonic | 时间是否单调 |
| quaternion normalized | 姿态四元数是否归一化 |
| NaN / inf | 是否存在非法数值 |
| conservative envelope | 相对 origin 的半径是否在可配置粗略 envelope 内 |

关键结果：

| field | value |
|---|---:|
| point_count | 275 |
| xy_range_m | x `[-0.049057, 0.048721]`, y `[-0.049392, 0.049392]` |
| z_range_m | `[0.0, 0.0]` |
| radius_range_m | `[0.000756, 0.064444]` |
| max_step_m | 0.002488 |
| max_speed_m_s | 0.04 |
| time_monotonic | true |
| quaternion_normalized | true |
| has_nan_or_inf | false |
| required_fields_present | true |
| within_conservative_envelope | true |
| recommended_for_real_ik_check | true |
| warnings | [] |

说明文档和论文固定索引：

```text
experiments/llm_style_trajectory/docs/aubo_i5_ik_feasibility_notes.md
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_index.md
```

结论：系统已具备进入真实 IK 检查前的离线数据质量与几何前检查层。该层只回答“是否具备进入真实 IK dry-run 的基本条件”，不等价于 AUBO i5 真实可达、无碰撞、无奇异位形或满足关节限位。

## 5. 推荐论文图表

固定整理目录：

```text
experiments/llm_style_trajectory/outputs/paper_figures/
experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md
```

| 图表 | 内容 | 推荐来源 |
|---|---|---|
| 系统流程图 | 自然语言到 CSV 与评价闭环 | 本文档第 1 节流程 |
| 连笔 ablation 图 | 山：none / weak / normal | `outputs/paper_figures/fig_modifier_connection_shan.png` |
| 执行层连笔图 | 山：none / weak / normal 的宽度、压力和连接可视化 | `outputs/paper_figures/fig_execution_ablation_shan.png` |
| 执行层连笔表 | connector length、pen-up length、pressure、width | `outputs/paper_figures/execution_ablation_table.md` |
| 工作空间映射图 | 山：纸面边界内的 stroke / connector / pen-up move | `outputs/paper_figures/fig_workspace_ablation_shan.png` |
| 工作空间检查表 | XY/Z 越界、max step、segment counts | `outputs/batch_20260613_154131/workspace_mapping_summary.csv` |
| 工作空间重采样图 | 山：none / weak / normal 重采样后路径和最大步长 | `outputs/paper_figures/fig_workspace_resampling_shan.png` |
| 工作空间重采样表 | 原始/重采样点数、max step、速度和估计时长 | `outputs/batch_20260613_154131/workspace_resampling_summary.csv` |
| CoppeliaSim 播放检查表 | 修复后 3D / XY / Z 最大步长与段类型统计 | `outputs/batch_20260613_154131/coppeliasim_playback_summary.csv` |
| CoppeliaSim 标准场景图 | 120mm 纸面、坐标轴、边界和 weak 行楷山路径 | `outputs/paper_figures/fig_coppeliasim_standard_scene_shan.png` |
| CoppeliaSim 标准场景结果 | 真实播放 finished / stopped / bounds 检查 | `outputs/paper_figures/coppeliasim_standard_scene_result.md` |
| CoppeliaSim 最小播放记录 | 重采样 CSV 到三维仿真笔尖路径播放 | `experiments/llm_style_trajectory/coppeliasim/README.md` |
| AUBO i5 command adapter 索引 | target poses 到离线 SDK command plan 与 safety check | `outputs/paper_figures/aubo_i5_command_adapter_index.md` |
| AUBO i5 command plan | 接近、线性跟随、撤离三类 dry-run 命令计划 | `outputs/paper_figures/aubo_i5_command_plan.md` |
| AUBO i5 IK feasibility 索引 | 进入真实 IK 前的数据质量与几何范围前检查 | `outputs/paper_figures/aubo_i5_ik_feasibility_index.md` |
| 三字体总览图 | 山/中/永/福/明 x kaishu/xingkai/lishu | `outputs/paper_figures/fig_style_profile_compare_grid.png` |
| 三字体指标表 | trajectory/execution/workspace 三层综合指标 | `outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_profile_compare_summary.csv` |
| 宽扁 ablation 图 | 中：normal / flatter / wider | `outputs/paper_figures/fig_modifier_shape_zhong.png` |
| 圆滑 ablation 图 | 永：medium / high / low | `outputs/paper_figures/fig_modifier_smoothness_yong.png` |
| DeepSeek planner 鲁棒性表 | JSON、非法请求拒绝、危险输出 | `outputs/planner_robustness_20260608_163557/` |
| modifier 总表 | 三类自然语言控制指标汇总 | 本文档第 4 节 |

## 6. 大论文结构中的位置

建议放置方式：

- 第 3 章：系统总体设计  
  写 LLM planner、request validation、style modifiers、style profile、trajectory generator、render/eval 的整体架构。
- 第 4 章：结构化字形知识与风格参数构建  
  写 Make Me a Hanzi、字体统计 style profile、哪些参数来自统计、哪些是过程先验。
- 第 5 章：自然语言约束驱动的多风格轨迹生成  
  写 planner schema、style_modifiers、白名单映射、CSV 生成。
- 第 6 章：实验与分析  
  写 DeepSeek planner 鲁棒性、连笔/宽扁/圆滑 ablation、虚拟书写渲染评价。

## 7. 当前可写创新点

1. 构建了 LLM planner 与本地确定性轨迹工具解耦的书法机器人轨迹生成框架。
2. 设计了 request boundary validation，避免 LLM 直接生成轨迹、误放行 unsupported style 或多字符任务。
3. 提出 `style_modifiers` 作为自然语言意图与轨迹参数之间的可解释中间层。
4. 使用白名单映射函数将离散语义转化为可控的 `connection`、`shape`、`smoothness` 参数变化。
5. 通过连笔、宽扁、圆滑三类 ablation 验证自然语言约束可以产生可量化轨迹差异。
6. 新增二维 execution layer，将中心线轨迹扩展为含压力、宽度、速度、落笔/抬笔和连接段状态的虚拟执行表示。
7. 新增机器人纸面工作空间映射与仿真前检查层，为后续机械臂末端轨迹仿真提供坐标和安全检查基础。
8. 通过五个汉字的三字体基础风格对比，验证基础 style profile 本身能够产生可量化和可视化差异。
9. 新增工作空间轨迹重采样与分段速度规划，降低仿真前的末端跳点风险。
10. 完成 CoppeliaSim 最小笔尖路径播放验证，证明工作空间 CSV 可以进入三维仿真环境进行可视化检查。
11. 通过 CoppeliaSim playback dry-run 发现并修复 weak/normal connector 段间 XY 跳变，明确 `connection_strength` 只影响压力、宽度和速度，不截断几何连接。
12. 整理 CoppeliaSim 标准书写场景图和真实播放 result，为论文/汇报提供固定仿真工作空间素材。
13. 结合师兄视觉抓取实验资料，确认后续真实机械臂平台优先按 AUBO i5 / 遨博 i5 协作机械臂规划。
14. 将末端目标位姿序列转换为 AUBO i5 SDK dry-run command plan，并整理 safety check 与论文固定索引，为后续 IK/实机接口验证提供离线准备层。
15. 新增 AUBO i5 IK feasibility dry-run 前检查层，验证目标位姿字段、纸面范围、点距、速度、时间单调性、四元数归一化和保守半径 envelope，为进入真实 IK 前提供可复查 gate。

## 8. 下一步建议

短期不建议继续增加 modifier 种类。更优先的是：

1. 将三类 ablation 结果整理成论文图表。
2. 用 DeepSeek API planner 跑一组同样的 modifier tasks，验证 API 与 mock 输出是否一致。
3. 后续图表和论文正文优先引用 `batch_20260613_154131` 及 `outputs/paper_figures/` 中的修复后固定图。
4. 给 `mean_turning`、`total_turning_angle`、`max_turning_angle` 写清楚定义，避免评价指标解释含糊。
5. 将 AUBO i5 command adapter 与 IK feasibility dry-run 作为论文中的“机器人接口准备层”表述清楚，强调 dry-run 边界。
6. 在 CoppeliaSim 中加入简单机器人或末端执行器模型，先做无真实 IK 的坐标系/纸面位置校准。
7. 进一步补充速度连续性、加速度/jerk 约束。
8. 若后续进入真实 IK，只先做离线 SDK/IK dry-run；条件允许时再选择 1 到 2 个字做低速空跑或实写验证。

## 2026-06-16 CoppeliaSim simple pen/tool coordinate calibration layer

本轮在 `experiments/llm_style_trajectory/coppeliasim/play_workspace_path.py`
中扩展了标准 CoppeliaSim pen-tip 场景，新增 `--tool-model simple-pen`、
`--show-tool-frame`、`--tool-length-mm`、`--tool-radius-mm`、
`--tcp-offset-mm` 和 `--base-frame-origin-mm`。默认 `--tool-model none`
保持旧的 pen-tip/sphere playback 行为；显式启用 `simple-pen` 时，只创建
竖直笔杆和 TCP frame 可视化对象，不接入 AUBO i5 机械臂模型、不做 IK、
不做动力学或碰撞检测，也不发送任何控制命令。

固定 dry-run 样例：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

新增输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_tool_model_result.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_tool_model_result.md
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_index.md
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_result.json
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_result.md
```

关键结果：

| field | value |
|---|---:|
| status | dry_run |
| point_count | 275 |
| tool_model | simple-pen |
| show_tool_frame | true |
| tool_length_mm | 120.0 |
| tool_radius_mm | 4.0 |
| tcp_offset_mm | 0.0 |
| max_xy_step_mm | 2.487672 |
| max_z_step_mm | 0.0 |
| recommended_playback | true |
| recommended_for_coordinate_calibration | true |
| warnings | [] |

坐标关系记录为：`paper_frame` 位于 120mm 纸面中心且 Z=0；
`workspace_frame` 当前与 `paper_frame` 重合，并保留
`base_frame_origin_mm` 作为后续标定元数据；`tool_tcp_frame` 将 CSV 点视为
笔尖 TCP 目标，`simple-pen` 笔杆只沿 +Z 做方向可视化。该层用于进入真实
IK/实机前的坐标系和末端工具方向 sanity check，不是真实 AUBO i5 IK。

## 2026-06-16 Motion continuity dry-run 检查层

新增 `experiments/llm_style_trajectory/src/motion_continuity_check.py`，
支持读取 `robot_target_poses.csv` 或 `robot_workspace_trajectory_resampled.csv`，
离线检查时间连续性、相邻点 3D 距离、速度、速度跳变、加速度、jerk、
四元数归一化和分段统计。该层仍然只做 dry-run，不是真实机器人动力学、
不做 IK、不检查关节空间速度/加速度/力矩，也不连接 AUBO i5 或发送命令。

新增说明与测试：

```text
experiments/llm_style_trajectory/docs/motion_continuity_check_notes.md
experiments/llm_style_trajectory/tests/test_motion_continuity_check.py
```

默认样例输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

默认样例输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_points.csv
experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_check_index.md
```

关键结果：

| field | value |
|---|---:|
| point_count | 275 |
| duration_s | 13.0528205 |
| path_length_m | 0.359530547 |
| dt_nonpositive_count | 4 |
| max_speed_m_s | 0.04 |
| max_speed_jump_m_s | 0.025 |
| max_accel_m_s2 | 0.533536284 |
| max_jerk_m_s3 | 11.386446091 |
| jerk_peak_count | 6 |
| quaternion_normalized | true |
| has_nan_or_inf | false |
| recommended_for_coppeliasim_playback | false |
| recommended_for_ik_dry_run | false |

结论：默认 target pose 序列通过了字段、几何范围、速度和四元数检查，但
更严格的 motion continuity gate 检出 4 个零时长重复边界点，并在保守阈值下
出现 acceleration / jerk 超限。因此进入真实 IK dry-run 或低速空跑准备前，
应先做 target pose 去重、retiming 和速度曲线平滑。

## 2026-06-17 Target pose retiming / smoothing 后处理层

新增 `experiments/llm_style_trajectory/src/target_pose_retiming.py`，用于把
`robot_target_poses.csv` 离线后处理为
`robot_target_poses_smoothed.csv`。该层只删除相邻静止重复点并重写时间戳，
不改变字形几何路径；后处理后复用 `motion_continuity_check.py` 生成
after-retiming 连续性报告。

新增说明与测试：

```text
experiments/llm_style_trajectory/docs/target_pose_retiming_notes.md
experiments/llm_style_trajectory/tests/test_target_pose_retiming.py
```

默认样例输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

默认样例输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses_smoothed.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/target_pose_retiming_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/target_pose_retiming_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_after_retiming_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_after_retiming_report.md
experiments/llm_style_trajectory/outputs/paper_figures/target_pose_retiming_index.md
```

before / after 关键指标：

| field | before | after |
|---|---:|---:|
| point_count | 275 | 271 |
| removed_duplicate_count | 0 | 4 |
| duration_s | 13.0528205 | 22.039876274 |
| dt_nonpositive_count | 4 | 0 |
| max_speed_m_s | 0.04 | 0.01792 |
| max_accel_m_s2 | 0.533536284 | 0.274132141 |
| max_jerk_m_s3 | 11.386446091 | 4.193553547 |
| recommended_for_coppeliasim_playback | false | true |
| recommended_for_ik_dry_run | false | true |

几何保持：

```text
geometry_path_length_before_m = 0.359530546527
geometry_path_length_after_m  = 0.359530546527
path_length_delta_m           = 0.0
```

结论：retiming 后默认 weak 行楷山样例已通过保守的 motion-continuity dry-run
gate，可继续用于 CoppeliaSim playback、真实 IK 前离线检查或低速空跑准备。
该层仍不是 AUBO i5 真实动力学优化，不做 IK，不检查关节空间速度/加速度/力矩，
不连接 SDK 或实机，也不发送机器人命令。

## 2026-06-17 Smoothed target poses 接回后续 dry-run 默认流程

将 AUBO i5 command adapter 和 IK feasibility dry-run 的默认样例输入切换为
`robot_target_poses_smoothed.csv`：当默认任务目录中存在 smoothed 文件时，CLI
默认使用 smoothed；用户显式传入 `--csv robot_target_poses.csv` 时仍保留原始
before-retiming 对照行为，不会被自动替换。

新增共享 helper 与测试：

```text
experiments/llm_style_trajectory/src/target_pose_defaults.py
experiments/llm_style_trajectory/tests/test_smoothed_target_pose_default.py
```

smoothed command adapter 输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan_smoothed.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_safety_check_smoothed.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan_smoothed.md
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_adapter_smoothed_index.md
```

smoothed IK feasibility 输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_smoothed_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_smoothed_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_smoothed_points.csv
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_smoothed_index.md
```

关键结果：

| field | before-retiming | after-retiming smoothed |
|---|---:|---:|
| command point_count | 275 | 271 |
| command_count | 277 | 273 |
| command max_speed_m_s | 0.04 | 0.01792 |
| recommended_for_sdk_dry_run | true | true |
| IK feasibility point_count | 275 | 271 |
| IK max_speed_m_s | 0.04 | 0.01792 |
| recommended_for_real_ik_check | true | true |
| warnings | [] | [] |

结论：流程已经从“motion continuity 发现原始 target pose 时间/jerk 问题”，推进到
“retiming 修复后重新生成机器人接口 dry-run 结果”。后续机器人接口准备的推荐输入为
`robot_target_poses_smoothed.csv`；原始 `robot_target_poses.csv` 保留为 before-retiming
对照。当前仍不是真实 IK，不连接 AUBO i5，不调用 SDK，不发送机器人运动命令。

## 2026-06-17 多字样本风格区分度与参数诊断实验

本轮从机器人接口准备层回到方法核心，新增多字样本 style profile 诊断实验，用于检查
`kaishu` / `xingkai` / `lishu` 三种基础风格在更多汉字结构上的稳定性和可区分度。实验仍只使用
mock planner、本地 style profile、execution layer、workspace mapping 和 workspace resampling；
不调用 API、不连接 CoppeliaSim、不连接 AUBO i5、不做真实 IK、不调用 SDK、不发送机器人命令。

新增配置、脚本与测试：

```text
experiments/llm_style_trajectory/configs/style_diagnostic_chars.json
experiments/llm_style_trajectory/src/style_diagnostics.py
experiments/llm_style_trajectory/tests/test_style_diagnostics.py
```

诊断样本覆盖 18 个常用字：

```text
山、中、永、大、小、人、明、林、好、和、花、思、音、景、国、风、福、德
```

每个字生成 `kaishu` / `xingkai` / `lishu` 三种风格，共 54 个 char x style 样本。每个成功样本生成
`trajectory.csv`、`execution_trajectory.csv`、`robot_workspace_trajectory.csv`、
`robot_workspace_trajectory_resampled.csv` 以及预览/summary，并汇总到诊断表与图中。

输出目录：

```text
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_summary.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_style_means.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_char_means.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_failures.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_report.md
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_grid.png
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_metric_bars.png
experiments/llm_style_trajectory/outputs/paper_figures/style_diagnostics_index.md
```

样本统计：

| total_samples | success_count | failure_count | missing_char_count |
|---:|---:|---:|---:|
| 54 | 54 | 0 | 0 |

三风格平均指标：

| style | sample_count | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_pen_up_move_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.018672 | 786.158 | 0.000 | 0.000 | 524.004 | 9.000 | 614.139 | 0 |
| lishu | 18 | 1.465173 | 783.776 | 0.000 | 0.000 | 522.929 | 10.000 | 612.518 | 0 |
| xingkai | 18 | 1.070791 | 1314.104 | 6.056 | 525.944 | 0.000 | 7.489 | 615.987 | 0 |

诊断结论：

- `lishu` 的平均 `aspect_ratio=1.465173`，明显高于 `kaishu=1.018672` 和
  `xingkai=1.070791`，说明宽扁 profile 在 18 字样本中稳定可见。
- `xingkai` 的平均 `connection_count=6.056`、`connector_draw_length=525.944`，
  明显高于 `kaishu` / `lishu` 的 0，说明行楷默认弱连接逻辑在多字样本中稳定生效。
- `kaishu` 与 `lishu` 都保持 `connection_count=0`，说明基础 profile 的“无跨笔连接”约束稳定。
- 三种风格 `out_of_bounds_count=0`，说明当前 profile 在 120mm 纸面映射和重采样层没有越界。
- 参数仍偏粗：宽扁和连接差异最清晰；笔画级宽度、部件级比例、转折圆滑度仍主要依赖全局参数，
  下一步应优先从字体/图像统计中重新估计这些细粒度参数。

边界说明：本轮不是最终真实书法风格学习结果，而是参数化 style profile + 部分字体统计 + prior 的稳定性诊断。
LLM/API planner 仍不直接输出 CSV、轨迹点或机器人命令，所有轨迹仍由本地确定性工具生成。

## 2026-06-17 风格诊断 v2：异常样本定位与人工看图校验包

基于上一轮 54 个多字样本 style diagnostic 结果，新增人工看图校验包生成层，用于把“数值上最值得关注”的样本收敛为少量可直接检查的图片清单。该层仍只做诊断和整理，不调参、不调用 API、不连接 CoppeliaSim、不连接 AUBO i5、不做真实 IK、不调用 SDK、不发送机器人命令。

新增脚本与测试：

```text
experiments/llm_style_trajectory/src/style_visual_audit.py
experiments/llm_style_trajectory/tests/test_style_visual_audit.py
```

输入诊断目录：

```text
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/
```

输出目录：

```text
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/
```

固定资料：

```text
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_candidates.csv
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_report.md
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_checklist.md
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_image_manifest.csv
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/selected_images/
experiments/llm_style_trajectory/outputs/paper_figures/style_visual_audit_index.md
```

候选样本统计：

| candidate_count | high_aspect_spread | low_aspect_spread | long_xingkai_connector | high_lishu_aspect | representative |
|---:|---:|---:|---:|---:|---:|
| 18 | 5 | 3 | 3 | 3 | 4 |

最值得先看的一组样本：

- `人 / kaishu`, `人 / lishu`, `人 / xingkai`：三风格 aspect_ratio 差异最强，适合先看“是否肉眼可分”。
- `国 / xingkai`, `德 / xingkai`, `福 / xingkai`：行楷连接段最长，适合先看 connector 是否过长或不自然。
- `中 / kaishu`, `中 / lishu`, `中 / xingkai`：三风格 aspect_ratio 差异弱，适合看风格是否肉眼难分。
- `和 / kaishu`, `和 / lishu`, `和 / xingkai`：代表样本，用于和异常样本做对照。
- `思 / kaishu`：另一个代表样本，用于确认楷书是否保守但不机械。

边界说明：

- 本轮没有替用户完成视觉判断，不能只看指标得出最终视觉效果结论。
- 后续是否调参，应先看 `selected_images/` 或 `visual_audit_image_manifest.csv`，再根据人工标注决定。
## 2026-06-18 Connector / brush 可视化诊断图包

基于 `style_visual_audit_20260617_224321` 的人工看图候选样本，新增 connector / brush 诊断图包生成层，用于把旧 selected_images 中不易区分的灰线、连笔段、抬笔移动、笔宽和压力拆开显示。本轮只做视觉诊断和论文/汇报图整理，不调 style profile、brush profile、modifier 或 planner 参数。

新增文件：

```text
experiments/llm_style_trajectory/src/connector_brush_visual_diagnostics.py
experiments/llm_style_trajectory/tests/test_connector_brush_visual_diagnostics.py
```

输出目录：

```text
experiments/llm_style_trajectory/outputs/connector_brush_visual_diagnostics_20260618_093510/
experiments/llm_style_trajectory/outputs/paper_figures/connector_brush_visual_diagnostics_index.md
```

关键输出：

```text
connector_brush_diagnostic_report.md
connector_brush_diagnostic_cases.csv
connector_brush_image_manifest.csv
figures/segment_legend.png
figures/connector_overlay_u56fd_xingkai.png
figures/connector_overlay_u5fb7_xingkai.png
figures/connector_overlay_u798f_xingkai.png
figures/brush_width_diagnostic_u4eba_xingkai.png
figures/style_side_by_side_u4eba.png
figures/style_side_by_side_u4e2d.png
figures/style_side_by_side_u548c.png
figures/lishu_deformation_u4eba.png
figures/lishu_deformation_u597d.png
figures/lishu_deformation_u98ce.png
```

样本统计：

| case_type | count |
|---|---:|
| long_xingkai_connector | 3 |
| brush_width_diagnostic | 1 |
| style_side_by_side | 9 |
| lishu_deformation | 6 |

诊断重点：
- 灰线问题：旧 selected_images 中的灰/浅线可能混合了渲染透明度、connector 过渡和 pen-up/transition 视觉线索；新图中灰色虚线只表示 `pen_up_move`，红/橙色表示 connector。
- 宽度问题：固定墨迹预览会弱化 `width/pressure` 的差异，因此新增 brush width diagnostic 单独展示 stroke 与 connector 的宽度/压力均值和执行层 overlay。
- 隶书问题：当前 lishu 的可见差异主要仍是全局水平拉宽 / 垂直压缩，stroke-level 隶书笔画特征不足，需要用户人工看图判断是否可接受。
- 行楷问题：`国/德/福` 的 xingkai connector 是优先看图样本，用于判断 connector 是否过长、过直或穿越部件。

边界：该图包仍是人工校验准备层，不能只看指标得出最终风格效果结论；下一轮是否调参应等待用户看图反馈。
## 2026-06-18 宽度 / 压力渐变可视化诊断

基于 `connector_brush_visual_diagnostics_20260618_093510` 的人工看图候选样本，新增 `execution_trajectory.csv` 的 width / pressure 渐变渲染层。本轮只改可视化诊断，不调 style profile、brush profile、modifier 参数，不改 planner，不扩大样本，不修改 execution CSV，不接入 API、CoppeliaSim 或机器人接口。

新增文件：

```text
experiments/llm_style_trajectory/src/width_pressure_visualization.py
experiments/llm_style_trajectory/tests/test_width_pressure_visualization.py
```

输出目录：

```text
experiments/llm_style_trajectory/outputs/width_pressure_visualization_20260618_101349/
experiments/llm_style_trajectory/outputs/paper_figures/width_pressure_visualization_index.md
```

关键输出：

```text
width_pressure_visualization_report.md
width_pressure_visualization_manifest.csv
width_pressure_value_ranges.json
figures/
```

图像组合：

- `width_global_*`：全局 width 范围归一化，便于跨字/跨风格比较。
- `pressure_global_*`：全局 pressure 范围归一化，便于观察 connector 低压。
- `width_per_image_*`：单图内部 width 归一化，便于观察单样本内部细微变化。
- `pressure_per_image_*`：单图内部 pressure 归一化。

关键范围：

| field | min | max |
|---|---:|---:|
| global_width | 4.245 | 10.0 |
| global_pressure | 0.338 | 1.0 |
| stroke width | 9.0 | 10.0 |
| connector width | 4.245 | 4.245 |
| stroke pressure | 1.0 | 1.0 |
| connector pressure | 0.338 | 0.338 |

样本统计：

| field | value |
|---|---:|
| sample_count | 16 |
| generated_figure_count | 64 |
| connector 明显更细样本 | 6 |
| connector 明显更低压样本 | 6 |
| stroke width nearly constant 样本 | 16 |

诊断结论：
- 当前数据层面，`xingkai` connector 的 width / pressure 明显低于主体 stroke，因此“连笔更细、更低压”确实写在 execution 数据中。
- 所有本轮样本的主体 stroke width 基本恒定，说明旧图中看不出主体笔画内部粗细变化不是可视化失败，而是当前 execution 数据本身缺少 stroke 内部宽度变化。
- 这些图只用于人工诊断，不能当作最终书法渲染效果；是否调整 connector 规则或增加 stroke 内部宽度变化，应等待用户看图反馈。

## 2026-06-18 Execution refinement：connector 收紧 + stroke taper + 可读色阶

基于上一轮 connector / brush 视觉诊断和 width / pressure 渐变图，新增一轮执行层 refinement 实验。本轮允许修改 execution / connector 生成规则，但仍只在 `experiments/llm_style_trajectory` 内工作，不调用 API，不连接 CoppeliaSim/AUBO i5，不做 IK/SDK/机器人控制。

新增文件：

```text
experiments/llm_style_trajectory/configs/execution_refinement_profiles.json
experiments/llm_style_trajectory/src/execution_refinement.py
experiments/llm_style_trajectory/src/execution_refinement_experiment.py
experiments/llm_style_trajectory/tests/test_execution_refinement.py
experiments/llm_style_trajectory/tests/test_execution_refinement_experiment.py
```

修改文件：

```text
experiments/llm_style_trajectory/src/execution_tools.py
experiments/llm_style_trajectory/src/width_pressure_visualization.py
experiments/llm_style_trajectory/tests/test_width_pressure_visualization.py
```

输出目录：

```text
experiments/llm_style_trajectory/outputs/execution_refinement_20260618_104837/
experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_index.md
```

关键输出：

```text
execution_refinement_summary.csv
execution_refinement_report.md
execution_refinement_cases.csv
figures/
```

核心变化：

- `baseline` connector rule 保持旧行为：允许连接时相邻笔画全连，用于 before 对照。
- `conservative` connector rule 使用 distance gate、angle gate 和 `connect_every_n=2` 收紧行楷 connector，不再默认所有相邻笔画都连。
- `simple_taper` 对 stroke 段生成起笔 / 中段 / 收笔 width 和 pressure 曲线；connector 与 pen-up move 不套用 taper。
- 可视化浅色端改为可见浅蓝 / 棕灰，背景为浅暖灰，`min_alpha=0.55`，`min_visible_linewidth=1.2`。本轮颜色只为可读性，不代表真实墨色。

before/after 指标：

| char | style | connection_count | connector_draw_length | stroke_width_range | stroke_pressure_range |
|---|---|---:|---:|---:|---:|
| 国 | xingkai | 7 -> 1 | 810.946 -> 106.146 | 0.0 -> 3.23 | 0.0 -> 0.18 |
| 德 | xingkai | 14 -> 1 | 878.276 -> 45.035 | 0.0 -> 3.23 | 0.0 -> 0.18 |
| 福 | xingkai | 12 -> 1 | 886.416 -> 96.856 | 0.0 -> 3.229996 | 0.0 -> 0.18 |
| 人 | xingkai | 1 -> 0 | 131.331 -> 0.0 | 0.0 -> 3.226268 | 0.0 -> 0.179843 |
| 中 | xingkai | 3 -> 0 | 310.785 -> 0.0 | 0.0 -> 3.229764 | 0.0 -> 0.179987 |
| 和 | xingkai | 7 -> 2 | 531.324 -> 101.215 | 0.0 -> 3.229996 | 0.0 -> 0.18 |
| 人 | kaishu | 0 -> 0 | 0.0 -> 0.0 | 0.0 -> 3.054751 | 0.0 -> 0.179767 |
| 人 | lishu | 0 -> 0 | 0.0 -> 0.0 | 0.0 -> 3.3998 | 0.0 -> 0.179989 |

可读色阶：

| field | value |
|---|---:|
| background_color | `#f7f7f2` |
| stroke_light_color | `#6baed6` |
| connector_light_color | `#b07d62` |
| stroke_light_distance_from_white | 0.680886 |
| connector_light_distance_from_white | 0.857291 |
| min_alpha | 0.55 |
| min_visible_linewidth | 1.2 |

诊断结论：

- conservative gate 已显著减少行楷 connector，尤其 `国/德/福/和` 不再“所有相邻笔画必连”。
- simple taper 已让 stroke 内部 width/pressure 出现可量化变化。
- `kaishu/lishu` 仍保持无跨笔 connector，但也获得 stroke taper 诊断图，用于确认宽度曲线是否可见。
- `skip_if_crosses_bbox_center` 已在代码中实现，但本轮配置为 false；在当前样本上启用会让 connector 几乎清零，不利于 before/after 人工比较。
- 本轮不是最终行楷规则，不是真实笔刷模型，也不解决 lishu 真实风格来源问题；需要用户人工看图后再决定是否继续调 connector 或设计更细的笔画级宽度模型。

## 2026-06-18 Execution refinement 人工反馈归档与 candidate_default_v1

在用户人工看图后，对 `execution_refinement_20260618_104837` 做小收口：

```text
experiments/llm_style_trajectory/docs/execution_refinement_decision.md
experiments/llm_style_trajectory/configs/execution_refinement_profiles.json
```

人工反馈摘要：

- 行楷连笔确实更自然，但目前基本只有一两笔连笔，略显偏少；暂时接受。
- stroke 粗细变化可见，效果不错。
- 隶书两张图没有观察到连笔。
- `人/lishu connector_draw_length: 0.0 -> 3.3998` 是可疑读数，需要核查。

核查结论：

- `人/lishu` refined execution 中 `segment_type=connector` 行数为 0。
- `人/lishu` refined execution 中 `is_connector=1` 行数为 0。
- summary 中 `after_connector_draw_length=0.0`。
- `3.3998` 对应 `after_stroke_width_range`，不是 connector_draw_length。

决策：

- 当前 `conservative connector + simple_taper` 标记为 `candidate_default_v1`。
- `candidate_default_v1` 只是下一轮候选默认，不替换全局默认。
- 下一步如果继续推进 execution refinement，应先扩大样本人工看图，或设计介于 conservative 与 all-adjacent 之间的 `balanced` connector 档位。

## 2026-06-18 candidate_default_v1 多样本验证

在不继续调参、不扩大到机器人接口的前提下，对 `candidate_default_v1`
做了 18 个样本的 before/after 验证：

```text
experiments/llm_style_trajectory/outputs/execution_refinement_validation_20260618_120238/
experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_validation_index.md
```

验证配置仍为：

- connector_rule: `conservative`
- stroke_width_profile: `simple_taper`
- candidate status: `accepted_for_next_round_candidate`

核心结果：

| metric | value |
|---|---:|
| selected_count | 18 |
| success_count | 18 |
| failure_count | 0 |
| xingkai_samples | 8 |
| xingkai connection_count sum | 58 -> 5 |
| xingkai connector_draw_length sum | 4938.116 -> 349.252 |
| xingkai samples retaining connectors | 4 / 8 |
| kaishu/lishu connector violations | 0 |
| mean after stroke_width_range | 3.2295 |

代表样本：

| char | style | connection_count | connector_draw_length | stroke_width_range |
|---|---|---:|---:|---:|
| 国 | xingkai | 7 -> 1 | 810.946 -> 106.146 | 0.0 -> 3.23 |
| 德 | xingkai | 14 -> 1 | 878.276 -> 45.035 | 0.0 -> 3.23 |
| 福 | xingkai | 12 -> 1 | 886.416 -> 96.856 | 0.0 -> 3.229996 |
| 和 | xingkai | 7 -> 2 | 531.324 -> 101.215 | 0.0 -> 3.229996 |
| 中 | xingkai | 3 -> 0 | 310.785 -> 0.0 | 0.0 -> 3.229764 |
| 人 | lishu | 0 -> 0 | 0.0 -> 0.0 | 0.0 -> 3.3998 |

诊断结论：

- 行楷 connector 从“过多”明显收敛到少量连接，但 `中/人/明/林` 等样本 after connector 清零，仍需人工看图判断是否偏保守。
- 楷书 / 隶书样本没有 connector violation，继续满足“非行楷不误连”的边界。
- simple_taper 在所有成功样本中都打开了 stroke width range，可作为人工看图时的笔画粗细变化依据。
- 该轮仍只证明 `candidate_default_v1` 是可进入下一轮人工审查的候选，不代表已经替换全局默认。

## 2026-06-18 balanced connector + 行楷局部风格增强实验

基于用户反馈“candidate_default_v1 行楷仍偏保守、像楷书加少量连笔”，新增一个只用于实验的
`balanced` connector 档位和轻量行楷局部增强。本轮不进入仿真书写、不接机器人接口、不调用 API。

```text
experiments/llm_style_trajectory/outputs/xingkai_balanced_experiment_20260618_141424/
experiments/llm_style_trajectory/outputs/paper_figures/xingkai_balanced_experiment_index.md
```

新增配置：

- `connector_rules.balanced`：distance / angle gate + 短 connector 优先，介于 `baseline/all_adjacent` 与 `conservative` 之间。
- `connector_shapes.slight_curve`：对保留的行楷 connector 使用轻微二次贝塞尔曲线。
- `stroke_width_profiles.xingkai_expressive_taper`：只在行楷 balanced 实验中增强起收笔 taper。

关键指标：

| metric | baseline | conservative | balanced |
|---|---:|---:|---:|
| xingkai connection_count sum | 58 | 5 | 10 |
| xingkai connector_draw_length sum | 4938.116 | 349.252 | 586.339 |
| kaishu/lishu connector violations | 0 | 0 | 0 |

行楷样本：

| char | baseline conn | conservative conn | balanced conn | balanced curved |
|---|---:|---:|---:|---|
| 国 | 7 | 1 | 2 | true |
| 德 | 14 | 1 | 3 | true |
| 福 | 12 | 1 | 1 | true |
| 和 | 7 | 2 | 2 | true |
| 中 | 3 | 0 | 0 | false |
| 人 | 1 | 0 | 0 | false |
| 明 | 7 | 0 | 1 | true |
| 林 | 7 | 0 | 1 | true |

诊断结论：

- balanced 在总量上确实位于 baseline 与 conservative 之间，没有回到全连。
- `国/德/明/林` 比 conservative 增加了少量 curved connector，是优先人工看图样本。
- `福/和` 数量与 conservative 相同，但 connector 曲线和 taper 有变化。
- `中/人` 仍清零，说明 balanced 对极短/结构简单字可能仍偏保守。
- 楷书/隶书安全检查没有 connector violation。
- 该轮不是最终行楷模型，也不是 `candidate_default_v2`；是否继续推进需要用户人工看图反馈。

## 2026-06-18 balanced 行楷 refinement 人工反馈归档与 candidate_default_v2

用户人工看图后，对 `xingkai_balanced_experiment_20260618_141424` 做收口记录：

```text
experiments/llm_style_trajectory/docs/xingkai_balanced_decision.md
experiments/llm_style_trajectory/configs/execution_refinement_profiles.json
```

人工反馈摘要：

- 每个字基本只多了一笔连笔，变化不激进。
- `福` 的连笔数量仍为 1，但换了位置。
- balanced 效果可以接受。
- 曲线 connector 更像“带过去”，都是曲线而不是直线。
- 当前仍不直接进入仿真书写，只作为候选执行层。

决策：

- 新增 `candidate_default_v2`。
- `candidate_default_v2.connector_rule = balanced`。
- `candidate_default_v2.connector_shape = slight_curve`。
- `candidate_default_v2.stroke_width_profile = xingkai_expressive_taper`。
- `candidate_default_v2.status = accepted_for_next_round_candidate`。
- `candidate_default_v2` 暂不替换全局默认。
- `candidate_default_v1` 继续保留为 conservative refined baseline。

边界：

- v2 不是最终行楷模型，不是真实书法学习。
- v2 不解决 lishu 真实风格来源问题。
- v2 不代表真实机器人书写效果，也不进入 CoppeliaSim/AUBO i5 仿真或实机链路。

## 2026-06-18 Font-driven style gap analysis / 字体轮廓驱动的风格差距诊断

基于用户判断“Make Me a Hanzi 统一基底会限制真实风格上限”，本轮停止继续细调 connector/taper，新增字体轮廓驱动的风格差距诊断：

```text
experiments/llm_style_trajectory/configs/font_style_gap_chars.json
experiments/llm_style_trajectory/src/font_style_gap_analysis.py
experiments/llm_style_trajectory/tests/test_font_style_gap_analysis.py
experiments/llm_style_trajectory/outputs/font_style_gap_analysis_20260618_144838/
experiments/llm_style_trajectory/outputs/paper_figures/font_style_gap_analysis_index.md
```

本轮使用 `style_sources.json` 中的系统字体样本：kaishu=`simkai.ttf`、xingkai=`STXINGKA.TTF`、lishu=`SIMLI.TTF`。
对 18 个字 × 3 种风格共 54 个样本进行字体二值渲染，并与上一轮多字轨迹诊断
`style_diagnostics_20260617_200746/style_diagnostic_summary.csv` 对齐比较。

样本统计：

| total | rendered_success | failures |
|---:|---:|---:|
| 54 | 54 | 0 |

三风格均值：

| style | samples | mean_font_aspect_ratio | mean_trajectory_aspect_ratio | mean_abs_aspect_ratio_gap | mean_font_components | mean_trajectory_connections | mean_font_stroke_width | mean_trajectory_mean_width |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.029878 | 1.018672 | 0.058451 | 2.888889 | 0.0 | 6.320909 | 9.0 |
| xingkai | 18 | 0.989059 | 1.070791 | 0.126632 | 1.555556 | 6.055556 | 9.575023 | 7.488813 |
| lishu | 18 | 1.480275 | 1.465173 | 0.110869 | 2.5 | 0.0 | 8.956169 | 10.0 |

主要诊断结论：

- lishu 平均字体 aspect ratio 与当前轨迹均值接近，说明全局宽扁比例大体对上；但这不能证明已经学到真实隶书结构，因为当前轨迹仍主要是楷书 median 骨架的全局横向拉宽/纵向压扁。
- xingkai 字体 connected component 均值为 `1.555556`，当前轨迹 connection_count 均值为 `6.055556`；二者只是弱对应，但提示当前 connector prior 仍带有较强人工规则色彩。
- kaishu 的 aspect ratio gap 最小，符合当前基底本身更接近楷书的判断。
- 本轮更明确地把下一步升级方向从“继续盲调 connector/taper”转向“从字体/图像统计中系统估计 style profile 参数”。

建议优先数据化升级的参数：

- `horizontal_scale / vertical_scale`
- stroke width distribution
- component-level proportions
- connectedness / connector prior
- horizontal / vertical projection distribution

边界：

- 字体轮廓不等于真实书写轨迹。
- 静态字体不能直接给出真实书写时序、速度、抬笔高度或机器人动态控制参数。
- 本轮不调 style profile，不替换全局默认，不生成最终新轨迹，不调用 API，不连接 CoppeliaSim/AUBO i5。
- 图表仍需要人工看图校验，尤其是 `font_style_grid.png`、`lishu_flatness_gap.png` 与 `xingkai_connectedness_gap.png`。

## 2026-06-18 Style profile 数据化升级方案设计与参数分层表

基于上一轮 font-driven style gap analysis，本轮不再细调 connector/taper，也不替换默认 style profile，而是新增一套 style profile 数据化升级方案：

```text
experiments/llm_style_trajectory/configs/style_profile_parameter_schema.json
experiments/llm_style_trajectory/src/style_profile_upgrade_plan.py
experiments/llm_style_trajectory/tests/test_style_profile_upgrade_plan.py
experiments/llm_style_trajectory/outputs/style_profile_upgrade_plan_20260618_150757/
experiments/llm_style_trajectory/outputs/paper_figures/style_profile_upgrade_plan_index.md
```

输出文件：

| 文件 | 内容 |
|---|---|
| `style_profile_parameter_matrix.csv` | 23 个参数的层级、来源、估计可行性、优先级和风险 |
| `style_profile_upgrade_plan.md` | 数据化升级方案报告 |
| `style_profile_upgrade_recommendations.json` | 三阶段升级建议 |
| `prototype_style_profile_estimates.json` | 仅供参考的 style-level prototype hints，不接默认流程 |
| `figures/parameter_source_matrix.png` | 参数来源矩阵图 |
| `figures/upgrade_priority_chart.png` | 分阶段优先级图 |

参数分层统计：

| level | count |
|---|---:|
| style | 10 |
| component | 2 |
| process_prior | 11 |

阶段统计：

| phase | count | can_estimate_now |
|---|---:|---:|
| phase_1 | 7 | 7 |
| phase_2 | 5 | 0 |
| phase_3 | 11 | 0 |

三阶段路线：

- Phase 1：现在就能做、风险较低的字体轮廓全局形态和宽度参数，包括 `horizontal_scale`、`vertical_scale`、`base_width`、`stroke_width_distribution`、`horizontal_projection_distribution`、`vertical_projection_distribution`、`lishu_flatness`。
- Phase 2：需要设计映射的 char/component-level 参数，包括 `smoothness`、`corner_rounding`、`component_width_ratio`、`component_height_ratio`、`xingkai_connectedness_prior`。
- Phase 3：静态字体难直接估计、需要轨迹或人工反馈的 process priors，包括 `speed_scale`、`connection_strength`、`allow_interstroke_connections`、`pen_up_height`、stroke taper、`pressure_curve`、connector trigger/shape/width 等。

明确不能从静态字体直接估计：

- `pen_up_height`
- `speed_scale`
- `pressure_curve`
- `allow_interstroke_connections`
- `real_robot_dynamics`

prototype 状态：

- `prototype_style_profile_estimates.json` 已生成。
- `_status = prototype_not_used_by_default`
- `_warning = not wired into generation pipeline`
- 该文件只用于后续讨论和设计，不被 `run_demo.py` 或当前生成链路读取。

边界：

- 本轮不替换默认 style profile，不改变 `run_demo.py` 默认行为。
- 本轮不继续调 connector/taper 数值。
- 字体轮廓不等于真实书写轨迹，Phase 1 之后仍需要人工看图校验。
- 静态字体不能直接给速度、抬笔高度、真实压力或机器人动态控制。

## 2026-06-18 Phase 1 font-outline style profile readonly estimator

基于上一轮参数分层表，本轮新增 Phase 1 只读估计器，把可从静态字体轮廓低风险估计的参数整理成候选 estimates 文件和报告。本轮不替换 `style_profiles.json`，不改变 `run_demo.py` 默认行为，不生成新 trajectory / execution / workspace。

```text
experiments/llm_style_trajectory/src/style_profile_phase1_estimator.py
experiments/llm_style_trajectory/tests/test_style_profile_phase1_estimator.py
experiments/llm_style_trajectory/outputs/style_profile_phase1_estimates_20260618_152952/
experiments/llm_style_trajectory/outputs/paper_figures/style_profile_phase1_estimates_index.md
```

输出文件：

| 文件 | 内容 |
|---|---|
| `style_profile_phase1_estimates.json` | 只读候选 estimates，含 `_status=readonly_estimate_not_used_by_default` |
| `style_profile_phase1_parameter_comparison.csv` | 当前 profile vs Phase 1 hints |
| `style_profile_phase1_estimate_report.md` | Phase 1 估计报告 |
| `style_profile_phase1_estimate_warnings.csv` | 静态字体不支持估计的参数 |
| `figures/current_vs_phase1_scale.png` | 当前 scale 与 Phase 1 scale hints 对比 |
| `figures/current_vs_phase1_width.png` | Phase 1 base width hints |
| `figures/phase1_projection_summary.png` | 字体投影 spread summary |

候选 estimates 状态：

- `_status = readonly_estimate_not_used_by_default`
- `_source = font_style_gap_analysis_20260618_144838`
- `_warning = not wired into generation pipeline`

Current vs Phase 1 关键差异：

| style | parameter | current | phase1_hint | delta | confidence |
|---|---|---:|---:|---:|---|
| kaishu | horizontal_scale | 1.0 | 1.0 | 0.0 | medium |
| kaishu | vertical_scale | 1.0 | 1.0 | 0.0 | medium |
| lishu | horizontal_scale | 1.18 | 1.198887 | 0.018887 | medium |
| lishu | vertical_scale | 0.82 | 0.834107 | 0.014107 | medium |
| xingkai | horizontal_scale | 1.03 | 0.979982 | -0.050018 | low |
| xingkai | vertical_scale | 0.98 | 1.020427 | 0.040427 | low |
| kaishu | base_width | - | 6.320909 | - | medium |
| lishu | base_width | - | 8.956169 | - | medium |
| xingkai | base_width | - | 9.575023 | - | medium |

可估计的 Phase 1 hints：

- `horizontal_scale_hint`
- `vertical_scale_hint`
- `base_width_hint`
- `stroke_width_distribution`
- `projection_summary`
- `lishu_flatness`

不支持从静态字体估计：

- `connection_strength`
- `allow_interstroke_connections`
- `connector_trigger`
- `connector_shape`
- `pressure_curve`
- `speed_scale`
- `pen_up_height`
- `real_robot_dynamics`

诊断结论：

- lishu flatness 可以从字体 aspect 统计给出提示；但当前 lishu 接近字体 aspect 仍只说明整体宽扁比例接近，真实隶书结构需要 component-level / 笔画级数据。
- xingkai connectedness 不能直接等价为 connector 数量，connector 仍需人工看图、轨迹数据或执行层反馈。
- 这些 estimates 只适合下一轮生成“非默认对比图”时作为实验输入，不能直接替换默认 profile。
## 2026-06-18 Phase 1 readonly estimates 非默认对比图验证

本轮基于上一轮 `style_profile_phase1_estimates.json` 生成了显式输入的 comparison-only profile，并对 current profile 与 phase1 candidate 做轨迹/执行层图像和指标对比。该候选 profile 只写入实验输出目录，不替换 `experiments/llm_style_trajectory/configs/style_profiles.json`，不改变 `run_demo.py` 默认行为，也不接入默认生成链路。

输出目录：

```text
experiments/llm_style_trajectory/outputs/phase1_profile_comparison_20260618_155353/
experiments/llm_style_trajectory/outputs/paper_figures/phase1_profile_comparison_index.md
```

关键输出：

| 文件 | 内容 |
|---|---|
| `style_profile_phase1_candidate.json` | `_status=comparison_only_not_default` 的临时候选 profile |
| `phase1_profile_comparison_summary.csv` | current vs phase1 指标表 |
| `phase1_profile_comparison_report.md` | Phase 1 有效性和局限报告 |
| `phase1_profile_comparison_manifest.csv` | 人工看图清单 |
| `figures/compare_current_phase1_u4eba_all_styles.png` | “人”三风格 current/phase1 对比 |
| `figures/compare_current_phase1_u4e2d_all_styles.png` | “中”三风格 current/phase1 对比 |
| `figures/compare_current_phase1_u597d_lishu.png` | “好”隶书对比 |
| `figures/compare_current_phase1_u98ce_lishu.png` | “风”隶书对比 |
| `figures/compare_current_phase1_u56fd_xingkai.png` | “国”行楷对比 |
| `figures/compare_current_phase1_u5fb7_xingkai.png` | “德”行楷对比 |

平均变化：

| style | samples | mean_abs_aspect_ratio_delta | mean_abs_path_length_delta | mean_abs_mean_width_delta |
|---|---:|---:|---:|---:|
| kaishu | 3 | 0.000000 | 0.000 | 0.000000 |
| lishu | 4 | 0.001680 | 10.368 | 0.000000 |
| xingkai | 5 | 0.090515 | 7.508 | 0.006537 |

诊断结论：

- kaishu 基本不变，符合 Phase 1 估计。
- lishu 只有全局尺度层面的小幅变化；如果人工看图仍像“压扁版楷书”，说明真正问题不在全局 flatness，而在结构/笔画级特征。
- xingkai 的 aspect 会随全局 scale 改变，但 connector 数量和规则被明确保留，因此不能靠 Phase 1 全局 scale 解决行楷味问题。
- Phase 1 的主要价值是确认“全局字体轮廓参数改善空间有限”；下一步应进入 Phase 2 component/stroke-level style modeling，而不是把 readonly estimates 接入默认流程。

人工看图优先级：优先看 “人/中” 三风格总览、“好/风” 隶书、“国/德/福” 行楷。数值指标只能说明全局比例变化，最终仍需人工确认 lishu 是否仍像压扁楷书、xingkai 是否仍主要由 connector 决定。
## 2026-06-18 小论文实验对比方案与可执行实验清单

本轮没有新增算法、没有调参、没有扩大实验，也没有接入 API、CoppeliaSim、AUBO i5、IK 或 SDK。目标是把当前已有结果整理成可写小论文的实验对比方案。

新增固定资料：

```text
experiments/llm_style_trajectory/docs/mini_paper_experiment_plan.md
experiments/llm_style_trajectory/configs/mini_paper_experiment_matrix.json
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_experiment_plan_index.md
```

建议论文主线：

```text
自然语言约束驱动的书法机器人参数化轨迹生成与执行前检查方法
```

建议主实验分为六组：

- A. 自然语言 modifier 可控性：fixed profile/no modifier vs modifier-controlled profile。
- B. 行楷 connector rule 对比：all_adjacent baseline vs candidate_default_v1 vs candidate_default_v2。
- C. execution width/pressure 对比：fixed width/flat pressure vs simple_taper / xingkai_expressive_taper。
- D. motion continuity 与 retiming：raw target poses vs smoothed target poses。
- E. robot-interface precheck chain：2D trajectory vs execution/workspace/retiming/command/IK-feasibility dry-run chain。
- F. font outline gap / style profile 数据化：current profile vs Phase 1 readonly estimates / comparison-only profile，用作限制和后续工作。

边界写法已经明确：当前方法是参数化控制和执行前检查，不是真实书法风格学习；Make Me a Hanzi median strokes 限制风格上限；字体轮廓不等于真实书写轨迹；AUBO i5 仍是 dry-run，不是实机验证。
## 2026-06-18 小论文固定图表包整理

本轮继续沿用上一轮小论文实验方案，不新增算法、不调参数、不跑新的大规模实验、不接机器人接口，只把分散结果整理为固定命名图表包。

新增整理脚本：

```text
experiments/llm_style_trajectory/src/mini_paper_figure_pack.py
experiments/llm_style_trajectory/tests/test_mini_paper_figure_pack.py
```

固定输出目录：

```text
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/
```

关键输出：

| 文件 | 内容 |
|---|---|
| `mini_paper_figure_index.md` | 小论文固定图表包索引、caption 草稿、人工看图提示和边界说明 |
| `mini_paper_figure_manifest.csv` | 12 个 figure/supplementary figure 条目的来源、caption、状态和人工检查标记 |
| `mini_paper_table_manifest.csv` | 3 个 table 条目的来源、caption 和状态 |
| `missing_sources.csv` | 缺源记录，本轮为 0 |
| `fig1_system_pipeline.png` | 基于已有文档重画的系统流程图 |
| `fig2_modifier_control_connection.png` | 连笔 modifier 可控性图 |
| `fig2_modifier_control_shape.png` | 宽扁 modifier 可控性图 |
| `fig2_modifier_control_smoothness.png` | 圆滑 modifier 可控性图 |
| `fig3_xingkai_connector_levels_u56fd.png` | 国 / 行楷 connector baseline-v1-v2 对比 |
| `fig3_xingkai_connector_levels_u5fb7.png` | 德 / 行楷 connector baseline-v1-v2 对比 |
| `fig3_xingkai_connector_levels_u660e.png` | 明 / 行楷 connector baseline-v1-v2 对比 |
| `fig4_execution_width_pressure.png` | execution width / pressure 可视化 |
| `table1_retiming_before_after.md/.csv` | raw target poses vs smoothed target poses |
| `table2_robot_precheck_summary.md/.csv` | workspace / CoppeliaSim / command / IK feasibility dry-run 链条 |
| `table3_external_functional_comparison.md/.csv` | 外部方法功能维度对比表，不含外部数值复现 |

补充材料放入：

```text
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/supplementary/
```

其中包含 font style gap 和 Phase 1 readonly estimates 相关图，用于说明当前风格仍是参数化控制，真实风格学习与 component/stroke-level profile 数据化是后续方向。

需要人工重点看的图：Figure 2 三组 modifier 图、Figure 3 三张行楷 connector 对比图、Figure 4 execution width/pressure 图，以及 supplementary 中的 lishu flatness gap 图。数值指标不能替代人工看图。

边界：该图表包只做整理、复制、重命名、汇总和一张流程示意图；没有替换默认 style profile，没有把 `candidate_default_v2` 设为全局默认，没有调用 API/CoppeliaSim/AUBO i5/SDK，也没有发送机器人命令。

## 2026-06-18 小论文人工视觉评价与图注草稿整理

本轮继续围绕 `mini_paper_figures` 固定图表包做论文写作材料整理，不新增算法、不调 style/profile/refinement 参数、不调用 API、不连接 CoppeliaSim/AUBO/SDK、不修改 shared data 或 legacy。

新增材料：

```text
experiments/llm_style_trajectory/docs/mini_paper_visual_evaluation_template.md
experiments/llm_style_trajectory/docs/mini_paper_figure_captions_draft.md
experiments/llm_style_trajectory/docs/mini_paper_experiment_section_outline.md
experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/human_visual_evaluation_template.csv
```

`human_visual_evaluation_template.csv` 覆盖 15 个评价项，评价维度包括 modifier 控制是否可见、行楷 connector 是否自然、stroke taper / pressure-width 可视化是否清楚、隶书是否只是横向拉宽/纵向压扁、布局是否自然、是否适合作为论文主图。

`mini_paper_figure_captions_draft.md` 已为 Figure 1-4、Table 1-3 和 supplementary style gap / Phase 1 图写出中文图注草稿。图注统一保持保守表述：`candidate_default_v2` 只写为折中候选规则；CoppeliaSim/AUBO 只写执行前检查、dry-run 或可视化准备；外部方法表只写功能维度对比，不写数值复现。

`mini_paper_experiment_section_outline.md` 给出实验章节草稿骨架，包含实验设置、modifier 可控性、行楷 connector rule 消融、执行层 width/pressure、motion continuity 与 retiming、机器人接口前 dry-run、外部方法功能对比、局限性与未来工作。

核心限制已经写入文档：当前风格变化仍是参数化控制；隶书仍可能偏“压扁楷书”；行楷 connector 是规则生成，不是真实书法风格学习；机器人相关输出仍不是实机实验。

## 2026-06-19 Font-outline-derived trajectory basis feasibility

本轮暂停 mini-paper 图表包装，转向“大方向方法验证”：判断是否继续把 MakeMeAHanzi median 作为唯一轨迹基底。

新增只读诊断：
```text
experiments/llm_style_trajectory/configs/font_outline_basis_chars.json
experiments/llm_style_trajectory/src/font_outline_basis_feasibility.py
experiments/llm_style_trajectory/tests/test_font_outline_basis_feasibility.py
```

真实输出目录：
```text
experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/
```

固定论文/汇报入口：
```text
experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_feasibility_index.md
```

本轮使用 `style_sources.json` 中的本地字体候选，对 `山、中、永、人、国、德、福、明、和、风` 做 MakeMeAHanzi median 与三字体 mask+skeleton candidate 对比。三种字体 skeleton 提取成功率均为 10/10；隶书相对 median 的 aspect 差异最明显，说明字体轮廓基底确实能呈现比全局拉宽/压扁更强的风格差异。复杂字如 `德`、`福`、`明` 的 skeleton 端点和分叉较多，提示直接转轨迹前需要去噪、连通性修复和笔画顺序恢复。

边界：本轮只是 feasibility / diagnostic，不替换默认 pipeline，不改 `style_profiles.json`，不改 `run_demo.py` 默认行为，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。

## 2026-06-19 Font outline basis 人工筛选包与 skeleton 问题分类

基于上一轮：
```text
experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/
```

新增只读 audit 层：
```text
experiments/llm_style_trajectory/src/font_outline_basis_audit.py
experiments/llm_style_trajectory/tests/test_font_outline_basis_audit.py
```

真实输出目录：
```text
experiments/llm_style_trajectory/outputs/font_outline_basis_audit_20260619_120211/
```

固定论文/汇报入口：
```text
experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_audit_index.md
```

## 2026-06-19 Font skeleton cleanup prototype（kaishu / lishu only）

基于 `font_outline_basis_feasibility_20260619_115008/` 和上一轮人工筛选结论，本轮新增只读诊断层：

```text
experiments/llm_style_trajectory/src/font_skeleton_cleanup_prototype.py
experiments/llm_style_trajectory/tests/test_font_skeleton_cleanup_prototype.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/font_skeleton_cleanup_prototype_20260619_122355/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_cleanup_prototype_index.md
```

本轮只处理 `山 / 中 / 人 / 永 / 风` 的 `kaishu` 和 `lishu` 字体 skeleton，明确排除 `xingkai`，不生成正式 `trajectory.csv`，不替换默认 MakeMeAHanzi median pipeline。cleanup 仅包含轻量操作：删除小连通分量、剪短端点枝、可选合并极近端点，并输出 before/after 图和统计。

成功率：kaishu=5/5，lishu=5/5。平均变化：kaishu endpoint -1.8、branch -1.8、component 0.0、skeleton pixels -8.6；lishu endpoint -0.8、branch -0.8、component 0.0、skeleton pixels -2.0。说明轻量 cleanup 对楷书简化更明显，对隶书更保守；`永/kaishu`、`永/lishu`、`风/kaishu` 清理后仍有多连通分量，需要人工看图判断是否可进入 path extraction。

边界：当前仍不是正式书写轨迹，不是默认 pipeline，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。

输出包括 `font_outline_basis_audit_candidates.csv`、`font_outline_basis_audit_report.md`、`visual_audit_checklist.md`、`font_outline_basis_image_manifest.csv` 和 `selected_images/`。本轮共 30 条 char/style 候选，复制 10 张优先人工看图图片。问题标签统计：`disconnected_skeleton=15`、`promising_candidate=10`、`complex_skeleton=8`、`high_aspect_gap=8`、`high_branch_count=8`、`high_endpoint_count=8`。优先人工看的样本集中在 `德`、`福`、`国` 的高分叉/多连通分量风险，以及 `山`、`中`、`风` 等隶书 high aspect gap 样本。

边界：本轮只做人工筛选包和 skeleton 问题分类，不把 font skeleton 接入默认 pipeline，不调 connector/taper，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。
## 2026-06-19 Font skeleton path extraction prototype（very small sample）

基于 `font_skeleton_cleanup_prototype_20260619_122355/`，本轮新增 very small-sample path extraction prototype：

```text
experiments/llm_style_trajectory/src/font_skeleton_path_extraction_prototype.py
experiments/llm_style_trajectory/tests/test_font_skeleton_path_extraction_prototype.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/font_skeleton_path_extraction_20260619_123527/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_path_extraction_index.md
```

样本严格限制为 `山/kaishu`、`人/kaishu`、`中/kaishu`、`山/lishu`、`永/lishu`；明确不处理 xingkai、德、福、国、风和其他复杂字。本轮把 cleaned skeleton 当作 8-neighborhood graph，提取 endpoint-to-branch / branch-to-branch / endpoint-to-endpoint 候选 segments，并按 `component_order_longest_first` 给出 candidate order 标签。

五个样本都生成了候选 path segments，且 `recommended_for_next_stage=True`。其中 `山/kaishu`、`人/kaishu`、`山/lishu` 更适合先人工看图判断是否进入 font-derived trajectory trial；`中/kaishu` 存在 `high_branch_count`，`永/lishu` 存在 `multi_component_skeleton`，虽有风格信号但仍需人工确认路径是否过碎或顺序明显不合理。

边界：当前不是正式轨迹，不生成 `trajectory.csv`，不含真实笔顺，不替换 MakeMeAHanzi median，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。
## 2026-06-19 Font-derived trajectory trial（3 low-risk samples）

基于 `font_skeleton_path_extraction_20260619_123527/`，本轮只处理三个低风险样本：

```text
山 / kaishu
人 / kaishu
山 / lishu
```

新增 trial 脚本与测试：

```text
experiments/llm_style_trajectory/src/font_derived_trajectory_trial.py
experiments/llm_style_trajectory/tests/test_font_derived_trajectory_trial.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/font_derived_trajectory_trial_20260619_125428/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_derived_trajectory_trial_index.md
```

每个样本子目录只输出 `font_derived_trial_trajectory.csv`、`font_derived_trial_summary.json` 和 `font_derived_trial_compare.png`；没有生成正式 `trajectory.csv`，也没有生成 execution / workspace / CoppeliaSim / AUBO 文件。

三样本结果：`山/kaishu` segment_count=7、point_count=19、warning=`short_segments_filtered:10`；`人/kaishu` segment_count=4、point_count=19、warning=`short_segments_filtered:2`；`山/lishu` segment_count=4、point_count=16、warning=`short_segments_filtered:4`。当前最值得人工看的图是 `人/kaishu`（最干净）、`山/lishu`（隶书风格信号明显）和 `山/kaishu`（暴露 segment order 仍非真实笔顺）。

边界：本轮不是正式轨迹，不含真实笔顺，不含 execution width/pressure，不接机器人，不替换 MakeMeAHanzi median，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。
# 2026-06-19 Font skeleton stroke ordering / simplification prototype

基于 `font_derived_trajectory_trial_20260619_125428/`，本轮只处理两个极小样本：

```text
人 / kaishu
山 / lishu
```

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/font_skeleton_stroke_ordering_prototype.py
experiments/llm_style_trajectory/tests/test_font_skeleton_stroke_ordering_prototype.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/font_skeleton_stroke_ordering_20260619_132543/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_stroke_ordering_index.md
```

本轮只读取 `font_derived_trial_trajectory.csv`，对 trial path segments 做保守简化、短段过滤和近端点合并，并给出 `candidate writable order`。每个样本只输出 `font_skeleton_ordered_trial_trajectory.csv`、`font_skeleton_ordering_summary.json` 和 `font_skeleton_ordering_compare.png`，没有生成正式 `trajectory.csv`，也没有生成 execution/workspace/CoppeliaSim/AUBO 文件。

结果：`人/kaishu` 从 raw_segment_count=4 简化为 simplified_segment_count=2，ordered_stroke_like_count=2，适合作为两个主笔画的首个可写顺序候选；`山/lishu` raw_segment_count=4，simplified_segment_count=4，ordered_stroke_like_count=4，warning=`segment_count_unchanged`，说明当前更适合保留多个 stroke-like segments，不应强行全部连起来。

边界：这仍不是正式轨迹，不是真实笔顺恢复，不接默认 pipeline，不替换 MakeMeAHanzi median，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。下一步只有在人工看图确认顺序和风格保留可接受后，才建议进入 font-derived execution mock。

# 2026-06-19 Median-to-font skeleton alignment / adaptation prototype

暂停纯 font skeleton -> trajectory 路线后，本轮转向 B 路线：保留 MakeMeAHanzi median 的 stroke order 和 stroke break，用 font mask / cleaned skeleton 作为形态参考，对 median 点做轻量 soft projection。

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/median_font_alignment_prototype.py
experiments/llm_style_trajectory/tests/test_median_font_alignment_prototype.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/median_font_alignment_20260619_145307/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/median_font_alignment_index.md
```

本轮只处理 `人/kaishu` 和 `山/lishu`。输出 `adapted_trial_alpha_025.csv`、`adapted_trial_alpha_050.csv`、`median_font_alignment_summary.json` 和 `median_font_alignment_compare.png`，没有生成正式 `trajectory.csv`，也没有生成 execution/workspace/CoppeliaSim/AUBO 文件。

结果：`人/kaishu` stroke_count=2 保持不变，projection distance 从 6.557520 降到 4.918140（alpha=0.25）和 3.278760（alpha=0.5），max shift 分别为 5.748356 / 11.496712 px；视觉上两笔结构保持较稳。`山/lishu` stroke_count=3 保持不变，projection distance 从 36.000849 降到 29.389616（alpha=0.25）和 23.972679（alpha=0.5），max shift 分别为 10.532784 / 15.000000 px；但 bbox aspect 从 median 0.945007 变到 0.882980 / 0.864289，未朝 lishu font aspect 1.375 靠近，说明最近邻吸附改善了局部贴近度，但尚未解决全局隶书宽底形态。

边界：本轮是 median + font skeleton 融合诊断，不是纯 skeleton 轨迹，不恢复真实笔顺，不改变 stroke 数量，不接默认 pipeline，不替换 MakeMeAHanzi median，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。下一步若继续，建议做 median-font adaptation v2：加入 stroke-level bbox / anchor alignment 和更保守的 alpha 策略。

# 2026-06-19 Median-font adaptation v2 prototype

在 B 路线 v1 的 alpha-only 最近点吸附基础上，本轮新增 global bbox alignment 与 stroke-level anchor alignment，继续只处理两个极小样本：

```text
人 / kaishu
山 / lishu
```

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/median_font_adaptation_v2.py
experiments/llm_style_trajectory/tests/test_median_font_adaptation_v2.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/median_font_adaptation_v2_20260619_154351/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/median_font_adaptation_v2_index.md
```

本轮输出 `adapted_v2_conservative.csv` 与 `adapted_v2_stronger.csv`，没有生成正式 `trajectory.csv`，也没有生成 execution/workspace/CoppeliaSim/AUBO 文件。stroke_count 保持不变：`人/kaishu=2`，`山/lishu=3`。

关键结果：

| 样本 | before projection | v1 alpha=0.25 | v2 conservative | v2 stronger | aspect gap before | aspect gap v1 | aspect gap v2 conservative | aspect gap v2 stronger |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 人/kaishu | 6.557520 | 4.918140 | 4.521372 | 3.739090 | 0.066713 | 0.062410 | 0.061491 | 0.053279 |
| 山/lishu | 36.000849 | 29.389616 | 24.474754 | 20.563365 | 0.433371 | 0.495398 | 0.435363 | 0.441557 |

诊断结论：`人/kaishu` 的 projection distance 与 aspect gap 都较 v1 有小幅改善，且最大点移动保持在 10.335839 px 以内，是 B 路线的稳定正例。`山/lishu` 的 projection distance 进一步下降，但 aspect gap 只是从 v1 的更差状态回到接近原 median，并未明显逼近 lishu font aspect；stronger 版本最大点移动达到 18 px 上限，后续必须人工看图判断是否是有效隶书形态改善，而不是局部牵引变形。

边界：本轮仍是 diagnostic prototype，不恢复真实笔顺，不改变 stroke 数量，不接默认 pipeline，不替换 MakeMeAHanzi median，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。下一步建议先人工查看 `median_font_adaptation_v2_compare.png`，若继续推进，应优先做 v3 的结构约束或小样本扩展，而不是直接接入默认流程。

# 2026-06-19 Lishu structure adaptation v3 prototype

基于 v2 结论“继续增大 alpha / 最近点吸附不能解决 `山/lishu` 的整体结构问题”，本轮只处理一个样本：

```text
山 / lishu
```

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/lishu_structure_adaptation_v3.py
experiments/llm_style_trajectory/tests/test_lishu_structure_adaptation_v3.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/lishu_structure_adaptation_v3_20260619_155525/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/lishu_structure_adaptation_v3_index.md
```

本轮在 v2 stronger 的基础上加入显式结构约束：下半部横向支撑、左右外侧点轻微外展、bottom support guide。输出 `lishu_structure_v3_conservative.csv` 和 `lishu_structure_v3_stronger.csv`，没有生成正式 `trajectory.csv`，没有生成 execution/workspace/robot 文件。

关键结果：

| 指标 | v2 stronger | v3 conservative | v3 stronger |
|---|---:|---:|---:|
| projection distance | 20.563365 | 20.157518 | 20.090813 |
| bbox aspect | 0.936821 | 0.958776 | 0.958299 |
| lower-half width | 156.629793 | 158.148182 | 159.569313 |
| max point shift | 18.0 | 22.0 | 22.0 |
| path length ratio | 0.870460 | 0.855510 | 0.851677 |

诊断结论：v3 的结构约束使 `山/lishu` 下半部宽度和 bbox aspect 相比 v2 有小幅改善，说明隶书确实需要 structure-level constraints，而不是继续 point-level projection。但两个 v3 版本都触达 22 px shift cap，且 bbox aspect 仍远低于 font aspect 1.378378，说明当前 heuristic 只解决了一部分结构形态问题，不能直接进入默认 pipeline。下一步更适合转向 component-level alignment 或更明确的笔画/部件锚点约束，并先人工看图判断是否出现拉扯或折笔。

边界：本轮仍是 diagnostic prototype，不声明真实隶书风格学习，不恢复真实笔顺，不改变 stroke_count，不接默认 pipeline，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。

# 2026-06-19 Lishu component-level alignment prototype

基于 v3 已触达 22px shift cap 的结论，本轮停止继续加大全局/结构拉扯，改做 `山/lishu` 的 component-level alignment prototype。样本仍只包含：

```text
山 / lishu
```

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/lishu_component_alignment_prototype.py
experiments/llm_style_trajectory/tests/test_lishu_component_alignment_prototype.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/lishu_component_alignment_20260619_160805/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/lishu_component_alignment_index.md
```

本轮把 median 点按 x/y 位置粗分为四类 component group：`left_group`、`center_group`、`right_group`、`lower_support_group`，并分别向 lishu font mask 的左右区域、中心竖向区域和下半支撑区域轻微对齐。group 点数为：

```json
{"left_group": 2, "center_group": 2, "right_group": 3, "lower_support_group": 12}
```

关键结果：

| 指标 | v3 stronger | component conservative | component stronger |
|---|---:|---:|---:|
| projection distance | 20.090813 | 19.949109 | 20.215119 |
| bbox aspect | 0.958299 | 0.970717 | 0.971593 |
| aspect gap | 0.420079 | 0.407661 | 0.406785 |
| lower-half width | 159.569313 | 160.028913 | 160.743366 |
| max point shift | 22.0 | 24.0 | 24.0 |
| path length ratio | 0.851677 | 0.843491 | 0.845014 |

诊断结论：component-level alignment 相比 v3 对 bbox aspect 和 lower-half width 有小幅正向作用，conservative 的 projection distance 也略低于 v3；但 stronger 的 projection distance 反而升高，且两个 component variant 都触达 24px shift cap。说明按部件分组是比继续全局拉扯更合理的方向，但当前 heuristic 仍偏粗，下一步如果继续，应优先改进 component group 与字体部件 target 的定义，而不是简单加大 alpha。

# 2026-06-19 Trajectory style route decision report

本轮暂停新增算法与参数调整，整理当前三条路线的证据链并形成路线决策报告：

```text
experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md
experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json
experiments/llm_style_trajectory/outputs/paper_figures/trajectory_style_route_decision_index.md
```

路线结论：

- Route A（MakeMeAHanzi median + style profile）：保留为稳定 baseline 和 robot dry-run/precheck backbone。它证明系统链路、request boundary、受控 modifier、execution layer、workspace mapping、CoppeliaSim pen-tip playback、robot target poses、AUBO command dry-run 与 IK feasibility dry-run，但不能声称高质量真实书法风格生成。
- Route B（median + font skeleton/mask adaptation）：作为保留笔顺的 safe style adaptation research direction。`人/kaishu` 是正例；`山/lishu` 多轮 v1/v2/v3/component-level 尝试说明强风格隶书迁移不能靠继续加大 point projection 或结构拉扯解决。
- Route C（font skeleton derived path）：作为 style basis research only。字体 skeleton 有更强风格信号，但笔顺恢复、路径碎片、分叉/断裂和复杂字泛化风险高，暂不接默认 pipeline。

当前推荐：下一阶段先写 hybrid route design spec，而不是继续盲调 connector/taper 或直接替换 MakeMeAHanzi median。建议结构是：A 提供笔顺、可写性、执行层和机器人 precheck 链路；B 提供有边界的形态适配；C 提供人工筛选的字体轮廓风格参考。

边界：本轮只做证据整理和路线决策，不新增生成算法，不调参数，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不做机器人控制。

# 2026-06-19 Hybrid style trajectory design spec

基于 route decision report，本轮只做 hybrid route 方案设计和接口边界整理，没有新增算法、没有调参、没有接默认 pipeline。

新增固定资料：

```text
experiments/llm_style_trajectory/docs/hybrid_style_trajectory_design_spec.md
experiments/llm_style_trajectory/configs/hybrid_style_trajectory_design_spec.json
experiments/llm_style_trajectory/outputs/paper_figures/hybrid_style_trajectory_design_index.md
```

Hybrid 核心：

- A：稳定的 MakeMeAHanzi median trajectory backbone，负责笔顺、可写性、execution layer 和 robot dry-run/precheck 链路。
- B：bounded adaptation module，只输出 trial-only CSV，必须保持 stroke_count、stroke_order 和 stroke breaks，不生成正式 `trajectory.csv`。
- C：font reference / candidate basis module，只提供人工筛选后的字体轮廓、骨架和形态参考，不直接替换 A，不直接接 execution 或机器人链路。
- Human audit gate：所有 modifier 图、font skeleton、B adaptation compare、C path extraction compare 和 execution render 都必须经过人工看图；视觉判断不能由单一指标替代。

候选 prototype：

- H1：A median + B bounded adaptation，适合后续低风险小样本，但当前 B 证据显示 `山/lishu` 容易触达 shift cap。
- H2：A median + C font reference constraints only，推荐下一步。先整理字体轮廓/骨架能提供哪些可信约束，不移动轨迹点。
- H3：A baseline + C-derived style exemplar visualization，适合论文证据和限制说明。

推荐：优先 H2。原因是它先定义 C 证据到 B 约束之间的安全接口，比继续做 point movement 更稳，也更适合论文方法框架表述。

边界：本轮不生成新轨迹，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不修改 `style_profiles.json` 或 `run_demo.py` 默认行为。

# 2026-06-19 H2 font reference constraints package

基于 hybrid route design spec，本轮执行推荐的 H2 prototype：A median + C font reference constraints only。该任务只从字体 mask / skeleton 中提取可解释风格约束，不移动 MakeMeAHanzi median 点，不生成 adapted CSV，不生成正式 `trajectory.csv`，也不接默认 pipeline、execution、workspace 或 robot 链路。

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/font_reference_constraints_package.py
experiments/llm_style_trajectory/tests/test_font_reference_constraints_package.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/font_reference_constraints_20260619_230426/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/font_reference_constraints_index.md
```

处理范围严格限制为 7 个 kaishu / lishu 代表样本：`山/kaishu`、`人/kaishu`、`中/kaishu`、`山/lishu`、`中/lishu`、`永/lishu`、`风/lishu`；明确不处理 xingkai、德、福、国和机器人接口。

约束统计：

| recommended_use | count |
|---|---:|
| usable_for_adaptation | 25 |
| visual_reference_only | 25 |
| unsafe_for_direct_use | 34 |

样本级推荐：

| recommendation | count |
|---|---:|
| candidate_for_bounded_B_adaptation | 4 |
| visual_reference_with_limited_constraints | 1 |
| visual_reference_only_high_risk | 2 |

可用于下一轮 B adaptation 的低风险约束包括 `bbox_aspect`、`lower_half_width_ratio`、`left_right_spread` 和极小幅度的 `bbox_center_shift_x/y`。`skeleton_component_count`、`skeleton_endpoint_count`、`skeleton_branch_count`、`skeleton_complexity_score` 仅作为视觉审计和复杂度诊断信号。`raw_skeleton_path` 与 `unordered_skeleton_segments` 被明确标记为 `unsafe_for_direct_use`，不能直接驱动轨迹点移动。

边界：该约束包状态为 `reference_constraints_only_not_used_by_default`。它不改 `style_profiles.json`，不改 `run_demo.py` 默认行为，不生成任何 adapted/trajectory/execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，也不修改 `code/data` 或 legacy。

边界：本轮仍是 diagnostic prototype，不声明真实隶书生成，不恢复真实笔顺，不改变 stroke_count，不接默认 pipeline，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。需要人工看图判断 component groups 是否合理、right stroke 是否过度拉扯，以及 conservative 是否比 stronger 更自然。

# 2026-06-19 H1-lite constraint-bounded median adaptation prototype

基于 H2 font reference constraints package，本轮执行 H1-lite：只使用 H2 中 `usable_for_adaptation` 的安全约束，对 MakeMeAHanzi median 做有界形态试探。该 prototype 不使用 raw skeleton path、不使用 unordered skeleton segments、不做最近点 skeleton pulling，并且保留 stroke_count、stroke order、stroke breaks 和点顺序。

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/constraint_bounded_adaptation_h1_lite.py
experiments/llm_style_trajectory/tests/test_constraint_bounded_adaptation_h1_lite.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/constraint_bounded_adaptation_h1_lite_20260619_231903/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/constraint_bounded_adaptation_h1_lite_index.md
```

处理范围严格限制为两个样本：`人/kaishu` 和 `山/lishu`。本轮不处理 xingkai、复杂字、execution、workspace、CoppeliaSim、AUBO 或 SDK。

使用的 H2 约束限定为：

```text
bbox_aspect
lower_half_width_ratio
left_right_spread
bbox_center_shift_x
bbox_center_shift_y
```

关键结果：

| char/style | bbox aspect median -> conservative -> balanced | lower-half width median -> conservative -> balanced | max shift conservative / balanced | path length ratio conservative / balanced |
|---|---:|---:|---:|---:|
| 人/kaishu | 1.414861 -> 1.402621 -> 1.392189 | 215.040000 -> 214.046706 -> 213.207647 | 1.056528 / 1.776407 px | 1.000038 / 1.000135 |
| 山/lishu | 0.945007 -> 0.998870 -> 1.048676 | 187.343097 -> 193.898937 -> 199.553901 | 5.461121 / 9.845336 px | 0.994134 / 0.989006 |

诊断：`人/kaishu` 变化非常保守，适合作为“轻量约束不破坏可写性”的正例；`山/lishu` 的 aspect 和 lower-half width 明显朝字体参考方向移动，且未触达 12/18px shift cap，说明 H2 约束比 raw skeleton pulling 更安全。但这仍需人工看图确认 balanced 是否自然、是否保留可写性和隶书结构暗示。

边界：本轮输出为 `h1_lite_conservative.csv` / `h1_lite_balanced.csv`，不生成正式 `trajectory.csv`，不接 `run_demo.py` 默认流程，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `style_profiles.json`、`run_demo.py`、`code/data` 或 legacy。

# 2026-06-19 H1-lite style contrast expansion: 山/kaishu vs 山/lishu

基于 H1-lite 的安全约束，本轮只扩展 `山/kaishu`，并与既有 `山/lishu` H1-lite 结果形成同字不同风格对照。该扩展继续复用 H2 `usable_for_adaptation` 约束，不使用 raw skeleton path、不使用 unordered skeleton segments、不做最近点吸附。

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/h1_lite_style_contrast_expansion.py
experiments/llm_style_trajectory/tests/test_h1_lite_style_contrast_expansion.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/h1_lite_style_contrast_20260619_234043/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/h1_lite_style_contrast_index.md
```

关键指标：

| style | bbox aspect median -> conservative -> balanced | lower-half width median -> conservative -> balanced | max shift conservative / balanced | path ratio balanced |
|---|---:|---:|---:|---:|
| 山/kaishu | 0.945007 -> 0.965779 -> 0.984478 | 187.343097 -> 190.213398 -> 192.664933 | 2.388712 / 4.341142 px | 0.996284 |
| 山/lishu | 0.945007 -> 0.998870 -> 1.048676 | 187.343097 -> 193.898937 -> 199.553901 | 5.461121 / 9.845336 px | 0.989006 |

同字风格 gap：

| metric | before | after conservative | after balanced |
|---|---:|---:|---:|
| bbox_aspect_gap | 0.000000 | 0.033091 | 0.064198 |
| lower_half_width_gap | 0.000000 | 3.685539 | 6.888968 |

诊断：`山/kaishu` 的 H1-lite 变化更保守，`山/lishu` 的 H1-lite 变化更明显，因此同字不同风格 gap 被拉开，同时两个 style 都保持 stroke_count=3。该结果支持 H1-lite 作为一个比 raw skeleton pulling 更稳的 hybrid B prototype，但是否“楷书仍像楷书、隶书更宽底”仍必须看 `h1_lite_u5c71_kaishu_lishu_contrast.png`。

边界：本轮仍是 trial-only / not_used_by_default，不生成正式 `trajectory.csv`，不接默认 pipeline，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `style_profiles.json`、`run_demo.py`、`code/data` 或 legacy。

# 2026-06-21 Section constraints package / fallback guide

在 hybrid section refinement 之后，本轮不继续扩大样本或调参，而是把 section-level 证据整理成可复用的约束包与 fallback guide。目标是明确：

- 什么时候 component bbox 可用；
- 什么时候必须回退 `top/mid/bottom` fallback；
- 哪些约束可以给后续 B 路线使用；
- 哪些只适合视觉参考；
- 哪些不安全，不能直接驱动轨迹变形。

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/section_constraints_package.py
experiments/llm_style_trajectory/tests/test_section_constraints_package.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/section_constraints_package_index.md
```

约束封装样本：

```text
山 / kaishu
山 / lishu
风 / lishu
```

关键结论：

- `山/kaishu` 与 `山/lishu` 都可作为 future B route 的安全输入，`section_source = component_bbox`，`fallback_used = False`。
- `风/lishu` 这次明确回退到 `top_mid_bottom_fallback`，`fallback_used = True`，适合作为 fallback-first reference-only 样本。
- usable constraints 统一为：
  `bbox_aspect`、`lower_half_width_ratio`、`left_right_spread`、`bbox_center_shift_x/y`
- reference-only constraints 统一为：
  `component_count`、`endpoint_count`、`branch_count`
- unsafe constraints 统一为：
  `raw_skeleton_path`、`unordered_skeleton_segments`

本轮不是新增算法，而是将 section-level 规则封装成 machine-readable package，便于后续 B 路线复用。边界仍然是 trial-only / not_used_by_default，不生成正式 `trajectory.csv`，不接默认 pipeline，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-20 Hybrid section refinement v1: 风/lishu single-sample risk trial

在 `风/lishu` 的 H1-lite risk trial 之后，本轮不继续扩大 H1-lite 覆盖字集，而是转向更保守的 section-level refinement。方案采用用户确认的 hybrid section 划分：

- 优先使用 font component bbox；
- 如果 component 不稳定，则回退到 `top/mid/bottom`；
- 仍只允许使用 H2 的 safe constraints：
  `bbox_aspect`、`lower_half_width_ratio`、`left_right_spread`、`bbox_center_shift_x/y`；
- 不使用 raw skeleton path、unordered skeleton segments 或最近点吸附。

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/hybrid_section_refinement_v1.py
experiments/llm_style_trajectory/tests/test_hybrid_section_refinement_v1.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/hybrid_section_refinement_index.md
```

本轮只处理：

```text
风 / lishu
```

关键结果：

| field | value |
|---|---|
| section_count | 3 |
| section_names | `top_band`, `mid_band`, `bottom_band` |
| section_source | `top_mid_bottom_fallback` |
| stroke_count | 4 |
| point_count | 39 |

关键指标：

| variant | bbox_aspect | lower_half_width | left_right_spread | max_point_shift_px | path_length_ratio |
|---|---:|---:|---:|---:|---:|
| median | 1.188427 | 215.040000 | 215.040000 | 0.000000 | 1.000000 |
| conservative | 1.259425 | 219.856896 | 219.856896 | 5.543559 | 0.982155 |
| balanced | 1.306963 | 223.297536 | 223.297536 | 8.824495 | 0.973699 |

诊断：本轮 `风/lishu` 没有得到足够稳定的 font component bbox，最终自动走了 `top/mid/bottom fallback`。这说明对更复杂的隶书字，component-first 思路在当前提取质量下还不够稳，而 hybrid fallback 至少避免了继续走 raw skeleton pulling。结果上，`bbox_aspect` 和 `lower_half_width` 都比 H1-lite 有轻微继续向隶书宽底方向移动，同时 `max_point_shift_px` 仍保持在 9px 以内，`path_length_ratio` 也没有明显塌缩，因此从数值看比早期 v3/component-level 的大拉扯更稳。

但这一轮并没有真正验证“component bbox 为主”的收益，因为实际使用的是 fallback 分段。下一步更适合先整理 section 约束包或先在 `山/lishu` 这种更稳定样本上复现同样流程，而不是马上扩大到更多复杂 lishu 字。人工看图仍然是决定是否继续的前置 gate。

边界：本轮仍是 trial-only / not_used_by_default，不生成正式 `trajectory.csv`，不接默认 pipeline，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `style_profiles.json`、`run_demo.py`、`code/data` 或 legacy。

# 2026-06-20 H1-lite single-sample risk trial: 风/lishu

在 H1-lite small contrast 之后，本轮只对更复杂的 `风/lishu` 做 single-sample risk trial，继续使用 H2 的安全约束：`bbox_aspect`、`lower_half_width_ratio`、`left_right_spread` 和小幅 `bbox_center_shift_x/y`。不使用 raw skeleton path、不使用 unordered skeleton segments、不做最近点吸附，不生成正式 `trajectory.csv`、execution/workspace/robot 文件，也不接默认 pipeline。

新增脚本和测试：

```text
experiments/llm_style_trajectory/src/h1_lite_feng_lishu_risk_trial.py
experiments/llm_style_trajectory/tests/test_h1_lite_feng_lishu_risk_trial.py
```

真实输出目录：

```text
experiments/llm_style_trajectory/outputs/h1_lite_feng_lishu_risk_trial_20260620_212829/
```

固定论文/汇报入口：

```text
experiments/llm_style_trajectory/outputs/paper_figures/h1_lite_feng_lishu_risk_trial_index.md
```

关键指标：

| char/style | bbox aspect median -> conservative -> balanced | lower-half width median -> conservative -> balanced | max shift conservative / balanced | path ratio balanced |
|---|---:|---:|---:|---:|
| 风/lishu | 1.188427 -> 1.249587 -> 1.305703 | 215.040000 -> 220.805168 -> 225.873828 | 4.388260 / 8.007583 px | 0.985405 |

与山/lishu 的参考对照：

| metric | before | after conservative | after balanced |
|---|---:|---:|---:|
| bbox_aspect_gap | 0.243420 | 0.250717 | 0.257027 |
| lower_half_width_gap | 27.696903 | 26.906231 | 26.319927 |

诊断：风/lishu 仍可保持 trial-only、stroke_count=4 不变，并且 balanced 比 conservative 更明显地朝 lishu 宽底方向移动，但它已经比山/lishu 更复杂，gap 也更大，说明 H1-lite 对复杂 lishu 字开始接近边界。下一步更适合转回 component-level / section-level constraint refinement，而不是直接继续扩大 H1-lite 覆盖字集。

边界：本轮仍是 trial-only / not_used_by_default，不生成正式 `trajectory.csv`，不接默认 pipeline，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `style_profiles.json`、`run_demo.py`、`code/data` 或 legacy。


## B-route constraint registry / gated probe

The B route now has a registry-gated adaptation entry point. H2 font-reference constraints and section constraints are unified into a read-only registry, and the very small probe is limited to 山/lishu and 风/lishu. The registry classifies constraints into usable / reference-only / blocked buckets, keeps raw skeleton paths blocked, and stays trial-only / not used by default.


## B-route handoff note
A short handoff note now points new threads to the route decision report, the B-route registry index, and the section/font reference packages. It keeps the B route trial-only and blocks raw skeleton pulling from the default path.

# 2026-06-21 B-route 关键图中文化 + 差异辅助重绘

本轮不做新实验，只对三张关键 B-route 图做中文化和差异辅助表达增强：

- `h1_lite_u5c71_kaishu_lishu_contrast_cn.png`
- `h1_lite_u98ce_lishu_risk_contrast_cn.png`
- `hybrid_section_compare_cn.png`

重绘内容包括：中文标题、中文 panel 标签、原始灰色轨迹与调整后彩色轨迹叠加、位移细连线、以及 `山` 底部 / `风` 下半部的局部放大。

诊断：`山/kaishu vs 山/lishu` 现在更容易看出宽底差异，但整体差异仍偏弱；`风/lishu` 的 conservative / balanced 仍然接近，是最需要诚实提示“差异不大”的一张；`hybrid_section_compare_cn` 现在最适合做人工判断，因为 section 分区、原始轨迹和两档 refinement 被放在同一页里。

边界：本轮是 presentation-only redraw，不改算法、不调参数、不接默认 pipeline，不生成 execution/workspace/robot 文件。

# 2026-06-21 B-route visual conclusion freeze note

本轮不做新实验，只把最新一轮中文化后的三张 B-route 关键图的人工结论固定下来，避免后续线程反复改口。

- `hybrid_section_compare_cn.png` 冻结为 `main_candidate`，适合作为正文里的 B-route 代表图。
- `h1_lite_u5c71_kaishu_lishu_contrast_cn.png` 冻结为 `supplementary_candidate`，只作为“弱但存在的差异”证据。
- `h1_lite_u98ce_lishu_risk_contrast_cn.png` 冻结为 `limitation_or_risk_case`，用于说明复杂隶书字上的风险与局限性。

固定文档：

```text
experiments/llm_style_trajectory/docs/b_route_visual_conclusion_freeze_note.md
experiments/llm_style_trajectory/configs/b_route_visual_conclusion_freeze_note.json
experiments/llm_style_trajectory/outputs/paper_figures/b_route_visual_conclusion_freeze_index.md
```

边界：本轮只是人工结论固定，不新增算法、不调参数、不改默认 pipeline。

# 2026-06-23 A-route 大样本展示层补强

本轮回到 A-route，只做论文展示层补强，不新增算法、不调参数、不接默认 pipeline。新增固定展示字符集与展示包脚本：

```text
experiments/llm_style_trajectory/configs/a_route_showcase_chars.json
experiments/llm_style_trajectory/src/a_route_showcase_pack.py
experiments/llm_style_trajectory/tests/test_a_route_showcase_pack.py
```

输出目录：

```text
experiments/llm_style_trajectory/outputs/a_route_showcase_20260623_091212/
experiments/llm_style_trajectory/outputs/paper_figures/a_route_showcase_index.md
```

展示包覆盖三类证据：

- 基础 style 对比：kaishu / xingkai / lishu 的大样本 grid。
- modifier / behavior control：把 connection 重新表述为“跨笔过渡控制 / 跨笔连续性控制”，不再作为真实行楷风格迁移证据。
- execution layer：展示 width / pressure / connector / pen-up，使中心线之外的执行行为更容易目检。

关键图：

```text
a_route_style_overview_grid.png
a_route_modifier_control_overview.png
a_route_execution_display_grid.png
a_route_behavior_control_compare.png
a_route_smoothness_supplementary.png
```

叙事边界：connector / 连笔当前证明的是自然语言驱动的跨笔过渡控制和 execution 行为控制，不是真实行楷书法风格学习或风格迁移成功。
