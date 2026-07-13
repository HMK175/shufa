from target_glyph_generation.audit import summarize_dataset


def test_summarize_dataset_reports_style_and_character_counts():
    summary = summarize_dataset(
        style_ids=["a", "a", "b"],
        character_ids=["一", "乙", "一"],
        failures=[{"reason": "missing_glyph"}],
    )

    assert summary == {
        "accepted_style_count": 2,
        "rendered_target_count": 3,
        "unique_character_count": 2,
        "failure_count": 1,
    }
