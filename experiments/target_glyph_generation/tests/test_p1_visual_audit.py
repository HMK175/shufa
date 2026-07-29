import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

from PIL import Image
import pytest

from target_glyph_generation.p1_visual_audit import (
    GENERATED_MANIFEST_FIELDS,
    REQUIRED_CHECKPOINT_FILES,
    build_generated_rows,
    load_and_validate_visual_manifest,
    stable_generated_filename,
    validate_checkpoint_directory,
    write_audit_pages,
    write_generated_manifest,
    write_run_summary,
)


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "run_p1_checkpoint_visual_audit.py"


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


def _create_cli_fixture(tmp_path, checkpoint_steps=(1000, 5000, 10000)):
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

    return dataset_root, manifest, checkpoint_root, tmp_path / "audit_output"


def _run_cli(dataset_root, manifest, checkpoint_root, output_root, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--dataset-root",
            str(dataset_root),
            "--visual-manifest",
            str(manifest),
            "--checkpoint-root",
            str(checkpoint_root),
            "--output-root",
            str(output_root),
            "--expected-record-count",
            "2",
            "--expected-style-count",
            "2",
            *extra,
        ],
        capture_output=True,
        text=True,
    )


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


def test_manifest_validation_rejects_wrong_cardinality(tmp_path):
    manifest = tmp_path / "visual_test_manifest.csv"
    _write_manifest(manifest, [_record("style_a", "甲", 1)])

    with pytest.raises(ValueError, match="expected 2 visual records"):
        load_and_validate_visual_manifest(manifest, tmp_path / "dataset", 2, 1)


def test_manifest_validation_rejects_image_paths_that_escape_dataset_root(tmp_path):
    dataset_root = tmp_path / "dataset"
    outside_image = tmp_path / "outside" / "escape.jpg"
    _image(outside_image, (1, 2, 3))
    row = _record("style_a", "甲", 1)
    for field in ("content_path", "reference_path", "target_path"):
        row[field] = "../outside/escape.jpg"
    manifest = tmp_path / "visual_test_manifest.csv"
    _write_manifest(manifest, [row])

    with pytest.raises(ValueError, match="escapes dataset root"):
        load_and_validate_visual_manifest(manifest, dataset_root, 1, 1)


def test_checkpoint_validation_requires_all_four_weight_files(tmp_path):
    checkpoint = tmp_path / "global_step_1000"
    checkpoint.mkdir()
    for filename in REQUIRED_CHECKPOINT_FILES[:-1]:
        (checkpoint / filename).write_bytes(b"weight")

    with pytest.raises(ValueError, match="missing checkpoint weight"):
        validate_checkpoint_directory(checkpoint)


def _generated_records_and_images(
    dataset_root: Path,
    checkpoint_dir: Path,
    count: int,
) -> list[dict[str, str]]:
    records = [_record("style_a", f"char_{index:02d}", index) for index in range(1, count + 1)]
    for index, record in enumerate(records, start=1):
        _image(dataset_root / record["content_path"], (index, 0, 0))
        _image(dataset_root / record["reference_path"], (0, index, 0))
        _image(dataset_root / record["target_path"], (0, 0, index))
        _image(
            checkpoint_dir / "generated" / stable_generated_filename(index, record["evaluation_id"]),
            (index, index, 0),
        )
    return records


def test_generated_manifest_summary_and_twenty_sample_style_audit_page(tmp_path):
    dataset_root = tmp_path / "dataset"
    checkpoint_dir = tmp_path / "global_step_1000"
    records = _generated_records_and_images(dataset_root, checkpoint_dir, 20)

    generated_rows = build_generated_rows(records, checkpoint_dir / "generated", checkpoint_step=1000)
    manifest_path = checkpoint_dir / "generated_manifest.csv"
    summary_path = checkpoint_dir / "run_summary.json"
    audit_dir = checkpoint_dir / "audit_pages"
    write_generated_manifest(manifest_path, generated_rows)
    write_run_summary(summary_path, {"status": "complete"})
    pages = write_audit_pages(generated_rows, dataset_root, checkpoint_dir, audit_dir)

    with manifest_path.open(encoding="utf-8-sig", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    assert len(manifest_rows) == 20
    assert tuple(manifest_rows[0]) == GENERATED_MANIFEST_FIELDS
    assert manifest_rows[0]["checkpoint_step"] == "1000"
    assert manifest_rows[0]["sample_index"] == "1"
    assert manifest_rows[0]["generated_path"] == (
        f"generated/{stable_generated_filename(1, records[0]['evaluation_id'])}"
    )
    with summary_path.open(encoding="utf-8") as handle:
        assert json.load(handle)["status"] == "complete"
    assert pages == [checkpoint_dir / "audit_pages" / "style_a.png"]
    with Image.open(pages[0]) as audit_page:
        assert audit_page.size == (8 * 96, 10 * 96 + 24)


def test_audit_page_requires_expected_records_per_style(tmp_path):
    dataset_root = tmp_path / "dataset"
    checkpoint_dir = tmp_path / "global_step_1000"
    records = _generated_records_and_images(dataset_root, checkpoint_dir, 1)
    generated_rows = build_generated_rows(records, checkpoint_dir / "generated", checkpoint_step=1000)

    with pytest.raises(ValueError, match="expected 20 records"):
        write_audit_pages(generated_rows, dataset_root, checkpoint_dir, checkpoint_dir / "audit")


def test_one_sample_style_audit_page_uses_the_standard_layout(tmp_path):
    dataset_root = tmp_path / "dataset"
    checkpoint_dir = tmp_path / "global_step_1000"
    records = _generated_records_and_images(dataset_root, checkpoint_dir, 1)
    generated_rows = build_generated_rows(records, checkpoint_dir / "generated", checkpoint_step=1000)

    write_audit_pages(
        generated_rows,
        dataset_root,
        checkpoint_dir,
        checkpoint_dir / "audit",
        samples_per_style=1,
    )

    assert (checkpoint_dir / "audit" / "style_a.png").is_file()


def test_audit_page_orders_each_style_by_numeric_sample_index(tmp_path):
    dataset_root = tmp_path / "dataset"
    checkpoint_dir = tmp_path / "global_step_1000"
    records = [_record("style_a", "first", 1), _record("style_a", "second", 2)]
    content_colors = [(11, 22, 33), (44, 55, 66)]
    for index, (record, content_color) in enumerate(zip(records, content_colors), start=1):
        record["content_path"] = f"test/ContentImage/{record['character']}.png"
        _image(dataset_root / record["content_path"], content_color)
        _image(dataset_root / record["reference_path"], (0, index, 0))
        _image(dataset_root / record["target_path"], (0, 0, index))
        _image(
            checkpoint_dir / "generated" / stable_generated_filename(index, record["evaluation_id"]),
            (index, index, 0),
        )
    generated_rows = build_generated_rows(records, checkpoint_dir / "generated", checkpoint_step=1000)

    pages = write_audit_pages(
        list(reversed(generated_rows)),
        dataset_root,
        checkpoint_dir,
        checkpoint_dir / "audit",
        tile_size=16,
        samples_per_style=2,
    )

    with Image.open(pages[0]) as audit_page:
        assert audit_page.getpixel((10, 24 + 10)) == content_colors[0]


def test_audit_page_rejects_generated_paths_that_escape_checkpoint_directory(tmp_path):
    dataset_root = tmp_path / "dataset"
    checkpoint_dir = tmp_path / "global_step_1000"
    records = _generated_records_and_images(dataset_root, checkpoint_dir, 1)
    generated_rows = build_generated_rows(records, checkpoint_dir / "generated", checkpoint_step=1000)
    generated_rows[0]["generated_path"] = "../outside.png"

    with pytest.raises(ValueError, match="escapes checkpoint directory"):
        write_audit_pages(
            generated_rows,
            dataset_root,
            checkpoint_dir,
            checkpoint_dir / "audit",
            samples_per_style=1,
        )


def test_validate_only_cli_writes_summary_without_gpu_or_official_fontdiffuser(tmp_path):
    dataset_root, manifest, checkpoint_root, output_root = _create_cli_fixture(tmp_path)
    result = _run_cli(dataset_root, manifest, checkpoint_root, output_root, "--validate-only")

    assert result.returncode == 0, result.stderr
    assert json.loads((output_root / "run_summary.json").read_text(encoding="utf-8")) == {
        "checkpoint_steps": [1000, 5000, 10000],
        "seed": 20260716,
        "selected_record_count": 2,
        "status": "validated",
        "style_count": 2,
    }
    assert all(
        not (output_root / f"global_step_{checkpoint_step}" / "generated").exists()
        for checkpoint_step in (1000, 5000, 10000)
    )


def test_validate_only_cli_accepts_custom_checkpoint_steps(tmp_path):
    checkpoint_steps = (10000, 20000, 30000, 40000, 50000)
    dataset_root, manifest, checkpoint_root, output_root = _create_cli_fixture(
        tmp_path, checkpoint_steps=checkpoint_steps
    )
    result = _run_cli(
        dataset_root,
        manifest,
        checkpoint_root,
        output_root,
        "--checkpoint-steps",
        *(str(checkpoint_step) for checkpoint_step in checkpoint_steps),
        "--validate-only",
    )

    assert result.returncode == 0, result.stderr
    summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "validated"
    assert summary["checkpoint_steps"] == list(checkpoint_steps)


def test_validate_only_cli_writes_failure_summary_for_invalid_checkpoint_steps(tmp_path):
    dataset_root, manifest, checkpoint_root, output_root = _create_cli_fixture(tmp_path)
    result = _run_cli(
        dataset_root,
        manifest,
        checkpoint_root,
        output_root,
        "--checkpoint-steps",
        "1000",
        "1000",
        "--validate-only",
    )

    assert result.returncode != 0
    summary_path = output_root / "run_summary.json"
    assert summary_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["checkpoint_step"] is None
    assert summary["evaluation_id"] is None
    assert summary["checkpoint_steps"] is None
    assert "checkpoint_steps must not contain duplicates" in summary["error"]


def test_validate_only_cli_preflights_checkpoints_before_selection_and_writes_failure_summary(
    tmp_path,
):
    dataset_root, manifest, checkpoint_root, output_root = _create_cli_fixture(tmp_path)
    (checkpoint_root / "global_step_1000" / REQUIRED_CHECKPOINT_FILES[-1]).unlink()
    result = _run_cli(
        dataset_root,
        manifest,
        checkpoint_root,
        output_root,
        "--limit-per-style",
        "-1",
        "--validate-only",
    )

    assert result.returncode != 0
    assert "missing checkpoint weight" in result.stderr
    summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["checkpoint_step"] is None
    assert summary["evaluation_id"] is None
    assert "missing checkpoint weight" in summary["error"]


def test_validate_only_cli_rejects_output_inside_checkpoint_root_without_summary(tmp_path):
    dataset_root, manifest, checkpoint_root, _ = _create_cli_fixture(tmp_path)
    output_root = checkpoint_root / "nested-audit-output"
    result = _run_cli(dataset_root, manifest, checkpoint_root, output_root, "--validate-only")

    assert result.returncode != 0
    assert not (output_root / "run_summary.json").exists()


def test_validate_only_cli_rejects_nonempty_checkpoint_audit_output_without_overwriting_it(tmp_path):
    dataset_root, manifest, checkpoint_root, output_root = _create_cli_fixture(tmp_path)
    old_image = output_root / "global_step_1000" / "generated" / "old.png"
    _image(old_image, (17, 18, 19))
    original_bytes = old_image.read_bytes()
    result = _run_cli(dataset_root, manifest, checkpoint_root, output_root, "--validate-only")

    assert result.returncode != 0
    assert "checkpoint audit output already exists" in result.stderr
    summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert "checkpoint audit output already exists" in summary["error"]
    assert old_image.read_bytes() == original_bytes


def test_validate_only_cli_rejects_existing_selected_custom_checkpoint_output_without_overwriting_it(
    tmp_path,
):
    checkpoint_steps = (10000, 20000, 30000, 40000, 50000)
    dataset_root, manifest, checkpoint_root, output_root = _create_cli_fixture(
        tmp_path, checkpoint_steps=checkpoint_steps
    )
    old_image = output_root / "global_step_20000" / "generated" / "old.png"
    _image(old_image, (17, 18, 19))
    original_bytes = old_image.read_bytes()
    result = _run_cli(
        dataset_root,
        manifest,
        checkpoint_root,
        output_root,
        "--checkpoint-steps",
        *(str(checkpoint_step) for checkpoint_step in checkpoint_steps),
        "--validate-only",
    )

    assert result.returncode != 0
    assert "checkpoint audit output already exists" in result.stderr
    summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["checkpoint_steps"] == list(checkpoint_steps)
    assert "checkpoint audit output already exists" in summary["error"]
    assert old_image.read_bytes() == original_bytes


def test_formal_audit_page_includes_exact_traceability_metadata_and_ascii_trace(tmp_path):
    dataset_root = tmp_path / "dataset"
    checkpoint_dir = tmp_path / "global_step_1000"
    records = _generated_records_and_images(dataset_root, checkpoint_dir, 20)
    records[0]["character"] = "甲A"
    records[0]["evaluation_id"] = "style_a+甲A"
    _image(dataset_root / records[0]["content_path"], (1, 0, 0))
    _image(dataset_root / records[0]["reference_path"], (0, 1, 0))
    _image(dataset_root / records[0]["target_path"], (0, 0, 1))
    _image(
        checkpoint_dir / "generated" / stable_generated_filename(1, records[0]["evaluation_id"]),
        (1, 1, 0),
    )
    generated_rows = build_generated_rows(records, checkpoint_dir / "generated", checkpoint_step=1000)

    page = write_audit_pages(
        generated_rows,
        dataset_root,
        checkpoint_dir,
        checkpoint_dir / "audit_pages",
        samples_per_style=20,
    )[0]

    from target_glyph_generation import p1_visual_audit

    with Image.open(page) as audit_page:
        metadata = json.loads(audit_page.text["p1_visual_audit"])
    assert p1_visual_audit.ascii_character_trace("1", "甲A") == "001 U+7532 A"
    assert metadata["style_id"] == "style_a"
    assert metadata["rows"][0] == {
        "style_id": "style_a",
        "character": "甲A",
        "evaluation_id": "style_a+甲A",
        "sample_index": "1",
    }


def _load_audit_cli_module(monkeypatch):
    module_name = "p1_visual_audit_cli_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def test_resolve_checkpoint_steps_defaults_to_the_original_three_steps(monkeypatch):
    script = _load_audit_cli_module(monkeypatch)

    assert script.resolve_checkpoint_steps(None) == (1000, 5000, 10000)


@pytest.mark.parametrize("raw_steps", [[], [1000, 1000], [0], [-1]])
def test_resolve_checkpoint_steps_rejects_empty_duplicate_or_nonpositive_values(monkeypatch, raw_steps):
    script = _load_audit_cli_module(monkeypatch)

    with pytest.raises(ValueError):
        script.resolve_checkpoint_steps(raw_steps)


def _install_fake_fontdiffuser_config(monkeypatch):
    parser_calls: list[list[str]] = []
    configs_module = ModuleType("configs")
    configs_module.__path__ = []
    fontdiffuser_module = ModuleType("configs.fontdiffuser")

    class FakeParser:
        def parse_args(self, arguments):
            parser_calls.append(arguments)
            return SimpleNamespace()

    fontdiffuser_module.get_parser = lambda: FakeParser()
    configs_module.fontdiffuser = fontdiffuser_module
    monkeypatch.setitem(sys.modules, "configs", configs_module)
    monkeypatch.setitem(sys.modules, "configs.fontdiffuser", fontdiffuser_module)
    return parser_calls


def test_build_sampling_args_uses_fixed_p1_inference_settings_without_official_repo(monkeypatch, tmp_path):
    script = _load_audit_cli_module(monkeypatch)
    parser_calls = _install_fake_fontdiffuser_config(monkeypatch)

    config = script.build_sampling_args(tmp_path, tmp_path / "global_step_1000", "cuda:7", 101)

    assert parser_calls == [[]]
    assert config.ckpt_dir == str(tmp_path / "global_step_1000")
    assert config.device == "cuda:7"
    assert config.seed == 101
    assert config.demo is False
    assert config.character_input is False
    assert config.resolution == 96
    assert config.style_image_size == (96, 96)
    assert config.content_image_size == (96, 96)
    assert config.content_encoder_downsample_size == 3
    assert config.algorithm_type == "dpmsolver++"
    assert config.guidance_type == "classifier-free"
    assert config.guidance_scale == 7.5
    assert config.num_inference_steps == 20
    assert config.order == 2
    assert config.skip_type == "time_uniform"
    assert config.method == "multistep"
    assert config.correcting_x0_fn is None
    assert config.t_start is None
    assert config.t_end is None


def test_run_sampling_runtime_seam_uses_one_pipeline_per_checkpoint_without_cuda(
    monkeypatch, tmp_path
):
    script = _load_audit_cli_module(monkeypatch)
    _install_fake_fontdiffuser_config(monkeypatch)
    pipeline_loads: list[object] = []
    cache_calls: list[None] = []
    fake_torch = ModuleType("torch")
    fake_torch.cuda = SimpleNamespace(empty_cache=lambda: cache_calls.append(None))
    fake_sample = ModuleType("sample")
    fake_sample.image_process = object()
    fake_sample.load_fontdiffuer_pipeline = lambda args: pipeline_loads.append(args) or object()
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "sample", fake_sample)
    monkeypatch.setattr(script, "generate_one", lambda *args: Image.new("RGB", (8, 8), "yellow"))

    dataset_root = tmp_path / "dataset"
    record = _record("style_a", "char_a", 1)
    for field, color in (
        ("content_path", (1, 0, 0)),
        ("reference_path", (0, 1, 0)),
        ("target_path", (0, 0, 1)),
    ):
        _image(dataset_root / record[field], color)
    manifest = tmp_path / "visual_test_manifest.csv"
    _write_manifest(manifest, [record])

    checkpoint_root = tmp_path / "checkpoints"
    checkpoint_directories = []
    for checkpoint_step in (1000, 5000, 10000):
        checkpoint_dir = checkpoint_root / f"global_step_{checkpoint_step}"
        checkpoint_dir.mkdir(parents=True)
        for filename in REQUIRED_CHECKPOINT_FILES:
            (checkpoint_dir / filename).write_bytes(b"weight")
        checkpoint_directories.append((checkpoint_step, checkpoint_dir))
    official_root = tmp_path / "official"
    (official_root / "sample.py").parent.mkdir(parents=True)
    (official_root / "sample.py").write_text("", encoding="utf-8")
    output_root = tmp_path / "audit_output"
    arguments = SimpleNamespace(
        dataset_root=dataset_root,
        visual_manifest=manifest,
        checkpoint_root=checkpoint_root,
        output_root=output_root,
        fontdiffuser_root=official_root,
        device="cuda:0",
        expected_record_count=1,
        expected_style_count=1,
        limit_per_style=1,
        seed=20260716,
        checkpoint_steps=None,
        validate_only=False,
    )
    monkeypatch.setattr(script, "parse_args", lambda: arguments)

    script.main()

    summary = json.loads((output_root / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "complete"
    assert len(summary["checkpoints"]) == 3
    assert len(pipeline_loads) == 3
    assert len(cache_calls) == 3
    for checkpoint_step, _ in checkpoint_directories:
        checkpoint_output = output_root / f"global_step_{checkpoint_step}"
        assert (checkpoint_output / "generated_manifest.csv").is_file()
        assert (checkpoint_output / "audit_pages" / "style_a.png").is_file()
