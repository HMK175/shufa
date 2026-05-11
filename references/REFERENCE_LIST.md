# 精选参考文献列表（2023-2025）

论文方向：书法机器人轨迹生成、图像骨架提取、强化学习优化

---

## 1. 核心直接相关（书法机器人 + 笔画提取 + 轨迹规划）

### [1] Wu Y, Feng J, Chen W, Guan Y. "Application of Stroke Extraction and Trajectory Planning in Robotic Calligraphy"
- **来源**: ICIRA 2024, Springer LNCS Vol. 15202, pp. 308-320, 2025
- **DOI**: 10.1007/978-981-96-0774-7_23
- **核心方法**: CNN字符分割 + 笔画识别 → 骨架化 → 动态路径规划生成轨迹点序列
- **匹配度**: ★★★★★ 直接匹配骨架提取+轨迹规划

### [2] Luo Y, Wu Z, Lian Z. "CalliRewrite: Recovering Handwriting Behaviors from Calligraphy Images without Supervision"
- **来源**: IEEE ICRA 2024, pp. 8671-8678
- **arXiv**: 2405.15776
- **核心方法**: 无监督CNN-LSTM image-to-sequence模型分解笔画 + SAC强化学习微调笔刷轨迹
- **匹配度**: ★★★★★ RL优化轨迹，无监督骨架分解

### [3] Guo D, Yan G. "B-BSMG: Bézier Brush Stroke Model-Based Generator for Robotic Chinese Calligraphy"
- **来源**: International Journal of Computational Intelligence Systems, Vol. 17, Article 104, 2024
- **DOI**: 10.1007/s44196-024-00499-4
- **核心方法**: Bézier曲线笔画模型 + 神经网络生成器，将机器人控制参数(h,α,β)映射为笔画图像
- **匹配度**: ★★★★ 笔画模型与轨迹生成

### [4] Guo D, Min H, Yan G. "SPSOC: Staged Pseudo-Spectral Optimal Control Optimization Model for Robotic Chinese Calligraphy"
- **来源**: ICIRA 2023, Springer LNCS Vol. 14270, pp. 416-428
- **DOI**: 10.1007/978-981-99-6492-5_36
- **核心方法**: 伪谱最优控制轨迹优化 + 三阶段书写模型(qibi-xingbi-shoubi)
- **匹配度**: ★★★★ 轨迹优化 + 骨架拟合

### [5] Guo D, Fang W, Yang W. "Brush Stroke-Based Writing Trajectory Control Model for Robotic Chinese Calligraphy"
- **来源**: Electronics (MDPI), Vol. 14, No. 15, Article 3000, 2025
- **DOI**: 10.3390/electronics14153000
- **核心方法**: CCD-BSM复合曲线膨胀笔刷模型，分解起笔/行笔/收笔阶段，Cosine Similarity 99.54%
- **匹配度**: ★★★★ 精细轨迹控制

---

## 2. 强化学习/深度学习书法机器人

### [6] Li Q, Guo Z, Chao F, et al. "Solving Robotic Trajectory Sequential Writing Problem via Learning Character's Structural and Sequential Information"
- **来源**: IEEE Transactions on Cybernetics, Vol. 54, No. 2, pp. 1096-1108, 2024
- **DOI**: 10.1109/TCYB.2022.3194700
- **核心方法**: GRU网络学习书写序列 + 群优化算法调参，从有限数据生成多样书写轨迹
- **匹配度**: ★★★★★ 轨迹序列生成 + 机器人书写

### [7] Wu R, Chao F, Zhou C, et al. "Internal Model Control Structure Inspired Robotic Calligraphy System"
- **来源**: IEEE Transactions on Industrial Informatics, Vol. 20, No. 2, pp. 2600-2610, 2024
- **DOI**: 10.1109/TII.2023.3292972
- **核心方法**: 视觉-运动网络 + 运动-视觉网络(IMC-inspired)，图像输入→机器人动作输出
- **匹配度**: ★★★★ 图像到轨迹的端到端方法

### [8] Xu W, Li X, Li Q, Yang C. "An Image-Based Imitation Learning Framework for Robotic Writing Tasks"
- **来源**: IEEE M2VIP 2024, October 2024
- **DOI**: 10.1109/M2VIP62491.2024.10746145
- **核心方法**: GMM + DMP模仿学习，将静态书法图像转化为动态笔画轨迹
- **匹配度**: ★★★★ 模仿学习轨迹生成

---

## 3. 骨架提取与轨迹生成方法

### [9] Zingrebe D S, Gülzow J M, Deussen O. "Robotic Writing of Arbitrary Unicode Characters Using Paintbrushes"
- **来源**: Robotics (MDPI), Vol. 12, No. 3, Article 72, 2023
- **DOI**: 10.3390/robotics12030072
- **核心方法**: Voronoi Medial Axis (VMA)骨架提取 + 贪心笔画提取 + 笔刷滞后补偿
- **匹配度**: ★★★★★ 骨架提取+轨迹生成，非常直接相关

### [10] Karimov A, Strelnikov M, Mazin S, et al. "Physically Motivated Model of a Painting Brush for Robotic Painting and Calligraphy"
- **来源**: Robotics (MDPI), Vol. 13, No. 6, Article 94, 2024
- **DOI**: 10.3390/robotics13060094
- **核心方法**: 物理笔刷柔顺性模型 + 笔刷滞后建模 + 标定方法
- **匹配度**: ★★★ 笔刷动力学模型补充

---

## 4. 模仿学习与端到端方法

### [11] Xie F, Le Meur P, Fernando C. "End-to-end Manipulator Calligraphy Planning via Variational Imitation Learning"
- **来源**: arXiv:2304.02801, 2023
- **核心方法**: VAE + BiLSTM + MLP，3D轨迹表示（含笔尖旋转），从专家演示中模仿学习
- **匹配度**: ★★★★ 端到端轨迹规划

### [12] Jia B, Manocha D. "Sim-to-Real Brush Manipulation Using Behavior Cloning and Reinforcement Learning"
- **来源**: arXiv:2309, 2023
- **核心方法**: 行为克隆 + RL训练绘画智能体，从仿真到真实机械臂的笔刷操控迁移
- **匹配度**: ★★★★ Sim-to-Real + RL笔刷操控

---

## 5. 奠基性GAN文献（对话中已分析）

### [13] Wu R, Chao F, et al. "GANCCRobot: Generative Adversarial Nets Based Chinese Calligraphy Robot"
- **来源**: IEEE ICRA 2018 (或相关会议)
- **核心方法**: GAN + Policy Gradient，Generator输出机器人动作轨迹点
- **匹配度**: ★★★★★ 直接奠基文献

### [14] Wu R, Chao F, et al. "Integration of an Actor-Critic Model and Generative Adversarial Networks for a Chinese Calligraphy Robot"
- **来源**: IEEE ROBIO 2019
- **核心方法**: GAN预训练 + Actor-Critic (DDPG), Discriminator作为reward function
- **匹配度**: ★★★★★ 直接奠基文献

---

## 检索关键词总结

**中文**：书法机器人 轨迹规划 | 书法机器人 强化学习 | 书写机器人 笔画轨迹 | 汉字书写机器人 骨架提取 | 书法机器人 DDPG | 机械臂 书写 轨迹优化

**英文**：robotic calligraphy trajectory planning | Chinese calligraphy robot reinforcement learning | robotic handwriting stroke trajectory | skeleton extraction robot writing | DDPG robotic calligraphy
