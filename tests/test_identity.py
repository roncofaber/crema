import pytest

from core.identity import is_email, normalize_name, normalize_token, validate_token


def test_normalize_name_trims_whitespace():
    assert normalize_name("  Alice  ") == "Alice"


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_normalize_name_rejects_invalid_values(name):
    with pytest.raises(ValueError, match="Name"):
        normalize_name(name)


def test_validate_token_matches_scanner_canonicalization():
    assert validate_token("  Alice@Example.COM  ") == "alice@example.com"
    assert normalize_token(" Alice@Example.COM ") == "alice@example.com"
    assert is_email("alice@example.com")


@pytest.mark.parametrize("token", ["", "not-an-email", "a@localhost", "@example.com"])
def test_validate_token_rejects_unscannable_values(token):
    assert not is_email(token)
    with pytest.raises(ValueError, match="Token"):
        validate_token(token)
