# CalliRewrite: Recovering Handwriting Behaviors from Calligraphy Images without Supervision

- **发表信息**: Yuxuan Luo, Zekun Wu, Zhouhui Lian (北京大学王选计算机研究所), 2024
- **方法**: 无监督 Coarse-to-Fine：CNN-LSTM 笔画分解 + SAC (Soft Actor-Critic) 强化学习轨迹精细控制
- **流程**:
  1. **粗阶段 (Coarse)**：输入字形图像 → CNN-LSTM backbone → 逐时间步推理二次 Bézier 笔画参数 Bt=(p, x0, y0, x1, y1, x2, y2, w0, w1) → 可微分裁剪-粘贴渲染 → 无监督损失训练
     - 感知损失 (VGG-16, relu1_2/2_2/3_3/5_1)
     - 正则化损失 (惩罚提笔动作)
     - 平滑损失 (余弦相似度保证笔画连续性)
     - 角度损失 (约束笔画方向)
     - 渐进式训练策略 (先训练前N步再增加)
  2. **精阶段 (Fine)**：粗笔画序列 → 离散化为 {Pi} → SAC RL 在约束区域内探索 → 9维状态空间 (h, r, l, θ, ρ, δx, δy, vx, vy) → 动作偏移 (δx, δy) 或加角度 θ
     - 自适应形状奖励 (shape reward 权重随进度递减，IoU 权重递增)
     - Plug-and-play 工具模型 (毛笔/硬笔/马克笔，各自几何与动力学参数)
  3. 输出精细控制点序列 → Dobot Magician 机械臂执行

- **主要贡献**:
  - **无监督笔画分解**：不依赖标注，仅从图像自学习笔画顺序和分割，在 SNR 和 Chamfer Distance 上超越 LTP/GVS 等无监督方法
  - **RL 轨迹精细控制**：SAC + 约束探索 + 自适应奖励设计，实现不同工具的灵巧控制
  - **跨域泛化**：在中文各体（甲骨文/篆/隶/楷/行/草）、英文花体、古埃及象形文字、泰米尔文上均能复现
  - **低资源训练**：仅需 1000 张图像即可达到最优效果
  - 代码开源: https://luoprojectpage.github.io/callirewrite/

- **不足/局限**:
  - 存在笔画分割错误和误差累积导致的失败案例
  - 无 sim2real 自适应，仿真到实体有轻微失真
  - 仅处理单字，未涉及多字篇章布局
  - 无监督分割在处理部分典型字体时仍不够完美

- **与本课题的关系**:
  - **高度相关**：本课题采用 DDPG 做 RL 轨迹优化，CalliRewrite 使用 SAC，可对比两种 RL 算法在书法轨迹任务上的效果
  - 其无监督笔画分解的 Bézier 参数化思路可借鉴，但本课题用的是骨架提取路线，各有优劣
  - "Plug-and-play 工具模型"的概念可引入本课题，简化仿真环境搭建
  - 自适应奖励设计（从 shape 过渡到 IoU）是很好的参考
