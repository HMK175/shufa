# AUBO i5 命令适配器 Dry-Run 说明

日期：2026-06-15

## 范围

该层把 `robot_target_poses.csv` 转换为离线 AUBO i5 command plan。它只是 dry-run adapter。

它不会：

- import 或执行 `libpyauboi5`；
- 连接真实 AUBO i5；
- 把历史 IP 或端口作为默认配置；
- 求逆运动学；
- 调用 `move_joint` 或 `move_line`；
- 发送任何真实机器人控制命令。

该输出用于说明：在未来确认机器人 IP、TCP、工具夹具、纸面坐标系、速度限制、可达性、急停和现场安全之后，SDK adapter 大致应该如何组织。

## 输入

默认输入：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

## 输出

在同一任务目录生成：

```text
aubo_i5_command_plan.csv
aubo_i5_safety_check.json
aubo_i5_command_plan.md
```

## 命令计划

`aubo_i5_command_plan.csv` 包含：

```text
command_id
command_type
pose_id
t_s
X_m
Y_m
Z_m
qw
qx
qy
qz
speed_m_s
accel_m_s2
pen_down
segment_type
dry_run_only
sdk_hint
notes
```

命令类型：

- `move_joint_approach`：未来到第一个目标上方的接近动作。当前只记录
  `future: inverse_kin + move_joint`，不求 IK。
- `move_line`：每个 target pose 对应一行 command-plan。抬笔段仍为
  `move_line`，但 `pen_down=0`。
- `move_line_retract`：未来从最后一个目标上方撤离的动作。

每一行都设置 `dry_run_only=true`。

## 安全检查

`aubo_i5_safety_check.json` 记录：

- `point_count`
- `command_count`
- `source_csv`
- `max_step_m`
- `max_speed_m_s`
- `max_accel_m_s2_estimate`
- `xy_range_m`
- `z_range_m`
- `quaternion_normalized`
- `time_monotonic`
- `has_nan_or_inf`
- `workspace_hint`
- `recommended_for_sdk_dry_run`
- `warnings`
- `scope`

默认阈值：

```text
max_step_m <= 0.015
max_speed_m_s <= 0.10
max_accel_m_s2_estimate <= 0.50
quaternion norm tolerance = 1e-6
```

workspace 检查刻意保持保守。它不是 AUBO i5 真实可达性、碰撞、奇异位形或关节限位检查。

## 当前样例结果

weak 行楷“山”样例：

```text
point_count = 275
command_count = 277
max_step_m = 0.002488
max_speed_m_s = 0.04
max_accel_m_s2_estimate = 0.0
recommended_for_sdk_dry_run = true
warnings = []
```

## 后续 SDK Bridge

历史平台资料在：

```text
AUBO_I5_PLATFORM_NOTES.md
```

其中提到的可能 SDK 调用包括：

- `inverse_kin`
- `move_joint`
- `move_line`
- `set_tool_kinematics_param`

这些都只是资料参考。任何真实 SDK 运行前，必须确认当前机器人 IP、控制器状态、急停、工具 TCP、笔夹具、纸面位姿、工作空间边界、速度和加速度限制，以及人员安全条件。
