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

## 2026-06-14 师兄资料中的机械臂平台确认

- 查看 `D:\edge download\视觉抓取26.04.27` 中的视觉抓取实验资料。
- `遨博机器人运动控制实验记录.docx` 明确写到实验目标为与 `AUBO i5` 机械臂通讯并进行运动控制。
- SDK 目录包含 AUBO C/C++/Python SDK，Python 包为 `auboi5-sdk-for-windows-python3.7-x64-v1.5.2`，并包含 `libpyauboi5.pyd`、`pyauboi51.dll`。
- 视觉抓取程序中 `robotcontrol.py` 使用 `import libpyauboi5`，定义 `Auboi5Robot`，并封装 `connect`、`inverse_kin`、`move_joint`、`move_line` 等接口。
- `arm_server_py37.py` 和 `real_grasp.py` 中保留过 AUBO i5 的连接 IP 和端口 `8899`，但这些历史 IP 仅作为线索，实机前需现场重新确认。
- 新增记录文件：`AUBO_I5_PLATFORM_NOTES.md`。
- 更新 `ROBOT_TEST_PLAN.md`，将后续真实机械臂方向优先定位为 AUBO i5 / 遨博 i5。

---

## 2026-06-14 机械臂 IK 前末端目标位姿准备层

- 新增 `experiments/llm_style_trajectory/src/robot_target_poses.py`，把 `robot_workspace_trajectory_resampled.csv` 转换为 `robot_target_poses.csv`。
- 新增 `experiments/llm_style_trajectory/tests/test_robot_target_poses.py`，覆盖 mm-to-m、固定 RPY、quaternion 归一化、时间单调、速度单位转换和输出文件。
- 新增 `experiments/llm_style_trajectory/docs/aubo_i5_target_pose_notes.md`，说明当前只生成目标位姿，不做真实 AUBO i5 IK 或实机控制。
- 默认验证对象：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_workspace_trajectory_resampled.csv`
- 新生成输出：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_pose_report.md`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_pose_summary.json`
- 关键结果：`point_count=275`，`duration_s=13.05282`，`path_length_m=0.359531`，`max_step_m=0.002488`，`recommended_for_ik_dry_run=true`，`warnings=[]`。
- 当前阶段已从 pen-tip playback 推进到 robot end-effector target pose representation；仍不做真实 IK、不连接 AUBO i5 实机、不发控制命令。

---

## 2026-06-15 AUBO i5 IK dry-run 命令适配层

- 新增 `experiments/llm_style_trajectory/src/aubo_i5_command_adapter.py`，将 `robot_target_poses.csv` 转成离线 AUBO i5 command plan。
- 新增 `experiments/llm_style_trajectory/tests/test_aubo_i5_command_adapter.py`，覆盖 command plan 生成、危险输入安全检查、以及不 import `libpyauboi5`。
- 新增 `experiments/llm_style_trajectory/docs/aubo_i5_command_adapter_notes.md`，说明当前只是 dry-run command plan，不做 IK、不连接真实 AUBO i5、不调用 `move_joint` / `move_line`、不使用历史 IP。
- 默认验证对象：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/robot_target_poses.csv`
- 新生成输出：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan.csv`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_safety_check.json`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_command_plan.md`
- 关键结果：`point_count=275`，`command_count=277`，`max_step_m=0.002488`，`max_speed_m_s=0.04`，`max_accel_m_s2_estimate=0.0`，`recommended_for_sdk_dry_run=true`，`warnings=[]`。
- 当前层只做离线 SDK dry-run 计划，不判断真实 AUBO i5 可达性、碰撞、奇异位形或关节限位。

---

## 2026-06-16 AUBO i5 command adapter 论文素材整理

- 将 AUBO i5 command adapter 的固定结果整理到 `experiments/llm_style_trajectory/outputs/paper_figures/`。
- 新增固定索引：`aubo_i5_command_adapter_index.md`。
- 固定复制：
  - `aubo_i5_command_plan.csv`
  - `aubo_i5_command_plan.md`
  - `aubo_i5_safety_check.json`
- 更新 `paper_experiment_index.md`，在 CoppeliaSim 标准场景之后新增 AUBO i5 离线命令计划小节，并加入推荐展示顺序。
- 更新 `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md`，把 AUBO i5 command adapter 纳入推荐论文图表和当前创新点。
- 关键结论：当前系统已经形成 `robot_target_poses.csv -> AUBO i5 dry-run command plan` 的离线接口准备层，但仍不做 IK、不连接实机、不调用 `move_joint` / `move_line`。

---

## 2026-06-16 根目录文档路线整理

- 新增当前路线入口：`CURRENT_PROJECT_GUIDE.md`。
- 重写根目录 `README.md`，将项目首页从旧的“图像骨架提取 + RL 优化”路线改为当前 `experiments/llm_style_trajectory` 路线。
- 重写 `AGENTS.md`，明确新对话优先阅读顺序、当前主线、旧路线归档位置和工作边界。
- 新建旧路线归档目录：`docs/legacy_image_skeleton_rl_route/`。
- 归档早期路线文档：
  - `README_legacy.md`
  - `CLAUDE.md`
  - `AGENTS_legacy.md`
  - `TODO.md`
  - `PAPER_OUTLINE.md`
  - `METHOD_NOTES.md`
  - `RESEARCH_NOTES.md`
- 新增归档说明：`docs/legacy_image_skeleton_rl_route/README.md`。
- 整理目标：切换新对话时，优先读当前路线入口，不再被根目录旧路线文档误导。

---

## 2026-06-16 AUBO i5 IK feasibility dry-run 前检查层

- 新增 `experiments/llm_style_trajectory/src/aubo_i5_ik_feasibility.py`，对 `robot_target_poses.csv` 做进入真实 IK 前的离线 feasibility 检查。
- 新增 `experiments/llm_style_trajectory/tests/test_aubo_i5_ik_feasibility.py`，覆盖正常样例、缺字段、NaN/inf、非单调时间、quaternion 非归一化、超出 envelope，以及不 import `libpyauboi5`。
- 新增 `experiments/llm_style_trajectory/docs/aubo_i5_ik_feasibility_notes.md`。
- 生成默认输出：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_summary.json`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_report.md`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/aubo_i5_ik_feasibility_points.csv`
- 固定论文/汇报资料写入 `experiments/llm_style_trajectory/outputs/paper_figures/aubo_i5_ik_feasibility_index.md` 及对应 summary/report/points 副本。
- 关键结果：`point_count=275`，`radius_range_m=[0.000756, 0.064444]`，`max_step_m=0.002488`，`max_speed_m_s=0.04`，`recommended_for_real_ik_check=true`，`warnings=[]`。
- 当前仍不是 AUBO i5 真实 IK，不连接 SDK 或实机，不判断关节限位、碰撞、奇异位形或真实可达性。

---

## 2026-06-16 IK feasibility 整理同步

- 更新 `CURRENT_PROJECT_GUIDE.md`、根目录 `README.md` 和 `AGENTS.md`，把 AUBO i5 IK feasibility dry-run 纳入当前主线链路与已完成清单。
- 更新 `AUBO_I5_PLATFORM_NOTES.md` 和 `ROBOT_TEST_PLAN.md`，避免后续新对话误以为下一步仍是生成 target poses 或 command adapter。
- 更新 `LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md` 和 `paper_experiment_index.md`，将 IK feasibility 固定为第 6 章机器人接口准备层的一部分。
- 边界保持不变：当前仍不做真实 IK、不连接 AUBO i5、不调用 SDK、不发送任何运动命令。

---

## 2026-06-16 CoppeliaSim simple pen/tool coordinate calibration layer

- 扩展 `experiments/llm_style_trajectory/coppeliasim/play_workspace_path.py`，
  新增 simple pen/tool 可视化参数：`--tool-model simple-pen`、
  `--show-tool-frame`、`--tool-length-mm`、`--tool-radius-mm`、
  `--tcp-offset-mm`、`--base-frame-origin-mm`。
- 默认 `--tool-model none` 保持旧的 pen-tip/sphere playback 行为；启用
  `simple-pen` 时结果文件改写为 `coppeliasim_tool_model_result.json/md`。
- 新增 `experiments/llm_style_trajectory/tests/test_coppeliasim_tool_model.py`，
  覆盖 dry-run result、参数解析、旧行为保持和不 import `libpyauboi5`。
- 已对推荐 weak 行楷山样例执行 dry-run：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_tool_model_result.json`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/coppeliasim_tool_model_result.md`
- 固定论文/汇报索引：
  - `experiments/llm_style_trajectory/outputs/paper_figures/coppeliasim_tool_model_index.md`
- 关键结果：`point_count=275`，`tool_model=simple-pen`，
  `recommended_for_coordinate_calibration=true`，`warnings=[]`。
- 当前仍只是 simple pen/tool visual sanity check，不是 AUBO i5 真实机器人模型、
  不做 IK、不连接实机、不调用 SDK、不发送运动命令。

---

## 2026-06-16 Motion continuity dry-run 检查层

- 新增 `experiments/llm_style_trajectory/src/motion_continuity_check.py`，
  用于离线检查 workspace / target pose 的时间连续性、速度、速度跳变、
  加速度、jerk、四元数归一化和分段统计。
- 新增 `experiments/llm_style_trajectory/tests/test_motion_continuity_check.py`。
- 新增 `experiments/llm_style_trajectory/docs/motion_continuity_check_notes.md`。
- 默认样例输出：
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_summary.json`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_report.md`
  - `experiments/llm_style_trajectory/outputs/batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/motion_continuity_points.csv`
- 固定论文/汇报索引：
  - `experiments/llm_style_trajectory/outputs/paper_figures/motion_continuity_check_index.md`
- 关键结论：默认 weak 行楷山 target pose 的速度不过阈值
  (`max_speed_m_s=0.04`)，四元数归一化正常，但存在
  `dt_nonpositive_count=4`，且保守阈值下
  `max_accel_m_s2=0.533536284`、`max_jerk_m_s3=11.386446091` 超限。
- 因此当前 `recommended_for_coppeliasim_playback=false`、
  `recommended_for_ik_dry_run=false`；后续应先做 target pose 去重、retiming
  和速度平滑，再进入真实 IK dry-run 或低速空跑准备。
- 本层仍是离线检查，不是真实机器人动力学，不做 IK，不连接实机，不调用 SDK，
  不发送运动命令。

---

## 模板

## YYYY-MM-DD
- 完成事项
- 遇到的问题
- 解决方案
- 下一步计划

---

## 2026-06-17 Target pose retiming / smoothing 后处理层

- 新增 `experiments/llm_style_trajectory/src/target_pose_retiming.py`，
  将 `robot_target_poses.csv` 离线后处理为 `robot_target_poses_smoothed.csv`。
- 新增 `experiments/llm_style_trajectory/tests/test_target_pose_retiming.py`。
- 新增 `experiments/llm_style_trajectory/docs/target_pose_retiming_notes.md`。
- 默认 weak 行楷山样例删除 4 个相邻静止重复点，几何路径长度保持不变
  (`path_length_delta_m=0.0`)。
- retiming 后指标：`dt_nonpositive_count=0`，
  `max_accel_m_s2=0.274132141`，`max_jerk_m_s3=4.193553547`，
  `recommended_for_coppeliasim_playback=true`，
  `recommended_for_ik_dry_run=true`。
- 固定论文/汇报入口：
  `experiments/llm_style_trajectory/outputs/paper_figures/target_pose_retiming_index.md`。
- 本层仍只做离线 target-pose 时间规划，不做真实 IK，不连接 AUBO i5，
  不调用 SDK，不发送机器人命令。

---

## 2026-06-17 Smoothed target poses 接回 dry-run 默认流程

- 新增 `experiments/llm_style_trajectory/src/target_pose_defaults.py`，
  统一 raw / smoothed target pose 默认选择逻辑。
- 更新 `aubo_i5_command_adapter.py` 与 `aubo_i5_ik_feasibility.py`：
  默认 CLI 优先使用 `robot_target_poses_smoothed.csv`；显式 `--csv` 不会被替换。
- 新增 `experiments/llm_style_trajectory/tests/test_smoothed_target_pose_default.py`，
  覆盖默认选择、显式原始输入、smoothed 文件名、point_count 和不 import SDK。
- 重新生成 smoothed dry-run 输出：
  - `aubo_i5_command_plan_smoothed.csv`
  - `aubo_i5_safety_check_smoothed.json`
  - `aubo_i5_command_plan_smoothed.md`
  - `aubo_i5_ik_feasibility_smoothed_summary.json`
  - `aubo_i5_ik_feasibility_smoothed_report.md`
  - `aubo_i5_ik_feasibility_smoothed_points.csv`
- 关键结果：smoothed command `point_count=271`、`command_count=273`、
  `recommended_for_sdk_dry_run=true`；smoothed IK feasibility `point_count=271`、
  `recommended_for_real_ik_check=true`，warnings 均为空。
- 固定论文/汇报入口：
  `aubo_i5_command_adapter_smoothed_index.md` 和
  `aubo_i5_ik_feasibility_smoothed_index.md`。
- 当前仍只做离线 dry-run，不做真实 IK、不连接 AUBO i5、不调用 SDK、不发送运动命令。

---

## 2026-06-17 多字样本风格诊断实验

- 新增 `experiments/llm_style_trajectory/configs/style_diagnostic_chars.json`，覆盖 18 个常用字和
  `kaishu` / `xingkai` / `lishu` 三种基础风格。
- 新增 `experiments/llm_style_trajectory/src/style_diagnostics.py`，批量生成本地 trajectory、
  execution trajectory、workspace trajectory 和 resampled workspace trajectory，并汇总风格诊断指标。
- 新增 `experiments/llm_style_trajectory/tests/test_style_diagnostics.py`，覆盖小型 config、缺字不中断、
  summary/style means/report/figure 生成，以及不 import `libpyauboi5`。
- 生成输出目录：
  `experiments/llm_style_trajectory/outputs/style_diagnostics_20260617_200746/`。
- 固定论文/汇报入口：
  `experiments/llm_style_trajectory/outputs/paper_figures/style_diagnostics_index.md`。
- 样本统计：54 个 char x style 样本全部成功，`failure_count=0`，`missing_char_count=0`。
- 三风格诊断：`lishu` 的 `avg_aspect_ratio=1.465173`，宽扁差异稳定；`xingkai` 的
  `avg_connection_count=6.056`、`avg_connector_draw_length=525.944`，连接差异稳定；
  `kaishu` 与 `lishu` 均保持 `connection_count=0`。
- 参数诊断：当前宽扁和连接参数有效，但笔画级宽度、部件级比例、转折圆滑度仍偏粗，后续应优先从字体/图像统计中重新估计。
- 本轮不调用 API，不连接 CoppeliaSim/AUBO i5，不做真实 IK，不调用 SDK，不发送机器人命令。

---

## 2026-06-17 人工看图校验规则补充

- 更新 `CURRENT_PROJECT_GUIDE.md`、`AGENTS.md` 和 `experiments/llm_style_trajectory/README.md`。
- 明确轨迹图、渲染图、风格对比图、CoppeliaSim 截图等图像结果不能只看数值指标判断效果。
- 后续若某轮结果可能“指标正常但视觉效果不佳”，代码线程需要主动提醒用户人工目检，并在实验记录中说明。
- 风格差异、连笔外观、笔画宽度和布局自然度等判断，数值指标只作辅助，最终需要结合人工看图。

---

## 2026-06-17 code/ 旧路线代码归档整理

- 对 `code/` 做引用审计：当前 `experiments/llm_style_trajectory` 主线直接使用的是
  `code/data/makemeahanzi/graphics.txt`；未发现当前主线直接 import 旧的 `code/stroke.py`、
  `code/pipeline.py` 或 `code/skeleton.py`。
- 保留当前共享数据：
  `code/data/makemeahanzi/graphics.txt`、`dictionary.txt`、`COPYING`、`LGPL`。
- 新增 `code/README.md`，说明当前主线位于 `experiments/llm_style_trajectory/`，
  `code/data/makemeahanzi/` 是共享数据，`code/legacy_image_skeleton_rl_route/` 是旧路线归档。
- 新增 `code/legacy_image_skeleton_rl_route/README.md`。
- 将旧图像骨架、RL、训练预测和 Make Me a Hanzi 导入/生成脚本移动到：
  `code/legacy_image_skeleton_rl_route/scripts/`。
- 将旧模型 JSON 移动到：
  `code/legacy_image_skeleton_rl_route/models/`。
- 将旧 tune/holdout 列表移动到：
  `code/legacy_image_skeleton_rl_route/lists/`。
- 将旧本地生成物、缓存、数据集和输出目录移动到：
  `code/legacy_image_skeleton_rl_route/artifacts/`。
- 更新 `CURRENT_PROJECT_GUIDE.md`、`AGENTS.md`、根目录 `README.md` 和
  `experiments/llm_style_trajectory/README.md`，将保护检查改为确认 legacy 归档文件和
  Make Me a Hanzi 数据仍存在。
- 由于当前沙箱无法写 `.git/index.lock`，本次经用户允许使用 PowerShell `Move-Item` 完成文件组织，
  没有使用 `git mv` 写入 index。

---

## 2026-06-17 风格诊断 v2：异常样本定位与人工看图校验包

- 新增 `experiments/llm_style_trajectory/src/style_visual_audit.py`，从上一轮
  `style_diagnostic_summary.csv` 中自动挑选异常/代表样本。
- 新增 `experiments/llm_style_trajectory/tests/test_style_visual_audit.py`，覆盖 fake summary、
  high/low aspect spread、行楷 connector 过长、候选去重、manifest fallback、人工看图说明和不 import SDK。
- 生成 visual audit 输出目录：
  `experiments/llm_style_trajectory/outputs/style_visual_audit_20260617_224321/`。
- 输出：
  - `visual_audit_candidates.csv`
  - `visual_audit_report.md`
  - `visual_audit_checklist.md`
  - `visual_audit_image_manifest.csv`
  - `selected_images/`
  - `visual_audit_top_cases.png`
- 固定论文/汇报入口：
  `experiments/llm_style_trajectory/outputs/paper_figures/style_visual_audit_index.md`。
- 候选统计：18 个候选样本，其中 `high_aspect_spread=5`、`high_lishu_aspect=3`、
  `long_xingkai_connector=3`、`low_aspect_spread=3`、`representative=4`。
- 优先人工看图样本：`人` 三风格、`国/德/福` 行楷、`中` 三风格、`和` 三风格。
- 本轮只做诊断和人工校验包，不调参数；下一步应等待用户人工看图反馈后再决定调哪些 style profile 或 connector 参数。
# 2026-06-18 Connector / brush 可视化诊断图包

- 在 `experiments/llm_style_trajectory` 中新增 connector / brush 视觉诊断图包生成脚本，输入为 `style_visual_audit_20260617_224321` 和 `style_diagnostics_20260617_200746`。
- 生成输出目录：`experiments/llm_style_trajectory/outputs/connector_brush_visual_diagnostics_20260618_093510/`。
- 生成报告与清单：`connector_brush_diagnostic_report.md`、`connector_brush_diagnostic_cases.csv`、`connector_brush_image_manifest.csv`。
- 生成关键图：segment legend、`国/德/福` xingkai connector overlay、`人/中/和` 三风格 side-by-side、`人/好/风` lishu deformation、`人/xingkai` brush width diagnostic。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/connector_brush_visual_diagnostics_index.md`。
- 本轮只做视觉诊断和人工看图准备，不调 style/brush/modifier 参数，不调用 API，不连接 CoppeliaSim/AUBO i5，不做真实 IK/SDK/机器人命令。
# 2026-06-18 宽度 / 压力渐变可视化诊断

- 新增 `experiments/llm_style_trajectory/src/width_pressure_visualization.py`，为 `execution_trajectory.csv` 的 `width` / `pressure` 生成可复用渐变诊断图。
- 新增 `experiments/llm_style_trajectory/tests/test_width_pressure_visualization.py`。
- 生成输出目录：`experiments/llm_style_trajectory/outputs/width_pressure_visualization_20260618_101349/`。
- 生成 `width_pressure_visualization_report.md`、`width_pressure_visualization_manifest.csv`、`width_pressure_value_ranges.json` 和 64 张 `figures/*.png`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/width_pressure_visualization_index.md`。
- 关键观察：connector 数据上明显更细、更低压；主体 stroke width 在本轮 16 个样本中几乎恒定。因此旧图中看不出主体 stroke 内部粗细变化，主要是 execution 数据变化不足，而不是新的可视化失败。
- 本轮只做可视化诊断，不调参数、不改 planner、不调用 API、不连接 CoppeliaSim/AUBO i5、不做机器人接口。

# 2026-06-18 Execution refinement 实验

- 新增 execution refinement 配置、模块、实验脚本和测试：
  - `experiments/llm_style_trajectory/configs/execution_refinement_profiles.json`
  - `experiments/llm_style_trajectory/src/execution_refinement.py`
  - `experiments/llm_style_trajectory/src/execution_refinement_experiment.py`
  - `experiments/llm_style_trajectory/tests/test_execution_refinement.py`
  - `experiments/llm_style_trajectory/tests/test_execution_refinement_experiment.py`
- 修改 `execution_tools.py`，默认保持 baseline / flat 旧行为；只有显式传入 refinement 参数时才启用 conservative connector gate 和 stroke taper。
- 修改 `width_pressure_visualization.py`，新增浅暖灰背景、非白浅色端、`min_alpha`、`min_visible_linewidth` 等可读性参数。
- 真实输出目录：`experiments/llm_style_trajectory/outputs/execution_refinement_20260618_104837/`。
- 生成 `execution_refinement_summary.csv`、`execution_refinement_report.md`、`execution_refinement_cases.csv` 和 before/after 图。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_index.md`。
- 初步结果：`国/德/福/和` 行楷 connector 从“几乎每笔相连”下降到少量连接；stroke width / pressure 曲线已经进入 execution 层；可视化最浅颜色不再接近白色。
- 本轮仍不调用 API、不连接 CoppeliaSim/AUBO i5、不做 IK/SDK/机器人控制，也不改 `code/data` 或 legacy。

# 2026-06-18 Execution refinement 人工反馈收口

- 新增决策文档：`experiments/llm_style_trajectory/docs/execution_refinement_decision.md`。
- 在 `execution_refinement_profiles.json` 中新增 `candidate_default_v1` metadata：当前 conservative connector + simple_taper 作为下一轮候选默认，但暂不替换全局默认。
- 记录用户人工反馈：connector 更自然但偏保守；stroke taper 可见且效果不错；lishu 没有误连笔。
- 核查 `人/lishu` 可疑字段：refined CSV 中 connector 行数为 0，summary 中 `after_connector_draw_length=0.0`；`3.3998` 是 `after_stroke_width_range`。
- 更新 paper figures 固定入口与阶段总结。下一步建议不是继续盲调，而是扩大样本看图或设计 `balanced` connector 档位。

# 2026-06-18 candidate_default_v1 多样本验证

- 新增并运行 `execution_refinement_validation.py`，把人工接受的 `candidate_default_v1` 扩展到 18 个样本做 before/after 验证。
- 输出目录：`experiments/llm_style_trajectory/outputs/execution_refinement_validation_20260618_120238/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/execution_refinement_validation_index.md`。
- 验证结果：18 个样本成功，失败 0；行楷 8 个样本的 connector 总数从 58 降到 5，connector 绘制长度从 4938.116 降到 349.252。
- `国/德/福/和` 仍保留少量 connector，`中/人/明/林` 行楷 connector 清零，需要用户人工看图判断 candidate 是否偏保守。
- 楷书/隶书 connector violation 为 0；stroke taper 在多样本中均打开了宽度变化。
- 本轮没有调参，没有接机器人接口，没有调用 API/CoppeliaSim/AUBO i5/SDK，也没有改动 `code/data` 或 legacy。

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

- 新增字体轮廓差距诊断配置、脚本和测试：
  - `experiments/llm_style_trajectory/configs/font_style_gap_chars.json`
  - `experiments/llm_style_trajectory/src/font_style_gap_analysis.py`
  - `experiments/llm_style_trajectory/tests/test_font_style_gap_analysis.py`
- 真实输出目录：`experiments/llm_style_trajectory/outputs/font_style_gap_analysis_20260618_144838/`。
- 固定论文/汇报入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_style_gap_analysis_index.md`。
- 字体可用情况：kaishu/xingkai/lishu 三种系统字体均可渲染；18 字 × 3 风格共 54 个样本成功，失败 0。
- 三风格均值：kaishu font aspect=1.029878 / trajectory=1.018672；xingkai font aspect=0.989059 / trajectory=1.070791；lishu font aspect=1.480275 / trajectory=1.465173。
- 关键诊断：lishu 的全局宽扁比例接近真实字体，但仍主要是 median 骨架的比例变换；xingkai connector 与字体连通性只有弱对应，当前 connection_count 均值 6.055556 仍反映较强人工 connector prior。
- 下一步参数升级应优先数据化估计 `horizontal_scale / vertical_scale`、stroke width distribution、component proportions、connector prior 和 projection distribution。
- 本轮只做 gap analysis，不调参数、不替换默认、不调用 API、不连接 CoppeliaSim/AUBO i5、不做机器人接口；字体轮廓不等于真实书写轨迹，仍需人工看图校验。

# 2026-06-18 Style profile 数据化升级方案

- 新增参数 schema：`experiments/llm_style_trajectory/configs/style_profile_parameter_schema.json`。
- 新增方案生成脚本：`experiments/llm_style_trajectory/src/style_profile_upgrade_plan.py`。
- 新增测试：`experiments/llm_style_trajectory/tests/test_style_profile_upgrade_plan.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/style_profile_upgrade_plan_20260618_150757/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/style_profile_upgrade_plan_index.md`。
- 参数矩阵覆盖 23 个参数，其中 style=10、component=2、process_prior=11。
- Phase 1 包含 7 个现在可估计的字体轮廓参数：`horizontal_scale`、`vertical_scale`、`base_width`、`stroke_width_distribution`、`horizontal_projection_distribution`、`vertical_projection_distribution`、`lishu_flatness`。
- Phase 2 处理 component/char-level 映射：`smoothness`、`corner_rounding`、`component_width_ratio`、`component_height_ratio`、`xingkai_connectedness_prior`。
- Phase 3 保留 process priors：速度、抬笔、压力、connector trigger/shape/width、stroke taper 等。
- 已生成 `prototype_style_profile_estimates.json`，但标记为 `_status=prototype_not_used_by_default` 和 `_warning=not wired into generation pipeline`；不接默认流程，不替换 `style_profiles.json`，不改变 `run_demo.py`。
- 本轮只做升级方案和参数分层，不调用 API、不连接 CoppeliaSim/AUBO i5、不做机器人接口，也不修改 shared data 或 legacy。

# 2026-06-18 Phase 1 font-outline readonly estimator

- 新增 `experiments/llm_style_trajectory/src/style_profile_phase1_estimator.py`，把 font gap analysis 中低风险可估计参数整理为只读候选 estimates。
- 新增 `experiments/llm_style_trajectory/tests/test_style_profile_phase1_estimator.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/style_profile_phase1_estimates_20260618_152952/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/style_profile_phase1_estimates_index.md`。
- 输出 `style_profile_phase1_estimates.json`、`style_profile_phase1_parameter_comparison.csv`、`style_profile_phase1_estimate_report.md`、`style_profile_phase1_estimate_warnings.csv` 和三张图。
- estimates 明确标记 `_status=readonly_estimate_not_used_by_default`、`_warning=not wired into generation pipeline`。
- 当前 vs Phase 1：lishu scale hint 与当前接近但略高，xingkai scale hint 置信度低且与当前方向不同；base width hints 为 kaishu=6.320909、lishu=8.956169、xingkai=9.575023。
- 明确 unsupported：connection/connector、pressure、speed、pen_up、robot dynamics。
- 本轮不接默认、不改 `style_profiles.json`、不改变 `run_demo.py`、不生成新轨迹、不调用 API/CoppeliaSim/AUBO i5。
# 2026-06-18 Phase 1 readonly estimates 非默认对比图验证

- 新增 `phase1_profile_comparison.py` 和对应测试，使用上一轮 `style_profile_phase1_estimates.json` 生成 `style_profile_phase1_candidate.json`。
- candidate profile 标记为 `_status=comparison_only_not_default`，仅用于显式对比实验；没有替换默认 `style_profiles.json`，没有改变 `run_demo.py` 默认行为。
- 输出目录：`experiments/llm_style_trajectory/outputs/phase1_profile_comparison_20260618_155353/`。
- 输出 `phase1_profile_comparison_summary.csv`、`phase1_profile_comparison_report.md`、`phase1_profile_comparison_manifest.csv` 和 current/phase1 对比图。
- paper figures 入口：`experiments/llm_style_trajectory/outputs/paper_figures/phase1_profile_comparison_index.md`。
- 结果表明 kaishu 基本不变，lishu 只小幅变化，xingkai 的全局 scale 会改变 aspect 但不会解决 connector 规则问题；下一步更适合进入 component/stroke-level style modeling。
- 本轮未调用 API，未连接 CoppeliaSim/AUBO i5，未 import SDK，未修改 shared data 或 legacy。
# 2026-06-18 小论文实验对比方案与实验矩阵整理

- 在 `experiments/llm_style_trajectory/docs/mini_paper_experiment_plan.md` 中整理了当前主线可写小论文的实验对比方案。
- 新增 `experiments/llm_style_trajectory/configs/mini_paper_experiment_matrix.json`，记录 6 组推荐实验、指标、状态、优先级、已有结果路径和外部方法功能对比维度。
- 新增 `experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_experiment_plan_index.md`，作为论文/汇报固定入口。
- 建议主线为“自然语言约束驱动的书法机器人参数化轨迹生成与执行前检查方法”。
- 当前最适合作为正文主实验的是 modifier controllability、xingkai connector rule、execution width/pressure、motion continuity retiming 和 robot-interface precheck chain；font outline gap / Phase 1 readonly estimates 更适合作为限制和后续工作。
- 本轮不新增算法、不调参数、不调用 API、不连接 CoppeliaSim/AUBO i5、不做 IK/SDK/机器人命令。
# 2026-06-18 小论文固定图表包整理

- 新增 `mini_paper_figure_pack.py`，把已完成的 modifier、行楷 balanced、execution width/pressure、retiming、robot precheck、external comparison 和 style gap 资料整理到固定图表包。
- 输出目录：`experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/`。
- 生成 `mini_paper_figure_index.md`、`mini_paper_figure_manifest.csv`、`mini_paper_table_manifest.csv` 和 `missing_sources.csv`。
- 图表包当前 `figure_count=12`、`table_count=3`、`missing_count=0`。
- 需要人工重点看的图已经在 index 中标出：modifier 三联图、行楷 connector 对比图、execution width/pressure 图和 lishu flatness gap 补充图。
- 本轮只整理已有结果，没有新增算法、没有调参、没有调用 API/CoppeliaSim/AUBO i5/SDK、没有修改 `code/data` 或 legacy。

# 2026-06-18 小论文人工视觉评价与图注草稿整理

- 围绕 `experiments/llm_style_trajectory/outputs/paper_figures/mini_paper_figures/` 新增人工看图评价表和论文写作草稿。
- 新增 `mini_paper_visual_evaluation_template.md`、`mini_paper_figure_captions_draft.md`、`mini_paper_experiment_section_outline.md`。
- 新增 `human_visual_evaluation_template.csv`，包含 15 个待人工填写评价项。
- 图注草稿已覆盖 Figure 1-4、Table 1-3 和 supplementary style gap / Phase 1 图。
- 实验章节骨架已包含 8 个小节：实验设置、modifier 可控性、行楷 connector 消融、execution width/pressure、motion continuity 与 retiming、robot-interface precheck dry-run、外部功能对比、局限性与未来工作。
- 本轮没有调参数、没有新增生成算法、没有调用 API/CoppeliaSim/AUBO/SDK、没有修改 shared data 或 legacy。

## 2026-06-19 Font-outline-derived trajectory basis feasibility

- 暂停 mini-paper 图表包装，转向方法主线诊断：比较 MakeMeAHanzi median 与字体轮廓 skeleton candidate，判断是否值得继续把 MakeMeAHanzi median 作为唯一轨迹基底。
- 新增 `experiments/llm_style_trajectory/src/font_outline_basis_feasibility.py`、`configs/font_outline_basis_chars.json` 和对应测试。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_outline_basis_feasibility_20260619_115008/`。
- paper figures 入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_feasibility_index.md`。
- 三字体 skeleton 成功率均为 10/10；视觉上 `山`、`德`、`福` 等样本显示字体轮廓骨架更能呈现行楷/隶书差异，但复杂字 skeleton 分叉和端点多，后续不能直接接轨迹生成，需要人工看图和骨架后处理。
- 本轮只做只读 feasibility / diagnostic，不替换默认 pipeline，不改 profile 或 run_demo 默认行为，不调用 API/CoppeliaSim/AUBO/SDK，不修改 shared data 或 legacy。

## 2026-06-19 Font outline basis audit

- 新增 `font_outline_basis_audit.py`，把 font-outline feasibility 输出整理为人工看图筛选包和 skeleton 问题分类。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_outline_basis_audit_20260619_120211/`。
- paper figures 入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_outline_basis_audit_index.md`。
- 生成 `font_outline_basis_audit_candidates.csv`、`font_outline_basis_audit_report.md`、`visual_audit_checklist.md`、`font_outline_basis_image_manifest.csv` 和 `selected_images/`。
- 共 30 条候选，10 张 selected images；主要问题为 disconnected skeleton、complex skeleton、high branch/endpoint count 和 lishu high aspect gap。
- 结论：下一步应先人工看图决定哪些 font skeleton 值得继续做轨迹基底；本轮不接默认 pipeline、不调参数、不接机器人接口。
## 2026-06-19 Font skeleton cleanup prototype

- 在 `experiments/llm_style_trajectory` 内新增 kaishu / lishu font skeleton cleanup prototype。
- 输入：`outputs/font_outline_basis_feasibility_20260619_115008/`。
- 输出：`outputs/font_skeleton_cleanup_prototype_20260619_122355/`。
- 固定入口：`outputs/paper_figures/font_skeleton_cleanup_prototype_index.md`。
- 只处理 `山 / 中 / 人 / 永 / 风` × `kaishu / lishu`，明确不处理 xingkai，不接默认 pipeline。
- 成功率 kaishu=5/5、lishu=5/5。轻量 cleanup 主要减少 endpoint/branch，对楷书更明显，对隶书更保守。
- 仍需人工看图判断 cleaned skeleton 是否保留风格且接近可写路径；当前不生成正式轨迹，不接机器人接口，不调用 API，不改 shared data 或 legacy。
## 2026-06-19 Font skeleton path extraction prototype

- 在 `experiments/llm_style_trajectory` 内新增 very small-sample path extraction prototype。
- 输入：`outputs/font_skeleton_cleanup_prototype_20260619_122355/`。
- 输出：`outputs/font_skeleton_path_extraction_20260619_123527/`。
- 固定入口：`outputs/paper_figures/font_skeleton_path_extraction_index.md`。
- 只处理 `山/kaishu`、`人/kaishu`、`中/kaishu`、`山/lishu`、`永/lishu`；不处理 xingkai 和复杂字。
- 五个样本都提取到候选 path segments；`中/kaishu` 分叉较多，`永/lishu` 多连通分量，后续需要人工看图。
- 当前仍是 diagnostic：不生成正式 `trajectory.csv`，不替换默认 pipeline，不调用 API/CoppeliaSim/AUBO/SDK，不改 shared data 或 legacy。
## 2026-06-19 Font-derived trajectory trial

- 在 `experiments/llm_style_trajectory` 内新增最小范围 font-derived trajectory trial。
- 输入：`outputs/font_skeleton_path_extraction_20260619_123527/`。
- 输出：`outputs/font_derived_trajectory_trial_20260619_125428/`。
- 固定入口：`outputs/paper_figures/font_derived_trajectory_trial_index.md`。
- 只处理 `山/kaishu`、`人/kaishu`、`山/lishu` 三个低风险样本；不处理 xingkai 和复杂字。
- 每个样本只生成 `font_derived_trial_trajectory.csv`、summary JSON 和 compare 图；没有生成正式 `trajectory.csv`，也没有 execution/workspace/robot 输出。
- 观察：`人/kaishu` 最干净，`山/lishu` 风格信号明显，`山/kaishu` 暴露 candidate order 仍非真实笔顺。下一步应做 stroke ordering / simplification 小样本验证。
# 2026-06-19 Font skeleton stroke ordering / simplification prototype

- 在 `experiments/llm_style_trajectory` 内新增极小样本 stroke ordering prototype。
- 输入：`outputs/font_derived_trajectory_trial_20260619_125428/`。
- 输出：`outputs/font_skeleton_stroke_ordering_20260619_132543/`。
- 只处理 `人/kaishu` 和 `山/lishu`，不处理 `山/kaishu`、xingkai 或复杂字。
- `人/kaishu`：raw_segment_count 4 -> simplified_segment_count 2，ordered_stroke_like_count=2。
- `山/lishu`：raw_segment_count 4 -> simplified_segment_count 4，ordered_stroke_like_count=4，warning=`segment_count_unchanged`。
- 固定 paper figures 入口：`outputs/paper_figures/font_skeleton_stroke_ordering_index.md`。
- 本轮仍是 diagnostic：不是真实笔顺恢复，不生成正式 `trajectory.csv`，不接默认 pipeline/机器人接口，不调用 API，不修改 `code/data` 或 legacy。

# 2026-06-19 Median-to-font skeleton alignment / adaptation prototype

- 转向 B 路线：median-to-font skeleton alignment / adaptation prototype。
- 新增脚本：`experiments/llm_style_trajectory/src/median_font_alignment_prototype.py`。
- 新增测试：`experiments/llm_style_trajectory/tests/test_median_font_alignment_prototype.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/median_font_alignment_20260619_145307/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/median_font_alignment_index.md`。
- 只处理 `人/kaishu` 与 `山/lishu`；不处理 xingkai、复杂字或其他字符。
- `人/kaishu`：projection distance 从 6.557520 降至 4.918140(alpha=0.25) / 3.278760(alpha=0.5)，stroke_count=2 保持不变。
- `山/lishu`：projection distance 从 36.000849 降至 29.389616(alpha=0.25) / 23.972679(alpha=0.5)，stroke_count=3 保持不变；但 bbox aspect 未朝 lishu font aspect 靠近，v2 需要加入 stroke-level bbox / anchor alignment。
- 本轮不生成正式 `trajectory.csv`，不接默认 pipeline，不接机器人接口，不调用 API，不修改 `code/data` 或 legacy。

# 2026-06-19 Median-font adaptation v2 prototype

- 在 `experiments/llm_style_trajectory` 内新增 B 路线 v2：global bbox alignment + stroke-level anchor alignment。
- 脚本：`experiments/llm_style_trajectory/src/median_font_adaptation_v2.py`。
- 测试：`experiments/llm_style_trajectory/tests/test_median_font_adaptation_v2.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/median_font_adaptation_v2_20260619_154351/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/median_font_adaptation_v2_index.md`。
- `人/kaishu`：v2 conservative / stronger 均进一步降低 projection distance，aspect gap 也小幅改善，stroke_count=2 保持不变。
- `山/lishu`：v2 projection distance 继续下降，但 aspect gap 未明显改善；stronger 达到 18 px shift cap，后续需人工看图判断是否只是牵引变形。
- 本轮仍是 diagnostic：不生成正式 `trajectory.csv`，不接默认 pipeline，不接机器人接口，不调用 API，不修改 `code/data` 或 legacy。

# 2026-06-19 Lishu structure adaptation v3 prototype

- 在 `experiments/llm_style_trajectory` 内新增只针对 `山/lishu` 的 structure-constrained adaptation v3。
- 脚本：`experiments/llm_style_trajectory/src/lishu_structure_adaptation_v3.py`。
- 测试：`experiments/llm_style_trajectory/tests/test_lishu_structure_adaptation_v3.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/lishu_structure_adaptation_v3_20260619_155525/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/lishu_structure_adaptation_v3_index.md`。
- 结果：projection distance 20.563365(v2) -> 20.157518 / 20.090813(v3)，bbox aspect 0.936821 -> 0.958776 / 0.958299，lower-half width 156.629793 -> 158.148182 / 159.569313。
- 诊断：structure-level constraints 对 `山/lishu` 有小幅正向作用，但两个 v3 variant 都触达 22 px shift cap，仍需要人工看图判断是否出现拉扯；下一步不宜直接接默认 pipeline，更适合做 component-level alignment。
- 本轮不生成正式 `trajectory.csv`，不接默认 pipeline，不接机器人接口，不调用 API，不修改 `code/data` 或 legacy。

# 2026-06-19 Lishu component-level alignment prototype

- 在 `experiments/llm_style_trajectory` 内新增只针对 `山/lishu` 的 component-level alignment prototype，停止继续加大 v3 的全局/结构拉扯。
- 脚本：`experiments/llm_style_trajectory/src/lishu_component_alignment_prototype.py`。
- 测试：`experiments/llm_style_trajectory/tests/test_lishu_component_alignment_prototype.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/lishu_component_alignment_20260619_160805/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/lishu_component_alignment_index.md`。
- component groups：`left_group=2`、`center_group=2`、`right_group=3`、`lower_support_group=12`。
- 结果：projection distance 20.090813(v3) -> 19.949109(component conservative) / 20.215119(component stronger)；bbox aspect 0.958299 -> 0.970717 / 0.971593；lower-half width 159.569313 -> 160.028913 / 160.743366。
- 诊断：component-level alignment 对 aspect gap 和 lower-half width 有小幅正向作用，conservative 的 projection distance 也略好于 v3；但 stronger projection 反而略差，两个 variant 都触达 24 px shift cap。下一步如果继续，应优先改进 component target 定义，而不是继续增大 alpha 或拉扯强度。
- 本轮仍是 diagnostic：不生成正式 `trajectory.csv`，不接默认 pipeline，不接机器人接口，不调用 API，不修改 `code/data` 或 legacy。

# 2026-06-19 Trajectory style route decision report

- 暂停继续新增算法和调参，完成 A/B/C 三条轨迹风格路线的决策总结。
- 新增文档：`experiments/llm_style_trajectory/docs/trajectory_style_route_decision_report.md`。
- 新增 JSON 摘要：`experiments/llm_style_trajectory/configs/trajectory_style_route_decision_summary.json`。
- 新增固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/trajectory_style_route_decision_index.md`。
- 结论：A 路线保留为稳定 baseline 和机器人 dry-run/precheck backbone；B 路线作为保留笔顺的安全风格适配研究方向；C 路线作为小样本、人工筛选的 style basis research，不接默认 pipeline。
- 当前推荐：先写 hybrid route design spec，把 A 的可写性和执行链路、B 的有界形态适配、C 的字体轮廓风格参考组合起来；不要继续盲调 connector/taper，也不要直接用 font skeleton 替换 MakeMeAHanzi median。
- 边界：本轮只做证据整理和路线比较，不新增生成算法，不调用 API，不连接 CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 Hybrid style trajectory design spec

- 完成 hybrid route 方案设计和接口边界整理，不新增算法、不调参、不接默认 pipeline。
- 新增文档：`experiments/llm_style_trajectory/docs/hybrid_style_trajectory_design_spec.md`。
- 新增 JSON 摘要：`experiments/llm_style_trajectory/configs/hybrid_style_trajectory_design_spec.json`。
- 新增固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/hybrid_style_trajectory_design_index.md`。
- 设计分工：A 保留为 stable median trajectory / execution / robot precheck backbone；B 是 trial-only bounded adaptation；C 是人工筛选的 font reference / candidate basis；Human audit gate 必须保留。
- 推荐下一步 prototype：H2（A median + C font reference constraints only），先整理可信字体参考约束，不移动轨迹点、不生成正式 `trajectory.csv`。
- 边界：本轮不调用 API，不连接 CoppeliaSim/AUBO/SDK，不修改 `style_profiles.json`、`run_demo.py` 默认行为、`code/data` 或 legacy。

# 2026-06-19 H2 font reference constraints package

- 按 hybrid route 推荐执行 H2：只提取 font reference constraints，不移动 MakeMeAHanzi median 点。
- 新增脚本：`experiments/llm_style_trajectory/src/font_reference_constraints_package.py`。
- 新增测试：`experiments/llm_style_trajectory/tests/test_font_reference_constraints_package.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/font_reference_constraints_20260619_230426/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/font_reference_constraints_index.md`。
- 处理 7 个 kaishu / lishu 代表样本，明确不处理 xingkai 或机器人链路。
- 约束统计：usable_for_adaptation=25，visual_reference_only=25，unsafe_for_direct_use=34。
- 结论：下一步 B adaptation 可优先参考 bbox_aspect、lower_half_width_ratio、left_right_spread；raw skeleton path 和 unordered skeleton segments 只能作为人工视觉参考或风险提示，不能直接驱动点移动。
- 边界：本轮不生成 adapted CSV、正式 trajectory、execution/workspace/robot 文件，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 H1-lite constraint-bounded median adaptation prototype

- 在 `experiments/llm_style_trajectory` 内新增 H1-lite：只使用 H2 中 `usable_for_adaptation` 的安全字体参考约束，对 MakeMeAHanzi median 做有界形态试探。
- 脚本：`experiments/llm_style_trajectory/src/constraint_bounded_adaptation_h1_lite.py`。
- 测试：`experiments/llm_style_trajectory/tests/test_constraint_bounded_adaptation_h1_lite.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/constraint_bounded_adaptation_h1_lite_20260619_231903/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/constraint_bounded_adaptation_h1_lite_index.md`。
- 只处理 `人/kaishu` 和 `山/lishu`，不处理 xingkai 或复杂字。
- 结果：`人/kaishu` 的变化很小，stroke_count=2 保持不变；`山/lishu` 的 bbox aspect 从 0.945007 推到 0.998870 / 1.048676，lower-half width 从 187.343097 推到 193.898937 / 199.553901，stroke_count=3 保持不变。
- 诊断：H1-lite 是比 raw skeleton path 更安全的 hybrid B prototype；仍需人工看图确认 balanced variant 是否自然，当前不接默认 pipeline。
- 边界：本轮不生成正式 `trajectory.csv`，不接 execution/workspace/robot，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-19 H1-lite style contrast expansion

- 在 `experiments/llm_style_trajectory` 内新增 H1-lite 同字风格对照扩展，只新增处理 `山/kaishu`，并读取既有 `山/lishu` H1-lite 输出做对照。
- 脚本：`experiments/llm_style_trajectory/src/h1_lite_style_contrast_expansion.py`。
- 测试：`experiments/llm_style_trajectory/tests/test_h1_lite_style_contrast_expansion.py`。
- 输出目录：`experiments/llm_style_trajectory/outputs/h1_lite_style_contrast_20260619_234043/`。
- 固定入口：`experiments/llm_style_trajectory/outputs/paper_figures/h1_lite_style_contrast_index.md`。
- `山/kaishu` balanced：bbox aspect=0.984478，lower-half width=192.664933，max shift=4.341142 px，path ratio=0.996284。
- `山/lishu` balanced：bbox aspect=1.048676，lower-half width=199.553901，max shift=9.845336 px，path ratio=0.989006。
- 同字 style gap：bbox_aspect_gap 0.000000 -> 0.064198，lower_half_width_gap 0.000000 -> 6.888968。
- 诊断：H1-lite 让 `山/lishu` 比 `山/kaishu` 更明显地朝宽底方向移动，同时保持 stroke_count=3；下一步应先人工看 contrast 图，再决定是否扩到 `风/lishu`。
- 边界：trial-only / not_used_by_default；不生成正式 `trajectory.csv`，不接默认 pipeline、execution、workspace 或 robot，不调用 API/CoppeliaSim/AUBO/SDK，不修改 `code/data` 或 legacy。

# 2026-06-20 Hybrid section refinement v1

- 在 `experiments/llm_style_trajectory` 内新增 `hybrid_section_refinement_v1.py`，只对 `风/lishu` 做 hybrid section refinement。
- 优先使用 font component bbox；若 component 不稳定，则回退到 `top/mid/bottom`。本轮真实结果走的是 `top_mid_bottom_fallback`。
- 输出目录：`experiments/llm_style_trajectory/outputs/hybrid_section_refinement_20260620_215513/`。
- 关键结果：`bbox_aspect 1.188427 -> 1.259425 / 1.306963`，`lower_half_width 215.040000 -> 219.856896 / 223.297536`，`max_shift 5.543559 / 8.824495 px`，`path_ratio 0.982155 / 0.973699`。
- 诊断：这轮更像是在验证 section-level fallback 的安全性，而不是 component-first 的真正收益；但相比前面更激进的 v3/component-level，大拉扯已明显收敛，适合作为后续 section 约束整理的基础。

# 2026-06-21 Section constraints package / fallback guide

- 在 `experiments/llm_style_trajectory` 内新增 `section_constraints_package.py`，把 section-level 证据整理成 machine-readable 的约束包与 fallback guide。
- 证据来源整合自：
  - `font_reference_constraints_20260619_230426`
  - `h1_lite_style_contrast_20260619_234043`
  - `h1_lite_feng_lishu_risk_trial_20260620_212829`
  - `hybrid_section_refinement_20260620_215513`
- 输出目录：`experiments/llm_style_trajectory/outputs/section_constraints_package_20260621_003023/`
- 关键规则：component bbox stable 时优先 component-first；不稳定时回退 top/mid/bottom fallback。usable / reference-only / unsafe 约束都已写入 JSON/CSV/report。
- 诊断：`山/kaishu` 与 `山/lishu` 适合作为 future B 路线的安全输入；`风/lishu` 需 fallback-first 处理。该包是后续 B 路线的约束封装，不是默认流程。


- 2026-06-21: B-route constraint registry + registry-gated probe landed. Registry unifies H2 + section constraints; probe covers 山/lishu and 风/lishu only, trial-only, not used by default.

- 2026-06-21: B-route handoff note added for new threads. It is a short entry map, not a new algorithm, and keeps B route registry-gated / trial-only.

- 2026-06-21：完成 B-route 三张关键图的中文化与差异辅助重绘，只重绘表达，不改算法。结论：`山/kaishu vs 山/lishu` 仍属弱差异；`风/lishu` conservative vs balanced 最接近；`hybrid_section_compare_cn` 最适合人工复检。
- 2026-06-21：新增 B-route visual conclusion freeze note 和 JSON 摘要，冻结三张关键中文图的论文角色；除非后续出现更强且经人工复检认可的新图，否则不再随意更换它们的正文/补充/局限性定位。
- 2026-06-23：完成 A-route 大样本展示层补强。新增 `a_route_showcase_chars.json`、`a_route_showcase_pack.py` 与测试，生成 `experiments/llm_style_trajectory/outputs/a_route_showcase_20260623_091212/`。本轮把 connector / 连笔重新定位为“自然语言驱动的跨笔过渡控制 / execution 行为控制”，不再作为真实行楷风格迁移证据；关键图固定到 `outputs/paper_figures/a_route_showcase_index.md`。
- 2026-06-29：更新大论文结构文档。新的推荐结构调整为：第 3 章“多模态风格意图理解与目标字图像生成方法”、第 4 章“目标字图像到可写轨迹恢复方法”、第 5 章“execution / 仿真 / 执行前检查方法”。同步更新 `THESIS_FRAMEWORK_2026.md`、`experiments/llm_style_trajectory/docs/thesis_mini_paper_positioning_note.md` 与 `CURRENT_PROJECT_GUIDE.md`。当前建议将第 4 章作为更优先的小论文候选，第 3 章在后续时间更充裕时允许引入深度学习并基于公开 few-shot font / calligraphy generation 基线做场景化改进。
- 2026-07-01：确定当前大论文题目为“机器人书写目标字图像生成与轨迹恢复研究”。同步更新 `THESIS_FRAMEWORK_2026.md`、`experiments/llm_style_trajectory/docs/thesis_mini_paper_positioning_note.md` 与 `CURRENT_PROJECT_GUIDE.md`，并在论文框架文档中将第 4 章相关表述从“可写轨迹恢复”统一收敛为“书写轨迹恢复 / 轨迹恢复”，避免术语过于自造化。
