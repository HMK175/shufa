# 外部书法数据集单图 OCR 字符标签恢复设计

## 状态

已完成方案确认，等待用户审阅后实施。

## 目标

为两份缺少字符真值的本地书法图像数据建立可追溯的字符标签清单，使图像能够按**字符本身**而非原始文件编号与内容字体图像连接，构成 FontDiffuser 类目标字生成实验的候选样本。

本设计只恢复标签和输出审计结果，不训练模型、不改变旧路线代码，也不改变数据许可结论。

## 数据范围

### ChineseStyle

- 本地目录：`D:\edge download\隶书和行楷\ChineseStyle`
- 风格：`lishu`（隶书）、`xingkai`（行楷）
- 每种风格共 6,763 张、原始分辨率 256×256。
- 两种风格的同名编号不是同一字符的配对依据；编号仅用于回溯原图。

### 20 书法家数据的首批子集

本地目录：`D:\edge download\Chinese Calligraphy Styles by Calligraphers`。

首批只处理 8 位代表性书法家，其余 12 位保留给后续扩展或消融实验：

| 目录标签 | 书法家 | 覆盖的主要作用 |
| --- | --- | --- |
| `wxz` | 王羲之 | 行书代表 |
| `yzq` | 颜真卿 | 楷书代表 |
| `lgq` | 柳公权 | 楷书代表 |
| `oyx` | 欧阳询 | 楷书代表 |
| `mf` | 米芾 | 行书代表 |
| `sgt` | 孙过庭 | 草书代表 |
| `yyr` | 于右任 | 草书代表 |
| `shz` | 宋徽宗 | 瘦金体 / 特殊结构代表 |

该数据图像为 64×64。书法家目录是风格标签；不同书法家间、同一书法家 train/test 间的同编号均不产生字符对应关系。

## 标签恢复流程

```text
原始单字图像
-> 数据集适配器（提取数据集、风格、原始 split、文件名、原始编号）
-> 本地 OCR 单图预测
-> 临时标签清单
-> 异常检测与人工复核 / 更正
-> 最终字符标签清单
-> 按 (style_id, character) 与内容字体图像连接
```

OCR 在本机运行。每张图独立预测，绝不使用跨目录、跨风格或跨书法家的编号一致性规则。

## 清单字段与复核状态

每个候选标签至少保存：

- `dataset_id`：数据来源标识；
- `style_id`、`style_display_name`：书体或书法家风格；
- `source_split`：原始 `train` / `test`；
- `raw_filename`、`raw_index`、`image_path`：可回溯原图；
- `ocr_text`、`ocr_score`：OCR 原始输出；
- `manual_character`：人工修正值，未修正时为空；
- `character`：最终使用值，优先采用人工修正；
- `review_state`：`provisional`、`required_review`、`sample_checked`、`manual_override`、`rejected`；
- `flags`：非单汉字、同风格字符重复、读取失败等原因。

低置信度用于排列复核优先级，不会单独造成删除。非单个汉字、同一风格中预测字符重复、读取失败的记录必须进入复核队列。

## 人工复核标准

1. 全量图像均生成 OCR 临时标签。
2. 每种风格随机抽查 200 张；不足 200 张时全查。首批共 10 种风格，计划抽查 2,000 张。
3. 所有必查异常均需人工确认、修正或拒绝。
4. 人工更正写入独立 overrides 清单，保留 OCR 原值，禁止直接覆盖原始预测。

## 配对与训练样本边界

内容字体为某一字符 `c` 渲染的普通字体图像 `S(c)`；目标图是经审计后具有相同字符标签的风格图像 `T(style_id, c)`。

只有 `S(c)` 与 `T(style_id, c)` 具有相同最终 `character` 时，才能形成训练候选样本。原始编号不会进入配对条件。

同一风格内若存在多个原图被修正为同一字符，必须进入冲突复核；首版数据集每个 `(style_id, character)` 只保留一张人工确认的目标图，其他图保留在审计清单中，不自动加入训练。

原始 `train` / `test` 划分默认保留；不会为追求字符一致性而跨原始划分调换图像。

## 输出与验证

受 Git 忽略的本地数据输出：

```text
experiments/target_glyph_generation/data/external_ocr_labels/
  chinese_style/
  calligrapher8/
experiments/target_glyph_generation/outputs/external_dataset_audit/
  chinese_style_single_image_ocr/
  calligrapher8_single_image_ocr/
```

每份输出包含完整 CSV、异常队列 CSV、人工抽查页、人工更正模板和 JSON 汇总。验证必须确认：

- 原图数量与发现数量一致；
- 每个原始图仅出现一次；
- 已接受记录均为单个 CJK 字符；
- 每个风格的重复字符都被解决或标记拒绝；
- 每个风格有 200 条抽查记录（不足 200 时为全量）；
- 汇总中记录 OCR 模型名称、阈值、数据集哈希与人工更正数量。

## 非目标

- 不把 OCR 推测描述为数据集原始官方真值；论文中须说明其为“本地 OCR 生成并经抽样人工复核的标签”。
- 不处理剩余 12 位书法家，不将 Calli-Tongji 混入本轮标签恢复。
- 不实施模型训练、指标评测或真实机器人控制。
