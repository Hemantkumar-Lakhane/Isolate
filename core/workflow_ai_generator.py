"""
core/workflow_ai_generator.py
==============================
AI Workflow Copilot Synthesizer for SMBFlow.

Translates plain-English prompts into structured multi-agent DAG workflows
using a real LLM call (litellm / Anthropic Claude Haiku by default).

Falls back to the deterministic keyword-based generator only when every LLM
provider fails (network down, keys missing, etc.).

Output schema matches what the frontend dagToFlow adapter expects:
  {
    name, key, description, category, industry, scope, trigger_type,
    sla_hours, estimated_duration_minutes,
    nodes: [{ id, type, position, data: { name, agentType, ... } }],
    edges: [{ id, source, target, condition }],
    explanation
  }
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Optional

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Available node/agent type catalogue
# (must stay in sync with PALETTE_ITEMS in WorkflowBuilder.jsx)
# ---------------------------------------------------------------------------

NODE_CATALOGUE = """
TRIGGER NODES  (agentType starting with "trigger_")
  trigger_manual    – Manual / on-demand execution
  trigger_schedule  – Cron / scheduled periodic execution
  trigger_email     – Inbound email received (Gmail / Outlook webhook)
  trigger_webhook   – Inbound HTTP POST webhook from external system

AI AGENT NODES
  research_agent      – Gathers context: queries DB, fetches documents, vector search
  reasoning_agent     – Multi-step logic, classification, risk scoring, decisions
  drafting_agent      – Generates text content: emails, summaries, reports
  verification_agent  – Deterministic safety, policy compliance, quality guard
  execution_agent     – Dispatches external API calls, fires integrations

LOGIC / FLOW NODES
  logic_condition     – Boolean branch / filter (use for if/else decision points)
  logic_approval_gate – Pause for human-in-the-loop (HITL) review and approval
  code_transform      – JavaScript/Python code step; data transformation

TOOL / CONNECTOR NODES
  tool_gmail     – Send or receive email via Gmail API
  tool_slack     – Post message to Slack channel
  tool_hubspot   – Read/write HubSpot CRM (contacts, deals, tasks)
  tool_stripe    – Stripe billing: invoices, subscriptions, payments
  tool_sheet     – Google Sheets: read/write spreadsheet rows
  tool_postgres  – Run SQL query against PostgreSQL database
  tool_calendar  – Google Calendar: create/read events, schedule slots
  tool_telegram  – Send Telegram bot message
  tool_webhook   – Outbound HTTP POST to external REST API
"""

# Canonical colour map kept in sync with the palette
_NODE_COLORS: dict[str, str] = {
    "trigger_manual":    "#10B981",
    "trigger_schedule":  "#6366F1",
    "trigger_email":     "#06B6D4",
    "trigger_webhook":   "#8B5CF6",
    "research_agent":    "#6366F1",
    "reasoning_agent":   "#00D4FF",
    "drafting_agent":    "#10E580",
    "verification_agent":"#F59E0B",
    "execution_agent":   "#EF4444",
    "logic_condition":   "#F59E0B",
    "logic_approval_gate":"#6366F1",
    "code_transform":    "#F59E0B",
    "tool_gmail":        "#EA4335",
    "tool_slack":        "#EC4899",
    "tool_hubspot":      "#FF7A59",
    "tool_stripe":       "#6366F1",
    "tool_sheet":        "#10B981",
    "tool_postgres":     "#336791",
    "tool_calendar":     "#4285F4",
    "tool_telegram":     "#229ED9",
    "tool_webhook":      "#14B8A6",
}

# All valid agentType values
_VALID_AGENT_TYPES = set(_NODE_COLORS.keys())

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a workflow architect for SMBFlow, a multi-agent automation platform.
Your job is to convert a plain-English workflow description into a precise,
machine-readable DAG (Directed Acyclic Graph) in JSON.

═══════════════════════════════════════
AVAILABLE NODE TYPES
═══════════════════════════════════════
{node_catalogue}

═══════════════════════════════════════
OUTPUT SCHEMA (strict JSON, no markdown)
═══════════════════════════════════════
{{
  "name":         "Human-readable workflow name (title-case, max 6 words)",
  "key":          "snake_case_workflow_key",
  "description":  "One-sentence description of what this workflow does",
  "category":     "one of: operations | sales | marketing | healthcare | finance | compliance | productivity",
  "industry":     "one of: saas | healthcare | finance | real_estate | retail | general",
  "scope":        "GLOBAL or INDUSTRY",
  "trigger_type": "manual | schedule | email | webhook",
  "sla_hours":    2,
  "nodes": [
    {{
      "id":   "unique_snake_case_id",
      "agentType": "one of the agentType values listed above",
      "name": "Short display name for the node (max 5 words)",
      "description": "What this specific node does in this workflow"
    }}
  ],
  "edges": [
    {{
      "source": "source_node_id",
      "target": "target_node_id",
      "condition": null
    }}
  ],
  "explanation": "2-3 sentence explanation of the generated workflow"
}}

═══════════════════════════════════════
RULES
═══════════════════════════════════════
1. ONLY include nodes that are necessary for the described workflow.
   Do NOT add research_agent, verification_agent, or execution_agent unless
   the prompt explicitly or clearly implies them.

2. For IF/ELSE logic: use logic_condition. Connect it to TWO outgoing edges,
   each with a condition string (e.g. "approved" / "rejected", "> $10,000" / "<= $10,000").

3. For human review / approval: use logic_approval_gate.

4. Every workflow must start with exactly one trigger node.

5. Node IDs must be unique snake_case strings (e.g. "validate_customer_info").

6. Every edge source and target must reference a node ID that exists in nodes[].

7. Produce a valid DAG — no cycles.

8. Do NOT invent agentType values. Use only the listed types.

9. If the prompt asks for something the available nodes cannot represent,
   use the closest available node and note the limitation in the explanation.

10. Return ONLY the JSON object. No markdown fences. No prose outside the JSON.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_slug(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", text.strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")


def _extract_json(raw: str) -> dict:
    """Extract the first JSON object from raw LLM output (handles stray prose)."""
    raw = raw.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
        raw = raw.strip()

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extract first {...} block
    start = raw.find("{")
    end   = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response. Raw (first 400 chars): {raw[:400]}")


def _assign_positions(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """
    Compute 2-D canvas positions via topological sort.
    Each topological layer is a column; nodes in the same layer are stacked
    vertically. This keeps the layout from the LLM out of the loop.
    """
    node_ids = [n["id"] for n in nodes]
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
    children:  dict[str, list[str]] = {nid: [] for nid in node_ids}

    for e in edges:
        src = e.get("source") or e.get("from", "")
        tgt = e.get("target") or e.get("to", "")
        if src in in_degree and tgt in in_degree:
            in_degree[tgt] += 1
            children[src].append(tgt)

    # Kahn's BFS
    queue = [nid for nid, d in in_degree.items() if d == 0]
    layer_map: dict[str, int] = {}
    visited = []

    while queue:
        current = queue.pop(0)
        if current in layer_map:
            continue
        layer_map[current] = max(
            (layer_map.get(p, -1) + 1
             for e in edges
             for p in [e.get("source") or e.get("from", "")]
             if (e.get("target") or e.get("to", "")) == current),
            default=0,
        )
        visited.append(current)
        for child in children[current]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # Any nodes not reached (shouldn't happen in valid DAG) get layer 0
    for nid in node_ids:
        if nid not in layer_map:
            layer_map[nid] = 0

    # Group by layer to calculate y-positions
    from collections import defaultdict
    layer_nodes: dict[int, list[str]] = defaultdict(list)
    for nid, layer in layer_map.items():
        layer_nodes[layer].append(nid)

    X_SPACING = 280
    Y_SPACING = 160
    Y_BASE    = 180

    pos_map: dict[str, dict] = {}
    for layer, layer_node_ids in layer_nodes.items():
        x = 60 + layer * X_SPACING
        n_nodes = len(layer_node_ids)
        total_h  = (n_nodes - 1) * Y_SPACING
        y_start  = Y_BASE - total_h / 2
        for i, nid in enumerate(layer_node_ids):
            pos_map[nid] = {"x": x, "y": y_start + i * Y_SPACING}

    return [
        {**n, "position": pos_map.get(n["id"], {"x": 60, "y": Y_BASE})}
        for n in nodes
    ]


def _validate_and_repair(dag: dict) -> dict:
    """
    Validate the LLM-generated DAG and repair common issues:
      - agentType falls back to drafting_agent if unknown
      - edges with missing/invalid node references are dropped
      - missing required fields get sensible defaults
    Returns the repaired dag dict (same structure as the response schema).
    """
    nodes   = dag.get("nodes", [])
    edges   = dag.get("edges", [])
    node_ids = set()

    repaired_nodes = []
    for n in nodes:
        nid = n.get("id", "").strip()
        if not nid:
            nid = f"node_{uuid.uuid4().hex[:6]}"
        # Normalise id to snake_case
        nid = _clean_slug(nid)

        agent_type = n.get("agentType", "drafting_agent")
        if agent_type not in _VALID_AGENT_TYPES:
            log.warning("Unknown agentType replaced", original=agent_type, replacement="drafting_agent")
            agent_type = "drafting_agent"

        node_ids.add(nid)
        repaired_nodes.append({
            "id":        nid,
            "agentType": agent_type,
            "name":      (n.get("name") or nid.replace("_", " ").title())[:60],
            "description": n.get("description", ""),
        })

    # Drop edges that reference non-existent node IDs
    repaired_edges = []
    seen_pairs: set[tuple] = set()
    for i, e in enumerate(edges):
        src = _clean_slug(e.get("source") or e.get("from", ""))
        tgt = _clean_slug(e.get("target") or e.get("to", ""))
        if not src or not tgt:
            continue
        if src not in node_ids or tgt not in node_ids:
            log.warning("Edge dropped — node ID not found", source=src, target=tgt)
            continue
        if src == tgt:
            continue
        pair = (src, tgt)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        repaired_edges.append({
            "id":        f"e_{src}_{tgt}",
            "source":    src,
            "target":    tgt,
            "condition": e.get("condition") or None,
        })

    if not repaired_nodes:
        raise ValueError("LLM returned no valid nodes after repair.")

    dag["nodes"]  = repaired_nodes
    dag["edges"]  = repaired_edges
    return dag


def _build_final_response(dag: dict, prompt: str) -> dict:
    """
    Merge the validated LLM DAG with the required top-level metadata,
    assign 2-D positions, and shape the nodes into the frontend format.
    """
    raw_name  = (dag.get("name") or "Custom Workflow").strip()
    raw_key   = dag.get("key") or _clean_slug(raw_name)
    clean_key = _clean_slug(raw_key)
    if len(clean_key) < 3:
        clean_key = f"custom_workflow_{uuid.uuid4().hex[:6]}"

    category = dag.get("category", "operations")
    industry = dag.get("industry", "general")
    trigger  = dag.get("trigger_type", "manual")
    scope    = "GLOBAL" if industry in ("general", "") else "INDUSTRY"

    # Assign positions
    nodes_with_pos = _assign_positions(dag["nodes"], dag["edges"])

    # Shape nodes into the frontend-expected format
    shaped_nodes = []
    for n in nodes_with_pos:
        agent_type = n["agentType"]
        shaped_nodes.append({
            "id":   n["id"],
            "type": _agent_type_to_canvas_type(agent_type),
            "position": n["position"],
            "data": {
                "name":             n["name"],
                "agentType":        agent_type,
                "category":         category,
                "color":            _NODE_COLORS.get(agent_type, "#6366F1"),
                "prompt_directive": n.get("description", ""),
                "timeout_seconds":  90,
                "retry_count":      2,
                "tools":            [],
            },
        })

    explanation = dag.get("explanation") or (
        f"Generated a {len(shaped_nodes)}-node workflow for: {prompt[:80]}"
    )

    return {
        "name":                     raw_name,
        "key":                      clean_key,
        "description":              dag.get("description") or f"AI-generated workflow for: {prompt}",
        "category":                 category,
        "industry":                 industry,
        "scope":                    scope,
        "trigger_type":             trigger,
        "sla_hours":                dag.get("sla_hours", 4),
        "estimated_duration_minutes": len(shaped_nodes),
        "nodes":                    shaped_nodes,
        "edges":                    dag["edges"],
        "explanation":              explanation,
    }


def _agent_type_to_canvas_type(agent_type: str) -> str:
    """Map agentType → canvas node type for dagToFlow."""
    if agent_type.startswith("trigger_"):
        return "triggerNode"
    if agent_type.startswith("tool_"):
        return "toolNode"
    if agent_type == "code_transform":
        return "codeNode"
    if agent_type.startswith("logic_") or agent_type in ("approval_gate", "condition_branch"):
        return "logicNode"
    return "agentNode"


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

async def _call_llm_for_dag(prompt: str, industry: Optional[str]) -> dict:
    """
    Call the LLM with the structured DAG system prompt.
    Tries models in order; raises on complete failure.
    """
    from litellm import acompletion  # local import — avoids module-level cost

    # Model preference order — cheaper/faster first, fall back to heavier
    models_to_try = []

    mini_model  = os.getenv("LLM_MINI_MODEL",  "anthropic/claude-haiku-4-5-20251001")
    fast_model  = os.getenv("LLM_FAST_MODEL",  "groq/llama-3.1-8b-instant")
    heavy_model = os.getenv("LLM_HEAVY_MODEL", "anthropic/claude-sonnet-4-20250514")

    # Prefer Haiku (reliable JSON) → heavy as final resort
    models_to_try = [mini_model, heavy_model]

    user_message = (
        f"Convert the following workflow description into the required JSON DAG.\n\n"
        f"Industry context: {industry or 'general'}\n\n"
        f"Workflow description:\n{prompt}"
    )

    system_text = _SYSTEM_PROMPT.format(node_catalogue=NODE_CATALOGUE)

    last_err: Exception | None = None

    for model in models_to_try:
        try:
            log.info("Calling LLM for DAG generation", model=model)

            kwargs: dict[str, Any] = {
                "model":       model,
                "messages": [
                    {"role": "system", "content": system_text},
                    {"role": "user",   "content": user_message},
                ],
                "temperature": 0.2,
                "max_tokens":  4096,
                "timeout":     60,
            }

            # Anthropic and OpenAI support JSON mode — enable where available
            if "anthropic" in model or "openai" in model or "gpt" in model:
                # Use json_object response format only for OpenAI-compatible models
                # Anthropic doesn't use response_format but is reliable with the prompt
                if "openai" in model or "gpt" in model:
                    kwargs["response_format"] = {"type": "json_object"}

            response = await acompletion(**kwargs)
            raw_text = response.choices[0].message.content or ""

            dag = _extract_json(raw_text)
            dag = _validate_and_repair(dag)
            return dag

        except Exception as e:
            last_err = e
            log.warning("LLM DAG generation attempt failed", model=model, error=str(e)[:200])
            continue

    raise RuntimeError(
        f"All LLM providers failed for DAG generation. Last error: {last_err}"
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def generate_workflow_from_prompt(
    prompt: str,
    industry: Optional[str] = "general",
    category: Optional[str] = None,
) -> dict[str, Any]:
    """
    Synthesize an end-to-end multi-agent DAG workflow from a natural-language prompt.

    1. Calls Claude Haiku (or configured LLM_MINI_MODEL) with a structured system prompt.
    2. Parses + validates the returned JSON against the DAG schema.
    3. Assigns 2-D canvas positions via topological sort.
    4. Falls back to the deterministic keyword generator only if every LLM call fails.
    """
    # ── Try LLM path ──────────────────────────────────────────────────────────
    try:
        dag = await _call_llm_for_dag(prompt, industry)
        result = _build_final_response(dag, prompt)
        log.info(
            "LLM DAG generation succeeded",
            name=result["name"],
            nodes=len(result["nodes"]),
            edges=len(result["edges"]),
        )
        return result

    except Exception as llm_err:
        log.warning(
            "LLM DAG generation failed — falling back to keyword generator",
            error=str(llm_err)[:300],
        )

    # ── Keyword fallback (original implementation, unchanged) ─────────────────
    return await _keyword_based_generator(prompt, industry, category)


# ---------------------------------------------------------------------------
# Keyword-based fallback generator (original logic, preserved exactly)
# ---------------------------------------------------------------------------

# Supported Agent Types & Visual Styles
AGENT_PALETTE = {
    "research_agent": {
        "name": "Research Agent",
        "description": "Context gathering, database query & document fetch",
        "color": "#6C63FF",
        "default_tools": ["tool_db_mutation"],
    },
    "reasoning_agent": {
        "name": "Reasoning Agent",
        "description": "Multi-step logic, analysis, risk classification & scoring",
        "color": "#00D4FF",
        "default_tools": [],
    },
    "drafting_agent": {
        "name": "Drafting Agent",
        "description": "Generates structured content, customized copy, reports & emails",
        "color": "#10E580",
        "default_tools": ["tool_email_dispatch"],
    },
    "verification_agent": {
        "name": "Verification Agent",
        "description": "Deterministic safety, policy compliance, and quality verification",
        "color": "#FFB800",
        "default_tools": [],
    },
    "execution_agent": {
        "name": "Execution Agent",
        "description": "Dispatches tool actions and external API integrations",
        "color": "#FF4757",
        "default_tools": ["tool_http_webhook", "tool_email_dispatch"],
    },
}

LOGIC_PALETTE = {
    "condition_branch": {
        "name": "Condition / Filter",
        "description": "Evaluates boolean logic and branches execution path",
        "color": "#F59E0B",
    },
    "switch_router": {
        "name": "Switch Router",
        "description": "Multi-way routing by category or confidence",
        "color": "#EC4899",
    },
    "approval_gate": {
        "name": "HITL Approval Gate",
        "description": "Pauses execution for human SME review and approval",
        "color": "#4F46E5",
    },
}

TRIGGER_PALETTE = {
    "manual":    {"name": "Manual UI Trigger",    "category": "trigger", "color": "#10B981"},
    "email":     {"name": "Inbound Email Trigger","category": "trigger", "color": "#06B6D4"},
    "scheduled": {"name": "Scheduled Cron",       "category": "trigger", "color": "#6366F1"},
    "webhook":   {"name": "Webhook Ingest",        "category": "trigger", "color": "#8B5CF6"},
}


async def _keyword_based_generator(
    prompt: str,
    industry: Optional[str] = "general",
    category: Optional[str] = None,
) -> dict[str, Any]:
    """
    Original deterministic keyword-based workflow generator.
    Used only as a fallback when all LLM providers are unavailable.
    """
    p_lower = prompt.lower()

    # 1. Detect Category & Industry
    inferred_category = category or "operations"
    if any(k in p_lower for k in ("lead", "sale", "deal", "pipeline", "crm", "outreach", "prospect")):
        inferred_category = "sales"
    elif any(k in p_lower for k in ("marketing", "campaign", "social", "post", "blog", "ad", "launch", "content")):
        inferred_category = "marketing"
    elif any(k in p_lower for k in ("patient", "clinic", "doctor", "health", "hospital", "medical", "appointment", "triage")):
        inferred_category = "healthcare"
    elif any(k in p_lower for k in ("invoice", "fraud", "payment", "billing", "expense", "refund", "financial", "tax", "accounting")):
        inferred_category = "finance"
    elif any(k in p_lower for k in ("compliance", "kyc", "audit", "legal", "gdpr", "policy", "security", "risk")):
        inferred_category = "compliance"
    elif any(k in p_lower for k in ("ticket", "support", "customer", "onboarding", "sla", "service", "helpdesk")):
        inferred_category = "productivity"

    inferred_industry = industry if industry and industry != "general" else "general"
    if inferred_category == "healthcare":
        inferred_industry = "healthcare"
    elif inferred_category == "finance":
        inferred_industry = "finance"
    elif any(k in p_lower for k in ("saas", "software", "api", "cloud")):
        inferred_industry = "saas"
    elif any(k in p_lower for k in ("retail", "store", "ecommerce", "shopify", "order")):
        inferred_industry = "retail"
    elif any(k in p_lower for k in ("property", "tenant", "real estate", "lease")):
        inferred_industry = "real_estate"

    # 2. Detect Trigger
    trigger_type = "manual"
    if any(k in p_lower for k in ("webhook", "api", "incoming post", "stripe", "hubspot", "event")):
        trigger_type = "webhook"
    elif any(k in p_lower for k in ("email", "inbox", "gmail", "inbound mail", "outlook")):
        trigger_type = "email"
    elif any(k in p_lower for k in ("cron", "schedule", "nightly", "daily", "hourly", "periodic", "every")):
        trigger_type = "scheduled"

    # 3. Detect name & key
    raw_title = prompt.split(".")[0].split(",")[0]
    raw_title = re.sub(r"^(create|build|make|generate|set up|design)\s+(an?\s+)?", "", raw_title, flags=re.IGNORECASE).strip()
    if len(raw_title) > 40:
        raw_title = " ".join(raw_title.split()[:5])
    name = raw_title.title() if raw_title else "AI Custom Multi-Agent Workflow"
    key  = _clean_slug(name)
    if len(key) < 3:
        key = f"custom_workflow_{uuid.uuid4().hex[:6]}"

    # 4. Synthesize DAG Steps
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    trig_id   = "node_trig_01"
    trig_info = TRIGGER_PALETTE.get(trigger_type, TRIGGER_PALETTE["manual"])
    nodes.append({
        "id":   trig_id,
        "type": "triggerNode",
        "position": {"x": 60, "y": 180},
        "data": {
            "name":         f"{trig_info['name']} ({name})",
            "triggerType":  trigger_type,
            "category":     "trigger",
            "color":        trig_info["color"],
            "description":  f"Entrypoint for {name}",
            "agentType":    f"trigger_{trigger_type}",
        },
    })

    requires_research  = True
    requires_reasoning = True
    requires_approval  = any(k in p_lower for k in ("approval", "human", "review", "manager", "gate", "sme", "high risk", "confirm", "approve", "dispute", "refund"))
    requires_drafting  = any(k in p_lower for k in ("draft", "write", "generate", "create email", "compose", "post", "summary", "report", "message", "alert"))
    requires_execution = True

    step_sequence = []

    if requires_research:
        step_sequence.append({
            "id":        "node_res_01",
            "agent":     "research_agent",
            "name":      f"{inferred_category.title()} Data Gatherer",
            "directive": f"Extract all relevant entities, historical records, and context regarding {prompt[:80]}.",
            "tools":     ["tool_db_mutation"],
        })

    if requires_reasoning:
        step_sequence.append({
            "id":        "node_reason_01",
            "agent":     "reasoning_agent",
            "name":      f"{inferred_category.title()} Logic & Risk Assessor",
            "directive": "Analyze gathered context, evaluate decision policies, classify priority score, and check constraints.",
            "tools":     [],
        })

    if requires_drafting or (not requires_approval and not requires_drafting):
        step_sequence.append({
            "id":        "node_draft_01",
            "agent":     "drafting_agent",
            "name":      "Action Plan & Response Drafter",
            "directive": "Generate structured output payload, client communication draft, or decision report.",
            "tools":     ["tool_email_dispatch"],
        })

    if requires_approval:
        step_sequence.append({
            "id":        "node_gate_01",
            "agent":     "approval_gate",
            "name":      "SME Human Approval Gate",
            "directive": "Pauses execution and alerts human operator if confidence < 0.85 or risk score is elevated.",
            "tools":     [],
        })

    step_sequence.append({
        "id":        "node_verify_01",
        "agent":     "verification_agent",
        "name":      "Deterministic Safety & Policy Guard",
        "directive": "Enforce strict schema validation, tenant budget caps, and regulatory compliance rules.",
        "tools":     [],
    })

    if requires_execution:
        step_sequence.append({
            "id":        "node_exec_01",
            "agent":     "execution_agent",
            "name":      "Integration & Dispatch Executor",
            "directive": "Execute finalized actions, dispatch notifications, and commit atomic state changes to external systems.",
            "tools":     ["tool_http_webhook", "tool_email_dispatch", "tool_db_mutation"],
        })

    prev_id = trig_id
    for idx, step in enumerate(step_sequence):
        s_id       = step["id"]
        agent_type = step["agent"]
        is_gate    = agent_type == "approval_gate"
        is_logic   = agent_type in LOGIC_PALETTE

        meta = AGENT_PALETTE.get(agent_type) or LOGIC_PALETTE.get(agent_type, {
            "name": step["name"], "description": "Workflow step", "color": "#6366F1",
        })

        x_pos     = 60 + ((idx + 1) * 280)
        node_type = "logicNode" if is_logic else "agentNode"

        nodes.append({
            "id":   s_id,
            "type": node_type,
            "position": {"x": x_pos, "y": 180},
            "data": {
                "name":             step["name"],
                "agentType":        agent_type,
                "category":         inferred_category,
                "color":            meta.get("color", "#6366F1"),
                "prompt_directive": step["directive"],
                "temperature":      0.2 if agent_type in ("reasoning_agent", "verification_agent") else 0.7,
                "timeout_seconds":  60,
                "retry_count":      2,
                "required_inputs":  ["context_payload"],
                "tools":            step.get("tools", []),
            },
        })

        edge_label = "Approved / Confidence > 0.85" if is_gate else None
        edges.append({
            "id":        f"e_{prev_id}_{s_id}",
            "source":    prev_id,
            "target":    s_id,
            "label":     edge_label,
            "condition": "confidence >= 0.85" if is_gate else None,
        })
        prev_id = s_id

    explanation = (
        f"[FALLBACK] Keyword-based generator produced a {len(nodes)}-node workflow for '{name}'. "
        f"LLM generation was unavailable — this is a generic template, not a precise interpretation."
    )

    return {
        "name":                     name,
        "key":                      key,
        "description":              f"AI-synthesized multi-agent workflow for: {prompt}",
        "category":                 inferred_category,
        "industry":                 inferred_industry,
        "scope":                    "GLOBAL" if inferred_industry == "general" else "INDUSTRY",
        "trigger_type":             trigger_type,
        "sla_hours":                2 if inferred_category in ("sales", "productivity") else 4,
        "estimated_duration_minutes": len(nodes),
        "nodes":                    nodes,
        "edges":                    edges,
        "explanation":              explanation,
    }
