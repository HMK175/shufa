# 面向书法机器人的自然语言约束驱动参数化轨迹生成及执行前检查方法

## 核心主张

本文面向书法机器人从自然语言书写意图到执行前准备之间缺少可解释中间层的问题，提出一种“自然语言约束解析 - 参数化轨迹生成 - 执行层表达 - 执行前检查”的方法链，实现可控轨迹生成与 dry-run 准备，但不以强字体风格迁移、真实字体学习或实机闭环验证为目标。

## 摘要

针对书法机器人中自然语言书写意图难以稳定映射为可执行轨迹、中心线轨迹缺少执行语义以及机器人接口前检查链不完整的问题，本文提出一种面向书法机器人的自然语言约束驱动参数化轨迹生成及执行前检查方法。该方法首先由 planner 将用户请求解析为结构化书写约束，再通过本地确定性的 style modifier 和参数化 style profile 在 MakeMeAHanzi median 笔画基础上生成中心线轨迹；随后构建 execution layer，对 width、pressure、connector 和 pen-up 等执行语义进行显式表达，并进一步推进到 workspace 映射、retiming、motion continuity 检查、CoppeliaSim dry-run 播放以及 AUBO dry-run precheck。实验结果表明，当前方法能够在整体外形控制、行楷连笔规则约束以及执行层粗细/压力表达方面形成可见差异，其中 execution layer 的 width/pressure 变化最为明显；同时，retiming 能够修复 target pose 中的时间连续性问题，并提升后续 dry-run 检查的可通过性。本文结果支持“自然语言可控的参数化轨迹生成与执行前检查链路”这一主张，但不支持强字体风格迁移、真实字体风格学习或实机闭环书写验证等更强结论。

**关键词：** 书法机器人；自然语言约束；参数化轨迹生成；执行层；执行前检查

## 1 引言

书法机器人同时涉及字符表达、轨迹生成、执行语义建模和机器人接口准备。对于实际系统而言，用户往往更倾向于使用自然语言描述书写需求，例如“更宽扁一些”“连笔更自然一些”或“保持较保守的书写风格”。然而，自然语言到可执行轨迹之间通常缺少一个可解释、可约束的中间层，这使得系统要么停留在静态视觉结果，要么直接面对低层轨迹参数，难以形成稳定的上层输入到下层执行的衔接链路。

现有相关方法中，一部分工作主要关注图像骨架提取或字体轮廓恢复，能够提供一定的形态线索，但难以直接支撑自然语言控制与后续机器人接口前准备；另一部分工作依赖示教轨迹、强化学习或复杂风格生成模型，虽然能够在特定条件下改进书写表现，但通常存在数据依赖强、可解释性不足或系统链路不完整等问题。因此，如何构建一条从“语言约束”到“参数化轨迹”再到“执行前检查”的稳定链路，仍然是一个具有工程意义的问题。

针对上述问题，本文不试图直接解决真实书法风格学习，而是提出一条保守但可落地的主线：首先由 planner 解析自然语言约束，通过白名单 style modifier 和参数化 style profile 在 MakeMeAHanzi median 笔画基础上生成中心线轨迹；随后构建 execution layer，对 width、pressure、connector 和 pen-up 等执行语义进行显式表达；最后将结果推进到 workspace、retiming、motion continuity、CoppeliaSim 和 AUBO dry-run precheck，形成完整的执行前检查链路。

本文的主要贡献包括以下三点：

1. 提出一种面向书法机器人的自然语言约束驱动参数化轨迹生成方法，实现从语言输入到结构化轨迹生成的可解释映射。
2. 构建 execution layer，在中心线轨迹之上显式表达 width、pressure、connector 和 pen-up 等执行语义。
3. 形成从二维轨迹到 workspace、retiming、CoppeliaSim 和 AUBO dry-run precheck 的执行前检查链路。

需要说明的是，本文不以强字体风格迁移、真实字体风格学习或实机闭环书写验证为目标。当前系统仍建立在 MakeMeAHanzi median 笔画 backbone 之上，因此风格变化本质上属于参数化控制；同时，文中的 CoppeliaSim 和 AUBO 结果均属于 dry-run 或 precheck 范畴，不等价于真实 IK 或实机书写结果。

## 2 方法

### 2.1 方法总体框架

本文方法的目标是在不让大语言模型直接输出轨迹点、CSV 或机器人命令的前提下，将自然语言书写意图转化为可控的参数化轨迹，并进一步推进到执行前检查阶段。整体流程如图 1 所示：用户首先输入自然语言任务；planner 将其解析为结构化书写约束；style modifier 根据白名单规则对参数化 style profile 进行调整；随后系统在 MakeMeAHanzi median 笔画基础上生成中心线 trajectory；在此基础上再构建 execution layer；最后进入 workspace 映射、resampling、target pose retiming、motion continuity 检查、CoppeliaSim dry-run 和 AUBO dry-run precheck。

这一设计的核心在于，将“语言理解”和“几何生成”明确分层：planner 负责约束解析，轨迹与执行数据则由本地确定性工具生成。这样可以避免语言模型直接产生不可控的底层几何输出，也使每一层的功能边界更加清晰。

### 2.2 自然语言 planner 与 modifier 边界

在本文方法中，planner 的职责被严格限制在结构化计划生成层。给定用户输入的自然语言描述，planner 只输出一组受约束的字段，例如书写风格类别、形态倾向、连笔偏好以及执行相关提示，而不直接输出轨迹点、CSV 行或机器人控制指令。这样做的目的是将自然语言输入限制在一个可解释、可审计的边界之内。

在结构化计划生成后，系统通过本地白名单 style modifier 对参数化 style profile 进行修改。当前主线中，这些 modifier 主要作用于整体形态、连笔规则和执行层参数，而不是从真实字体图像中端到端学习笔画结构。因此，本文中的“风格变化”应理解为参数化可控的形态与执行差异，而非真实书法字体的学习结果。

### 2.3 参数化轨迹生成

本文的中心线轨迹生成以 MakeMeAHanzi median 笔画为基础。该基础提供了相对稳定的笔画数、笔顺和可书写中心线结构，是当前 A-route 能够保持稳定性和可写性的关键原因。系统并不替换这一中心线基础，而是在其上施加参数化 style profile 调整，从而得到具有不同形态倾向的 trajectory。

这种设计带来的优势是稳定和可控：一方面，可以在保持基本笔顺结构不变的前提下形成一定的外形差异；另一方面，也有利于后续 execution、workspace 和 robot precheck 的统一处理。相应地，它的边界也十分明确：由于轨迹基底仍然来自 MakeMeAHanzi median，当前方法在风格表达上的上限受到该基础结构的约束，因此不能把结果解释为强字体风格迁移。

### 2.4 Execution layer

仅有中心线 trajectory 并不足以支撑后续执行层表达与机器人接口准备。为此，本文在中心线轨迹之上构建 execution layer，用于显式记录 width、pressure、pen-down、is-connector 和 segment-type 等执行语义。与仅表示几何路径的中心线不同，execution trajectory 可以进一步反映连接段、抬笔段和笔画宽度变化等信息。

这一层的意义主要体现在两个方面：第一，它使二维轨迹不再只是静态中心线，而成为可表达执行状态的中间表示；第二，它为后续 workspace 映射、retiming 和 dry-run precheck 提供了更贴近执行过程的输入。需要说明的是，execution layer 仍是参数化语义表达层，而非真实物理笔刷模型，因此不能把其中的粗细或压力变化解释为对真实毛笔动力学的完整建模。

### 2.5 执行前检查链路

在 execution trajectory 生成后，系统继续将结果推进到执行前检查链路。该链路依次包括 workspace 映射、resampling、target pose 生成、retiming、motion continuity 检查、CoppeliaSim dry-run 播放以及 AUBO dry-run precheck。

其中，workspace 映射用于将二维执行轨迹约束到预定义书写区域内；retiming 和 motion continuity 检查用于发现并修复时间戳非单调、步长跳变以及保守 acceleration/jerk 超限等问题；CoppeliaSim 部分仅用于标准 pen-tip/sphere scene 下的 dry-run 播放验证；AUBO 相关部分则仅形成 command plan 和 feasibility 风格的前检查结果。换言之，本文方法的最终输出并不是实机控制指令，而是一组经过执行前检查的 dry-run readiness 结果。

## 3 实验与结果分析

### 3.1 实验设置

本文实验围绕 A-route 主线展开，关注的问题不是“是否实现了真实书法风格学习”，而是“自然语言约束能否被转化为可控的参数化轨迹，并进一步进入执行前检查链路”。因此，正文中的主结果只围绕图 1、图 2、图 3、图 4、表 1 和表 2 组织，不将 B-route 相关图像作为主结果。

实验链路按照“自然语言约束 - 参数化轨迹 - execution 表达 - retiming - dry-run precheck”依次展开。对于视觉差异明确的结果，将其作为主图证据；对于视觉变化较弱的结果，只作补充说明或不作为主结论展开。

### 3.2 参数化可控性

本文首先考察自然语言 modifier 的可控性。根据当前已有结果，shape modifier 对整体外形的影响最适合作为正文主证据。图 2 展示了同一字符在不同 shape emphasis 设置下的输出差异。可以观察到，`flatter` 与 `wider` 等设置能够在整体外形上形成一定区别，说明参数化 style profile 对全局形态具有可控作用。

这一结果支持的是“参数化形态可控”，而不是“真实隶书结构已被学习”。当前外形变化仍建立在 MakeMeAHanzi median 中心线基础之上，因此更合适的解释是：系统能够对整体横纵比例和书写外形进行有限、稳定的参数化调节。

相对而言，smoothness 相关结果虽然存在数值变化，但人工看图结论表明其视觉差异不明显，因此不宜作为正文主证据。基于这一原因，本文不将 smoothness 结果作为主要正结论展开。

### 3.3 行楷 connector 消融

为了分析行楷连笔规则的作用，本文对 xingkai connector 设置进行了消融。图 3 给出了 all-adjacent baseline、conservative 以及 balanced 三种设置下的对比结果。人工看图结论表明，相较于过密的 baseline，当前 balanced 方案在连笔数量和自然度之间形成了更可接受的折中，视觉上也比早期过度连笔结果更自然。

这一结果说明，行楷连笔并非越多越好，而应通过规则约束控制在较小范围内。balanced 方案的意义不在于它已经等价于真实行楷书写规律，而在于它展示出一种较为保守且可接受的 connector 生成策略。因此，本文能够支持“规则式 connector 可以被调得更自然”，但不能支持“系统已经学习到真实行楷连笔”。

### 3.4 Execution 表达能力

本文的一个较强结果来自 execution layer。图 4 展示了 execution trajectory 中 width 与 pressure 的可视化效果。人工看图结论表明，该图中的粗细和压力变化明显，可作为当前系统最强的正结果之一。

这一结果表明，在中心线 trajectory 之外，execution layer 能够提供更丰富的执行语义表达。例如，连接段可以表现出更低的压力或更细的宽度，普通笔画段则保持相对稳定的书写状态。与仅包含二维路径的中心线相比，execution trajectory 为后续虚拟书写和机器人接口前检查提供了更贴近执行过程的中间表示。

需要强调的是，本文并不将 execution layer 解释为真实物理笔刷模型。图 4 所展示的是参数化执行语义，而不是经过真实笔刷动力学验证的书写过程。因此，本节最稳妥的结论应是：execution layer 在中间表示层面显著增强了轨迹的可表达性。

### 3.5 Retiming 与 robot precheck 链路

除轨迹本身外，本文还关注轨迹能否进入执行前检查链路。表 1 给出了 retiming 前后的 target pose 对比结果。已有结果表明，原始 target poses 中存在时间连续性问题，而 retiming 后这些问题得到修复，且保守 acceleration/jerk 指标下降，系统对后续 dry-run 检查的推荐状态也随之改善。

在此基础上，表 2 进一步汇总了 robot precheck chain 的结果，包括 workspace、CoppeliaSim、AUBO command adapter 和 IK feasibility dry-run 等环节。该结果的意义在于说明：本文方法并不止于生成一条二维中心线或二维 render，而是能够形成进入机器人接口前的离线准备链路。

不过，本节结论必须保持克制。本文能够支持的只是“执行前检查”和“dry-run readiness”，而不是“真实 AUBO i5 IK 验证”或“实机闭环书写完成”。因此，workspace、CoppeliaSim 与 AUBO 相关结果应统一表述为执行前检查链，而非实机实验结果。

## 本文贡献

1. 提出一种面向书法机器人的自然语言约束驱动参数化轨迹生成方法，实现从语言输入到结构化轨迹生成的可解释映射。
2. 构建包含 width、pressure、connector 和 pen-up 语义的 execution layer，增强中心线轨迹的执行语义表达能力。
3. 形成从轨迹生成到 retiming、motion continuity、CoppeliaSim 以及 AUBO dry-run precheck 的执行前检查链路。

## 需要后续人工补充的信息

1. **最终数字**  
   - 正文中若要写入更具体的数值结论，需要从 `table1_retiming_before_after`、`table2_robot_precheck_summary` 以及 connector 对比结果中提取最终确认值。  
   - 当前初稿只保留了方向性表述。

2. **图表编号**  
   - 当前文中使用的是“图 1、图 2、图 3、图 4、表 1、表 2”的占位编号。  
   - 若后续正文结构有调整，需要统一最终编号与交叉引用。

3. **参考文献**  
   - 当前初稿未插入具体参考文献。  
   - 后续需要补充：书法机器人相关工作、MakeMeAHanzi、CoppeliaSim、AUBO dry-run/precheck 背景以及必要的方法类文献。

4. **数据集与任务描述细节**  
   - 需要补充当前正文实验中实际使用了哪些字、哪些 style case、哪些 xingkai 样本。  
   - 还需要明确 MakeMeAHanzi median 在本文中的使用范围和实验任务集合。

5. **是否加入少量人工视觉评价表**  
   - 当前主结论已经基于人工看图判断收束。  
   - 若后续需要更稳的论文表达，可以考虑加入一张小规模人工视觉评价表，但不应写成大规模用户研究。

6. **补充材料与局限性部分的最终落点**  
   - B-route 相关中文图、font gap 分析和 Phase 1 readonly estimates 需要在最终稿中明确放入 supplementary、limitation 或 future work。  
   - 当前初稿没有展开这些部分，只保留了边界。

