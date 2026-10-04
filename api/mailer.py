"""
api/mailer.py
=============
System (transactional) email integration point.

This is intentionally a thin, honest boundary around the Python standard
library (``smtplib`` + ``email.message``) — NO new third-party dependency and
NO fake delivery. Behavior:

  • If SMTP is configured (SMTP_HOST + SMTP_FROM present), email is really sent.
  • If SMTP is NOT configured, we do NOT pretend to send. We log that delivery
    was skipped (never logging the token/link) and report the real status back
    to the caller, which decides whether the dev-only inspection path applies.

Distinct from ``integrations/connectors.py`` GmailConnector, which sends
*per-tenant workflow* customer emails via the Gmail API. That path is for
tenant business email; this module is for platform/system email (e.g. password
reset) and shares nothing with it by design.

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

import structlog

log = structlog.get_logger()


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def is_email_configured() -> bool:
    """True only when the minimum SMTP settings are present."""
    return bool(_env("SMTP_HOST") and _env("SMTP_FROM"))


def app_base_url() -> str:
    """Public base URL of the frontend, used to build reset links."""
    return _env("APP_BASE_URL", "http://localhost:5173").rstrip("/")


def is_production() -> bool:
    return _env("ENVIRONMENT", "development").lower() == "production"


def dev_token_inspection_enabled() -> bool:
    """
    The dev-only reset-link inspection path is allowed ONLY when ALL hold:
      1. ENVIRONMENT is not "production"
      2. ALLOW_DEV_TOKEN_INSPECTION is explicitly "true" (never defaulted on)
      3. real email delivery is NOT configured
    In production this is always False regardless of the other flags.
    """
    if is_production():
        return False
    if _env("ALLOW_DEV_TOKEN_INSPECTION").lower() != "true":
        return False
    return not is_email_configured()


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """
    Attempt to send a password-reset email.

    Returns True if an email was actually handed off to an SMTP server,
    False if delivery was skipped (unconfigured) or failed. The raw reset URL
    is passed to the SMTP server only — it is never logged here.
    """
    if not is_email_configured():
        # Honest non-delivery: do not fake success, and never log the URL/token.
        log.info(
            "password_reset.email_skipped",
            reason="SMTP not configured (SMTP_HOST/SMTP_FROM unset)",
            recipient_domain=to_email.split("@")[-1] if "@" in to_email else "",
        )
        return False

    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", "587") or "587")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASSWORD")
    sender = _env("SMTP_FROM")
    use_starttls = _env("SMTP_STARTTLS", "true").lower() != "false"

    msg = EmailMessage()
    msg["Subject"] = "Reset your SMBFlow password"
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(
        "We received a request to reset your SMBFlow password.\n\n"
        f"Use the link below to choose a new password:\n{reset_url}\n\n"
        "This link expires shortly and can be used only once. If you did not "
        "request a password reset, you can safely ignore this email — your "
        "password will not change."
    )

    try:
        if port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
                if user:
                    server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                if use_starttls:
                    server.starttls(context=ssl.create_default_context())
                if user:
                    server.login(user, password)
                server.send_message(msg)
        # Log delivery WITHOUT the URL/token.
        log.info(
            "password_reset.email_sent",
            recipient_domain=to_email.split("@")[-1] if "@" in to_email else "",
        )
        return True
    except Exception as e:
        # Never include the reset URL/token in the error log.
        log.error("password_reset.email_failed", error=str(e))
        return False
