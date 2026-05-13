# End-to-end Manipulator Calligraphy Planning via Variational Imitation Learning

- **发表信息**: Fangping Xie et al. (avatarin Inc.), 2023
- **相关度**: ★★
- **方法**: VAE + Bi-LSTM + MLP 的变分模仿学习，3D 轨迹(位置+笔尖旋转)
- **流程**:
  1. Encoder: 残差连接特征金字塔网络 → 隐空间 z
  2. Bi-LSTM 预测下一个隐状态
  3. Decoder (MLP): 输出 3D translation t + 4D quaternion rotation R + 图像 I
  4. 损失: KL散度 + MAE/MSE (位置/旋转/图像)

- **主要贡献**:
  - 3D 轨迹表示(含笔尖旋转)适用于日本书道复杂笔画
  - 变分模仿学习处理分布偏移(distribution shift)问题
  - 残差连接特征金字塔提取多尺度特征

- **不足/局限**:
  - 面向日本书道而非中国书法
  - 需要专家示教数据
  - 模仿学习固有的 compounding error 问题

- **与本课题的关系**:
  - 弱相关：方法偏模仿学习而非 RL 优化
  - 3D 轨迹+旋转的表示方式可参考（如果后续扩展到机械臂姿态控制）
