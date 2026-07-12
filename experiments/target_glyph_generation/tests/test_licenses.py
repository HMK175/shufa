from target_glyph_generation.licenses import ACCEPTED_LICENSES, is_accepted_license


def test_only_explicitly_approved_license_identifiers_are_accepted():
    assert ACCEPTED_LICENSES == {"OFL-1.1", "Apache-2.0"}
    assert is_accepted_license("OFL-1.1") is True
    assert is_accepted_license("Apache-2.0") is True
    assert is_accepted_license("Proprietary") is False
    assert is_accepted_license("") is False
