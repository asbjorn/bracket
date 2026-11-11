from heliclockter import datetime_utc

from bracket.models.db.jury import JuryMember, JuryRole, JuryWarning, jury_warnings
from bracket.utils.id_types import TournamentId


def member(name: str, club: str | None, role: JuryRole = JuryRole.MEMBER) -> JuryMember:
    return JuryMember(
        id=hash(name) % 1000,
        tournament_id=TournamentId(1),
        created=datetime_utc.now(),
        name=name,
        club_name=club,
        role=role,
    )


def test_jury_rules() -> None:
    chair = member("Kari", "Brann", JuryRole.CHAIR)
    assert jury_warnings([]) == [JuryWarning.TOO_FEW_MEMBERS]
    assert jury_warnings([chair, member("Ola", "Lyn")]) == [JuryWarning.TOO_FEW_MEMBERS]
    assert not jury_warnings([chair, member("Ola", "Lyn"), member("Per", "Fana")])
    # At most one per club (ignoring case and spaces)
    assert jury_warnings([chair, member("Ola", " brann"), member("Per", "Fana")]) == [
        JuryWarning.SAME_CLUB
    ]
    # Members without a club don't clash
    assert not jury_warnings([chair, member("Ola", None), member("Per", None)])
    assert jury_warnings([member("A", "x"), member("B", "y"), member("C", "z")]) == [
        JuryWarning.NO_CHAIR
    ]
