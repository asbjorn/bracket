"""
Sending email over SMTP (standard library only). Configured with the `SMTP_*` settings;
without them email is disabled. Tests replace the sender with `set_email_sender`.
"""

import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from bracket.config import config

SMTP_TIMEOUT_SECONDS = 20


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmtpSender:
    def send(self, message: EmailMessage) -> None:
        assert config.smtp_host is not None
        context = ssl.create_default_context()
        smtp: smtplib.SMTP
        if config.smtp_ssl:
            smtp = smtplib.SMTP_SSL(
                config.smtp_host, config.smtp_port, context=context, timeout=SMTP_TIMEOUT_SECONDS
            )
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=SMTP_TIMEOUT_SECONDS)
        with smtp:
            if not config.smtp_ssl and config.smtp_starttls:
                smtp.starttls(context=context)
            if config.smtp_username and config.smtp_password:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)


_sender_override: list[EmailSender | None] = []


def set_email_sender(sender: EmailSender | None) -> None:
    """For tests: send with `sender` instead of SMTP (`None` restores the configuration)."""
    _sender_override.clear()
    if sender is not None:
        _sender_override.append(sender)


def get_email_sender() -> EmailSender | None:
    """The sender to use, or `None` when email isn't set up."""
    if _sender_override:
        return _sender_override[0]
    return SmtpSender() if config.is_email_enabled() else None


def sender_address() -> str:
    return config.smtp_from or "bracket@localhost"
