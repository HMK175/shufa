# P1 风格池整合设计

## 目标

把已完成 OCR 审计、抽样人工复核和许可核对的来源登记为一个可追溯的 P1 风格池，供后续 FontDiffuser Phase 1 数据构建使用；不在本步骤复制图像、渲染内容字图或启动训练。

## 分层

- **P1-core（17 种）**：9 位书法家风格（柳公权、颜真卿、黄庭坚、管峻、文徵明、弘一、八大山人、赵孟頫、褚遂良）与 8 种许可明确的开源字体。
- **P1-extended（2 种）**：ChineseStyle 的隶书、行楷。两者已完成全量人工标签复核；用户已确认纳入论文实验。其原始训练许可仍标记为 `unverified`，并以 `user_confirmed_unverified_source` 记录该决定。
- **排除**：毛泽东及其他尚未通过严格准入的书法家不写入 P1 可用风格池。

## 数据流与边界

各书法家原图始终保留在外部数据盘。整合产物只保存相对的审计证据位置、筛选规则、候选计数和可复现的候选清单；不会复制原始图片，也不会把外部绝对路径或字体大文件提交到 Git。

候选规则固定如下：柳公权、颜真卿只取 `review_state=provisional` 且 OCR 置信度不低于 0.90 的单字标签；黄庭坚使用已应用人工覆写的标签并采用同一高置信规则；其余六位通过人工抽检的书法家直接使用已有的高置信候选清单。ChineseStyle 使用全量已定稿候选清单。

## 产物

1. `configs/p1_style_pool.yaml`：19 个风格的机器可读准入登记，明确 tier、许可、来源审计文件与筛选规则。
2. `outputs/p1_style_pool_20260716/style_pool.csv`：供人工查看的风格总表。
3. `outputs/p1_style_pool_20260716/core_calligrapher_candidates.csv`：9 位 P1-core 书法家的严格候选清单。
4. `outputs/p1_style_pool_20260716/extended_chinese_style_candidates.csv`：ChineseStyle 扩展候选清单。
5. `outputs/p1_style_pool_20260716/summary.json` 和 `README.md`：记录计数、来源和论文使用边界。

## 验收条件

- 风格登记必须恰好为 17 个 core 与 2 个 extended；没有未准入书法家。
- core 书法家候选只来自指定审计产物，且每张原图路径存在、字符为单一 CJK 字符、没有重复的 `style_id + source_split + raw_filename`。
- extended 清单恰好包含 ChineseStyle 的隶书和行楷，并在清单和说明中显式标记 `unverified` 与用户确认使用依据。
- 汇总数量与现有审计结果一致，并有自动化测试覆盖。

## 后续但不在本次范围内

下一阶段才决定字符覆盖策略、训练/验证/测试切分，渲染开源字体内容图，建立 FontDiffuser 目录适配器和执行训练。传统字与简化字仍按 Unicode 精确区分，不在本步骤做归一化。
