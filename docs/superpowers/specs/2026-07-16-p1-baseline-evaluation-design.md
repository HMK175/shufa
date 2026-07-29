# P1-extended 正式基线与固定测试集设计

## 目标

为 FontDiffuser 的 P1-extended Phase 1 先导基线建立一个可迁移到 AutoDL 的训练配置，以及一个在训练前固定、不随结果调整的测试清单。

## 任务边界

本阶段只评估“已见风格、未见字符”：

- 训练参考图必须来自 `train/TargetImage/<style_id>/`。
- 内容图和真实目标图必须来自 `test/`，且字符划分由既有 P1 划分决定。
- 不启用 Phase 2 / SCR。
- 每个测试样本的风格参考图在同一风格的训练集内固定选择；由于字符划分互斥，该参考字不会等于测试字。

## 输出

构建器从 P1 Phase 1 的 `manifests/samples.csv` 生成：

1. `paired_test_manifest.csv`：全部 9,580 个测试目标图的成对评估清单。每行包含测试内容图、训练风格参考图和测试真实目标图，可用于 L1、SSIM、LPIPS 及批量分布指标。
2. `visual_test_manifest.csv`：每种风格稳定抽取最多 20 个样本的可视化清单，当前共 380 行；每个 checkpoint 都对相同样本进行采样。
3. `evaluation_summary.json`：统计、随机种子和数据泄漏防护结果。

训练配置使用官方的 96 × 96 Phase 1 设置，且首轮限定为 10,000 个优化步、每 1,000 step 保存 checkpoint。它是正式基线的先导运行配置，不将 10,000 step 的输出误作为最终论文结果。

## 验收条件

- 清单仅使用 test 目标和 test 内容图。
- 所有参考图来自同一风格的 train 目录。
- 同一输入和随机种子重复生成时 CSV 字节一致。
- 配置明确 `phase_2=false`、`scr=false`、96 × 96、FP16、batch size 1、梯度累积 8 和 10,000 step。
- 输出记录 P1 数据范围与 ChineseStyle 的许可状态边界。
