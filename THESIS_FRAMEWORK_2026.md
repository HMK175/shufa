# 论文框架与当前研究主线记录

记录日期：2026-06-06

## 当前建议主线

当前大论文建议从早期“真实图像骨架提取 + 笔画拆分 + RL 优化”主线，收束为：

> 基于大语言模型规划与结构化字形知识的多风格书法机器人轨迹生成方法

核心思想不是让 LLM 直接输出轨迹 CSV，而是让 LLM 或规则 planner 负责自然语言任务解析、风格选择和工具编排；轨迹点仍由可解释、可复现的确定性工具生成。

建议系统链路：

```text
自然语言输入
→ LLM / 规则 planner 生成结构化书写计划
→ Make Me a Hanzi 字形与笔顺知识库
→ 字体样本统计 style profile
→ 参数化轨迹生成
→ style-aware brush rendering
→ 虚拟书写评价 / 后续机器人执行
```

当前已验证的阶段结果：

- `experiments/llm_style_trajectory` 已建立为独立实验模块。
- Make Me a Hanzi 可提供标准字形、笔顺和 median 轨迹。
- 已使用三种 Windows 字体样本进行 style profile 数据化：
  - 楷书：`simkai.ttf`
  - 行楷：`STXINGKA.TTF`
  - 隶书：`SIMLI.TTF`
- 已从字体渲染图统计估计部分形态参数：
  - `horizontal_scale`
  - `vertical_scale`
  - `smoothness`
  - `corner_rounding`
  - `speed_scale`
- 以下书写过程参数仍为人工先验：
  - `connection_strength`
  - `allow_interstroke_connections`
  - `pen_up_height`
- 已完成 fixed renderer 与 style-aware brush renderer 的虚拟书写评价。
- 已修正隶书错误连笔问题：静态字体不能可靠估计连笔/抬笔信息，隶书目标字体无连笔时不应插入跨笔连接。

## 大论文结构建议

### 第 1 章 绪论

主要内容：

- 书法机器人、文化传承、教育展示和人机交互背景。
- 人工示教成本高，多风格轨迹生成困难。
- 传统图像骨架拆分在复杂字形、交点和粘连结构上不稳定。
- 引入 LLM 规划和结构化字形知识的意义。

建议定位：

> 本研究不追求任意真实书法图像的通用识别，而是面向结构清晰的标准字形和规范书写场景，构建可解释、可复现、可执行的多风格书法机器人轨迹生成系统。

### 第 2 章 相关研究与技术基础

建议包括：

- 书法机器人轨迹生成与机器人书写控制。
- 汉字笔顺、笔画结构和字形知识库。
- 字体/书法风格参数化方法。
- LLM 在机器人任务规划和工具调用中的应用。
- 轨迹评价与图像相似度指标：IoU、Chamfer、aspect ratio error、中心偏移等。

### 第 3 章 系统总体方案设计

本章作为系统框架章。

建议模块：

- 自然语言任务解析与 planner。
- Make Me a Hanzi 字形结构知识库。
- 字体样本统计 style profile 构建。
- 参数化轨迹生成模块。
- style-aware brush rendering 模块。
- 虚拟评价与机器人输出接口。

需要重点画系统框图，突出：

```text
LLM/Planner 只负责规划，不直接生成 CSV；
轨迹由结构化知识和确定性工具生成。
```

### 第 4 章 字形结构与风格参数构建方法

建议内容：

- Make Me a Hanzi 数据说明：
  - 标准字形；
  - 笔顺；
  - 每笔 median；
  - 结构化笔画信息。
- 基准轨迹生成方式。
- 三种字体样本来源：
  - 楷书 `simkai.ttf`
  - 行楷 `STXINGKA.TTF`
  - 隶书 `SIMLI.TTF`
- 字体渲染样本的几何指标统计：
  - bbox 宽高；
  - aspect ratio；
  - 前景比例；
  - 重心；
  - 估计笔画宽度；
  - turning / curvature 近似。
- style profile 参数映射。

必须明确边界：

- 可由字体图像估计的参数：形态尺度、平滑/转折、粗略速度相关参数。
- 不可由静态字体可靠估计的参数：连笔、抬笔高度等书写过程参数。

### 第 5 章 多风格轨迹生成与笔刷渲染方法

建议内容：

- 基于 median 的轨迹生成。
- 横纵缩放、重采样、平滑和转折处理。
- 笔画间连接控制：
  - `allow_interstroke_connections`
  - `connection_strength`
  - 明确连接参数是书写过程先验。
- CSV 输出格式。
- fixed renderer baseline。
- style-aware brush renderer：
  - 基础笔宽；
  - 起笔/收笔变化；
  - 转折处宽度调整；
  - 横竖方向差异；
  - 风格相关笔刷参数。

### 第 6 章 实验与结果分析

建议实验组：

1. 三风格轨迹生成可视化实验  
   比较 `山/中/永` 等字在 kaishu / xingkai / lishu 下的轨迹差异。

2. style profile 数据化实验  
   说明哪些参数来自字体统计，哪些仍是人工先验。

3. fixed renderer 与 style-aware brush renderer 消融实验  
   已有结果示例：

   | style | fixed IoU | style_brush IoU |
   |---|---:|---:|
   | kaishu | 0.1701 | 0.1833 |
   | xingkai | 0.2352 | 0.2478 |
   | lishu | 0.1951 | 0.2124 |

   注意：上述为修正隶书连笔前的 brush 消融结果；修正后应使用最新 batch 指标作为正式结果。

4. 连笔先验修正实验  
   说明去掉隶书错误连笔后，IoU 下降但书写逻辑更正确。

5. 虚拟书写评价  
   指标包括：
   - IoU；
   - Chamfer distance；
   - aspect ratio error；
   - foreground ratio；
   - center offset；
   - connection_count；
   - out_of_bounds。

6. 后续可扩展：机器人实写实验  
   如果具备条件，可加入机械臂/写字机绘制验证。

### 第 7 章 总结与展望

总结贡献：

- 引入 LLM/Planner 的书写任务规划框架。
- 利用 Make Me a Hanzi 构建结构化字形轨迹。
- 基于字体样本统计构建可解释 style profile。
- 实现参数化多风格轨迹生成。
- 构建 style-aware brush rendering 与虚拟评价闭环。

展望：

- 接入真实 LLM API 或本地模型。
- 使用示教轨迹或真实书写过程数据估计连笔、抬笔和速度参数。
- 扩展更多字体与书法风格。
- 完成真实机器人书写验证。

## 小论文建议

小论文不建议写整个大系统，范围过大。建议聚焦在大论文第 4、5、6 章中的一部分：

> 字体样本统计驱动的多风格书法机器人轨迹生成与虚拟评价方法

建议小论文题目方向：

- 《基于字体几何特征统计的多风格书法机器人轨迹生成方法》
- 《融合结构化字形知识与风格参数的书法机器人轨迹生成研究》
- 《面向书法机器人的参数化多风格轨迹生成与虚拟评价方法》

小论文推荐主线：

```text
Make Me a Hanzi 结构轨迹
→ 字体几何统计 style profile
→ 参数化多风格轨迹生成
→ style-aware brush rendering
→ 虚拟书写评价
```

小论文中可以弱化 LLM，仅作为后续自然语言规划接口或系统扩展，不建议在真实 LLM 尚未接入前把 LLM 写成核心贡献。

小论文可写贡献：

1. 构建基于 Make Me a Hanzi 的标准笔画轨迹生成流程。
2. 从楷书、行楷、隶书字体样本统计风格参数。
3. 实现参数化多风格轨迹 CSV 生成。
4. 设计 style-aware brush rendering。
5. 使用 IoU、Chamfer、aspect ratio error 等指标进行虚拟书写评价。

## 当前表述边界

需要避免的过度表述：

- 不要说“已经学习真实书法风格”。
- 不要说“LLM 已经自动生成机器人轨迹”。
- 不要说“可处理任意真实书法图像”。
- 不要把 `connection_strength`、`allow_interstroke_connections`、`pen_up_height` 说成从静态字体图像估计得到。

当前稳妥表述：

> 本研究基于结构化字形知识和字体样本几何统计，构建参数化多风格书法机器人轨迹生成方法；大语言模型或规则 planner 负责自然语言任务解析和工具编排，轨迹由可解释的确定性模块生成。

## 后续优先级

建议后续工作顺序：

1. 完成 LLM planner 框架：mock / api / local 模式，但默认不依赖网络。
2. 在最新修正后的 batch 上整理正式实验指标。
3. 选择若干代表字生成论文图，包括轨迹图、brush render 图、target overlay 图。
4. 如条件允许，做简单机器人或绘图机书写验证。
5. 小论文优先围绕“字体统计 style profile + 参数化轨迹 + 虚拟评价”撰写。

---

## 2026-06-13 补充：LLM planner + style modifiers 当前证据链

详细阶段总结见：

```text
LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md
```

当前更适合采用的大论文主线可以进一步明确为：

> 基于大语言模型规划与受控风格修饰符的书法机器人轨迹生成方法

其中 LLM / planner 的作用不是直接生成轨迹点或 CSV，而是输出结构化书写计划与离散 `style_modifiers`；本地系统通过 request boundary validation 和白名单映射函数，将自然语言约束转化为可解释的轨迹参数变化。

已完成的三类自然语言约束验证：

| 类别 | 示例语义 | modifier | 主要评价指标 |
|---|---|---|---|
| 连笔控制 | 不要连笔 / 默认 / 更连贯 | `connection_preference` | `connection_strength`, `connection_count`, `path_length`, `pen_up_count` |
| 宽扁控制 | 宽扁一点 / 更宽 | `shape_emphasis` | `horizontal_scale`, `vertical_scale`, `bbox_width`, `bbox_height`, `aspect_ratio` |
| 圆滑控制 | 更圆滑 / 更平滑 / 更保守 | `smoothness_level` | `smoothness`, `total_turning_angle`, `max_turning_angle`, `path_length` |

可作为第 6 章实验图表的当前输出：

```text
experiments/llm_style_trajectory/outputs/batch_20260611_210502/modifier_ablation_u5c71.png
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_shape_u4e2d.png
experiments/llm_style_trajectory/outputs/batch_20260613_085440/modifier_ablation_smoothness_u6c38.png
```

当前创新点应表述为“自然语言意图到可解释轨迹参数的受控映射”，而不是“LLM 直接生成书法轨迹”。
