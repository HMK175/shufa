# Automatic Stroke Generation for Style-Oriented Robotic Chinese Calligraphy

- **发表信息**: Lin Gan et al. (厦门大学/Aberystwyth/Northumbria/Yuan Ze), Future Generation Computer Systems 119, pp.20-30, 2021
- **相关度**: ★★★
- **方法**: 字符拆分 + 笔画匹配 + GAN 风格学习
- **流程**:
  1. 汉字拆分为笔画（基于角点检测的字符拆解）
  2. 笔画生成模块 (GAN)：学习目标风格的笔画特征
  3. 生成任意汉字：将学习到的风格笔画按结构组合成新字
  4. 机器人书写

- **主要贡献**:
  - 仅需少量手写样本即可学习目标风格并生成任意汉字
  - 自动字符拆解不依赖字体数据库
  - 解决了冷僻字无法书写的问题

- **不足/局限**:
  - 笔画拆解精度受限（角点检测方法对行书/草书效果差）
  - GAN 生成的笔画拼接可能不自然
  - 未考虑笔画间过渡的连贯性

- **与本课题的关系**:
  - 笔画拆分思路可参考（但本课题面向的是骨架+RL，不依赖 GAN 风格生成）
  - 少量样本学习的策略有借鉴意义
