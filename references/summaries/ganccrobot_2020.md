# GANCCRobot: Generative Adversarial Nets Based Chinese Calligraphy Robot

- **发表信息**: Ruiqi Wu et al. (厦门大学/Aberystwyth/Northumbria/Yuan Ze), Information Sciences 516, pp.474-490, 2020
- **相关度**: ★★
- **方法**: 条件 GAN (cGAN) + 隐编码控制风格多样性
- **流程**:
  1. 条件 GAN：输入笔画类型标签 + 隐编码(latent code) → 生成笔画图像
  2. 隐编码控制风格多样性（同一笔画可生成多种风格）
  3. 图像处理二值化 → 轨迹提取 → 机器人书写

- **主要贡献**:
  - 用 latent code 实现风格多样化生成
  - 条件信息(笔画类型)控制生成内容
  - 不需要人工设计评价函数

- **不足/局限**:
  - 仅生成基本笔画，未扩展到完整汉字
  - GAN 生成的笔画可能有伪影
  - 从生成图像提取轨迹有信息损失

- **与本课题的关系**:
  - 弱相关：GANCCRobot 侧重于"生成多样笔画"，而本课题侧重"写得更像"
  - latent code 控制风格的想法可参考，但本课题用 RL 实现更好
- **与本课题同一作者系列**：Wu Ruiqi 也是 actor-critic+GAN 论文(gan_ac_2020.md)的作者，这是其前作
