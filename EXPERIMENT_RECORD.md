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

---

## 2026-06-06 LLM planner 框架接入记录

### 实验范围

本轮在 `experiments/llm_style_trajectory` 独立模块中接入 LLM planner 框架，不修改 `code/stroke.py`、`code/pipeline.py` 或旧图像骨架/CNN 分割流程。当前尚未调用真实在线 API 或本地模型，主要完成 mock / api / local 三种 planner 模式的统一接口与 schema 约束。

### 修改/新增

- `experiments/llm_style_trajectory/src/planner.py`
- `experiments/llm_style_trajectory/src/run_demo.py`
- `experiments/llm_style_trajectory/README.md`
- `experiments/llm_style_trajectory/configs/planner_prompt.md`
- `experiments/llm_style_trajectory/tests/test_planner_modes.py`

### planner 模式

| mode | 当前状态 | 说明 |
|---|---|---|
| `mock` | 已实现 | 规则/模拟 planner，不调用模型，用于默认运行和测试 |
| `api` | 安全占位 | 预留在线 LLM API 接口，未配置时不联网、不偷偷 fallback |
| `local` | 安全占位 | 预留本地模型接口，未配置时不启动模型、不偷偷 fallback |

`api/local` 未配置时的提示：

- api：`api planner not configured; use --fallback-to-mock or set LLM_STYLE_PLANNER_API_KEY and LLM_STYLE_PLANNER_ENDPOINT`
- local：`local planner not configured; use --fallback-to-mock or set LLM_STYLE_PLANNER_LOCAL_CMD`

只有显式添加 `--fallback-to-mock` 时，才会退回 mock planner。

### plan schema 示例

```json
{
  "char": "山",
  "style": "xingkai",
  "style_params": {},
  "constraints": {
    "allow_interstroke_connections": true,
    "emphasize_flat_shape": false
  },
  "stroke_plan": {
    "source": "makemeahanzi",
    "order": "source_order",
    "generator": "deterministic_style_profile"
  },
  "planner_mode": "mock",
  "source": "mock_rule_based",
  "warnings": [],
  "raw_response": null,
  "validation": {
    "ok": true,
    "errors": [],
    "warnings": []
  }
}
```

### demo 输出

- 行楷“山”：`experiments/llm_style_trajectory/outputs/u5c71_xingkai_20260606_161529/plan.json`
- 隶书“山，不要连笔”：`experiments/llm_style_trajectory/outputs/u5c71_lishu_20260606_161535/plan.json`

### 验证

运行命令：

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode mock
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个隶书风格的山，不要连笔" --planner-mode mock
python -m pytest experiments\llm_style_trajectory\tests -q
```

结果：`31 passed`，有 5 个 DejaVu Sans 中文缺字 warning，不影响 planner、轨迹生成或测试结果。

### 阶段判断

LLM planner 已从概念进入系统接口层，但当前仍未验证真实 LLM 能力。现阶段可支撑的表述是：

> 已构建面向自然语言书写任务的 planner 接口框架，支持 mock / api / local 三种模式，并通过 schema validation 限定 LLM 只输出结构化书写计划，不直接生成轨迹 CSV。

该设计保证：

- LLM 仅负责任务解析、风格选择、约束生成和工具编排。
- `trajectory.csv` 仍由 Make Me a Hanzi、style profile 和确定性轨迹工具生成。
- API 和本地模型接入可以复用同一 plan schema 与 validation。
- 真实模型接入前，系统仍可通过 mock planner 稳定复现。

---

## 2026-06-08 DeepSeek-V4-Pro API planner smoke 记录

### 实验范围

本轮使用已配置的 DeepSeek-V4-Pro API key 对 `experiments/llm_style_trajectory` 的 `api` planner 模式进行真实 smoke test。未修改 `code/stroke.py`、`code/pipeline.py` 或旧主流程。

### 运行命令

```powershell
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个行楷风格的山" --planner-mode api
python experiments\llm_style_trajectory\src\run_demo.py --task "写一个隶书风格的山，不要连笔" --planner-mode api
```

运行中出现 Matplotlib `DejaVu Sans` 缺少中文字形 warning，仅影响图标题显示，不影响 plan、CSV 或轨迹生成。

### 输出位置

- 行楷“山”：`experiments/llm_style_trajectory/outputs/u5c71_xingkai_20260608_145428/`
  - `plan.json`
  - `trajectory.csv`
  - `preview.png`
  - `summary.json`
- 隶书“山，不要连笔”：`experiments/llm_style_trajectory/outputs/u5c71_lishu_20260608_145435/`
  - `plan.json`
  - `trajectory.csv`
  - `preview.png`
  - `summary.json`

### plan 检查

行楷“山”：

- `planner_mode=api`
- `source=deepseek_v4_pro`
- `char=山`
- `style=xingkai`
- `allow_interstroke_connections=true`
- `stroke_count=3`
- `validation.ok=true`

隶书“山，不要连笔”：

- `planner_mode=api`
- `source=deepseek_v4_pro`
- `char=山`
- `style=lishu`
- `allow_interstroke_connections=false`
- `emphasize_flat_shape=true`
- `connection_strength=0.0`
- `stroke_count=3`
- `validation.ok=true`

两个 plan 均未包含 `trajectory`、`csv`、`points` 等被禁止的直接轨迹字段；API key 未写入输出文件。

### 知识库使用方式

当前 API planner 并不是把完整本地知识库上传给 DeepSeek。实际数据流为：

1. 本地读取 planner prompt 与支持的 style profile 摘要。
2. 将用户任务、planner prompt、style profile 摘要发送给 DeepSeek。
3. DeepSeek 返回结构化 plan JSON。
4. 本地代码使用 style profile 补全 `style_params`，并用 Make Me a Hanzi 验证字符存在、补充 `stroke_count`。
5. 本地确定性工具根据 Make Me a Hanzi median 和 style profile 生成 `trajectory.csv`。

因此，当前更准确地说是：

> API planner + 本地结构化知识库校验/补全 + 本地轨迹工具生成

不是完整向量检索式 RAG，也不是让 DeepSeek 自己记忆或生成字形轨迹。

### 阶段判断

DeepSeek-V4-Pro API 已能稳定完成文本 planner 的基本任务：将自然语言书写请求解析为合法结构化 plan，并通过本地 validation 驱动后续确定性轨迹生成。该结果可用于论文或汇报中证明：

- LLM 环节已经实际接入，而非仅保留接口。
- LLM 的作用被限制在任务解析、风格选择与约束生成。
- 本地知识库与确定性工具仍是轨迹生成的主体，避免 LLM 直接编造 CSV。

---

## 2026-06-08 LLM planner 鲁棒性边界收紧记录

### 背景

手动运行 DeepSeek-V4-Pro API planner 鲁棒性测试后，得到初始结果：

```json
{
  "total": 12,
  "validation_ok_count": 12,
  "char_correct_count": 11,
  "style_correct_count": 8,
  "connection_constraint_correct_count": 9,
  "expected_invalid_rejected_count": 0,
  "dangerous_output_count": 0,
  "json_parse_success_count": 12,
  "average_latency": 8.8464
}
```

该结果说明 DeepSeek 在 JSON 输出稳定性方面表现较好，且没有直接输出 `trajectory/csv/points` 等危险字段；但本地 planner 边界过宽，导致模型把不支持或非法请求“好心”归一化为支持项。

典型问题包括：

- `草书` 被映射为 `xingkai`
- `火星文` 被映射为 `xingkai`
- `山水` 被截断为单字 `山`
- `好看一点` 被模型自行理解成 `xingkai`

### 修改内容

本轮只修改 `experiments/llm_style_trajectory`，没有修改 `code/stroke.py` / `code/pipeline.py`。

核心修正：

- 在 planner 输出中新增请求边界字段：
  - `request_status`
  - `requested_style_raw`
  - `requested_chars_raw`
  - `mapped_style`
  - `rejection_reason`
- 新增本地 request-boundary 分析层：
  - unsupported style：`草书`、`行草`、`火星文` 等必须拒绝
  - multi-character request：如 `山水` 必须拒绝，不能截断
  - ambiguous style：如 `好看一点` 默认保守映射到 `kaishu`，并写入 warning
- 更新 `planner_prompt.md`，明确要求 API/local 模型不要把 unsupported 请求偷偷映射成 supported style。
- 更新鲁棒性评估 CSV 字段，使每条任务能直接看到请求状态、原始风格、原始字符和拒绝原因。
- 补充回归测试，覆盖 unsupported style、multi-character、ambiguous default、inter-stroke constraint words 等边界。

### 验证

完整测试：

```powershell
python -m pytest experiments\llm_style_trajectory\tests -q
```

结果：

```text
42 passed, 5 warnings
```

warnings 仍是 Matplotlib `DejaVu Sans` 缺少中文标题字形，不影响 plan、CSV、trajectory 或 render/eval。

mock 鲁棒性评估：

```powershell
python experiments\llm_style_trajectory\src\evaluate_planner_robustness.py --planner-mode mock
```

输出目录：

```text
experiments/llm_style_trajectory/outputs/planner_robustness_20260608_153906/
```

指标：

```json
{
  "total": 12,
  "validation_ok_count": 9,
  "char_correct_count": 12,
  "style_correct_count": 12,
  "connection_constraint_correct_count": 12,
  "expected_invalid_rejected_count": 3,
  "dangerous_output_count": 0,
  "json_parse_success_count": 12,
  "average_latency": 0.0459
}
```

### 阶段判断

这轮修正的核心意义是：LLM planner 的可靠性不再只依赖 prompt，而是由本地 validation 明确控制边界。论文中可以表述为：

> 大模型只负责自然语言任务解析和结构化计划生成；系统通过本地请求边界分析与 schema validation 对模型输出进行二次约束，防止其将不支持风格、多字符输入或轨迹坐标生成请求误归一化为合法轨迹任务。

下一步需要在已配置 API key 的 PowerShell 会话中重新运行：

```powershell
python experiments\llm_style_trajectory\src\evaluate_planner_robustness.py --planner-mode api
```

期望观察重点：

- `expected_invalid_rejected_count` 是否从上一轮 API 的 `0/3` 提升到 `3/3`
- `style_correct_count` 是否提升，尤其 `ambiguous_good_shan` 是否回到 `kaishu`
- `dangerous_output_count` 是否继续保持 0

---

## 2026-06-08 DeepSeek API planner 鲁棒性复测环境检查

### 执行命令

按要求先从 Windows 用户级环境变量导入到当前 PowerShell 会话：

```powershell
$env:LLM_STYLE_PLANNER_API_KEY = [Environment]::GetEnvironmentVariable("LLM_STYLE_PLANNER_API_KEY", "User")
$env:LLM_STYLE_PLANNER_ENDPOINT = [Environment]::GetEnvironmentVariable("LLM_STYLE_PLANNER_ENDPOINT", "User")
$env:LLM_STYLE_PLANNER_MODEL = [Environment]::GetEnvironmentVariable("LLM_STYLE_PLANNER_MODEL", "User")
[bool]$env:LLM_STYLE_PLANNER_API_KEY
python experiments\llm_style_trajectory\src\evaluate_planner_robustness.py --planner-mode api
```

### 结果

`[bool]$env:LLM_STYLE_PLANNER_API_KEY` 输出为 `False`，说明当前 Codex/PowerShell 会话没有读取到用户级 DeepSeek API key。因此本轮没有真实调用 DeepSeek，只生成了 API 未配置状态下的鲁棒性报告。

输出目录：

```text
experiments/llm_style_trajectory/outputs/planner_robustness_20260608_162126/
```

指标：

```json
{
  "total": 12,
  "validation_ok_count": 0,
  "char_correct_count": 0,
  "style_correct_count": 0,
  "connection_constraint_correct_count": 8,
  "expected_invalid_rejected_count": 3,
  "dangerous_output_count": 0,
  "json_parse_success_count": 0,
  "average_latency": 0.0
}
```

### 判断

这不是一次有效的 DeepSeek planner 能力评估；所有任务均因 `api_unconfigured` 失败。`expected_invalid_rejected_count=3` 只是因为所有 plan 都未通过 validation，并不能说明模型正确拒绝了 unsupported / multi-character 请求。

下一步需要确保 `LLM_STYLE_PLANNER_API_KEY` 写入当前 Codex 进程可见的用户级或进程级环境变量后，再重新运行同一命令。

---

## 2026-06-08 DeepSeek API planner 鲁棒性有效复测

### 执行条件

按当前 Codex 进程环境变量复测，不再从 `HKCU:\Environment` 导入或覆盖 API key。执行前后只检查布尔可见性和非敏感 endpoint/model：

```text
ProcessKeyVisible=True
ProcessEndpoint=https://api.deepseek.com/chat/completions
ProcessModel=deepseek-v4-pro
```

本轮未打印、未记录、未写入 API key。

### 输出位置

```text
experiments/llm_style_trajectory/outputs/planner_robustness_20260608_163557/
experiments/llm_style_trajectory/outputs/planner_robustness_20260608_163557/planner_robustness_summary.csv
experiments/llm_style_trajectory/outputs/planner_robustness_20260608_163557/planner_robustness_report.md
```

### 指标

```json
{
  "total": 12,
  "validation_ok_count": 9,
  "char_correct_count": 11,
  "style_correct_count": 10,
  "connection_constraint_correct_count": 12,
  "expected_invalid_rejected_count": 3,
  "dangerous_output_count": 0,
  "json_parse_success_count": 12,
  "average_latency": 10.3482
}
```

### 重点样本

- `ambiguous_good_shan`：任务为“写一个好看一点的山”，实际风格回到 `kaishu`，`validation_ok=true`。
- `unsupported_caoshu_shan`：模型输出经过本地边界检查后被拒绝，原因为 `unsupported style requested: 草书`。
- `abnormal_mars_style_shan`：被拒绝，原因为 `unsupported style requested: 火星文`。
- `multi_char_shanshui`：被拒绝，原因为多字输入 `山水` 不符合单字任务边界。

### 判断

这是一轮有效的 DeepSeek-V4-Pro 文本 planner 鲁棒性复测：12 条任务均成功返回可解析 JSON，危险输出为 0，三个 expected-invalid 任务均被拒绝，模糊风格请求回到保守默认 `kaishu`。`style_correct_count=10/12` 的两个未计入项来自 unsupported 风格任务；对预期有效任务而言，风格解析和连笔约束均满足当前实验边界。

当前结论：DeepSeek-V4-Pro 已足够作为文本 planner 基准继续使用，但必须保留本地 request boundary + schema validation，不能只依赖 prompt 约束。

---

## 2026-06-11 style modifiers 梯度对比实验

### 实验目的

在 `experiments/llm_style_trajectory` 中验证受控自然语言 modifiers 是否能形成可解释的轨迹参数梯度。本轮只使用 `mock` planner，不调用 API，不允许 LLM 直接输出 CSV、轨迹点或任意数值 style 参数。

### 实现调整

- 普通 `xingkai` 默认 `connection_preference` 从 `normal` 改为 `weak`。
- 用户明确“更连贯 / 连起来 / 连笔”时映射为 `connection_preference=normal`。
- 用户明确“不要连笔 / 不连笔 / 不要连接”时映射为 `connection_preference=none`，并强制 `allow_interstroke_connections=false`、`connection_strength=0`。
- `kaishu` / `lishu` 仍不会被普通 modifier 打开跨笔连笔，除非对应 style profile 明确允许。
- 新增 `configs/modifier_ablation_tasks.json` 和 batch 输出的 `modifier_ablation_<char_id>.png` 对比图。

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260611_210502/
experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_ablation_u5c71.png
```

### 山字三组指标

| task | connection_preference | connection_strength | connection_count | path_length | pen_up_count | mean_turning |
|---|---:|---:|---:|---:|---:|---:|
| 写一个不要连笔的行楷山 | none | 0.0 | 0 | 578.070 | 2 | 0.053843 |
| 写一个行楷风格的山 | weak | 0.176 | 2 | 611.321 | 0 | 0.053843 |
| 写一个更连贯的行楷山 | normal | 0.32 | 2 | 638.527 | 0 | 0.053843 |

### 验证

```text
python -m pytest experiments\llm_style_trajectory\tests -q
48 passed, 9 warnings
```

warnings 为 Matplotlib 默认字体缺少中文 glyph 的预览图标题提示，不影响 planner、modifier 映射或轨迹生成。

---

## 2026-06-17 风格诊断 v2：异常样本定位 + 人工看图校验包

### 实验目的

基于上一轮 54 个多字样本风格诊断结果，自动挑出最值得人工看图的样本和最需要后续调参的问题。目标是把“数据层诊断”推进到“人工视觉校验准备”，但本轮不调 style profile 参数。

### 实现

- 新增 `experiments/llm_style_trajectory/src/style_visual_audit.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_style_visual_audit.py`。
- 从 `style_diagnostic_summary.csv` 中选择异常/代表候选。
- 复制候选样本图片到 `selected_images/`，不移动原图。
- 输出候选 CSV、manifest、人工看图 checklist 和报告。

### 输出

```text
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_candidates.csv
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_report.md
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_checklist.md
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/visual_audit_image_manifest.csv
experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/selected_images/
experiments/llm_style_trajectory/outputs/paper_figures/style_visual_audit_index.md
```

### 候选统计

| case_type | count |
|---|---:|
| high_aspect_spread | 5 |
| high_lishu_aspect | 3 |
| long_xingkai_connector | 3 |
| low_aspect_spread | 3 |
| representative | 4 |

总候选数：18。

### 优先人工看图样本

- `人 / kaishu`、`人 / lishu`、`人 / xingkai`：三风格宽扁差异强，检查是否只是横向拉伸。
- `国 / xingkai`、`德 / xingkai`、`福 / xingkai`：connector 最长，检查行楷连接是否过长或不自然。
- `中 / kaishu`、`中 / lishu`、`中 / xingkai`：三风格差异弱，检查肉眼是否难分。
- `和 / kaishu`、`和 / lishu`、`和 / xingkai`：代表样本，用于和异常样本对照。

### 边界

本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不做真实 IK，不调用 SDK，不发送机器人命令。人工看图结论尚未完成，不能把数值诊断当作最终视觉效果结论；下一轮应等待用户看图反馈后再决定是否调参。

---

## 2026-06-17 多字样本风格区分度与参数诊断实验

### 实验目的

扩充样本量，诊断当前参数化 style profile / modifier 在更多汉字结构上的稳定性，重点回答：

- 三种基础风格 `kaishu` / `xingkai` / `lishu` 是否仍稳定可区分。
- 哪些指标最能区分三种风格。
- 哪些字或风格容易失败。
- 下一步哪些参数最值得重新估计或重新设计。

本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不做真实 IK，不调用 SDK，不发送机器人命令。

### 实现

- 新增 `experiments/llm_style_trajectory/configs/style_diagnostic_chars.json`。
- 新增 `experiments/llm_style_trajectory/src/style_diagnostics.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_style_diagnostics.py`。
- 固定论文/汇报入口：
  `experiments/llm_style_trajectory/outputs/paper_figures/style_diagnostics_index.md`。

### 输出

```text
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_summary.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_style_means.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_char_means.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_failures.csv
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_report.md
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_diagnostic_grid.png
experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/style_metric_bars.png
```

### 样本统计

| total_samples | success_count | failure_count | missing_char_count |
|---:|---:|---:|---:|
| 54 | 54 | 0 | 0 |

### 三风格平均指标

| style | samples | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.018672 | 786.158 | 0.000 | 0.000 | 9.000 | 614.139 | 0 |
| lishu | 18 | 1.465173 | 783.776 | 0.000 | 0.000 | 10.000 | 612.518 | 0 |
| xingkai | 18 | 1.070791 | 1314.104 | 6.056 | 525.944 | 7.489 | 615.987 | 0 |

### 诊断结论

- `lishu` 在多字样本中稳定呈现更宽扁的 aspect ratio。
- `xingkai` 在多字样本中稳定产生 connector，`connection_count` 和 `connector_draw_length` 是最清晰的区分指标。
- `kaishu` 和 `lishu` 都保持无跨笔连接，说明基础 profile 的禁止连笔逻辑稳定。
- 本轮 18 字 x 3 风格均成功生成，没有缺字、失败样本或 workspace 越界样本。
- 当前风格参数仍偏粗，下一步应优先重新估计笔画级宽度、部件级比例、转折圆滑度和 connector 触发规则。

### 边界

本轮是参数化 profile 的稳定性诊断，不是最终真实书法风格学习结果。LLM/API planner 不直接输出 CSV 或轨迹点，所有轨迹仍由本地确定性工具生成。

---

## 2026-06-17 Target pose 去重 + retiming + 速度平滑后处理层

### 实验目的

上一轮 `motion_continuity_check.py` 对默认 weak 行楷山样例发现：

- `dt_nonpositive_count=4`
- `max_accel_m_s2=0.533536284`，超过保守阈值 `0.50`
- `max_jerk_m_s3=11.386446091`，超过保守阈值 `5.0`
- `recommended_for_coppeliasim_playback=false`
- `recommended_for_ik_dry_run=false`

本轮目标是在不改变字形几何路径的前提下，删除相邻静止重复点并重写严格递增时间戳。

### 实现

- 新增 `experiments/llm_style_trajectory/src/target_pose_retiming.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_target_pose_retiming.py`。
- 新增 `experiments/llm_style_trajectory/docs/target_pose_retiming_notes.md`。
- 固定论文入口 `experiments/llm_style_trajectory/outputs/paper_figures/target_pose_retiming_index.md`。
- 后处理完成后复用 `motion_continuity_check.py` 输出 after-retiming summary/report/points。

### 默认样例输出

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses_smoothed.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/target_pose_retiming_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/target_pose_retiming_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_after_retiming_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_after_retiming_report.md
```

### 关键结果

| field | before | after |
|---|---:|---:|
| point_count | 275 | 271 |
| removed_duplicate_count | 0 | 4 |
| duration_s | 13.0528205 | 22.039876274 |
| dt_nonpositive_count | 4 | 0 |
| max_speed_m_s | 0.04 | 0.01792 |
| max_accel_m_s2 | 0.533536284 | 0.274132141 |
| max_jerk_m_s3 | 11.386446091 | 4.193553547 |
| recommended_for_coppeliasim_playback | false | true |
| recommended_for_ik_dry_run | false | true |

几何路径长度保持不变：`path_length_delta_m=0.0`。

### 判断

retiming 后默认 weak 行楷山样例已通过 conservative motion-continuity gate，可作为进入 CoppeliaSim playback、真实 IK 前离线检查或低速空跑准备的时间序列版本。该层仍不是真实机器人动力学优化，不做 IK、不连接 AUBO i5、不调用 SDK、不发送机器人命令。

---

## 2026-06-17 Smoothed target poses 接回 AUBO dry-run 默认流程

### 实验目的

上一轮 retiming 已生成 `robot_target_poses_smoothed.csv`，并通过 conservative motion-continuity gate。本轮将后续 AUBO command adapter 和 IK feasibility 的默认样例输入切到 smoothed target poses，同时保留原始 `robot_target_poses.csv` 作为 before-retiming 对照。

### 实现

- 新增 `experiments/llm_style_trajectory/src/target_pose_defaults.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_smoothed_target_pose_default.py`。
- 更新 `aubo_i5_command_adapter.py` 和 `aubo_i5_ik_feasibility.py`：
  - 默认 CLI 未显式传入 `--csv` 时优先选择同目录 `robot_target_poses_smoothed.csv`。
  - 用户显式传入原始 `robot_target_poses.csv` 时不替换。
  - smoothed 输入输出 `_smoothed` 后缀文件，避免覆盖 before-retiming 结果。
  - summary/report 写入 `source_target_pose_csv`、`source_retiming_summary`、`source_retimming_summary` 和 `source_motion_continuity_after_retiming`。

### 输出

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan_smoothed.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_safety_check_smoothed.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan_smoothed.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_smoothed_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_smoothed_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_smoothed_points.csv
```

### 关键结果

| field | before-retiming | after-retiming smoothed |
|---|---:|---:|
| command point_count | 275 | 271 |
| command_count | 277 | 273 |
| command max_speed_m_s | 0.04 | 0.01792 |
| recommended_for_sdk_dry_run | true | true |
| IK feasibility point_count | 275 | 271 |
| IK max_speed_m_s | 0.04 | 0.01792 |
| recommended_for_real_ik_check | true | true |
| warnings | [] | [] |

### 判断

机器人接口准备链路已经统一到 smoothed target poses：原始 target poses 用于展示 before-retiming 问题，smoothed target poses 用于后续 command adapter、IK feasibility 和真实 IK 前离线检查。当前仍不是真实 IK 或实机控制。

---

## 2026-06-16 CoppeliaSim simple pen/tool coordinate calibration layer

- 扩展 `experiments/llm_style_trajectory/coppeliasim/play_workspace_path.py`，
  新增 `--tool-model simple-pen`、`--show-tool-frame`、`--tool-length-mm`、
  `--tool-radius-mm`、`--tcp-offset-mm` 和 `--base-frame-origin-mm`。
- 默认 `--tool-model none` 保持旧的 pen-tip/sphere playback result 文件名；
  启用 simple pen/tool frame 时输出：
  - `coppeliasim_tool_model_result.json`
  - `coppeliasim_tool_model_result.md`
- 固定样例输入：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv`
- 固定样例输出：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_tool_model_result.json`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_tool_model_result.md`
  - `experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_index.md`
- 关键 dry-run 结果：`point_count=275`，`tool_model=simple-pen`，
  `tool_length_mm=120.0`，`tool_radius_mm=4.0`，`tcp_offset_mm=0.0`，
  `max_xy_step_mm=2.487672`，`recommended_for_coordinate_calibration=true`，
  `warnings=[]`。
- 本轮仍是 simple pen/tool visual sanity check，不是 AUBO i5 真实机器人模型、
  不是真实 IK、不做动力学/碰撞检测、不连接实机、不调用 SDK、不发送控制命令。

---

## 2026-06-16 Motion continuity dry-run 检查层

- 新增 `experiments/llm_style_trajectory/src/motion_continuity_check.py`，
  支持 `robot_target_poses.csv` 与 `robot_workspace_trajectory_resampled.csv`
  两类输入。
- 新增 `experiments/llm_style_trajectory/tests/test_motion_continuity_check.py`，
  覆盖正常 target pose、非单调时间、速度尖峰、jerk 尖峰、四元数异常、
  workspace CSV 自动识别，以及不 import AUBO SDK。
- 新增说明文档：
  - `experiments/llm_style_trajectory/docs/motion_continuity_check_notes.md`
- 默认样例输入：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv`
- 默认样例输出：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_summary.json`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_report.md`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_points.csv`
  - `experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_check_index.md`
- 关键结果：`point_count=275`，`max_speed_m_s=0.04`，
  `max_speed_jump_m_s=0.025`，`max_accel_m_s2=0.533536284`，
  `max_jerk_m_s3=11.386446091`，`dt_nonpositive_count=4`，
  `quaternion_normalized=true`，`has_nan_or_inf=false`。
- 推荐状态：`recommended_for_coppeliasim_playback=false`，
  `recommended_for_ik_dry_run=false`。
- 失败原因：存在零时长重复边界点，且保守阈值下 acceleration / jerk 超限。
  后续进入真实 IK dry-run 或低速空跑准备前，应先做去重、retiming 和速度曲线平滑。
- 当前仍是离线 dry-run，不是真实机器人动力学，不做 IK，不连接实机，不调用 SDK，
  不发送控制命令。

---

## 2026-06-16 AUBO i5 command adapter 论文素材整理

### 实验目的

将上一轮 AUBO i5 IK dry-run 命令适配层的结果固定整理为论文/阶段汇报素材，避免后续写作时继续从任务输出目录中手动查找 `aubo_i5_command_plan.csv`、`aubo_i5_safety_check.json` 和报告文件。

本轮只整理已有结果，不新增算法、不运行 IK、不连接真实 AUBO i5、不调用 SDK、不修改 `code/stroke.py` 或 `code/pipeline.py`。

### 源目录

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

源文件：

```text
aubo_i5_command_plan.csv
aubo_i5_safety_check.json
aubo_i5_command_plan.md
```

### 固定整理输出

```text
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_adapter_index.md
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_plan.csv
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_command_plan.md
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_safety_check.json
```

同时更新：

```text
experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md
LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md
PROJECT_LOG.md
```

### 关键指标

| field | value |
|---|---:|
| point_count | 275 |
| command_count | 277 |
| max_step_m | 0.002488 |
| max_speed_m_s | 0.04 |
| max_accel_m_s2_estimate | 0.0 |
| recommended_for_sdk_dry_run | true |
| warnings | [] |

command plan 类型统计：

| command_type | count |
|---|---:|
| move_joint_approach | 1 |
| move_line | 275 |
| move_line_retract | 1 |

### 论文使用方式

建议将该组结果放在第 6 章 CoppeliaSim 标准场景之后，作为“机器人接口准备层”或“AUBO i5 离线命令计划与安全检查”小节。可用于说明系统已经从笔尖路径播放推进到面向真实机械臂 SDK 的离线接口准备，但仍未进入真实 IK 或实机控制。

### 边界说明

- 当前 command plan 是 dry-run only。
- 不做 IK。
- 不连接真实 AUBO i5。
- 不导入或执行 `libpyauboi5`。
- 不使用历史 IP。
- 不调用 `move_joint` / `move_line`。
- 不发送任何真实机器人控制命令。

### 判断

该整理补齐了 AUBO i5 command adapter 在论文图表索引中的固定入口。后续写论文或做 PPT 时，可优先从 `paper_figures/aubo_i5_command_adapter_index.md` 查找这组结果。

---

## 2026-06-15 AUBO i5 IK dry-run 命令适配层 / 离线接口准备

### 实验目的

基于已经生成的 `robot_target_poses.csv`，新增一个离线 AUBO i5 command adapter dry-run，把末端目标位姿序列转换成“未来接入 AUBO i5 SDK 时可能如何调用”的命令计划和安全检查报告。本轮不做真实 IK、不导入或执行 `libpyauboi5`、不连接真实 AUBO i5、不使用历史 IP、不发送任何真实机器人控制命令。

### 实现内容

- 新增 `experiments/llm_style_trajectory/src/aubo_i5_command_adapter.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_aubo_i5_command_adapter.py`。
- 新增 `experiments/llm_style_trajectory/docs/aubo_i5_command_adapter_notes.md`。
- 输出离线三件套：
  - `aubo_i5_command_plan.csv`
  - `aubo_i5_safety_check.json`
  - `aubo_i5_command_plan.md`

### 输入

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_safety_check.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan.md
```

### 命令计划语义

| command_type | 说明 |
|---|---|
| `move_joint_approach` | 到第一个点上方的安全接近位姿，只记录 future `inverse_kin + move_joint` hint，不求 IK |
| `move_line` | 沿目标位姿序列跟随；若输入为 `pen_up_move` 则保留 `pen_down=0` |
| `move_line_retract` | 结束后抬高到安全高度，只记录 future `move_line` hint |

所有命令行均写入 `dry_run_only=true`，`sdk_hint` 只是未来 SDK 接口提示，不会触发真实调用。

### 安全检查结果

| field | value |
|---|---:|
| point_count | 275 |
| command_count | 277 |
| max_step_m | 0.002488 |
| max_speed_m_s | 0.04 |
| max_accel_m_s2_estimate | 0.0 |
| quaternion_normalized | true |
| time_monotonic | true |
| has_nan_or_inf | false |
| recommended_for_sdk_dry_run | true |
| warnings | `[]` |

默认阈值为 `max_step_m <= 0.015`、`max_speed_m_s <= 0.10`、`max_accel_m_s2_estimate <= 0.50`、quaternion norm tolerance `1e-6`。workspace 检查只作为纸面工作空间提示，不判断真实 AUBO i5 可达性、碰撞、奇异位形或关节限位。

### 结论

系统已从 robot end-effector target pose representation 进一步推进到 AUBO i5 SDK dry-run command plan。当前仍是离线接口准备层：不做 IK、不连接实机、不发送 `move_joint` / `move_line`。真正接入 AUBO i5 前，必须重新确认机器人 IP、急停、工具 TCP、夹具、纸面坐标系、速度/加速度限制、可达性和现场安全。

---

## 2026-06-16 AUBO i5 IK feasibility dry-run / 可达性前检查层

### 实验目的

在 `robot_target_poses.csv -> aubo_i5_command_plan.csv` 的离线命令计划之后，新增一个进入真实 IK 检查前的 feasibility gate，用于判断目标末端位姿序列是否具备进入真实 AUBO i5 IK dry-run 的基本数据条件。本轮仍不做真实 IK、不导入或执行 `libpyauboi5`、不连接真实 AUBO i5、不使用历史 IP、不发送机器人控制命令。

### 实现内容

- 新增 `experiments/llm_style_trajectory/src/aubo_i5_ik_feasibility.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_aubo_i5_ik_feasibility.py`。
- 新增 `experiments/llm_style_trajectory/docs/aubo_i5_ik_feasibility_notes.md`。
- 输出：
  - `aubo_i5_ik_feasibility_summary.json`
  - `aubo_i5_ik_feasibility_report.md`
  - `aubo_i5_ik_feasibility_points.csv`
- 固定副本和索引写入 `experiments/llm_style_trajectory/outputs/paper_figures/`。

### 输入

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
```

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_summary.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_points.csv
```

### 固定论文/汇报资料

```text
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_index.md
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_summary.json
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_report.md
experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_points.csv
```

### 检查内容

- target pose 必需字段是否存在。
- XY 是否仍在纸面范围内。
- Z 是否在 `0..8mm` 预期范围内。
- 相邻点距离是否过大。
- 速度是否超过阈值。
- 时间是否单调。
- quaternion 是否归一化。
- 是否存在 NaN / inf。
- 相对 origin 的保守半径 envelope hint。

### 关键结果

| field | value |
|---|---:|
| point_count | 275 |
| xy_range_m | x `[-0.049057, 0.048721]`, y `[-0.049392, 0.049392]` |
| z_range_m | `[0.0, 0.0]` |
| radius_range_m | `[0.000756, 0.064444]` |
| max_step_m | 0.002488 |
| max_speed_m_s | 0.04 |
| time_monotonic | true |
| quaternion_normalized | true |
| has_nan_or_inf | false |
| required_fields_present | true |
| within_conservative_envelope | true |
| recommended_for_real_ik_check | true |
| warnings | `[]` |

### 结论

该层确认当前 weak 行楷山目标位姿具备进入真实 IK dry-run 的基础数据条件。但它不是 AUBO i5 真实 IK，不判断关节限位、碰撞、奇异位形、真实可达性或动力学约束。进入真实 IK 或实机前，仍必须现场确认 TCP、base 坐标系、纸面位姿、机器人 IP、急停、安全边界、工具夹具和速度/加速度限制。

---

## 2026-06-16 IK feasibility 文档入口整理

### 整理目的

上一轮已经完成 AUBO i5 IK feasibility dry-run 和论文固定副本。本轮不新增算法、不运行真实 IK、不连接真实 AUBO i5，只把该层同步到新对话入口、论文图表索引和机器人测试计划中，避免后续切换线程时继续按旧状态理解项目。

### 更新内容

- `CURRENT_PROJECT_GUIDE.md`：当前链路追加 `aubo_i5_ik_feasibility.py`，已完成清单追加 IK feasibility dry-run，下一步建议移到 CoppeliaSim 简单机器人/末端执行器模型、加速度/jerk 检查和论文写作。
- `AGENTS.md`：接手说明追加 AUBO i5 IK feasibility dry-run，并明确不要连接真实机械臂、不要真实 IK、不要调用 SDK 运动命令。
- `README.md`：项目首页追加 IK feasibility 前检查层和离线 dry-run 边界。
- `experiments/llm_style_trajectory/README.md`：补充 command adapter 与 IK feasibility 的论文索引入口。
- `AUBO_I5_PLATFORM_NOTES.md`：将当前已完成层更新到 target poses、command plan 与 IK feasibility dry-run。
- `ROBOT_TEST_PLAN.md`：把机器人测试计划从旧的图片输入路线调整为当前自然语言到轨迹、CoppeliaSim 和 AUBO i5 dry-run 路线。
- `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md` 与 `paper_experiment_index.md`：把 IK feasibility 纳入第 6 章机器人接口准备层和推荐图表入口。

### 边界说明

本轮只是文档整理。当前 AUBO i5 相关工作仍停留在离线 command plan 与 IK feasibility dry-run 前检查，不求真实 IK、不导入或执行 SDK、不连接实机、不发送控制命令。

---

## 2026-06-13 CoppeliaSim 标准书写场景自动创建与场景报告

### 实验目的

在已完成 pen-tip/sphere 最小播放、低负载播放和单次 result 留痕后，本轮将 CoppeliaSim 播放层固定为标准书写场景：自动创建纸面、边界框、坐标轴、笔尖球和路径段，并在 result JSON/Markdown 中记录场景参数、坐标映射和工作空间 bounds 检查。

本轮不调用 API，不接机械臂 IK，不修改 `code/stroke.py` 或 `code/pipeline.py`。

### 实现内容

- `play_workspace_path.py` 新增 `--scene-setup standard`、`--clear-previous-scene`、`--paper-size-mm`、`--pen-tip-radius-mm`、`--show-axes`、`--show-boundary`。
- 标准场景对象统一使用 `llm_style_trajectory_*` 前缀，便于下一次播放前清理。
- dry-run 不连接 CoppeliaSim，但会根据 `paper_size_mm` 和 Z 范围做场景自检。
- result 中新增 `scene_setup`、`paper_size_mm`、`pen_tip_radius_mm`、`axes_enabled`、`boundary_enabled`、`clear_previous_scene`、`coordinate_mapping`、`workspace_bounds`、`scene_warnings`、`recommended_playback`。

### 验证对象

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.md
```

### 关键结果

| field | value |
|---|---:|
| status | finished |
| point_count | 275 |
| simulation_stopped | true |
| scene_setup | standard |
| paper_size_mm | 120.0 |
| pen_tip_radius_mm | 1.5 |
| axes_enabled | true |
| boundary_enabled | true |
| clear_previous_scene | true |
| recommended_playback | true |
| max_step_3d_mm | 2.487672 |
| max_xy_step_mm | 2.487672 |
| max_z_step_mm | 0.0 |

`workspace_bounds` 显示 X/Y 均在 `±60mm` 纸面范围内，Z 在 `0..8mm` 范围内，`scene_warnings=[]`。

### 结论

CoppeliaSim 播放层已支持标准书写场景自动创建和场景报告，可作为后续论文/汇报中固定工作空间定义的基础。用户不需要手动创建纸面、边界或坐标轴，也可以通过 result 文件复查本次播放是否结束、是否自动停止以及是否适合播放。当前仍只是 standard pen-tip/sphere scene，不包含机械臂模型、IK、动力学或控制器。

---

## 2026-06-14 机械臂 IK 前的末端目标点跟随准备层

### 实验目的

在 CoppeliaSim standard pen-tip/sphere playback 之后，进一步把 `robot_workspace_trajectory_resampled.csv` 转换为面向 AUBO i5 / 通用机械臂的末端目标位姿序列 `robot_target_poses.csv`。本轮只生成目标位姿和前检查报告，不做真实 IK、不连接 AUBO i5 实机、不发送控制命令。

### 实现内容

- 新增 `experiments/llm_style_trajectory/src/robot_target_poses.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_robot_target_poses.py`。
- 新增 `experiments/llm_style_trajectory/docs/aubo_i5_target_pose_notes.md`。
- `robot_target_poses.py` 支持：
  - `--csv`
  - `--origin-x-m`
  - `--origin-y-m`
  - `--origin-z-m`
  - `--roll-deg`
  - `--pitch-deg`
  - `--yaw-deg`
- 输出 `robot_target_poses.csv`、`robot_target_pose_report.md`、`robot_target_pose_summary.json`。

### 默认输入

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_pose_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_pose_summary.json
```

### 位姿规则

坐标：

```text
X_m = X_mm / 1000 + origin_x_m
Y_m = Y_mm / 1000 + origin_y_m
Z_m = Z_mm / 1000 + origin_z_m
```

默认姿态：

```text
roll_deg = 180
pitch_deg = 0
yaw_deg = 0
quaternion ~= (qw=0, qx=1, qy=0, qz=0)
```

如果输入 CSV 没有 `t_s`，则根据相邻点 3D 距离和 `speed_mm_s` 积分生成时间；`speed_m_s = speed_mm_s / 1000`。

### 关键结果

| field | value |
|---|---:|
| point_count | 275 |
| duration_s | 13.05282 |
| path_length_m | 0.359531 |
| max_step_m | 0.002488 |
| max_speed_m_s | 0.04 |
| segment_counts | `{"connector": 38, "stroke": 237}` |
| source_x_mm_range | `[-49.057031, 48.721406]` |
| source_y_mm_range | `[-49.392188, 49.392188]` |
| source_z_mm_range | `[0.0, 0.0]` |
| recommended_for_ik_dry_run | true |
| warnings | `[]` |

### 结论

系统已从 pen-tip playback 推进到 robot end-effector target pose representation。该层为 AUBO i5 IK dry-run 前的中间层，已经完成单位转换、固定工具姿态、时间/速度生成和基础安全检查；当前仍不做真实 IK、不控制机械臂。实机前必须重新确认 IP、TCP、夹具、急停、安全范围和现场设备状态。

---

## 2026-06-13 CoppeliaSim 播放评价层：低负载选项与 batch dry-run

### 完成事项

- 修改 `experiments/llm_style_trajectory/coppeliasim/play_workspace_path.py`：
  - 新增 `--display-stride N`，降低 colored path segment 绘制密度，但笔尖仍按完整 CSV 播放。
  - 新增 `--no-path-objects`，只播放 pen-tip sphere，不创建 colored path objects。
  - 新增 `--auto-stop`，播放结束后尝试停止 CoppeliaSim 仿真。
  - dry-run summary 新增 `max_step_3d_mm`、`max_xy_step_mm`、`max_z_step_mm`，保留 `max_step_mm` 作为 3D 兼容字段。
- 新增 `experiments/llm_style_trajectory/coppeliasim/evaluate_playback_batch.py`，批量扫描 `robot_workspace_trajectory_resampled.csv` 并输出 dry-run 检查表和报告。
- 新增/更新测试：
  - `tests/test_coppeliasim_export.py`
  - `tests/test_coppeliasim_playback_eval.py`

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/coppeliasim_playback_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/coppeliasim_playback_report.md
```

### 三组山字 dry-run 指标

| connection | point_count | duration_s | path_length_mm | max_step_3d_mm | max_xy_step_mm | max_z_step_mm | stroke_count | connector_count | pen_up_move_count | out_of_workspace_bounds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | 258 | 12.972534 | 391.530547 | 8.0 | 4.749192 | 8.0 | 237 | 0 | 21 | False |
| weak | 246 | 14.147425 | 359.530547 | 43.046802 | 43.046802 | 0.0 | 237 | 9 | 0 | False |
| normal | 251 | 14.133252 | 359.530547 | 35.523756 | 35.523756 | 0.0 | 237 | 14 | 0 | False |

### 结论

- CoppeliaSim 播放层已支持低负载选项，GUI 高 GPU 占用可通过 `--display-stride` 和 `--no-path-objects` 缓解。
- dry-run 指标已拆分 3D / XY / Z 最大点距，避免把 Z 轴抬笔高度误判为 XY 平面跳点。
- batch dry-run 不依赖 CoppeliaSim GUI 或 ZeroMQ client，可作为仿真前检查层。
- 当前仍只是 pen-tip/sphere playback，不包含机械臂 IK、真实动力学、碰撞检查或控制器。

---

## 2026-06-13 weak/normal 连笔执行层段间跳变修复

### 问题

上一轮 playback dry-run 显示：

- `weak` 行楷山存在约 43mm 的 XY 跳变。
- `normal` 行楷山存在约 35mm 的 XY 跳变。

根因是 `connection_strength` 被用于缩短 connector 几何路径，connector 没有真正到达下一笔起点，随后 stroke 段从下一笔起点开始，形成段间跳变。

### 修复

- `trajectory_tools.insert_connections()`：connector 几何固定为完整 `prev_end -> next_start`。
- `execution_tools.build_execution_trajectory()`：connector 几何固定为完整 `prev_end -> next_start`。
- `connection_strength` 改为只影响 connector 的 pressure / width / speed 映射，不再缩短路径。
- `connection_preference=none` 继续使用 pen-up move，Z 轴抬笔 8mm 保留。

### 新输出

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
experiments/llm_style_trajectory/outputs/batch_20260613_154131/coppeliasim_playback_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_154131/coppeliasim_playback_report.md
```

### 三组山字验收

| connection | max_step_3d_mm | max_xy_step_mm | max_z_step_mm | connector_count | pen_up_move_count |
|---|---:|---:|---:|---:|---:|
| none | 8.0 | 4.749192 | 8.0 | 0 | 21 |
| weak | 2.487672 | 2.487672 | 0.0 | 38 | 0 |
| normal | 2.487672 | 2.487672 | 0.0 | 38 | 0 |

### 结论

weak/normal 的 35mm / 43mm XY 段间跳变已消失；重采样后 connector 最大 XY 步长约 2.488mm，满足接近 `connector <= 2.5mm` 的验收目标。none 仍保留 8mm 抬笔高度，且 XY 最大步长小于 5mm。

---

## 2026-06-13 CoppeliaSim 播放完成反馈与结果留痕

### 完成事项

- `play_workspace_path.py` 的 dry-run 和真实播放都会输出明确 JSON summary。
- 新增 `--result-out-dir`，默认仍把单次 playback result 写到 CSV 所在目录。
- 每次 dry-run 或真实播放都会生成：
  - `coppeliasim_playback_result.json`
  - `coppeliasim_playback_result.md`
- summary/result 记录：
  - `status`
  - `point_count`
  - `segment_type_counts`
  - `duration_estimate_s`
  - `speed_scale`
  - `display_stride`
  - `path_objects_enabled`
  - `auto_stop`
  - `simulation_stopped`
  - `max_step_3d_mm`
  - `max_xy_step_mm`
  - `max_z_step_mm`
  - `x/y/z range`
  - `dry_run`
  - 当前范围说明：`pen-tip/sphere playback only, no robot IK`

### 验证对象

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv
```

### 输出文件

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.json
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.md
```

### dry-run 摘要

| status | point_count | display_stride | auto_stop | path_objects_enabled | simulation_stopped | max_step_3d_mm | max_xy_step_mm | max_z_step_mm |
|---|---:|---:|---|---|---|---:|---:|---:|
| dry_run | 275 | 5 | True | True | False | 2.487672 | 2.487672 | 0.0 |

### 结论

用户现在可以通过终端 JSON 和任务目录 result 文件确认播放是否结束、播放了多少点、是否启用 auto-stop，以及最大跳点指标；不再需要只靠观察 CoppeliaSim GUI 判断播放完成。当前仍只是 pen-tip/sphere playback，不包含机械臂 IK、真实动力学或控制器。

---

## 2026-06-13 修复后论文图表主版本刷新

### 整理目的

将 `weak/normal` connector 几何连续性修复后的结果设为后续论文/汇报的主版本，避免继续引用存在 35mm / 43mm XY 段间跳变的旧 batch。

### 主版本 batch

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/
```

旧 batch `batch_20260613_092733/` 保留为“发现段间跳变问题”的历史记录，不再作为连笔、execution layer、workspace resampling 和 CoppeliaSim dry-run 的最终展示结果。

### 固定图表刷新

已将以下固定图表更新到修复后版本：

```text
experiments/llm_style_trajectory/outputs/paper_figures/fig_modifier_connection_shan.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_ablation_shan.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_workspace_ablation_shan.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_workspace_resampling_shan.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_none_render.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_weak_render.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_normal_render.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_none_debug.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_weak_debug.png
experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_normal_debug.png
```

同步更新：

```text
experiments/llm_style_trajectory/outputs/paper_figures/execution_ablation_table.md
experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md
LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md
```

### 修复后关键口径

- connector 几何必须完整连接上一笔终点与下一笔起点。
- `connection_strength` 不再控制连接几何长度，只控制 connector 的 `pressure`、`width`、`speed` 等执行属性。
- `weak` 与 `normal` 的几何连接长度可以相同，但 `normal` 的连接压力和宽度更高。
- 修复后三组山字 CoppeliaSim dry-run：`none max_xy=4.749192mm`、`weak max_xy=2.487672mm`、`normal max_xy=2.487672mm`。

---

## 2026-06-13 CoppeliaSim 标准场景论文图与结果留痕整理

### 整理目的

在完成 standard scene 自动创建与真实播放后，将可用于论文/汇报的仿真工作空间素材固定到 `paper_figures`，避免后续临时截图或误用旧 batch。

### 来源

```text
experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/
```

### 固定资料

```text
experiments/llm_style_trajectory/outputs/paper_figures/fig_coppeliasim_standard_scene_shan.png
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_standard_scene_result.json
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_standard_scene_result.md
experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_standard_scene_index.md
```

### 关键结果

| status | simulation_stopped | recommended_playback | point_count | max_xy_step_mm | max_z_step_mm | paper_size_mm |
|---|---|---|---:|---:|---:|---:|
| finished | true | true | 275 | 2.487672 | 0.0 | 120.0 |

### 结论

标准 CoppeliaSim 纸面场景已经具备固定论文素材：`120mm x 120mm` 纸面、坐标轴、边界、weak 行楷山路径和真实播放 result。当前仍是 pen-tip/sphere scene，不包含机械臂 IK、动力学、碰撞检测或控制器调参。

---

## 2026-06-13 CoppeliaSim 最小笔尖轨迹播放验证

### 实验目的

在完成 `robot_workspace_trajectory_resampled.csv` 后，验证工作空间轨迹是否可以进入三维仿真环境播放。当前目标不是机械臂 IK 或真实控制，而是先确认：

- CoppeliaSim ZeroMQ remote API 可以连接。
- 重采样后的 CSV 能被脚本读取并映射到仿真单位。
- 仿真中可以看到纸面、笔尖球体和路径段可视化。

### 环境与配置

CoppeliaSim Edu 解压位置：

```text
D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win
```

在进入项目目录的 PowerShell 中设置 CoppeliaSim Python client 路径：

```powershell
$env:PYTHONPATH="D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win\programming\zmqRemoteApi\clients\python\src;$env:PYTHONPATH"
```

补充 Python 依赖：

```powershell
python -m pip install pyzmq cbor
```

导入检查：

```powershell
python -c "from coppeliasim_zmqremoteapi_client import RemoteAPIClient; print('ok')"
```

### 验证对象

```text
experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv
```

### dry-run 结果

```json
{
  "point_count": 258,
  "segment_type_counts": {
    "pen_up_move": 21,
    "stroke": 237
  },
  "x_mm_range": [-49.057031, 48.721406],
  "y_mm_range": [-49.392188, 49.392188],
  "z_mm_range": [0.0, 8.0],
  "duration_estimate_s": 12.972534,
  "max_step_mm": 8.0
}
```

### 真实播放命令

先启动：

```powershell
D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win\coppeliaSim.exe
```

再运行：

```powershell
python experiments\llm_style_trajectory\coppeliasim\play_workspace_path.py `
  --csv experiments\llm_style_trajectory\outputs\batch_20260613_092733\u5c71_xingkai_20260613_092733_979792\robot_workspace_trajectory_resampled.csv `
  --speed-scale 1.0
```

### 结论

- 真实 CoppeliaSim 播放已成功。
- 当前验证的是 paper plane + pen-tip sphere + colored path segments 的最小播放链路。
- 还没有接入机械臂模型、逆运动学、末端工具标定、碰撞检测或控制器调参。
- dry-run 中 `max_step_mm=8.0` 是三维相邻点距离，可能包含 Z 轴 0mm 到 8mm 的抬笔高度变化；后续应拆分为 `max_step_3d_mm`、`max_xy_step_mm` 和 `max_z_step_mm`。
- 这一步说明前面的 workspace mapping / resampling 结果已经具备进入三维仿真环境的基本可用性。

---

## 2026-06-13 二维虚拟书写执行层增强

### 实验目的

在不改变旧 `trajectory.csv` 的中心线格式前提下，新增面向虚拟书写和后续机器人仿真的 execution trajectory。目标是让 `width`、`pressure`、`speed`、`pen_down`、`connector` 等执行状态进入 CSV、渲染图和 summary，特别是让“不要连笔 / 默认 weak / 更连贯 normal”的行楷山在视觉和指标上形成更清晰差异。

本轮只使用 `mock` planner 和本地确定性工具，未调用 API，未接入 CoppeliaSim / RoboDK，未修改 `code/stroke.py` 或 `code/pipeline.py`。

### 实现内容

- 新增 `experiments/llm_style_trajectory/src/execution_tools.py`。
- `run_demo.py` 为每个任务额外输出：
  - `execution_trajectory.csv`
  - `execution_render.png`
  - `execution_debug.png`
- `execution_trajectory.csv` 字段包含：
  - `stroke_id`
  - `point_id`
  - `y`
  - `x`
  - `z`
  - `speed`
  - `pressure`
  - `width`
  - `pen_down`
  - `is_connector`
  - `segment_type`
- `segment_type` 支持 `stroke`、`connector`、`pen_up_move`。
- `modifier_summary.csv` / `summary.json` 新增执行层指标：
  - `stroke_draw_length`
  - `connector_draw_length`
  - `pen_up_move_length`
  - `mean_pressure`
  - `mean_width`
  - `connector_mean_pressure`
  - `connector_mean_width`
- 批量输出新增 `execution_ablation_<char_id>.png`，用于对比 none / weak / normal 的虚拟书写效果。

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/
experiments/llm_style_trajectory/outputs/batch_20260613_092733/modifier_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/execution_ablation_u5c71.png
```

### 山字 execution ablation 指标

| task | connection_preference | connector_draw_length | pen_up_move_length | connector_mean_pressure | connector_mean_width | mean_width | mean_pressure |
|---|---:|---:|---:|---:|---:|---:|---:|
| 写一个不要连笔的行楷山 | none | 0.000 | 188.929 | 0.000 | 0.000 | 9.500000 | 1.000000 |
| 写一个行楷风格的山 | weak | 33.251 | 0.000 | 0.340 | 4.275 | 9.215798 | 0.964101 |
| 写一个更连贯的行楷山 | normal | 60.457 | 0.000 | 0.680 | 6.840 | 9.248145 | 0.969702 |

### 结论

- `none` 任务没有 connector draw segment，仍保留抬笔移动长度，符合“不要连笔”的执行语义。
- 默认行楷 `weak` 连接段有痕迹，但压力和宽度明显低于普通笔画。
- 更连贯行楷 `normal` 的连接段更长，且 `connector_mean_pressure` / `connector_mean_width` 均高于 weak，能在执行层和渲染层体现“更连贯”的语义强度。
- 旧 `trajectory.csv` 仍保留原 `y,x` + `nan,nan` 格式，execution layer 作为独立增强输出，不破坏已有下游。

### 验证

```text
python -m pytest experiments\llm_style_trajectory\tests -q
53 passed, 15 warnings
```

warnings 为 Matplotlib 默认字体缺少中文 glyph 的预览图标题提示，不影响 execution trajectory、modifier 映射或渲染输出。

---

## 2026-06-13 机器人工作空间映射与仿真前检查层

### 实验目的

在不接 CoppeliaSim / RoboDK 的前提下，将 `execution_trajectory.csv` 从图像坐标系映射到机器人纸面工作空间，生成 `robot_workspace_trajectory.csv`，并进行越界、Z 轴抬笔高度、相邻点跳变和执行状态一致性检查，为后续三维仿真准备输入。

本轮只处理 `experiments/llm_style_trajectory/outputs/batch_20260613_092733/` 的已有 execution 输出，未调用 API，未修改 `code/stroke.py` 或 `code/pipeline.py`。

### 实现内容

- 新增 `experiments/llm_style_trajectory/src/workspace_mapping.py`。
- 输入：单任务目录或 batch 目录下的 `execution_trajectory.csv`。
- 每个任务目录输出：
  - `robot_workspace_trajectory.csv`
  - `workspace_validation_report.md`
  - `workspace_path_preview.png`
- batch 根目录输出：
  - `workspace_mapping_summary.csv`
  - `workspace_mapping_report.md`
  - `workspace_ablation_u5c71.png`
- 新增 `experiments/llm_style_trajectory/tests/test_workspace_mapping.py`。

### 映射规则

默认参数：

```text
image_size = 256
paper_width_mm = 120
paper_height_mm = 120
pen_up_height_mm = 8
base_speed_mm_s = 30
```

坐标映射：

```text
X_mm = (x / image_size - 0.5) * paper_width_mm
Y_mm = (0.5 - y / image_size) * paper_height_mm
speed_mm_s = base_speed_mm_s * execution_speed
```

Z 轴规则：

```text
stroke / connector 且 pen_down=1 -> Z_mm=0
pen_up_move 或 pen_down=0 -> Z_mm=8
```

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_mapping_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_mapping_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_ablation_u5c71.png
```

### 山字 workspace mapping 指标

| task | segment_counts | workspace_path_length_mm | max_step_mm | large_jump | out_of_bounds | z_range | pen_up_move_length_mm |
|---|---|---:|---:|---|---|---|---:|
| 写一个不要连笔的行楷山 | `{"pen_up_move": 2, "stroke": 3}` | 359.531 | 52.241 | True | False | 0.000..8.000 | 88.560 |
| 写一个行楷风格的山 | `{"connector": 2, "stroke": 3}` | 286.557 | 9.194 | False | False | 0.000..0.000 | 0.000 |
| 写一个更连贯的行楷山 | `{"connector": 2, "stroke": 3}` | 299.310 | 16.717 | True | False | 0.000..0.000 | 0.000 |

### 质检结论

- 三组山字轨迹均未超出 120mm x 120mm 纸面边界。
- `pen_up_move` 的 Z 轴高度为 8mm，stroke/connector 的 Z 轴高度为 0mm。
- `none` 的 `large_jump=True` 来自长距离抬笔移动，属于可解释的仿真前检查提示。
- `normal` 的 `max_step_mm=16.717` 略高于 15mm 阈值，说明后续进入仿真前应考虑 connector 重采样或速度规划。
- 本轮只完成二维工作空间映射和检查报告，不涉及三维机械臂控制或仿真器接口。

### 验证

```text
python -m pytest experiments\llm_style_trajectory\tests\test_workspace_mapping.py -q
5 passed
```

---

## 2026-06-13 三字体基础风格对比实验

### 实验目的

前几轮主要验证的是 `style_modifiers` 对同一基础风格的影响。本轮固定同一批汉字，对比 `kaishu`、`xingkai`、`lishu` 三种基础 style profile 本身在 trajectory、execution、workspace 三层上的差异，补充论文/汇报中“基础风格参数是否有效”的证据。

本轮只使用 `mock` planner、本地 style profile、execution layer 和 workspace mapping，未调用 API，未接 CoppeliaSim / RoboDK，未修改 `code/stroke.py` 或 `code/pipeline.py`。

### 配置与实现

- 新增任务配置：`experiments/llm_style_trajectory/configs/style_profile_compare_tasks.json`。
- 新增批处理脚本：`experiments/llm_style_trajectory/src/style_profile_compare.py`。
- 新增测试：`experiments/llm_style_trajectory/tests/test_style_profile_compare.py`。
- 任务覆盖 5 个字：`山`、`中`、`永`、`福`、`明`。
- 每个字生成 3 种风格：`kaishu`、`xingkai`、`lishu`，共 15 个任务。
- 每个任务输出：
  - `plan.json`
  - `trajectory.csv`
  - `execution_trajectory.csv`
  - `robot_workspace_trajectory.csv`
  - `preview.png`
  - `execution_render.png`
  - `execution_debug.png`
  - `workspace_path_preview.png`
  - `summary.json`

### 输出位置

```text
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_profile_compare_summary.csv
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_profile_compare_report.md
experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_compare_grid.png
```

每字三风格对比图：

```text
style_compare_u5c71.png  # 山
style_compare_u4e2d.png  # 中
style_compare_u6c38.png  # 永
style_compare_u798f.png  # 福
style_compare_u660e.png  # 明
```

### 三种基础风格平均指标

| style | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |
|---|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 0.920111 | 772.899 | 0.000 | 0.000 | 9.000000 | 602.907 | 0 |
| xingkai | 0.966550 | 863.159 | 5.600 | 90.279 | 8.991667 | 404.606 | 0 |
| lishu | 1.322317 | 758.556 | 0.000 | 0.000 | 10.000000 | 588.240 | 0 |

### 质检结论

- 15 个任务均生成成功，5 个字都具备三种 style 结果。
- `lishu` 的平均 `aspect_ratio=1.322317`，明显高于 `kaishu=0.920111` 和 `xingkai=0.966550`，说明隶书 profile 的宽扁倾向在几何指标中可见。
- `xingkai` 的 `avg_connection_count=5.600`、`avg_connector_draw_length=90.279`，说明行楷 profile 默认弱连接能够在 execution layer 中体现。
- `kaishu` 的连接指标为 0，保持保守、无跨笔连接，可作为基础结构轨迹基准。
- 三种 style 的 `out_of_bounds_count` 均为 0，说明当前参数化变换在 120mm x 120mm 工作空间内可用。
- 边界说明：当前比较的是人工/估计结合的参数化 style profile 效果，不是完整真实书法风格学习。

### 验证

```text
python -m pytest experiments\llm_style_trajectory\tests\test_style_profile_compare.py -q
2 passed, 5 warnings
```

warnings 为 Matplotlib 默认字体缺少中文 glyph 的预览图标题提示，不影响 trajectory、execution 或 workspace 输出。

---

## 2026-06-13 workspace trajectory 重采样与速度规划

### 实验目的

上一轮 workspace mapping 发现 `不要连笔行楷山` 的 `pen_up_move` 最大点距约 52.241mm，`更连贯行楷山` 的 connector 最大点距约 16.717mm。为降低后续 CoppeliaSim / RoboDK 末端轨迹仿真前的跳点风险，本轮对 `robot_workspace_trajectory.csv` 做分段线性重采样和分段常数速度规划。

本轮不修改旧 `trajectory.csv`、`execution_trajectory.csv` 或 `robot_workspace_trajectory.csv`，只新增 `_resampled` 输出；未调用 API，未接仿真器，未修改 `code/stroke.py` 或 `code/pipeline.py`。

### 实现内容

- 新增 `experiments/llm_style_trajectory/src/workspace_resampling.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_workspace_resampling.py`。
- 每个任务目录输出：
  - `robot_workspace_trajectory_resampled.csv`
  - `workspace_resampling_report.md`
  - `workspace_resampled_preview.png`
- batch 根目录输出：
  - `workspace_resampling_summary.csv`
  - `workspace_resampling_report.md`
  - `workspace_resampling_ablation_u5c71.png`

### 重采样与速度规则

最大点距：

```text
stroke <= 2.0 mm
connector <= 2.5 mm
pen_up_move <= 5.0 mm
```

速度规划：

```text
stroke = 25 mm/s
weak connector = 40 mm/s
normal connector = 32 mm/s
pen_up_move = 70 mm/s
```

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_resampling_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_resampling_report.md
experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_resampling_ablation_u5c71.png
```

### 山字重采样前后对比

| task | original_point_count | resampled_point_count | original_max_step_mm | resampled_max_step_mm | original_path_length_mm | resampled_path_length_mm | estimated_duration_s | max_speed_mm_s | stroke_max_step_mm | connector_max_step_mm | pen_up_move_max_step_mm |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 写一个不要连笔的行楷山 | 125 | 258 | 52.241 | 4.749 | 359.531 | 359.531 | 12.103962 | 70.0 | 1.888 | 0.000 | 4.749 |
| 写一个行楷风格的山 | 125 | 246 | 9.194 | 2.299 | 286.557 | 286.557 | 11.228480 | 40.0 | 1.888 | 2.299 | 0.000 |
| 写一个更连贯的行楷山 | 125 | 251 | 16.717 | 2.388 | 299.310 | 299.310 | 11.724427 | 32.0 | 1.888 | 2.388 | 0.000 |

### 质检结论

- `不要连笔行楷山` 的抬笔大跳点从 52.241mm 降到 4.749mm，满足 `pen_up_move <= 5.0mm`。
- `更连贯行楷山` 的 connector 超阈值从 16.717mm 降到 2.388mm，满足 `connector <= 2.5mm`。
- stroke 段最大点距为 1.888mm，满足 `stroke <= 2.0mm`。
- 重采样前后路径长度保持一致，说明线性插值没有改变几何路径。
- 本轮只是仿真前后处理，后续若接 CoppeliaSim / RoboDK，可继续在此基础上加入 S 曲线或加速度限制。

### 验证

```text
python -m pytest experiments\llm_style_trajectory\tests\test_workspace_resampling.py -q
5 passed
```

### 判断

这轮调整后，`none / weak / normal` 在 `connection_strength`、`path_length` 和 `pen_up_count` 上形成了清晰梯度：不连笔保留两次抬笔，默认行楷生成较弱连接，更连贯行楷生成更长连接。该结果适合作为论文中“自然语言约束通过受控 modifier 影响确定性轨迹工具”的小型有效性验证。

---

## 2026-06-13 style modifiers 宽扁与圆滑 ablation

### 实验目的

在已完成“连笔语义”梯度实验后，继续验证另外两类自然语言约束：

- 宽扁 / 更宽：是否能通过 `shape_emphasis` 改变 `horizontal_scale`、`vertical_scale` 和字形 bbox。
- 圆滑 / 平滑 / 保守：是否能通过 `smoothness_level` 改变平滑参数和转向指标。

本轮仍只使用 `mock` planner，不调用 API，不允许 LLM 直接生成 CSV、轨迹点或任意数值参数。

### 实现调整

- 新增 `configs/modifier_shape_smoothness_tasks.json`。
- `modifier_summary.csv` 增加 `bbox_width`、`bbox_height`、`total_turning_angle`、`max_turning_angle`。
- 新增专用对比图输出：
  - `modifier_ablation_shape_<char_id>.png`
  - `modifier_ablation_smoothness_<char_id>.png`
- 补充“圆润 / 更圆润”到 `smoothness_level=high` 的规则解析。

### 输出位置

```text
experiments/llm_style_trajectory/outputs/batch_20260613_085440/
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_summary.csv
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_shape_u4e2d.png
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_smoothness_u6c38.png
```

### 宽扁语义：中

| task | shape_emphasis | horizontal_scale | vertical_scale | bbox_width | bbox_height | aspect_ratio |
|---|---:|---:|---:|---:|---:|---:|
| 写一个隶书风格的中 | normal | 1.18 | 0.82 | 175.851 | 176.333 | 0.997268 |
| 写一个宽扁一点的隶书中 | flatter | 1.298 | 0.7544 | 193.446 | 162.226 | 1.192443 |
| 写一个更宽的隶书中 | wider | 1.2744 | 0.82 | 190.540 | 176.333 | 1.080569 |

结论：`flatter` 同时增宽并压低高度，aspect ratio 提升最大；`wider` 主要增宽，保留原高度，符合“更宽但不明显压扁”的语义边界。

### 圆滑语义：永

| task | smoothness_level | smoothness | path_length | mean_turning | total_turning_angle | max_turning_angle | connection_preference | connection_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 写一个楷书风格的永 | medium | 0.18 | 649.156 | 0.099365 | 10.632062 | 0.971813 | weak | 0 |
| 写一个更圆滑的楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 写一个更平滑的楷书永 | high | 0.305 | 647.360 | 0.098744 | 10.565580 | 0.895203 | weak | 0 |
| 写一个更保守的行楷永 | low | 0.231 | 653.408 | 0.081651 | 10.696220 | 1.048066 | none | 0 |

结论：`mean_turning` 变化较小，因此补充 `total_turning_angle` 和 `max_turning_angle` 更能说明“圆滑/平滑”的效果：high smoothness 使总转向量和最大转向角下降，路径长度略降；“更保守”取消跨笔连接，并降低行楷平滑参数。

### 验证

```text
python -m pytest experiments\llm_style_trajectory\tests -q
49 passed, 11 warnings
```

warnings 为 Matplotlib 默认字体缺少中文 glyph 的预览图标题提示，不影响 planner、modifier 映射或轨迹生成。
# 2026-06-18 Connector / brush 可视化诊断图包

- 新增 `experiments/llm_style_trajectory/src/connector_brush_visual_diagnostics.py`，基于上一轮 `style_visual_audit_20260617_224321` 自动生成 connector / brush 视觉诊断图包。
- 新增 `experiments/llm_style_trajectory/tests/test_connector_brush_visual_diagnostics.py`，覆盖 fake candidates、legend、connector overlay、缺样本 warning、`needs_user_review` 字段和不 import `libpyauboi5`。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/connector_brush_visual_diagnostics_20260618_093510/`。
- 输出文件：`connector_brush_diagnostic_report.md`、`connector_brush_diagnostic_cases.csv`、`connector_brush_image_manifest.csv`、`selected_cases/`、`figures/`。
- 关键图：`segment_legend.png`、`connector_overlay_u56fd_xingkai.png`、`connector_overlay_u5fb7_xingkai.png`、`connector_overlay_u798f_xingkai.png`、`brush_width_diagnostic_u4eba_xingkai.png`、`style_side_by_side_u4eba.png`、`style_side_by_side_u4e2d.png`、`style_side_by_side_u548c.png`、`lishu_deformation_u4eba.png`、`lishu_deformation_u597d.png`、`lishu_deformation_u98ce.png`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/connector_brush_visual_diagnostics_index.md`。
- 本轮结论：旧 selected_images 中的灰线/浅线需要用 segment-aware 图重新解释；固定墨迹渲染可能隐藏 connector width/pressure 差异；当前 lishu 视觉差异仍主要来自全局宽扁变形，需要人工看图确认。该轮不调参数、不调用 API、不连接 CoppeliaSim/AUBO i5、不做 IK/SDK/机器人控制。
# 2026-06-18 宽度 / 压力渐变可视化诊断

- 新增 `experiments/llm_style_trajectory/src/width_pressure_visualization.py`，从 `connector_brush_diagnostic_cases.csv` 自动读取对应样本目录的 `execution_trajectory.csv`，生成 width / pressure 渐变诊断图。
- 新增 `experiments/llm_style_trajectory/tests/test_width_pressure_visualization.py`，覆盖 fake execution CSV、global/per-image normalization、无 connector 容错、stroke width nearly constant 标记、manifest 字段、报告关键词和不 import `libpyauboi5`。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/width_pressure_visualization_20260618_101349/`。
- 输出文件：`width_pressure_visualization_report.md`、`width_pressure_visualization_manifest.csv`、`width_pressure_value_ranges.json`、`figures/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/width_pressure_visualization_index.md`。
- 关键范围：global width `4.245..10.0`，global pressure `0.338..1.0`；stroke width `9.0..10.0`，connector width `4.245..4.245`；stroke pressure `1.0..1.0`，connector pressure `0.338..0.338`。
- 诊断结论：6 个行楷样本 connector 明显更细、更低压；16 个样本主体 stroke width 基本恒定。当前旧图看不出主体笔画内部粗细变化，主要是因为 execution 数据中的 stroke 内部宽度/压力变化不足，不是可视化失败。
- 本轮不调参数，不修改 `execution_trajectory.csv`，不调用 API，不连接 CoppeliaSim/AUBO i5，不做 IK/SDK/机器人控制。

# 2026-06-18 Execution refinement：connector 收紧 + stroke taper + 可见性改进

- 新增 `experiments/llm_style_trajectory/configs/execution_refinement_profiles.json`，记录 baseline / conservative connector rule、flat / simple_taper stroke width profile 和 non-white 可读色阶。
- 新增 `experiments/llm_style_trajectory/src/execution_refinement.py`，提供 execution rows 层面的 connector gate、stroke taper 和 before/after metrics。
- 以最小侵入方式扩展 `execution_tools.build_execution_trajectory(...)`：默认仍保持旧行为，只有显式传入 `connector_rule` 或 `stroke_width_profile` 时才启用 refinement。
- 扩展 `width_pressure_visualization.py`，支持 `--background-color`、`--min-alpha`、`--min-visible-linewidth` 和非白浅色端配置。
- 新增 `experiments/llm_style_trajectory/src/execution_refinement_experiment.py`，从上一轮 connector brush visual diagnostics 中选取 `国/德/福/人/中/和` 行楷以及 `人` 楷书/隶书样本，生成 before/after 图与指标。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/execution_refinement_20260618_104837/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_index.md`。
- 关键结果：`国/德/福/和` 行楷 connector 数量显著下降；所有样本 stroke width range 从 0 打开到约 3px；浅色端距离白色至少 0.680886。
- 边界：本轮不是最终行楷规则，不是真实笔刷模型，不解决 lishu 真实风格来源问题；仍需用户人工看图确认后再决定下一步调参。

# 2026-06-18 Execution refinement 人工反馈归档

- 新增 `experiments/llm_style_trajectory/docs/execution_refinement_decision.md`。
- 在 `experiments/llm_style_trajectory/configs/execution_refinement_profiles.json` 中新增 `candidate_defaults.candidate_default_v1`。
- `candidate_default_v1` 指向 `connector_rule=conservative` 与 `stroke_width_profile=simple_taper`，状态为 `accepted_for_next_round_candidate`。
- 人工反馈：行楷 connector 自然度改善但略偏保守，暂时接受；stroke taper 可见且效果不错；隶书未观察到连笔。
- 可疑字段核查：`人/lishu` refined execution 中无 `segment_type=connector`，无 `is_connector=1`；summary 中 `after_connector_draw_length=0.0`，`3.3998` 实为 `after_stroke_width_range`。
- 更新 `execution_refinement_report.md`、`execution_refinement_index.md` 和 `paper_experiment_index.md`，明确该候选版本不是全局默认，后续可设计 `balanced` connector 档位。
- 本轮不继续调参数、不扩大实验、不接机器人接口、不调用 API/CoppeliaSim/AUBO i5/SDK。

# 2026-06-18 candidate_default_v1 多样本验证

- 新增 `experiments/llm_style_trajectory/src/execution_refinement_validation.py`，对 `candidate_default_v1` 执行多样本 before/after 验证。
- 新增 `experiments/llm_style_trajectory/tests/test_execution_refinement_validation.py`，覆盖候选默认配置读取、缺样本不中断、行楷 connector 收敛、楷/隶无 connector violation、stroke taper 生效和不 import SDK。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/execution_refinement_validation_20260618_120238/`。
- 输出：`execution_refinement_validation_summary.csv`、`execution_refinement_validation_report.md`、`execution_refinement_validation_manifest.csv`、`execution_refinement_validation_failures.csv` 和 `figures/` 下的 before/after、connector overlay、width/pressure 图。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_validation_index.md`。
- 样本统计：18 个样本全部成功，失败 0；其中行楷 8 个，楷/隶 10 个。
- 行楷 connector 汇总：`connection_count` 从 58 降到 5，`connector_draw_length` 从 4938.116 降到 349.252；4/8 个行楷样本仍保留少量 connector。
- 楷书/隶书 connector violation 为 0；simple_taper 后平均 `stroke_width_range` 为 3.2295。
- 本轮只做候选默认验证与人工看图包，不继续调 connector 或 taper 参数，不调用 API，不连接 CoppeliaSim/AUBO i5，不做 IK/SDK/机器人命令。

# 2026-06-18 balanced connector + 行楷局部风格增强实验

- 新增 `connector_rules.balanced`、`connector_shapes.slight_curve`、`stroke_width_profiles.xingkai_expressive_taper` 到 `execution_refinement_profiles.json`。
- 扩展 `execution_refinement.py`，支持短 connector 优先、curved connector 生成和可选 connector shape；扩展 `execution_tools.py` 透传 `connector_shape`，默认行为保持不变。
- 新增 `experiments/llm_style_trajectory/src/xingkai_balanced_experiment.py`，复用上一轮 validation cases 生成 baseline / conservative / balanced 三档对照。
- 新增 `experiments/llm_style_trajectory/tests/test_xingkai_balanced_refinement.py`，覆盖 balanced 介于 baseline/conservative、none/kaishu/lishu 不误连、slight_curve 非直线、实验输出和不 import SDK。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/xingkai_balanced_experiment_20260618_141424/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/xingkai_balanced_experiment_index.md`。
- 行楷汇总：baseline connection_count=58，conservative=5，balanced=10；baseline connector_draw_length=4938.116，conservative=349.252，balanced=586.339。
- 8 个行楷样本中 balanced 均未回到全连；`国/德/明/林` 比 conservative 增加少量 connector，`中/人` 仍清零，需要人工看图判断是否仍偏保守。
- 楷书/隶书 connector violation 为 0。
- 本轮只做轨迹/执行层风格实验与可视化对比，不调用 API，不连接 CoppeliaSim/AUBO i5，不做 IK/SDK/机器人命令，不修改 shared data 或 legacy。

# 2026-06-18 balanced 行楷 refinement 人工反馈归档

- 在 `experiments/llm_style_trajectory/configs/execution_refinement_profiles.json` 中新增 `candidate_default_v2`。
- `candidate_default_v2` 指向 `connector_rule=balanced`、`connector_shape=slight_curve`、`stroke_width_profile=xingkai_expressive_taper`，状态为 `accepted_for_next_round_candidate`。
- 新增决策文档：`experiments/llm_style_trajectory/docs/xingkai_balanced_decision.md`。
- 记录用户人工反馈：每个字基本只多一笔连笔，变化不激进；`福` 数量仍为 1 但位置变化；balanced 效果可以接受；曲线 connector 更像“带过去”；当前仍不直接进入仿真书写。
- 保留 `candidate_default_v1` 作为 conservative refined baseline，不替换全局默认。
- 本轮只做配置 metadata、决策文档和测试，不继续调参数，不扩大实验，不接机器人接口，不调用 API/CoppeliaSim/AUBO i5/SDK。

# 2026-06-18 Font-driven style gap analysis / 字体轮廓驱动的风格差距诊断

- 新增 `experiments/llm_style_trajectory/configs/font_style_gap_chars.json`，固定 18 个常用字与 kaishu/xingkai/lishu 三风格。
- 新增 `experiments/llm_style_trajectory/src/font_style_gap_analysis.py`，从 `style_sources.json` 渲染真实字体轮廓，并与 `style_diagnostics_20260617_200746/style_diagnostic_summary.csv` 的当前轨迹指标对齐比较。
- 新增 `experiments/llm_style_trajectory/tests/test_font_style_gap_analysis.py`，覆盖字体缺失容错、二值图指标、gap 计算、报告关键词和不 import `libpyauboi5`。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/font_style_gap_analysis_20260618_144838/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_style_gap_analysis_index.md`。
- 输出文件：`font_style_gap_summary.csv`、`font_style_gap_style_means.csv`、`font_style_gap_char_report.csv`、`font_style_gap_failures.csv`、`font_style_gap_report.md` 和 `figures/`。
- 代表图：`font_style_grid.png`、`font_vs_trajectory_aspect_ratio.png`、`lishu_flatness_gap.png`、`xingkai_connectedness_gap.png`、`style_separation_gap.png`。

样本统计：

| total | rendered_success | failures |
|---:|---:|---:|
| 54 | 54 | 0 |

三风格均值：

| style | samples | mean_font_aspect_ratio | mean_trajectory_aspect_ratio | mean_abs_aspect_ratio_gap | mean_font_components | mean_trajectory_connections | mean_font_stroke_width | mean_trajectory_mean_width |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kaishu | 18 | 1.029878 | 1.018672 | 0.058451 | 2.888889 | 0.0 | 6.320909 | 9.0 |
| xingkai | 18 | 0.989059 | 1.070791 | 0.126632 | 1.555556 | 6.055556 | 9.575023 | 7.488813 |
| lishu | 18 | 1.480275 | 1.465173 | 0.110869 | 2.5 | 0.0 | 8.956169 | 10.0 |

诊断结论：

- `lishu` 字体与当前轨迹的平均 aspect ratio 接近，但这主要支持“全局宽扁比例接近”，不能说明当前轨迹已经学到真实隶书笔画结构。
- `xingkai` 字体 connected component 与当前轨迹 connector 指标只能弱对应；当前轨迹的平均 connection_count 更高，说明 connector prior 仍然偏人工规则。
- `kaishu` 的 aspect ratio gap 最小，符合 Make Me a Hanzi median 基底更接近楷书的判断。
- 下一步更值得数据化升级的是 `horizontal_scale / vertical_scale`、stroke width distribution、component-level proportions、connectedness/connector prior 和 projection distribution，而不是继续盲调 connector/taper。

边界：本轮不调 style profile，不替换全局默认，不生成更好轨迹，不调用 API，不连接 CoppeliaSim/AUBO i5，也不做 IK/SDK/机器人控制；字体轮廓不等于真实书写轨迹，图表仍需人工看图校验。

# 2026-06-18 Style profile 数据化升级方案设计与参数分层表

- 新增 `experiments/llm_style_trajectory/configs/style_profile_parameter_schema.json`，把 style profile 相关参数按 style / char / component / process_prior 分层，并标注当前来源、建议来源、估计可行性、风险和阶段。
- 新增 `experiments/llm_style_trajectory/src/style_profile_upgrade_plan.py`，读取 font gap analysis 输出与参数 schema，生成参数矩阵、三阶段升级建议、prototype hints 和图表。
- 新增 `experiments/llm_style_trajectory/tests/test_style_profile_upgrade_plan.py`，覆盖 schema 关键参数、matrix/recommendations/report/prototype 输出、关键词边界和不 import `libpyauboi5`。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/style_profile_upgrade_plan_20260618_150757/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/style_profile_upgrade_plan_index.md`。

输出：

| 文件 | 内容 |
|---|---|
| `style_profile_parameter_matrix.csv` | 参数分层与来源矩阵 |
| `style_profile_upgrade_plan.md` | 数据化升级方案报告 |
| `style_profile_upgrade_recommendations.json` | 三阶段升级建议 |
| `prototype_style_profile_estimates.json` | 未接默认流程的 prototype hints |
| `parameter_source_matrix.png` | 参数来源矩阵图 |
| `upgrade_priority_chart.png` | 升级阶段优先级图 |

关键统计：

| item | value |
|---|---:|
| parameter_count | 23 |
| can_estimate_now_count | 7 |
| phase_1_count | 7 |
| phase_2_count | 5 |
| phase_3_count | 11 |

三阶段建议：

- Phase 1：`horizontal_scale`、`vertical_scale`、`base_width`、`stroke_width_distribution`、`horizontal_projection_distribution`、`vertical_projection_distribution`、`lishu_flatness`。
- Phase 2：`smoothness`、`corner_rounding`、`component_width_ratio`、`component_height_ratio`、`xingkai_connectedness_prior`。
- Phase 3：`speed_scale`、`connection_strength`、`allow_interstroke_connections`、`pen_up_height`、stroke taper、`pressure_curve`、connector trigger/shape/width 等 process priors。

不能从静态字体直接估计：

- `pen_up_height`
- `speed_scale`
- `pressure_curve`
- `allow_interstroke_connections`
- `real_robot_dynamics`

prototype 状态：

- `prototype_style_profile_estimates.json` 已生成。
- `_status = prototype_not_used_by_default`
- `_warning = not wired into generation pipeline`
- 当前不接入 `run_demo.py`，不替换默认 `style_profiles.json`。

本轮结论：下一步应先做字体轮廓可支持的全局形态与宽度统计，再进入 component/char-level 结构适配；connector/taper/pressure/speed 等仍需要人工看图、轨迹数据或机器人过程约束，不能继续凭感觉盲调。

# 2026-06-18 Phase 1 font-outline style profile readonly estimator

- 新增 `experiments/llm_style_trajectory/src/style_profile_phase1_estimator.py`，读取 `font_style_gap_summary.csv` 和 `font_style_gap_style_means.csv`，生成 Phase 1 字体轮廓只读候选 estimates。
- 新增 `experiments/llm_style_trajectory/tests/test_style_profile_phase1_estimator.py`，覆盖 fake 输入、readonly status、unsupported 参数、报告关键词和不 import `libpyauboi5`。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/style_profile_phase1_estimates_20260618_152952/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/style_profile_phase1_estimates_index.md`。

输出：

| 文件 | 内容 |
|---|---|
| `style_profile_phase1_estimates.json` | readonly estimates JSON |
| `style_profile_phase1_parameter_comparison.csv` | current profile vs phase1 hints |
| `style_profile_phase1_estimate_report.md` | Phase 1 估计报告 |
| `style_profile_phase1_estimate_warnings.csv` | 静态字体不支持估计的参数 |
| `current_vs_phase1_scale.png` | 当前 scale 与 Phase 1 hints 对比 |
| `current_vs_phase1_width.png` | Phase 1 base width hints |
| `phase1_projection_summary.png` | 投影 spread summary |

关键状态：

| field | value |
|---|---|
| `_status` | `readonly_estimate_not_used_by_default` |
| `_warning` | `not wired into generation pipeline` |
| `_source` | `font_style_gap_analysis_20260618_144838` |

Current vs Phase 1 差异：

| style | parameter | current | phase1_hint | delta | confidence |
|---|---|---:|---:|---:|---|
| kaishu | horizontal_scale | 1.0 | 1.0 | 0.0 | medium |
| kaishu | vertical_scale | 1.0 | 1.0 | 0.0 | medium |
| lishu | horizontal_scale | 1.18 | 1.198887 | 0.018887 | medium |
| lishu | vertical_scale | 0.82 | 0.834107 | 0.014107 | medium |
| xingkai | horizontal_scale | 1.03 | 0.979982 | -0.050018 | low |
| xingkai | vertical_scale | 0.98 | 1.020427 | 0.040427 | low |

可估计的 Phase 1 hints：

- `horizontal_scale_hint`
- `vertical_scale_hint`
- `base_width_hint`
- `stroke_width_distribution`
- `projection_summary`
- `lishu_flatness`

明确 unsupported：

- `connection_strength`
- `allow_interstroke_connections`
- `connector_trigger`
- `connector_shape`
- `pressure_curve`
- `speed_scale`
- `pen_up_height`
- `real_robot_dynamics`

边界：本轮只读输入数据，不接默认流程，不替换 `style_profiles.json`，不改变 `run_demo.py` 默认行为，不生成新 trajectory / execution / workspace。
# 2026-06-18 Phase 1 readonly estimates 非默认对比图验证

- 新增 `experiments/llm_style_trajectory/src/phase1_profile_comparison.py`，从 readonly estimates 生成 comparison-only candidate profile，并显式对比 current profile 与 phase1 candidate。
- 新增 `experiments/llm_style_trajectory/tests/test_phase1_profile_comparison.py`，覆盖 fake estimates 生成候选 profile、不修改 current profile、summary/report/manifest 输出、report 关键边界说明、xingkai unsupported connector 参数不被覆盖，以及不 import `libpyauboi5`。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/phase1_profile_comparison_20260618_155353/`。
- 生成 `style_profile_phase1_candidate.json`，其中 `_status=comparison_only_not_default`；只覆盖 Phase 1 支持的 `horizontal_scale` / `vertical_scale` hints，保留 `connection_strength`、`allow_interstroke_connections`、`speed_scale`、`pen_up_height` 等当前 profile 参数。
- 生成 `phase1_profile_comparison_summary.csv`、`phase1_profile_comparison_report.md`、`phase1_profile_comparison_manifest.csv` 和 8 张 current/phase1 对比图。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/phase1_profile_comparison_index.md`。
- 关键均值：kaishu 平均 aspect/path/width 变化均为 0；lishu 平均 aspect delta 约 0.001680、path delta 约 10.368；xingkai 平均 aspect delta 约 0.090515，但 connector 规则保持不变。
- 结论：Phase 1 全局 scale 对 kaishu/lishu 影响有限；xingkai 不能靠全局 scale 解决 connector/行楷味问题。下一步应转向 Phase 2 component/stroke-level style modeling。本轮不接默认、不替换 `style_profiles.json`、不改变 `run_demo.py`。
# 2026-06-18 小论文实验对比方案整理

- 新增 `experiments/llm_style_trajectory/docs/mini_paper_experiment_plan.md`，整理小论文建议主线、六组实验、外部功能对比表、已有结果路径和最小下一步。
- 新增 `experiments/llm_style_trajectory/configs/mini_paper_experiment_matrix.json`，把实验组、指标、状态、优先级、已有路径和边界写成可机器读取矩阵。
- 新增 `experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_experiment_plan_index.md`，作为 paper_figures 固定入口。
- 建议题目：`自然语言约束驱动的书法机器人参数化轨迹生成与执行前检查方法`。
- 推荐主实验：modifier controllability、xingkai connector rule、execution width/pressure、motion continuity retiming、robot-interface precheck chain；font outline gap / Phase 1 estimates 建议放入限制和未来工作。
- 明确不可写成真实书法风格学习、真实机器人书写、图像到轨迹风格迁移或 AUBO i5 真实 IK/实机控制。
- 本轮只做文档和配置整理，没有调参数，没有新增生成算法，没有调用 API/CoppeliaSim/AUBO i5/SDK，也没有修改 shared data 或 legacy。
# 2026-06-18 小论文固定图表包整理

- 新增 `experiments/llm_style_trajectory/src/mini_paper_figure_pack.py`，用于从已有输出中复制、重命名和索引小论文固定图表包。
- 新增 `experiments/llm_style_trajectory/tests/test_mini_paper_figure_pack.py`，覆盖图表包生成、manifest、missing source 记录和外部功能对比表输出。
- 生成固定输出目录：`experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/`。
- 图表包包含 12 个 figure/supplementary figure 条目、3 个 table 条目，`missing_count=0`。
- 生成 `fig1_system_pipeline.png`，说明 LLM/mock planner 只输出结构化 plan，轨迹由本地确定性工具生成。
- 复制整理 Figure 2 modifier 可控性图、Figure 3 行楷 connector baseline/v1/v2 对比图、Figure 4 execution width/pressure 图。
- 生成 `table1_retiming_before_after.md/.csv`、`table2_robot_precheck_summary.md/.csv`、`table3_external_functional_comparison.md/.csv`。
- `mini_paper_figure_index.md` 已写明哪些图需要人工看图、哪些图只放补充材料，以及当前不是完整真实书法风格学习、CoppeliaSim/AUBO 均为 dry-run/precheck、外部方法表不是数值复现。
- 本轮没有新增生成算法、没有调参数、没有跑新的大规模实验、没有调用 API、没有连接 CoppeliaSim/AUBO i5、没有 import SDK、没有修改 shared data 或 legacy。

# 2026-06-18 小论文人工视觉评价与图注草稿整理

- 新增 `experiments/llm_style_trajectory/docs/mini_paper_visual_evaluation_template.md`，说明人工看图评分规则和必须避免的过度表述。
- 新增 `experiments/llm_style_trajectory/docs/mini_paper_figure_captions_draft.md`，覆盖 `fig1_system_pipeline.png`、Figure 2 三张 modifier 图、Figure 3 三张行楷 connector 图、`fig4_execution_width_pressure.png`、Table 1-3 和 supplementary style gap / Phase 1 图。
- 新增 `experiments/llm_style_trajectory/docs/mini_paper_experiment_section_outline.md`，整理实验章节草稿骨架，包含实验设置、modifier 可控性、行楷 connector 消融、execution width/pressure、retiming、robot precheck dry-run、外部方法功能对比、局限性与未来工作。
- 新增 `experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/human_visual_evaluation_template.csv`，共 15 个评价项，覆盖 modifier 可见性、connector 自然度、taper/pressure-width 可视化、隶书压扁风险、布局自然度和是否适合作为论文主图。
- 更新 `mini_paper_figure_index.md` 和 `paper_experiment_index.md`，加入人工评价表、图注草稿和实验章节骨架入口。
- 文档中明确：当前风格变化仍是参数化控制，隶书仍可能偏“压扁楷书”，行楷 connector 是规则生成，不是真实书法风格学习；CoppeliaSim/AUBO 仍是 dry-run/precheck。
- 本轮只做论文材料整理，没有新增算法、没有调参、没有调用 API、没有连接 CoppeliaSim/AUBO/SDK，也没有修改 shared data 或 legacy。

# 2026-06-19 Font-outline-derived trajectory basis feasibility / 字体轮廓轨迹基底可行性诊断

- 新增配置：`experiments/llm_style_trajectory/configs/font_outline_basis_chars.json`，固定 10 个代表字：`山、中、永、人、国、德、福、明、和、风`。
- 新增脚本：`experiments/llm_style_trajectory/src/font_outline_basis_feasibility.py`，渲染 kaishu/xingkai/lishu 本地字体轮廓，提取 skeleton candidate，并与 MakeMeAHanzi median 进行图像和指标对比。
- 新增测试：`experiments/llm_style_trajectory/tests/test_font_outline_basis_feasibility.py`，覆盖 skeleton fallback、小型配置输出、manifest 图片存在、缺字体/缺 median 容错和不 import `libpyauboi5`。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_feasibility_index.md`。
- 输出文件：`font_outline_basis_summary.csv`、`font_outline_basis_manifest.csv`、`font_outline_basis_report.md` 和 `figures/basis_compare_uXXXX.png`。
- skeleton 成功率：kaishu=10/10，xingkai=10/10，lishu=10/10。
- 初步诊断：`山`、`德`、`福` 等图中 xingkai/lishu 字体轮廓骨架比 MakeMeAHanzi median 更能体现风格差异；但复杂字 skeleton 端点和分叉偏多，不能直接当最终轨迹，需要后续去噪、断裂修复、笔画顺序恢复和人工看图确认。
- 本轮不替换默认 pipeline，不改 `style_profiles.json`，不改 `run_demo.py` 默认行为，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不做机器人控制，不修改 `code/data` 或 legacy。

# 2026-06-19 Font outline basis 人工筛选包 + skeleton 问题分类

- 新增 `experiments/llm_style_trajectory/src/font_outline_basis_audit.py`，读取 feasibility summary/manifest，按 diagnostic threshold 给 skeleton 候选打标签并整理人工看图包。
- 新增 `experiments/llm_style_trajectory/tests/test_font_outline_basis_audit.py`，覆盖 candidates/report/checklist/image manifest/selected images 输出、issue tag 分类和不 import `libpyauboi5`。
- 输入目录：`experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/`。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_outline_basis_audit_20260619_120211/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_audit_index.md`。
- audit candidates：30 条；selected images：10 张。
- issue tag 统计：`disconnected_skeleton=15`、`promising_candidate=10`、`complex_skeleton=8`、`high_aspect_gap=8`、`high_branch_count=8`、`high_endpoint_count=8`。
- 最值得先人工看的样本：`德/kaishu`、`德/lishu`、`福/kaishu`、`国/kaishu`、`国/lishu`、`德/xingkai`、`福/lishu`、`福/xingkai`、`中/lishu`、`山/lishu`。
- 本轮只做人工筛选包和问题分类，不把 font skeleton 接入默认 pipeline，不改 style profile，不调 connector/taper，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。
## 2026-06-19 Font skeleton cleanup prototype（kaishu / lishu only）

- 新增 `experiments/llm_style_trajectory/src/font_skeleton_cleanup_prototype.py`，只针对 `kaishu` / `lishu` 做 font-outline skeleton cleanup 诊断。
- 新增 `experiments/llm_style_trajectory/tests/test_font_skeleton_cleanup_prototype.py`，覆盖小连通分量删除、短枝剪除、summary/report/manifest/figure 生成和不 import `libpyauboi5`。
- 输入来源：`experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/`。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_skeleton_cleanup_prototype_20260619_122355/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_cleanup_prototype_index.md`。
- 处理范围：`山 / 中 / 人 / 永 / 风` × `kaishu / lishu`，明确不处理 `xingkai`。
- 成功率：kaishu=5/5，lishu=5/5。
- cleanup 平均变化：kaishu endpoint -1.8、branch -1.8、component 0.0、skeleton pixels -8.6；lishu endpoint -0.8、branch -0.8、component 0.0、skeleton pixels -2.0。
- 值得人工优先看图：`永/kaishu`、`永/lishu`、`风/kaishu`（仍有多连通分量），以及 `山/kaishu`、`中/kaishu`、`中/lishu`（有简化但需确认是否保留风格）。
- 结论：轻量 cleanup 对楷书更有效，隶书更保守；下一步可以考虑 path extraction prototype，但必须先人工看 before/after 图。
- 边界：不生成正式 `trajectory.csv`，不替换默认 pipeline，不改 `style_profiles.json` 或 `run_demo.py`，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。
## 2026-06-19 Font skeleton path extraction prototype（very small sample）

- 新增 `experiments/llm_style_trajectory/src/font_skeleton_path_extraction_prototype.py`，将 cleaned font skeleton 转成候选可写 path segments。
- 新增 `experiments/llm_style_trajectory/tests/test_font_skeleton_path_extraction_prototype.py`，覆盖 graph segment extraction、小样本输出、report/manifest/figure 生成和不 import `libpyauboi5`。
- 输入来源：`experiments/llm_style_trajectory/outputs/font_skeleton_cleanup_prototype_20260619_122355/`。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_skeleton_path_extraction_20260619_123527/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_path_extraction_index.md`。
- 样本范围：`山/kaishu`、`人/kaishu`、`中/kaishu`、`山/lishu`、`永/lishu`。明确不处理 xingkai、德、福、国、风或其他复杂字。
- 结果：5 个样本都提取到候选 path segments，且 `recommended_for_next_stage=True`。
- 关键诊断：`山/kaishu` segments=7，`人/kaishu` segments=4，`中/kaishu` segments=14 且 `high_branch_count`，`山/lishu` segments=4，`永/lishu` segments=8 且 `multi_component_skeleton`。
- 结论：建议进入更小范围的 font-derived trajectory trial，但只优先使用 `山/kaishu`、`人/kaishu`、`山/lishu` 这类低风险样本；`中/kaishu` 和 `永/lishu` 需要先人工看图确认 path 是否过碎、candidate order 是否明显不合理。
- 边界：不是正式轨迹，不生成 `trajectory.csv`，不恢复真实笔顺，不替换默认 pipeline，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。
## 2026-06-19 Font-derived trajectory trial（3 low-risk samples）

- 新增 `experiments/llm_style_trajectory/src/font_derived_trajectory_trial.py`，把 extracted path segments 转成 font-derived trial trajectory。
- 新增 `experiments/llm_style_trajectory/tests/test_font_derived_trajectory_trial.py`，覆盖三样本子目录、trial CSV、summary JSON、compare 图、无正式 `trajectory.csv` 和不 import `libpyauboi5`。
- 输入来源：`experiments/llm_style_trajectory/outputs/font_skeleton_path_extraction_20260619_123527/`。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_derived_trajectory_trial_20260619_125428/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_derived_trajectory_trial_index.md`。
- 样本范围：只处理 `山/kaishu`、`人/kaishu`、`山/lishu`；不处理 xingkai、`中/kaishu`、`永/lishu`、德、福、国、风或其他复杂字。
- 结果：`山/kaishu` segment_count=7、point_count=19、warning=`short_segments_filtered:10`；`人/kaishu` segment_count=4、point_count=19、warning=`short_segments_filtered:2`；`山/lishu` segment_count=4、point_count=16、warning=`short_segments_filtered:4`。
- 人工看图重点：`人/kaishu` 最干净，适合做 stroke ordering / simplification 的第一例；`山/lishu` 最能展示字体轮廓基底的隶书风格信号；`山/kaishu` 可用于观察 candidate segment order 与真实笔顺的差距。
- 边界：不是正式轨迹，不含真实笔顺，不含 execution width/pressure，不接机器人，不接默认 pipeline，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。
# 2026-06-19 Font skeleton stroke ordering / simplification prototype

- 新增 `experiments/llm_style_trajectory/src/font_skeleton_stroke_ordering_prototype.py`，只读取 `font_derived_trajectory_trial_20260619_125428/` 中的 trial CSV，对 `人/kaishu` 与 `山/lishu` 两个样本做保守 segment simplification 和 candidate writable order。
- 新增 `experiments/llm_style_trajectory/tests/test_font_skeleton_stroke_ordering_prototype.py`，覆盖只生成两个样本、不生成正式 `trajectory.csv`、summary/report/manifest/compare 图存在、以及不 import `libpyauboi5`。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_skeleton_stroke_ordering_20260619_132543/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_skeleton_stroke_ordering_index.md`。
- 结果：`人/kaishu` 从 4 个 raw trial segments 简化为 2 个 stroke-like candidates；`山/lishu` 保持 4 个 stroke-like candidates，warning=`segment_count_unchanged`，保留隶书轮廓风格，不强行全连。
- 边界：本轮不是正式轨迹，不是真实笔顺恢复，不接默认 pipeline，不替换 MakeMeAHanzi median，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 Median-to-font skeleton alignment / adaptation prototype

- 暂停纯 font skeleton -> trajectory 推进，转向 B 路线：保留 MakeMeAHanzi median stroke order，用 font skeleton / font mask 做形态参考进行 soft projection。
- 新增 `experiments/llm_style_trajectory/src/median_font_alignment_prototype.py`。
- 新增 `experiments/llm_style_trajectory/tests/test_median_font_alignment_prototype.py`，覆盖两个样本输出、无正式 `trajectory.csv`、stroke_count 不变、shift cap、生成人工看图报告、以及不 import `libpyauboi5`。
- 输出目录：`experiments/llm_style_trajectory/outputs/median_font_alignment_20260619_145307/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/median_font_alignment_index.md`。
- `人/kaishu`：stroke_count=2 保持不变，projection distance 6.557520 -> 4.918140(alpha=0.25) / 3.278760(alpha=0.5)，max shift 5.748356 / 11.496712 px。视觉上两笔结构保持稳定。
- `山/lishu`：stroke_count=3 保持不变，projection distance 36.000849 -> 29.389616(alpha=0.25) / 23.972679(alpha=0.5)，max shift 10.532784 / 15.000000 px。但 bbox aspect 未朝 lishu font aspect 靠近，说明最近邻吸附只改善局部贴近度，v2 需要 stroke-level bbox / anchor alignment。
- 边界：本轮不是正式轨迹，不恢复真实笔顺，不改变 stroke 数量，不接默认 pipeline，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 Median-font adaptation v2 prototype

- 新增 `experiments/llm_style_trajectory/src/median_font_adaptation_v2.py`，在 v1 alpha-only 最近点吸附基础上加入 global bbox alignment 与 stroke-level anchor alignment。
- 新增 `experiments/llm_style_trajectory/tests/test_median_font_adaptation_v2.py`，覆盖两样本输出、stroke_count 不变、无正式 `trajectory.csv`、报告边界说明、bbox alignment 单元行为和不 import `libpyauboi5`。
- 输出目录：`experiments/llm_style_trajectory/outputs/median_font_adaptation_v2_20260619_154351/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/median_font_adaptation_v2_index.md`。
- `人/kaishu`：projection distance 6.557520 -> 4.918140(v1 alpha=0.25) -> 4.521372(v2 conservative) / 3.739090(v2 stronger)；aspect gap 0.066713 -> 0.062410 -> 0.061491 / 0.053279，stroke_count=2 保持不变。
- `山/lishu`：projection distance 36.000849 -> 29.389616(v1 alpha=0.25) -> 24.474754(v2 conservative) / 20.563365(v2 stronger)；aspect gap 0.433371 -> 0.495398 -> 0.435363 / 0.441557。v2 改善局部贴近度，但尚未真正解决隶书宽底/结构形态适配。
- 边界：本轮仍是 diagnostic prototype，不生成正式 `trajectory.csv`，不接默认 pipeline，不接机器人接口，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 Lishu structure adaptation v3 prototype

- 新增 `experiments/llm_style_trajectory/src/lishu_structure_adaptation_v3.py`，只针对 `山/lishu` 做 structure-constrained adaptation v3。
- 新增 `experiments/llm_style_trajectory/tests/test_lishu_structure_adaptation_v3.py`，覆盖只处理一个样本、stroke_count 不变、无正式 `trajectory.csv`、summary/report/manifest/compare 图输出、结构 spread 单元行为和不 import `libpyauboi5`。
- 输出目录：`experiments/llm_style_trajectory/outputs/lishu_structure_adaptation_v3_20260619_155525/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/lishu_structure_adaptation_v3_index.md`。
- v3 在 v2 stronger 后加入下半部横向支撑、左右外展和 bottom support guide；输出 `lishu_structure_v3_conservative.csv` 与 `lishu_structure_v3_stronger.csv`，不生成正式 `trajectory.csv`。
- 指标：projection distance 从 v2 stronger 的 20.563365 降到 20.157518 / 20.090813；bbox aspect 从 0.936821 提到 0.958776 / 0.958299；lower-half width 从 156.629793 提到 158.148182 / 159.569313。
- 限制：两个 v3 版本都触达 22 px shift cap，且 aspect 仍远低于 lishu font aspect 1.378378，说明 structure constraints 方向有效但还不够，后续更适合做 component-level alignment 或更明确的部件锚点约束。
- 边界：本轮仍是 diagnostic prototype，不接默认 pipeline，不接机器人接口，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 Lishu component-level alignment prototype

- 新增 `experiments/llm_style_trajectory/src/lishu_component_alignment_prototype.py`，只针对 `山/lishu` 做 component-level alignment。
- 新增 `experiments/llm_style_trajectory/tests/test_lishu_component_alignment_prototype.py`，覆盖只处理一个样本、component group 输出、stroke_count 不变、无正式 `trajectory.csv`、summary/report/manifest/compare 图输出和不 import `libpyauboi5`。
- 输出目录：`experiments/llm_style_trajectory/outputs/lishu_component_alignment_20260619_160805/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/lishu_component_alignment_index.md`。
- component groups：`left_group=2`、`center_group=2`、`right_group=3`、`lower_support_group=12`。
- 指标：projection distance 为 v3 stronger 20.090813、component conservative 19.949109、component stronger 20.215119；bbox aspect 为 0.958299、0.970717、0.971593；lower-half width 为 159.569313、160.028913、160.743366。
- 诊断：component conservative 相比 v3 在 projection/aspect/lower-half width 上有小幅改善；component stronger 的 projection 反而略差。两个 component variant 都触达 24px shift cap，说明继续加大强度不合适。
- 边界：本轮仍是 diagnostic prototype，不生成正式 `trajectory.csv`，不接默认 pipeline，不接机器人接口，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 Trajectory style route decision report

- 暂停新增算法、调参和 pipeline 接入，整理 A/B/C 三条路线的证据链。
- 新增 `experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md`。
- 新增 `experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json`。
- 新增固定入口 `experiments/llm_style_trajectory/outputs/paper_figures/trajectory_style_route_decision_index.md`。
- 更新 `experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`、`LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`、`PROJECT_LOG.md` 和 `CURRENT_PROJECT_GUIDE.md`。
- 路线状态：
  - A：MakeMeAHanzi median + style profile，保留为 stable baseline / robot backbone。
  - B：median + font skeleton/mask adaptation，作为 safe style adaptation research direction。
  - C：font skeleton derived path，作为 style basis research only，不接默认 pipeline。
- 当前推荐：下一阶段先写 hybrid route design spec，让 A 提供笔顺和执行/机器人 precheck 链路，B 提供有边界的形态适配，C 提供人工筛选的字体轮廓风格参考。
- 边界：当前不宜继续盲目调 connector/taper，也不宜直接把 font skeleton 接默认 pipeline；本轮只做证据整理和路线决策，不新增算法、不调参数、不调用 API、不接 CoppeliaSim/AUBO/SDK。

# 2026-06-19 Hybrid style trajectory design spec

- 基于 route decision report，新增 `experiments/llm_style_trajectory/docs/hybrid_style_trajectory_design_spec.md`。
- 新增机器可读设计摘要 `experiments/llm_style_trajectory/configs/hybrid_style_trajectory_design_spec.json`。
- 新增固定入口 `experiments/llm_style_trajectory/outputs/paper_figures/hybrid_style_trajectory_design_index.md`。
- 更新 `paper_experiment_index.md`、`LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`、`PROJECT_LOG.md` 和 `CURRENT_PROJECT_GUIDE.md`。
- 核心设计：A 作为 stable median trajectory / execution / robot precheck backbone；B 作为 trial-only bounded adaptation module；C 作为人工筛选的 font reference / candidate basis module；Human audit gate 作为视觉效果判断入口。
- 候选 prototype：H1=A+B bounded adaptation，H2=A+C font reference constraints only，H3=A baseline + C exemplar visualization。
- 推荐下一步：H2。先定义字体轮廓/骨架证据能形成哪些可信约束，不移动轨迹点、不生成正式 `trajectory.csv`、不接默认 pipeline。
- 边界：本轮只做 spec/design/planning，不新增算法、不调参数、不调用 API、不连接 CoppeliaSim/AUBO/SDK、不修改 `code/data` 或 legacy。

# 2026-06-19 H2 font reference constraints package

- 执行 hybrid route 推荐的 H2 prototype：A median + C font reference constraints only。
- 新增 `experiments/llm_style_trajectory/src/font_reference_constraints_package.py`，从 kaishu / lishu 字体 mask 和 skeleton 中提取可解释参考约束。
- 新增 `experiments/llm_style_trajectory/tests/test_font_reference_constraints_package.py`，覆盖输出文件、JSON 状态、样本范围、无正式 trajectory/adapted/execution/workspace 文件，以及不 import `libpyauboi5`。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_reference_constraints_20260619_230426/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_reference_constraints_index.md`。
- 样本范围：`山/kaishu`、`人/kaishu`、`中/kaishu`、`山/lishu`、`中/lishu`、`永/lishu`、`风/lishu`；不处理 xingkai、德、福、国。
- 约束统计：`usable_for_adaptation=25`、`visual_reference_only=25`、`unsafe_for_direct_use=34`。
- 样本级推荐：`candidate_for_bounded_B_adaptation=4`、`visual_reference_with_limited_constraints=1`、`visual_reference_only_high_risk=2`。
- 下一步最适合给 B adaptation 使用的约束是 bounded `bbox_aspect`、`lower_half_width_ratio`、`left_right_spread` 和很小幅度的 `bbox_center_shift_x/y`；raw skeleton path 和 unordered skeleton segments 明确不安全。
- 边界：本轮不移动轨迹点、不生成 adapted CSV、不生成正式 `trajectory.csv`、不接默认 pipeline、不调用 API/CoppeliaSim/AUBO/SDK、不修改 `code/data` 或 legacy。

# 2026-06-19 H1-lite constraint-bounded median adaptation prototype

- 基于 H2 约束包执行 H1-lite：只使用 `usable_for_adaptation` 的 `bbox_aspect`、`lower_half_width_ratio`、`left_right_spread`、`bbox_center_shift_x/y`。
- 新增脚本：`experiments/llm_style_trajectory/src/constraint_bounded_adaptation_h1_lite.py`。
- 新增测试：`experiments/llm_style_trajectory/tests/test_constraint_bounded_adaptation_h1_lite.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/constraint_bounded_adaptation_h1_lite_20260619_231903/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/constraint_bounded_adaptation_h1_lite_index.md`。
- 只处理 `人/kaishu` 与 `山/lishu`，不处理 xingkai 或复杂字。
- `人/kaishu`：bbox aspect 1.414861 -> 1.402621(conservative) / 1.392189(balanced)，max shift 1.056528 / 1.776407 px，stroke_count=2 保持不变。
- `山/lishu`：bbox aspect 0.945007 -> 0.998870(conservative) / 1.048676(balanced)，lower-half width 187.343097 -> 193.898937 / 199.553901，max shift 5.461121 / 9.845336 px，stroke_count=3 保持不变。
- 诊断：H1-lite 比 raw skeleton pulling 更有边界，`山/lishu` 在未触达 shift cap 的情况下朝字体参考的宽底方向移动；仍需人工看图决定是否继续扩展。
- 边界：本轮不使用 raw skeleton path、不使用 unordered skeleton segments、不做最近点吸附，不生成正式 `trajectory.csv`，不接默认 pipeline/execution/workspace/robot，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 H1-lite style contrast expansion: 山/kaishu vs 山/lishu

- 基于 H1-lite 做 small contrast expansion：新增 `山/kaishu`，与已有 `山/lishu` H1-lite 结果做同字不同风格对照。
- 新增脚本：`experiments/llm_style_trajectory/src/h1_lite_style_contrast_expansion.py`。
- 新增测试：`experiments/llm_style_trajectory/tests/test_h1_lite_style_contrast_expansion.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/h1_lite_style_contrast_20260619_234043/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/h1_lite_style_contrast_index.md`。
- `山/kaishu`：bbox aspect 0.945007 -> 0.965779 / 0.984478，lower-half width 187.343097 -> 190.213398 / 192.664933，max shift 2.388712 / 4.341142 px，stroke_count=3 保持不变。
- `山/lishu`：沿用 H1-lite 结果，bbox aspect 0.945007 -> 0.998870 / 1.048676，lower-half width 187.343097 -> 193.898937 / 199.553901，stroke_count=3 保持不变。
- style gap：bbox_aspect_gap 从 0.000000 增至 0.033091(conservative) / 0.064198(balanced)，lower_half_width_gap 从 0.000000 增至 3.685539 / 6.888968。
- 诊断：同字不同风格 gap 被拉开，kaishu 变化更保守，lishu 变化更明显；下一步是否扩到 `风/lishu` 需要先人工看对照图。
- 边界：trial-only / not_used_by_default；不使用 raw skeleton path，不生成正式 `trajectory.csv`，不生成 execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-20 Hybrid section refinement v1 / 风-隶书单样本风险试验

- 新增 `experiments/llm_style_trajectory/src/hybrid_section_refinement_v1.py`，只对 `风/lishu` 做 hybrid section refinement。
- 新增 `experiments/llm_style_trajectory/tests/test_hybrid_section_refinement_v1.py`，覆盖：
  - 只处理 `风/lishu`
  - 输出 `hybrid_section_conservative.csv` / `hybrid_section_balanced.csv`
  - 生成 summary / report / manifest / compare 图
  - `stroke_count` 保持不变
  - 输出明确 `trial_not_used_by_default`
  - 不 import `libpyauboi5`
- section 方案：
  - 优先 `component_bbox`
  - 不稳定则回退 `top_mid_bottom_fallback`
  - 本轮真实结果使用 `top_mid_bottom_fallback`
- 输出目录：`experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/`
- 关键结果：
  - `section_count=3`
  - `section_names = top_band / mid_band / bottom_band`
  - `bbox_aspect: 1.188427 -> 1.259425 / 1.306963`
  - `lower_half_width: 215.040000 -> 219.856896 / 223.297536`
  - `max_point_shift_px: 5.543559 / 8.824495`
  - `path_length_ratio: 0.982155 / 0.973699`
- 诊断：
  - 对 `风/lishu` 而言，当前 component bbox 提取还不够稳定，因此 hybrid section 这轮主要验证了 fallback section 的安全性，而不是 component-first 的真实收益。
  - 相比之前更激进的 v3/component-level，大拉扯被明显抑制，说明 section-level refinement 更适合做复杂 lishu 的下一步整理基础。
  - 下一步更建议先整理 section 约束包，或先在 `山/lishu` 上复现同一套流程，而不是继续扩大复杂字覆盖。

# 2026-06-21 Section constraints package / fallback guide

- 新增 `experiments/llm_style_trajectory/src/section_constraints_package.py`，把 section-level 证据整理成 machine-readable 的约束包与 fallback guide。
- 新增 `experiments/llm_style_trajectory/tests/test_section_constraints_package.py`，覆盖：
  - 输出 JSON / CSV / report / manifest / figures
  - JSON 可被 `python -m json.tool` 解析
  - summary 明确 `trial_only_not_used_by_default`
  - `山/kaishu`、`山/lishu` 作为安全 B 输入
  - `风/lishu` 作为 fallback-first reference-only
  - 不 import `libpyauboi5`
- 输出目录：`experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/`
- 关键规则：
  - component bbox stable 时：优先 component-first，只做轻量 bbox 对齐和 section anchor 对齐
  - component bbox 不稳定时：回退 top/mid/bottom fallback
  - usable constraints：`bbox_aspect`、`lower_half_width_ratio`、`left_right_spread`、`bbox_center_shift_x/y`
  - reference-only constraints：`component_count`、`endpoint_count`、`branch_count`
  - unsafe constraints：`raw_skeleton_path`、`unordered_skeleton_segments`
- 诊断：
  - `山/kaishu` 与 `山/lishu` 可作为 future B 路线的安全输入，`section_source=component_bbox`，`fallback_used=False`
  - `风/lishu` 回退到 `top_mid_bottom_fallback`，适合作为 fallback-first reference-only 样本
  - 这一轮不做算法推进，只做约束封装与规则归纳，避免继续盲目加大拉扯


- 2026-06-21: added B-route constraint registry and registry-gated probe. H2 font-reference constraints and section constraints are unified into a read-only evidence pack. Probe remains trial-only for 山/lishu and 风/lishu, not used by default.

- 2026-06-21: added B-route handoff note and machine-readable summary for new threads. The note points to the route decision report, B-route registry index, section constraints package, and font reference constraints package.

- 2026-06-21：完成 B-route 三张关键图的中文化与差异辅助重绘，只重绘表达，不改算法。结论：`山/kaishu vs 山/lishu` 仍属弱差异；`风/lishu` conservative vs balanced 最接近；`hybrid_section_compare_cn` 最适合人工复检。
- 2026-06-21：新增 B-route visual conclusion freeze note，固定三张中文关键图的论文角色：`hybrid_section_compare_cn` 为正文候选，`h1_lite_u5c71_kaishu_lishu_contrast_cn` 为补充材料候选，`h1_lite_u98ce_lishu_risk_contrast_cn` 为风险/局限性图。

# 2026-06-23 A-route showcase pack / 跨笔过渡控制展示包

- 新增 A-route 展示字符集：`experiments/llm_style_trajectory/configs/a_route_showcase_chars.json`。
- 新增展示包脚本：`experiments/llm_style_trajectory/src/a_route_showcase_pack.py`。
- 新增测试：`experiments/llm_style_trajectory/tests/test_a_route_showcase_pack.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/a_route_showcase_20260623_091212/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/a_route_showcase_index.md`。
- 关键图：`a_route_style_overview_grid.png`、`a_route_modifier_control_overview.png`、`a_route_execution_display_grid.png`、`a_route_behavior_control_compare.png`、`a_route_smoothness_supplementary.png`。
- 本轮重新定位 connector / 连笔：它用于证明自然语言驱动的跨笔过渡控制 / execution 行为控制，不再写成真实行楷风格迁移成功。
- 边界：不新增算法，不调 style/profile 参数，不调用 API，不接 CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。
