# 文献总结索引

## ★★★★★ 直接相关（优先参考）
| 文件 | 论文 | 核心方法 | 与本课题关联 |
|------|------|----------|-------------|
| [gan_ac_2020](gan_ac_2020.md) | Integration of Actor-Critic + GAN (Wu 2020) | GAN评价 + AC强化学习 | **GAN-as-evaluator 思路可直接用于RL reward函数** |
| [ccdbsm_2025](ccdbsm_2025.md) | CCD-BSM Trajectory Control (Guo 2025) | 笔刷物理模型 + 三阶段轨迹控制 | **起笔/行笔/收笔三段式框架可引入轨迹生成** |

## ★★★★ 高度相关
| 文件 | 论文 | 核心方法 | 与本课题关联 |
|------|------|----------|-------------|
| [spsoc_2023](spsoc_2023.md) | SPSOC (Guo 2023) | 伪谱最优控制 + 分段轨迹优化 | 分段优化思路，传统方法可作 RL 对比基线 |
| [rodal_2024](rodal_2024.md) | RoDAL (Wang 2024) | 双生成器GAN + 风格+机器人 | SSIM/IoU评价指标，轨迹提取 |
| [gru_swarm_2024](gru_swarm_2024.md) | GRU + Swarm (Li 2024) | GRU轨迹生成 + 竞争群优化 | 三维评价体系(形状+序列+结构) |
| [stroke_extraction_trajectory_planning_icira2024](stroke_extraction_trajectory_planning_icira2024.md) | Stroke Extraction (Wu ICIRA2024) ✅已总结 | 角点分割 + CNN笔画识别 + 骨架路径规划 | pipeline方向一致，规则式方法可作对比 |
| [callirewrite_2024](callirewrite_2024.md) | CalliRewrite (Luo 2024) ✅已总结 | CNN-LSTM笔画分解 + SAC RL | **最相关：SAC RL轨迹优化，与本课题DDPG直接对比** |

## ★★★ 中等相关
| 文件 | 论文 | 核心方法 |
|------|------|----------|
| [style_oriented_stroke_2021](style_oriented_stroke_2021.md) | Stroke Generation (Gan 2021) | 字符拆分 + GAN风格笔画 |
| [bbsmg_2024](bbsmg_2024.md) | B-BSMG (Guo 2024) | Bézier笔刷模型 + 神经渲染 |
| [arbitrary_unicode_2023](arbitrary_unicode_2023.md) | Arbitrary Unicode (Zingrebe 2023) | Voronoi笔画分割 + 笔刷模型 |
| [imitation_learning_fgmm_2024](imitation_learning_fgmm_2024.md) | Imitation Learning (Xu 2024) | FGMM + DMP模仿学习 |
| [char_decomp_gesture_2019](char_decomp_gesture_2019.md) | Character Decomp (Chao 2019) | Harris角点拆字 + 手势示教 |
| [sim2real_brush_2023](sim2real_brush_2023.md) | Sim2Real Brush (2023) ⚠PDF缺失 | BC+RL sim2real |

## ★★ 弱相关 / 仅部分参考
| 文件 | 论文 | 可参考内容 |
|------|------|----------|
| [style_transfer_2020](style_transfer_2020.md) | Style Transfer (Liang 2020) | 相似度评价指标 |
| [ganccrobot_2020](ganccrobot_2020.md) | GANCCRobot (Wu 2020) | latent code风格控制 |
| [beautification_2019](beautification_2019.md) | Beautification (Zhang 2019) | SCV形状描述向量 |
| [brush_physics_2024](brush_physics_2024.md) | Brush Physics (Karimov 2024) | 笔刷物理模型 |
| [variational_imitation_2023](variational_imitation_2023.md) | VI Imitation (Xie 2023) | 3D轨迹+旋转表示 |
| [internal_model_control_2024](internal_model_control_2024.md) | IMC Calligraphy (2024) ⚠无PDF | IMC控制框架 |

## 无需总结
- `Identification Method of Interturn Short Circuit Fault...` (710) — 配电变压器故障检测，无关
- `Formally Integrable Structures II` (698) — 纯数学论文，无关
- 简体中文论文 3 篇 — 暂不总结
