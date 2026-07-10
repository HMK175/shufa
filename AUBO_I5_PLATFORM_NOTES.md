# AUBO i5 机械臂平台资料记录

记录日期：2026-06-14

## 1. 资料来源

来源文件夹：

```text
D:\edge download\视觉抓取26.04.27
```

该文件夹包含师兄视觉抓取实验遗留资料，包括运动控制记录、AUBO SDK、Python 控制程序、相机/抓取相关代码和标定资料。

## 2. 机械臂型号判断

当前资料能够明确指向：

```text
AUBO i5 / 遨博 i5 协作机械臂
```

主要证据：

1. `遨博机器人运动控制实验记录.docx`
   - 文档中写明实验目标为：与 `AUBO i5` 机械臂实现通讯，并对其进行运动控制。
   - 文档中包含控制柜、示教器网络设置、机器人 IP 和电脑静态 IP 配置说明。

2. `SDK应用开发包/`
   - 包含 `Aubo_CPlusPlus_SDK_CHN.pdf`、`Aubo_C_SDK_CHN.pdf`、`SDK-Python_Manual_CHN_V1.0.pdf`。
   - 包含 `auboi5-sdk-for-windows-python3.7-x64-v1.5.2.zip`。
   - 解压目录中包含 `libpyauboi5.pyd`、`pyauboi51.dll` 等 AUBO i5 Python SDK 组件。

3. `视觉抓取程序/robotcontrol.py`
   - 使用 `import libpyauboi5`。
   - 定义 `Auboi5Robot` 类。
   - 封装了 `connect`、`move_joint`、`move_line`、`inverse_kin`、`set_tool_kinematics_param`、`set_tool_dynamics_param` 等接口。

4. `视觉抓取程序/arm_server_py37.py`
   - 使用 `Auboi5Robot` 初始化和连接机械臂。
   - 连接端口为 `8899`。
   - 保留过可连接 IP，例如 `192.168.94.130`。

5. `视觉抓取程序/real_grasp.py`
   - 使用 `Auboi5Robot` 和 `robot.connect(ip, port)`。
   - 保留过 IP：`192.168.174.129`。
   - 包含相机坐标系、末端坐标系、基座坐标系之间的转换矩阵。

## 3. 已发现的网络配置线索

文档和代码中出现过以下网络配置：

| 位置 | 信息 |
|---|---|
| `遨博机器人运动控制实验记录.docx` | 示教器/机器人 IP 设置为 `192.168.174.29` |
| `遨博机器人运动控制实验记录.docx` | 电脑设置同网段静态 IP，例如 `192.168.174.249` |
| `real_grasp.py` | `ip = '192.168.174.129'` |
| `arm_server_py37.py` | `ip = "192.168.94.130"` |
| AUBO SDK / 代码 | 默认通信端口 `8899` |

这些 IP 可能来自不同实验环境或虚拟机环境，后续实机连接前不能直接照抄，需要以现场示教器和控制柜网络设置为准。

## 4. 对当前书法机器人课题的影响

后续真实机械臂路线应优先围绕 AUBO i5，而不是默认使用 UR5、Panda、xArm 等通用模型。

建议平台表述：

```text
AUBO i5 collaborative robot / 遨博 i5 协作机械臂
```

当前 `experiments/llm_style_trajectory` 已完成的是：

```text
自然语言/风格规划
-> trajectory.csv
-> execution_trajectory.csv
-> robot_workspace_trajectory.csv
-> robot_workspace_trajectory_resampled.csv
-> CoppeliaSim standard pen-tip scene playback
-> robot_target_poses.csv
-> AUBO i5 dry-run command plan
-> AUBO i5 IK feasibility dry-run
```

下一阶段若进入真实机械臂或机械臂仿真，应优先补：

1. 在 CoppeliaSim 中加入简单机器人或末端执行器模型，先验证 base 坐标系、纸面位置和工具姿态定义。
2. 补充速度连续性、加速度和 jerk 检查，避免直接把可视化轨迹当作真实控制轨迹。
3. 进入真实 IK 前，仍需现场确认工具 TCP、纸面位姿、夹具和安全边界。
4. 后续 AUBO i5 的 IK / 运动接口适配可围绕：
   - `inverse_kin`
   - `move_joint`
   - `move_line`
   - 工具运动学参数设置
   - 末端速度/加速度限制
5. 安全检查仍必须包含：
   - 工作空间是否可达
   - 相邻位姿距离
   - 速度/加速度限制
   - 抬笔高度
   - 与纸面/夹具的安全距离

## 5. 近期建议

短期不建议直接发送轨迹到真实 AUBO i5。当前已经完成：

```text
robot_workspace_trajectory_resampled.csv
-> robot_target_poses.csv
-> AUBO i5 IK / command adapter dry-run
-> AUBO i5 IK feasibility dry-run
```

更稳妥的下一步是先做 CoppeliaSim 机器人/末端执行器模型的坐标系校准，或继续补充速度、加速度、jerk 等离线检查，不立即控制实机。

论文中可以把当前阶段表述为：

> 在仿真阶段，本文已将二维书写轨迹映射到标准纸面工作空间，并在 CoppeliaSim 中完成笔尖路径播放验证。结合实验室已有 AUBO i5 协作机械臂资料，后续可将重采样后的工作空间轨迹进一步转换为 AUBO i5 末端位姿序列，通过逆运动学和运动控制接口实现实体机器人书写验证。

## 6. 注意事项

- 师兄资料中包含真实控制代码，但不能在未确认现场设备、网络、安全状态、急停、夹具和工具参数前直接运行。
- 历史 IP 地址仅作线索，不作为当前实验默认配置。
- 当前书法项目中的 CoppeliaSim standard scene 仍是 pen-tip/sphere playback，不包含 AUBO i5 机械臂模型、真实 IK、真实动力学或控制器。IK feasibility dry-run 只是进入真实 IK 前的数据质量和几何范围前检查。
