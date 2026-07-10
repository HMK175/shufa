# AUBO i5 Command Adapter Paper Index

记录日期：2026-06-16

本页固定整理 AUBO i5 离线命令适配层的论文/阶段汇报素材。该层位于 CoppeliaSim 笔尖路径播放和真实机械臂控制之间，用于说明系统已经能够把末端目标位姿序列转换为面向 AUBO i5 SDK 的 dry-run command plan。

## 1. 源结果

源任务目录：

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

源输入：

```text
robot_target_poses.csv
```

固定整理文件：

| 文件 | 内容 |
|---|---|
| `aubo_i5_command_plan.csv` | 离线 AUBO i5 SDK 调用计划表 |
| `aubo_i5_safety_check.json` | 步长、速度、时间、四元数和边界检查 |
| `aubo_i5_command_plan.md` | dry-run 命令计划说明和 safety summary |
| `aubo_i5_command_adapter_index.md` | 本索引 |

## 2. Command Plan 摘要

| command_type | 数量 | 含义 |
|---|---:|---|
| `move_joint_approach` | 1 | 到第一个点上方的安全接近位姿，仅作为 future `inverse_kin + move_joint` hint |
| `move_line` | 275 | 沿 `robot_target_poses.csv` 中的末端目标位姿序列跟随 |
| `move_line_retract` | 1 | 结束后抬高到安全高度，仅作为 future `move_line` hint |

所有 command row 均设置 `dry_run_only=true`。当前没有求解 IK，没有连接真实 AUBO i5，也没有调用 SDK 的 `move_joint` 或 `move_line`。

## 3. Safety Check 摘要

| field | value |
|---|---:|
| `point_count` | 275 |
| `command_count` | 277 |
| `max_step_m` | 0.002488 |
| `max_speed_m_s` | 0.04 |
| `max_accel_m_s2_estimate` | 0.0 |
| `quaternion_normalized` | true |
| `time_monotonic` | true |
| `has_nan_or_inf` | false |
| `recommended_for_sdk_dry_run` | true |
| `warnings` | [] |

## 4. 论文可写结论

可写作：

> 在完成机器人纸面工作空间映射和重采样后，本文进一步将末端目标位姿序列转换为面向 AUBO i5 SDK 的离线命令计划。该计划包含安全接近、线性跟随和安全撤离三类命令，并对相邻位姿步长、速度、加速度估计、时间单调性和四元数归一化进行检查。样例轨迹满足 SDK dry-run 前置检查条件，说明当前轨迹表达已经具备进入机械臂运动接口适配的基础。

必须保留的边界：

> 当前阶段不进行逆运动学求解，不连接真实 AUBO i5，不导入或执行 `libpyauboi5`，不使用历史 IP，不发送任何真实机器人控制命令。真实机械臂实验前仍需现场确认机器人 IP、急停状态、工具 TCP、夹具、纸面坐标系、速度/加速度限制、可达性和安全边界。

## 5. 推荐放置位置

- 大论文第 6 章：仿真与机器人接口准备。
- 小节标题可写为：`AUBO i5 末端命令计划离线适配与安全检查`。
- 建议放在 CoppeliaSim 标准书写场景之后、真实机械臂实验之前。

