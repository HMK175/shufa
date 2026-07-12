# 目标字图像生成实验

本目录对应论文第 3 章的独立数据准备实验：给定规范内容字与风格参考字，为 FontDiffuser 类目标字图像生成模型构建可复现、可审计的数据集。

## 边界

- 仅使用许可证明确为 `OFL-1.1`、`Apache-2.0` 或另有书面训练许可的字体；不得放入商业字体或许可证不清楚的字体。
- 本目录只处理目标字图像数据，不生成笔画轨迹、机器人控制命令或真实机械臂指令。
- `data/` 保存字体文件、渲染图像和构建清单，`outputs/` 保存审计图；二者均被 Git 忽略。
- 不提交模型权重、渲染图片、字体大文件或本机绝对路径。

## 预期数据布局

```text
data/fontdiffuser_open_dataset/
  fonts/
  rendered/ContentImage/<字符>.png
  rendered/TargetImage/<字体ID>/<字体ID>+<字符>.png
  manifests/
outputs/dataset_audit/
```

所有字体在进入构建流程前均须通过许可证、文件哈希和字符覆盖率审计；完整构建结束后必须人工查看审计网格，再决定是否进行模型训练。
