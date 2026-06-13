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

## 8. 下一步建议

短期不建议继续增加 modifier 种类。更优先的是：

1. 将三类 ablation 结果整理成论文图表。
2. 用 DeepSeek API planner 跑一组同样的 modifier tasks，验证 API 与 mock 输出是否一致。
3. 后续图表和论文正文优先引用 `batch_20260613_154131` 及 `outputs/paper_figures/` 中的修复后固定图。
4. 给 `mean_turning`、`total_turning_angle`、`max_turning_angle` 写清楚定义，避免评价指标解释含糊。
5. 在 CoppeliaSim 中加入简单机器人或末端执行器模型，先做无 IK 的坐标系/纸面位置校准，再决定是否进入机械臂 IK。
6. 进一步补充速度连续性、加速度/jerk 约束。
7. 若条件允许，选择 1 到 2 个字导出 CSV 到机器人/绘图设备做实写验证。
