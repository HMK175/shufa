# Sim-to-Real Brush Manipulation Using Behavior Cloning and Reinforcement Learning

- **发表信息**: arXiv preprint, 2023
- **相关度**: ★★★
- **方法**: Behavior Cloning (BC) + RL 实现仿真到真实的笔刷操作迁移
- **说明**: 此论文的 PDF 文件在 Zotero 存储中标题有误（实际内容为无关的数学论文），以下基于 arXiv 摘要分析
- **已知信息**:
  - 在仿真环境中训练 painting agent
  - 使用 BC 从人类演示中学习初始策略
  - 再用 RL 在仿真中微调
  - 迁移到真实机器人

- **与本课题的关系**:
  - BC+RL 的两阶段训练策略与本课题有相似之处
  - Sim2Real 是 RL 的常见难点，但本项目目前仅在二维仿真中做 RL
  - **建议**: 如果能获取到正确 PDF，值得详细阅读其 sim2real 迁移方案

- **状态**: ⚠ PDF 待修复
