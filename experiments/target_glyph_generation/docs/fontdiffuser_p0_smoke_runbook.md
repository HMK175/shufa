# FontDiffuser P0 冒烟训练运行清单

## 当前已完成

- 官方仓库：`external_repos/FontDiffuser/`
- 固定提交：`7b28ce9c3b357f4fb23296622f458cf169803539`
- 官方数据目录已适配完成：
  `experiments/target_glyph_generation/data/fontdiffuser_p0_fontdiffuser_adapter/`
  - 8 个训练风格
  - 640 个训练字
  - 5,120 张目标图
- 本机冒烟子集已适配完成：
  `experiments/target_glyph_generation/data/fontdiffuser_p0_smoke_adapter/`
  - 风格：`lishu`、`lgq`
  - 64 个训练字、128 张目标图
- 官方 `FontDataset` 已识别 Windows 路径和目录结构；当前只被旧版 Torch 与 NumPy 2 的兼容性阻断。

## 恢复前置条件

1. C 盘至少保留 20GB 空闲空间，推荐 30GB 以上。
2. 模型环境、数据、缓存、临时目录和输出全部指向 D 盘工作区。
3. 不重新安装已在 D 盘环境中的 Torch 1.13.1 / CUDA 11.7。

```powershell
$project = 'D:\sw data\vscode\shufa\.worktrees\target-glyph-dataset'
$py = "$project\.venvs\fontdiffuser\Scripts\python.exe"
$cacheRoot = "$project\experiments\target_glyph_generation\data\fontdiffuser_runtime_cache"
New-Item -ItemType Directory -Force -Path $cacheRoot, "$cacheRoot\tmp", "$cacheRoot\pip", "$cacheRoot\torch" | Out-Null
$env:TEMP = "$cacheRoot\tmp"
$env:TMP = "$cacheRoot\tmp"
$env:PIP_CACHE_DIR = "$cacheRoot\pip"
$env:TORCH_HOME = "$cacheRoot\torch"
$constraints = "$project\experiments\target_glyph_generation\configs\fontdiffuser_legacy_constraints.txt"
```

## 补齐环境与修复 NumPy 兼容性

在上述环境变量仍生效的 PowerShell 中执行：

```powershell
& $py -m pip install --disable-pip-version-check --no-input --progress-bar off --force-reinstall "numpy==1.26.4"
& $py -m pip install --disable-pip-version-check --no-input --progress-bar off --force-reinstall --no-deps `
  torch==1.13.1+cu117 torchvision==0.14.1+cu117 torchaudio==0.13.1 `
  --extra-index-url https://download.pytorch.org/whl/cu117
& $py -m pip install --disable-pip-version-check --no-input --progress-bar off `
  -r "$project\external_repos\FontDiffuser\requirements.txt" --constraint $constraints
& $py -m pip install --disable-pip-version-check --no-input --progress-bar off tensorboard
& $py -m pip check
```

注意：该仓库发布于 2023 年，不能直接在无约束条件下执行原始 `requirements.txt`。约束文件会固定 `kornia==0.6.12` 和 `huggingface-hub==0.25.2`，避免 pip 将官方 CUDA 版 Torch 升级为不兼容的新版 CPU 包，或使 `diffusers==0.22.0` 因缺失 `cached_download` 接口而无法导入。

## 官方数据加载检查

```powershell
$env:PYTHONPATH = "$project\external_repos\FontDiffuser"
& $py -c "from types import SimpleNamespace; from dataset.font_dataset import FontDataset; args=SimpleNamespace(data_root=r'$project\experiments\target_glyph_generation\data\fontdiffuser_p0_smoke_adapter', resolution=96); ds=FontDataset(args, 'train', transforms=None, scr=False); sample=ds[0]; print({'dataset_length': len(ds), 'style_count': len(ds.style_to_images), 'resized_target_shape': tuple(sample['nonorm_target_image'].shape)})"
```

预期：输出 `dataset_length: 128`、`style_count: 2`，且 `resized_target_shape` 为 `(3, 96, 96)`。

## 4060 Ti 8GB 冒烟训练

此命令只运行官方 Phase 1；不加载 SCR、不执行 Phase 2、不修改网络结构。

```powershell
Set-Location "$project\external_repos\FontDiffuser"
& $py -m accelerate.commands.launch --num_processes 1 train.py `
  --seed 20260715 `
  --experience_name p0_smoke_lishu_lgq `
  --data_root "$project\experiments\target_glyph_generation\data\fontdiffuser_p0_smoke_adapter" `
  --output_dir "$project\experiments\target_glyph_generation\outputs\fontdiffuser_p0_smoke" `
  --report_to tensorboard `
  --resolution 96 `
  --style_image_size 96 `
  --content_image_size 96 `
  --content_encoder_downsample_size 3 `
  --channel_attn True `
  --content_start_channel 64 `
  --style_start_channel 64 `
  --train_batch_size 1 `
  --gradient_accumulation_steps 8 `
  --mixed_precision fp16 `
  --perceptual_coefficient 0.01 `
  --offset_coefficient 0.5 `
  --max_train_steps 100 `
  --ckpt_interval 100 `
  --log_interval 10 `
  --learning_rate 1e-4 `
  --lr_scheduler constant `
  --lr_warmup_steps 0 `
  --drop_prob 0.1
```

## 冒烟通过标准

- CUDA 进程能够启动且不出现 out-of-memory。
- 前 10 个 step 的 loss、学习率和 TensorBoard 日志可写入 D 盘输出目录。
- 训练运行到 100 step，至少产生一次 checkpoint / 验证输出。
- 人工查看输出图：字形不是全白、全黑或无结构噪声。

若在 `batch=1`、`fp16` 下仍显存溢出，停止本机训练，不缩小官方网络；改用 24GB 以上 Linux GPU 进行后续训练。

## 数据范围说明

本冒烟子集使用 P0，目的是验证代码、数据读取和训练流程。P0 含有授权状态未核验的 ChineseStyle 数据，不能用于论文最终实验或正式投稿结果。
