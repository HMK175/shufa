# Physically Motivated Model of a Painting Brush for Robotic Painting and Calligraphy

- **发表信息**: Artur Karimov et al. (圣彼得堡电子技术大学), Robotics 13, 94, 2024
- **相关度**: ★★
- **方法**: 物理驱动的笔刷接触面数学模型推导 + 参数标定
- **流程**:
  1. 推导笔刷接触面(contact patch)的位置和形状方程
  2. 分析笔刷运动的滞后效应(brush lag)：刷头位置落后于 TCP
  3. 提出参数标定方法将模型匹配到实际笔刷

- **主要贡献**:
  - 物理正确的笔刷柔顺性(compliance)模型
  - 笔刷滞后效应的数学描述
  - 参数标定流程

- **不足/局限**:
  - 纯粹物理建模，不含书写系统
  - 圆头笔刷假设，不完全适用中国毛笔
  - 没有实际的机器人书写验证

- **与本课题的关系**:
  - 弱相关：纯笔刷物理模型，可作为仿真环境的笔刷模块参考
  - 比 CCD-BSM 更底层但覆盖面更窄
