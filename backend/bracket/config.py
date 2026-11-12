import logging
import os
import sys
from enum import auto
from typing import Annotated

import sentry_sdk
from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

from bracket.utils.redact import redact_sentry_event
from bracket.utils.types import EnumAutoStr


class Environment(EnumAutoStr):
    PRODUCTION = auto()
    DEVELOPMENT = auto()
    DEMO = auto()
    CI = auto()

    def get_log_level(self) -> int:
        return {
            Environment.CI: logging.WARNING,
            Environment.DEVELOPMENT: logging.DEBUG,
            Environment.PRODUCTION: logging.INFO,
            Environment.DEMO: logging.INFO,
        }[self]


class Config(BaseSettings):
    admin_email: str | None = None
    admin_password: str | None = None
    allow_insecure_http_sso: bool = False
    allow_user_registration: bool = True
    allow_demo_user_registration: bool = True
    captcha_secret: str | None = None
    base_url: str = "http://localhost:8400"
    cors_origin_regex: str = ""
    cors_origins: str = "*"
    jwt_secret: str
    auto_run_migrations: bool = True
    pg_dsn: PostgresDsn = PostgresDsn("postgresql://user:pass@localhost:5432/db")
    sentry_dsn: str | None = None
    serve_frontend: bool = False
    api_prefix: str = ""

    # Email to team contacts (announcements, schedule changes, registrations). Disabled unless
    # `smtp_host` and `smtp_from` are set.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    # STARTTLS on a plain connection (port 587); `smtp_ssl` for implicit TLS (port 465)
    smtp_starttls: bool = True
    smtp_ssl: bool = False

    # Reverse proxies whose X-Forwarded-For header is trusted, as a comma separated list of
    # IP addresses or networks (e.g. "10.0.0.0/8,127.0.0.1"). Empty: the direct peer is the client.
    trusted_proxies: str = ""

    def is_email_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    # Limits for regular (non-demo) accounts, see `bracket.logic.subscriptions`.
    # Teams, players, courts, stages, stage items, rounds, rankings and categories (age classes)
    # are counted per tournament, clubs per user and tournaments per club.
    limit_max_teams: int = Field(128, ge=1)
    limit_max_players: int = Field(256, ge=1)
    limit_max_clubs: int = Field(32, ge=1)
    limit_max_tournaments: int = Field(64, ge=1)
    limit_max_courts: int = Field(32, ge=1)
    limit_max_stages: int = Field(16, ge=1)
    limit_max_stage_items: int = Field(64, ge=1)
    limit_max_rounds: int = Field(64, ge=1)
    limit_max_rankings: int = Field(16, ge=1)
    limit_max_categories: int = Field(32, ge=1)

    def is_cors_enabled(self) -> bool:
        return self.cors_origins != "*"


class CIConfig(Config):
    model_config = SettingsConfigDict(env_file="ci.env")


class DevelopmentConfig(Config):
    admin_email: Annotated[str | None, Field("test@example.org")]
    admin_password: Annotated[str | None, Field("aeGhoe1ahng2Aezai0Dei6Aih6dieHoo")]
    allow_insecure_http_sso: Annotated[bool, Field(True)]
    jwt_secret: Annotated[
        str, Field("7495204c062787f257b12d03b88d80da1d338796a6449666eb634c9efbbf5fa7")
    ]

    model_config = SettingsConfigDict(env_file="dev.env")


class ProductionConfig(Config):
    model_config = SettingsConfigDict(env_file="prod.env")


class DemoConfig(Config):
    model_config = SettingsConfigDict(env_file="demo.env")


def currently_testing() -> bool:
    return "pytest" in sys.modules


environment = Environment(
    os.getenv("ENVIRONMENT", "CI" if currently_testing() else "DEVELOPMENT").upper()
)
config: Config

match environment:
    case Environment.CI:
        config = CIConfig()  # type: ignore[call-arg]
    case Environment.DEVELOPMENT:
        config = DevelopmentConfig()  # type: ignore[call-arg]
    case Environment.PRODUCTION:
        config = ProductionConfig()  # type: ignore[call-arg]
    case Environment.DEMO:
        config = DemoConfig()  # type: ignore[call-arg]


def init_sentry() -> None:
    if config.sentry_dsn:
        sentry_sdk.init(
            dsn=config.sentry_dsn,
            environment=str(environment.value),
            include_local_variables=False,
            # Result-link tokens in URLs give access: never send them to Sentry
            before_send=redact_sentry_event,
            before_breadcrumb=redact_sentry_event,
            before_send_transaction=redact_sentry_event,
        )
