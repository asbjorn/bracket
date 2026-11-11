"""
CSV files for spreadsheets (Excel in Norway): UTF-8 with BOM, `;` between the columns and every
cell quoted. Text that a spreadsheet would run as a formula is neutralised (CSV injection).
"""

import csv
import io
import re
from collections.abc import Iterable

# A spreadsheet runs a cell (or a line within it) starting with these as a formula
FORMULA_START = re.compile(r"(^|[\r\n\t;,])(?=[=+\-@\t\r])")


def csv_cell(value: object) -> str:
    """The text of a cell, with `'` before a formula start, also after a newline or separator."""
    text = "" if value is None else str(value)
    return FORMULA_START.sub(lambda match: match.group(1) + "'", text)


def to_csv(header: Iterable[object], rows: Iterable[Iterable[object]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_ALL)
    writer.writerow(csv_cell(value) for value in header)
    for row in rows:
        writer.writerow(csv_cell(value) for value in row)
    return "﻿" + output.getvalue()
