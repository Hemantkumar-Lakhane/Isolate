"""
integrations/registry.py
========================
Unified Provider & Capability Registry for SMBFlow Tool Connections.
Defines all supported integration providers, capability-to-scope mappings,
authentication requirements, error normalizations, and scope levels (personal vs org).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import structlog

log = structlog.get_logger()


class AuthType(str, Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    CUSTOM = "custom"


class ScopeLevel(str, Enum):
    PERSONAL = "personal"         # Tied to individual user (e.g., Personal LinkedIn, Personal Gmail)
    ORGANIZATION = "organization" # Shared across organization (e.g., Slack Workspace, HubSpot CRM, Stripe)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConnectionStatus(str, Enum):
    NOT_CONNECTED = "not_connected"
    CONNECTING = "connecting"
    AUTHORIZING = "authorizing"
    VERIFYING = "verifying"
    CONNECTED = "connected"
    TESTING = "testing"
    REFRESHING = "refreshing"
    REAUTH_REQUIRED = "reauth_required"
    PERMISSION_REQUIRED = "permission_required"
    ERROR = "error"


@dataclass
class CapabilityDefinition:
    id: str
    name: str
    description: str
    category: str
    required_scopes: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    requires_hitl: bool = False
    requires_special_approval: bool = False  # e.g., LinkedIn organization page posting approval


@dataclass
class ProviderDefinition:
    tool_name: str
    display_name: str
    category: str
    description: str
    auth_type: AuthType
    scope_level: ScopeLevel
    capabilities: List[CapabilityDefinition]
    
    # OAuth configuration (if auth_type == OAUTH2)
    oauth_authorize_url: Optional[str] = None
    oauth_token_url: Optional[str] = None
    oauth_userinfo_url: Optional[str] = None
    client_id_env: Optional[str] = None
    client_secret_env: Optional[str] = None
    default_scopes: List[str] = field(default_factory=list)
    scope_separator: str = " "
    supports_pkce: bool = False
    
    # API key / token configuration
    required_fields: List[str] = field(default_factory=list)
    config_fields: List[str] = field(default_factory=list)
    
    # Visual and catalog meta
    icon_key: str = ""
    docs_url: Optional[str] = None
    enabled: bool = True

    def get_client_id(self) -> Optional[str]:
        if not self.client_id_env:
            return None
        # Always check os.environ and reload .env if needed
        val = os.getenv(self.client_id_env, "").strip()
        if not val:
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
                val = os.getenv(self.client_id_env, "").strip()
            except Exception:
                pass
        # Check provider specific aliases
        if not val and self.tool_name == "google_workspace":
            val = os.getenv("GMAIL_CLIENT_ID", "").strip() or os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        if not val and self.tool_name == "linkedin":
            val = os.getenv("LINKEDIN_CLIENT_ID", "").strip() or os.getenv("LINKEDIN_OAUTH_CLIENT_ID", "").strip()
        return val or None

    def get_client_secret(self) -> Optional[str]:
        if not self.client_secret_env:
            return None
        val = os.getenv(self.client_secret_env, "").strip()
        if not val:
            try:
                from dotenv import load_dotenv
                load_dotenv(override=True)
                val = os.getenv(self.client_secret_env, "").strip()
            except Exception:
                pass
        # Check provider specific aliases
        if not val and self.tool_name == "google_workspace":
            val = os.getenv("GMAIL_CLIENT_SECRET", "").strip() or os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        if not val and self.tool_name == "linkedin":
            val = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip() or os.getenv("LINKEDIN_OAUTH_CLIENT_SECRET", "").strip()
        return val or None

    def resolve_scopes_for_capabilities(self, capability_ids: Optional[List[str]] = None) -> List[str]:
        """
        Least-privilege scope resolver.
        Maps only the requested capabilities to their verified provider OAuth permissions.
        Supports normalized aliases (e.g., 'gmail.read' -> 'google.gmail.read').
        """
        resolved: set[str] = set(self.default_scopes)
        if not capability_ids:
            # If no specific capabilities requested, return baseline identity scopes
            return sorted(list(resolved))

        alias_map = {
            "gmail.read": "google.gmail.read",
            "gmail.read_inbox": "google.gmail.read",
            "gmail.send": "google.gmail.send",
            "gmail.send_message": "google.gmail.send",
            "calendar.read": "google.calendar.read",
            "calendar.create": "google.calendar.create",
            "meet.read": "google.meet.read",
            "meet.transcript.read": "google.meet.transcript.read",
            "drive.read": "google.drive.read",
            "drive.write": "google.drive.write",
            "docs.read": "google.docs.read",
            "docs.write": "google.docs.write",
            "sheets.read": "google.sheets.read",
            "sheets.write": "google.sheets.write",
            "slides.read": "google.slides.read",
            "slides.write": "google.slides.write",
        }

        cap_map = {c.id: c for c in self.capabilities}
        for cid in capability_ids:
            canonical_id = alias_map.get(cid, cid)
            if canonical_id in cap_map:
                for sc in cap_map[canonical_id].required_scopes:
                    resolved.add(sc)
            elif cid in cap_map:
                for sc in cap_map[cid].required_scopes:
                    resolved.add(sc)
        return sorted(list(resolved))

    def get_missing_scopes_for_capability(self, capability_id: str, granted_scopes: List[str]) -> List[str]:
        """Check if granted scopes fulfill the capability requirements."""
        cap_map = {c.id: c for c in self.capabilities}
        if capability_id not in cap_map:
            return []
        required = cap_map[capability_id].required_scopes
        granted_set = set(granted_scopes)
        return [sc for sc in required if sc not in granted_set]


# ─────────────────────────────────────────────────────────────────────────────
# Canonical Provider Catalog
# ─────────────────────────────────────────────────────────────────────────────

PROVIDER_CATALOG: Dict[str, ProviderDefinition] = {
    "google_workspace": ProviderDefinition(
        tool_name="google_workspace",
        display_name="Google Workspace",
        category="Productivity & Communication",
        description="Unified Google connection for Gmail, Google Calendar, Google Meet Intelligence, Google Drive, Docs, Sheets, and Slides with capability-level permission controls.",
        auth_type=AuthType.OAUTH2,
        scope_level=ScopeLevel.ORGANIZATION,
        icon_key="google_workspace",
        client_id_env="GOOGLE_CLIENT_ID",
        client_secret_env="GOOGLE_CLIENT_SECRET",
        oauth_authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        oauth_token_url="https://oauth2.googleapis.com/token",
        oauth_userinfo_url="https://www.googleapis.com/oauth2/v2/userinfo",
        default_scopes=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
        capabilities=[
            # ── Gmail Capabilities ──
            CapabilityDefinition(
                id="google.gmail.read",
                name="Read Gmail Inbox",
                description="Scan and fetch inbound email messages and threads for triage and analysis.",
                category="Gmail",
                required_scopes=["https://www.googleapis.com/auth/gmail.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.gmail.send",
                name="Send Outbound Emails",
                description="Send confirmed response emails to clients via Gmail (Human approval required).",
                category="Gmail",
                required_scopes=["https://www.googleapis.com/auth/gmail.send"],
                risk_level=RiskLevel.HIGH,
                requires_hitl=True,
            ),
            # ── Calendar Capabilities ──
            CapabilityDefinition(
                id="google.calendar.read",
                name="Read Calendar Events",
                description="Check schedule availability, participant lists, and conference attachments.",
                category="Calendar",
                required_scopes=["https://www.googleapis.com/auth/calendar.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.calendar.create",
                name="Schedule Calendar Events",
                description="Book meetings, product launch consultations, and client calls.",
                category="Calendar",
                required_scopes=["https://www.googleapis.com/auth/calendar.events"],
                risk_level=RiskLevel.MEDIUM,
            ),
            # ── Google Meet & Intelligence Capabilities ──
            CapabilityDefinition(
                id="google.meet.read",
                name="Read Meeting Spaces",
                description="Retrieve Google Meet spaces and conference metadata via Google Meet REST API v2.",
                category="Meeting Intelligence",
                required_scopes=["https://www.googleapis.com/auth/meetings.space.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.meet.transcript.read",
                name="Read Meeting Transcripts",
                description="Fetch real Google Meet conference transcript records for AI analysis.",
                category="Meeting Intelligence",
                required_scopes=["https://www.googleapis.com/auth/meetings.space.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.meet.transcript.entries.read",
                name="Read Transcript Utterance Entries",
                description="Retrieve timestamped participant speech entries and speaker turns.",
                category="Meeting Intelligence",
                required_scopes=["https://www.googleapis.com/auth/meetings.space.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.meet.recording.read",
                name="Read Meeting Recordings",
                description="Access Google Meet video/audio recording metadata and drive references.",
                category="Meeting Intelligence",
                required_scopes=["https://www.googleapis.com/auth/meetings.space.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            # ── Google Drive & Docs Capabilities ──
            CapabilityDefinition(
                id="google.drive.read",
                name="Read Drive Files",
                description="Access uploaded invoices, meeting assets, and documentation stored in Drive.",
                category="Drive & Docs",
                required_scopes=["https://www.googleapis.com/auth/drive.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.drive.write",
                name="Upload & Save Drive Files",
                description="Save generated campaign assets, meeting briefs, and reports to Google Drive.",
                category="Drive & Docs",
                required_scopes=["https://www.googleapis.com/auth/drive.file"],
                risk_level=RiskLevel.MEDIUM,
            ),
            CapabilityDefinition(
                id="google.docs.read",
                name="Read Google Docs",
                description="Read structured text and tables from Google Docs.",
                category="Drive & Docs",
                required_scopes=["https://www.googleapis.com/auth/documents.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.docs.write",
                name="Create & Edit Google Docs",
                description="Generate meeting summaries, proposals, and SOP documents in Google Docs.",
                category="Drive & Docs",
                required_scopes=["https://www.googleapis.com/auth/documents"],
                risk_level=RiskLevel.MEDIUM,
            ),
            # ── Google Sheets & Slides Capabilities ──
            CapabilityDefinition(
                id="google.sheets.read",
                name="Read Google Sheets",
                description="Read rows and tabular data from Google Spreadsheets.",
                category="Sheets & Slides",
                required_scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.sheets.write",
                name="Append & Edit Google Sheets",
                description="Log workflow metrics, CRM leads, and analytics into Google Spreadsheets.",
                category="Sheets & Slides",
                required_scopes=["https://www.googleapis.com/auth/spreadsheets"],
                risk_level=RiskLevel.MEDIUM,
            ),
            CapabilityDefinition(
                id="google.slides.read",
                name="Read Google Slides",
                description="Read presentation deck structure and slide content.",
                category="Sheets & Slides",
                required_scopes=["https://www.googleapis.com/auth/presentations.readonly"],
                risk_level=RiskLevel.LOW,
            ),
            CapabilityDefinition(
                id="google.slides.write",
                name="Create & Edit Google Slides",
                description="Generate presentation decks and stakeholder slides.",
                category="Sheets & Slides",
                required_scopes=["https://www.googleapis.com/auth/presentations"],
                risk_level=RiskLevel.MEDIUM,
            ),
        ],
        config_fields=["default_calendar_id", "default_folder_id", "sender_alias", "sender_name", "queue_for_approval"],
    ),

    "linkedin": ProviderDefinition(
        tool_name="linkedin",
        display_name="LinkedIn",
        category="Social",
        description="Publish product announcements, schedule campaign posts, and analyze professional engagement.",
        auth_type=AuthType.OAUTH2,
        scope_level=ScopeLevel.PERSONAL,
        icon_key="linkedin",
        client_id_env="LINKEDIN_CLIENT_ID",
        client_secret_env="LINKEDIN_CLIENT_SECRET",
        oauth_authorize_url="https://www.linkedin.com/oauth/v2/authorization",
        oauth_token_url="https://www.linkedin.com/oauth/v2/accessToken",
        oauth_userinfo_url="https://api.linkedin.com/v2/userinfo",
        default_scopes=["openid", "profile", "email"],
        capabilities=[
            CapabilityDefinition(
                id="linkedin.profile.read",
                name="Read Profile & Identity",
                description="Retrieve connected member profile information and author URN.",
                category="Identity",
                required_scopes=["openid", "profile", "email"],
                risk_level="low",
            ),
            CapabilityDefinition(
                id="linkedin.post.create",
                name="Publish Member Posts",
                description="Publish authorized product updates and campaign content to personal profile.",
                category="Publishing",
                required_scopes=["w_member_social"],
                risk_level="medium",
            ),
            CapabilityDefinition(
                id="linkedin.organization.post.create",
                name="Publish Company Page Posts",
                description="Publish announcements to LinkedIn Company/Organization Page.",
                category="Publishing",
                required_scopes=["w_organization_social"],
                risk_level="medium",
                requires_special_approval=True,
            ),
        ],
        config_fields=["author_urn", "default_visibility"],
    ),

    "slack": ProviderDefinition(
        tool_name="slack",
        display_name="Slack Notifications",
        category="Communication",
        description="Broadcast urgent workflow alerts, coordinator notifications, and approval requests to team channels.",
        auth_type=AuthType.API_KEY,  # Bot Token or Webhook
        scope_level=ScopeLevel.ORGANIZATION,
        icon_key="slack",
        required_fields=["bot_token"],
        config_fields=["cs_alerts_channel", "sales_channel"],
        capabilities=[
            CapabilityDefinition(
                id="slack.message.send",
                name="Post Channel Messages",
                description="Post operational alerts and summary cards to Slack channels.",
                category="Messaging",
                risk_level="low",
            ),
            CapabilityDefinition(
                id="slack.alert.post",
                name="Post Risk Escalations",
                description="Post urgent supervisor approval requests with Action Center links.",
                category="Messaging",
                risk_level="medium",
            ),
            CapabilityDefinition(
                id="slack.channel.read",
                name="Read Channel History",
                description="Monitor team discussion and coordinator resolution notes.",
                category="Messaging",
                risk_level="low",
            ),
        ],
    ),

    "hubspot": ProviderDefinition(
        tool_name="hubspot",
        display_name="HubSpot CRM",
        category="CRM",
        description="Sync customer leads, enrich contact records, and advance deals through sales pipelines.",
        auth_type=AuthType.API_KEY,
        scope_level=ScopeLevel.ORGANIZATION,
        icon_key="hubspot",
        required_fields=["api_key"],
        config_fields=["pipeline_id"],
        capabilities=[
            CapabilityDefinition(
                id="hubspot.read_contacts",
                name="Read Contacts & Deals",
                description="Query CRM contacts, lead scores, and active deals.",
                category="CRM",
                risk_level="low",
            ),
            CapabilityDefinition(
                id="hubspot.create_contact",
                name="Create Inbound Leads",
                description="Insert new leads discovered through email triage and website forms.",
                category="CRM",
                risk_level="low",
            ),
            CapabilityDefinition(
                id="hubspot.update_deal",
                name="Update Pipeline Deals",
                description="Advance deal stages and record ARR values automatically.",
                category="CRM",
                risk_level="medium",
            ),
        ],
    ),

    "stripe": ProviderDefinition(
        tool_name="stripe",
        display_name="Stripe Payments & Billing",
        category="Finance",
        description="Retrieve invoice history, reconcile payments against purchase orders, and verify subscriber status.",
        auth_type=AuthType.API_KEY,
        scope_level=ScopeLevel.ORGANIZATION,
        icon_key="stripe",
        required_fields=["secret_key"],
        config_fields=[],
        capabilities=[
            CapabilityDefinition(
                id="stripe.read_customers",
                name="Read Customer Accounts",
                description="Access payment profiles and customer billing history.",
                category="Finance",
                risk_level="low",
            ),
            CapabilityDefinition(
                id="stripe.read_invoices",
                name="Read Billing Invoices",
                description="Fetch invoice PDFs and reconcile payment due dates.",
                category="Finance",
                risk_level="low",
            ),
            CapabilityDefinition(
                id="stripe.read_subscriptions",
                name="Read Subscriptions",
                description="Query active subscriptions and ARR renewal dates.",
                category="Finance",
                risk_level="low",
            ),
        ],
    ),

    "rest_api": ProviderDefinition(
        tool_name="rest_api",
        display_name="Custom REST Connector",
        category="Developer Tools",
        description="Connect arbitrary business REST APIs and custom internal services.",
        auth_type=AuthType.API_KEY,
        scope_level=ScopeLevel.ORGANIZATION,
        icon_key="webhook",
        required_fields=["base_url", "api_key"],
        config_fields=["auth_header", "auth_prefix"],
        capabilities=[
            CapabilityDefinition(
                id="rest.get_resource",
                name="Query GET Endpoints",
                description="Fetch data from custom REST APIs.",
                category="Custom API",
                risk_level="low",
            ),
            CapabilityDefinition(
                id="rest.post_resource",
                name="Write POST Endpoints",
                description="Send structured JSON payloads to external webhooks.",
                category="Custom API",
                risk_level="medium",
            ),
        ],
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Error Normalizer
# ─────────────────────────────────────────────────────────────────────────────

ERROR_CODE_MAP = {
    "invalid_grant": ("INVALID_CREDENTIALS", "Your credentials or authorization code are invalid or have expired. Please reconnect."),
    "invalid_client": ("INVALID_CLIENT_CONFIG", "Provider client ID or client secret is misconfigured. Please check server configuration."),
    "unauthorized_client": ("UNAUTHORIZED_CLIENT", "This application is not authorized to request these permissions."),
    "access_denied": ("OAUTH_DENIED", "The authorization request was cancelled or denied."),
    "insufficient_scope": ("INSUFFICIENT_SCOPE", "This integration is connected, but the requested action requires additional permissions."),
    "token_expired": ("TOKEN_EXPIRED", "Your session token has expired. Please reconnect or refresh the connection."),
    "rate_limited": ("RATE_LIMITED", "The external service is temporarily rate-limiting requests. Please try again shortly."),
    "service_unavailable": ("PROVIDER_UNAVAILABLE", "The external provider is temporarily unavailable. SMBFlow will retry automatically."),
    "invalid_token": ("INVALID_CREDENTIALS", "The stored connection token is invalid. Please reconnect the integration."),
}


def normalize_error(raw_error: str, default_code: str = "CONNECTION_ERROR") -> Dict[str, str]:
    """
    Normalizes raw technical/provider error strings into safe, user-friendly descriptions.
    Technical details should only be logged server-side.
    """
    raw_lower = (raw_error or "").lower()
    for pattern, (code, msg) in ERROR_CODE_MAP.items():
        if pattern in raw_lower:
            return {"code": code, "error_code": code, "user_message": msg}

    if "401" in raw_lower or "unauthorized" in raw_lower:
        return {"code": "INVALID_CREDENTIALS", "error_code": "INVALID_CREDENTIALS", "user_message": "Authentication failed or expired with the provider. Please reconnect."}
    if "403" in raw_lower or "forbidden" in raw_lower:
        return {"code": "INSUFFICIENT_SCOPE", "error_code": "INSUFFICIENT_SCOPE", "user_message": "Additional provider permissions are required to execute this capability."}
    if "429" in raw_lower:
        return {"code": "RATE_LIMITED", "error_code": "RATE_LIMITED", "user_message": "The service rate limit was exceeded. Please wait a moment."}
    if "timeout" in raw_lower or "timed out" in raw_lower:
        return {"code": "PROVIDER_TIMEOUT", "error_code": "PROVIDER_TIMEOUT", "user_message": "The provider API timed out. Please verify provider status."}

    return {
        "code": default_code,
        "error_code": default_code,
        "user_message": "We could not complete the integration request. Please verify your credentials or reconnect."
    }


def get_provider(tool_name: str) -> Optional[ProviderDefinition]:
    """Look up provider definition from registry."""
    if not tool_name:
        return None
    k = tool_name.lower().strip()
    if k in ["google", "google_workspace", "gmail", "meet", "calendar", "drive", "docs", "sheets", "slides", "sheet"]:
        return PROVIDER_CATALOG.get("google_workspace")
    return PROVIDER_CATALOG.get(k)


def list_providers(include_disabled: bool = False) -> List[ProviderDefinition]:
    """List all registered providers in catalog."""
    if include_disabled:
        return list(PROVIDER_CATALOG.values())
    return [p for p in PROVIDER_CATALOG.values() if p.enabled]


def find_provider_for_capability(capability_id: str) -> Optional[ProviderDefinition]:
    """Find the registered provider that exposes a given capability (supports aliases)."""
    if not capability_id:
        return None
    cid = capability_id.strip()
    # Search all capabilities
    for provider in PROVIDER_CATALOG.values():
        for cap in provider.capabilities:
            if cap.id == cid or cap.id.replace("google.", "") == cid or cid.replace("google.", "") == cap.id:
                return provider
    # Alias / prefix fallback search
    if any(cid.startswith(pfx) for pfx in ("gmail.", "google.", "calendar.", "meet.", "drive.", "docs.", "sheets.", "slides.")):
        return PROVIDER_CATALOG.get("google_workspace")
    if cid.startswith("linkedin."):
        return PROVIDER_CATALOG.get("linkedin")
    if cid.startswith("slack."):
        return PROVIDER_CATALOG.get("slack")
    if cid.startswith("hubspot."):
        return PROVIDER_CATALOG.get("hubspot")
    if cid.startswith("stripe."):
        return PROVIDER_CATALOG.get("stripe")
    if cid.startswith("rest."):
        return PROVIDER_CATALOG.get("rest_api")
    return None


async def resolve_capability_requirement(
    db: Any,
    org_id: Any,
    user_id: Optional[Any],
    capability_id: str,
) -> Dict[str, Any]:
    """
    Check if a required capability is satisfied by an active connection.
    Used by the SMBFlow workflow runtime before executing any capability action.
    """
    from db.models.core import ToolConnection
    from sqlalchemy import select

    provider = find_provider_for_capability(capability_id)
    if not provider:
        return {
            "status": "unsupported_capability",
            "capability": capability_id,
            "message": f"No provider registered for capability '{capability_id}'.",
        }

    # Query connection for organization
    target_names = [provider.tool_name]
    if provider.tool_name == "google_workspace":
        target_names.extend(["google", "gmail", "calendar", "meet", "drive"])

    stmt = select(ToolConnection).where(
        ToolConnection.organization_id == org_id,
        ToolConnection.tool_name.in_(target_names),
    )
    result = await db.execute(stmt)
    conns = result.scalars().all()

    # Match active connection considering personal vs organization scope
    matched_conn = None
    for conn in conns:
        if provider.scope_level == ScopeLevel.PERSONAL:
            if user_id and conn.user_id == user_id and conn.status == "connected":
                matched_conn = conn
                break
        else:
            if conn.status == "connected":
                matched_conn = conn
                break

    if not matched_conn:
        # Check if an error or reauth connection exists
        problem_conn = conns[0] if conns else None
        if problem_conn and problem_conn.status in ("error", "reauth_required"):
            return {
                "status": "connection_required",
                "provider": provider.tool_name,
                "provider_name": provider.display_name,
                "capability": capability_id,
                "substatus": problem_conn.status,
                "message": f"{provider.display_name} requires reconnection ({problem_conn.last_error_message or 'Authentication error'}).",
                "connect_url": f"/integrations?connect={provider.tool_name}",
            }

        return {
            "status": "connection_required",
            "provider": provider.tool_name,
            "provider_name": provider.display_name,
            "capability": capability_id,
            "message": f"{provider.display_name} must be connected before this workflow can continue.",
            "connect_url": f"/integrations?connect={provider.tool_name}",
        }

    # Verify granted scopes if connection has scope info
    if matched_conn.granted_scopes:
        missing = provider.get_missing_scopes_for_capability(capability_id, matched_conn.granted_scopes)
        if missing:
            return {
                "status": "connection_required",
                "provider": provider.tool_name,
                "provider_name": provider.display_name,
                "capability": capability_id,
                "substatus": "permission_required",
                "missing_scopes": missing,
                "message": f"{provider.display_name} is connected, but additional permissions ({', '.join(missing)}) are required for {capability_id}.",
                "connect_url": f"/integrations?connect={provider.tool_name}&capabilities={capability_id}",
            }

    return {
        "status": "available",
        "provider": provider.tool_name,
        "provider_name": provider.display_name,
        "capability": capability_id,
        "connection_id": str(matched_conn.id),
        "account_name": matched_conn.provider_account_name or (matched_conn.config or {}).get("connected_email"),
        "scope_level": provider.scope_level.value,
        "is_reusable": True,
    }

