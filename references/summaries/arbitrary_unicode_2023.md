# Robotic Writing of Arbitrary Unicode Characters Using Paintbrushes

- **发表信息**: David S. Zingrebe, Jörg M. Gülzow, Oliver Deussen (Univ. Konstanz), Robotics 12, 72, 2023
- **相关度**: ★★★
- **方法**: 两阶段流水线：字形笔画分割 + 笔刷模型轨迹生成
- **流程**:
  1. Stage 1 (Stroke Extraction): 从字体 glyph 中提取笔画 → 基于 Voronoi 中轴 + 宽度信息的笔画分割
  2. Stage 2 (Trajectory Generation): 笔刷模型(考虑笔刷压力→宽度, 笔刷滞后 lag)生成轨迹
  3. 自动标定笔刷滞后参数（通过画标定图案+摄像头记录）

- **主要贡献**:
  - 处理任意 Unicode 字符（不仅是中文）
  - 笔刷滞后(brush lag)的物理建模和自动标定
  - 不需要视觉反馈的开放环路控制

- **不足/局限**:
  - 笔画分割对复杂汉字可能不准确
  - 开环控制，无书写质量反馈
  - 笔刷模型假设为圆形刷头

- **与本课题的关系**:
  - 笔画分割用到 Voronoi 中轴（与骨架提取有共通之处）
  - 笔刷滞后建模可参考用于仿真环境
  - 但不涉及 RL，与本课题的核心优化路线无关
