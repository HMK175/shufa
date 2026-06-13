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

### LLM planner 框架接入
- 在 `experiments/llm_style_trajectory` 中接入 planner 统一接口，支持 `mock`、`api`、`local` 三种模式。
- 当前 `mock` 已实现并通过 demo；`api/local` 为安全占位，未配置时不联网、不启动本地模型，也不会自动 fallback。
- 新增 `planner_prompt.md` 和 plan schema 约束，明确 LLM 只输出结构化书写计划，不直接生成 CSV 或轨迹点。
- demo 已生成行楷“山”和隶书“山，不要连笔”的 `plan.json`；测试结果 `31 passed`。
- 当前仍未验证真实 LLM 能力，但系统已经具备安全接入在线 API 或本地模型的接口基础。

### DeepSeek API smoke
- 已使用 DeepSeek-V4-Pro API 真实运行 `--planner-mode api`。
- 行楷“山”和隶书“山，不要连笔”均生成 `plan.json`、`trajectory.csv`、`preview.png`、`summary.json`。
- 两个 plan 均为 `planner_mode=api`、`source=deepseek_v4_pro`，且 `validation.ok=true`。
- DeepSeek 正确解析“不要连笔”：隶书 plan 中 `allow_interstroke_connections=false`、`connection_strength=0.0`。
- 当前知识库使用方式为：本地发送 planner prompt 与 style profile 摘要给 API，API 返回结构化 plan；本地再用 Make Me a Hanzi 与 style profile 完成校验、补全和轨迹生成。不是让 LLM 直接生成 CSV，也不是上传完整知识库。

---

## 2026-06-08 LLM planner 鲁棒性边界收紧

### 完成事项
- 针对 DeepSeek-V4-Pro 鲁棒性测试中暴露的“过度归一化”问题，收紧 `experiments/llm_style_trajectory` 的 planner 请求边界。
- 新增 `request_status`、`requested_style_raw`、`requested_chars_raw`、`mapped_style`、`rejection_reason` 等 plan 字段，便于区分“模型输出”和“用户原始请求”。
- 本地 validation 现在会拒绝 unsupported / invalid 请求：例如草书、火星文、多字输入不再被偷偷映射成行楷、楷书或单字。
- 对“好看一点”这类未明确风格请求采用保守默认：`kaishu`，并在 warnings 中记录 default 行为。
- 鲁棒性 summary CSV 已增加请求边界字段，便于后续对 API / local / mock 三种 planner 进行对比分析。

### 验证结果
- `python -m pytest experiments\llm_style_trajectory\tests -q`
- 结果：`42 passed`，5 个 Matplotlib 中文字体 warning，不影响 planner、轨迹或评价逻辑。
- mock 鲁棒性评估输出：`experiments/llm_style_trajectory/outputs/planner_robustness_20260608_153906/`
- mock 指标：`total=12`，`validation_ok_count=9`，`expected_invalid_rejected_count=3`，`dangerous_output_count=0`，`json_parse_success_count=12`。

### 当前判断
- 这轮修正后，LLM planner 不再只依赖 prompt 约束，而是由本地 schema validation 控制安全边界。
- 下一步真实 API 评估应在已设置 DeepSeek key 的 PowerShell 会话中重跑 `evaluate_planner_robustness.py --planner-mode api`，观察 `expected_invalid_rejected_count` 是否从 0 提升到 3。

---

## 2026-06-08 DeepSeek API planner 鲁棒性复测环境检查

### 完成事项
- 按要求从 Windows 用户级环境变量导入 `LLM_STYLE_PLANNER_API_KEY` / `LLM_STYLE_PLANNER_ENDPOINT` / `LLM_STYLE_PLANNER_MODEL` 到当前 PowerShell 会话。
- 只用布尔值检查 key 可见性，未打印、记录或写入 API key。
- 运行 `python experiments\llm_style_trajectory\src\evaluate_planner_robustness.py --planner-mode api`，输出目录为 `experiments/llm_style_trajectory/outputs/planner_robustness_20260608_162126/`。

### 结果
- `[bool]$env:LLM_STYLE_PLANNER_API_KEY` 为 `False`，当前 Codex/PowerShell 会话未读取到用户级 DeepSeek API key。
- 本轮没有真实调用 DeepSeek；summary/report 记录的是 `api_unconfigured` 状态。
- 指标：`total=12`，`validation_ok_count=0`，`char_correct_count=0`，`style_correct_count=0`，`connection_constraint_correct_count=8`，`expected_invalid_rejected_count=3`，`dangerous_output_count=0`，`json_parse_success_count=0`。

### 当前判断
- 这不是有效的模型鲁棒性结论，只证明脚本在 API 未配置时能完整跑完并生成报告。
- 需要在当前 Codex 可见的环境中重新设置 `LLM_STYLE_PLANNER_API_KEY` 后再复测，重点观察 `style_correct_count`、`ambiguous_good_shan` 是否回到 `kaishu`、以及 `dangerous_output_count` 是否保持 0。

---

## 2026-06-08 DeepSeek API planner 有效复测

### 完成事项
- 按当前 Codex 进程环境变量复测 DeepSeek-V4-Pro API planner；未从 `HKCU:\Environment` 导入或覆盖 API key。
- 只检查 `ProcessKeyVisible=True` 和 endpoint/model，未打印、记录或写入 API key。
- 真实运行 `python experiments\llm_style_trajectory\src\evaluate_planner_robustness.py --planner-mode api`，输出目录为 `experiments/llm_style_trajectory/outputs/planner_robustness_20260608_163557/`。

### 结果
- summary: `experiments/llm_style_trajectory/outputs/planner_robustness_20260608_163557/planner_robustness_summary.csv`
- report: `experiments/llm_style_trajectory/outputs/planner_robustness_20260608_163557/planner_robustness_report.md`
- 指标：`total=12`，`validation_ok_count=9`，`char_correct_count=11`，`style_correct_count=10`，`connection_constraint_correct_count=12`，`expected_invalid_rejected_count=3`，`dangerous_output_count=0`，`json_parse_success_count=12`。
- `ambiguous_good_shan` 已回到 `kaishu`；草书、火星文和多字输入三个 expected-invalid 任务均被本地边界校验拒绝。

### 当前判断
- DeepSeek-V4-Pro 已足够作为文本 planner 基准继续使用，尤其在自然语言风格解析、连笔约束和模糊请求默认处理上表现稳定。
- 安全边界仍必须由本地 request boundary + schema validation 保证；LLM 仍只负责结构化计划，不直接生成 CSV 或轨迹点。

---

## 2026-06-11 style modifiers 梯度对比实验

### 完成事项
- 在 `experiments/llm_style_trajectory` 中继续完善受控 `style_modifiers`，本轮只用 `mock` planner，未调用 API。
- 将普通 `xingkai` 默认 `connection_preference` 调整为 `weak`，把“更连贯 / 连笔 / 连起来”映射为 `normal`，把“不要连笔 / 不连笔”映射为 `none`。
- 新增 `configs/modifier_ablation_tasks.json`，并为 batch 输出增加 `modifier_ablation_<char_id>.png` 对比图。
- `modifier_summary.csv` 增加 `pen_up_count`，便于对比自然语言约束对抬笔次数和连接强度的影响。

### 结果
- 输出目录：`experiments/llm_style_trajectory/outputs/batch_20260611_210502/`
- summary：`experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_summary.csv`
- 山字对比图：`experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_ablation_u5c71.png`
- 山字三组结果：不连笔 `connection_strength=0.0, connection_count=0, path_length=578.070, pen_up_count=2`；默认行楷 `connection_strength=0.176, connection_count=2, path_length=611.321, pen_up_count=0`；更连贯行楷 `connection_strength=0.32, connection_count=2, path_length=638.527, pen_up_count=0`。

### 验证
- `python -m pytest experiments\llm_style_trajectory\tests -q`
- 结果：`48 passed, 9 warnings`，warning 为 Matplotlib 中文字体提示。

### 当前判断
- `style_modifiers` 已能形成可解释的 none / weak / normal 语义梯度，适合作为“自然语言约束有效性验证”的小实验。
- 仍保持安全边界：planner 只输出离散 modifiers，本地白名单映射到 style/brush 参数，LLM 不直接生成轨迹点或 CSV。

---

## 2026-06-13 style modifiers 宽扁与圆滑 ablation

### 完成事项
- 继续在 `experiments/llm_style_trajectory` 中完成宽扁语义和圆滑语义的 modifier ablation，本轮只用 `mock` planner，未调用 API。
- 新增 `configs/modifier_shape_smoothness_tasks.json`。
- `modifier_summary.csv` 增加 `bbox_width`、`bbox_height`、`total_turning_angle`、`max_turning_angle`。
- 新增 shape/smoothness 专用对比图：`modifier_ablation_shape_<char_id>.png` 和 `modifier_ablation_smoothness_<char_id>.png`。

### 结果
- 输出目录：`experiments/llm_style_trajectory/outputs/batch_20260613_085440/`
- summary：`experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_summary.csv`
- 中字 shape 对比图：`experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_shape_u4e2d.png`
- 永字 smoothness 对比图：`experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_smoothness_u6c38.png`
- 宽扁实验：默认隶书中 `aspect_ratio=0.997268`；宽扁一点 `aspect_ratio=1.192443`；更宽 `aspect_ratio=1.080569`。
- 圆滑实验：默认楷书永 `total_turning_angle=10.632062, max_turning_angle=0.971813`；更圆滑/更平滑 `total_turning_angle=10.565580, max_turning_angle=0.895203`。

### 验证
- `python -m pytest experiments\llm_style_trajectory\tests -q`
- 结果：`49 passed, 11 warnings`，warning 为 Matplotlib 中文字体提示。

### 当前判断
- 宽扁/更宽语义已能在 `horizontal_scale`、`vertical_scale`、bbox 和 aspect ratio 上产生可解释差异。
- 圆滑/平滑语义在 `mean_turning` 上变化较小，但 `total_turning_angle` 和 `max_turning_angle` 能更稳定地反映转折减弱，因此后续论文展示应使用补充转向指标而不是只看 mean turning。

---

## 2026-06-13 论文实验图表索引整理

### 完成事项
- 将当前论文/汇报推荐图统一复制到固定目录：`experiments/llm_style_trajectory/outputs/paper_figures/`。
- 新增图表索引：`experiments/llm_style_trajectory/outputs/paper_figures/paper_experiment_index.md`。
- 更新 `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`，将推荐图表来源改为固定命名文件。

### 固定图表
- 三风格基础对比：`fig_style_profile_compare_grid.png`
- 连笔 modifier：`fig_modifier_connection_shan.png`
- 宽扁 modifier：`fig_modifier_shape_zhong.png`
- 圆滑 modifier：`fig_modifier_smoothness_yong.png`
- 二维执行层：`fig_execution_ablation_shan.png`
- 工作空间映射：`fig_workspace_ablation_shan.png`

### 当前判断
- 后续写论文或做 PPT 时优先从 `paper_experiment_index.md` 查找图表和对应指标，不再直接翻多个 batch 输出目录。

---

## 2026-06-13 LLM style trajectory 阶段整理

### 完成事项
- 新增根目录阶段总结文档：`LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`。
- 在 `experiments/llm_style_trajectory/README.md` 中增加阶段总结入口和推荐图路径。
- 在 `THESIS_FRAMEWORK_2026.md` 中补充 “LLM planner + style modifiers 当前证据链” 小节。

### 整理内容
- 汇总当前方法链路：自然语言 -> planner -> request boundary validation -> style_modifiers -> style profile + 白名单映射 -> trajectory CSV -> brush rendering -> virtual metrics。
- 汇总 DeepSeek API planner 鲁棒性复测结果。
- 汇总三类自然语言 modifier ablation：连笔、宽扁、圆滑。
- 标出推荐用于论文/汇报的三张图：
  - `experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_ablation_u5c71.png`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_shape_u4e2d.png`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_smoothness_u6c38.png`

### 当前判断
- 这阶段已经可以作为“自然语言约束通过受控 modifier 影响确定性轨迹工具”的实验闭环。
- 后续不宜继续盲目增加 modifier 种类，优先应把三类 ablation 整理成论文图表，并考虑用真实 API planner 跑同一组 modifier tasks 做一致性验证。

---

## 2026-06-13 二维虚拟书写执行层增强

### 完成事项
- 在 `experiments/llm_style_trajectory` 中新增二维 execution layer，本轮只使用 `mock` planner 和本地确定性工具。
- 保留旧 `trajectory.csv` 的 `y,x` + `nan,nan` 格式，同时为每个任务新增 `execution_trajectory.csv`。
- `execution_trajectory.csv` 增加 `z`、`speed`、`pressure`、`width`、`pen_down`、`is_connector`、`segment_type` 等字段，用于虚拟书写渲染和后续机器人仿真准备。
- 新增 `execution_render.png` / `execution_debug.png`，并为行楷山 none / weak / normal 生成 `execution_ablation_u5c71.png`。
- `modifier_summary.csv` 增加 `stroke_draw_length`、`connector_draw_length`、`pen_up_move_length`、`mean_pressure`、`mean_width`、`connector_mean_pressure`、`connector_mean_width`。

### 结果
- 输出目录：`experiments/llm_style_trajectory/outputs/batch_20260613_092733/`
- summary：`experiments/llm_style_trajectory/outputs/batch_20260613_092733/modifier_summary.csv`
- execution 对比图：`experiments/llm_style_trajectory/outputs/batch_20260613_092733/execution_ablation_u5c71.png`
- 行楷山三组关键结果：
  - 不要连笔：`connector_draw_length=0.000`，`pen_up_move_length=188.929`，`connector_mean_pressure=0.000`，`connector_mean_width=0.000`。
  - 默认 weak：`connector_draw_length=33.251`，`connector_mean_pressure=0.340`，`connector_mean_width=4.275`。
  - 更连贯 normal：`connector_draw_length=60.457`，`connector_mean_pressure=0.680`，`connector_mean_width=6.840`。

### 验证
- `python -m pytest experiments\llm_style_trajectory\tests -q`
- 结果：`53 passed, 15 warnings`，warning 为 Matplotlib 中文字体提示。

### 当前判断
- 二维执行层已经能把中心线以外的执行状态显式化：none 保留抬笔移动，weak 产生低压细连接，normal 产生更明显连接。
- 这一步比单纯中心线预览更适合作为进入三维机械臂仿真前的中间层；下一步可基于 `execution_trajectory.csv` 做速度/压力曲线细化或再接机器人工作空间映射。

---

## 2026-06-13 二维执行层结果质检与论文图整理

### 完成事项
- 使用已有输出目录 `experiments/llm_style_trajectory/outputs/batch_20260613_092733/` 复核 execution ablation 文件完整性。
- 检查三个山字任务的 `execution_trajectory.csv`、`execution_render.png`、`execution_debug.png`、`trajectory.csv`、`plan.json`、`summary.json` 均存在。
- 对 `execution_debug.png` 做轻量可视化增强：增加标题和图例，明确区分 `stroke`、`connector`、`pen-up move`。
- 对 `execution_ablation_u5c71.png` 做轻量可视化增强：在三栏顶部标注 `none`、`weak`、`normal`。
- 整理论文/汇报图到固定目录 `experiments/llm_style_trajectory/outputs/paper_figures/`。

### 结果
- 论文图目录：`experiments/llm_style_trajectory/outputs/paper_figures/`
- 执行层对比图：`experiments/llm_style_trajectory/outputs/paper_figures/fig_execution_ablation_shan.png`
- 三组 render/debug 图：
  - `fig_execution_none_render.png` / `fig_execution_none_debug.png`
  - `fig_execution_weak_render.png` / `fig_execution_weak_debug.png`
  - `fig_execution_normal_render.png` / `fig_execution_normal_debug.png`
- 指标表：`experiments/llm_style_trajectory/outputs/paper_figures/execution_ablation_table.md`

### 当前判断
- 图像和指标均能区分三种执行状态：none 无连接绘制段且有抬笔移动，weak 是低压细连接，normal 是更明显的连接。
- 这组图表适合作为“execution layer 比中心线轨迹更能表达连笔执行差异”的论文/汇报素材。

---

## 2026-06-13 机器人工作空间映射与仿真前检查层

### 完成事项
- 新增 `experiments/llm_style_trajectory/src/workspace_mapping.py`，将 `execution_trajectory.csv` 映射为机器人纸面坐标。
- 每个任务目录生成 `robot_workspace_trajectory.csv`、`workspace_validation_report.md` 和 `workspace_path_preview.png`。
- batch 根目录生成 `workspace_mapping_summary.csv`、`workspace_mapping_report.md` 和 `workspace_ablation_u5c71.png`。
- 新增 `tests/test_workspace_mapping.py`，覆盖坐标方向、Z 轴抬笔规则、batch 输出和越界检查。

### 结果
- 输出目录：`experiments/llm_style_trajectory/outputs/batch_20260613_092733/`
- summary：`experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_mapping_summary.csv`
- report：`experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_mapping_report.md`
- workspace 对比图：`experiments/llm_style_trajectory/outputs/batch_20260613_092733/workspace_ablation_u5c71.png`
- 三个山字任务均 `out_of_bounds=False`。
- `none` 的 `max_step_mm=52.241` 来自抬笔移动；`normal` 的 `max_step_mm=16.717` 略高于 15mm 阈值，后续仿真前建议补 connector/pen-up move 重采样或速度规划。

### 当前判断
- 工作空间映射层已能提供进入 CoppeliaSim / RoboDK 前所需的基础 CSV 和检查报告。
- 本轮仍未接任何三维仿真器；下一步如果进入仿真，应优先处理过大跳变和速度连续性。

---

## 2026-06-13 三字体基础风格对比实验

### 完成事项
- 新增 `configs/style_profile_compare_tasks.json`，覆盖 `山 / 中 / 永 / 福 / 明` 五个字的 `kaishu / xingkai / lishu` 三风格任务，共 15 个。
- 新增 `src/style_profile_compare.py`，复用 mock planner、trajectory 生成、execution layer 和 workspace mapping，生成三层综合对比。
- 新增 `tests/test_style_profile_compare.py`，覆盖配置加载、summary/report/grid 输出、每字三风格完整性和关键字段。

### 结果
- 输出目录：`experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/`
- summary：`experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_profile_compare_summary.csv`
- report：`experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_profile_compare_report.md`
- grid：`experiments/llm_style_trajectory/outputs/style_profile_compare_20260613_101423/batch_20260613_101423/style_compare_grid.png`
- 每字三风格对比图：`style_compare_u5c71.png`、`style_compare_u4e2d.png`、`style_compare_u6c38.png`、`style_compare_u798f.png`、`style_compare_u660e.png`。

### 平均指标
- `kaishu`: `avg_aspect_ratio=0.920111`，`avg_connection_count=0.0`，`avg_connector_draw_length=0.0`，`avg_workspace_path_length_mm=602.907`。
- `xingkai`: `avg_aspect_ratio=0.966550`，`avg_connection_count=5.6`，`avg_connector_draw_length=90.279`，`avg_workspace_path_length_mm=404.606`。
- `lishu`: `avg_aspect_ratio=1.322317`，`avg_connection_count=0.0`，`avg_connector_draw_length=0.0`，`avg_workspace_path_length_mm=588.240`。
- 三种风格 `out_of_bounds_count` 均为 0。

### 当前判断
- 三种基础 style profile 已形成可解释差异：`lishu` 更宽扁，`xingkai` 更容易产生弱连接，`kaishu` 更保守。
- 这组实验可作为“基础风格 profile 有效性”的图表证据；边界仍需说明这是参数化 profile 效果，不是完整真实书法风格学习。

---

## 2026-06-13 workspace trajectory 重采样与速度规划

### 完成事项
- 新增 `experiments/llm_style_trajectory/src/workspace_resampling.py`，对 `robot_workspace_trajectory.csv` 做分段重采样和速度规划。
- 新增 `tests/test_workspace_resampling.py`，覆盖 stroke / connector / pen_up_move 阈值、状态保持、估计时长和 batch 输出。
- 对 `experiments/llm_style_trajectory/outputs/batch_20260613_092733/` 运行重采样。
- 每个任务新增 `robot_workspace_trajectory_resampled.csv`、`workspace_resampling_report.md`、`workspace_resampled_preview.png`。
- batch 根目录新增 `workspace_resampling_summary.csv`、`workspace_resampling_report.md`、`workspace_resampling_ablation_u5c71.png`。

### 结果
- `不要连笔行楷山`：`original_max_step_mm=52.241` -> `resampled_max_step_mm=4.749`，解决 pen-up move 大跳点。
- `默认行楷山`：`original_max_step_mm=9.194` -> `resampled_max_step_mm=2.299`。
- `更连贯行楷山`：`original_max_step_mm=16.717` -> `resampled_max_step_mm=2.388`，解决 connector 超 15mm 阈值问题。
- 分段速度规划：stroke 25mm/s，weak connector 40mm/s，normal connector 32mm/s，pen-up move 70mm/s。

### 当前判断
- 重采样后三组山字均满足本轮设定的分段最大点距约束：stroke <= 2mm，connector <= 2.5mm，pen_up_move <= 5mm。
- 该层可作为后续 CoppeliaSim / RoboDK 前的最后二维后处理；下一步如果接仿真，应继续加入加速度/jerk 限制或 S 曲线速度规划。

---

## 2026-06-13 CoppeliaSim 最小笔尖轨迹播放验证

### 完成事项
- 使用本机 CoppeliaSim Edu：`D:\software\CoppeliaSim_Edu_V4_10_0_rev0_Win`。
- 在 PowerShell 中通过 `PYTHONPATH` 暴露 ZeroMQ remote API Python client。
- 安装并验证 `pyzmq` / `cbor` 依赖。
- 对 `robot_workspace_trajectory_resampled.csv` 先完成 dry-run，再完成真实 CoppeliaSim 播放。
- 更新 `experiments/llm_style_trajectory/coppeliasim/README.md`，记录环境配置、dry-run、真实播放命令和边界。

### 验证对象
- `experiments/llm_style_trajectory/outputs/batch_20260613_092733/u5c71_xingkai_20260613_092733_979792/robot_workspace_trajectory_resampled.csv`

### dry-run 摘要
- `point_count=258`
- `stroke=237`
- `pen_up_move=21`
- `X=-49.057031..48.721406mm`
- `Y=-49.392188..49.392188mm`
- `Z=0.0..8.0mm`
- `duration_estimate_s=12.972534`
- `max_step_mm=8.0`

### 当前判断
- CoppeliaSim 最小接入链路已跑通，工作空间轨迹可以进入三维仿真环境做笔尖路径可视化。
- 当前仍只是 paper plane + pen-tip sphere + colored path segments，不包含机械臂模型、IK、末端工具标定、碰撞检测或控制器调参。
- `max_step_mm=8.0` 需要在后续报告中进一步拆分为 3D / XY / Z 分量，避免把 Z 轴抬笔高度误解为平面跳点。

---

## 2026-06-13 CoppeliaSim 播放评价层完善

- 在 `experiments/llm_style_trajectory/coppeliasim/play_workspace_path.py` 中新增低负载播放参数：`--display-stride`、`--no-path-objects`、`--auto-stop`。
- dry-run summary 已拆分 `max_step_3d_mm`、`max_xy_step_mm`、`max_z_step_mm`，并保留旧 `max_step_mm` 作为兼容字段。
- 新增 `evaluate_playback_batch.py`，对 `batch_20260613_092733` 批量统计 5 条 `robot_workspace_trajectory_resampled.csv`。
- 输出记录：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_092733/coppeliasim_playback_summary.csv`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_092733/coppeliasim_playback_report.md`
- 三组山字任务中，none 的最大 3D 跳变主要来自 8mm 抬笔高度；weak/normal 的较大跳变主要来自 XY 连接路径。当前仍只是 pen-tip/sphere playback，不包含机械臂 IK、真实动力学或控制器。

---

## 2026-06-13 连笔 connector 几何连续性修复

- 修复 `connection_strength` 缩短 weak/normal connector 几何路径的问题。
- `trajectory_tools.insert_connections()` 和 `execution_tools.build_execution_trajectory()` 现在都让 connector 从上一笔终点连续走到下一笔起点。
- `connection_strength` 改为影响 connector 的 pressure / width / speed，不再影响几何长度。
- 重新生成 batch：`experiments/llm_style_trajectory/outputs/batch_20260613_154131/`。
- 修复后三组山字 playback dry-run：
  - none: `max_xy_step_mm=4.749192`，`max_z_step_mm=8.0`
  - weak: `max_xy_step_mm=2.487672`
  - normal: `max_xy_step_mm=2.487672`
- weak/normal 不再出现 35mm / 43mm 的 XY 段间跳变。

---

## 2026-06-13 修复后论文图表主版本刷新

- 将后续论文/汇报主版本切换到 `experiments/llm_style_trajectory/outputs/batch_20260613_154131/`。
- 刷新 `experiments/llm_style_trajectory/outputs/paper_figures/` 中的连笔、execution、workspace 和 resampling 相关固定图。
- 新增固定图：`fig_workspace_resampling_shan.png`。
- 更新 `execution_ablation_table.md`，改为修复后口径：connector 几何完整连接，`connection_strength` 只影响 pressure / width / speed。
- 更新 `paper_experiment_index.md` 和 `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`，明确 `batch_20260613_092733` 是发现跳变问题的历史输出，`batch_20260613_154131` 是后续优先引用的修复后主结果。

---

## 2026-06-13 CoppeliaSim 播放完成反馈与单次 result 留痕

- `play_workspace_path.py` 现在在 dry-run 和真实播放结束后输出明确 JSON summary。
- 每次播放或 dry-run 会写入单次结果文件：`coppeliasim_playback_result.json` 和 `coppeliasim_playback_result.md`。
- 新增 `--result-out-dir`，可把单次 result 写到指定目录；默认写在 CSV 所在目录。
- 指定 weak 行楷山 dry-run 已生成：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.json`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.md`
- 用户现在可以从终端 JSON 和 result 文件确认播放是否结束、播放点数、auto-stop 参数和最大跳点；当前仍只是 pen-tip/sphere playback，不包含机械臂 IK。

---

## 2026-06-13 CoppeliaSim 标准书写场景自动创建

- `experiments/llm_style_trajectory/coppeliasim/play_workspace_path.py` 新增标准场景参数：`--scene-setup standard`、`--clear-previous-scene`、`--paper-size-mm`、`--pen-tip-radius-mm`、`--show-axes`、`--show-boundary`。
- CoppeliaSim 中可自动创建 `120mm x 120mm` paper plane、纸面 boundary、X/Y/Z axes、pen-tip sphere 和分色 path segments；脚本对象统一使用 `llm_style_trajectory_*` 前缀，便于清理。
- 单次 result JSON/Markdown 已追加 `scene_setup`、纸面大小、笔尖半径、坐标映射、workspace bounds、scene warnings 和 `recommended_playback`。
- 已对修复后的 weak 行楷山执行真实播放验证：
  - CSV：`experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv`
  - result：`experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_playback_result.json`
  - 结果：`status=finished`，`simulation_stopped=true`，`recommended_playback=true`，`max_xy_step_mm=2.487672`。
- 当前层仍是 standard pen-tip/sphere scene，不含机械臂 IK、动力学或控制器；该层用于固定论文中的仿真工作空间定义。

---

## 2026-06-13 CoppeliaSim 标准场景论文图整理

- 将 standard scene 真实播放结果整理到 `experiments/llm_style_trajectory/outputs/paper_figures/`。
- 新增标准场景示意图：`fig_coppeliasim_standard_scene_shan.png`。
- 复制真实播放结果：`coppeliasim_standard_scene_result.json`、`coppeliasim_standard_scene_result.md`。
- 新增索引：`coppeliasim_standard_scene_index.md`。
- 更新 `paper_experiment_index.md` 与 `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`，将 CoppeliaSim 标准场景列入论文/汇报推荐素材。
- 关键结果：`status=finished`、`simulation_stopped=true`、`recommended_playback=true`、`point_count=275`、`max_xy_step_mm=2.487672`、`paper_size_mm=120.0`。
- 当前仍是 pen-tip/sphere scene，不包含机械臂 IK。

---

## 模板

## YYYY-MM-DD
- 完成事项
- 遇到的问题
- 解决方案
- 下一步计划
