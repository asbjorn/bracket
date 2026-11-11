from bracket.utils.csv_export import csv_cell, to_csv


def test_csv_cell_escapes_formulas() -> None:
    assert csv_cell("=1+1") == "'=1+1"
    assert csv_cell("+47 912") == "'+47 912"
    assert csv_cell("-x") == "'-x"
    assert csv_cell("@SUM") == "'@SUM"
    assert csv_cell("\tx") == "'\tx"
    assert csv_cell("Brann 1") == "Brann 1"
    assert csv_cell(None) == ""
    assert csv_cell(3) == "3"
    # Also after a separator or a newline inside the cell
    assert csv_cell("a;=1+1") == "a;'=1+1"
    assert csv_cell("a,@x") == "a,'@x"
    assert csv_cell("x\n=cmd") == "x\n'=cmd"
    assert csv_cell("x\r\n-2") == "x\r\n'-2"
    assert csv_cell("1-2; 3") == "1-2; 3"


def test_to_csv_quotes_every_cell() -> None:
    content = to_csv(["Lag", "Kommentar"], [["Brann;1", 'si "hei"\n=x']])
    assert content == '﻿"Lag";"Kommentar"\r\n"Brann;1";"si ""hei""\n\'=x"\r\n'
