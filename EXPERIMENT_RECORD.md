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

---

## 2026-05-29 结构约束版 next-stroke 分割实验记录

### 背景

前一阶段已将笔画分割路线从 fixed 13-channel ordered mask baseline 转为 next-stroke/current-stroke segmentation：

- fixed 13-channel baseline：test Dice 约 0.2295。
- next-stroke teacher-forcing：test Dice 0.6173。
- next-stroke autoregressive rollout：test Dice 0.3299。

随后尝试 previous-mask noise、mixed previous、predicted-previous cache / DAgger 式再训练，均未超过 baseline autoregressive=0.3299。问题进一步定位为：模型未显式学会排除已写 previous 区域，rollout 中易出现重复预测、overlap、overflow 和误差累积。

### 本轮改动

未改 `code/stroke.py`、`code/pipeline.py` 或旧真实图像流程。本轮只改 next-stroke segmentation 独立实验链路。

修改/新增文件：

- `code/stroke_next_model.py`：新增 `compute_remaining_mask`、4 通道输入支持、`overlap_penalty_loss`。
- `code/train_stroke_next_model.py`：新增 `--use-remaining-channel`、`--overlap-penalty-weight`。
- `code/predict_stroke_next_rollout.py`：新增 `--constrain-remaining`，preview 增加 full / previous / remaining / GT / pred / diff。
- `code/predict_stroke_next_model.py`：支持按 checkpoint 加载 3/4 通道模型。
- `tests/test_stroke_next_remaining.py`：覆盖 remaining mask、4 通道 forward、overlap penalty 等。

### 实验结果

| 实验 | teacher Dice | autoregressive Dice | drop | overlap | overflow |
|---|---:|---:|---:|---:|---:|
| baseline | 0.6173 | 0.3299 | 0.2874 | 0.2197 | 0.3935 |
| baseline + constrain remaining | 0.6173 | 0.3079 | 0.3094 | 0.0000 | 0.3932 |
| 4ch remaining + penalty | 0.5737 | 0.2613 | 0.3124 | 0.2444 | 0.3671 |
| 4ch remaining + penalty + constrain | 0.5737 | 0.2409 | 0.3328 | 0.0000 | 0.3665 |

4 通道模型：

- 模型路径：`code/models/stroke_next_unet_remaining.pt`
- 训练轮数：12 epoch
- 耗时：约 558.5s
- overlap penalty：`--overlap-penalty-weight 0.35`
- best threshold：0.3

典型预览：

- baseline constrained `志`：`code/output/stroke_next_rollout_constrained/u5fd7/rollout_preview.png`
- remaining `志`：`code/output/stroke_next_rollout_remaining/u5fd7/rollout_preview.png`
- remaining `以`：`code/output/stroke_next_rollout_remaining/u4ee5/rollout_preview.png`
- remaining constrained `飞`：`code/output/stroke_next_rollout_remaining_constrained/u98de/rollout_preview.png`

验证命令：

```powershell
python -m pytest tests\test_stroke_next_remaining.py tests\test_stroke_next_dagger.py tests\test_stroke_next_rollout.py tests\test_stroke_next_model.py tests\test_stroke_seg_model.py tests\test_makemeahanzi_seg_dataset.py tests\test_makemeahanzi_import.py -q
```

结果：`28 passed, 2 warnings`。

### 阶段判断

结构约束没有超过 baseline autoregressive=0.3299。

- `constrain-remaining` 能将 overlap 压到 0，但 Dice 下降，说明硬扣 previous 会切掉当前笔画与已写区域之间自然连接或交叠部分。
- 4 通道 remaining 模型略降 overflow，但 teacher-forcing 与 autoregressive Dice 均下降，说明 remaining 通道和 overlap penalty 暂未解决当前笔定位问题。
- 当前分割尚不适合直接进入 mask-to-trajectory 主链路。

结论：不建议继续只围绕 previous/remaining mask 做简单约束或加训。下一阶段更值得考虑“每一步直接预测 remaining/current 的组合目标”、加入笔画 order/class 先验，或扩大/重构训练样本后再评估 next-stroke 分割稳定性。

---

## 2026-05-30 LLM style trajectory 三风格对比实验记录

### 实验范围

本轮只整理 `experiments/llm_style_trajectory` 独立实验模块的风格对比结果，未修改 `code/stroke.py`、`code/pipeline.py` 或旧真实图像流程。

### 输出位置

- 批量输出目录：`experiments/llm_style_trajectory/outputs/batch_20260529_163539/`
- 汇总指标表：`experiments/llm_style_trajectory/outputs/batch_20260529_163539/batch_summary.csv`
- 展示说明：`experiments/llm_style_trajectory/outputs/batch_20260529_163539/README.md`

### demo 字与风格

| 字 | 风格 |
|---|---|
| 山 | kaishu / xingkai / lishu |
| 中 | kaishu / xingkai / lishu |
| 永 | kaishu / xingkai / lishu |

### compare 图

| 字 | compare 图 |
|---|---|
| 山 | `experiments/llm_style_trajectory/outputs/batch_20260529_163539/compare_u5c71.png` |
| 中 | `experiments/llm_style_trajectory/outputs/batch_20260529_163539/compare_u4e2d.png` |
| 永 | `experiments/llm_style_trajectory/outputs/batch_20260529_163539/compare_u6c38.png` |

### 关键结论

- `kaishu`：参数最保守，`connection_count=0`，轨迹主要保持 Make Me a Hanzi median 的基本结构。
- `xingkai`：加入连接与更强平滑，`connection_count` 分别为山 2、中 3、永 4；`mean_turning` 通常低于 kaishu，表现为更连贯、更圆滑。
- `lishu`：横向放大、纵向压缩最明显，三个字的 `aspect_ratio` 均高于对应 kaishu/xingkai，形成较明显的宽扁效果。
- 坐标范围检查稳定：9 个 demo 的 `out_of_bounds` 全部为 `False`。

### 边界说明

当前 `style_profiles.json` 是人工设定的参数化风格 profile，不是从书法图片、字体数据或人工示教轨迹中学习得到。当前 planner 仍是规则/模拟版；LLM 的预期角色是任务解析、风格选择与工具编排，CSV 轨迹由确定性轨迹工具生成，不由 LLM 直接编造。

---

## 2026-06-05 style profile 数据化实验记录

### 实验范围

本轮继续整理 `experiments/llm_style_trajectory` 独立实验模块，不修改 `code/stroke.py`、`code/pipeline.py` 或旧真实图像流程。目标是将三风格轨迹中的部分 style profile 参数从纯人工设定推进为“字体渲染样本统计 + 参数化映射”。

### 数据来源

本机发现并成功使用 3 个 Windows 中文字体文件：

| style | font |
|---|---|
| kaishu | `C:\Windows\Fonts\simkai.ttf` |
| xingkai | `C:\Windows\Fonts\STXINGKA.TTF` |
| lishu | `C:\Windows\Fonts\SIMLI.TTF` |

每种 style 成功渲染 10/10 个测试字符，用于估计几何统计指标。

### 输出位置

- style profile 构建目录：`experiments/llm_style_trajectory/outputs/style_profile_build_20260601_135213/`
- 指标表：`experiments/llm_style_trajectory/outputs/style_profile_build_20260601_135213/style_metrics.csv`
- 估计参数：`experiments/llm_style_trajectory/outputs/style_profile_build_20260601_135213/style_profile_estimated.json`
- 报告：`experiments/llm_style_trajectory/outputs/style_profile_build_20260601_135213/style_profile_report.md`
- 字体风格对比图：`experiments/llm_style_trajectory/outputs/style_profile_build_20260601_135213/compare_styles.png`
- 使用 estimated profile 生成的三风格 demo：`experiments/llm_style_trajectory/outputs/batch_20260601_135226/`

estimated profile demo compare 图：

| 字 | compare 图 |
|---|---|
| 山 | `experiments/llm_style_trajectory/outputs/batch_20260601_135226/compare_u5c71.png` |
| 中 | `experiments/llm_style_trajectory/outputs/batch_20260601_135226/compare_u4e2d.png` |
| 永 | `experiments/llm_style_trajectory/outputs/batch_20260601_135226/compare_u6c38.png` |

### 参数来源

| parameter | source |
|---|---|
| `horizontal_scale` | estimated |
| `vertical_scale` | estimated |
| `smoothness` | estimated |
| `corner_rounding` | estimated |
| `speed_scale` | estimated |
| `connection_strength` | default_prior |
| `pen_up_height` | default_prior |

说明：静态字体几何可支持形态尺度、平滑/转折和粗略速度相关参数估计；连接强度和抬笔高度仍缺少可靠字体图像依据，因此保留人工先验，没有伪装为学习结果。

### 人工质检

人工查看 `compare_styles.png` 及 `山/中/永` 的 estimated profile compare 图后，确认三种字体风格本身存在可见差异，使用 estimated profile 生成的轨迹也存在可见差异。当前尚未通过机器人或绘图设备实际书写，因此只能判断图像/轨迹层面的差异，不能判断真实落笔效果、笔触质感和机械执行稳定性。

### 验证

```powershell
python -m pytest experiments\llm_style_trajectory\tests -q
```

结果：`10 passed, 4 warnings`。warnings 来自 Matplotlib 默认字体缺少中文字形，仅影响标题显示，不影响 CSV、轨迹和 compare 图生成。

### 阶段判断

本轮将多风格轨迹从“纯人工 style profile demo”推进为“基于字体渲染样本统计的参数化风格 profile”。目前可用于论文或汇报中的稳妥表述是：

> 通过楷书、行楷、隶书字体样本的几何统计，估计部分风格参数，并用于参数化轨迹生成。

仍需保留的边界：

- 当前不是从真实书法图片中学习风格。
- 当前不是深度学习风格迁移。
- 当前未接入真实 LLM，planner 仍是规则/模拟版。
- 当前仅验证生成轨迹和预览图存在风格差异，未验证真实机器人书写效果。

---

## 2026-06-05 trajectory render/evaluation 虚拟书写评价记录

### 实验范围

本轮继续在 `experiments/llm_style_trajectory` 独立模块内增加虚拟书写评价，不修改 `code/stroke.py`、`code/pipeline.py` 或旧真实图像/CNN 分割流程。目标是将 estimated profile 生成的 `trajectory.csv` 渲染成模拟书写图，并与对应 style 字体渲染图进行定量对比。

### 输入与输出

评价 batch：

- `experiments/llm_style_trajectory/outputs/batch_20260601_135226/`

新增输出：

- 汇总表：`experiments/llm_style_trajectory/outputs/batch_20260601_135226/render_eval_summary.csv`
- `山` render compare：`experiments/llm_style_trajectory/outputs/batch_20260601_135226/render_compare_u5c71.png`
- `中` render compare：`experiments/llm_style_trajectory/outputs/batch_20260601_135226/render_compare_u4e2d.png`
- `永` render compare：`experiments/llm_style_trajectory/outputs/batch_20260601_135226/render_compare_u6c38.png`

典型 overlay：

- 相对较好：`中 / xingkai`，IoU=0.34628，`experiments/llm_style_trajectory/outputs/batch_20260601_135226/u4e2d_xingkai_20260601_135226/render_eval_overlay.png`
- 偏弱样本：`山 / kaishu`，IoU=0.112562，`experiments/llm_style_trajectory/outputs/batch_20260601_135226/u5c71_kaishu_20260601_135226/render_eval_overlay.png`

### 平均指标

| style | mean IoU | mean Chamfer | mean aspect_ratio_error |
|---|---:|---:|---:|
| kaishu | 0.170100 | 9.428120 | 0.139753 |
| xingkai | 0.235248 | 6.992876 | 0.077497 |
| lishu | 0.195113 | 9.129582 | 0.300849 |

### 关键观察

- 模拟书写后仍能观察到风格差异，尤其 `lishu` 的宽扁趋势在 rendered bbox/aspect 上仍较明显。
- 在当前 3 字 × 3 风格样本中，`xingkai` 与对应字体 target 的平均 IoU、Chamfer 和 aspect error 最好。
- 整体 IoU 偏低，主要原因是当前由 median trajectory 按固定 `stroke_width` 渲染，难以匹配真实字体完整笔画轮廓中的粗细变化、起收笔形态和转折笔触。
- 当前瓶颈从“能否生成不同风格轨迹”进一步转向“笔刷/笔宽渲染模型是否足够接近目标字体轮廓”。

### 验证

```powershell
python -m pytest experiments\llm_style_trajectory\tests -q
```

结果：`16 passed, 4 warnings`。warnings 仍来自 Matplotlib 默认字体缺少中文字形，不影响 CSV、渲染图、overlay 或评价指标生成。

### 阶段判断

本轮补齐了“轨迹 CSV -> 模拟书写图 -> 目标字体图评价”的闭环。当前可以支撑的稳妥表述是：

> 参数化风格轨迹在虚拟书写评价中保留了一定风格差异，但固定笔宽渲染与目标字体轮廓仍存在明显差距。

下一阶段若继续提升该路线，应优先考虑 style-aware brush rendering，例如按风格、笔画方向、起收笔和转折位置调整笔宽，而不是继续优先调 LLM planner。

---

## 2026-06-05 inter-stroke connection 先验修正记录

### 问题背景

人工查看 estimated profile demo 后发现：目标隶书字体样本本身没有连笔，但生成的 `lishu` 轨迹存在笔画间连接。进一步检查后确认，原因不是字体样本估计错误，而是 `connection_strength` 使用了人工默认先验；此前 `lishu.connection_strength=0.06`，导致轨迹生成工具插入跨笔连接段。

这暴露了一个方法边界：静态字体图像可以用于估计宽高比、形态压缩/拉伸、转折和平滑趋势，但不能可靠估计“是否连笔”和“抬笔高度”等书写过程参数。

### 修正内容

未修改 `code/stroke.py`、`code/pipeline.py` 或旧主流程。本轮只修正 `experiments/llm_style_trajectory` 独立实验模块。

修改/新增：

- `experiments/llm_style_trajectory/configs/style_profiles.json`
- `experiments/llm_style_trajectory/src/planner.py`
- `experiments/llm_style_trajectory/src/trajectory_tools.py`
- `experiments/llm_style_trajectory/src/run_demo.py`
- `experiments/llm_style_trajectory/src/build_style_profiles.py`
- `experiments/llm_style_trajectory/tests/test_interstroke_connections.py`

核心策略：

- 新增/使用 `allow_interstroke_connections` 显式控制是否允许跨笔连接。
- 默认没有 `allow_interstroke_connections=true` 时绝不插入跨笔连接。
- `kaishu`：不允许跨笔连接。
- `lishu`：不允许跨笔连接。
- `xingkai`：允许跨笔连接，并保留 `connection_strength` 人工先验。
- `connection_strength` 与 `allow_interstroke_connections` 均标记为 `default_prior`，不伪装为从静态字体中估计得到。

### 新输出

- estimated profile：`experiments/llm_style_trajectory/outputs/style_profile_build_20260605_235140/style_profile_estimated.json`
- profile report：`experiments/llm_style_trajectory/outputs/style_profile_build_20260605_235140/style_profile_report.md`
- 新 batch：`experiments/llm_style_trajectory/outputs/batch_20260605_235159/`
- fixed eval：`experiments/llm_style_trajectory/outputs/batch_20260605_235159/render_eval_fixed_summary.csv`
- brush eval：`experiments/llm_style_trajectory/outputs/batch_20260605_235159/render_eval_style_brush_summary.csv`

### connection_count 检查

| style | per-char connection_count | total |
|---|---|---:|
| kaishu | [0, 0, 0] | 0 |
| xingkai | [2, 3, 4] | 9 |
| lishu | [0, 0, 0] | 0 |

### lishu 修改前后指标

| renderer | old IoU | new IoU | old Chamfer | new Chamfer | old aspect err | new aspect err |
|---|---:|---:|---:|---:|---:|---:|
| fixed | 0.1951 | 0.1603 | 9.1296 | 11.0451 | 0.3008 | 0.3008 |
| style_brush | 0.2124 | 0.1825 | 8.7357 | 10.3775 | 0.2978 | 0.2994 |

说明：去掉隶书连笔后 IoU 与 Chamfer 指标下降，但这是预期且合理的。旧指标中的一部分提升来自错误跨笔连接，不能作为风格正确性的依据。新 `lishu` 的 mean aspect ratio 仍为 1.0794，宽扁风格保留。

### 验证

```powershell
python -m pytest experiments\llm_style_trajectory\tests -q
```

结果：`24 passed`，仅有 DejaVu Sans 缺中文字形的测试 warning。

### 阶段判断

本轮修正了“目标隶书无连笔但生成轨迹有连笔”的问题。后续论文/汇报中应明确区分：

- 可由静态字体估计的形态参数：`horizontal_scale`、`vertical_scale`、`smoothness`、`corner_rounding`、`speed_scale`。
- 需要书写过程先验或示教数据支撑的动态参数：`connection_strength`、`allow_interstroke_connections`、`pen_up_height`。

该修正体现了方法边界：风格参数不应为了提升 IoU 而违反目标字体/书写逻辑。
