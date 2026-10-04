"""
core/dag_validator.py
=====================
Static analysis validator for workflow DAG JSON.

Validates before saving to prevent "Dead Node" crashes 10 minutes into execution.

Checks:
  1. All agent strings map to known AGENT_MAP keys
  2. All prompt_file paths resolve to actual files on disk
  3. Tool references exist in LOCAL_TOOL_SCHEMAS or custom_tools table
  4. No circular dependencies in edges
  5. All depends_on references point to valid node IDs
  6. Required _meta fields present

Returns a ValidationResult with errors (blocking) and warnings (non-blocking).

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

KNOWN_AGENT_TYPES = {
    "research_agent",
    "reasoning_agent",
    "drafting_agent",
    "verification_agent",
    "execution_agent",
    "memory_agent",
    "discovery_agent",
    "consensus_agent",
    "customer_outreach_agent",
    "customer_support_agent",
    "marketing_outreach_agent",
    "summarizer_agent",
    "recommendation_agent",
    "comparison_agent",
    "hr_agent",
    "operations_agent",
}

# Tools always available regardless of custom tools
BUILTIN_TOOL_NAMES = {
    "db_write_outcome",
    "db_update_pattern",
    "product_api_usage",
    "product_api_nps",
    "product_api_deals",
    "get_communication_history",
    "get_activity_log",
    "retail_get_inventory",
    "retail_get_sales",
    "health_get_patients",
    "health_get_appointments",
    "finance_get_expenses",
    "finance_get_employees",
    "email_get_synthetic_messages",
    "crm_get_synthetic_leads",
    "auto",  # Discovery agent wildcard
}

PROMPTS_DIR = Path("workflows/prompts")


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


def validate_dag(
    dag: dict,
    custom_tool_names: Optional[set[str]] = None,
) -> ValidationResult:
    """
    Run all static checks on a DAG definition.

    Args:
        dag: The DAG dict (parsed JSON)
        custom_tool_names: Set of custom tool names registered for this tenant

    Returns:
        ValidationResult with errors (blocking) and warnings (non-blocking)
    """
    result = ValidationResult()
    custom_tools = custom_tool_names or set()
    all_known_tools = BUILTIN_TOOL_NAMES | custom_tools

    nodes: list[dict] = dag.get("nodes", [])
    edges: list[dict] = dag.get("edges", [])
    meta: dict = dag.get("_meta", {})

    # ── 1. _meta validation ───────────────────────────────────────────────
    if not meta:
        result.add_warning("Missing _meta section — display name and industry will be unknown")
    else:
        if not meta.get("name"):
            result.add_warning("_meta.name is empty — workflow will show ID only in UI")
        if not meta.get("industry"):
            result.add_warning("_meta.industry is empty")

    # ── 2. Node validation ────────────────────────────────────────────────
    if not nodes:
        result.add_error("DAG has no nodes — workflow will do nothing")
        return result  # No point continuing

    node_ids: set[str] = set()
    for i, node in enumerate(nodes):
        node_id = node.get("id")
        if not node_id:
            result.add_error(f"Node[{i}] missing 'id' field")
            continue

        if node_id in node_ids:
            result.add_error(f"Duplicate node id: '{node_id}'")
        node_ids.add(node_id)

        # Check agent type
        agent = node.get("agent", "")
        if not agent:
            result.add_error(f"Node '{node_id}': missing 'agent' field")
        elif agent not in KNOWN_AGENT_TYPES:
            result.add_error(
                f"Node '{node_id}': unknown agent type '{agent}'. "
                f"Known types: {sorted(KNOWN_AGENT_TYPES)}"
            )

        # Check prompt_file exists
        prompt_file = node.get("prompt_file", "")
        if prompt_file:
            p = PROMPTS_DIR / prompt_file
            if not p.exists():
                result.add_error(
                    f"Node '{node_id}': prompt_file '{prompt_file}' not found at "
                    f"{p.resolve()}. Create the file or remove prompt_file from the node."
                )

        # Check tools exist
        tools: list = node.get("tools", [])
        for tool in tools:
            if tool not in all_known_tools:
                result.add_warning(
                    f"Node '{node_id}': tool '{tool}' is not in built-in or registered "
                    f"custom tools. It may be unregistered or misspelled."
                )

        # Check depends_on references (will be validated against final node_ids below)
        depends_on: list = node.get("depends_on", [])
        if not isinstance(depends_on, list):
            result.add_error(f"Node '{node_id}': 'depends_on' must be a list")

        # Timeout sanity
        timeout = node.get("timeout_seconds", 90)
        if timeout < 10:
            result.add_warning(f"Node '{node_id}': timeout_seconds={timeout} is very low (<10s)")
        if timeout > 600:
            result.add_warning(f"Node '{node_id}': timeout_seconds={timeout} is very high (>10min)")

    # ── 3. depends_on references ──────────────────────────────────────────
    for node in nodes:
        node_id = node.get("id", "?")
        for dep in node.get("depends_on", []):
            if dep not in node_ids:
                result.add_error(
                    f"Node '{node_id}': depends_on '{dep}' which doesn't exist in this DAG"
                )

    # ── 4. Edge validation ────────────────────────────────────────────────
    for i, edge in enumerate(edges):
        frm = edge.get("from")
        to = edge.get("to")
        if not frm:
            result.add_error(f"Edge[{i}]: missing 'from' field")
        elif frm not in node_ids:
            result.add_error(f"Edge[{i}]: 'from' node '{frm}' doesn't exist")

        if not to:
            result.add_error(f"Edge[{i}]: missing 'to' field")
        elif to not in node_ids:
            result.add_error(f"Edge[{i}]: 'to' node '{to}' doesn't exist")

    # ── 5. Circular dependency detection ─────────────────────────────────
    _detect_cycles(nodes, edges, result)

    # ── 6. Escalation config ──────────────────────────────────────────────
    esc_config = dag.get("escalation_config", {})
    if not esc_config:
        result.add_warning("No escalation_config — escalations will use system defaults")

    return result


def _detect_cycles(nodes: list[dict], edges: list[dict], result: ValidationResult) -> None:
    """DFS-based cycle detection on edge graph."""
    from_to: dict[str, list[str]] = {}
    for edge in edges:
        frm = edge.get("from")
        to = edge.get("to")
        if frm and to:
            from_to.setdefault(frm, []).append(to)

    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(node_id: str) -> bool:
        visited.add(node_id)
        in_stack.add(node_id)
        for neighbor in from_to.get(node_id, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in in_stack:
                result.add_error(
                    f"Circular dependency detected: '{node_id}' → '{neighbor}' creates a cycle"
                )
                return True
        in_stack.discard(node_id)
        return False

    node_ids = [n.get("id") for n in nodes if n.get("id")]
    for nid in node_ids:
        if nid not in visited:
            dfs(nid)