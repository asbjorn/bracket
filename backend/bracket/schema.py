from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import declarative_base  # type: ignore[attr-defined]
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, DateTime, Enum, Float, Text

Base = declarative_base()
metadata = Base.metadata
DateTimeTZ = DateTime(timezone=True)

clubs = Table(
    "clubs",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
)

tournaments = Table(
    "tournaments",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("start_time", DateTimeTZ, nullable=False),
    Column("club_id", BigInteger, ForeignKey("clubs.id"), index=True, nullable=False),
    Column("dashboard_public", Boolean, nullable=False),
    Column("logo_path", String, nullable=True),
    Column("dashboard_endpoint", String, nullable=True, index=True, unique=True),
    Column("players_can_be_in_multiple_teams", Boolean, nullable=False, server_default="f"),
    Column("auto_assign_courts", Boolean, nullable=False, server_default="f"),
    Column("duration_minutes", Integer, nullable=False, server_default="15"),
    Column("margin_minutes", Integer, nullable=False, server_default="5"),
    # Scheduling: minimum time between the end of a team's match and its next match, and time
    # between the last match of a stage and the first match of the next stage of a class
    Column("min_rest_minutes", Integer, nullable=False, server_default="0"),
    Column("stage_buffer_minutes", Integer, nullable=False, server_default="10"),
    Column("walkover_goals", Integer, nullable=False, server_default="3"),
    # Discipline (13+): matches suspended per red card; yellow cards that give a suspension
    Column("suspension_matches_per_red", Integer, nullable=False, server_default="1"),
    Column("yellow_cards_for_suspension", Integer, nullable=True),
    # Public banner, e.g. a weather warning: text, "INFO" or "WARNING", shown until (optional)
    Column("announcement_text", Text, nullable=True),
    Column("announcement_level", Text, nullable=True),
    Column("announcement_until", DateTimeTZ, nullable=True),
    # The rules of the cup, shown on a public page
    Column("rules_text", Text, nullable=True),
    Column(
        "status",
        Enum(
            "OPEN",
            "ARCHIVED",
            name="tournament_status",
        ),
        nullable=False,
        server_default="OPEN",
        index=True,
    ),
    # Minutes after a class's last match until its prize ceremony (suggestion)
    Column("ceremony_offset_minutes", Integer, nullable=False, server_default="15"),
)

categories = Table(
    "categories",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", Text, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("age", Integer, nullable=True),
    Column("results_public", Boolean, nullable=False, server_default="t"),
    # Overrides of the tournament defaults for matches of this class
    Column("duration_minutes", Integer, nullable=True),
    Column("margin_minutes", Integer, nullable=True),
    Column("min_rest_minutes", Integer, nullable=True),
    # e.g. "7v7": matches of this class are only scheduled on courts of this format
    Column("game_format", Text, nullable=True),
    # Public sign-up: open until the deadline; beyond `max_teams` teams go to the waitlist
    Column("registration_open", Boolean, nullable=False, server_default="f"),
    Column("registration_deadline", DateTimeTZ, nullable=True),
    Column("max_teams", Integer, nullable=True),
    Column("entry_fee", Integer, nullable=True),  # NOK per team
    # NULL: the default for the age (see max_matches_per_day_for_age)
    Column("max_matches_per_day", Integer, nullable=True),
    UniqueConstraint("tournament_id", "name"),
    # BOYS, GIRLS or MIXED (NULL: not given), with a note, e.g. "girls may play a year down"
    Column("kind", Text, nullable=True),
    Column("kind_note", Text, nullable=True),
)

# The periods in which matches can be played, e.g. one per day; a lunch break is the gap between
# two periods on the same day
time_windows = Table(
    "time_windows",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("start_time", DateTimeTZ, nullable=False),
    Column("end_time", DateTimeTZ, nullable=False),
    # Both NULL: a window of the cup. Otherwise the opening hours of one pitch or the days and
    # hours of one class.
    Column(
        "court_id",
        BigInteger,
        ForeignKey("courts.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    ),
    Column(
        "category_id",
        BigInteger,
        ForeignKey("categories.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    ),
    CheckConstraint(
        "court_id IS NULL OR category_id IS NULL", name="time_windows_court_or_category_check"
    ),
)

stages = Table(
    "stages",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="false"),
    Column("category_id", BigInteger, ForeignKey("categories.id"), index=True, nullable=True),
)

stage_items = Table(
    "stage_items",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", Text, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("stage_id", BigInteger, ForeignKey("stages.id"), index=True, nullable=False),
    Column("team_count", Integer, nullable=False),
    Column("ranking_id", BigInteger, ForeignKey("rankings.id"), nullable=False),
    Column(
        "type",
        Enum(
            "SINGLE_ELIMINATION",
            "SWISS",
            "ROUND_ROBIN",
            name="stage_type",
        ),
        nullable=False,
    ),
)

STAGE_ITEM_INPUT_KIND_CHECK = (
    "(best_from_stage_id IS NULL AND best_rank IS NULL"
    " AND (winner_from_stage_item_id IS NULL) = (winner_position IS NULL))"
    " OR (best_from_stage_id IS NOT NULL AND best_rank IS NOT NULL"
    " AND winner_position IS NOT NULL AND winner_from_stage_item_id IS NULL)"
)

stage_item_inputs = Table(
    "stage_item_inputs",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("slot", Integer, nullable=False),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column(
        "stage_item_id",
        BigInteger,
        ForeignKey("stage_items.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("team_id", BigInteger, ForeignKey("teams.id"), nullable=True),
    Column("winner_from_stage_item_id", BigInteger, ForeignKey("stage_items.id"), nullable=True),
    Column("winner_position", Integer, nullable=True),
    Column("points", Float, nullable=False, server_default="0"),
    Column("wins", Integer, nullable=False, server_default="0"),
    Column("draws", Integer, nullable=False, server_default="0"),
    Column("losses", Integer, nullable=False, server_default="0"),
    Column("goals_for", Integer, nullable=False, server_default="0"),
    Column("goals_against", Integer, nullable=False, server_default="0"),
    # Place in the ranking of the stage item (1 = first), after applying the tiebreakers
    Column("position", Integer, nullable=True),
    # The `best_rank`-th best team at `winner_position` of all groups in `best_from_stage_id`,
    # e.g. the 2 best third placed teams
    Column("best_from_stage_id", BigInteger, ForeignKey("stages.id"), nullable=True),
    Column("best_rank", Integer, nullable=True),
    UniqueConstraint("stage_item_id", "team_id"),
    UniqueConstraint("stage_item_id", "winner_from_stage_item_id", "winner_position"),
    # Every row is one kind of input (empty, team, group placing or best placed); a team can be
    # set on top of a placing. Keeps rows from ending up as something no code can read.
    CheckConstraint(STAGE_ITEM_INPUT_KIND_CHECK, name="stage_item_inputs_kind_check"),
    # Drawing of lots (manual, lower is better) as the last tiebreaker
    Column("lot_number", Integer, nullable=True),
)

rounds = Table(
    "rounds",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", Text, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("is_draft", Boolean, nullable=False),
    Column("stage_item_id", BigInteger, ForeignKey("stage_items.id"), nullable=False),
)


matches = Table(
    "matches",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("start_time", DateTimeTZ, nullable=True),
    Column("duration_minutes", Integer, nullable=True),
    Column("margin_minutes", Integer, nullable=True),
    Column("custom_duration_minutes", Integer, nullable=True),
    Column("custom_margin_minutes", Integer, nullable=True),
    Column("round_id", BigInteger, ForeignKey("rounds.id"), nullable=False),
    Column("stage_item_input1_id", BigInteger, ForeignKey("stage_item_inputs.id"), nullable=True),
    Column("stage_item_input2_id", BigInteger, ForeignKey("stage_item_inputs.id"), nullable=True),
    Column("stage_item_input1_conflict", Boolean, nullable=False),
    Column("stage_item_input2_conflict", Boolean, nullable=False),
    Column(
        "stage_item_input1_winner_from_match_id",
        BigInteger,
        ForeignKey("matches.id"),
        nullable=True,
    ),
    Column(
        "stage_item_input2_winner_from_match_id",
        BigInteger,
        ForeignKey("matches.id"),
        nullable=True,
    ),
    # Third place match: the inputs are the losers of the semifinals
    Column(
        "stage_item_input1_loser_from_match_id",
        BigInteger,
        ForeignKey("matches.id"),
        nullable=True,
    ),
    Column(
        "stage_item_input2_loser_from_match_id",
        BigInteger,
        ForeignKey("matches.id"),
        nullable=True,
    ),
    Column("court_id", BigInteger, ForeignKey("courts.id"), nullable=True),
    Column("stage_item_input1_score", Integer, nullable=False),
    Column("stage_item_input2_score", Integer, nullable=False),
    Column("position_in_schedule", Integer, nullable=True),
    # Kick-off: a started match keeps its time and pitch when the schedule is changed
    Column("started_at", DateTimeTZ, nullable=True),
    Column("played", Boolean, nullable=False, server_default="f"),
    Column(
        "result_type",
        Enum("NORMAL", "EXTRA_TIME", "PENALTIES", "WALKOVER", name="match_result_type"),
        nullable=False,
        server_default="NORMAL",
    ),
    Column("stage_item_input1_penalties", Integer, nullable=True),
    Column("stage_item_input2_penalties", Integer, nullable=True),
)

# Clubs that take part in a cup with one or more teams (not the organiser's clubs, which own
# tournaments)
participating_clubs = Table(
    "participating_clubs",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Index(
        "ix_participating_clubs_tournament_id_lower_name",
        "tournament_id",
        text("lower(name)"),
        unique=True,
    ),
    # The club's teams never play at the same time (shared coaches or players)
    Column("no_overlap", Boolean, nullable=False, server_default="f"),
)

teams = Table(
    "teams",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column("active", Boolean, nullable=False, index=True, server_default="t"),
    Column("elo_score", Float, nullable=False, server_default="0"),
    Column("swiss_score", Float, nullable=False, server_default="0"),
    Column("wins", Integer, nullable=False, server_default="0"),
    Column("draws", Integer, nullable=False, server_default="0"),
    Column("losses", Integer, nullable=False, server_default="0"),
    Column("logo_path", String, nullable=True),
    Column("category_id", BigInteger, ForeignKey("categories.id"), index=True, nullable=True),
    # The club the team plays for (e.g. "Brann" for "Brann 2"); keeps clubs apart in the draw
    Column(
        "club_id",
        BigInteger,
        ForeignKey("participating_clubs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    ),
    # A withdrawn team loses its remaining matches by walkover
    Column("withdrawn", Boolean, nullable=False, server_default="f"),
    Column("checked_in", Boolean, nullable=False, server_default="f"),
    # APPROVED / REGISTERED teams take part; WAITLIST and REJECTED teams don't
    Column("registration_status", Text, nullable=False, index=True, server_default="APPROVED"),
    # Players in the squad, e.g. for counting medals
    Column("squad_size", Integer, nullable=True),
)

# Contact details of a registered team: personal data, only for the organiser
team_registrations = Table(
    "team_registrations",
    metadata,
    Column("team_id", BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("contact_name", Text, nullable=True),
    Column("contact_email", Text, nullable=True),
    Column("contact_phone", Text, nullable=True),
    Column("comment", Text, nullable=True),
    Column("registered_at", DateTimeTZ, nullable=True),
    Column("paid", Boolean, nullable=False, server_default="f"),
    Column("squad_reported", Boolean, nullable=False, server_default="f"),
)

players = Table(
    "players",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column("elo_score", Float, nullable=False),
    Column("swiss_score", Float, nullable=False),
    Column("wins", Integer, nullable=False),
    Column("draws", Integer, nullable=False),
    Column("losses", Integer, nullable=False),
    Column("active", Boolean, nullable=False, index=True, server_default="t"),
)

users = Table(
    "users",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("email", String, nullable=False, index=True, unique=True),
    Column("name", String, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column(
        "account_type",
        Enum(
            "REGULAR",
            "DEMO",
            name="account_type",
        ),
        nullable=False,
    ),
)

users_x_clubs = Table(
    "users_x_clubs",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("club_id", BigInteger, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column(
        "relation",
        Enum(
            "OWNER",
            "COLLABORATOR",
            name="user_x_club_relation",
        ),
        nullable=False,
        default="OWNER",
    ),
)

players_x_teams = Table(
    "players_x_teams",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
)

courts = Table(
    "courts",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", Text, nullable=False),
    # e.g. "7v7"; courts without a format can be used for any class
    Column("game_format", Text, nullable=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), nullable=False, index=True),
    # A part of a split pitch (e.g. a 7v7 half of an 11v11 pitch): the full pitch
    Column(
        "parent_court_id",
        BigInteger,
        ForeignKey("courts.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    ),
)

rankings = Table(
    "rankings",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("win_points", Float, nullable=False),
    Column("draw_points", Float, nullable=False),
    Column("loss_points", Float, nullable=False),
    Column("add_score_points", Boolean, nullable=False),
    # Applied in this order when teams have the same number of points
    Column(
        "tiebreakers",
        ARRAY(Text),
        nullable=False,
        server_default=text("'{GOAL_DIFFERENCE,GOALS_SCORED,HEAD_TO_HEAD}'::text[]"),
    ),
    # Fair play tiebreaker: penalty points per card (fewer is better)
    Column("fair_play_yellow_points", Integer, nullable=False, server_default="1"),
    Column("fair_play_red_points", Integer, nullable=False, server_default="3"),
)


# Links for entering results without an account, e.g. as a QR code at a pitch. Only the hash
# of the token is stored; the token itself is shown once when the link is created.
score_links = Table(
    "score_links",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    # Only this court; NULL: the whole tournament
    Column("court_id", BigInteger, ForeignKey("courts.id", ondelete="CASCADE"), nullable=True),
    Column("name", Text, nullable=False),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("expires_at", DateTimeTZ, nullable=False),
    Column("revoked_at", DateTimeTZ, nullable=True),
)

# Messages from the pitches to the organiser on match day, e.g. "running 10 minutes late"
match_day_notices = Table(
    "match_day_notices",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("court_id", BigInteger, ForeignKey("courts.id", ondelete="SET NULL"), nullable=True),
    Column(
        "score_link_id",
        BigInteger,
        ForeignKey("score_links.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("delay_minutes", Integer, nullable=True),
    Column("message", Text, nullable=False, server_default=""),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("resolved", Boolean, nullable=False, server_default="f"),
)

# Referees and match hosts (kampverter). Phone and email are personal data: organiser only.
officials = Table(
    "officials",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("age", Integer, nullable=True),
    Column("level", Text, nullable=True),
    Column("club_name", Text, nullable=True),
    Column("phone", Text, nullable=True),
    Column("email", Text, nullable=True),
    # REFEREE or HOST
    Column("role", Text, nullable=False, server_default="REFEREE"),
    Column("fee_per_match", Integer, nullable=False, server_default="0"),
    Column("fee_per_day", Integer, nullable=False, server_default="0"),
    Column("active", Boolean, nullable=False, server_default="t"),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
)

# Who refs a match: one REFEREE and any number of ASSISTANTs
match_officials = Table(
    "match_officials",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "match_id",
        BigInteger,
        ForeignKey("matches.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column(
        "official_id",
        BigInteger,
        ForeignKey("officials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("role", Text, nullable=False, server_default="REFEREE"),
    UniqueConstraint("match_id", "official_id"),
    Index(
        "ix_match_officials_one_referee",
        "match_id",
        unique=True,
        postgresql_where=text("role = 'REFEREE'"),
    ),
)

# Match host (kampvert) of a court during a period
court_hosts = Table(
    "court_hosts",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("court_id", BigInteger, ForeignKey("courts.id", ondelete="CASCADE"), nullable=False),
    Column(
        "official_id",
        BigInteger,
        ForeignKey("officials.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("start_time", DateTimeTZ, nullable=False),
    Column("end_time", DateTimeTZ, nullable=False),
)

# Cards in a match (only classes from 13 years with public results)
match_cards = Table(
    "match_cards",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column(
        "match_id",
        BigInteger,
        ForeignKey("matches.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("team_id", BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("player_name", Text, nullable=False),
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="SET NULL"), nullable=True),
    # YELLOW, YELLOW_RED (second yellow, counts as red) or RED
    Column("card_type", Text, nullable=False),
    Column("minute", Integer, nullable=True),
    Column("note", Text, nullable=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
)

# The jury's log; a decision about a card can change its suspension
jury_decisions = Table(
    "jury_decisions",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("match_id", BigInteger, ForeignKey("matches.id", ondelete="SET NULL"), nullable=True),
    Column("team_id", BigInteger, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
    Column("card_id", BigInteger, ForeignKey("match_cards.id", ondelete="SET NULL"), nullable=True),
    Column("text", Text, nullable=False),
    # Matches added to (or removed from, when negative) the suspension of the card
    Column("suspension_change", Integer, nullable=False, server_default="0"),
    Column("decided_at", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("decided_by", BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    # Jury members who took the decision
    Column("member_ids", ARRAY(BigInteger), nullable=False, server_default="{}"),
)


# Cup facts that are only needed for the application to the district (krets), e.g. the jury.
# Contact details are personal data: organiser only.
tournament_details = Table(
    "tournament_details",
    metadata,
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("organiser_club", Text, nullable=True),
    Column("contact_name", Text, nullable=True),
    Column("contact_phone", Text, nullable=True),
    Column("contact_email", Text, nullable=True),
    Column("jury_chair_name", Text, nullable=True),
    Column("jury_chair_phone", Text, nullable=True),
    Column("venue", Text, nullable=True),
    Column("rules_summary", Text, nullable=True),
    Column("notes", Text, nullable=True),
    # Language of the emails to team contacts: "nb" (default) or "en"
    Column("email_language", Text, nullable=True),
)

# Emails to team contacts: a queue (PENDING, SENDING) and a log (SENT, FAILED). The same
# `dedupe_key` is never sent twice, e.g. the same announcement to the same team.
notifications_sent = Table(
    "notifications_sent",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("team_id", BigInteger, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True),
    Column("kind", Text, nullable=False),
    Column("dedupe_key", Text, nullable=False),
    Column("recipient", Text, nullable=False),
    Column("reply_to", Text, nullable=True),
    Column("subject", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="PENDING", index=True),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("error", Text, nullable=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    # When a process started sending it; after 10 minutes another process may retry
    Column("claimed_at", DateTimeTZ, nullable=True),
    Column("sent_at", DateTimeTZ, nullable=True),
    UniqueConstraint("tournament_id", "dedupe_key"),
)


# Two teams that must never play at the same time (they share coaches or players)
team_conflicts = Table(
    "team_conflicts",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("team1_id", BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("team2_id", BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    UniqueConstraint("team1_id", "team2_id"),
    CheckConstraint("team1_id < team2_id", name="team_conflicts_ordered"),
)

# The cup's jury (NFF: at least three members, at most one per club)
jury_members = Table(
    "jury_members",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("club_name", Text, nullable=True),
    Column("phone", Text, nullable=True),
    # CHAIR or MEMBER
    Column("role", Text, nullable=False, server_default="MEMBER"),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
)
