"""
Names end up in email headers (subjects), CSV files and printed pages: they must be one line
without control characters, so e.g. "Brann\\r\\nBcc: x@example.org" can't inject a header.
"""

import re

from pydantic import AfterValidator

# C0 and C1 control characters (incl. CR, LF, tab) and the Unicode line separators
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")


def check_single_line(value: str) -> str:
    if CONTROL_CHARACTERS.search(value):
        raise ValueError("may not contain line breaks or control characters")
    return value


def strip_control_characters(value: str) -> str:
    """For values going into email headers: control characters become spaces."""
    return CONTROL_CHARACTERS.sub(" ", value)


SingleLine = AfterValidator(check_single_line)
