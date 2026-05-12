# 书法机器人轨迹生成项目

## 项目概述

针对书法机器人书写轨迹人工示教成本高、轨迹还原度不足的问题，提出一种结合图像骨架提取和强化学习局部优化的笔画轨迹生成方法。

**核心流程**：输入字形图像 → 图像预处理 → 骨架提取 → 初始轨迹生成 → 强化学习优化 → 机器人末端轨迹输出

**定位**：不做完整汉字生成，不做复杂大模型。只做"给定笔画/字形图像后，机器人如何写得更像"。面向工程实现的轻量化方案：骨架提取 + RL局部优化。适用于中文普刊、专硕毕业要求。

## 技术栈

- Python 3.8+, OpenCV, NumPy, Matplotlib, PyTorch (RL部分)
- 仿真环境：二维平面轨迹仿真，可映射到机械臂工作空间

## 项目结构

```
shufa/
├── README.md              # 项目说明
├── PROJECT_LOG.md         # 项目日志
├── TODO.md                # 待办事项
├── PAPER_OUTLINE.md       # 论文大纲
├── EXPERIMENT_RECORD.md   # 实验记录
├── METHOD_NOTES.md        # 方法笔记
├── ROBOT_TEST_PLAN.md     # 机器人测试计划
├── references/            # 参考文献和PDF
│   ├── downloads/         # 已下载PDF
│   └── import_to_zotero.py
└── code/                  # 代码
    ├── pipeline.py        # 主流程
    ├── skeleton.py        # 骨架提取
    ├── trajectory.py      # 轨迹生成
    ├── utils.py           # 工具函数
    └── gen_test_image.py  # 测试图像生成
```

## 当前进度

- [x] 已完成最小 pipeline：图片 → 二值化 → 骨架提取 → 轨迹 → 平滑 → CSV输出
- [ ] 强化学习轨迹优化模块（DDPG）待实现
- [ ] 对比实验待完成
- [ ] 论文正文待撰写

## Zotero 文献管理

- Zotero 数据目录：`D:\basic data\zotero`（非默认路径，通过 `extensions.zotero.dataDir` 配置）
- 书法机器人文献集合 collectionID = 5
- 所有 Zotero 操作使用 `D:\basic data\zotero\zotero.sqlite`
- 参考文献管理脚本：`references/import_to_zotero.py`

## 两机协作说明

此 CLAUDE.md 随 git 同步。在两台电脑上：
- Zotero 数据目录路径可能不同，需根据实际机器调整
- Python 环境需各自配置
- 其他项目文件结构保持一致即可
