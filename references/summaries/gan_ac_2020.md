# Integration of an Actor-Critic Model and GAN for a Chinese Calligraphy Robot

- **发表信息**: Ruiqi Wu et al. (厦门大学 / Aberystwyth / Northumbria / Yuan Ze), Neurocomputing 388, pp.12-23, 2020
- **相关度**: ★★★★★ (直接相关)
- **方法**: GAN 预训练评估函数 + Actor-Critic (AC) 深度强化学习
- **流程**:
  1. GAN 模块预训练：Generator 从随机噪声生成笔画图像，Discriminator 判断真假
  2. AC 模块：Actor 网络输出关节动作 → 机器人写笔画 → 摄像头捕获 → Discriminator 作为评价函数打分 → Critic 网络估计 Q 值 → 策略梯度更新 Actor
  3. 机器人模块：逆运动学将关节值转为轨迹执行

- **主要贡献**:
  - GAN 的 Discriminator 复用为 RL 的评价函数，解决了书法美学难以手工设计 reward 的问题
  - AC 模型不需要最优动作样本，通过探索机制自学
  - 闭环系统：写 → 看 → 评 → 改

- **不足/局限**:
  - 仅处理基本笔画（横竖撇捺），未扩展到完整汉字
  - 训练需大量迭代
  - 风格多样性受限于训练样本

- **与本课题的关系**:
  - **高度直接相关**：本课题用 DDPG，此文用 AC——DDPG 本质上是 AC 的确定性版本 + experience replay。可参考其 GAN-as-evaluator 的思路来设计 RL reward 函数
  - GAN+RL 的闭环框架可以借鉴到本课题的 RL 优化模块
