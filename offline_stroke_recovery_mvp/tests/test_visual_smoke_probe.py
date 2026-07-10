from pathlib import Path
import importlib.util
import json

from PIL import Image, ImageDraw


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "visual_smoke_probe.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("visual_smoke_probe", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_simple_glyph(path: Path) -> None:
    image = Image.new("L", (48, 48), 255)
    draw = ImageDraw.Draw(image)
    draw.line((8, 24, 40, 24), fill=0, width=4)
    image.save(path)


def test_build_arg_parser_uses_visual_smoke_defaults():
    module = _load_module()

    args = module.build_arg_parser().parse_args([])

    assert args.input_dir == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "visual_smoke_probe_after_review"
        / "inputs"
    )
    assert args.output_dir == (
        Path("offline_stroke_recovery_mvp")
        / "outputs"
        / "visual_smoke_probe_rerun"
    )
    assert args.threshold == 180
    assert args.min_component_pixels == 6
    assert args.spur_max_length == 1
    assert args.ordering_endpoint_merge_distance == 1.0
    assert args.ordering_direction_cos_threshold == 0.65
    assert args.require_skeleton_backend is None


def test_run_visual_smoke_probe_reports_missing_input_dir(tmp_path: Path):
    module = _load_module()

    payload = module.run_visual_smoke_probe(
        input_dir=tmp_path / "missing_inputs",
        output_root=tmp_path / "outputs",
        threshold=180,
        crop_pad=2,
        min_component_pixels=6,
        spur_max_length=1,
        min_segment_pixels=2,
    )

    assert payload["status"] == "missing_input_dir"
    assert payload["stage"] == "visual_smoke_probe"


def test_run_visual_smoke_probe_writes_batch_artifacts(tmp_path: Path):
    module = _load_module()
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    _make_simple_glyph(input_dir / "yi.png")

    payload = module.run_visual_smoke_probe(
        input_dir=input_dir,
        output_root=tmp_path / "outputs",
        threshold=180,
        crop_pad=2,
        min_component_pixels=6,
        spur_max_length=1,
        min_segment_pixels=2,
        ordering_endpoint_merge_distance=1.0,
        ordering_direction_cos_threshold=0.7,
    )

    assert payload["status"] == "ok"
    batch_dir = Path(payload["batch_dir"])
    assert batch_dir.exists()
    assert (batch_dir / "manual_audit_sheet.csv").exists()
    assert (batch_dir / "visual_audit_contact_sheet.png").exists()
    report = json.loads((batch_dir / "visual_smoke_report.json").read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["sample_count"] == 1
    assert report["ordering_endpoint_merge_distance"] == 1.0
    assert report["ordering_direction_cos_threshold"] == 0.7


def test_run_visual_smoke_probe_can_fail_fast_on_backend_mismatch(tmp_path: Path, monkeypatch):
    module = _load_module()
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    _make_simple_glyph(input_dir / "yi.png")

    monkeypatch.setattr(module, "_detect_skeleton_backend", lambda: "numpy_midpoint_fallback")

    payload = module.run_visual_smoke_probe(
        input_dir=input_dir,
        output_root=tmp_path / "outputs",
        threshold=180,
        crop_pad=2,
        min_component_pixels=6,
        spur_max_length=1,
        min_segment_pixels=2,
        required_skeleton_backend="skimage_skeletonize",
    )

    assert payload["status"] == "skeleton_backend_mismatch"
    assert payload["detected_skeleton_backend"] == "numpy_midpoint_fallback"
    assert "batch_dir" not in payload
