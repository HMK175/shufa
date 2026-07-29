# P1-extended Phase 1 50k 正式基线运行手册

本手册只用于新的 P1-extended Phase 1 **50,000 step 正式基线**，不是既有 10k 先导实验的续训步骤。训练必须从随机初始化开始；不得加载、恢复或以任何方式复用 10k 权重作为正式 50k 的起点。原因是官方 Phase 1 checkpoint 不含优化器、学习率调度器和随机状态，加载权重后重置这些状态不等同于连续训练。

本次运行固定为 Phase 1，且不启用 SCR（配置契约为 `scr: false`）。不要改写、删除或覆盖任何既有 10k 输出。

## 1. 需要同步的文件

除训练数据、固定视觉清单和 `external_repos/FontDiffuser/` 外，本次至少同步以下三项；路径均相对于仓库根目录：

```text
experiments/target_glyph_generation/configs/fontdiffuser_p1_extended_phase1_baseline_50k.yaml
experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py
experiments/target_glyph_generation/src/target_glyph_generation/p1_visual_audit.py
```

不要在同步命令、日志或本手册中记录密码、密钥、主机地址或端口。

## 2. 环境、路径和全新输出目录

以下命令在服务器 shell 中执行。每次 Python 调用都使用 `conda run --no-capture-output -n fontdiffuser python`。固定使用项目根目录 `/root/autodl-tmp/shufa`，并限制 OpenMP/MKL 线程数：

```bash
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

export PROJECT=/root/autodl-tmp/shufa
export DATASET_ROOT="$PROJECT/experiments/target_glyph_generation/data/fontdiffuser_p1_extended"
export VISUAL_MANIFEST="$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_evaluation_20260716/visual_test_manifest.csv"
export TRAIN_OUT="$PROJECT/experiments/target_glyph_generation/outputs/fontdiffuser_p1_extended_phase1_baseline_50k"
export CHECKPOINT_ROOT="$TRAIN_OUT"
export FONTDIFFUSER_ROOT="$PROJECT/external_repos/FontDiffuser"
export DEVICE=cuda:0

export VALIDATE_OUTPUT_ROOT="$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_phase1_baseline_50k_checkpoint_visual_audit_validate_20260717"
export SMOKE_OUTPUT_ROOT="$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_phase1_baseline_50k_checkpoint_visual_audit_smoke_20260717"
export AUDIT_OUTPUT_ROOT="$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_phase1_baseline_50k_checkpoint_visual_audit_20260717"
```

`TRAIN_OUT` 必须在训练开始前不存在；它固定为 50k 路径，不能改指向 10k 目录，也不能位于 10k 输出目录内。三个审计输出根目录也必须彼此不同、与 `CHECKPOINT_ROOT` 分离，并且均为本次新建目录。先做无破坏性存在性检查；若任一目录已经存在，停止并换用新的带日期/批次标识的输出根目录，**不得删除或清空旧目录**：

```bash
for path in "$TRAIN_OUT" "$VALIDATE_OUTPUT_ROOT" "$SMOKE_OUTPUT_ROOT" "$AUDIT_OUTPUT_ROOT"; do
  if [ -e "$path" ]; then
    printf '输出路径已存在，停止运行且不覆盖：%s\n' "$path" >&2
    exit 1
  fi
done
```

不使用自动关机、自动删除或其他破坏性清理命令。

## 3. 正式训练

先进入固定的 screen 会话：

```bash
screen -S p1_phase1_baseline_50k_20260717
```

在会话中进入 FontDiffuser 目录。下列命令是本基线的完整训练命令：batch size 1、梯度累积 8、fp16、学习率 `1e-4`、constant scheduler、训练到 50k，每 10k 保存 checkpoint。不要添加恢复 10k checkpoint 的参数，也不要启用 SCR。

```bash
cd "$FONTDIFFUSER_ROOT"

conda run --no-capture-output -n fontdiffuser python -m accelerate.commands.launch --num_processes 1 train.py \
  --seed 20260716 \
  --experience_name p1_extended_phase1_baseline_50k \
  --data_root "$PROJECT/experiments/target_glyph_generation/data/fontdiffuser_p1_extended" \
  --output_dir "$TRAIN_OUT" \
  --report_to tensorboard \
  --resolution 96 \
  --style_image_size 96 \
  --content_image_size 96 \
  --content_encoder_downsample_size 3 \
  --channel_attn True \
  --content_start_channel 64 \
  --style_start_channel 64 \
  --train_batch_size 1 \
  --gradient_accumulation_steps 8 \
  --mixed_precision fp16 \
  --perceptual_coefficient 0.01 \
  --offset_coefficient 0.5 \
  --max_train_steps 50000 \
  --ckpt_interval 10000 \
  --log_interval 50 \
  --learning_rate 1e-4 \
  --lr_scheduler constant \
  --lr_warmup_steps 0 \
  --drop_prob 0.1
```

以每 update 约 1.73 秒估算，50,000 update 约需 24 小时、约 45 元。这是**预估**，不含排队、数据读取抖动、重启或平台计费策略变化；以实际日志和账单为准。

训练完成后应保留以下五个 checkpoint，供后续固定审计使用：

```text
global_step_10000
global_step_20000
global_step_30000
global_step_40000
global_step_50000
```

## 4. 无卡预检查：五个 checkpoint

训练结束后，先在未分配 GPU 或无需 GPU 的状态进行预检查。该步骤验证完整的固定视觉清单（380 条、19 种风格）、五个 checkpoint 的必要权重和全新的审计输出根目录；不采样图像。成功时 `run_summary.json` 的 `status` 必须为 `validated`。

```bash
conda run --no-capture-output -n fontdiffuser python \
  "$PROJECT/experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py" \
  --dataset-root "$DATASET_ROOT" \
  --visual-manifest "$VISUAL_MANIFEST" \
  --checkpoint-root "$CHECKPOINT_ROOT" \
  --output-root "$VALIDATE_OUTPUT_ROOT" \
  --fontdiffuser-root "$FONTDIFFUSER_ROOT" \
  --device "$DEVICE" \
  --expected-record-count 380 \
  --expected-style-count 19 \
  --checkpoint-steps 10000 20000 30000 40000 50000 \
  --validate-only
```

本手册仍强制要求每次验证使用全新的 `VALIDATE_OUTPUT_ROOT`。脚本本身会拒绝两类不安全路径：`--output-root` 位于 `CHECKPOINT_ROOT` 内（含相同目录），以及任一已选定的 `global_step_<n>` 审计目录已经存在且非空；但若仅验证输出根目录已存在而这些选定目录均为空/不存在，脚本仍可能重写根目录的 `run_summary.json`。因此，人工的“全新输出根目录”规则仍不可省略：它保护此前的根级验证摘要，并使每次验证与后续冒烟/正式审计的产物边界清晰、可追溯。不要清理旧结果；改用新的 `VALIDATE_OUTPUT_ROOT` 后重新执行。

## 5. GPU 冒烟审计：五个 checkpoint、每风格一个样本

确认 GPU 可用后，先运行一次小规模采样。参数仍显式指定相同的五个 checkpoint，只增加 `--limit-per-style 1`。脚本仍会先验证完整 380 条清单和 19 种风格，随后每个 checkpoint 只生成每风格 1 张图。该步骤使用独立且全新的 `SMOKE_OUTPUT_ROOT`，不得与预检查或正式审计复用。

```bash
conda run --no-capture-output -n fontdiffuser python \
  "$PROJECT/experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py" \
  --dataset-root "$DATASET_ROOT" \
  --visual-manifest "$VISUAL_MANIFEST" \
  --checkpoint-root "$CHECKPOINT_ROOT" \
  --output-root "$SMOKE_OUTPUT_ROOT" \
  --fontdiffuser-root "$FONTDIFFUSER_ROOT" \
  --device "$DEVICE" \
  --expected-record-count 380 \
  --expected-style-count 19 \
  --checkpoint-steps 10000 20000 30000 40000 50000 \
  --limit-per-style 1
```

## 6. 正式五 checkpoint 视觉审计

冒烟结果确认可用后，运行正式审计。**不要**在本命令中加入 `--limit-per-style`；正式审计必须覆盖固定清单中每种风格的 20 个样本。使用第三个全新的输出根目录 `AUDIT_OUTPUT_ROOT`：

```bash
conda run --no-capture-output -n fontdiffuser python \
  "$PROJECT/experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py" \
  --dataset-root "$DATASET_ROOT" \
  --visual-manifest "$VISUAL_MANIFEST" \
  --checkpoint-root "$CHECKPOINT_ROOT" \
  --output-root "$AUDIT_OUTPUT_ROOT" \
  --fontdiffuser-root "$FONTDIFFUSER_ROOT" \
  --device "$DEVICE" \
  --expected-record-count 380 \
  --expected-style-count 19 \
  --checkpoint-steps 10000 20000 30000 40000 50000
```

正式审计预期每个 checkpoint 生成 380 张图和 19 页审计图；五个 checkpoint 合计为 1,900 张生成图和 95 页审计图。输出根目录不得位于 `CHECKPOINT_ROOT` 内，且不得覆盖任何已有审计输出。

## 7. 人工目检与 40k/50k 决策门槛

必须由人工逐页查看五个 checkpoint 的 19 个风格审计页，并以同一固定清单比较 `C content / R reference / T target / G generated` 四格。至少记录以下判断：

- 字符内容是否可辨认，部件、笔画、相对布局是否与内容/目标一致；是否缺笔、多笔、错位或截断。
- 风格是否从参考图迁移，而不是仅复制内容或目标；观察笔画形态、粗细、倾斜、留白和整体布局。
- 是否出现全黑、全白、纯噪声、塌缩、明显伪影、边缘裁切或风格间系统性失败。
- 同一风格的 20 个固定样本是否稳定；不得挑选单张“好看”样例替代整页判断。
- 10k、20k、30k、40k、50k 的结构可辨识度、风格一致性和伪影是否呈合理趋势，而非只依赖数值指标。

在五个阶段的图像均经人工视觉确认前，**禁止**启动 9,580 条全量生成或任何对应的 L1、SSIM、LPIPS、FID 等指标计算。数值结果只能作为补充证据，不能取代目检。

决策规则如下：若 40k 相比更早 checkpoint 仍有清晰且一致的视觉改进，可在人工确认后讨论是否延长训练；若 40k 至 50k 已进入平台期、改进很小或无一致改进，则固定 50k 作为正式基线，并据此再决定是否进入全量评估。任何一项决定都应引用完整审计页，而非个别样例。

## 8. 完成条件与边界

完成本轮运行至少应具备：50k 从随机初始化完成、五个 checkpoint 完整、无卡预检查通过、GPU 冒烟完成、正式 1,900 图/95 页审计完成，以及人工视觉结论与 40k/50k 决策已记录。整个流程不记录凭据，不使用自动关机，不使用删除、覆盖或其他破坏性命令，也不在文档中写入主机地址或端口。
