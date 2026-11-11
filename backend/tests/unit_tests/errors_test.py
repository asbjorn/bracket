import asyncpg  # type: ignore[import-untyped]
import pytest
from fastapi import HTTPException

from bracket.utils.errors import (
    GENERIC_FOREIGN_KEY_VIOLATION,
    ForeignKey,
    check_foreign_key_violation,
)


def foreign_key_violation(constraint_name: str) -> Exception:
    error: Exception = asyncpg.exceptions.ForeignKeyViolationError("violates foreign key")
    setattr(error, "constraint_name", constraint_name)  # As asyncpg sets it from the server
    return error


@pytest.mark.parametrize(
    "constraint_name",
    [
        pytest.param("some_new_table_tournament_id_fkey", id="unknown constraint"),
        pytest.param("teams_tournament_id_fkey", id="known but not expected here"),
    ],
)
def test_unexpected_foreign_key_violation_is_a_clear_400(constraint_name: str) -> None:
    with pytest.raises(HTTPException) as error:
        with check_foreign_key_violation({ForeignKey.stages_tournament_id_fkey}):
            raise foreign_key_violation(constraint_name)
    assert (error.value.status_code, error.value.detail) == (400, GENERIC_FOREIGN_KEY_VIOLATION)


def test_expected_foreign_key_violation_has_its_message() -> None:
    with pytest.raises(HTTPException) as error:
        with check_foreign_key_violation({ForeignKey.stages_tournament_id_fkey}):
            raise foreign_key_violation("stages_tournament_id_fkey")
    assert error.value.detail == "This tournament still has stages, delete those first"
