# P1 固定检查点视觉采样与审计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 对 P1-extended Phase 1 已有的 1,000、5,000 和 10,000 step 权重，针对固定的 380 个测试样例生成可复核图像、生成映射清单和按风格组织的视觉审计页；本轮不计算完整测试集指标、不改动模型训练。

**Architecture:** 无 GPU 的清单校验、稳定命名、结果清单、运行摘要和审计页拼图放在一个纯 Python 模块，先由合成小图单测。GPU 命令行脚本只负责加载官方 FontDiffuser pipeline：每个 checkpoint 只加载一次，逐样例推理；任何输入或样例失败均非零退出，且不能把不完整 checkpoint 标记为完成。

**Tech Stack:** Python 3.10、csv/json/hashlib/pathlib、Pillow、PyTorch 1.13.1 + CUDA、官方 FontDiffuser sample.py、DPM-Solver++。

---

## 文件边界与固定契约

- 新建 experiments/target_glyph_generation/src/target_glyph_generation/p1_visual_audit.py：纯函数；绝不导入 Torch 或官方仓库。
- 新建 experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py：GPU 命令行入口，复用官方 image_process()、load_fontdiffuer_pipeline()，但不调用会覆盖输出文件名的官方 sampling()。
- 新建 experiments/target_glyph_generation/tests/test_p1_visual_audit.py：临时目录和 8×8 RGB 合成图单测；不需要 GPU、权重或 FontDiffuser。
- 修改 experiments/target_glyph_generation/docs/fontdiffuser_p1_baseline_runbook.md：增加无卡预检、19 条 GPU 冒烟、380×3 正式运行和人工目检说明。

默认固定输入为 outputs/p1_extended_evaluation_20260716/visual_test_manifest.csv，必须验证 380 条、19 种风格和每条内容图、参考图、目标图。固定 checkpoint 为 global_step_1000、global_step_5000、global_step_10000，每个目录必须有 unet.pth、style_encoder.pth、content_encoder.pth、total_model.pth。

固定推理参数为 resolution=96、style_image_size=(96,96)、content_image_size=(96,96)、content_encoder_downsample_size=3、algorithm_type=dpmsolver++、guidance_type=classifier-free、guidance_scale=7.5、num_inference_steps=20、order=2、skip_type=time_uniform、method=multistep、seed=20260716。

正式输出根目录为 outputs/p1_extended_checkpoint_visual_audit_20260717，不能位于训练 checkpoint 根目录中。每个 checkpoint 下有 generated、generated_manifest.csv、audit_pages。图像名固定为 sample_0001_<sha12>.png 至 sample_0380_<sha12>.png；其中 sha12 是 evaluation ID 的 SHA-256 前 12 位。

正式运行的每张 style 审计页含 20 个样例：4 列×5 行 tile，每个 tile 为 2×2 面板，左上内容 C、右上参考 R、左下真实目标 T、右下生成 G。GPU 冒烟明确传入每风格 1 条，因此生成同布局的单 tile 页面而不把空白误称为缺图。审计页仅写 ASCII 风格 ID 和样例序号；字符和完整路径保留在 UTF-8 BOM CSV，避免服务器缺中文字体时给出错误标签。

### Task 1: 建立无 GPU 的输入契约与稳定输出名

**Files:**
- Create: experiments/target_glyph_generation/tests/test_p1_visual_audit.py
- Create: experiments/target_glyph_generation/src/target_glyph_generation/p1_visual_audit.py

- [ ] **Step 1: 写失败测试，锁定清单和 checkpoint 校验行为。**

在测试文件写入以下测试和辅助函数。

    import csv
    from pathlib import Path

    import pytest
    from PIL import Image

    from target_glyph_generation.p1_visual_audit import (
        REQUIRED_CHECKPOINT_FILES,
        load_and_validate_visual_manifest,
        stable_generated_filename,
        validate_checkpoint_directory,
    )


    def _image(path: Path, color: tuple[int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), color).save(path)


    def _record(style: str, character: str, index: int) -> dict[str, str]:
        return {
            "evaluation_id": f"{style}+{character}",
            "style_id": style,
            "character": character,
            "content_path": f"test/ContentImage/{character}.jpg",
            "reference_path": f"train/TargetImage/{style}/reference.jpg",
            "target_path": f"test/TargetImage/{style}/{index}.jpg",
        }


    def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


    def test_manifest_validation_sorts_records_and_checks_each_image(tmp_path):
        dataset_root = tmp_path / "dataset"
        rows = [_record("style_b", "乙", 2), _record("style_a", "甲", 1)]
        for index, row in enumerate(rows):
            _image(dataset_root / row["content_path"], (index + 1, 0, 0))
            _image(dataset_root / row["reference_path"], (0, index + 1, 0))
            _image(dataset_root / row["target_path"], (0, 0, index + 1))
        manifest = tmp_path / "visual_test_manifest.csv"
        _write_manifest(manifest, rows)

        records = load_and_validate_visual_manifest(
            manifest, dataset_root, expected_record_count=2, expected_style_count=2
        )

        assert [record["evaluation_id"] for record in records] == ["style_a+甲", "style_b+乙"]
        assert stable_generated_filename(1, "style_a+甲") == stable_generated_filename(1, "style_a+甲")
        assert stable_generated_filename(1, "style_a+甲") != stable_generated_filename(2, "style_a+甲")


    def test_manifest_validation_rejects_missing_image_and_wrong_cardinality(tmp_path):
        manifest = tmp_path / "visual_test_manifest.csv"
        _write_manifest(manifest, [_record("style_a", "甲", 1)])

        with pytest.raises(ValueError, match="expected 2 visual records"):
            load_and_validate_visual_manifest(manifest, tmp_path / "dataset", 2, 1)


    def test_checkpoint_validation_requires_all_four_weight_files(tmp_path):
        checkpoint = tmp_path / "global_step_1000"
        checkpoint.mkdir()
        for filename in REQUIRED_CHECKPOINT_FILES[:-1]:
            (checkpoint / filename).write_bytes(b"weight")

        with pytest.raises(ValueError, match="missing checkpoint weight"):
            validate_checkpoint_directory(checkpoint)

- [ ] **Step 2: 运行测试，确认模块尚不存在而失败。**

Run:

    Set-Location 'D:\sw data\vscode\shufa\.worktrees\target-glyph-dataset'
    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py -q

Expected: collection error saying target_glyph_generation.p1_visual_audit does not exist.

- [ ] **Step 3: 实现最小的清单、权重和命名接口。**

在 p1_visual_audit.py 写入此初版实现。稳定图像名只由 1-based 序号和 evaluation ID 的 SHA-256 前 12 位组成；校验拒绝空列、重复 ID、缺图、记录数不符和风格数不符。

    """Pure-Python utilities for P1 fixed-checkpoint visual audits."""

    import csv
    import hashlib
    from pathlib import Path


    REQUIRED_MANIFEST_FIELDS = (
        "evaluation_id",
        "style_id",
        "character",
        "content_path",
        "reference_path",
        "target_path",
    )
    REQUIRED_CHECKPOINT_FILES = (
        "unet.pth",
        "style_encoder.pth",
        "content_encoder.pth",
        "total_model.pth",
    )


    def stable_generated_filename(index: int, evaluation_id: str) -> str:
        if index <= 0:
            raise ValueError("generated-image index must be positive")
        digest = hashlib.sha256(evaluation_id.encode("utf-8")).hexdigest()[:12]
        return f"sample_{index:04d}_{digest}.png"


    def load_and_validate_visual_manifest(
        manifest_path: Path,
        dataset_root: Path,
        expected_record_count: int,
        expected_style_count: int,
    ) -> list[dict[str, str]]:
        manifest_path, dataset_root = Path(manifest_path), Path(dataset_root)
        try:
            with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None or not set(REQUIRED_MANIFEST_FIELDS).issubset(reader.fieldnames):
                    raise ValueError(f"visual manifest misses required columns: {manifest_path}")
                rows = list(reader)
        except OSError as error:
            raise ValueError(f"unable to read visual manifest: {manifest_path}") from error

        if len(rows) != expected_record_count:
            raise ValueError(f"expected {expected_record_count} visual records, found {len(rows)}")

        seen_ids: set[str] = set()
        for row in rows:
            if any(not row[field].strip() for field in REQUIRED_MANIFEST_FIELDS):
                raise ValueError(f"visual manifest has an empty required field: {row}")
            if row["evaluation_id"] in seen_ids:
                raise ValueError(f"visual manifest has duplicate evaluation_id: {row['evaluation_id']}")
            seen_ids.add(row["evaluation_id"])
            for field in ("content_path", "reference_path", "target_path"):
                image_path = dataset_root / row[field]
                if not image_path.is_file():
                    raise ValueError(f"visual manifest image is missing: {image_path}")

        style_count = len({row["style_id"] for row in rows})
        if style_count != expected_style_count:
            raise ValueError(f"expected {expected_style_count} styles, found {style_count}")
        return sorted(rows, key=lambda row: (row["style_id"], row["character"], row["evaluation_id"]))


    def validate_checkpoint_directory(checkpoint_dir: Path) -> None:
        checkpoint_dir = Path(checkpoint_dir)
        for filename in REQUIRED_CHECKPOINT_FILES:
            weight_path = checkpoint_dir / filename
            if not weight_path.is_file():
                raise ValueError(f"missing checkpoint weight: {weight_path}")

- [ ] **Step 4: 运行首批测试并确认通过。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py -q

Expected: 3 passed.

### Task 2: 写生成映射、运行摘要与四联审计页

**Files:**
- Modify: experiments/target_glyph_generation/tests/test_p1_visual_audit.py
- Modify: experiments/target_glyph_generation/src/target_glyph_generation/p1_visual_audit.py

- [ ] **Step 1: 增加失败测试，锁定 20 样例 style 页、CSV 和摘要。**

追加以下测试。20 个同 style 合成图保证一页审计图只能在该 style 完整时生成。

    from target_glyph_generation.p1_visual_audit import (
        build_generated_rows,
        write_audit_pages,
        write_generated_manifest,
        write_run_summary,
    )


    def test_generated_manifest_and_style_audit_page_are_complete(tmp_path):
        dataset_root, checkpoint_dir = tmp_path / "dataset", tmp_path / "global_step_1000"
        generated_dir = checkpoint_dir / "generated"
        records = [_record("style_a", chr(0x4E00 + index), index) for index in range(20)]
        for index, record in enumerate(records, start=1):
            _image(dataset_root / record["content_path"], (255, 0, 0))
            _image(dataset_root / record["reference_path"], (0, 255, 0))
            _image(dataset_root / record["target_path"], (0, 0, 255))
            _image(generated_dir / stable_generated_filename(index, record["evaluation_id"]), (255, 255, 0))

        generated_rows = build_generated_rows(records, generated_dir, checkpoint_step=1000)
        manifest_path = checkpoint_dir / "generated_manifest.csv"
        write_generated_manifest(manifest_path, generated_rows)
        pages = write_audit_pages(
            generated_rows,
            dataset_root,
            checkpoint_dir,
            checkpoint_dir / "audit_pages",
            tile_size=16,
            samples_per_style=20,
        )
        summary_path = tmp_path / "run_summary.json"
        write_run_summary(summary_path, {"status": "complete", "checkpoint_count": 1})

        with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
            assert len(list(csv.DictReader(handle))) == 20
        assert [page.name for page in pages] == ["style_a.png"]
        assert Image.open(pages[0]).size == (8 * 16, 10 * 16 + 24)
        assert '"status": "complete"' in summary_path.read_text(encoding="utf-8")


    def test_audit_page_refuses_incomplete_style_group(tmp_path):
        rows = [{"style_id": "style_a", "evaluation_id": "style_a+甲", "sample_index": "1"}]
        with pytest.raises(ValueError, match="expected 20 records"):
            write_audit_pages(
                rows, tmp_path, tmp_path, tmp_path / "audit_pages", tile_size=16, samples_per_style=20
            )


    def test_audit_page_allows_explicit_single_sample_smoke_group(tmp_path):
        dataset_root, checkpoint_dir = tmp_path / "dataset", tmp_path / "global_step_1000"
        record = _record("style_a", "甲", 1)
        for field, color in (
            ("content_path", (255, 0, 0)),
            ("reference_path", (0, 255, 0)),
            ("target_path", (0, 0, 255)),
        ):
            _image(dataset_root / record[field], color)
        generated_dir = checkpoint_dir / "generated"
        _image(generated_dir / stable_generated_filename(1, record["evaluation_id"]), (255, 255, 0))

        rows = build_generated_rows([record], generated_dir, checkpoint_step=1000)
        pages = write_audit_pages(
            rows, dataset_root, checkpoint_dir, checkpoint_dir / "audit_pages", tile_size=16, samples_per_style=1
        )

        assert [page.name for page in pages] == ["style_a.png"]

- [ ] **Step 2: 运行测试，确认新增接口尚未定义而失败。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py -q

Expected: collection error naming build_generated_rows, write_audit_pages, write_generated_manifest or write_run_summary.

- [ ] **Step 3: 实现结果映射与审计图。**

在 p1_visual_audit.py 文件头补充 import json、from collections import defaultdict、from PIL import Image, ImageDraw，并追加以下实现。generated_path 始终相对 checkpoint 目录，生成面板明确从 checkpoint_dir / generated_path 读取。

    GENERATED_MANIFEST_FIELDS = (
        "checkpoint_step", "sample_index", "evaluation_id", "style_id", "character",
        "content_path", "reference_path", "target_path", "generated_path",
    )


    def build_generated_rows(
        records: list[dict[str, str]], generated_dir: Path, checkpoint_step: int,
    ) -> list[dict[str, str]]:
        rows = []
        for index, record in enumerate(records, start=1):
            filename = stable_generated_filename(index, record["evaluation_id"])
            generated_path = Path(generated_dir) / filename
            if not generated_path.is_file():
                raise ValueError(f"generated image is missing: {generated_path}")
            rows.append(
                {
                    "checkpoint_step": str(checkpoint_step),
                    "sample_index": str(index),
                    "evaluation_id": record["evaluation_id"],
                    "style_id": record["style_id"],
                    "character": record["character"],
                    "content_path": record["content_path"],
                    "reference_path": record["reference_path"],
                    "target_path": record["target_path"],
                    "generated_path": (Path("generated") / filename).as_posix(),
                }
            )
        return rows


    def write_generated_manifest(path: Path, rows: list[dict[str, str]]) -> None:
        if not rows:
            raise ValueError("generated manifest cannot be empty")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=GENERATED_MANIFEST_FIELDS)
            writer.writeheader()
            writer.writerows(rows)


    def _load_panel(path: Path, tile_size: int) -> Image.Image:
        return Image.open(path).convert("RGB").resize((tile_size, tile_size), Image.Resampling.NEAREST)


    def write_audit_pages(
        rows: list[dict[str, str]], dataset_root: Path, checkpoint_dir: Path,
        audit_dir: Path, tile_size: int = 96, samples_per_style: int = 20,
    ) -> list[Path]:
        by_style: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            by_style[row["style_id"]].append(row)

        pages = []
        for style_id, style_rows in sorted(by_style.items()):
            ordered_rows = sorted(style_rows, key=lambda row: int(row["sample_index"]))
            if samples_per_style <= 0:
                raise ValueError("samples_per_style must be positive")
            if len(ordered_rows) != samples_per_style:
                raise ValueError(
                    f"style {style_id} expected {samples_per_style} records, found {len(ordered_rows)}"
                )
            page = Image.new("RGB", (8 * tile_size, 10 * tile_size + 24), "white")
            draw = ImageDraw.Draw(page)
            draw.text((4, 4), f"{style_id} | C=content R=reference T=target G=generated", fill="black")
            for local_index, row in enumerate(ordered_rows):
                x = (local_index % 4) * 2 * tile_size
                y = 24 + (local_index // 4) * 2 * tile_size
                panel_paths = (
                    Path(dataset_root) / row["content_path"],
                    Path(dataset_root) / row["reference_path"],
                    Path(dataset_root) / row["target_path"],
                    Path(checkpoint_dir) / row["generated_path"],
                )
                positions = ((x, y), (x + tile_size, y), (x, y + tile_size), (x + tile_size, y + tile_size))
                for panel_path, position in zip(panel_paths, positions):
                    page.paste(_load_panel(panel_path, tile_size), position)
                draw.text((x + 2, y + 2), f"{int(row['sample_index']):03d}", fill="red")
            page_path = Path(audit_dir) / f"{style_id}.png"
            page_path.parent.mkdir(parents=True, exist_ok=True)
            page.save(page_path)
            pages.append(page_path)
        return pages


    def write_run_summary(path: Path, payload: dict[str, object]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

- [ ] **Step 4: 运行审计页测试并确认通过。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py -q

Expected: 6 passed.

### Task 3: 实现一次加载一个 checkpoint 的 GPU 命令行采样器

**Files:**
- Modify: experiments/target_glyph_generation/tests/test_p1_visual_audit.py
- Create: experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py
- Modify: experiments/target_glyph_generation/src/target_glyph_generation/p1_visual_audit.py

- [ ] **Step 1: 写无 GPU 的 validate-only 集成测试。**

追加以下 subprocess 测试。它建 2 条、2 style 合成清单与三个完整假 checkpoint；此模式只能写 run_summary.json，不能导入模型或创建 generated 目录。

    import subprocess
    import sys

    PROJECT_DIR = Path(__file__).parents[1]


    def test_cli_validate_only_writes_summary_without_loading_model(tmp_path):
        dataset_root = tmp_path / "dataset"
        rows = [_record("style_a", "甲", 1), _record("style_b", "乙", 2)]
        for row in rows:
            for field in ("content_path", "reference_path", "target_path"):
                _image(dataset_root / row[field], (1, 2, 3))
        manifest = tmp_path / "visual.csv"
        _write_manifest(manifest, rows)

        checkpoint_root = tmp_path / "checkpoints"
        for step in (1000, 5000, 10000):
            directory = checkpoint_root / f"global_step_{step}"
            directory.mkdir(parents=True)
            for filename in REQUIRED_CHECKPOINT_FILES:
                (directory / filename).write_bytes(b"weight")

        output_root = tmp_path / "output"
        script = PROJECT_DIR / "scripts" / "run_p1_checkpoint_visual_audit.py"
        completed = subprocess.run(
            [
                sys.executable, str(script),
                "--dataset-root", str(dataset_root),
                "--visual-manifest", str(manifest),
                "--checkpoint-root", str(checkpoint_root),
                "--output-root", str(output_root),
                "--expected-record-count", "2",
                "--expected-style-count", "2",
                "--validate-only",
            ],
            check=False, capture_output=True, text=True,
        )

        assert completed.returncode == 0, completed.stderr
        assert '"status": "validated"' in (output_root / "run_summary.json").read_text(encoding="utf-8")
        assert not list(output_root.glob("global_step_*/generated"))

- [ ] **Step 2: 运行该测试，确认脚本不存在而失败。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py::test_cli_validate_only_writes_summary_without_loading_model -q

Expected: FAIL because run_p1_checkpoint_visual_audit.py does not exist.

- [ ] **Step 3: 实现 CLI 前置校验和 validate-only。**

新脚本入口如下。它把 src 加入 sys.path，默认强制 380 条、19 style；limit-per-style 只能在完整清单验证后每 style 选前 N 条。

    #!/usr/bin/env python
    """Generate fixed P1 visual samples for selected FontDiffuser checkpoints."""

    import argparse
    import sys
    from pathlib import Path

    SCRIPT_DIR = Path(__file__).resolve().parent
    EXPERIMENT_DIR = SCRIPT_DIR.parent
    sys.path.insert(0, str(EXPERIMENT_DIR / "src"))

    from target_glyph_generation.p1_visual_audit import (
        load_and_validate_visual_manifest,
        validate_checkpoint_directory,
        write_run_summary,
    )

    CHECKPOINT_STEPS = (1000, 5000, 10000)


    def parse_args() -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        parser.add_argument("--dataset-root", type=Path, required=True)
        parser.add_argument("--visual-manifest", type=Path, required=True)
        parser.add_argument("--checkpoint-root", type=Path, required=True)
        parser.add_argument("--output-root", type=Path, required=True)
        parser.add_argument("--fontdiffuser-root", type=Path)
        parser.add_argument("--device", default="cuda:0")
        parser.add_argument("--expected-record-count", type=int, default=380)
        parser.add_argument("--expected-style-count", type=int, default=19)
        parser.add_argument("--limit-per-style", type=int, default=0)
        parser.add_argument("--seed", type=int, default=20260716)
        parser.add_argument("--validate-only", action="store_true")
        return parser.parse_args()


    def select_records(records: list[dict[str, str]], limit_per_style: int) -> list[dict[str, str]]:
        if limit_per_style == 0:
            return records
        if limit_per_style < 0:
            raise ValueError("limit-per-style must be zero or positive")
        selected = []
        for style_id in sorted({record["style_id"] for record in records}):
            choices = [record for record in records if record["style_id"] == style_id]
            if len(choices) < limit_per_style:
                raise ValueError(f"style {style_id} has fewer than {limit_per_style} records")
            selected.extend(choices[:limit_per_style])
        return selected


    def main() -> None:
        args = parse_args()
        records = load_and_validate_visual_manifest(
            args.visual_manifest, args.dataset_root, args.expected_record_count, args.expected_style_count
        )
        checkpoint_dirs = {step: args.checkpoint_root / f"global_step_{step}" for step in CHECKPOINT_STEPS}
        for directory in checkpoint_dirs.values():
            validate_checkpoint_directory(directory)
        if args.checkpoint_root.resolve() in args.output_root.resolve().parents:
            raise ValueError("output-root must not be inside checkpoint-root")
        selected = select_records(records, args.limit_per_style)
        if args.validate_only:
            write_run_summary(
                args.output_root / "run_summary.json",
                {
                    "status": "validated",
                    "selected_record_count": len(selected),
                    "style_count": len({record["style_id"] for record in selected}),
                    "checkpoint_steps": list(CHECKPOINT_STEPS),
                    "seed": args.seed,
                },
            )
            return
        if args.fontdiffuser_root is None or not (args.fontdiffuser_root / "sample.py").is_file():
            raise ValueError("fontdiffuser-root must point to the official repository containing sample.py")
        run_sampling(args, selected, checkpoint_dirs)


    if __name__ == "__main__":
        main()

- [ ] **Step 4: 运行无 GPU CLI 测试并确认通过。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py::test_cli_validate_only_writes_summary_without_loading_model -q

Expected: 1 passed.

- [ ] **Step 5: 加入官方模型适配和全部推理循环。**

在同一脚本的 select_records 和 main 之间添加以下函数；main 最后保留 run_sampling 调用。显式设置 P1 基线的全部采样参数；每个 checkpoint 只创建一个 pipeline，发生任何异常时写 status=failed 摘要并抛出，因而不会写该 checkpoint 的映射清单或审计页。

    def build_sampling_args(official_root: Path, checkpoint_dir: Path, device: str, seed: int):
        sys.path.insert(0, str(official_root))
        from configs.fontdiffuser import get_parser

        config = get_parser().parse_args([])
        config.ckpt_dir = str(checkpoint_dir)
        config.device = device
        config.seed = seed
        config.demo = False
        config.character_input = False
        config.resolution = 96
        config.style_image_size = (96, 96)
        config.content_image_size = (96, 96)
        config.content_encoder_downsample_size = 3
        config.algorithm_type = "dpmsolver++"
        config.guidance_type = "classifier-free"
        config.guidance_scale = 7.5
        config.num_inference_steps = 20
        config.order = 2
        config.skip_type = "time_uniform"
        config.method = "multistep"
        config.correcting_x0_fn = None
        config.t_start = None
        config.t_end = None
        return config


    def generate_one(config, pipe, image_process, content_path: Path, reference_path: Path):
        import torch
        from accelerate.utils import set_seed

        config.content_image_path = str(content_path)
        config.style_image_path = str(reference_path)
        set_seed(config.seed)
        content_image, style_image, _ = image_process(config)
        with torch.no_grad():
            images = pipe.generate(
                content_images=content_image.to(config.device),
                style_images=style_image.to(config.device),
                batch_size=1,
                order=config.order,
                num_inference_step=config.num_inference_steps,
                content_encoder_downsample_size=config.content_encoder_downsample_size,
                t_start=config.t_start,
                t_end=config.t_end,
                dm_size=config.content_image_size,
                algorithm_type=config.algorithm_type,
                skip_type=config.skip_type,
                method=config.method,
                correcting_x0_fn=config.correcting_x0_fn,
            )
        return images[0]


    def run_sampling(args, records: list[dict[str, str]], checkpoint_dirs: dict[int, Path]) -> None:
        import torch
        from target_glyph_generation.p1_visual_audit import (
            build_generated_rows,
            stable_generated_filename,
            write_audit_pages,
            write_generated_manifest,
        )

        sys.path.insert(0, str(args.fontdiffuser_root))
        from sample import image_process, load_fontdiffuer_pipeline

        checkpoint_summaries = []
        for step in CHECKPOINT_STEPS:
            current_id = None
            checkpoint_dir = checkpoint_dirs[step]
            output_dir = args.output_root / f"global_step_{step}"
            generated_dir = output_dir / "generated"
            pipe = None
            try:
                config = build_sampling_args(args.fontdiffuser_root, checkpoint_dir, args.device, args.seed)
                pipe = load_fontdiffuer_pipeline(config)
                generated_dir.mkdir(parents=True, exist_ok=True)
                for index, record in enumerate(records, start=1):
                    current_id = record["evaluation_id"]
                    output_path = generated_dir / stable_generated_filename(index, current_id)
                    image = generate_one(
                        config, pipe, image_process,
                        args.dataset_root / record["content_path"],
                        args.dataset_root / record["reference_path"],
                    )
                    image.save(output_path)
                rows = build_generated_rows(records, generated_dir, step)
                write_generated_manifest(output_dir / "generated_manifest.csv", rows)
                pages = write_audit_pages(
                    rows,
                    args.dataset_root,
                    output_dir,
                    output_dir / "audit_pages",
                    tile_size=96,
                    samples_per_style=args.limit_per_style or 20,
                )
                checkpoint_summaries.append(
                    {"checkpoint_step": step, "image_count": len(rows), "audit_page_count": len(pages)}
                )
            except Exception as error:
                write_run_summary(
                    args.output_root / "run_summary.json",
                    {
                        "status": "failed",
                        "checkpoint_step": step,
                        "evaluation_id": current_id,
                        "error": str(error),
                    },
                )
                raise
            finally:
                if pipe is not None:
                    del pipe
                torch.cuda.empty_cache()

        write_run_summary(
            args.output_root / "run_summary.json",
            {
                "status": "complete",
                "selected_record_count": len(records),
                "style_count": len({record["style_id"] for record in records}),
                "checkpoint_steps": list(CHECKPOINT_STEPS),
                "seed": args.seed,
                "checkpoints": checkpoint_summaries,
            },
        )

- [ ] **Step 6: 运行所有新测试和既有 P1 清单测试。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests\test_p1_visual_audit.py experiments\target_glyph_generation\tests\test_p1_evaluation.py -q

Expected: all tests pass and no CUDA device allocation occurs.

### Task 4: 记录远程运行流程并做回归检查

**Files:**
- Modify: experiments/target_glyph_generation/docs/fontdiffuser_p1_baseline_runbook.md

- [ ] **Step 1: 新增 P1 Phase 1 检查点视觉审计一节。**

在运行手册文末加入以下正式远程命令；它不自动关机，先设置已验证的 OMP/MKL 修复值，且不记录密码或密钥。

    export OMP_NUM_THREADS=1
    export MKL_NUM_THREADS=1
    PROJECT=/root/autodl-tmp/shufa
    OUT=$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_checkpoint_visual_audit_20260717

    cd "$PROJECT/external_repos/FontDiffuser"
    conda run --no-capture-output -n fontdiffuser python "$PROJECT/experiments/target_glyph_generation/scripts/run_p1_checkpoint_visual_audit.py" --dataset-root "$PROJECT/experiments/target_glyph_generation/data/fontdiffuser_p1_extended" --visual-manifest "$PROJECT/experiments/target_glyph_generation/outputs/p1_extended_evaluation_20260716/visual_test_manifest.csv" --checkpoint-root "$PROJECT/experiments/target_glyph_generation/outputs/fontdiffuser_p1_extended_phase1_baseline_10k" --output-root "$OUT" --fontdiffuser-root "$PROJECT/external_repos/FontDiffuser" --device cuda:0

同节写明：

1. 无卡预检：正式命令加 --validate-only，应写 status=validated。
2. GPU 冒烟：正式命令加 --limit-per-style 1；仍校验完整 380/19 清单，但只生成 19×3 张图和每 checkpoint 19 张单 tile 审计页，只用于流程检查。
3. 正式完成判据：三个 generated_manifest.csv 各有 380 数据行；三个 generated 目录各有 380 张 PNG；三个 audit_pages 各有 19 张 PNG；根 run_summary.json 为 status=complete。随后必须人工目检字符结构、风格迁移、全黑/全白和纯噪声；确认前不能生成 9,580 张全测试集或报告 L1、SSIM、LPIPS、FID。

- [ ] **Step 2: 运行完整目标实验测试集。**

Run:

    & .\.venvs\target-glyph-dataset\Scripts\python.exe -m pytest experiments\target_glyph_generation\tests -q

Expected: all tests pass。若出现既有无关失败，原样记录失败测试名和输出，不能删弱本功能测试。

- [ ] **Step 3: 检查差异，不提交也不推送。**

Run:

    git -C 'D:\sw data\vscode\shufa\.worktrees\target-glyph-dataset' diff --check
    git -C 'D:\sw data\vscode\shufa\.worktrees\target-glyph-dataset' status --short

Expected: diff --check 没有空白错误；本功能仅改变本计划列出的模块、脚本、测试和运行手册。按当前用户约定，本计划和其实现均不自行提交或推送。

## 自检记录

- 固定 380 条、19 style、三 checkpoint、4 个权重文件和三类输入图的前置校验：Task 1 与 Task 3。
- P1 一致的 96×96、DPM-Solver++、CFG 7.5、20 步和 seed：Task 3。
- 单 checkpoint 单次加载、逐图稳定命名、失败不能产生伪完整审计页、输出不能覆盖训练结果：Task 3。
- 380 个生成图、380 条映射、19 张四联审计页、根摘要：Task 2 与 Task 3。
- GPU 冒烟、正式运行、人工目检边界、暂不做全量指标：Task 4。
- 函数名和参数保持一致：stable_generated_filename、load_and_validate_visual_manifest、validate_checkpoint_directory、build_generated_rows、write_generated_manifest、write_audit_pages、write_run_summary；write_audit_pages 显式接收 checkpoint_dir 与 samples_per_style，没有隐式路径推断，并同时支持正式 20 条和冒烟 1 条。
