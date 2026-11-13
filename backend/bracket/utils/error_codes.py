"""
Machine-readable codes for errors that people outside the organisation see (public sign-up,
pitch links) or that organisers often meet on match day. The code is sent in the
`X-Error-Code` header next to the unchanged English `detail`, so the frontend can show the
error in the user's language and fall back to the English text for anything else.
"""

ERROR_CODE_HEADER = "X-Error-Code"

ERROR_CODES: dict[str, str] = {
    # Public sign-up
    "Registration for this cup is closed": "registration_cup_closed",
    "This class doesn't exist": "registration_class_unknown",
    "Registration for this class is closed": "registration_class_closed",
    "Too many teams are registered, please contact the organiser": "registration_full",
    "A team with this name is already registered in this class": "registration_duplicate_team",
    "Could not find this cup": "cup_not_found",
    # Pitch (result) links
    "This link is not valid (any more). Ask the organiser for a new one.": "score_link_invalid",
    "The tournament is archived": "tournament_archived",
    "This match can't be entered with this link": "score_link_wrong_match",
    "The teams of this match are not known yet": "match_teams_unknown",
    "This team can't be checked in with this link": "score_link_wrong_team",
    "This card can't be changed with this link": "score_link_wrong_card",
    # Fitting the groups to the registered teams
    "Only the groups of a class can be fitted to its teams": "fit_no_class",
    "Only a stage with round robin groups can be fitted": "fit_not_groups",
    "The groups already have teams: fit them before the draw": "fit_already_drawn",
    "The class has more stages than groups and playoffs: change them on the stages page": (
        "fit_more_stages"
    ),
    "A playoff isn't filled from the groups only: change the groups on the stages page": (
        "fit_playoff_other_inputs"
    ),
    "The class needs at least 2 teams": "fit_too_few_teams",
    "A group has between 2 and 10 teams": "fit_group_size",
    # Group draw
    "The stage has no groups": "draw_no_groups",
    "Teams can only be drawn into round robin or swiss groups": "draw_wrong_stage",
    "All teams must belong to the class of the stage": "draw_wrong_class",
    "Teams on the waitlist or rejected teams can't be drawn": "draw_not_participating",
    "Some of the teams are already in a group of this stage": "draw_already_placed",
    "There are more teams than free places in the groups": "draw_too_many_teams",
    # Participating clubs
    "A club with this name already takes part in this cup": "club_duplicate_name",
    "Some of the teams already belong to another club": "club_team_taken",
    # Registrations (organiser)
    "The team is placed in a group; remove it there before it leaves the cup": (
        "registration_team_in_group"
    ),
    "There are no teams on the waitlist": "registration_waitlist_empty",
    # Everywhere
    "Too many requests, please wait a moment and try again": "too_many_requests",
}


def error_code_headers(detail: object) -> dict[str, str]:
    code = ERROR_CODES.get(detail) if isinstance(detail, str) else None
    return {} if code is None else {ERROR_CODE_HEADER: code}
