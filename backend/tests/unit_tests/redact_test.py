import logging

from bracket.utils.redact import RedactTokensFilter, redact_tokens, redact_value

TOKEN = "fCnsXSSriLgROBR29OuyRZ2g9JYQXHfEba3ZnqxPk1k"


def test_redact_tokens_in_paths() -> None:
    assert redact_tokens(f"GET /score/{TOKEN} HTTP/1.1") == "GET /score/<redacted> HTTP/1.1"
    assert redact_tokens(f"/api/score/{TOKEN}/matches/3/walkover") == (
        "/api/score/<redacted>/matches/3/walkover"
    )
    assert (
        redact_tokens(f"https://cup.no/score/{TOKEN}?x=1") == "https://cup.no/score/<redacted>?x=1"
    )
    assert redact_tokens("/tournaments/3/score_links") == "/tournaments/3/score_links"


def test_uvicorn_access_log_is_redacted() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "PUT", f"/score/{TOKEN}/matches/7", "1.1", 200),
        None,
    )
    assert RedactTokensFilter().filter(record)
    assert TOKEN not in record.getMessage()
    assert "/score/<redacted>/matches/7" in record.getMessage()


def test_sentry_event_is_redacted() -> None:
    event = {
        "request": {
            "url": f"https://cup.no/api/score/{TOKEN}",
            "headers": {"Referer": f"https://cup.no/score/{TOKEN}"},
        },
        "breadcrumbs": {"values": [{"data": {"url": f"/score/{TOKEN}/notices"}}]},
        "transaction": f"/score/{TOKEN}",
    }
    assert TOKEN not in str(redact_value(event))
    assert redact_value(event)["transaction"] == "/score/<redacted>"
