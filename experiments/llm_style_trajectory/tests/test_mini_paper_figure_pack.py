import csv
from pathlib import Path

from PIL import Image

from experiments.llm_style_trajectory.src import mini_paper_figure_pack


def _make_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 24), color=(240, 240, 240)).save(path)


def test_build_mini_paper_figure_pack_writes_manifests_and_missing_sources(tmp_path):
    paper_figures = tmp_path / "paper_figures"
    source_dir = paper_figures / "source"
    _make_png(source_dir / "fig_modifier_connection_shan.png")
    _make_png(source_dir / "xingkai_balanced_compare_connector_levels_u56fd_xingkai.png")

    out_dir = paper_figures / "mini_paper_figures"
    result = mini_paper_figure_pack.build_figure_pack(
        paper_figures_dir=paper_figures,
        out_dir=out_dir,
        source_overrides={
            "fig2a": source_dir / "fig_modifier_connection_shan.png",
            "fig2b": source_dir / "missing_shape.png",
            "fig3a": source_dir / "xingkai_balanced_compare_connector_levels_u56fd_xingkai.png",
        },
    )

    assert (out_dir / "fig1_system_pipeline.png").exists()
    assert (out_dir / "fig2_modifier_control_connection.png").exists()
    assert (out_dir / "fig3_xingkai_connector_levels_u56fd.png").exists()
    assert (out_dir / "mini_paper_figure_manifest.csv").exists()
    assert (out_dir / "mini_paper_table_manifest.csv").exists()
    assert (out_dir / "mini_paper_figure_index.md").exists()

    missing_path = out_dir / "missing_sources.csv"
    assert missing_path.exists()
    missing_rows = list(csv.DictReader(missing_path.open(encoding="utf-8-sig")))
    assert any(row["figure_id"] == "fig2b" for row in missing_rows)
    assert result["missing_count"] >= 1

    manifest_rows = list(
        csv.DictReader((out_dir / "mini_paper_figure_manifest.csv").open(encoding="utf-8-sig"))
    )
    assert all((out_dir / row["filename"]).exists() for row in manifest_rows)


def test_table_manifest_contains_external_functional_comparison(tmp_path):
    paper_figures = tmp_path / "paper_figures"
    out_dir = paper_figures / "mini_paper_figures"
    mini_paper_figure_pack.build_figure_pack(paper_figures_dir=paper_figures, out_dir=out_dir)

    table_rows = list(
        csv.DictReader((out_dir / "mini_paper_table_manifest.csv").open(encoding="utf-8-sig"))
    )
    assert any(row["table_id"] == "table3" for row in table_rows)
    assert (out_dir / "table3_external_functional_comparison.md").exists()
