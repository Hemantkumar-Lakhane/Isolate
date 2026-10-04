"""
integrations/tool_registry_builder.py
======================================
Builds the ToolRegistry for a workflow run by wiring up integration
connectors to callable tool functions with OpenAI-format schemas.

Each tool = one connector method + one JSON schema.
Agents reference tools by name in the DAG node config.

CONSTANT — tool interface is constant.
MODIFY — add new tools by adding entries to build_registry().
"""

from __future__ import annotations

import json
from typing import Optional

import structlog

from agents.base_agent import ToolRegistry
from integrations.connectors import (
    GenericRESTConnector, GmailConnector, GoogleWorkspaceConnector,
    HubSpotConnector, SlackConnector, StripeConnector,
)
from integrations.local_dev_tools import LOCAL_TOOL_FUNCTIONS, LOCAL_TOOL_SCHEMAS

log = structlog.get_logger()


def build_registry(tenant_config: dict, credentials: dict) -> ToolRegistry:
    """
    Build a ToolRegistry for a given tenant.
    Loads only the integrations that are enabled and credentialed.

    Args:
        tenant_config:  Full client config JSON
        credentials:    Dict of {tool_name: credentials_dict} — fetched from DB at runtime

    Returns:
        Populated ToolRegistry ready for use by agents
    """
    registry = ToolRegistry()
    integrations = tenant_config.get("integrations", {})

    # ── HubSpot ──────────────────────────────────────────────────────────
    if integrations.get("hubspot", {}).get("enabled") and "hubspot" in credentials:
        hs = HubSpotConnector(
            credentials=credentials["hubspot"],
            config=integrations["hubspot"],
        )
        _register_hubspot_tools(registry, hs)
        log.info("HubSpot tools registered")

    # ── Gmail ─────────────────────────────────────────────────────────────
    if (integrations.get("gmail", {}).get("enabled") or "gmail" in credentials) and "gmail" in credentials:
        gm_config = credentials["gmail"] if isinstance(credentials["gmail"], dict) else integrations.get("gmail", {})
        gm = GmailConnector(
            credentials=credentials["gmail"],
            config=gm_config,
        )
        _register_gmail_tools(registry, gm)
        log.info("Gmail tools registered")

    # ── Google Workspace (Calendar / Drive) ───────────────────────────────
    gw_creds = credentials.get("google_workspace") or credentials.get("gmail")
    if (integrations.get("google_workspace", {}).get("enabled") or integrations.get("gmail", {}).get("enabled")) and gw_creds:
        gw = GoogleWorkspaceConnector(
            credentials=gw_creds,
            config=integrations.get("google_workspace", {}),
        )
        _register_google_workspace_tools(registry, gw)
        log.info("Google Workspace tools registered")

    # ── Slack ─────────────────────────────────────────────────────────────
    if integrations.get("slack", {}).get("enabled") and "slack" in credentials:
        sl = SlackConnector(
            credentials=credentials["slack"],
            config=integrations["slack"],
        )
        _register_slack_tools(registry, sl)
        log.info("Slack tools registered")

    # ── Stripe ────────────────────────────────────────────────────────────
    if integrations.get("stripe", {}).get("enabled") and "stripe" in credentials:
        st = StripeConnector(
            credentials=credentials["stripe"],
            config=integrations["stripe"],
        )
        _register_stripe_tools(registry, st)
        log.info("Stripe tools registered")

    # ── Product DB (Generic REST) ─────────────────────────────────────────
    # Credentials are optional — local dev uses empty credentials with localhost
    if integrations.get("product_db", {}).get("enabled"):
        pdb_creds = credentials.get("product_db", {})  # Empty dict OK for local dev
        pdb_config = integrations["product_db"]
        grest = GenericRESTConnector(credentials=pdb_creds, config=pdb_config)
        _register_generic_tools(registry, grest, "product_api")
        log.info("Product API tools registered (generic REST)")

    # ── Always-available utility tools ───────────────────────────────────
    _register_utility_tools(registry)

    # ── Always register local dev tools ──────────────────────────────────
    # These read from seed data files — zero credentials needed.
    # They provide fallback data for any tool names the agents reference.
    _register_local_dev_tools(registry)

    return registry


# ─────────────────────────────────────────────────────────────────────────────
# Tool registration helpers
# ─────────────────────────────────────────────────────────────────────────────

def _register_hubspot_tools(registry: ToolRegistry, hs: HubSpotConnector) -> None:

    async def hubspot_read_contacts(limit: int = 100, filters: dict = None) -> list:
        return await hs.read("contacts", {"limit": limit, **(filters or {})})

    async def hubspot_read_deals(limit: int = 100, stage: str = None) -> list:
        f = {"limit": limit}
        if stage:
            f["stage"] = stage
        return await hs.read("deals", f)

    async def hubspot_create_task(owner_id: str, subject: str, body: str, due_date: str = None) -> dict:
        return await hs.create_task(owner_id, subject, body, due_date)

    async def hubspot_update_property(object_type: str, object_id: str, properties: dict) -> dict:
        return await hs.update_property(object_type, object_id, properties)

    async def hubspot_read_activity_log(contact_id: str, days_back: int = 30) -> list:
        return await hs.read("engagements", {"limit": 50, "contact_id": contact_id})

    async def hubspot_read_contact_history(contact_id: str) -> list:
        return await hs.read("communications", {"limit": 20, "contact_id": contact_id})

    registry.register("hubspot_read_contacts", hubspot_read_contacts, {
        "type": "function",
        "function": {
            "name": "hubspot_read_contacts",
            "description": "Read customer contacts from HubSpot CRM with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max records to return", "default": 100},
                    "filters": {"type": "object", "description": "Optional HubSpot filter criteria"},
                },
            },
        },
    })

    registry.register("hubspot_read_deals", hubspot_read_deals, {
        "type": "function",
        "function": {
            "name": "hubspot_read_deals",
            "description": "Read open deals from HubSpot pipeline",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 100},
                    "stage": {"type": "string", "description": "Filter by deal stage"},
                },
            },
        },
    })

    registry.register("hubspot_create_task", hubspot_create_task, {
        "type": "function",
        "function": {
            "name": "hubspot_create_task",
            "description": "Create an urgent task in HubSpot for a CSM or rep",
            "parameters": {
                "type": "object",
                "required": ["owner_id", "subject", "body"],
                "properties": {
                    "owner_id": {"type": "string", "description": "HubSpot owner ID"},
                    "subject": {"type": "string", "description": "Task subject"},
                    "body": {"type": "string", "description": "Task details"},
                    "due_date": {"type": "string", "description": "ISO8601 due date"},
                },
            },
        },
    })

    registry.register("hubspot_update_property", hubspot_update_property, {
        "type": "function",
        "function": {
            "name": "hubspot_update_property",
            "description": "Update a CRM object property (e.g. set churn_risk_score on a contact)",
            "parameters": {
                "type": "object",
                "required": ["object_type", "object_id", "properties"],
                "properties": {
                    "object_type": {"type": "string", "enum": ["contacts", "companies", "deals"]},
                    "object_id": {"type": "string"},
                    "properties": {"type": "object", "description": "Key-value pairs to update"},
                },
            },
        },
    })

    registry.register("hubspot_read_activity_log", hubspot_read_activity_log, {
        "type": "function",
        "function": {
            "name": "hubspot_read_activity_log",
            "description": "Read recent activity log for a contact to check for recent communication",
            "parameters": {
                "type": "object",
                "required": ["contact_id"],
                "properties": {
                    "contact_id": {"type": "string"},
                    "days_back": {"type": "integer", "default": 30},
                },
            },
        },
    })

    registry.register("hubspot_read_contact_history", hubspot_read_contact_history, {
        "type": "function",
        "function": {
            "name": "hubspot_read_contact_history",
            "description": "Read full communication history for a contact",
            "parameters": {
                "type": "object",
                "required": ["contact_id"],
                "properties": {"contact_id": {"type": "string"}},
            },
        },
    })


def _register_gmail_tools(registry: ToolRegistry, gm: GmailConnector) -> None:

    async def gmail_queue_email(to: str, subject: str, body: str, from_name: str = None) -> dict:
        return await gm.send_email(to, subject, body, from_name)

    async def gmail_read_recent_threads(query: str = "in:sent", limit: int = 10) -> list:
        return await gm.read("threads", {"q": query, "limit": limit})

    registry.register("gmail_queue_email", gmail_queue_email, {
        "type": "function",
        "function": {
            "name": "gmail_queue_email",
            "description": "Queue or send an email via Gmail. Respects queue_for_approval setting.",
            "parameters": {
                "type": "object",
                "required": ["to", "subject", "body"],
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string"},
                    "body": {"type": "string", "description": "Plain text email body"},
                    "from_name": {"type": "string", "description": "Sender display name override"},
                },
            },
        },
    })

    registry.register("gmail_read_recent_threads", gmail_read_recent_threads, {
        "type": "function",
        "function": {
            "name": "gmail_read_recent_threads",
            "description": "Read recent email threads to check if we've recently contacted someone",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": "in:sent"},
                    "limit": {"type": "integer", "default": 10},
                },
            },
        },
    })

    async def gmail_read_messages(query: str = "in:inbox", limit: int = 40) -> dict:
        msgs = await gm.read_detailed_messages(query=query, limit=limit)
        err_info = gm.get_last_error_info() if hasattr(gm, "get_last_error_info") else {}
        if not msgs and err_info.get("error_code") in (401, 403, 500):
            return {
                "status": "error",
                "error_code": "GMAIL_SOURCE_UNAVAILABLE",
                "detail": err_info.get("error") or "Gmail API read failed or unauthorized",
                "messages": [],
                "total_messages": 0,
                "data_origin": "real_gmail",
                "is_test_data": False,
            }

        normalized_msgs = []
        for m in msgs:
            email_id = m.get("email_id") or m.get("id") or m.get("message_id")
            sender_val = m.get("from") or m.get("sender", "Unknown Sender")
            timestamp_val = m.get("received_at") or m.get("date") or m.get("timestamp", "")
            body_val = m.get("body") or m.get("snippet", "")
            normalized_msgs.append({
                "id": str(email_id) if email_id else "",
                "message_id": str(email_id) if email_id else "",
                "thread_id": m.get("thread_id", ""),
                "from": sender_val,
                "sender": sender_val,
                "to": m.get("to", ""),
                "subject": m.get("subject", "(No Subject)"),
                "body": body_val,
                "snippet": body_val,
                "received_at": timestamp_val,
                "timestamp": timestamp_val,
                "labels": m.get("labels", []),
                "data_origin": "real_gmail",
                "is_test_data": False,
            })
        return {
            "messages": normalized_msgs,
            "total_messages": len(normalized_msgs),
            "data_origin": "real_gmail",
            "is_test_data": False,
        }

    registry.register("gmail_read_messages", gmail_read_messages, {
        "type": "function",
        "function": {
            "name": "gmail_read_messages",
            "description": "Fetch real incoming email messages from the user's connected Gmail account",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": "in:inbox"},
                    "limit": {"type": "integer", "default": 40},
                },
            },
        },
    })



def _register_google_workspace_tools(registry: ToolRegistry, gw: GoogleWorkspaceConnector) -> None:

    async def google_calendar_schedule_event(
        summary: str, description: str, start_iso: str, end_iso: str, attendees: list = None
    ) -> dict:
        return await gw.schedule_event(
            summary=summary,
            description=description,
            start_iso=start_iso,
            end_iso=end_iso,
            attendees=attendees or [],
        )

    async def google_calendar_read_events(calendar_id: str = "primary", limit: int = 15) -> list:
        return await gw.read("events", {"calendar_id": calendar_id, "limit": limit})

    async def google_drive_read_files(query: str = "trashed = false", limit: int = 20) -> list:
        return await gw.read("files", {"q": query, "limit": limit})

    registry.register("google_calendar_schedule_event", google_calendar_schedule_event, {
        "type": "function",
        "function": {
            "name": "google_calendar_schedule_event",
            "description": "Schedule a consultation, appointment, or meeting on Google Calendar",
            "parameters": {
                "type": "object",
                "required": ["summary", "start_iso", "end_iso"],
                "properties": {
                    "summary": {"type": "string", "description": "Event title or summary"},
                    "description": {"type": "string", "description": "Details or agenda"},
                    "start_iso": {"type": "string", "description": "ISO 8601 start datetime string"},
                    "end_iso": {"type": "string", "description": "ISO 8601 end datetime string"},
                    "attendees": {"type": "array", "items": {"type": "string"}, "description": "List of attendee email addresses"},
                },
            },
        },
    })

    registry.register("google_calendar_read_events", google_calendar_read_events, {
        "type": "function",
        "function": {
            "name": "google_calendar_read_events",
            "description": "Read upcoming calendar events and meetings from Google Calendar",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar_id": {"type": "string", "default": "primary"},
                    "limit": {"type": "integer", "default": 15},
                },
            },
        },
    })

    registry.register("google_drive_read_files", google_drive_read_files, {
        "type": "function",
        "function": {
            "name": "google_drive_read_files",
            "description": "Query patient or client document records and reports from Google Drive",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "default": "trashed = false"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
    })


def _register_slack_tools(registry: ToolRegistry, sl: SlackConnector) -> None:

    async def slack_post_message(channel: str, text: str) -> dict:
        return await sl.post_message(channel, text)

    async def slack_post_risk_alert(accounts: list, workflow: str = "") -> dict:
        return await sl.post_risk_alert(accounts, workflow=workflow)

    registry.register("slack_post_message", slack_post_message, {
        "type": "function",
        "function": {
            "name": "slack_post_message",
            "description": "Post an alert or notification to a Slack channel",
            "parameters": {
                "type": "object",
                "required": ["channel", "text"],
                "properties": {
                    "channel": {"type": "string", "description": "Slack channel e.g. #cs-alerts"},
                    "text": {"type": "string", "description": "Message text (supports Slack markdown)"},
                },
            },
        },
    })

    registry.register("slack_post_risk_alert", slack_post_risk_alert, {
        "type": "function",
        "function": {
            "name": "slack_post_risk_alert",
            "description": "Post a formatted account risk digest to the CS alerts channel",
            "parameters": {
                "type": "object",
                "required": ["accounts"],
                "properties": {
                    "accounts": {"type": "array", "items": {"type": "object"}},
                    "workflow": {"type": "string", "description": "Workflow name for context"},
                },
            },
        },
    })


def _register_stripe_tools(registry: ToolRegistry, st: StripeConnector) -> None:

    async def stripe_read_subscriptions(status: str = "active", limit: int = 100) -> list:
        return await st.read("subscriptions", {"status": status, "limit": limit})

    async def stripe_read_customers(limit: int = 100) -> list:
        return await st.read("customers", {"limit": limit})

    registry.register("stripe_read_subscriptions", stripe_read_subscriptions, {
        "type": "function",
        "function": {
            "name": "stripe_read_subscriptions",
            "description": "Read subscription data from Stripe (MRR, status, billing)",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["active", "trialing", "past_due", "canceled"], "default": "active"},
                    "limit": {"type": "integer", "default": 100},
                },
            },
        },
    })

    registry.register("stripe_read_customers", stripe_read_customers, {
        "type": "function",
        "function": {
            "name": "stripe_read_customers",
            "description": "Read customer records from Stripe",
            "parameters": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 100}},
            },
        },
    })


def _register_generic_tools(registry: ToolRegistry, conn: GenericRESTConnector, prefix: str) -> None:

    for endpoint_name in conn._endpoints:
        tool_name = f"{prefix}_{endpoint_name}"
        _endpoint = endpoint_name  # capture for closure

        async def _reader(resource: str = _endpoint, filters: dict = None) -> list:
            return await conn.read(resource, filters)

        registry.register(tool_name, _reader, {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": f"Read data from {prefix} endpoint: {endpoint_name}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filters": {"type": "object", "description": "Query parameters"},
                    },
                },
            },
        })


def _register_utility_tools(registry: ToolRegistry) -> None:
    """Always-available tools that don't require external credentials."""

    async def db_write_outcome(
        tenant_id: str, action_taken: str, metric_name: str = None, metric_value: float = None
    ) -> dict:
        log.info("Outcome logged", tenant=tenant_id, action=action_taken)
        return {"logged": True, "action": action_taken}

    async def db_update_pattern(
        tenant_id: str, pattern_key: str, pattern_data: dict, success: bool = True
    ) -> dict:
        log.info("Pattern updated", tenant=tenant_id, key=pattern_key)
        return {"updated": True, "key": pattern_key}

    registry.register("db_write_outcome", db_write_outcome, {
        "type": "function",
        "function": {
            "name": "db_write_outcome",
            "description": "Log an outcome to the database for future learning",
            "parameters": {
                "type": "object",
                "required": ["tenant_id", "action_taken"],
                "properties": {
                    "tenant_id": {"type": "string"},
                    "action_taken": {"type": "string"},
                    "metric_name": {"type": "string"},
                    "metric_value": {"type": "number"},
                },
            },
        },
    })

    registry.register("db_update_pattern", db_update_pattern, {
        "type": "function",
        "function": {
            "name": "db_update_pattern",
            "description": "Update a learned pattern in the memory store",
            "parameters": {
                "type": "object",
                "required": ["tenant_id", "pattern_key", "pattern_data"],
                "properties": {
                    "tenant_id": {"type": "string"},
                    "pattern_key": {"type": "string"},
                    "pattern_data": {"type": "object"},
                    "success": {"type": "boolean", "default": True},
                },
            },
        },
    })

def _register_local_dev_tools(registry: ToolRegistry) -> None:
    """
    Register local development tools that read directly from seed data files.
    Always registered — gracefully return empty data if seed files don't exist.
    These tools are the primary data source during development.
    """
    registered = 0
    for tool_name, fn in LOCAL_TOOL_FUNCTIONS.items():
        schema = LOCAL_TOOL_SCHEMAS.get(tool_name)
        if schema:
            registry.register(tool_name, fn, schema)
            registered += 1
    if registered:
        log.info("Local dev tools registered", count=registered,
                 tools=list(LOCAL_TOOL_FUNCTIONS.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# Tool RAG indexer — call once per workflow run from the orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def index_tools_in_rag(
    registry: ToolRegistry,
    rag_engine,
    tenant_id: str = "global",
) -> int:
    """
    Index every registered tool's name + description into the RAG vector store
    so DiscoveryAgent can retrieve the most relevant tools semantically instead
    of sending hundreds of schemas to the LLM context window.

    Safe to call repeatedly — RAGEngine.store_tool_schema is idempotent.

    Returns the number of tools successfully indexed.
    """
    indexed = 0
    for tool_name, tool_data in registry._tools.items():
        schema = tool_data.get("schema", {})
        fn_schema = schema.get("function", schema)
        description = fn_schema.get("description", "")
        if not description:
            continue
        try:
            await rag_engine.store_tool_schema(tool_name, description, tenant_id)
            indexed += 1
        except Exception as e:
            log.warning("Tool RAG indexing failed", tool=tool_name, error=str(e))

    log.info("Tool schemas indexed in RAG", count=indexed, tenant=tenant_id[:16])
    return indexed
