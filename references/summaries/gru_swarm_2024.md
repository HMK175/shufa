# Solving Robotic Trajectory Sequential Writing via GRU + Swarm Optimization

- **发表信息**: Quanfeng Li et al. (厦门大学/Aberystwyth/Northumbria/Yuan Ze), IEEE Trans. Cybernetics, Vol.54, No.2, 2024
- **相关度**: ★★★★
- **方法**: VAE 特征提取 + GRU 轨迹生成 + Competitive Swarm Optimization 优化
- **流程**:
  1. VAE 预处理：提取样本图像的均值和协方差归一化
  2. 循环 GRU：输入 28×28 空白图像 + 高斯噪声 → 输出轨迹点 → 机器人写 → 摄像头捕获 → 下一 GRU 单元
  3. 评价系统：形状相似度 + 书写顺序 + 结构信息
  4. 竞争群优化算法训练 GRU 参数

- **主要贡献**:
  - 小数据集也能学习书写序列（仅用阿拉伯数字训练）
  - 同时评价形状、序列、结构三个维度
  - 生成结果具有多样性（通过高斯噪声采样）

- **不足/局限**:
  - 仅验证阿拉伯数字，未涉及汉字
  - GRU 循环步数与笔画长度绑定，灵活性有限
  - 依赖摄像头实时反馈，仿真/实物有差异

- **与本课题的关系**:
  - 评价系统(形状+序列+结构)的三维评价思路可借鉴
  - GRU 生成轨迹 vs 本课题骨架+轨迹的方案：各有优劣
  - 竞争群优化可替代 RL，但 RL 更灵活
