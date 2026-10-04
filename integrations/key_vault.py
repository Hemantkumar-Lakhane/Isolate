"""
integrations/key_vault.py
==========================
Encrypted credential storage using Fernet symmetric encryption.
All client API keys (HubSpot, Stripe, etc.) are encrypted before DB storage.

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Optional

import structlog
from cryptography.fernet import Fernet, InvalidToken

log = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Vault Key Setup
# ─────────────────────────────────────────────────────────────────────────────
# In production: store VAULT_KEY in a secrets manager (AWS SSM, GCP Secret Manager)
# For development: auto-generate and persist in .env

# ─────────────────────────────────────────────────────────────────────────────
# Vault Key Setup — MultiFernet for seamless key rotation
# ─────────────────────────────────────────────────────────────────────────────
# To rotate keys:
#   1. Generate a new key: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   2. Set VAULT_ENCRYPTION_KEY=new_key,old_key (comma-separated, newest first)
#   3. On next read, old data decrypts with old_key; on next write it's re-encrypted with new_key
#   4. Once all old data has been read+written, remove old_key from the env var

from cryptography.fernet import Fernet, MultiFernet, InvalidToken

_VAULT_KEY_ENV = "VAULT_ENCRYPTION_KEY"


def _build_multi_fernet() -> MultiFernet:
    """
    Build a MultiFernet from the VAULT_ENCRYPTION_KEY environment variable.
    Supports comma-separated list of keys for rotation:
      VAULT_ENCRYPTION_KEY=new_key,old_key1,old_key2
    First key = current (used for encryption).
    Additional keys = old (used for decryption only).
    """
    keys_str = os.getenv(_VAULT_KEY_ENV, "").strip()
    if not keys_str:
        new_key = Fernet.generate_key()
        log.warning(
            "VAULT_ENCRYPTION_KEY not set — generated ephemeral key. "
            "Set this in .env to persist encrypted credentials across restarts.",
            key=new_key.decode(),
        )
        return MultiFernet([Fernet(new_key)])

    key_list = [k.strip() for k in keys_str.split(",") if k.strip()]
    try:
        fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in key_list]
        if len(fernets) > 1:
            log.info("MultiFernet initialized with key rotation support", num_keys=len(fernets))
        return MultiFernet(fernets)
    except Exception as e:
        log.error("Invalid VAULT_ENCRYPTION_KEY format", error=str(e))
        raise ValueError(f"Cannot initialize encryption: {e}")


_MULTI_FERNET = _build_multi_fernet()




# ─────────────────────────────────────────────────────────────────────────────
# Encryption / Decryption
# ─────────────────────────────────────────────────────────────────────────────

def encrypt_credentials(credentials: dict) -> str:
    """
    Serialize credentials dict to JSON, encrypt with Fernet, return base64 string.
    Safe to store in PostgreSQL TEXT column.
    """
    try:
        json_bytes = json.dumps(credentials).encode("utf-8")
        encrypted = _MULTI_FERNET.encrypt(json_bytes)
        return encrypted.decode("utf-8")
    except Exception as e:
        log.error("Credential encryption failed", error=str(e))
        raise ValueError(f"Failed to encrypt credentials: {e}")


def decrypt_credentials(encrypted_data: str) -> dict:
    """
    Decrypt a Fernet-encrypted credentials string back to dict.
    Raises ValueError if decryption fails (wrong key or tampered data).
    """
    try:
        decrypted_bytes = _MULTI_FERNET.decrypt(encrypted_data.encode("utf-8"))
        return json.loads(decrypted_bytes.decode("utf-8"))
    except InvalidToken:
        log.error("Credential decryption failed — wrong key or tampered data")
        raise ValueError("Cannot decrypt credentials: invalid token")
    except Exception as e:
        log.error("Credential decryption error", error=str(e))
        raise ValueError(f"Failed to decrypt credentials: {e}")


def rotate_encryption(old_encrypted_data: str, new_key: str) -> str:
    """
    Re-encrypt data under a new key.
    
    Usage during key rotation:
    1. Set VAULT_ENCRYPTION_KEY=new_key,old_key in env
    2. Read all credentials (MultiFernet decrypts with old_key)
    3. Call this to force re-encryption with the new_key only
    4. Store the result
    5. Once all records are updated, remove old_key from env
    """
    new_fernet = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)
    decrypted = _MULTI_FERNET.decrypt(old_encrypted_data.encode())
    return new_fernet.encrypt(decrypted).decode()


def mask_credentials(credentials: dict) -> dict:
    """Return credentials with sensitive values masked for display."""
    masked = {}
    sensitive_keys = {"api_key", "secret_key", "access_token", "bot_token", "password",
                      "client_secret", "private_key", "refresh_token"}
    for k, v in credentials.items():
        if k.lower() in sensitive_keys and isinstance(v, str) and len(v) > 8:
            masked[k] = v[:4] + "****" + v[-4:]
        else:
            masked[k] = v
    return masked


# ─────────────────────────────────────────────────────────────────────────────
# Credential Schema Definitions per Integration Type
# These define what fields are needed for each tool
# ─────────────────────────────────────────────────────────────────────────────

CREDENTIAL_SCHEMAS: dict[str, list[dict]] = {
    "hubspot": [
        {"key": "api_key", "label": "Private App Token", "type": "password",
         "hint": "Settings → Integrations → Private Apps → Access Token", "required": True},
        {"key": "pipeline_id", "label": "Pipeline ID", "type": "text",
         "hint": "The HubSpot deal pipeline ID to monitor", "required": False},
    ],
    "gmail": [
        {"key": "access_token", "label": "OAuth2 Access Token", "type": "password",
         "hint": "Google OAuth2 access token with gmail scope", "required": True},
        {"key": "refresh_token", "label": "OAuth2 Refresh Token", "type": "password",
         "hint": "Google OAuth2 refresh token for persistent access (optional)", "required": False},
        {"key": "client_id", "label": "Google Client ID", "type": "text",
         "hint": "Google OAuth Web Client ID (optional if set in env)", "required": False},
        {"key": "client_secret", "label": "Google Client Secret", "type": "password",
         "hint": "Google OAuth Web Client Secret (optional if set in env)", "required": False},
        {"key": "sender_alias", "label": "Sender Email", "type": "text",
         "hint": "The email address to send from (e.g. cs@yourcompany.com)", "required": False},
        {"key": "sender_name", "label": "Sender Display Name", "type": "text",
         "hint": "Name shown to email recipients", "required": False},
    ],
    "slack": [
        {"key": "bot_token", "label": "Bot OAuth Token", "type": "password",
         "hint": "Slack Bot User OAuth Token (xoxb-...)", "required": True},
        {"key": "cs_channel", "label": "CS Alerts Channel", "type": "text",
         "hint": "e.g. #cs-alerts", "required": True},
        {"key": "sales_channel", "label": "Sales Channel", "type": "text",
         "hint": "e.g. #sales", "required": False},
    ],
    "stripe": [
        {"key": "secret_key", "label": "Secret Key", "type": "password",
         "hint": "Stripe secret key (sk_live_... or sk_test_...)", "required": True},
    ],
    "openai": [
        {"key": "api_key", "label": "OpenAI API Key", "type": "password",
         "hint": "Your OpenAI API key (sk-...)", "required": True},
    ],
    "anthropic": [
        {"key": "api_key", "label": "Anthropic API Key", "type": "password",
         "hint": "Your Anthropic API key (sk-ant-...)", "required": True},
    ],
    "google": [
        {"key": "api_key", "label": "Google AI API Key", "type": "password",
         "hint": "Google AI Studio API key", "required": True},
    ],
    "groq": [
        {"key": "api_key", "label": "Groq API Key", "type": "password",
         "hint": "Your Groq API key (gsk_...)", "required": True},
    ],
    "generic_rest": [
        {"key": "api_key", "label": "API Key", "type": "password",
         "hint": "API key for authentication", "required": False},
        {"key": "bearer_token", "label": "Bearer Token", "type": "password",
         "hint": "Bearer token for Authorization header", "required": False},
        {"key": "username", "label": "Username (Basic Auth)", "type": "text",
         "hint": "Username for basic authentication", "required": False},
        {"key": "password", "label": "Password (Basic Auth)", "type": "password",
         "hint": "Password for basic authentication", "required": False},
    ],
}


def get_credential_schema(tool_name: str) -> list[dict]:
    """Return the credential field definitions for a given tool type."""
    return CREDENTIAL_SCHEMAS.get(tool_name, CREDENTIAL_SCHEMAS["generic_rest"])