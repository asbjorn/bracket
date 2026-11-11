import re

import pytest
from fastapi import HTTPException

from bracket.logic.scheduling.elimination import get_number_of_rounds_to_create_single_elimination
from bracket.logic.scheduling.round_robin import get_number_of_rounds_to_create_round_robin


def test_number_of_rounds_round_robin() -> None:
    assert get_number_of_rounds_to_create_round_robin(0) == 0
    assert get_number_of_rounds_to_create_round_robin(2) == 1
    assert get_number_of_rounds_to_create_round_robin(4) == 3
    assert get_number_of_rounds_to_create_round_robin(6) == 5


def test_number_of_rounds_single_elimination() -> None:
    assert get_number_of_rounds_to_create_single_elimination(0) == 0
    assert get_number_of_rounds_to_create_single_elimination(2) == 1
    assert get_number_of_rounds_to_create_single_elimination(4) == 2
    assert get_number_of_rounds_to_create_single_elimination(8) == 3
    assert get_number_of_rounds_to_create_single_elimination(16) == 4
    assert get_number_of_rounds_to_create_single_elimination(32) == 5

    # Any number of teams works, some teams get a bye in the first round
    assert get_number_of_rounds_to_create_single_elimination(3) == 2
    assert get_number_of_rounds_to_create_single_elimination(5) == 3
    assert get_number_of_rounds_to_create_single_elimination(6) == 3
    assert get_number_of_rounds_to_create_single_elimination(12) == 4
    assert get_number_of_rounds_to_create_single_elimination(64) == 6

    err_msg = re.escape("400: A knockout bracket needs at least 2 teams")
    with pytest.raises(HTTPException, match=err_msg):
        get_number_of_rounds_to_create_single_elimination(1)

    with pytest.raises(HTTPException, match=err_msg):
        get_number_of_rounds_to_create_single_elimination(1)
