# FontDiffuser P1-extended Phase 1 先导基线运行清单

## 目的与边界

本清单用于在 AutoDL 的高显存 GPU 上运行 P1-extended 的 10,000 step Phase 1 先导基线。它验证训练曲线、固定测试输出和指标趋势；不把 10,000 step 的结果作为论文最终结论。

- 任务：已见风格下的未见字符生成。
- 数据：P1-extended，包含 19 种风格。
- 不启用 SCR / Phase 2。
- ChineseStyle 的使用依据是用户确认的论文实验决定；其源许可状态仍为 `unverified`，不得在论文中表述为“已取得许可”。

## 需要传到服务器的内容

只传下列内容，不传原始 OCR 数据集和本地虚拟环境：

```text
external_repos/FontDiffuser/
experiments/target_glyph_generation/src/
experiments/target_glyph_generation/configs/fontdiffuser_p1_extended_phase1_baseline_10k.yaml
experiments/target_glyph_generation/scripts/
experiments/target_glyph_generation/data/fontdiffuser_p1_extended/
experiments/target_glyph_generation/outputs/p1_extended_evaluation_20260716/
```

其中 `fontdiffuser_p1_extended/` 是训练所需的 102,993 张已物化图像；原始书法家、ChineseStyle 和字体源文件均不需要上传。

## 服务器前置检查

在服务器的项目根目录执行：

```bash
nvidia-smi
python --version
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

推荐选择 24GB 及以上显存。若服务器 CUDA / PyTorch 环境与本地的 Torch 1.13.1 + CUDA 11.7 不兼容，先停在环境适配阶段，不启动训练；环境检查结果交给 Codex 后再确定兼容安装命令。

## 先导训练命令

以下命令在 `external_repos/FontDiffuser/` 下运行。`$PROJECT` 改为服务器上的项目根目录，`$PY` 改为服务器训练环境中的 Python。

```bash
PROJECT=/root/shufa
PY=$PROJECT/.venvs/fontdiffuser/bin/python

cd $PROJECT/external_repos/FontDiffuser
$PY -m accelerate.commands.launch --num_processes 1 train.py \
  --seed 20260716 \
  --experience_name p1_extended_phase1_baseline_10k \
  --data_root $PROJECT/experiments/target_glyph_generation/data/fontdiffuser_p1_extended \
  --output_dir $PROJECT/experiments/target_glyph_generation/outputs/fontdiffuser_p1_extended_phase1_baseline_10k \
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
  --max_train_steps 10000 \
  --ckpt_interval 1000 \
  --log_interval 50 \
  --learning_rate 1e-4 \
  --lr_scheduler constant \
  --lr_warmup_steps 0 \
  --drop_prob 0.1
```

## 固定评估清单

清单目录：

```text
experiments/target_glyph_generation/outputs/p1_extended_evaluation_20260716/
```

- `paired_test_manifest.csv`：9,580 个测试目标，后续逐项生成后可计算 L1、SSIM、LPIPS；也可按全部生成图和真实目标图计算 FID。
- `visual_test_manifest.csv`：每种风格固定 20 个样本，共 380 个。应在 step 1,000、5,000、10,000 生成同一批图，并进行人工目检。

在采样与指标脚本完成前，不应自行从测试集中临时挑选“好看”的样例用于论文配图。

## 先导运行验收

1. 训练可到达 step 1,000，并保存 `global_step_1000/`。
2. TensorBoard 日志、训练配置和 checkpoint 均写入服务器项目目录。
3. 用固定 380 样本生成图，人工检查非全黑、非全白、非纯噪声，并比较各 checkpoint 的结构与风格趋势。
4. 若 10,000 step 仍完全不能形成可辨认结构，再排查训练配置、数据比例和数据归一化；不要直接扩大到更长训练。

## P1 Phase 1 检查点视觉审计

本节只审计 P1-extended Phase 1 的固定 checkpoint `global_step_1000`、`global_step_5000` 和
`global_step_10000`。审计数据必须来自固定的 `visual_test_manifest.csv`，不得临时换样本或按
结果挑选样本。以下命令均在服务器上执行；不记录密码、密钥或其他凭据。

本节是独立的 AutoDL 审计流程，**仅**使用 `PROJECT=/root/autodl-tmp/shufa`，且每一条 Python
调用**仅**使用 `conda run --no-capture-output -n fontdiffuser python`。上文可能保留的 P0、本地或历史
训练记录（例如 `PROJECT=/root/shufa`、`$PY` 或 `.venvs/.../python`）不适用于本节的 P1 AutoDL
检查点审计；不要从这些旧块复制项目根目录或解释器。

### 1. 本地到服务器同步

除已有的配置、数据清单和训练 checkpoint 外，至少同步本次审计新增的两个文件：

```text
src/target_glyph_generation/p1_visual_audit.py
scripts/run_p1_checkpoint_visual_audit.py
```

它们位于仓库的 `experiments/target_glyph_generation/` 下。同步时不需要记录或写入密码，也不需要在文档或脚本中硬编码主机名、端口或凭据。

### 2. 统一路径、输出根目录与线程设置

在进入 `FontDiffuser` 目录前，设置单线程 OpenMP/MKL，避免小批量逐图采样造成过度线程竞争。项目根目录固定为
`/root/autodl-tmp/shufa`。预检查、GPU 冒烟和正式运行必须分别使用三个全新的输出根目录：

```bash
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

export PROJECT=/root/autodl-tmp/shufa
export DATASET_ROOT=$PROJECT/experiments/target_glyph_generation/data/fontdiffuser_p1_extended
export VISUAL_MANIFEST=$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_evaluation_20260716/visual_test_manifest.csv
export CHECKPOINT_ROOT=$PROJECT/experiments/target_glyph_generation/outputs/fontdiffuser_p1_extended_phase1_baseline_10k
export FONTDIFFUSER_ROOT=$PROJECT/external_repos/FontDiffuser
export DEVICE=cuda:0
export VALIDATE_OUTPUT_ROOT=$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_checkpoint_visual_audit_validate_20260717
export SMOKE_OUTPUT_ROOT=$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_checkpoint_visual_audit_smoke_20260717
export AUDIT_OUTPUT_ROOT=$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_checkpoint_visual_audit_20260717

cd "$FONTDIFFUSER_ROOT"
```

### 3. 无显卡预检查

无 GPU 或尚未分配显卡时，先以全新的 `VALIDATE_OUTPUT_ROOT` 执行 `--validate-only`：

```bash
conda run --no-capture-output -n fontdiffuser python \
  $PROJECT/experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py \
  --dataset-root "$DATASET_ROOT" \
  --visual-manifest "$VISUAL_MANIFEST" \
  --checkpoint-root "$CHECKPOINT_ROOT" \
  --output-root "$VALIDATE_OUTPUT_ROOT" \
  --fontdiffuser-root "$FONTDIFFUSER_ROOT" \
  --device "$DEVICE" \
  --validate-only
```

该步骤不采样，但会验证固定清单的全部 380 个输入、19 种风格，以及三个 checkpoint 的全部必需权重。成功后根目录
`run_summary.json` 的 `status` 必须为 `validated`。若该输出根目录中已经存在任一 checkpoint 的审计输出，必须改用新的
输出根目录再运行；不要尝试覆盖或删除旧结果。

### 4. 启动 GPU 后的冒烟检查

仅当无显卡预检查已得到 `status=validated` 后，启动/分配 GPU 并确认设备可用，再以单独且全新的
`SMOKE_OUTPUT_ROOT` 使用 `--limit-per-style 1` 检查 GPU 推理和审计页面的整个工作流：

```bash
nvidia-smi
```

```bash
conda run --no-capture-output -n fontdiffuser python \
  $PROJECT/experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py \
  --dataset-root "$DATASET_ROOT" \
  --visual-manifest "$VISUAL_MANIFEST" \
  --checkpoint-root "$CHECKPOINT_ROOT" \
  --output-root "$SMOKE_OUTPUT_ROOT" \
  --fontdiffuser-root "$FONTDIFFUSER_ROOT" \
  --device "$DEVICE" \
  --limit-per-style 1
```

即使只采样每种风格 1 个样本，脚本仍先验证完整的 380 条清单、19 种风格和三个 checkpoint。随后每个 checkpoint
会生成 19 张图，三个 checkpoint 合计 57 张；每个 checkpoint 还会为每种风格生成一页审计图，即每个 checkpoint
19 页。该步骤仅证明工作流可用，不是论文证据，也不能替代完整视觉审计。冒烟检查的 `run_summary.json` 必须为
`status=complete`；只有该步骤通过后，才能开始正式运行。

### 5. 仅在前两项成功后执行：正式审计运行

仅当预检查为 `status=validated` 且 GPU 冒烟检查为 `status=complete` 时，才可使用第三个全新的
`AUDIT_OUTPUT_ROOT` 执行正式运行。正式运行不加 `--limit-per-style`，并在交互式 `screen` 会话中执行，便于断线后继续查看日志：

```bash
screen -S p1_phase1_visual_audit_20260717
```

进入该会话后，确认已保留上述导出的变量，并在 `FontDiffuser` 目录运行以下正式命令：

```bash
cd "$FONTDIFFUSER_ROOT"

conda run --no-capture-output -n fontdiffuser python \
  $PROJECT/experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py \
  --dataset-root "$DATASET_ROOT" \
  --visual-manifest "$VISUAL_MANIFEST" \
  --checkpoint-root "$CHECKPOINT_ROOT" \
  --output-root "$AUDIT_OUTPUT_ROOT" \
  --fontdiffuser-root "$FONTDIFFUSER_ROOT" \
  --device "$DEVICE"
```

正式审计对每个 checkpoint 生成 380 张图、19 页审计图，三个 checkpoint 合计生成 1,140 张图。不要在命令中加入自动关机、自动删除或其他破坏性操作。

### 输出保护与完成条件

- `--output-root` 绝不能等于训练 `CHECKPOINT_ROOT`，也不能位于其内部；脚本会拒绝这种写入，防止训练 checkpoint 被污染。
- 脚本会拒绝非空的 checkpoint 审计输出目录。任何中断、失败或已完成的 checkpoint 审计输出都不得覆盖；重跑时必须指定新的输出根目录，且不要使用破坏性删除命令清理旧目录。
- 正式运行完成时，根目录 `run_summary.json` 的 `status` 必须是 `complete`。三个 `global_step_1000`、`global_step_5000`、`global_step_10000` 目录各自必须同时具备：
  - `generated_manifest.csv` 恰有 380 条数据行（不含表头）；
  - `generated/` 恰有 380 个 PNG；
  - `audit_pages/` 恰有 19 个 PNG。

### 强制人工视觉审计门槛

逐页检查每个 checkpoint、每种风格的字形结构是否可辨认，风格迁移是否合理，并明确排查全黑、全白和纯噪声输出。数值
计数、清单校验或 `run_summary.json` 只能证明流程完整，不能替代人工看图确认。

在人工视觉审计明确确认之前，不得生成 9,580 个完整测试样本，也不得报告 L1、SSIM、LPIPS 或 FID；这些指标和大规模
生成必须在人工确认后再单独启动。
