import builtins
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

from target_glyph_generation.external_dataset_discovery import ImageRecord


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_DIR / "scripts"


def _load_script(filename: str):
    module_name = f"test_{filename.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _image_record(tmp_path: Path, style_id: str, raw_filename: str = "7.jpg") -> ImageRecord:
    return ImageRecord(
        dataset_id="chinese_style" if style_id in {"lishu", "xingkai"} else "calligrapher20",
        style_id=style_id,
        style_display_name=style_id,
        source_split="train",
        raw_filename=raw_filename,
        raw_index=raw_filename.removesuffix(".jpg").removeprefix(f"{style_id}_"),
        image_path=tmp_path / style_id / raw_filename,
    )


def _patch_audit_steps(monkeypatch, module, expected_records, final_labels, expected_arguments):
    captured = {}

    def run_local_ocr(records, **kwargs):
        captured["ocr_records"] = list(records)
        captured["ocr_kwargs"] = kwargs
        return [("山", 0.99) for _ in captured["ocr_records"]]

    def build_label_records(records, predictions):
        captured["label_records"] = list(records)
        captured["predictions"] = predictions
        return final_labels

    def apply_manual_overrides(labels, overrides):
        captured["override_labels"] = labels
        captured["overrides"] = overrides
        return final_labels

    def fingerprint(records):
        captured["fingerprint_records"] = list(records)
        return "dataset-fingerprint"

    def write_outputs(labels, output_dir, allowed_characters, model_name, dataset_fingerprint, **kwargs):
        captured["write"] = {
            "labels": labels,
            "output_dir": output_dir,
            "allowed_characters": allowed_characters,
            "model_name": model_name,
            "dataset_fingerprint": dataset_fingerprint,
            **kwargs,
        }
        return {"label_count": len(labels), "required_review_count": 1}

    def select_sample(labels, **kwargs):
        captured["sample"] = {"labels": labels, **kwargs}
        return [final_labels[0], final_labels[-1]]

    def create_pages(labels, output_dir):
        captured["pages"] = {"labels": labels, "output_dir": output_dir}
        return [output_dir / "review_page_001.png"]

    monkeypatch.setattr(module, "run_local_ocr", run_local_ocr)
    monkeypatch.setattr(module, "build_label_records", build_label_records)
    monkeypatch.setattr(module, "apply_manual_overrides", apply_manual_overrides)
    monkeypatch.setattr(module, "dataset_fingerprint", fingerprint)
    monkeypatch.setattr(module, "write_audit_outputs", write_outputs)
    monkeypatch.setattr(module, "select_review_sample", select_sample)
    monkeypatch.setattr(module, "create_review_pages", create_pages)
    monkeypatch.setattr(module, "load_characters", lambda path: expected_arguments["characters"])
    monkeypatch.setattr(
        module,
        "load_manual_overrides",
        lambda path: expected_arguments["overrides"],
    )
    return captured


def test_chinese_style_cli_uses_independent_records_and_forwards_all_arguments(
    monkeypatch, tmp_path: Path, capsys
):
    module = _load_script("audit_chinese_style_ocr.py")
    records = [
        _image_record(tmp_path, "lishu", "lishu_7.jpg"),
        _image_record(tmp_path, "xingkai", "xingkai_7.jpg"),
        ImageRecord(
            dataset_id="chinese_style",
            style_id="lishu",
            style_display_name="lishu",
            source_split="test",
            raw_filename="lishu_8.jpg",
            raw_index="8",
            image_path=tmp_path / "lishu" / "lishu_8.jpg",
        ),
        ImageRecord(
            dataset_id="chinese_style",
            style_id="xingkai",
            style_display_name="xingkai",
            source_split="test",
            raw_filename="xingkai_8.jpg",
            raw_index="8",
            image_path=tmp_path / "xingkai" / "xingkai_8.jpg",
        ),
    ]
    required = SimpleNamespace(key=records[0].key, review_state="required_review")
    provisional = SimpleNamespace(key=records[1].key, review_state="provisional")
    expected = {"characters": ["山", "水"], "overrides": {records[0].key: {"decision": "reject"}}}
    captured = _patch_audit_steps(monkeypatch, module, records, [required, provisional], expected)
    monkeypatch.setattr(module, "discover_chinese_style_images", lambda root: records)
    for source_split in ("train", "test"):
        for style_id in ("lishu", "xingkai"):
            (tmp_path / "dataset" / source_split / style_id).mkdir(parents=True)
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_chinese_style_ocr.py",
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--output-dir",
            str(output_dir),
            "--characters",
            str(tmp_path / "characters.txt"),
            "--overrides",
            str(tmp_path / "overrides.csv"),
            "--model-name",
            "test-model",
            "--batch-size",
            "3",
            "--review-per-style",
            "4",
        ],
    )

    module.main()

    assert captured["ocr_records"] == records
    assert [(record.style_id, record.raw_index) for record in captured["ocr_records"]] == [
        ("lishu", "7"),
        ("xingkai", "7"),
        ("lishu", "8"),
        ("xingkai", "8"),
    ]
    assert captured["ocr_kwargs"] == {"model_name": "test-model", "batch_size": 3}
    assert captured["label_records"] == records
    assert captured["write"] == {
        "labels": [required, provisional],
        "output_dir": output_dir,
        "allowed_characters": {"山", "水"},
        "model_name": "test-model",
        "dataset_fingerprint": "dataset-fingerprint",
        "review_per_style": 4,
    }
    assert captured["pages"] == {
        "labels": [required, provisional],
        "output_dir": output_dir / "review_pages",
    }
    assert json.loads(capsys.readouterr().out) == {
        "label_count": 2,
        "required_review_count": 1,
        "review_page_count": 1,
    }


def test_calligrapher_cli_uses_only_configured_sources_and_forwards_all_arguments(
    monkeypatch, tmp_path: Path, capsys
):
    module = _load_script("audit_calligrapher8_ocr.py")
    records = [
        _image_record(tmp_path, "wxz", "7.jpg"),
        ImageRecord(
            dataset_id="calligrapher20",
            style_id="wxz",
            style_display_name="wxz",
            source_split="test",
            raw_filename="8.jpg",
            raw_index="8",
            image_path=tmp_path / "wxz" / "8.jpg",
        ),
    ]
    required = SimpleNamespace(key=records[0].key, review_state="required_review")
    expected = {"characters": ["山"], "overrides": {records[0].key: {"decision": "reject"}}}
    captured = _patch_audit_steps(monkeypatch, module, records, [required], expected)
    source_config = tmp_path / "sources.yaml"
    source_config.write_text(
        "sources:\n  wxz:\n    display_name: 王羲之\n    expected_total: 2\n",
        encoding="utf-8",
    )
    for source_split in ("train", "test"):
        (tmp_path / "dataset" / source_split / "wxz").mkdir(parents=True)

    def discover(root, sources):
        captured["discovery"] = {"root": root, "sources": sources}
        return records

    monkeypatch.setattr(module, "discover_calligrapher_images", discover)
    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_calligrapher8_ocr.py",
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--sources",
            str(source_config),
            "--output-dir",
            str(output_dir),
            "--characters",
            str(tmp_path / "characters.txt"),
            "--overrides",
            str(tmp_path / "overrides.csv"),
            "--model-name",
            "test-model",
            "--batch-size",
            "5",
            "--review-per-style",
            "6",
        ],
    )

    module.main()

    assert captured["discovery"] == {
        "root": tmp_path / "dataset",
        "sources": {"wxz": {"display_name": "王羲之", "expected_total": 2}},
    }
    assert captured["ocr_records"] == records
    assert {record.style_id for record in captured["ocr_records"]} == {"wxz"}
    assert captured["ocr_kwargs"] == {"model_name": "test-model", "batch_size": 5}
    assert captured["write"]["review_per_style"] == 6
    assert captured["pages"] == {"labels": [required], "output_dir": output_dir / "review_pages"}
    assert json.loads(capsys.readouterr().out) == {
        "label_count": 1,
        "required_review_count": 1,
        "review_page_count": 1,
    }


def test_calligrapher_cli_ignores_unselected_writer_directories_after_real_discovery(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_calligrapher8_ocr.py")
    dataset_root = tmp_path / "dataset"
    for source_split, filename in (("train", "1.jpg"), ("test", "2.jpg")):
        selected_path = dataset_root / source_split / "wxz" / filename
        selected_path.parent.mkdir(parents=True)
        selected_path.write_bytes(b"image")
        unselected_path = dataset_root / source_split / "bdsr" / filename
        unselected_path.parent.mkdir(parents=True)
        unselected_path.write_bytes(b"image")
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        "sources:\n  wxz:\n    display_name: Wang Xizhi\n    expected_total: 2\n",
        encoding="utf-8",
    )
    final_label = SimpleNamespace(key=("label",), review_state="provisional")
    captured = _patch_audit_steps(
        monkeypatch,
        module,
        [],
        [final_label],
        {"characters": ["山"], "overrides": {}},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_calligrapher8_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--sources",
            str(sources_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(tmp_path / "characters.txt"),
        ],
    )

    module.main()

    assert {(record.style_id, record.source_split) for record in captured["ocr_records"]} == {
        ("wxz", "train"),
        ("wxz", "test"),
    }
    assert all("bdsr" not in record.image_path.parts for record in captured["ocr_records"])


def test_load_manual_overrides_requires_the_template_header_and_validates_rows(tmp_path: Path):
    from target_glyph_generation.single_image_ocr import load_manual_overrides

    valid = tmp_path / "valid.csv"
    valid.write_text(
        "dataset_id,style_id,source_split,raw_filename,manual_character,decision,note\n"
        "\n"
        "calligrapher20,wxz,train,7.jpg,山,accept,confirmed\n",
        encoding="utf-8",
    )

    assert load_manual_overrides(valid) == {
        ("calligrapher20", "wxz", "train", "7.jpg"): {
            "manual_character": "山",
            "decision": "accept",
            "note": "confirmed",
        }
    }

    missing_column = tmp_path / "missing.csv"
    missing_column.write_text("dataset_id,style_id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        load_manual_overrides(missing_column)

    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text(
        "dataset_id,style_id,source_split,raw_filename,manual_character,decision,note\n"
        "calligrapher20,wxz,train,7.jpg,,reject,\n"
        "calligrapher20,wxz,train,7.jpg,,reject,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_manual_overrides(duplicate)

    invalid_decision = tmp_path / "invalid.csv"
    invalid_decision.write_text(
        "dataset_id,style_id,source_split,raw_filename,manual_character,decision,note\n"
        "calligrapher20,wxz,train,7.jpg,山,defer,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="decision"):
        load_manual_overrides(invalid_decision)


def test_ocr_runtime_imports_paddle_lazily(monkeypatch):
    module_name = "target_glyph_generation.ocr_runtime"
    sys.modules.pop(module_name, None)
    original_import = builtins.__import__

    def reject_paddle_import(name, *args, **kwargs):
        if name == "paddleocr":
            raise AssertionError("PaddleOCR must not import with the runtime module")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_paddle_import)
    module = importlib.import_module(module_name)

    assert hasattr(module, "run_local_ocr")


def test_ocr_runtime_batches_records_preserves_order_and_sets_model_source(monkeypatch, tmp_path: Path):
    from target_glyph_generation import ocr_runtime

    records = [_image_record(tmp_path, "wxz", f"{index}.jpg") for index in range(5)]
    calls = []

    class TextRecognition:
        def __init__(self, *, model_name):
            assert model_name == "test-model"

        def predict(self, paths, *, batch_size):
            calls.append((paths, batch_size))
            return [{"rec_text": Path(path).stem, "rec_score": "0.90"} for path in paths]

    monkeypatch.delenv("PADDLE_PDX_MODEL_SOURCE", raising=False)
    monkeypatch.setattr(ocr_runtime, "_load_text_recognition", lambda: TextRecognition)

    result = ocr_runtime.run_local_ocr(iter(records), model_name="test-model", batch_size=2)

    assert result == [(str(index), 0.90) for index in range(5)]
    assert calls == [
        ([str(record.image_path) for record in records[:2]], 2),
        ([str(record.image_path) for record in records[2:4]], 2),
        ([str(record.image_path) for record in records[4:]], 2),
    ]
    assert os.environ["PADDLE_PDX_MODEL_SOURCE"] == "BOS"


@pytest.mark.parametrize("batch_size", [0, -1, True, 1.5])
def test_ocr_runtime_rejects_invalid_batch_size(batch_size):
    from target_glyph_generation.ocr_runtime import run_local_ocr

    with pytest.raises(ValueError, match="batch_size"):
        run_local_ocr([], batch_size=batch_size)


def test_ocr_runtime_rejects_batch_result_count_mismatch(monkeypatch, tmp_path: Path):
    from target_glyph_generation import ocr_runtime

    class TextRecognition:
        def __init__(self, *, model_name):
            pass

        def predict(self, paths, *, batch_size):
            return []

    monkeypatch.setattr(ocr_runtime, "_load_text_recognition", lambda: TextRecognition)

    with pytest.raises(ValueError, match="exactly one"):
        ocr_runtime.run_local_ocr([_image_record(tmp_path, "wxz")], batch_size=1)


@pytest.mark.parametrize(
    ("script_name", "discovery_name", "source_arguments"),
    [
        ("audit_chinese_style_ocr.py", "discover_chinese_style_images", []),
        (
            "audit_calligrapher8_ocr.py",
            "discover_calligrapher_images",
            ["--sources", "unused-sources.yaml"],
        ),
    ],
)
@pytest.mark.parametrize("review_per_style", ["0", "-1"])
def test_audit_clis_reject_invalid_review_cap_before_discovery_or_inference(
    monkeypatch,
    tmp_path: Path,
    script_name: str,
    discovery_name: str,
    source_arguments: list[str],
    review_per_style: str,
):
    module = _load_script(script_name)
    calls = []
    monkeypatch.setattr(module, discovery_name, lambda *args: calls.append("discovery"))
    monkeypatch.setattr(module, "run_local_ocr", lambda *args, **kwargs: calls.append("ocr"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            script_name,
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(tmp_path / "missing-characters.txt"),
            "--review-per-style",
            review_per_style,
            *source_arguments,
        ],
    )

    with pytest.raises(SystemExit):
        module.main()

    assert calls == []


@pytest.mark.parametrize(
    ("script_name", "discovery_name", "source_arguments"),
    [
        ("audit_chinese_style_ocr.py", "discover_chinese_style_images", []),
        (
            "audit_calligrapher8_ocr.py",
            "discover_calligrapher_images",
            ["--sources", "unused-sources.yaml"],
        ),
    ],
)
@pytest.mark.parametrize(
    ("characters_path_kind", "expected_exception"),
    [("missing", FileNotFoundError), ("directory", OSError)],
)
def test_audit_clis_reject_missing_or_unreadable_characters_before_discovery_or_inference(
    monkeypatch,
    tmp_path: Path,
    script_name: str,
    discovery_name: str,
    source_arguments: list[str],
    characters_path_kind: str,
    expected_exception: type[OSError],
):
    module = _load_script(script_name)
    calls = []
    characters_path = tmp_path / "characters.txt"
    if characters_path_kind == "directory":
        characters_path.mkdir()
    monkeypatch.setattr(module, discovery_name, lambda *args: calls.append("discovery"))
    monkeypatch.setattr(module, "run_local_ocr", lambda *args, **kwargs: calls.append("ocr"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            script_name,
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
            *source_arguments,
        ],
    )

    with pytest.raises(expected_exception):
        module.main()

    assert calls == []


@pytest.mark.parametrize(
    ("script_name", "discovery_name", "source_arguments"),
    [
        ("audit_chinese_style_ocr.py", "discover_chinese_style_images", []),
        (
            "audit_calligrapher8_ocr.py",
            "discover_calligrapher_images",
            ["--sources", "unused-sources.yaml"],
        ),
    ],
)
@pytest.mark.parametrize(
    ("overrides_text", "error_pattern"),
    [
        ("dataset_id,style_id\n", "header"),
        (
            "dataset_id,style_id,source_split,raw_filename,manual_character,decision,note\n"
            "calligrapher20,wxz,train,7.jpg,,defer,\n",
            "decision",
        ),
    ],
)
def test_audit_clis_reject_malformed_or_invalid_overrides_before_discovery_or_inference(
    monkeypatch,
    tmp_path: Path,
    script_name: str,
    discovery_name: str,
    source_arguments: list[str],
    overrides_text: str,
    error_pattern: str,
):
    module = _load_script(script_name)
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("X\n", encoding="utf-8")
    overrides_path = tmp_path / "overrides.csv"
    overrides_path.write_text(overrides_text, encoding="utf-8")
    calls = []
    monkeypatch.setattr(module, discovery_name, lambda *args: calls.append("discovery"))
    monkeypatch.setattr(module, "run_local_ocr", lambda *args, **kwargs: calls.append("ocr"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            script_name,
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
            "--overrides",
            str(overrides_path),
            *source_arguments,
        ],
    )

    with pytest.raises(ValueError, match=error_pattern):
        module.main()

    assert calls == []


@pytest.mark.parametrize(
    ("script_name", "discovery_name", "source_arguments"),
    [
        ("audit_chinese_style_ocr.py", "discover_chinese_style_images", []),
        (
            "audit_calligrapher8_ocr.py",
            "discover_calligrapher_images",
            ["--sources", "unused-sources.yaml"],
        ),
    ],
)
def test_audit_clis_reject_blank_model_name_before_discovery_or_inference(
    monkeypatch, tmp_path: Path, script_name: str, discovery_name: str, source_arguments: list[str]
):
    module = _load_script(script_name)
    calls = []
    monkeypatch.setattr(module, discovery_name, lambda *args: calls.append("discovery"))
    monkeypatch.setattr(module, "run_local_ocr", lambda *args, **kwargs: calls.append("ocr"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            script_name,
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(tmp_path / "missing-characters.txt"),
            "--model-name",
            "   ",
            *source_arguments,
        ],
    )

    with pytest.raises(SystemExit):
        module.main()

    assert calls == []


@pytest.mark.parametrize(
    ("script_name", "discovery_name", "style_id", "requires_sources"),
    [
        (
            "audit_chinese_style_ocr.py",
            "discover_chinese_style_images",
            "lishu",
            False,
        ),
        (
            "audit_calligrapher8_ocr.py",
            "discover_calligrapher_images",
            "wxz",
            True,
        ),
    ],
)
def test_audit_clis_reject_unknown_override_keys_after_discovery_before_inference(
    monkeypatch,
    tmp_path: Path,
    script_name: str,
    discovery_name: str,
    style_id: str,
    requires_sources: bool,
):
    module = _load_script(script_name)
    records = [_image_record(tmp_path, style_id)]
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    overrides_path = tmp_path / "overrides.csv"
    overrides_path.write_text(
        "dataset_id,style_id,source_split,raw_filename,manual_character,decision,note\n"
        "unknown_dataset,unknown_style,train,missing.jpg,山,accept,\n",
        encoding="utf-8",
    )
    source_arguments = []
    if requires_sources:
        sources_path = tmp_path / "sources.yaml"
        sources_path.write_text("sources:\n  wxz: {}\n", encoding="utf-8")
        source_arguments = ["--sources", str(sources_path)]

    calls = []
    monkeypatch.setattr(
        module,
        discovery_name,
        lambda *args: calls.append("discovery") or records,
    )
    if script_name == "audit_chinese_style_ocr.py":
        monkeypatch.setattr(module, "validate_chinese_style_audit_inventory", lambda root, records: None)
    else:
        monkeypatch.setattr(
            module,
            "validate_calligrapher_audit_inventory",
            lambda root, records, sources: None,
        )
    monkeypatch.setattr(module, "run_local_ocr", lambda *args, **kwargs: calls.append("ocr"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            script_name,
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
            "--overrides",
            str(overrides_path),
            *source_arguments,
        ],
    )

    with pytest.raises(ValueError, match="override key"):
        module.main()

    assert calls == ["discovery"]


def test_chinese_style_cli_rejects_missing_required_directory_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_chinese_style_ocr.py")
    dataset_root = tmp_path / "dataset"
    for split, style_id in [("train", "lishu"), ("train", "xingkai"), ("test", "lishu")]:
        (dataset_root / split / style_id).mkdir(parents=True)
    records = [
        _image_record(tmp_path, "lishu", "lishu_7.jpg"),
        _image_record(tmp_path, "xingkai", "xingkai_7.jpg"),
    ]
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    ocr_calls = []

    monkeypatch.setattr(module, "discover_chinese_style_images", lambda root: records)

    def reject_ocr(*args, **kwargs):
        ocr_calls.append("ocr")
        raise AssertionError("OCR runtime must not be called for an incomplete inventory")

    monkeypatch.setattr(module, "run_local_ocr", reject_ocr)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_chinese_style_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(ValueError, match=r"test/xingkai"):
        module.main()

    assert ocr_calls == []


def test_chinese_style_cli_rejects_style_without_discovered_records_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_chinese_style_ocr.py")
    dataset_root = tmp_path / "dataset"
    for split in ("train", "test"):
        for style_id in ("lishu", "xingkai"):
            (dataset_root / split / style_id).mkdir(parents=True)
    records = [_image_record(tmp_path, "lishu", "lishu_7.jpg")]
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    ocr_calls = []

    monkeypatch.setattr(module, "discover_chinese_style_images", lambda root: records)

    def reject_ocr(*args, **kwargs):
        ocr_calls.append("ocr")
        raise AssertionError("OCR runtime must not be called for an incomplete inventory")

    monkeypatch.setattr(module, "run_local_ocr", reject_ocr)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_chinese_style_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(ValueError, match=r"missing records.*xingkai"):
        module.main()

    assert ocr_calls == []


def test_calligrapher_cli_rejects_missing_writer_directory_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_calligrapher8_ocr.py")
    dataset_root = tmp_path / "dataset"
    (dataset_root / "train" / "wxz").mkdir(parents=True)
    records = [_image_record(tmp_path, "wxz", "7.jpg")]
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        "sources:\n  wxz:\n    display_name: Wang Xizhi\n    expected_total: 1\n",
        encoding="utf-8",
    )
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    ocr_calls = []

    monkeypatch.setattr(module, "discover_calligrapher_images", lambda root, sources: records)

    def reject_ocr(*args, **kwargs):
        ocr_calls.append("ocr")
        raise AssertionError("OCR runtime must not be called for an incomplete inventory")

    monkeypatch.setattr(module, "run_local_ocr", reject_ocr)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_calligrapher8_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--sources",
            str(sources_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(ValueError, match=r"missing directories.*test/wxz"):
        module.main()

    assert ocr_calls == []


def test_calligrapher_cli_rejects_writer_total_mismatch_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_calligrapher8_ocr.py")
    dataset_root = tmp_path / "dataset"
    for split in ("train", "test"):
        (dataset_root / split / "wxz").mkdir(parents=True)
    records = [
        _image_record(tmp_path, "wxz", "7.jpg"),
        ImageRecord(
            dataset_id="calligrapher20",
            style_id="wxz",
            style_display_name="wxz",
            source_split="test",
            raw_filename="8.jpg",
            raw_index="8",
            image_path=tmp_path / "wxz" / "8.jpg",
        ),
    ]
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        "sources:\n  wxz:\n    display_name: Wang Xizhi\n    expected_total: 3\n",
        encoding="utf-8",
    )
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    ocr_calls = []

    monkeypatch.setattr(module, "discover_calligrapher_images", lambda root, sources: records)

    def reject_ocr(*args, **kwargs):
        ocr_calls.append("ocr")
        raise AssertionError("OCR runtime must not be called for an incomplete inventory")

    monkeypatch.setattr(module, "run_local_ocr", reject_ocr)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_calligrapher8_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--sources",
            str(sources_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(
        ValueError, match=r"writer image totals.*wxz.*expected 3.*discovered 2"
    ):
        module.main()

    assert ocr_calls == []


def test_chinese_style_cli_rejects_empty_required_test_split_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_chinese_style_ocr.py")
    dataset_root = tmp_path / "dataset"
    for source_split in ("train", "test"):
        for style_id in ("lishu", "xingkai"):
            (dataset_root / source_split / style_id).mkdir(parents=True)
    records = [
        _image_record(tmp_path, "lishu", "lishu_7.jpg"),
        _image_record(tmp_path, "xingkai", "xingkai_7.jpg"),
        ImageRecord(
            dataset_id="chinese_style",
            style_id="lishu",
            style_display_name="lishu",
            source_split="test",
            raw_filename="lishu_8.jpg",
            raw_index="8",
            image_path=tmp_path / "lishu" / "lishu_8.jpg",
        ),
    ]
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    ocr_calls = []

    monkeypatch.setattr(module, "discover_chinese_style_images", lambda root: records)

    def reject_ocr(*args, **kwargs):
        ocr_calls.append("ocr")
        raise AssertionError("OCR runtime must not be called for an incomplete inventory")

    monkeypatch.setattr(module, "run_local_ocr", reject_ocr)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_chinese_style_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(ValueError, match=r"test/xingkai: discovered 0"):
        module.main()

    assert ocr_calls == []


def test_calligrapher_cli_rejects_empty_required_test_writer_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_calligrapher8_ocr.py")
    dataset_root = tmp_path / "dataset"
    for source_split in ("train", "test"):
        (dataset_root / source_split / "wxz").mkdir(parents=True)
    records = [
        _image_record(tmp_path, "wxz", "7.jpg"),
        _image_record(tmp_path, "wxz", "8.jpg"),
    ]
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        "sources:\n  wxz:\n    display_name: Wang Xizhi\n    expected_total: 2\n",
        encoding="utf-8",
    )
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    ocr_calls = []

    monkeypatch.setattr(module, "discover_calligrapher_images", lambda root, sources: records)

    def reject_ocr(*args, **kwargs):
        ocr_calls.append("ocr")
        raise AssertionError("OCR runtime must not be called for an incomplete inventory")

    monkeypatch.setattr(module, "run_local_ocr", reject_ocr)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_calligrapher8_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--sources",
            str(sources_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(ValueError, match=r"test/wxz: discovered 0"):
        module.main()

    assert ocr_calls == []


def test_calligrapher_cli_rejects_malformed_sources_yaml_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_calligrapher8_ocr.py")
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text("sources: [\n", encoding="utf-8")
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(
        module,
        "discover_calligrapher_images",
        lambda root, sources: calls.append("discovery"),
    )
    monkeypatch.setattr(module, "run_local_ocr", lambda *args, **kwargs: calls.append("ocr"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_calligrapher8_ocr.py",
            "--dataset-root",
            str(tmp_path / "dataset"),
            "--sources",
            str(sources_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(ValueError, match=re.escape(str(sources_path))):
        module.main()

    assert calls == []


def test_calligrapher_cli_rejects_invalid_expected_total_before_ocr(
    monkeypatch, tmp_path: Path
):
    module = _load_script("audit_calligrapher8_ocr.py")
    dataset_root = tmp_path / "dataset"
    for source_split in ("train", "test"):
        (dataset_root / source_split / "wxz").mkdir(parents=True)
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(
        "sources:\n  wxz:\n    display_name: Wang Xizhi\n    expected_total: 0\n",
        encoding="utf-8",
    )
    characters_path = tmp_path / "characters.txt"
    characters_path.write_text("山\n", encoding="utf-8")
    records = [_image_record(tmp_path, "wxz", "7.jpg")]
    calls = []

    monkeypatch.setattr(
        module,
        "discover_calligrapher_images",
        lambda root, sources: calls.append("discovery") or records,
    )
    monkeypatch.setattr(module, "run_local_ocr", lambda *args, **kwargs: calls.append("ocr"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_calligrapher8_ocr.py",
            "--dataset-root",
            str(dataset_root),
            "--sources",
            str(sources_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--characters",
            str(characters_path),
        ],
    )

    with pytest.raises(ValueError, match=r"expected_total"):
        module.main()

    assert calls == ["discovery"]
