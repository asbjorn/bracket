from pathlib import Path

from bracket.utils.error_codes import ERROR_CODES, error_code_headers


def test_every_coded_message_is_still_raised_somewhere() -> None:
    """A changed message would silently lose its translation: keep the list in sync."""
    sources = "\n".join(
        path.read_text() for path in Path("bracket").rglob("*.py") if path.name != "error_codes.py"
    )
    flat = " ".join(sources.split())  # Messages may be wrapped over several lines
    for message in ERROR_CODES:
        assert f'"{message}"' in sources or message in flat, message


def test_codes_are_unique_and_headers() -> None:
    assert len(set(ERROR_CODES.values())) == len(ERROR_CODES)
    assert error_code_headers("Registration for this class is closed") == {
        "X-Error-Code": "registration_class_closed"
    }
    assert not error_code_headers("Something else")
    assert not error_code_headers(["not", "a", "string"])
