# P1 Phase 1 固定样例检查点采样与审计设计

## 目标

为已完成的 P1-extended Phase 1 基线生成可复核的视觉结果。对固定的 380 条 `visual_test_manifest.csv` 样例，分别加载 `global_step_1000`、`global_step_5000` 与 `global_step_10000`，输出生成图及便于人工比较的审计图。

本轮不生成 9,580 条完整测试集，不计算 L1、SSIM、LPIPS 或 FID，也不修改模型、训练配置或数据集。

## 输入与边界

- 数据根目录：`experiments/target_glyph_generation/data/fontdiffuser_p1_extended/`。
- 固定样例清单：`outputs/p1_extended_evaluation_20260716/visual_test_manifest.csv`，必须恰好包含 380 条记录和 19 种风格。
- 检查点：Phase 1 输出目录中的 `global_step_1000`、`global_step_5000`、`global_step_10000`；每个目录必须包含 `unet.pth`、`style_encoder.pth`、`content_encoder.pth` 与 `total_model.pth`。
- 推理参数与正式基线保持一致：96×96 输入、DPM-Solver++、classifier-free guidance、guidance scale 7.5、20 个推理步、固定随机种子 20260716。

## 方案选择

1. 手动调用官方 `sample.py`：实现快，但无法保证 380 条固定样例、文件命名和对照关系的完整性，不采用。
2. 读取固定清单的批量采样器：按检查点复用一次模型加载，逐条生成并写入映射记录；能够保证可复核性，采用。
3. 直接生成完整 9,580 条并计算指标：GPU 时间更长，且在尚未人工确认图像可辨识前缺少必要性，暂不采用。

## 组件与数据流

### 批量采样器

新增一个位于 `experiments/target_glyph_generation/scripts/` 的命令行脚本。

脚本接收数据根目录、视觉清单、三个检查点路径、输出根目录和 GPU 设备参数。对每个检查点：

1. 验证权重和全部输入图像存在；
2. 使用 FontDiffuser 官方构建函数加载一次模型与 DPM pipeline；
3. 按 `visual_test_manifest.csv` 的稳定顺序读取内容图和风格参考图；
4. 以固定种子逐条生成图片，保存为不依赖中文文件系统排序的 `evaluation_id` 文件名；
5. 写出该检查点的 `generated_manifest.csv`，包含 evaluation ID、风格、字符、内容图、参考图、真实目标图和生成图相对路径；
6. 释放模型与 CUDA 缓存后再处理下一检查点。

### 审计图生成器

采样器完成一个检查点后，使用其 `generated_manifest.csv` 生成按风格分组的审计页。每一条样例固定显示四个面板：内容字图、风格参考图、真实目标图、生成图，并在页脚保留风格 ID、字符和 evaluation ID。

审计图只用于人工检查字形结构、风格迁移、黑白反相、全黑/全白和纯噪声等可见问题；不从中挑选样例替代固定测试协议。

## 输出布局

```text
outputs/p1_extended_checkpoint_visual_audit_20260717/
  run_summary.json
  global_step_1000/
    generated/
    generated_manifest.csv
    audit_pages/
  global_step_5000/
    generated/
    generated_manifest.csv
    audit_pages/
  global_step_10000/
    generated/
    generated_manifest.csv
    audit_pages/
```

每个检查点应有 380 张生成图、380 条映射记录，并覆盖 19 种风格。输出根目录不可指向训练 checkpoint 目录，避免覆盖训练产物。

## 失败处理

- 清单记录数、风格数、图像路径或权重文件不符合预期时，在开始 GPU 推理前失败。
- 任一条采样失败时，写入失败 evaluation ID 并以非零状态退出；不会将不完整结果标记为完成。
- 每个检查点完成后才生成对应审计页；不对缺少生成图的样例制作伪完整审计图。

## 验证

- 单元测试：使用最小伪清单验证输入校验、稳定输出命名、映射记录、按检查点隔离输出和缺失文件错误。
- GPU 冒烟：使用正式数据的每种风格 1 条样例、3 个检查点，验证模型加载与图片输出；该小规模结果不作为论文材料。
- 正式运行：确认每个检查点生成 380 张图、19 种风格和对应审计页后，进行人工目检。

## 运行顺序

1. 在本机实现并测试脚本；
2. 在无卡模式上传新增的小脚本；
3. GPU 开机后执行 3 检查点的小规模冒烟；
4. 冒烟通过后执行固定 380×3 的正式视觉采样；
5. 人工目检后，另行决定是否开展完整测试集生成和指标计算。
