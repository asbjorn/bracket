from datetime import timedelta
from zoneinfo import ZoneInfo

from heliclockter import datetime_utc

from bracket.logic.planning.capacity import (
    CapacityBody,
    CapacityClass,
    CapacityCourts,
    CapacityWarning,
    calculate_capacity,
)
from bracket.logic.scheduling.cup_structure import PlayoffPreset, split_into_groups, split_placings
from bracket.models.db.time_window import TimeWindowBody

DAY = datetime_utc(2026, 6, 13, tzinfo=ZoneInfo("UTC"))


def window(start_hour: int, end_hour: int) -> TimeWindowBody:
    return TimeWindowBody(
        start_time=DAY + timedelta(hours=start_hour), end_time=DAY + timedelta(hours=end_hour)
    )


def test_split_into_groups() -> None:
    assert split_into_groups(8, 4) == [4, 4]
    assert split_into_groups(10, 4) == [4, 3, 3]
    assert split_into_groups(9, 4) == [3, 3, 3]
    assert split_into_groups(5, 5) == [5]
    assert split_into_groups(3, 4) == [3]


def test_split_placings() -> None:
    assert split_placings(4, 1) == [[1, 2, 3, 4]]
    assert split_placings(4, 2) == [[1, 2], [3, 4]]
    assert split_placings(5, 2) == [[1, 2, 3], [4, 5]]
    assert split_placings(4, 3) == [[1, 2], [3], [4]]
    assert split_placings(2, 3) == [[1], [2]]


def test_cup_manager_example() -> None:
    """
    200 teams in groups of 4 = 300 group matches of 2x15 + 2 minutes, 08:00-20:00:
    at least 14 courts (Cup Manager). With 8 courts, 6 more are needed.
    """
    classes = [
        CapacityClass(
            name=name, team_count=100, group_size=4, duration_minutes=30, margin_minutes=2
        )
        for name in ("G14", "J14")
    ]
    body = CapacityBody(
        classes=classes, courts=[CapacityCourts(count=14)], time_windows=[window(8, 20)]
    )
    result = calculate_capacity(body)
    assert sum(c.group_matches for c in result.classes) == 300
    assert result.schedule.unscheduled_match_ids == []

    smaller = body.model_copy(update={"courts": [CapacityCourts(count=8)]})
    result = calculate_capacity(smaller)
    assert len(result.schedule.unscheduled_match_ids) > 0
    assert [(c.game_format, c.count) for c in result.schedule.extra_courts or []] == [(None, 6)]


def test_areacopa_indoor_example() -> None:
    """
    8 teams, 2 groups of 4, the top 2 play semifinals and a final: 15 matches of 8 + 3 minutes
    from 14:00 on one court; the final ends at 16:50 (AreaCopa's timeline).
    """
    body = CapacityBody(
        classes=[
            CapacityClass(
                name="G12",
                age=12,
                team_count=8,
                group_size=4,
                playoff_placings=[[1, 2]],
                duration_minutes=8,
                margin_minutes=3,
            )
        ],
        courts=[CapacityCourts(count=1)],
        time_windows=[window(14, 17)],
        stage_buffer_minutes=5,
    )
    result = calculate_capacity(body)
    [class_result] = result.classes
    assert (class_result.group_matches, class_result.playoff_matches) == (12, 3)
    assert class_result.playoff_team_counts == [4]
    assert result.schedule.unscheduled_match_ids == []
    assert result.schedule.last_end == DAY + timedelta(hours=16, minutes=50)
    # Places 3 and 4 only play their 3 group matches; 12 is children's football
    assert class_result.min_matches_per_team == 3
    assert class_result.warnings == [CapacityWarning.PLAYOFFS_IN_CHILDRENS_FOOTBALL]


def test_warnings() -> None:
    def warnings_for(**values: object) -> list[CapacityWarning]:
        cup_class = CapacityClass.model_validate(
            {"name": "X", "team_count": 6, "group_size": 3, "duration_minutes": 10, **values}
        )
        body = CapacityBody(
            classes=[cup_class], courts=[CapacityCourts(count=4)], time_windows=[window(8, 20)]
        )
        return calculate_capacity(body).classes[0].warnings

    # Groups of 3 without playoffs: only 2 matches per team
    assert warnings_for(age=10) == [CapacityWarning.TOO_FEW_MATCHES]
    # With A and B playoffs everyone plays at least 3, but 10 is children's football
    assert warnings_for(age=10, playoffs=PlayoffPreset.AB) == [
        CapacityWarning.PLAYOFFS_IN_CHILDRENS_FOOTBALL
    ]
    # 13: groups of 6 and one playoff of 12 teams: up to 5 + 4 = 9 matches in a day
    assert warnings_for(age=13, team_count=12, group_size=6, playoffs=PlayoffPreset.A) == [
        CapacityWarning.TOO_MANY_MATCHES_PER_DAY
    ]
    assert warnings_for(age=16, team_count=12, group_size=6, playoffs=PlayoffPreset.A) == []


def test_matches_per_team_with_bronze_final() -> None:
    # 8 teams in 2 groups of 4; all go to playoff A (8 teams, 3 rounds) with a bronze final
    body = CapacityBody(
        classes=[
            CapacityClass(
                name="J16",
                age=16,
                team_count=8,
                group_size=4,
                playoffs=PlayoffPreset.A,
                third_place_match=True,
                duration_minutes=20,
            )
        ],
        courts=[CapacityCourts(count=4)],
        time_windows=[window(8, 20)],
    )
    result = calculate_capacity(body).classes[0]
    assert result.playoff_team_counts == [8]
    assert result.playoff_matches == 8
    # The bronze final replaces the final for the semifinal losers: no extra match
    assert (result.min_matches_per_team, result.max_matches_per_team) == (4, 6)
    assert result.warnings == []
