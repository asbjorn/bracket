from sqlalchemy import Column, ForeignKey, Integer, String, Table, UniqueConstraint, func, text
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
    UniqueConstraint("tournament_id", "name"),
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
    # The club the team plays for, e.g. "Brann" for "Brann 2"; used in the group draw
    Column("club_name", String, nullable=True),
    # A withdrawn team loses its remaining matches by walkover
    Column("withdrawn", Boolean, nullable=False, server_default="f"),
    Column("checked_in", Boolean, nullable=False, server_default="f"),
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
