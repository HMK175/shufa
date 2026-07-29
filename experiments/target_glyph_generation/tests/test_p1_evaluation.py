import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from target_glyph_generation.p1_evaluation import build_p1_fixed_test_manifests


PROJECT_DIR = Path(__file__).parents[1]


def _assert_p1_formal_baseline_50k_preserves_protected_fields(
    payload_50k: dict, payload_10k: dict
) -> None:
    assert payload_50k["data_root"] == payload_10k["data_root"]
    assert payload_50k["model"] == payload_10k["model"]

    preserved_training_50k = payload_50k["training"].copy()
    preserved_training_10k = payload_10k["training"].copy()
    for field in ("max_train_steps", "checkpoint_interval"):
        preserved_training_50k.pop(field)
        preserved_training_10k.pop(field)
    assert preserved_training_50k == preserved_training_10k

    for field in (
        "paired_test_manifest",
        "visual_test_manifest",
        "paired_metrics",
        "distribution_metric",
    ):
        assert payload_50k["evaluation"][field] == payload_10k["evaluation"][field]

    assert payload_50k["runtime"]["output_dir"] == (
        "../outputs/fontdiffuser_p1_extended_phase1_baseline_50k"
    )
    for field in ("recommended_gpu_memory_gib", "report_to"):
        assert payload_50k["runtime"][field] == payload_10k["runtime"][field]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sample(
    *,
    style_id: str,
    character: str,
    split: str,
    source_kind: str = "external",
) -> dict[str, str]:
    return {
        "source_kind": source_kind,
        "style_id": style_id,
        "character": character,
        "character_split": split,
        "target_path": f"{split}/TargetImage/{style_id}/{style_id}+{character}.jpg",
        "source_path": f"D:/raw/{style_id}_{character}.png",
        "image_preprocess": "none",
        "tier": "core",
        "paper_eligible": "True",
    }


def _create_dataset_files(dataset_root: Path, rows: list[dict[str, str]]) -> None:
    for row in rows:
        target_path = dataset_root / row["target_path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"target")
        content_path = dataset_root / row["character_split"] / "ContentImage" / f"{row['character']}.jpg"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_bytes(b"content")


def test_build_p1_fixed_test_manifests_pairs_test_targets_with_train_style_reference(tmp_path):
    dataset_root = tmp_path / "dataset"
    rows = [
        _sample(style_id="style_a", character="甲", split="train"),
        _sample(style_id="style_a", character="乙", split="train"),
        _sample(style_id="style_a", character="丙", split="test"),
        _sample(style_id="style_a", character="丁", split="test"),
        _sample(style_id="style_b", character="甲", split="train", source_kind="open_font"),
        _sample(style_id="style_b", character="丙", split="test", source_kind="open_font"),
    ]
    _create_dataset_files(dataset_root, rows)
    samples_csv = dataset_root / "manifests" / "samples.csv"
    _write_csv(samples_csv, rows)

    output_dir = tmp_path / "evaluation"
    summary = build_p1_fixed_test_manifests(samples_csv, output_dir, seed=7, visual_per_style=1)

    assert summary == {
        "paired_test_count": 3,
        "visual_test_count": 2,
        "style_count": 2,
        "seed": 7,
        "visual_per_style": 1,
    }
    with (output_dir / "paired_test_manifest.csv").open(encoding="utf-8-sig", newline="") as handle:
        paired_rows = list(csv.DictReader(handle))
    assert len(paired_rows) == 3
    assert {row["character_split"] for row in paired_rows} == {"test"}
    assert all(row["reference_path"].startswith("train/TargetImage/") for row in paired_rows)
    assert all(row["reference_style_id"] == row["style_id"] for row in paired_rows)
    assert all(row["reference_character"] not in {"丙", "丁"} for row in paired_rows)
    assert all((dataset_root / row["content_path"]).is_file() for row in paired_rows)
    assert all((dataset_root / row["target_path"]).is_file() for row in paired_rows)
    assert all((dataset_root / row["reference_path"]).is_file() for row in paired_rows)
    with (output_dir / "visual_test_manifest.csv").open(encoding="utf-8-sig", newline="") as handle:
        visual_rows = list(csv.DictReader(handle))
    assert len(visual_rows) == 2
    assert {row["style_id"] for row in visual_rows} == {"style_a", "style_b"}
    assert json.loads((output_dir / "evaluation_summary.json").read_text(encoding="utf-8")) == summary


def test_p1_baseline_config_fixes_phase1_pilot_and_evaluation_contract():
    config_path = PROJECT_DIR / "configs" / "fontdiffuser_p1_extended_phase1_baseline_10k.yaml"

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert payload["dataset_scope"] == "p1_extended"
    assert payload["phase"] == 1
    assert payload["scr"] is False
    assert payload["training"]["max_train_steps"] == 10000
    assert payload["training"]["checkpoint_interval"] == 1000
    assert payload["model"]["resolution"] == 96
    assert payload["training"]["batch_size"] == 1
    assert payload["training"]["gradient_accumulation_steps"] == 8
    assert payload["evaluation"]["paired_test_manifest"].endswith("paired_test_manifest.csv")
    assert payload["evaluation"]["visual_test_manifest"].endswith("visual_test_manifest.csv")


def test_p1_formal_baseline_50k_config_fixes_phase1_and_evaluation_contract():
    config_dir = PROJECT_DIR / "configs"
    config_path = config_dir / "fontdiffuser_p1_extended_phase1_baseline_50k.yaml"

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    payload_10k = yaml.safe_load(
        (config_dir / "fontdiffuser_p1_extended_phase1_baseline_10k.yaml").read_text(encoding="utf-8")
    )

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
    assert payload["runtime"]["output_dir"] == (
        "../outputs/fontdiffuser_p1_extended_phase1_baseline_50k"
    )
    assert payload["evaluation"]["sample_checkpoint_steps"] == [10000, 20000, 30000, 40000, 50000]
    assert payload["paper_boundary"]["task"] == "已见风格下的未见字符生成"
    assert payload["paper_boundary"]["chinese_style_license_status"] == "unverified"
    assert payload["paper_boundary"]["chinese_style_paper_use_basis"] == "user_confirmed_unverified_source"
    assert payload["paper_boundary"]["training_initialization"] == "random"
    assert payload["paper_boundary"]["checkpoint_resume"] == "prohibited_for_formal_baseline"
    _assert_p1_formal_baseline_50k_preserves_protected_fields(payload, payload_10k)


def test_p1_formal_baseline_50k_protected_fields_reject_changes():
    config_dir = PROJECT_DIR / "configs"
    payload_50k = yaml.safe_load(
        (config_dir / "fontdiffuser_p1_extended_phase1_baseline_50k.yaml").read_text(encoding="utf-8")
    )
    payload_10k = yaml.safe_load(
        (config_dir / "fontdiffuser_p1_extended_phase1_baseline_10k.yaml").read_text(encoding="utf-8")
    )
    changed_payload = deepcopy(payload_50k)
    changed_payload["model"]["resolution"] = 64

    with pytest.raises(AssertionError):
        _assert_p1_formal_baseline_50k_preserves_protected_fields(changed_payload, payload_10k)


def test_p1_formal_baseline_50k_protected_fields_reject_10k_nested_output_dir():
    config_dir = PROJECT_DIR / "configs"
    payload_50k = yaml.safe_load(
        (config_dir / "fontdiffuser_p1_extended_phase1_baseline_50k.yaml").read_text(encoding="utf-8")
    )
    payload_10k = yaml.safe_load(
        (config_dir / "fontdiffuser_p1_extended_phase1_baseline_10k.yaml").read_text(encoding="utf-8")
    )
    changed_payload = deepcopy(payload_50k)
    changed_payload["runtime"]["output_dir"] = (
        "../outputs/fontdiffuser_p1_extended_phase1_baseline_10k/baseline_50k"
    )

    with pytest.raises(AssertionError):
        _assert_p1_formal_baseline_50k_preserves_protected_fields(changed_payload, payload_10k)
