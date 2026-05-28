# 导师汇报 PPT 页面大纲

文件：`presentation/advisor_update_nextstroke.pptx`

本 PPT 是 2-3 页临时导师沟通材料，目标是说明“为什么换路线、现在路线是什么、已有初步证据和下一步怎么做”。不是答辩 PPT，也不是完整论文汇报。

## 第 1 页：课题问题与前期瓶颈

### 主要内容

- 课题目标：从字形图像生成机器人书写轨迹，降低人工示教成本。
- 原路线：真实/字体图像 -> 二值化 -> 骨架提取 -> 笔画拆分 -> 轨迹生成。
- 前期瓶颈：
  - 真实图像骨架在交点处容易扭曲。
  - 闭合结构和复杂字形拆分不稳定。
  - 继续靠规则调参，泛化提升有限。
- 阶段判断：前端笔画分割需要从“纯规则拆骨架”调整为“数据驱动 + 结构先验”。
- 边界表述：不宣称解决任意书法图像识别，当前面向结构清晰楷体/规范字体或近似规范书写图像。

### 使用图片

- `code/output/eval_tune_zhong.png`

### 讲稿提示

这页先讲清楚换路线不是推翻原课题，而是前端拆分方式遇到瓶颈。骨架和规则路线在简单字上能跑通，但在交点、闭合结构和复杂字上不稳定；后续机器人轨迹优化依赖前端笔画是否合理，所以需要先把逐笔 mask 做稳。

## 第 2 页：当前改进方案

### 主要内容

- 数据来源：Make Me a Hanzi，包含字形、笔顺、每笔路径。
- 构建数据集：完整字图、每笔 mask、每笔 median、笔顺信息。
- 模型形式：next-stroke/current-stroke segmentation。
- 输入：完整字图 + 已写笔画 mask + 当前步序信息。
- 输出：当前第 k 笔 mask。
- 核心变化：从固定 13 通道稀疏预测，改成逐笔二分类。
- 数据规模：106 个字扩展为 595 个逐笔样本。
- 定位：raw median 用作监督标签和评价基准，不直接当最终机器人轨迹。

### 使用图片

- `code/stroke_seg_dataset/preview/u4e2d_preview.png`

### 讲稿提示

这页强调新路线绕开的是“真实图像骨架拆分”这个最不稳定的前端，不是绕开 CNN 工作量。Make Me a Hanzi 的结构化笔画数据可以生成完整字图和逐笔监督标签，让模型学习“下一笔应该在哪里”，更接近真实书写过程。

## 第 3 页：初步结果与下一步

### 主要内容

- fixed 13-channel baseline test Dice 约 0.2295。
- next-stroke teacher-forcing test Dice 约 0.6173。
- autoregressive rollout Dice 约 0.3299。
- 结论：next-stroke 路线有效，但真实逐步预测时存在误差累积。
- 下一步：
  - previous-mask noise / scheduled sampling 提升 rollout 稳定性。
  - mask 转 skeleton/median，再生成轨迹 CSV。
  - 少量真实/近似真实字体外部测试，验证适用边界。

### 使用图片

- `code/output/stroke_next_predictions_full/u4e5f/sequence_preview.png`
- `code/output/stroke_next_rollout/u4e5f/rollout_preview.png`

### 讲稿提示

这页形成闭环：固定 13 通道 baseline 比较低，说明直接一次性预测所有笔画不稳；next-stroke 在 teacher-forcing 下明显提升，说明方向有希望；但 rollout 下降说明用预测 mask 继续预测会积累误差，下一步训练要模拟这个误差来源。

## 数值来源

- 106 个字、595 个逐笔样本：`code/stroke_seg_dataset/manifest.csv`
- next-stroke teacher-forcing 0.6173：`code/output/stroke_next_predictions_full/summary.csv`
- autoregressive rollout 0.3299：`code/output/stroke_next_rollout/rollout_summary.csv`
- fixed 13-channel baseline 0.2295：`code/output/stroke_seg_debug/val_metrics_noaug40.csv`

