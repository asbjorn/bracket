import pytest
from pydantic import ValidationError

from bracket.models.db.match import MatchBody, MatchResultType
from bracket.utils.id_types import RoundId


def body(**values: object) -> MatchBody:
    return MatchBody.model_validate({"round_id": RoundId(1), **values})


@pytest.mark.parametrize(
    ("values", "error"),
    [
        pytest.param(
            {"result_type": "PENALTIES", "stage_item_input1_score": 1},
            "Enter the penalty shootout score of both teams",
            id="penalties missing",
        ),
        pytest.param(
            {
                "result_type": "PENALTIES",
                "stage_item_input1_score": 2,
                "stage_item_input2_score": 1,
                "stage_item_input1_penalties": 5,
                "stage_item_input2_penalties": 4,
            },
            "only possible when the score is equal",
            id="score not equal",
        ),
        pytest.param(
            {
                "result_type": "PENALTIES",
                "stage_item_input1_penalties": 4,
                "stage_item_input2_penalties": 4,
            },
            "must have a winner",
            id="shootout without winner",
        ),
        pytest.param(
            {"stage_item_input1_penalties": 4, "stage_item_input2_penalties": 3},
            "only be entered for a penalty shootout",
            id="penalties without shootout",
        ),
        pytest.param(
            {"result_type": "WALKOVER"}, "A walkover must have a winner", id="walkover 0-0"
        ),
        pytest.param({"stage_item_input1_score": -1}, "greater than or equal to 0", id="negative"),
    ],
)
def test_invalid_results(values: dict[str, object], error: str) -> None:
    with pytest.raises(ValidationError, match=error):
        body(**values)


def test_valid_results() -> None:
    shootout = body(
        result_type="PENALTIES",
        stage_item_input1_score=2,
        stage_item_input2_score=2,
        stage_item_input1_penalties=3,
        stage_item_input2_penalties=5,
    )
    assert shootout.result_type is MatchResultType.PENALTIES
    assert body(result_type="EXTRA_TIME", stage_item_input1_score=3, stage_item_input2_score=2)
    assert body(result_type="WALKOVER", stage_item_input1_score=3)
    assert body().result_type is MatchResultType.NORMAL
