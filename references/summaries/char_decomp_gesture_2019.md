# Use of Automatic Chinese Character Decomposition and Human Gestures for Calligraphy Robots

- **发表信息**: Fei Chao et al. (厦门大学/Yuan Ze/Northumbria/Essex), IEEE Trans. Human-Machine Systems, Vol.49, No.1, 2019
- **相关度**: ★★★
- **方法**: Harris 角点检测拆字 + 人手势示教 → 笔画轨迹匹配
- **流程**:
  1. Harris 角点检测 → 字符自动分解为笔画
  2. 人演示手势 → 学习笔画书写轨迹
  3. 笔画分类匹配：拆出的笔画 ↔ 已学习的轨迹
  4. 机器人按笔画轨迹书写

- **主要贡献**:
  - 不需要字体数据库，直接从课本扫描字符即可
  - 手势示教降低机器人编程复杂度
  - 角点检测拆字适用于规范楷体

- **不足/局限**:
  - 仅适用规范楷体，行书/草书拆解效果差
  - 手势示教仍有较大人工投入
  - 笔画匹配可能出错

- **与本课题的关系**:
  - 字符拆分的角点检测方法可作为图像预处理的技术储备
  - 但其"人示教轨迹"的思路与本课题"自动生成轨迹"方向相反
