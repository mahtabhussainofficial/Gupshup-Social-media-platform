"""Sending email.

EMAIL_BACKEND=console  -> the email is printed in the terminal (default, zero setup).
EMAIL_BACKEND=smtp     -> sent through the SMTP server in your settings.
"""
import logging
import smtplib
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger("app.mailer")


def send_email(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if settings.email_backend == "smtp":
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
    else:
        logger.warning("EMAIL (console backend)\nTo: %s\nSubject: %s\n\n%s", to, subject, body)


def send_password_reset_email(to: str, reset_link: str) -> None:
    """Runs as a background task, so the HTTP response is not delayed by SMTP.
    Errors are logged, not raised: nobody is waiting for this response any more."""
    body = (
        f"Someone asked to reset the password for your {settings.app_name} account.\n\n"
        f"Open this link to choose a new password (valid for "
        f"{settings.reset_token_expire_minutes} minutes):\n{reset_link}\n\n"
        "If this was not you, ignore this email. Your password stays the same."
    )
    try:
        send_email(to, f"Reset your {settings.app_name} password", body)
    except Exception:
        logger.exception("Could not send password reset email")
