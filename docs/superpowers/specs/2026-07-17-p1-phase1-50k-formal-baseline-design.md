# P1-extended Phase 1 50k 正式基线设计

## 目标

在不启用 SCR / Phase 2 的前提下，从随机初始化完整训练一个 50,000 step 的 FontDiffuser Phase 1 正式基线，用于替代仅约 1 个数据遍历的 10,000 step 先导实验。训练过程保留 10k、20k、30k、40k、50k 五个 checkpoint，并以固定的 380 条视觉清单审计其收敛趋势。

本方案的论文任务边界仍为：已见风格下的未见字符生成。ChineseStyle 的许可状态继续记为 unverified，不改变其既有的用户确认实验范围。

## 依据与选择

P1-extended 训练集有约 76,523 张目标图；当前 batch=1、gradient accumulation=8，因此：

- 10,000 update step 约对应 1.05 次完整数据遍历；
- 30,000 update step 约对应 3.14 次完整数据遍历；
- 50,000 update step 约对应 5.23 次完整数据遍历。

已有固定样例显示 5k 到 10k 的字形仍在明显改善，因此 30k 不作为最终停止点。选择 50k 是在原始 FontDiffuser 长训练尺度与本项目数据规模、GPU 成本之间的可复核折中；它不是对原论文 440k 默认 step 数的机械复制。

## 训练契约

创建独立配置和独立服务器输出目录：

~~~~text
configs/fontdiffuser_p1_extended_phase1_baseline_50k.yaml
outputs/fontdiffuser_p1_extended_phase1_baseline_50k/
~~~~

训练参数与已完成的 10k 先导基线保持一致，唯有以下项变化：

~~~~text
run_name: p1_extended_phase1_baseline_50k
run_tier: formal_baseline
max_train_steps: 50000
checkpoint_interval: 10000
output_dir: .../fontdiffuser_p1_extended_phase1_baseline_50k
~~~~

必须从随机初始化开始，不从 10k 权重加载。原因是官方 Phase 1 checkpoint 只保存模型权重，没有优化器、学习率调度器和随机状态，加载后重置优化器不等同于连续训练。

服务器运行固定使用 /root/autodl-tmp/shufa、conda run --no-capture-output -n fontdiffuser python、OMP_NUM_THREADS=1 和 MKL_NUM_THREADS=1。运行于 screen 中，不设置自动关机；输出目录必须是全新目录，不能指向或嵌套在 10k 训练目录。

## 固定审计扩展

现有审计脚本的默认 checkpoint 仍保持 1000、5000、10000，从而保证已完成 10k 先导审计可复现。

新增可选参数：

~~~~text
--checkpoint-steps 10000 20000 30000 40000 50000
~~~~

传入该参数时，脚本只校验、采样并汇总给定的五个 checkpoint；其余数据保护规则不变：

- 完整验证固定 380 条清单、19 种风格和每个 checkpoint 的四个权重文件；
- 每个 checkpoint 只加载一次 pipeline；
- 非空 checkpoint 输出拒绝重跑，避免结果混合；
- 每个 checkpoint 成功后才写生成映射和审计页；
- 任何安全输出目录中的失败均写入 run_summary.json；
- 仍采用每个 style 20 条样例的 C/R/T/G 四联审计页和 PNG 元数据追溯。

50k 审计输出使用新的根目录，例如：

~~~~text
outputs/p1_visual_audit_50k_formal_<timestamp>/
  global_step_10000/
  global_step_20000/
  global_step_30000/
  global_step_40000/
  global_step_50000/
~~~~

## 验收和决策门槛

训练验收：

1. 5 个 checkpoint 各含 unet.pth、style_encoder.pth、content_encoder.pth、total_model.pth。
2. 训练日志覆盖到 step 50,000，且无 CUDA OOM 或非零退出。
3. 不覆盖已有 10k 先导训练或其正式审计目录。

视觉审计验收：

1. 每个 50k checkpoint 生成 380 张图、380 条生成映射、19 页审计图。
2. 人工比较同一风格在 10k、20k、30k、40k、50k 的字符可辨认性、风格迁移、笔画粘连和纹理伪影。
3. 若 50k 仍持续显著改善，则再讨论延长训练；若 40k 与 50k 已基本持平，则固定 50k 为正式基线。
4. 在人工确认图像可用前，不生成 9,580 条完整测试集，也不报告 L1、SSIM、LPIPS 或 FID。

## 验证

本地测试需新增或修改审计 CLI 的测试，覆盖：

- 默认仍使用 1000/5000/10000；
- 自定义 10000/20000/30000/40000/50000 可验证对应权重并写入摘要；
- 输出目录安全检查对自定义 checkpoint 列表同样生效；
- 现有无卡 validate-only、模拟 runtime seam 和 10k 视觉审计测试继续通过。

远程先进行无卡预检查，再进行每风格 1 条的 GPU 冒烟，最后进入 50k 正式 380×5 审计；不直接跳到完整 9,580 样本指标。

