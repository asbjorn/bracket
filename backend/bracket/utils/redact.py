"""
Keeps result-link tokens out of logs and error reports. A token in a path such as
/score/<token>/matches/3 gives access to enter results, so it's replaced by "<redacted>".
"""

import logging
import re
from typing import Any

TOKEN_IN_PATH = re.compile(r"(/score/)[^/\s?#\"']+")
REDACTED = r"\1<redacted>"


def redact_tokens(text: str) -> str:
    return TOKEN_IN_PATH.sub(REDACTED, text)


def redact_value(value: Any) -> Any:
    """Redacts strings in nested dicts, lists and tuples (e.g. a Sentry event)."""
    if isinstance(value, str):
        return redact_tokens(value)
    if isinstance(value, dict):
        return {key: redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value


class RedactTokensFilter(logging.Filter):
    """Redacts tokens in a log record's message and arguments (e.g. uvicorn's access log)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_tokens(record.msg)
        if record.args:
            record.args = redact_value(record.args)
        return True


REDACTED_LOGGERS = ("uvicorn.access", "uvicorn.error", "uvicorn", "bracket", "fastapi")


def install_log_redaction() -> None:
    redaction = RedactTokensFilter()
    for name in REDACTED_LOGGERS:
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactTokensFilter) for f in logger.filters):
            logger.addFilter(redaction)
        for handler in logger.handlers:
            if not any(isinstance(f, RedactTokensFilter) for f in handler.filters):
                handler.addFilter(redaction)


def redact_sentry_event(event: Any, _hint: Any) -> Any:
    return redact_value(event)
