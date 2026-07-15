import csv
import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

from target_glyph_generation.fontdiffuser_adapter import build_fontdiffuser_training_adapter


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_script(filename: str):
    spec = importlib.util.spec_from_file_location(f"test_{filename.replace('.', '_')}", SCRIPTS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _save_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("L", (256, 256), 255)
    ImageDraw.Draw(image).rectangle((64, 64, 192, 192), fill=0)
    image.save(path)


def test_build_fontdiffuser_training_adapter_links_only_train_styles_and_characters(tmp_path: Path):
    dataset_root = tmp_path / "p0"
    styles = [
        {"style_id": "style_a", "style_split": "train"},
        {"style_id": "style_b", "style_split": "train"},
        {"style_id": "held_out", "style_split": "test"},
    ]
    characters = [("一", "train"), ("二", "train"), ("三", "train"), ("四", "validation")]
    rows = []
    for character, character_split in characters:
        content_path = Path("rendered") / "ContentImage" / f"{character}.png"
        _save_image(dataset_root / content_path)
        for style in styles:
            target_path = Path("rendered") / "TargetImage" / style["style_id"] / f"{style['style_id']}+{character}.png"
            _save_image(dataset_root / target_path)
            rows.append(
                {
                    "style_id": style["style_id"],
                    "style_split": style["style_split"],
                    "character": character,
                    "character_split": character_split,
                    "content_path": content_path.as_posix(),
                    "target_path": target_path.as_posix(),
                }
            )
    _write_csv(
        dataset_root / "manifests" / "samples.csv",
        ["style_id", "style_split", "character", "character_split", "content_path", "target_path"],
        rows,
    )

    output_root = tmp_path / "fontdiffuser_train"
    summary = build_fontdiffuser_training_adapter(
        p0_dataset_root=dataset_root,
        output_root=output_root,
        style_ids=["style_a", "style_b"],
        character_limit=2,
        selection_seed=7,
    )

    assert summary["style_count"] == 2
    assert summary["character_count"] == 2
    assert summary["target_image_count"] == 4
    assert summary["excluded_style_count"] == 1
    content_paths = sorted((output_root / "train" / "ContentImage").glob("*.jpg"))
    target_paths = sorted((output_root / "train" / "TargetImage").glob("*/*.jpg"))
    assert len(content_paths) == 2
    assert len(target_paths) == 4
    assert all(path.parent.parent.name == "TargetImage" for path in target_paths)
    with Image.open(content_paths[0]) as image:
        assert image.size == (256, 256)
    with (output_root / "manifests" / "adapter_samples.csv").open(encoding="utf-8", newline="") as handle:
        manifest_rows = list(csv.DictReader(handle))
    assert len(manifest_rows) == 4
    assert {row["style_id"] for row in manifest_rows} == {"style_a", "style_b"}
    assert {row["character_split"] for row in manifest_rows} == {"train"}


def test_build_fontdiffuser_training_adapter_rejects_a_style_with_only_one_training_character(tmp_path: Path):
    dataset_root = tmp_path / "p0"
    content_path = Path("rendered") / "ContentImage" / "一.png"
    target_path = Path("rendered") / "TargetImage" / "style_a" / "style_a+一.png"
    _save_image(dataset_root / content_path)
    _save_image(dataset_root / target_path)
    _write_csv(
        dataset_root / "manifests" / "samples.csv",
        ["style_id", "style_split", "character", "character_split", "content_path", "target_path"],
        [
            {
                "style_id": "style_a",
                "style_split": "train",
                "character": "一",
                "character_split": "train",
                "content_path": content_path.as_posix(),
                "target_path": target_path.as_posix(),
            }
        ],
    )

    try:
        build_fontdiffuser_training_adapter(
            p0_dataset_root=dataset_root,
            output_root=tmp_path / "adapter",
            style_ids=["style_a"],
            character_limit=None,
            selection_seed=7,
        )
    except ValueError as error:
        assert "at least two training characters" in str(error)
    else:
        raise AssertionError("expected one-character style to be rejected")


def test_build_fontdiffuser_adapter_cli_forwards_selection_arguments(monkeypatch, tmp_path: Path, capsys):
    module = _load_script("build_fontdiffuser_adapter.py")
    captured = {}

    def fake_build(**kwargs):
        captured.update(kwargs)
        return {"target_image_count": 128}

    monkeypatch.setattr(module, "build_fontdiffuser_training_adapter", fake_build)
    arguments = {
        "p0_dataset_root": tmp_path / "p0",
        "output_root": tmp_path / "adapter",
        "style_ids": ["style_a", "style_b"],
        "character_limit": 64,
        "selection_seed": 7,
    }
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_fontdiffuser_adapter.py",
            "--p0-dataset-root", str(arguments["p0_dataset_root"]),
            "--output-root", str(arguments["output_root"]),
            "--style-ids", *arguments["style_ids"],
            "--character-limit", str(arguments["character_limit"]),
            "--selection-seed", str(arguments["selection_seed"]),
        ],
    )

    module.main()

    assert captured == arguments
    assert json.loads(capsys.readouterr().out) == {"target_image_count": 128}
