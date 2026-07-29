# P1 Phase 1 50k 正式基线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 新增从零训练的 P1-extended Phase 1 50,000 step 正式基线配置，并让固定视觉审计脚本可安全审计 10k、20k、30k、40k、50k 五个 checkpoint。

**Architecture:** 保持官方 FontDiffuser Phase 1 训练代码不变，只新增独立 50k 配置与独立服务器运行手册。将审计脚本中硬编码的 checkpoint 列表提升为显式、受验证的可选 CLI 参数；未传参数时仍精确使用既有 1000/5000/10000 默认值，确保已完成 10k 实验可复现。

**Tech Stack:** Python 3.12 本地测试环境、Python 3.10 AutoDL 运行环境、argparse、pytest、PyYAML、官方 FontDiffuser、Pillow。

---

## 文件边界

- Create: experiments/target_glyph_generation/configs/fontdiffuser_p1_extended_phase1_baseline_50k.yaml
  - 50k 正式基线的可追溯训练契约；不由官方 train.py 自动读取。
- Modify: experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py
  - 添加受验证的 checkpoint 步数参数；默认行为不变。
- Modify: experiments/target_glyph_generation/tests/test_p1_visual_audit.py
  - 覆盖默认兼容、自定义五 checkpoint 预检查、输出目录保护和 fake-runtime 推理循环。
- Modify: experiments/target_glyph_generation/tests/test_p1_evaluation.py
  - 读取并固定 50k 配置的训练与审计契约。
- Create: experiments/target_glyph_generation/docs/fontdiffuser_p1_baseline_50k_runbook.md
  - 中文 AutoDL 运行清单，含无卡预检查、GPU 冒烟、screen 正式训练、五 checkpoint 固定审计和人工目检门槛。

不修改 external_repos/FontDiffuser/train.py；不加载已有 10k 权重；不新增完整 9,580 样本指标计算。

### Task 1: 固定 50k 基线配置

**Files:**
- Modify: experiments/target_glyph_generation/tests/test_p1_evaluation.py
- Create: experiments/target_glyph_generation/configs/fontdiffuser_p1_extended_phase1_baseline_50k.yaml

- [ ] **Step 1: 写出 50k 配置的失败测试。**

在 test_p1_evaluation.py 追加下列测试。它只读取 YAML，不依赖 GPU：

    def test_p1_50k_formal_baseline_config_preserves_phase1_contract():
        config_path = PROJECT_DIR / "configs" / "fontdiffuser_p1_extended_phase1_baseline_50k.yaml"

        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

        assert payload["run_name"] == "p1_extended_phase1_baseline_50k"
        assert payload["run_tier"] == "formal_baseline"
        assert payload["dataset_scope"] == "p1_extended"
        assert payload["phase"] == 1
        assert payload["scr"] is False
        assert payload["training"]["seed"] == 20260716
        assert payload["training"]["batch_size"] == 1
        assert payload["training"]["gradient_accumulation_steps"] == 8
        assert payload["training"]["max_train_steps"] == 50000
        assert payload["training"]["checkpoint_interval"] == 10000
        assert payload["runtime"]["output_dir"].endswith("fontdiffuser_p1_extended_phase1_baseline_50k")
        assert payload["evaluation"]["sample_checkpoint_steps"] == [10000, 20000, 30000, 40000, 50000]
        assert payload["paper_boundary"]["task"] == "已见风格下的未见字符生成"
        assert payload["paper_boundary"]["chinese_style_license_status"] == "unverified"

- [ ] **Step 2: 运行测试，确认配置文件缺失。**

Run:

    Set-Location 'D:\sw data\vscode\shufa\.worktrees\target-glyph-dataset'
    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_evaluation.py::test_p1_50k_formal_baseline_config_preserves_phase1_contract -q

Expected: FAIL with FileNotFoundError for fontdiffuser_p1_extended_phase1_baseline_50k.yaml.

- [ ] **Step 3: 新建最小 50k 配置。**

创建 YAML，保留 10k 配置中一致的数据、模型和训练超参数，明确写入以下完整内容：

    # P1-extended Phase 1 正式基线：从随机初始化训练 50,000 step，不启用 SCR。
    run_name: p1_extended_phase1_baseline_50k
    run_tier: formal_baseline
    dataset_scope: p1_extended
    phase: 1
    scr: false

    data_root: ../data/fontdiffuser_p1_extended
    model:
      resolution: 96
      style_image_size: 96
      content_image_size: 96
      content_encoder_downsample_size: 3
      channel_attn: true
      content_start_channel: 64
      style_start_channel: 64

    training:
      seed: 20260716
      batch_size: 1
      gradient_accumulation_steps: 8
      mixed_precision: fp16
      learning_rate: 0.0001
      lr_scheduler: constant
      lr_warmup_steps: 0
      perceptual_coefficient: 0.01
      offset_coefficient: 0.5
      drop_prob: 0.1
      max_train_steps: 50000
      checkpoint_interval: 10000
      log_interval: 50

    evaluation:
      paired_test_manifest: ../outputs/p1_extended_evaluation_20260716/paired_test_manifest.csv
      visual_test_manifest: ../outputs/p1_extended_evaluation_20260716/visual_test_manifest.csv
      sample_checkpoint_steps: [10000, 20000, 30000, 40000, 50000]
      paired_metrics: [l1, ssim, lpips]
      distribution_metric: fid

    runtime:
      recommended_gpu_memory_gib: 24
      output_dir: ../outputs/fontdiffuser_p1_extended_phase1_baseline_50k
      report_to: tensorboard

    paper_boundary:
      task: 已见风格下的未见字符生成
      chinese_style_license_status: unverified
      chinese_style_paper_use_basis: user_confirmed_unverified_source
      training_initialization: random
      checkpoint_resume: prohibited_for_formal_baseline

- [ ] **Step 4: 运行配置测试。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_evaluation.py -q

Expected: all tests in test_p1_evaluation.py pass.

### Task 2: 支持自定义 checkpoint 审计列表

**Files:**
- Modify: experiments/target_glyph_generation/tests/test_p1_visual_audit.py
- Modify: experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py

- [ ] **Step 1: 先添加五 checkpoint 的无卡失败测试。**

在 test_p1_visual_audit.py 先提取现有 CLI 重复准备逻辑为下列测试辅助函数，再增加五 checkpoint 测试。两个辅助函数必须保留现有每一项 CLI 参数和真实临时图像创建行为。

    SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "run_p1_checkpoint_visual_audit.py"


    def _create_cli_fixture(
        tmp_path: Path, checkpoint_steps: tuple[int, ...] = (1000, 5000, 10000)
    ) -> tuple[Path, Path, Path]:
        dataset_root = tmp_path / "dataset"
        rows = [_record("style_a", "char_a", 1), _record("style_b", "char_b", 2)]
        for index, row in enumerate(rows, start=1):
            _image(dataset_root / row["content_path"], (index, 0, 0))
            _image(dataset_root / row["reference_path"], (0, index, 0))
            _image(dataset_root / row["target_path"], (0, 0, index))
        manifest = tmp_path / "visual_test_manifest.csv"
        _write_manifest(manifest, rows)
        checkpoint_root = tmp_path / "checkpoints"
        for checkpoint_step in checkpoint_steps:
            checkpoint_dir = checkpoint_root / f"global_step_{checkpoint_step}"
            checkpoint_dir.mkdir(parents=True)
            for filename in REQUIRED_CHECKPOINT_FILES:
                (checkpoint_dir / filename).write_bytes(b"weight")
        return dataset_root, manifest, checkpoint_root


    def _run_cli(
        dataset_root: Path, manifest: Path, checkpoint_root: Path, output_root: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable, str(SCRIPT_PATH),
                "--dataset-root", str(dataset_root),
                "--visual-manifest", str(manifest),
                "--checkpoint-root", str(checkpoint_root),
                "--output-root", str(output_root),
                "--expected-record-count", "2",
                "--expected-style-count", "2",
                *extra,
            ],
            capture_output=True,
            text=True,
        )

随后测试创建 global_step_10000、20000、30000、40000、50000；运行脚本时传入 --checkpoint-steps 10000 20000 30000 40000 50000 和 --validate-only；断言输出摘要的 checkpoint_steps 精确为这五个整数。

    def test_cli_validate_only_accepts_explicit_five_checkpoint_steps(tmp_path):
        dataset_root, manifest, checkpoint_root = _create_cli_fixture(
            tmp_path, checkpoint_steps=(10000, 20000, 30000, 40000, 50000)
        )
        output_root = tmp_path / "output"
        result = _run_cli(
            dataset_root,
            manifest,
            checkpoint_root,
            output_root,
            "--checkpoint-steps", "10000", "20000", "30000", "40000", "50000",
            "--validate-only",
        )

        assert result.returncode == 0, result.stderr
        summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == "validated"
        assert summary["checkpoint_steps"] == [10000, 20000, 30000, 40000, 50000]

将现有四个 validate-only CLI 测试改为调用这两个辅助函数，保留其原有断言；这样默认 checkpoint 列表仍是 (1000, 5000, 10000)，后续五 checkpoint 测试不会复制不同的命令结构。

- [ ] **Step 2: 运行新测试，确认 argparse 尚不识别参数。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py::test_cli_validate_only_accepts_explicit_five_checkpoint_steps -q

Expected: FAIL with argparse error mentioning unrecognized arguments: --checkpoint-steps.

- [ ] **Step 3: 将硬编码列表改为解析后的不可变步骤元组。**

在脚本保留 DEFAULT_CHECKPOINT_STEPS = (1000, 5000, 10000)，添加：

    def resolve_checkpoint_steps(raw_steps: list[int] | None) -> tuple[int, ...]:
        steps = DEFAULT_CHECKPOINT_STEPS if raw_steps is None else tuple(raw_steps)
        if not steps:
            raise ValueError("checkpoint_steps must not be empty")
        if any(step <= 0 for step in steps):
            raise ValueError("checkpoint_steps must contain positive integers")
        if len(set(steps)) != len(steps):
            raise ValueError("checkpoint_steps must not contain duplicates")
        return steps

在 parse_args 中添加：

    parser.add_argument("--checkpoint-steps", nargs="+", type=int)

将 _checkpoint_directories、_validate_empty_checkpoint_audit_outputs、run_sampling 统一接收 checkpoint_steps: tuple[int, ...] 或已构建的 checkpoint_directories；main 在预检查前调用 resolve_checkpoint_steps(args.checkpoint_steps)。所有 run_summary 的 checkpoint_steps 都使用 list(checkpoint_steps)，而非旧常量。

未传 --checkpoint-steps 时，摘要和行为必须保持 1000、5000、10000；传入的顺序必须保留，方便审计页按训练时间顺序输出。

- [ ] **Step 4: 添加默认兼容、重复值和自定义输出目录保护测试。**

追加三个测试：

    def test_resolve_checkpoint_steps_keeps_legacy_default():
        assert audit_script.resolve_checkpoint_steps(None) == (1000, 5000, 10000)

    @pytest.mark.parametrize("steps", [[], [10000, 10000], [0, 10000], [-1, 10000]])
    def test_resolve_checkpoint_steps_rejects_invalid_values(steps):
        with pytest.raises(ValueError):
            audit_script.resolve_checkpoint_steps(steps)

    def test_cli_rejects_existing_output_for_custom_checkpoint_step(tmp_path):
        dataset_root, manifest, checkpoint_root = _create_cli_fixture(
            tmp_path, checkpoint_steps=(10000, 20000, 30000, 40000, 50000)
        )
        output_root = tmp_path / "output"
        old_image = output_root / "global_step_20000" / "generated" / "old.png"
        _image(old_image, (1, 2, 3))
        result = _run_cli(
            dataset_root,
            manifest,
            checkpoint_root,
            output_root,
            "--checkpoint-steps", "10000", "20000", "30000", "40000", "50000",
            "--validate-only",
        )

        assert result.returncode != 0
        assert old_image.is_file()
        summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
        assert summary["status"] == "failed"
        assert "checkpoint audit output already exists" in summary["error"]

- [ ] **Step 5: 运行目标测试并验证默认与自定义行为。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py -q

Expected: all visual-audit tests pass, including existing default three-checkpoint and新增五-checkpoint预检查测试。

### Task 3: 记录 50k AutoDL 训练与五 checkpoint 审计流程

**Files:**
- Create: experiments/target_glyph_generation/docs/fontdiffuser_p1_baseline_50k_runbook.md

- [ ] **Step 1: 新建中文运行手册。**

创建独立文档，避免修改既有 10k 先导运行手册。文档必须逐段给出以下精确内容：

1. 训练性质：从随机初始化训练 50k；不得将 10k 权重加载为正式 50k 的起点；Phase 1 不启用 SCR。
2. 环境和路径：PROJECT=/root/autodl-tmp/shufa、OMP_NUM_THREADS=1、MKL_NUM_THREADS=1、conda run --no-capture-output -n fontdiffuser python。
3. 训练输出：TRAIN_OUT=$PROJECT/experiments/target_glyph_generation/outputs/fontdiffuser_p1_extended_phase1_baseline_50k，必须在运行前不存在；不得删除已有 10k 输出。
4. screen 命令：screen -S p1_phase1_baseline_50k_20260717。
5. 正式训练命令必须在 external_repos/FontDiffuser 下运行，并包含下列完整参数：

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

6. 训练完成后，先在无卡状态用 --checkpoint-steps 10000 20000 30000 40000 50000 --validate-only 检查固定清单、五个权重和全新审计输出根。
7. GPU 冒烟命令在同一五步骤参数后加 --limit-per-style 1；正式审计命令不加该参数。正式审计每个 checkpoint 生成 380 图和 19 页，五个 checkpoint 共 1,900 图和 95 页。
8. 只有人工确认五阶段图像后，才考虑 9,580 条全量生成和指标；50k 仍改善则讨论延长，40k 与 50k 平台期则固定 50k。
9. 不记录密码、密钥、主机地址或端口；不使用自动关机、自动删除或破坏性清理。

- [ ] **Step 2: 检查运行手册中的参数与脚本帮助一致。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe experiments\target_glyph_generation\scripts\run_p1_checkpoint_visual_audit.py --help

Expected: help includes --checkpoint-steps alongside existing input、安全和采样参数。

- [ ] **Step 3: 运行完整目标实验测试集和静态检查。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests -q
    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m py_compile experiments\target_glyph_generation\scripts\run_p1_checkpoint_visual_audit.py
    git diff --check

Expected: pytest has no failures; py_compile exits 0; diff --check has no whitespace errors. 现有 P0 文档的 LF/CRLF 提示如仍存在，记录为既有警告，不能通过改写无关文件消除。

- [ ] **Step 4: 不提交或推送。**

本轮只保留工作树修改，等待用户明确要求后再进行任何 Git 提交、推送、合并或清理操作。

## 自检记录

- 从随机初始化、50k、每10k checkpoint、保留既有 10k 先导实验：Task 1 和 Task 3。
- 自定义五 checkpoint 审计且默认 1k/5k/10k 兼容：Task 2。
- 380 固定样例、19 风格、非空输出拒绝、失败摘要和人工目检门槛：Task 2 和 Task 3。
- 不计算 9,580 全量指标、不启用 SCR、不动官方 train.py：全部任务均明确限制。
- 术语与函数名一致：DEFAULT_CHECKPOINT_STEPS、resolve_checkpoint_steps、checkpoint_steps、_checkpoint_directories、_validate_empty_checkpoint_audit_outputs、run_sampling。
