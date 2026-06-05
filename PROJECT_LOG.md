# 项目日志

## 2026-05-11
- 项目初始化
- 确定论文题目：基于图像骨架提取与强化学习优化的书法机器人笔画轨迹生成方法
- 建立项目文件结构
- 开始文献检索

---
## 2026-05-12
- 在两台电脑上配置了 Python 环境，安装了 opencv-python、matplotlib、scipy、scikit-image、torch
- 将骨架提取从 Zhang-Suen 替换为 skimage.morphology.thin，交叉点噪点从 29.3% 降至 1.7%
- 重写笔画提取算法（stroke.py）：从段提取+交叉分量配对改为简化图+端点方向配对
  - 骨架图压缩为简化图（节点=端点+交叉分量），收缩所有 deg-2 链点
  - 交叉分量按桥接边合并为超级交叉区
  - 按方向连续性配对 + 强制兜底配对（处理 90° 转角）
  - 删除约 340 行旧代码
- 修复 DFS 追踪器的多连通分量支持
- 实现逐笔画 B-spline 平滑（笔画间用 nan,nan 表示抬笔）
- 实现 DDPG 轨迹优化模块（rl_optimizer.py）
  - 状态空间：位置+局部图像 patch+距离变换+方向+曲率（57 维）
  - 动作空间：连续位移 (Δy, Δx) ∈ [-3, 3] px
  - 奖励：前景靠近 + 笔画内停留 + 平滑性 + 边界约束
  - 实验设计：加噪模拟初始化误差 → RL 恢复 → 量化改进
  - 初步结果：Chamfer 距离降低约 25%
- 添加 .jfif 图片格式支持
- 配置 SSH 密钥实现 GitHub 免密访问
- 用"永"字图片进行完整 pipeline 测试

### 遇到的问题
- Zhang-Suen 在复杂字形上骨架噪点极高（305 个交叉点 / 1040 像素），导致笔画碎片化
  - 解决：改用 skimage.morphology.thin，交叉点降至 15 个
- 笔画配对在 90° 转角处失效（方向连续性得分为 0）
  - 解决：添加强制配对兜底逻辑
- DDPG Critic 网络拼接 bug（逐元素相加 → 应为 channel 拼接）
  - 解决：改用 torch.cat
- RL 实验缺少优化空间（骨架轨迹已完美贴合前景，Chamfer=0）
  - 解决：加高斯噪声模拟不完美初始化，再让 RL 恢复

### 下一步计划
- 增加更多测试字形样本（≥5 个）
- 调优 RL 超参数（学习率、噪声幅度、训练轮数）
- 完成三组对比实验（骨架基线 / B样条平滑 / RL 优化）
- 撰写论文方法章节

---
## 2026-05-13

### 完成事项
- 实现 Wu ICIRA 2024 骨架提取模块 (`code/wu2024_skeleton.py`)：
  - Layer 1: 轮廓→中点骨架（距离变换 + PCA法向量 + 累加器阈值 + 形态学闭运算）
  - Layer 2: V/S/C 分类（Nc 邻居连通分量数，避免交叉区附近误分类）
  - Layer 3: 笔画组装（委托 stroke.py 已证明的简化图+端点配对算法）
  - 对薄笔画自动降级到 morphology thin 回退
- 实现轨迹优化工具包 (`code/trajectory_optimizer.py`)：
  - 增强平滑：Savitzky-Golay、自适应曲率 B-spline、弧长重采样
  - 速度规划：梯形速度剖面 + 曲率感知速度 + 时间参数化轨迹
  - 曲率优化：Menger 三点曲率 + 峰值检测 + 局部约束 B-spline
  - 工作空间映射：像素坐标 → 机器人 (X,Y,Z) 米制
  - 顶层编排器 `optimize_trajectory()`
- 集成 pipeline：新增 `--skeleton wu2024`、`--enhanced-smooth`、`--velocity-plan`、`--curvature-opt`、`--workspace-map` 等 CLI 参数
- 用 yong.jfif 验证：5 笔画正确，Chamfer=0.0px，输出 timed CSV + workspace CSV

### 关键发现
- 对连通字形图像（整字二值图），轮廓中点骨架与形态学细化收敛到同一条中轴，肉眼无法区分
- Wu ICIRA 2024 原文先分割笔画再对每笔求中点骨架，整字场景下优势不明显
- V/S/C 分类仍有差异（wu2024: V=12 S=3 vs thin: V=11 S=2），交叉区拓扑不同
- 速度规划 dt=0.01 产生 266K 轨迹点，实际使用需调大 dt 或降低采样率

### 下一步计划
- 用真实书法图片（笔画宽度 ≥8px）测试 wu2024 骨架在粗笔画上的表现
- 完成三组对比实验（骨架基线 / B样条平滑 / RL 优化）
- 撰写论文方法章节

---

## 2026-05-17

### 完成事项
- 多轮测试后确认：当前主要瓶颈在骨架拓扑解析和笔画路径选择，不在 RL 局部优化。
- 论文主线建议从“骨架提取 + RL 优化”收敛为“骨架拓扑分析 + 笔画路径修正 + 轨迹平滑/重采样”。
- 确定下一阶段方法方向：将 `stroke.py` 的交叉点贪心配对升级为候选路径生成 + 全局代价评分。
- 扩展并划分小测试集，分为调参集和保留测试集，避免针对少数字形反复过拟合。

### 关键发现
- “福”字近期效果变好，但简单字出现笔画缺失，说明局部规则存在类别间冲突。
- “中/口/田”等闭合结构需要单独保护，否则容易出现框线缺失、误连或异常绕行。
- “川”应作为简单字底线验收：如果复杂字修好了但“川”等简单字缺笔，说明规则不具备泛化价值。
- 继续微调单个阈值的收益下降，应转向全局路径选择和可量化评分。

### 下一步计划
- 固定调参集：`yi, san, shi, kou, tian, zhong, chuan, zhi, yong, fu, mu, ming`。
- 固定保留测试集：`ri, ren, da, shan, lin, hao, xiu, guo, hui, pin, xin, shui, xiao`。
- 在 `stroke.py` 中实现候选路径生成与全局代价评分。
- 增加结构化日志和验收指标：笔画数、骨架覆盖率、回绕数量、闭合结构保留情况、简单字是否缺笔。

### 本轮代码执行补充
- 修复 `stroke.py` 全局候选选择的覆盖账本问题：选中候选后不再破坏原始候选列表，避免已覆盖边被重复追加成大路径。
- 增加 global/legacy 安全门与结构化诊断输出；当前仅 `chuan`、`kou` 稳定接入 global，`tian/zhong/fu/yong/zhi` 因覆盖过量或高回绕回退 legacy。
- 增加简单字先验：`yi` 压回主体 1 笔，`san` 按三行合并为 3 笔；`chuan` 保持 3 笔。
- 9 字验收命令已跑通，输出保存到 `code/output/check_*.csv` 和 `code/output/check_*.png`。
- 继续修正 global 选择器：加入候选重叠惩罚并直接返回已选 edge ids，`tian/zhong` global 过覆盖回归测试转绿；`tian` 仍因高回绕安全回退。

---

## 2026-05-29

### 完成事项
- 完成结构约束版 next-stroke segmentation 独立实验，仍未接入旧 `stroke.py` / `pipeline.py` 主流程。
- 在 next-stroke 分割链路中加入 remaining mask、4 通道输入、overlap penalty 和 `constrain-remaining` rollout 后处理。
- 完整回归测试通过：`28 passed, 2 warnings`。

### 关键发现
- baseline 仍是当前最佳 next-stroke 模型：teacher-forcing Dice=0.6173，autoregressive Dice=0.3299。
- `constrain-remaining` 可将 overlap 压到 0，但 autoregressive Dice 从 0.3299 降至 0.3079，说明硬约束会误伤自然连接/交叠区域。
- 4 通道 remaining + overlap penalty 未提升自回归表现，autoregressive Dice 为 0.2613；加后处理后降至 0.2409。
- 仅靠 previous/remaining mask 约束不足以稳定解决自回归误差累积。

### 当前判断
- next-stroke 形式相对 fixed 13-channel 仍然成立，但自回归阶段尚不稳定。
- 当前分割结果还不适合直接进入 mask-to-trajectory 主链路。
- 下一阶段应考虑组合目标、笔画 order/class 先验或数据规模/样本设计调整，而不是继续堆 previous mask 噪声、DAgger 或硬 remaining 约束。

---

## 2026-05-30

### 完成事项
- 整理 `experiments/llm_style_trajectory` 独立实验模块的三风格批量 demo 结果。
- 当前模块已能批量生成 `山/中/永` 的 `kaishu/xingkai/lishu` 三风格轨迹，并输出单任务 `plan.json`、`trajectory.csv`、`preview.png`、`summary.json`。
- 批量输出增加 `batch_summary.csv` 与每字三风格 compare 图，便于观察 style profile 是否产生可见几何差异。

### 当前状态
- planner 仍是规则/模拟版，尚未接入真实 LLM 或外部 API。
- CSV 轨迹由确定性轨迹工具基于 Make Me a Hanzi medians 与人工 style profile 生成，不由 LLM 直接输出轨迹点。
- 当前风格 profile 是人工参数：`kaishu` 保守，`xingkai` 更连接/平滑，`lishu` 更宽扁；尚未从字体、图片或示教轨迹中学习。

### 下一步可选方向
- 接入真实 LLM planner，仅用于任务解析、风格选择和工具编排。
- 引入字体/图片统计或少量人工示教轨迹，估计更有依据的 style profile 参数。
- 继续保持该路线与旧图像骨架/CNN 分割路线隔离，避免影响主流程。

---

## 2026-06-05

### 完成事项
- 完成 `experiments/llm_style_trajectory` 的 style profile 数据化实验记录。
- 本机成功使用 3 个中文字体作为风格来源：楷书 `simkai.ttf`、行楷 `STXINGKA.TTF`、隶书 `SIMLI.TTF`。
- 每种风格成功渲染 10/10 个字符，并生成 `style_metrics.csv`、`style_profile_estimated.json`、`style_profile_report.md` 与 estimated profile 三风格 demo。

### 关键发现
- `horizontal_scale`、`vertical_scale`、`smoothness`、`corner_rounding`、`speed_scale` 已可由字体渲染样本统计估计。
- `connection_strength`、`pen_up_height` 仍保留为人工先验，不能表述为从字体或图片中学习得到。
- 人工查看确认三种字体风格差异明显，estimated profile 生成的轨迹也有可见差异。

### 当前判断
- 多风格轨迹模块已从“纯人工参数 demo”推进为“字体样本统计 + 参数化轨迹生成”。
- 当前仍未接入真实 LLM，planner 仍是规则/模拟版；CSV 仍由确定性轨迹工具生成。
- 当前尚未验证真实书写效果，后续若用于论文展示，应明确为字体几何统计驱动的参数化风格实验，而非真实书法风格学习。

### 虚拟书写评价补充
- 在 `experiments/llm_style_trajectory` 中新增 trajectory render/evaluation，已能将 `trajectory.csv` 渲染成模拟书写图，并与对应 style 字体图计算 IoU、Chamfer、aspect ratio error 等指标。
- 评价 batch：`experiments/llm_style_trajectory/outputs/batch_20260601_135226/`。
- 三风格平均指标：kaishu IoU=0.1701，xingkai IoU=0.2352，lishu IoU=0.1951；其中 xingkai 的平均 Chamfer 与 aspect error 最好。
- 模拟书写后仍能看到风格差异，尤其 lishu 的宽扁趋势仍明显；但整体 IoU 偏低，说明 median 轨迹 + 固定笔宽渲染与真实字体轮廓差距较大。
- 当前更值得优化的是 style-aware brush rendering，而不是继续优先调整 LLM planner。

### 连笔先验修正
- 人工检查发现目标隶书字体样本无连笔，但旧 `lishu.connection_strength=0.06` 会产生跨笔连接。
- 已新增/使用 `allow_interstroke_connections` 显式控制跨笔连接：`kaishu=false`、`lishu=false`、`xingkai=true`。
- 新 batch `experiments/llm_style_trajectory/outputs/batch_20260605_235159/` 中，connection_count 为 kaishu=0、xingkai=9、lishu=0。
- 去掉 lishu 错误连笔后，style_brush IoU 从 0.2124 降至 0.1825，但这是合理修正；旧分数部分来自不符合目标字体的错误连接。
- 当前方法边界更清楚：静态字体可估计形态参数，不能可靠估计连笔/抬笔等书写过程参数。

---

## 模板

## YYYY-MM-DD
- 完成事项
- 遇到的问题
- 解决方案
- 下一步计划
