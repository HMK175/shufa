from pathlib import Path
import importlib.util
import json

from PIL import Image, ImageDraw


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "local_method_final_attempt_probe.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("local_method_final_attempt_probe", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_glyph(path: Path) -> None:
    image = Image.new("L", (48, 48), 255)
    draw = ImageDraw.Draw(image)
    draw.line((8, 24, 40, 24), fill=0, width=4)
    draw.line((24, 8, 24, 40), fill=0, width=4)
    image.save(path)


def test_run_final_attempt_probe_writes_gate_report(tmp_path: Path):
    module = _load_module()
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for sample in ["xin", "yong", "zhong"]:
        _make_glyph(input_dir / f"{sample}.png")

    payload = module.run_final_attempt_probe(
        input_dir=input_dir,
        output_dir=tmp_path / "outputs",
        samples=["xin", "yong", "zhong"],
    )

    report_path = Path(payload["report_path"])
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["sample_count"] == 3
    assert report["decision"] in {"continue_local_method_once", "stop_and_switch_hybrid"}
    assert Path(report["batch_dir"]).exists()
    assert Path(report["visual_audit_contact_sheet"]).exists()
