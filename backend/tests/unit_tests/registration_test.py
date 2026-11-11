from bracket.logic.registration import csv_cell


def test_csv_cell_escapes_formulas() -> None:
    assert csv_cell("=1+1") == "'=1+1"
    assert csv_cell("+47 912") == "'+47 912"
    assert csv_cell("-x") == "'-x"
    assert csv_cell("@SUM") == "'@SUM"
    assert csv_cell("\tx") == "'\tx"
    assert csv_cell("Brann 1") == "Brann 1"
    assert csv_cell(None) == ""
    assert csv_cell(3) == "3"
