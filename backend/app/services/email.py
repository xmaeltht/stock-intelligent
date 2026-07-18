"""Minimal SMTP email sender (standard library)."""

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings


def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email via the configured SMTP server. Raises on failure."""
    settings = get_settings()
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)
