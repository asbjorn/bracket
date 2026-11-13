from bracket.logic.scheduling.fit_groups import fit_playoff
from bracket.models.db.playoffs import PlayoffBody


def test_fit_playoff_keeps_placings_of_the_smallest_group() -> None:
    playoff = PlayoffBody(name="B", placings=[3, 4], best_of_placing=None, third_place_match=True)
    assert fit_playoff(playoff, [4, 3, 3]) == PlayoffBody(
        name="B", placings=[3], best_of_placing=None, third_place_match=False
    )
    assert fit_playoff(playoff, [4, 4, 4]) == PlayoffBody(
        name="B", placings=[3, 4], best_of_placing=None, third_place_match=True
    )
    # No group has a third team: no B playoff
    assert fit_playoff(playoff, [2, 2]) is None


def test_fit_playoff_best_placed_teams() -> None:
    # The A playoff: group winners plus the two best runners-up
    playoff = PlayoffBody(name="A", placings=[1], best_of_placing=2, best_ranks=[1, 2])
    assert fit_playoff(playoff, [3, 3, 3]) == playoff
    # Only one group has a runner-up: only the best one of them is left
    assert fit_playoff(playoff, [2, 1]) == PlayoffBody(
        name="A", placings=[1], best_of_placing=2, best_ranks=[1]
    )
    # The best placed teams of a placing that is now fully in the playoff are left out
    assert fit_playoff(
        PlayoffBody(name="A", placings=[1, 2], best_of_placing=3, best_ranks=[1]), [2, 2]
    ) == PlayoffBody(name="A", placings=[1, 2], best_of_placing=None)
