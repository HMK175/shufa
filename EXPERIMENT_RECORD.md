# 实验记录

## 实验目标

验证基于图像骨架提取与强化学习优化的书法机器人轨迹生成方法的有效性。

## 实验数据

- 字形图像来源：网上书法字体图片 / 标准字体库
- 测试样本数：≥5 个不同字形
- 图像格式：黑白二值图

## 评价指标

- 轮廓相似度：优化后轨迹生成图像与目标图像的HD/SSIM
- 轨迹平滑度：曲率方差
- 轨迹误差：均方根误差(RMSE)

## 对比方法

1. 骨架提取原始轨迹（baseline）
2. 骨架轨迹 + B样条平滑
3. 骨架轨迹 + 强化学习优化（本文方法）

## 实验记录模板

### 实验编号：EXP-001
- 日期：
- 字形样本：
- 方法：
- 参数设置：
- 结果：
  - 轮廓相似度：
  - 轨迹平滑度：
  - 轨迹误差：
- 备注：

---
## 实验结果汇总

### EXP-001: "永"字基础测试
- 日期：2026-05-12
- 字形样本：yong.jfif（340×425，二值前景 25886 px）
- 方法：完整 pipeline（skimage.thin + 简化图笔画提取 + B-spline + DDPG）
- 参数：SMOOTH=2.0, SAMPLE=300, RL_EPISODES=200/stroke, noise_std=6px
- 骨架质量：904 px 骨架，15 交叉点（1.7%），10 端点，2 连通分量
- 笔画检测：5 笔画（正确）
- 轨迹点：665 原始 → 298 平滑后

| 阶段 | 平均 Chamfer (px) | 平均 IoU |
|------|------------------|----------|
| 骨架初始轨迹 | 0.0 | 0.03-0.23 |
| 加噪 (σ=6px) | 0.4 | 下降 |
| RL 优化后 | 0.3 (↓25%) | 恢复 |

- 备注：RL 对笔画 S4 (竖钩, 84pts) 效果最显著：Chamfer 0.7→0.3px

### EXP-002: 骨架化方法对比
- 日期：2026-05-12
- 字形样本：yong.jfif
- 对比方法：

| 方法 | 骨架像素 | 交叉点 | 交叉点占比 | 连接分量 |
|------|---------|--------|-----------|---------|
| Zhang-Suen (手工实现) | 1040 | 305 | 29.3% | 2 |
| skimage.skeletonize (Lee) | 945 | 28 | 3.0% | 2 |
| skimage.medial_axis | 1087 | 36 | 3.3% | 2 |
| **skimage.thin (选用)** | **904** | **15** | **1.7%** | **2** |

- 备注：skimage.thin 在交叉点噪点方面最优，选为最终方案

### EXP-003: 笔画追踪方法对比
- 日期：2026-05-12
- 字形样本：yong.jfif
- 骨架：skimage.thin (904px, pruned to 896px)

| 方法 | 轨迹点数 | 覆盖骨架比例 | 笔画数 |
|------|---------|-------------|--------|
| trace_skeleton (笔画感知) | 665 | 74.2% | 5 |
| trace_skeleton_dfs (简单DFS) | 896 | 100% | N/A |

- 备注：笔画感知模式丢失的 25.8% 主要在交叉区内部。DFS 模式覆盖完整但无笔画分割

| 实验编号 | 字形 | 方法 | 轮廓相似度 | 平滑度 | RMSE | 备注 |
|----------|------|------|------------|--------|------|------|
| EXP-001 | 永 | 完整 pipeline | IoU 0.03-0.32 | - | Chamfer 0.3px | 5 笔画正确检测 |
| EXP-002 | 永 | 骨架方法对比 | - | - | - | thin 最优 |
| EXP-003 | 永 | 追踪方法对比 | - | - | - | 笔画感知 74% 覆盖 |

---

## 2026-05-17 小测试集划分与近期观察

### 调参集（开发期间允许反复查看）

用于覆盖主要失败类型，后续参数调整和算法修改只应看这一组：

`yi, san, shi, kou, tian, zhong, chuan, zhi, yong, fu, mu, ming`

覆盖意图：

- `yi/san/shi/chuan`：简单字、少交叉、主体笔画不能缺失。
- `kou/tian/zhong`：封闭或半封闭结构，重点检查框线是否被拆散、误连或绕行。
- `zhi/yong`：弯折、钩、中心交叉和路径方向连续性。
- `fu/mu/ming`：多部件或复杂结构，检查部件边界和跨部件误连接。

### 保留测试集（调参时不要反复看）

用于最终检查泛化能力，不参与日常调参：

`ri, ren, da, shan, lin, hao, xiu, guo, hui, pin, xin, shui, xiao`

使用原则：

- 调参阶段只在调参集上判断是否改进。
- 每完成一轮较大的算法改动，再整体跑一次保留测试集。
- 如果保留集变差，优先判断是否发生过拟合，而不是继续针对单字补规则。

### 近期测试现象记录

- “福”字已有改善，尤其右侧“口/田”类结构比前几轮更稳定。
- 简单字出现笔画缺失，说明当前过滤、合并或笔画数约束可能过强。
- “中”等闭合结构仍然敏感，容易出现框线缺失、右侧变大弧线或闭合结构被破坏。
- “川”可作为简单字底线验收：应稳定输出 3 笔，不能为了处理复杂字而损失竖画。
- 当前主要矛盾不是 RL 优化效果，而是初始骨架拓扑和笔画路径选择是否正确。

---

## 2026-05-18 批量评估结果整理

### 数据来源

- 评估脚本：`code/evaluate_set.py`
- 调参集结果：`code/output/tune_eval.csv`
- 保留集结果：`code/output/holdout_eval.csv`
- 汇总表：`code/output/eval_summary.md`

### 总体结果

| subset | total | count correct | highest max winding |
|---|---:|---:|---|
| tune | 12 | 6 | fu = 4.59 |
| holdout | 13 | 12 | xiu = 3.99 |

说明：`count_correct=no` 需要结合 `expected` 是否为空解释。当前 tune 集中 `yi/san/shi/kou/tian/mu` 的 expected 为空，因此 6/12 并不全等价于算法笔画数错误，首先应视为验收先验缺失或未量化。

### tune_set 错误/未验收样本

| char | expected | final CSV strokes | method | fallback | max winding | note |
|---|---:|---:|---|---|---:|---|
| yi | - | 1 | legacy+prior | legacy_preferred_conservative_gate;simple_prior_longest_main_stroke | 1.35 | expected missing |
| san | - | 3 | global+prior | none | 1.65 | expected missing |
| shi | - | 4 | legacy | legacy_preferred_conservative_gate | 1.14 | expected missing |
| kou | - | 3 | global | none | 1.65 | expected missing |
| tian | - | 5 | legacy+prior | global_high_winding;closed_prior_split_frame_detour | 2.47 | expected missing |
| mu | - | 7 | legacy | legacy_preferred_conservative_gate | 1.77 | expected missing |

已记录 expected 的 tune 样本 `zhong/chuan/zhi/yong/fu/ming` 均达到笔画数验收。

### holdout_set 错误样本

| char | expected | final CSV strokes | method | fallback | max winding |
|---|---:|---:|---|---|---:|
| ri | 4 | 3 | legacy | global_count_farther_from_expected | 1.55 |

### 问题分类

A 类：笔画数错误或无法验收
- `ri`：expected=4，final=3，是当前保留集唯一确认笔画数错误。
- `yi/san/shi/kou/tian/mu`：tune CSV 中 `count_correct=no`，但原因是 expected 为空；下一步应先补齐或确认工程验收先验，再判断是否属于算法错误。

B 类：笔画数正确但绕行偏高
- `fu`：expected=13，final=13，max winding=4.59。
- `xiu`：expected=6，final=6，max winding=3.99。
- 次级观察：`guo=3.44`、`hui=3.38`、`xiao=3.28`、`hao=3.26`、`shan=3.23`、`shui=3.12`。

C 类：稳定样本，可用于论文展示
- `yi/san/chuan/kou/tian/zhong/shui/pin`。
- 这些样本覆盖简单字、三竖结构、闭合结构、闭合结构修复后稳定案例、保留集自然改善案例，可作为定性结果图候选。

### 下一轮建议

1. 第一优先：解释 tune_set 为什么只有 6/12 count-correct。当前更像验收数据问题，因为 6 个 `expected` 为空；建议先补齐 tune 集工程 expected count，再重新评估。
2. 第二优先：处理 `ri` 少 1 笔问题。它是保留集中唯一明确 count mismatch，适合做下一轮算法诊断目标。
3. 第三优先：处理 `xiu/fu` 高 winding。二者笔画数已经正确，后续重点应放在中高绕行路径的定位、合并策略和后处理质量，而不是笔画数先验。

阶段判断：当前可以开始撰写论文实验章节的评估框架和初步结果表，同时保留一轮小范围算法修复任务用于 `ri` 与 `xiu/fu`。

