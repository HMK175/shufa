# P1-extended Phase 1 图像数据集设计

## 目标

将 P1-extended 的外部书法字图与 8 个开源字体渲染结果整理为 FontDiffuser Phase 1 可直接读取的目录。该阶段只训练内容字泛化与已见风格生成；不开启 SCR，因此不要求所有风格共享完整字符集合。

## 输入与覆盖策略

- 外部字图：P1-extended 划分中的 39,741 张，包含 1,087 条黄庭坚 `mask_isolated_right_border_line` 动作。
- 开源字体：8 种字体按覆盖审计进行稀疏渲染，共 55,853 张，而非原计划的 59,192 张。
- 内容图：7,399 个字符由 Noto Sans SC Regular 渲染，按既有字符 split 进入 `train`、`validation`、`test`。
- 繁体、简体继续按 Unicode 码位精确区分。

## 输出布局

```text
data/fontdiffuser_p1_extended/
  train|validation|test/
    ContentImage/<字符>.jpg
    TargetImage/<风格ID>/<风格ID>+<字符>.jpg
  manifests/samples.csv
  manifests/styles.csv
  manifests/dataset_summary.json
```

对外部字图，先执行清单指定的遮蔽动作，再归一化到 256×256 灰度画布并保存 JPEG。原始 JPEG 始终不改写。对开源字体，只渲染覆盖审计确认存在的字符。所有风格在每一个字符集合内可出现；每种风格至少应有两张训练目标图，以满足 Phase 1 随机风格参考图采样。

## 验收与人工复核

构建后核验目标图数量、内容图数量、文件存在性、样本清单与字符 split 一致性。对黄庭坚遮蔽后的样本生成 120 张前后对照审计图，由用户人工确认黑线被去除且正常笔画未受影响。Phase 1 loader smoke test 仅使用 `scr=false`；SCR/Phase 2 留到共享字符子集准备完成后。
