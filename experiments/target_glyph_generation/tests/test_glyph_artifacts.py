import csv
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image

from target_glyph_generation.glyph_artifacts import (
    audit_right_border_lines,
    mask_isolated_right_border_lines,
)


def test_mask_isolated_right_border_line_removes_only_disconnected_line():
    image = Image.new("L", (8, 8), color=255)
    for x in range(1, 4):
        for y in range(2, 6):
            image.putpixel((x, y), 0)
    for y in range(8):
        image.putpixel((7, y), 0)

    cleaned, actions = mask_isolated_right_border_lines(image)

    assert all(cleaned.getpixel((7, y)) == 255 for y in range(8))
    assert cleaned.getpixel((1, 2)) == 0
    assert actions == [{"x0": 7, "y0": 0, "x1": 7, "y1": 7, "area": 8}]


def test_mask_isolated_right_border_line_keeps_connected_vertical_stroke():
    image = Image.new("L", (8, 8), color=255)
    for x in range(1, 4):
        for y in range(2, 6):
            image.putpixel((x, y), 0)
    for x in range(3, 8):
        image.putpixel((x, 4), 0)
    for y in range(8):
        image.putpixel((7, y), 0)

    cleaned, actions = mask_isolated_right_border_lines(image)

    assert cleaned.tobytes() == image.tobytes()
    assert actions == []


def test_audit_right_border_lines_writes_only_detected_actions(tmp_path):
    artifact_image = Image.new("L", (8, 8), color=255)
    for x in range(1, 4):
        for y in range(2, 6):
            artifact_image.putpixel((x, y), 0)
    for y in range(8):
        artifact_image.putpixel((7, y), 0)
    artifact_path = tmp_path / "artifact.png"
    artifact_image.save(artifact_path)
    clean_path = tmp_path / "clean.png"
    Image.new("L", (8, 8), color=255).save(clean_path)
    input_path = tmp_path / "samples.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["style_id", "source_split", "raw_filename", "target_path"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"style_id": "htj", "source_split": "train", "raw_filename": "1.jpg", "target_path": str(artifact_path)},
                {"style_id": "htj", "source_split": "train", "raw_filename": "2.jpg", "target_path": str(clean_path)},
            ]
        )
    output_path = tmp_path / "actions.csv"

    summary = audit_right_border_lines(input_path, output_path)

    assert summary == {"scanned_count": 2, "detected_count": 1}
    with output_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "style_id": "htj",
            "source_split": "train",
            "raw_filename": "1.jpg",
            "target_path": str(artifact_path),
            "image_preprocess": "mask_isolated_right_border_line",
            "component_count": "1",
        }
    ]


def test_audit_right_border_lines_cli_forwards_paths(monkeypatch, tmp_path, capsys):
    script_path = Path(__file__).parents[1] / "scripts" / "audit_right_border_lines.py"
    spec = importlib.util.spec_from_file_location("test_audit_right_border_lines", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captured = {}

    def fake_audit(input_csv: Path, output_csv: Path, path_column: str):
        captured.update({"input_csv": input_csv, "output_csv": output_csv, "path_column": path_column})
        return {"scanned_count": 2, "detected_count": 1}

    monkeypatch.setattr(module, "audit_right_border_lines", fake_audit)
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_right_border_lines.py",
            "--input-csv",
            str(input_path),
            "--output-csv",
            str(output_path),
            "--path-column",
            "image_path",
        ],
    )

    module.main()

    assert captured == {"input_csv": input_path, "output_csv": output_path, "path_column": "image_path"}
    assert json.loads(capsys.readouterr().out) == {"scanned_count": 2, "detected_count": 1}
