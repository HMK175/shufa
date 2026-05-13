# RoDAL: Style Generation in Robot Calligraphy with Deep Adversarial Learning

- **发表信息**: Xiaoming Wang, Zhiguo Gong (澳门大学), Applied Intelligence 54, pp.7913-7923, 2024
- **相关度**: ★★★★
- **方法**: 双生成器 GAN 框架：Encoder-Decoder 风格生成器 + 机器人运动生成器
- **流程**:
  1. Generator A (Encoder-Decoder + skip connections)：输入楷体字 → 输出启功风格字
  2. 轨迹提取：从生成的风格字提取骨架轨迹
  3. Generator B (机器人)：按轨迹书写 → 摄像头捕获书写结果
  4. Discriminator：判别机器人写的字 vs 真实启功字帖
  5. 双生成器交替优化

- **主要贡献**:
  - 双生成器结构实现了 2D 图像生成 → 3D 机器人动作的桥接
  - 多项评价指标（Coverage Rate, SSIM, IoU, Turing Test）
  - 目标风格 SSIM 75.91%, Coverage 70.25%, IoU 80.68%

- **不足/局限**:
  - 依赖特定字体（启功体）的训练样本
  - 风格迁移后机器人写，误差累积问题
  - 缺乏对笔画顺序/书写规则的约束

- **与本课题的关系**:
  - 双生成器(图像→机器人)的架构和 SSIM/IoU 评价指标可参考
  - 轨迹提取部分与本课题骨架提取有交集
