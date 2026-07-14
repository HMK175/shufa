import importlib.util
import json
from pathlib import Path

from target_glyph_generation.external_dataset_discovery import ImageRecord


def _record(tmp_path: Path, index: int) -> ImageRecord:
    return ImageRecord(
        dataset_id="calligrapher20",
        style_id="wxz",
        style_display_name="Wang Xizhi",
        source_split="train",
        raw_filename=f"{index}.jpg",
        raw_index=str(index),
        image_path=tmp_path / f"{index}.jpg",
    )


def test_ocr_runtime_reports_completed_batches_via_optional_progress_callback(monkeypatch, tmp_path: Path):
    from target_glyph_generation import ocr_runtime

    records = [_record(tmp_path, index) for index in range(1, 6)]
    progress = []

    class TextRecognition:
        def __init__(self, *, model_name):
            assert model_name == "test-model"

        def predict(self, paths, *, batch_size):
            return [{"rec_text": Path(path).stem, "rec_score": 0.95} for path in paths]

    monkeypatch.setattr(ocr_runtime, "_load_text_recognition", lambda: TextRecognition)

    predictions = ocr_runtime.run_local_ocr(
        records,
        model_name="test-model",
        batch_size=2,
        progress_callback=lambda completed, total: progress.append((completed, total)),
    )

    assert predictions == [(str(index), 0.95) for index in range(1, 6)]
    assert progress == [(2, 5), (4, 5), (5, 5)]


def test_calligrapher_audit_progress_uses_machine_readable_flushed_json(capsys):
    project_dir = Path(__file__).resolve().parents[1]
    script_path = project_dir / "scripts" / "audit_calligrapher8_ocr.py"
    spec = importlib.util.spec_from_file_location("test_calligrapher_progress", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module._emit_ocr_progress(250, 50310)

    assert json.loads(capsys.readouterr().out) == {
        "ocr_progress": {"completed": 250, "total": 50310}
    }
