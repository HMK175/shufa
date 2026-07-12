from target_glyph_generation.splits import split_characters


def test_split_characters_is_disjoint_and_has_expected_counts():
    characters = [chr(0x4E00 + index) for index in range(1000)]

    splits = split_characters(characters, seed=20260713)

    assert {name: len(values) for name, values in splits.items()} == {
        "train": 800,
        "validation": 100,
        "test": 100,
    }
    assert len(set().union(*splits.values())) == 1000
