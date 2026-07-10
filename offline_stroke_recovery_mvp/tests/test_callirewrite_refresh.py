from pathlib import Path
import json
import sys

import numpy as np
from PIL import Image, ImageDraw


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_refresh import run_callirewrite_refresh_probe


def _write_input_png(path: Path) -> None:
    image = Image.new("L", (64, 64), 255)
    draw = ImageDraw.Draw(image)
    draw.line((10, 32, 54, 32), fill=0, width=4)
    image.save(path)


def _write_stale_converted_sample(sample_dir: Path) -> None:
    sample_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "callirewrite_npz",
        "coordinate_frame": "callirewrite_image_pixels",
        "segments": [
            {
                "segment_id": 99,
                "source_segment_ids": [99],
                "points": [[10.0, 10.0], [40.0, 10.0]],
                "pixel_count": 2,
                "length_px": 30.0,
                "start": [10.0, 10.0],
                "end": [40.0, 10.0],
                "component_id": 1,
                "is_loop": False,
            }
        ],
        "boundary_note": "stale fixture",
    }
    (sample_dir / "callirewrite_recovered_strokes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (sample_dir / "callirewrite_summary.json").write_text(
        json.dumps(
            {
                "status": "ok",
                "source": "callirewrite_npz",
                "sample": sample_dir.name,
                "segment_count": 1,
                "trajectory_point_count": 2,
                "manual_audit_required": True,
                "failure_reason": "",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_run_callirewrite_refresh_probe_rebuilds_converted_outputs_before_hybrid(tmp_path: Path):
    seq_data_dir = tmp_path / "seq_data"
    converted_dir = tmp_path / "converted"
    input_dir = tmp_path / "inputs"
    output_dir = tmp_path / "outputs"
    seq_data_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)

    _write_input_png(input_dir / "yi.png")
    _write_stale_converted_sample(converted_dir / "yi")
    np.savez(
        seq_data_dir / "yi.npz",
        strokes_data=np.array(
            [
                [0.0, 0.0, 0.0, 0.0, 0.5, 0.2, 1.0],
            ],
            dtype=np.float32,
        ),
        init_cursors=np.array([[0.5, 0.5]], dtype=np.float32),
        image_size=np.array(64, dtype=np.int32),
        round_length=np.array([1], dtype=np.int32),
        init_width=np.array(0.2, dtype=np.float32),
    )

    payload = run_callirewrite_refresh_probe(
        seq_data_dir=seq_data_dir,
        converted_dir=converted_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        samples=["yi"],
    )

    assert payload["status"] == "ok"
    assert payload["stage"] == "callirewrite_refresh_probe"
    assert payload["converted_count"] == 1
    assert payload["converted_samples"] == ["yi"]
    assert Path(payload["hybrid_batch_dir"]).exists()
    assert Path(payload["visual_audit_contact_sheet"]).exists()
    assert Path(payload["refresh_report_path"]).exists()

    recovered = json.loads((converted_dir / "yi" / "callirewrite_recovered_strokes.json").read_text(encoding="utf-8"))
    points = recovered["segments"][0]["points"]
    assert points[0] == [32.0, 32.0]
    assert points[-1] == [32.0, 48.0]
    assert recovered["segments"][0]["source_segment_ids"] == [1]

    hybrid_summary = json.loads(
        (Path(payload["hybrid_batch_dir"]) / "yi" / "recovery_summary.json").read_text(encoding="utf-8")
    )
    assert hybrid_summary["raw_segment_count"] == 1
    assert hybrid_summary["ordered_source_segment_ids"] == [[1]]
