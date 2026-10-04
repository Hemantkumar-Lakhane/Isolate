"""
core/orchestrator.py  (full rewrite — event-driven suspension)
==============================================================
Key architectural changes vs. the original:

1. NO asyncio.sleep polling for A2A/escalation decisions.
   When a workflow hits a decision point it calls state_manager.suspend_workflow(),
   saves accumulated_context + suspension metadata to the DB, then EXITS.
   The API layer re-launches _resume_workflow_background when the decision arrives.

2. run_workflow()         — fresh run, delegates to _run_segment() from index 0.
   resume_workflow()      — loads DB state, delegates to _run_segment() from saved node.
   _run_segment()         — the actual execution loop (shared by both paths).

3. A2A protocol still creates a DB record and broadcasts WS events,
   but does NOT block.

4. All escalation/A2A records are created via StateManager (DB-backed).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
import traceback
import pytz
from datetime import datetime
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import aiofiles
import structlog

from agents.agents import (
    DraftingAgent, ExecutionAgent, MemoryAgent,
    ReasoningAgent, ResearchAgent, VerificationAgent,
    CustomerOutreachAgent, CustomerSupportAgent, MarketingOutreachAgent,
    SummarizerAgent, RecommendationAgent, ComparisonAgent, HRAgent, OperationsAgent,
    HumanizerAgent
)
from agents.base_agent import ALLOWED_EDGE_CONDITIONS, AgentInput, AgentOutput, BaseAgent, ToolRegistry
from core.llm_router import LLMRouter
from core.state_manager import AgentStatus, StateManager, WorkflowStatus
from core.rag_engine import RAGEngine
from epi.epi_manager import EPIManager
from agents.consensus_agent import ConsensusAgent
log = structlog.get_logger()

# Fix A: Per-process cache to avoid re-indexing tools on every workflow run.
# Key  : tenant_id
# Value: (unix_timestamp_of_last_index, frozenset_of_registered_tool_names)
_tool_index_cache: dict[str, tuple[float, frozenset]] = {}

DEFAULT_MAX_A2A_ATTEMPTS: int = 3

AGENT_MAP: dict[str, type[BaseAgent]] = {
    "research_agent":          ResearchAgent,
    "reasoning_agent":         ReasoningAgent,
    "drafting_agent":          DraftingAgent,
    "verification_agent":      VerificationAgent,
    "execution_agent":         ExecutionAgent,
    "memory_agent":            MemoryAgent,
    "consensus_agent":         ConsensusAgent,
    "customer_outreach_agent": CustomerOutreachAgent,
    "customer_support_agent":  CustomerSupportAgent,
    "marketing_outreach_agent":MarketingOutreachAgent,
    "summarizer_agent":        SummarizerAgent,
    "humanizer_agent":         HumanizerAgent,
    "recommendation_agent":    RecommendationAgent,
    "comparison_agent":        ComparisonAgent,
    "hr_agent":                HRAgent,
    "operations_agent":        OperationsAgent,
}

class _AttrDict(dict):
    """
    A dict subclass that supports attribute-style access and returns None for
    missing keys instead of raising AttributeError.
 
    Required for simpleeval to safely evaluate conditions like
    'not output.escalate' when the output dict may not contain every expected key
    (e.g. when JSON parsing partially failed).
    """
    def __getattr__(self, item):
        try:
            val = self[item]
            # Recursively wrap nested dicts so deep attribute paths also work
            if isinstance(val, dict) and not isinstance(val, _AttrDict):
                return _AttrDict(val)
            return val
        except KeyError:
            return None   # ← critical: None is falsy, so "not output.escalate" → True
 
    def __setattr__(self, key, value):
        self[key] = value

# Lazy import DiscoveryAgent to avoid circular at module load
def _get_discovery_agent():
    from agents.agents import DiscoveryAgent
    return DiscoveryAgent

def _prune_context_for_storage(
    context: dict,
    max_json_bytes: int = 200_000,
) -> dict:
    """
    Prune accumulated_context before writing to PostgreSQL JSONB column.
    Prevents TOAST storage (row > 8KB page) and index bloat.
    Keeps all keys but compresses large values. Metadata keys (prefix _) are kept verbatim.
    """
    raw = json.dumps(context, default=str)
    if len(raw.encode()) <= max_json_bytes:
        return context

    _META_KEYS = {
        "trigger_signal", "tenant_id", "workflow_name", "patterns",
        "started_at", "_rag_historical_context", "_a2a_refinement_note",
        "_forked_from", "_fork_node",
    }
    _SUMMARY_FIELDS = {
        "situation_summary", "urgency", "reasoning_confidence", "summary",
        "status", "escalate", "escalation_reason", "patterns_updated",
        "outcomes_logged", "delta_analysis", "delta_vs_history", "delta_trend",
        "passed", "emails_queued", "actions_taken", "total_cost_usd",
        "_prosecutor_issues", "_judge_verdict",
    }

    pruned: dict = {}
    for key, value in context.items():
        if key.startswith("_") or key in _META_KEYS:
            pruned[key] = value
            continue

        if isinstance(value, dict):
            val_json = json.dumps(value, default=str)
            if len(val_json) > 20_000:
                compact = {k: v for k, v in value.items() if k in _SUMMARY_FIELDS}
                # Preserve first 5 accounts for Time-Travel context reconstruction
                if "accounts" in value and isinstance(value["accounts"], list):
                    compact["accounts"] = value["accounts"][:5]
                    if len(value["accounts"]) > 5:
                        compact["_accounts_truncated"] = len(value["accounts"]) - 5
                compact["_context_pruned"] = True
                compact["_original_bytes"] = len(val_json)
                pruned[key] = compact
            else:
                pruned[key] = value

        elif isinstance(value, list) and len(value) > 20:
            pruned[key] = value[:20] + [{"_truncated": True, "total": len(value)}]

        else:
            pruned[key] = value
    # ADDED: Store full research output separately for fork replay
    # The pruned context is fine for display, but Time-Travel needs full data.
    research_full = context.get("research", {})
    if research_full and isinstance(research_full, dict):
        accounts_count = len(research_full.get("accounts") or [])
        if accounts_count > 5:
            # Store full research in a fork-only key that isn't pruned
            pruned["_fork_research_full"] = research_full
            pruned["_fork_accounts_count"] = accounts_count

    return pruned


# Keys whose VALUES must never be persisted or surfaced to the UI. Matched
# case-insensitively as substrings so "api_key", "X-Api-Key", "access_token",
# "authorization" all trip. Business content (email bodies, subjects, names,
# summaries) is intentionally NOT redacted — that is what the UI must show.
_SECRET_KEY_MARKERS = (
    "api_key", "apikey", "secret", "password", "passwd", "token",
    "authorization", "auth_header", "bearer", "private_key", "client_secret",
    "credential", "access_key", "session_key", "encryption_key",
)


def _redact_secrets(value):
    """Recursively replace secret-looking values with a redaction marker."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            key_l = str(k).lower()
            if any(marker in key_l for marker in _SECRET_KEY_MARKERS):
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact_secrets(v)
        return out
    if isinstance(value, list):
        return [_redact_secrets(v) for v in value]
    return value


def _prepare_output_for_persistence(
    output_data,
    max_json_bytes: int = 512_000,
) -> Optional[dict]:
    """
    Prepare a node's structured output for durable persistence in the
    agent_run_records.output_data column.

    Guarantees, in order:
      1. Secrets are redacted (never persist credentials — see _redact_secrets).
      2. The payload stays under a JSONB size cap; if a run produced something
         enormous, large lists/strings are truncated with an explicit marker
         rather than dropped silently.

    Business data (the 40 fetched emails, drafts, summaries) is preserved intact
    under the cap — that is exactly what the redesigned UI renders.
    """
    if output_data is None:
        return None
    if not isinstance(output_data, dict):
        output_data = {"value": output_data}

    safe = _redact_secrets(output_data)

    try:
        raw = json.dumps(safe, default=str)
    except Exception:
        return {"_unserializable": True, "_note": "output could not be JSON-encoded"}

    if len(raw.encode()) <= max_json_bytes:
        return safe

    # Over cap: truncate the largest offenders (long lists / strings) but keep
    # structure and an explicit truncation marker so the UI can say so honestly.
    trimmed: dict = {}
    for key, val in safe.items():
        if isinstance(val, list) and len(val) > 25:
            trimmed[key] = val[:25] + [{"_truncated": True, "total": len(val)}]
        elif isinstance(val, str) and len(val) > 20_000:
            trimmed[key] = val[:20_000] + " …[truncated]"
        else:
            trimmed[key] = val
    trimmed["_output_truncated"] = True
    trimmed["_original_bytes"] = len(raw.encode())
    # Final safety: if still over cap, store a compact marker instead.
    try:
        if len(json.dumps(trimmed, default=str).encode()) > max_json_bytes:
            return {
                "_output_truncated": True,
                "_original_bytes": len(raw.encode()),
                "_note": "output exceeded persistence cap; see live logs / EPI evidence for full payload",
            }
    except Exception:
        pass
    return trimmed


class WorkflowOrchestrator:
    """
    Stateless per-execution orchestrator.
    State is persisted to PostgreSQL via StateManager.
    """

    def __init__(
        self,
        state_manager: StateManager,
        llm_router: LLMRouter,
        tool_registry: ToolRegistry,
        epi_manager: EPIManager,
        rag_engine: Optional[RAGEngine] = None,
        ws_broadcast: Optional[Callable] = None,
        escalation_callback: Optional[Callable] = None,
        agent_run_callback: Optional[Callable] = None,
    ):
        self._state = state_manager
        self._llm = llm_router
        self._tools = tool_registry
        self._epi = epi_manager
        self._rag = rag_engine or RAGEngine()
        # GraphRAG knowledge graph (structural similarity queries)
        from core.graph_rag import GraphRAGEngine
        self._graph_rag = GraphRAGEngine()
        self._ws_broadcast = ws_broadcast
        self._escalation_cb = escalation_callback
        self._agent_run_cb = agent_run_callback

        # Pause events per run_id (asyncio.Event — no busy-wait)
        self._pause_events: dict[str, asyncio.Event] = {}
        self._agent_run_log: list[dict] = []
        # Nodes that completed but in a degraded/unreliable way (LLM fallback/mock,
        # verification FAIL, or a swallowed error). Used to compute an honest
        # completion_quality at the end of the run. Reset per run alongside _agent_run_log.
        self._degraded_nodes: list[dict] = []
        #   # Cost tracker and system logger (set per-run in run_workflow)
        self._cost_tracker = None
        self._sys_logger = None
        
        #   # Import BudgetExceededError for circuit breaker
        from core.cost_tracker import BudgetExceededError
        self._BudgetExceededError = BudgetExceededError

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    async def run_workflow(
        self,
        tenant_config: dict,
        workflow_name: str,
        trigger_signal: dict,
        instance_id: Optional[str] = None,
        budget_settings: Optional[dict] = None,
    ) -> dict:
        """Fresh run from the first DAG node."""
        tenant_id = tenant_config.get("client_id", str(uuid.uuid4()))
        run_id = instance_id or str(uuid.uuid4())

        bs = budget_settings or tenant_config.get("budget_governor", {})
        #   # ── Runtime config validation ─────────────────────────────────────────
        from core.config_validator import validate_tenant_config
        validation = validate_tenant_config(tenant_config, strict=False)
        if not validation.valid:
            log.error(
                "Config validation failed — workflow blocked",
                errors=[e.message for e in validation.errors],
                run_id=run_id[:8],
            )
            raise ValueError(
                f"Tenant config has {len(validation.errors)} blocking error(s): "
                + "; ".join(e.message for e in validation.errors[:3])
            )
        if validation.warnings:
            log.warning(
                "Config validation warnings",
                warnings=[w.message for w in validation.warnings],
                run_id=run_id[:8],
            )
        
        async def _check_connectors_background():
            integrations = tenant_config.get("integrations", {})
            for int_name, int_conf in integrations.items():
                if not isinstance(int_conf, dict) or not int_conf.get("enabled"):
                    continue
                # We don't have credentials here (passed in background task) —
                # so this is a lightweight availability pre-check only.
                # Full health check available via GET /connectors/health endpoint.
                log.debug("Connector pre-flight skipped (no creds in orchestrator)", connector=int_name)
 
        asyncio.create_task(_check_connectors_background())
        
        from core.cost_tracker import RunCostTracker
        self._cost_tracker = RunCostTracker(
            run_id=run_id,
            state_manager=self._state,
            budget_settings=bs,
            ws_broadcast=self._ws_broadcast,
        )
        # Initialize system logger
        from core.workflow_logger import WorkflowSystemLogger
        self._sys_logger = WorkflowSystemLogger(run_id, workflow_name, tenant_id)
        self._sys_logger.mark_config_validation(
            len(validation.errors), len(validation.warnings)
        )
        if self._rag and hasattr(self._rag, 'set_workflow_logger'):
            self._rag.set_workflow_logger(self._sys_logger)
        self._llm.set_workflow_logger(self._sys_logger)
        self._llm.set_budget_config(bs, tenant_id=tenant_id)   # Fix D
        self._llm.reset_session()
        self._agent_run_log = []
        self._degraded_nodes = []

        accumulated_context: dict = {
            "trigger_signal": trigger_signal,
            "tenant_id": tenant_id,
            "workflow_name": workflow_name,
            "started_at": datetime.utcnow().isoformat(),
            "patterns": [],
        }

        return await self._run_segment(
            run_id=run_id,
            tenant_config=tenant_config,
            workflow_name=workflow_name,
            trigger_signal=trigger_signal,
            accumulated_context=accumulated_context,
            start_node_index=0,
        )

    async def resume_workflow(
        self,
        instance_id: str,
        additional_context: Optional[dict] = None,
    ) -> dict:
        """
        Resume a suspended workflow.
        Loads accumulated_context + suspension envelope from DB,
        then re-enters _run_segment from the saved resume node.
        """
        accumulated_context, suspension = await self._state.get_suspension_context(instance_id)
        resume_node_id = suspension.get("resume_from_node")

        if additional_context:
            accumulated_context.update(additional_context)

        # Determine the workflow name and tenant_config from the DB instance
        result = await self._state.get_instance(instance_id)
        if not result:
            raise ValueError(f"Instance {instance_id} not found for resumption")

        workflow_name = result.workflow_name
        tenant_config = result.tenant_config or {}
        trigger_signal = accumulated_context.get("trigger_signal", {})

        dag = await self._load_dag(workflow_name)
        if not dag:
            raise ValueError(f"DAG not found: {workflow_name}")
        nodes = dag.get("nodes", [])

        start_idx = 0
        if resume_node_id:
            start_idx = next(
                (i for i, n in enumerate(nodes) if n["id"] == resume_node_id), 0
            )

        self._llm.reset_session()
        self._agent_run_log = []
        self._degraded_nodes = []

        return await self._run_segment(
            run_id=instance_id,
            tenant_config=tenant_config,
            workflow_name=workflow_name,
            trigger_signal=trigger_signal,
            accumulated_context=accumulated_context,
            start_node_index=start_idx,
        )
    async def fork_workflow(
        self,
        new_instance_id: str,
        workflow_name: str,
        tenant_config: dict,
        accumulated_context: dict,
        resume_from_node: str,
        budget_settings: Optional[dict] = None,
    ) -> dict:
        """
        Time-Travel Debugging: replay a workflow from a specific node.
        Uses the provided accumulated_context (reconstructed from original run)
        so expensive earlier agents (Research, etc.) are not re-run.
        """
        tenant_id = tenant_config.get("client_id", accumulated_context.get("tenant_id", ""))

        bs = budget_settings or {}
        self._llm.set_budget_config(bs, tenant_id=tenant_id)
        self._llm.reset_session()
        self._agent_run_log = []
        self._degraded_nodes = []

        dag = await self._load_dag(workflow_name)
        if not dag:
            raise ValueError(f"Workflow DAG not found: {workflow_name}")

        nodes = dag.get("nodes", [])
        start_idx = next(
            (i for i, n in enumerate(nodes) if n["id"] == resume_from_node), 0
        )

        log.info(
            "Forking workflow from checkpoint",
            new_run_id=new_instance_id,
            workflow=workflow_name,
            from_node=resume_from_node,
            start_idx=start_idx,
            ctx_keys=list(accumulated_context.keys()),
        )

        return await self._run_segment(
            run_id=new_instance_id,
            tenant_config=tenant_config,
            workflow_name=workflow_name,
            trigger_signal=accumulated_context.get("trigger_signal", {}),
            accumulated_context=accumulated_context,
            start_node_index=start_idx,
        )
    async def _update_graph_rag(
        self,
        agent_type: str,
        tenant_id: str,
        run_id: str,
        output_data: dict,
        workflow_name: str,
    ) -> None:
        """Update GraphRAG knowledge graph after an agent successfully completes."""
        try:
            if agent_type == "research_agent":
                # SaaS/Healthcare/Finance accounts
                for acc in (output_data.get("accounts") or [])[:20]:
                    acc_id = acc.get("id", "")
                    if acc_id:
                        await self._graph_rag.add_account(tenant_id, acc_id, acc)
                # Real estate listings
                for listing in (output_data.get("listings") or [])[:20]:
                    lid = listing.get("id", "")
                    if lid:
                        await self._graph_rag.add_listing(tenant_id, lid, listing)

            elif agent_type == "memory_agent":
                for pattern in (output_data.get("patterns_to_store") or []):
                    pk = f"{workflow_name}_{pattern.get('key', 'unknown')}"
                    await self._graph_rag.add_pattern(tenant_id, pk, pattern)
                await self._graph_rag.add_workflow_outcome(
                    tenant_id=tenant_id,
                    run_id=run_id,
                    outcome_data={"status": "completed", **output_data},
                )
        except Exception as _ge:
            log.debug("GraphRAG update failed (non-fatal)", agent=agent_type, error=str(_ge))
    # ─────────────────────────────────────────────────────────────────────
    # Core execution loop
    # ─────────────────────────────────────────────────────────────────────

    async def _run_segment(
        self,
        run_id: str,
        tenant_config: dict,
        workflow_name: str,
        trigger_signal: dict,
        accumulated_context: dict,
        start_node_index: int = 0,
    ) -> dict:
        tenant_id = tenant_config.get("client_id", accumulated_context.get("tenant_id", ""))
        a2a_enabled = tenant_config.get("budget_governor", {}).get("a2a_enabled", False)

        # Setup pause event
        if run_id not in self._pause_events:
            self._pause_events[run_id] = asyncio.Event()
        self._pause_events[run_id].set()

        log.info("[WORKFLOW_SETUP_START]", run_id=run_id[:8], workflow=workflow_name)
        # ── Index tool schemas for RAG-based DiscoveryAgent (versioned) ─────
        # Only re-index when the registered tool set or the CustomTool DB table
        # has changed since the last index, saving embedding API calls.
        if self._rag:
            try:
                log.info("[TOOL_REINDEX_CHECK]", run_id=run_id[:8], tenant=tenant_id[:8])
                reindex_required = await asyncio.wait_for(
                    self._needs_tool_reindex(tenant_id), timeout=5
                )
                log.info(
                    "[TOOL_REINDEX_REQUIRED]",
                    run_id=run_id[:8],
                    required=reindex_required,
                )
                if reindex_required:
                    from integrations.tool_registry_builder import index_tools_in_rag
                    log.info("[TOOL_REINDEX_START]", run_id=run_id[:8])
                    indexed = await asyncio.wait_for(
                        index_tools_in_rag(self._tools, self._rag, tenant_id),
                        timeout=10,
                    )
                    _tool_index_cache[tenant_id] = (
                        time.time(),
                        frozenset(self._tools._tools.keys()),
                    )
                    log.info(
                        "[TOOL_REINDEX_COMPLETE]",
                        run_id=run_id[:8],
                        tenant=tenant_id[:8],
                        indexed=indexed,
                    )
                else:
                    log.debug("Tool schemas up-to-date, skipping reindex", tenant=tenant_id[:8])
            except Exception as _idx_err:
                if self._state and self._state._db is not None:
                    try:
                        await asyncio.wait_for(self._state._db.rollback(), timeout=2)
                    except Exception as _rollback_err:
                        log.debug("Optional tool RAG rollback failed", error=str(_rollback_err))
                log.warning(
                    "Tool RAG indexing skipped (non-fatal)",
                    error_type=type(_idx_err).__name__,
                    error=str(_idx_err)[:200],
                )

        dag = await self._load_dag(workflow_name)
        if not dag:
            raise ValueError(f"Workflow DAG not found: {workflow_name}")

        nodes = dag.get("nodes", [])
        edges = {e["to"]: e for e in dag.get("edges", [])}

        await self._broadcast("workflow_running", {
            "run_id": run_id, "workflow": workflow_name, "tenant_id": tenant_id,
            "resuming_from_index": start_node_index,
        })

        outcome: dict = {}
        workflow_status = WorkflowStatus.RUNNING

        async with self._epi.record_workflow(workflow_name, tenant_id) as epi_ctx:
            try:
                i = start_node_index
                while i < len(nodes):
                    node = nodes[i]
                    node_id = node["id"]
                    agent_type = node["agent"]
                    if i == start_node_index:
                        log.info(
                            "[FIRST_NODE_START]",
                            run_id=run_id[:8],
                            node_id=node_id,
                            agent_type=agent_type,
                        )

                    # ── Stop check ────────────────────────────────────────
                    if self._state.should_stop(run_id):
                        workflow_status = WorkflowStatus.STOPPED
                        outcome = {"stopped_by": "admin", "at_node": node_id}
                        await self._broadcast("workflow_stopped",
                                              {"run_id": run_id, "at_node": node_id})
                        break

                    # ── Pause check (asyncio.Event, no busy-wait) ─────────
                    if not self._pause_events[run_id].is_set():
                        workflow_status = WorkflowStatus.PAUSED
                        await self._broadcast("workflow_paused",
                                              {"run_id": run_id, "at_node": node_id})
                        await self._pause_events[run_id].wait()
                        # ── Budget circuit breaker (Phases 2) ─────────────────────────────────
                        if hasattr(self, '_cost_tracker') and self._cost_tracker:
                            try:
                                await self._cost_tracker.check_budget()
                            except BudgetExceededError as _budget_err:
                                if hasattr(self, '_sys_logger') and self._sys_logger:
                                    self._sys_logger.mark_budget_circuit_breaker(
                                        _budget_err.current, _budget_err.limit
                                    )
                                # Force escalation instead of continuing
                                esc_id = await self._create_escalation(
                                    run_id=run_id, tenant_id=tenant_id, node_id=node_id,
                                    output=type('FakeOutput', (), {
                                        'escalate': True,
                                        'escalation_reason': f"Budget limit exceeded: ${_budget_err.current:.5f} > ${_budget_err.limit:.5f}",
                                        'confidence': 0.5,
                                        'output_data': {},
                                    })(),
                                    accumulated_context=accumulated_context,
                                    dag=dag,
                                )
                                workflow_status = WorkflowStatus.ESCALATED
                                outcome = {"status": "escalated", "escalation_id": esc_id,
                                            "reason": "budget_exceeded", "agent_runs": self._agent_run_log}
                                break
                        workflow_status = WorkflowStatus.RUNNING
                        await self._broadcast("workflow_resumed", {"run_id": run_id})

                    # ── Edge condition ────────────────────────────────────
                    if not self._should_run_node(node_id, edges, accumulated_context):
                        accumulated_context[node_id] = {"skipped": True}
                        i += 1
                        continue

                    # ── RAG injection for ReasoningAgent ──────────────────
                    if agent_type == "reasoning_agent" and self._rag:
                        research_data = accumulated_context.get("research", {})
                        rag_ctx = await self._rag.get_historical_context_for_reasoning(
                            tenant_id=tenant_id,
                            situation_description=json.dumps(research_data)[:500],
                            workflow_name=workflow_name,
                        )
                        accumulated_context["_rag_historical_context"] = rag_ctx

                    # ── GraphRAG structural context injection ──────────────
                    if agent_type == "reasoning_agent" and self._graph_rag:
                        try:
                            research_data = accumulated_context.get("research", {})
                            accounts = research_data.get("accounts", [])
                            if accounts:
                                graph_ctx = await self._graph_rag.get_graph_context_for_reasoning(
                                    tenant_id=tenant_id,
                                    current_accounts=accounts[:5],
                                )
                                if graph_ctx:
                                    existing = accumulated_context.get("_rag_historical_context", "")
                                    accumulated_context["_rag_historical_context"] = (
                                        f"{existing}\n\n{graph_ctx}" if existing else graph_ctx
                                    )
                        except Exception as _ge:
                            log.debug("GraphRAG context injection failed (non-fatal)", error=str(_ge))

                    # ── Summarization Bridge (Map-Reduce aware) ───────────────
                    if agent_type == "reasoning_agent":
                        research_data = accumulated_context.get("research", {})
                        if research_data:
                            raw_size = len(json.dumps(research_data, default=str))
                            _map_reduce_on = getattr(self._llm, "_enable_map_reduce", False)
                            should_summarize = (
                                self._llm._optimization_level >= 2
                                or _map_reduce_on
                                or raw_size > 40_000  # auto-trigger above ~10 K tokens
                            )
                            if should_summarize:
                                summary = await self._llm.summarize_for_context(
                                    research_data,
                                    "churn signals, usage drops, high-risk accounts",
                                    force=(_map_reduce_on or raw_size > 40_000),
                                )
                                accumulated_context["_research_summary"] = summary

                    # ── Context pruning ───────────────────────────────────
                    pruned = self._prune_context(node, accumulated_context)
                    if self._llm._optimization_level >= 2:
                        for k, v in list(pruned.items()):
                            if isinstance(v, dict) and "reasoning_chain" in v:
                                pruned[k]["reasoning_chain"] = await self._llm.truncate_reasoning_chain(
                                    v["reasoning_chain"]
                                )

                    # ── DiscoveryAgent: RAG-powered tool selection ─────────────
                    if agent_type == "discovery_agent" or "auto" in node.get("tools", []):
                        rag_tools: list[str] = []
                        if self._rag:
                            try:
                                rag_tools = await self._rag.retrieve_relevant_tools(
                                    query=json.dumps(trigger_signal)[:600],
                                    tenant_id=tenant_id,
                                    top_k=10,
                                )
                            except Exception as _rt_err:
                                log.warning("RAG tool retrieval failed, using full list",
                                            error=str(_rt_err))
                        if rag_tools:
                            node = {
                                **node,
                                "_all_tool_schemas":   self._tools.get_schemas(rag_tools),
                                "_rag_selected_tools": rag_tools,
                            }
                        else:
                            # Fallback: full list capped at 20 to stay within LLM context
                            node = {**node, "_all_tool_schemas": self._tools.get_schemas(
                                list(self._tools._tools.keys())[:20]
                            )}

                    # ── Inject A2A-requested tools (Feature 1: dynamic tool discovery) ─
                    # When an A2A approval included new_tools, merge them into this node
                    # for the duration of this single re-run, then clear from context.
                    _a2a_new_tools = accumulated_context.get("_a2a_new_tools", [])
                    _a2a_target    = accumulated_context.get("_a2a_target_node", "")
                    if _a2a_new_tools and node_id == _a2a_target:
                        existing = list(node.get("tools", []))
                        # dict.fromkeys preserves order and deduplicates
                        merged = list(dict.fromkeys(existing + _a2a_new_tools))
                        node = {**node, "tools": merged}
                        log.info(
                            "A2A: new tools injected into node",
                            node=node_id,
                            added=_a2a_new_tools,
                            merged=merged,
                        )
                        # Consume — only apply once to the target node
                        accumulated_context.pop("_a2a_new_tools", None)
                        accumulated_context.pop("_a2a_target_node", None)
                        
                    if agent_type == "consensus_agent":
                        # ── CONSENSUS PRE-GATE ─────────────────────────────────────────────────────────────
                        # Only applies to consensus_agent nodes. If reasoning confidence >= 0.90,
                        # skip the double-Sonnet debate and use reasoning output directly.
                        reasoning_output = accumulated_context.get("reasoning", {})
                        reasoning_confidence = float(reasoning_output.get("reasoning_confidence", 0.0))
                        gate_threshold = self._llm._consensus_config.get("pre_gate_confidence_threshold", 0.90)
                        
                        if reasoning_confidence >= gate_threshold:
                            log.info(
                                "CONSENSUS GATE: skipping consensus — reasoning confidence is high",
                                run=run_id[:8],
                                confidence=reasoning_confidence,
                                threshold=gate_threshold,
                                cost_saved="~$0.32 (2x Sonnet avoided)",
                            )
                            if hasattr(self, '_sys_logger') and self._sys_logger:
                                self._sys_logger.mark_consensus_gate(passed=True, confidence=reasoning_confidence)
                            # Inject reasoning output as consensus output — downstream agents proceed
                            accumulated_context[node_id] = {
                                **reasoning_output,
                                "consensus": True,
                                "agreement_score": 1.0,
                                "reasoning_confidence": reasoning_confidence,
                                "_gate_bypassed": True,
                                "_gate_reason": f"Reasoning confidence {reasoning_confidence:.0%} >= gate {gate_threshold:.0%}",
                            }
                            await self._broadcast("agent_completed", {
                                "run_id": run_id,
                                "node_id": node_id,
                                "agent_type": agent_type,
                                "success": True,
                                "confidence": reasoning_confidence,
                                "cost_usd": 0.0,
                                "tenant_id": tenant_id,
                                "output_preview": json.dumps({"consensus": True, "gate_bypassed": True, "confidence": reasoning_confidence}),
                            })
                            i += 1
                            continue  # Skip spawning the actual ConsensusAgent
                        else:
                            if hasattr(self, '_sys_logger') and self._sys_logger:
                                self._sys_logger.mark_consensus_gate(passed=False, confidence=reasoning_confidence)
                    # ── Adaptive max_tokens ───────────────────────────────────────────────
                    _adaptive_max_tokens: Optional[int] = None
                    if agent_type == "research_agent" or agent_type == "discovery_agent":
                        _adaptive_max_tokens = 8192  # Provide max room for raw data extraction
                    elif agent_type in ("reasoning_agent", "drafting_agent"):
                        research_data = accumulated_context.get("research", {})
                        # Check all entity types across all industries
                        account_count = len(
                            research_data.get("accounts")
                            or research_data.get("deals")
                            or research_data.get("patients")
                            or research_data.get("transactions")
                            or research_data.get("listings")   # real estate
                            or research_data.get("leases")     # real estate PM
                            or []
                        )
                        if account_count > 0:
                            TOKENS_PER_ACCOUNT = 600
                            BASE_MAX = 8192
                            ABSOLUTE_MAX = 32768
                            _adaptive_max_tokens = min(
                                ABSOLUTE_MAX,
                                max(BASE_MAX, int(account_count * TOKENS_PER_ACCOUNT * 1.3))
                            )
                            log.debug(
                                "Adaptive max_tokens computed (not mutating shared state)",
                                agent=agent_type,
                                accounts=account_count,
                                max_tokens=_adaptive_max_tokens,
                            )
                    
                    if agent_type == "execution_agent":
                        oh = tenant_config.get("business_rules", {}).get("operating_hours", {})
                        if oh.get("respect_hours_for_outreach"):
                            
                            tz_name = oh.get("timezone", "UTC")
                            try:
                                tz = pytz.timezone(tz_name)
                                now_local = datetime.now(tz)
                                hours_str = oh.get("hours", "8am-6pm")
                                days_str = oh.get("days", "Mon-Fri")
                                
                                # Simple weekday check
                                weekday = now_local.weekday()  # 0=Mon, 6=Sun
                                is_weekday = weekday < 5
                                
                                _WORK_DAY_CONFIGS = {
                                    "Mon-Fri": {0, 1, 2, 3, 4},
                                    "Monday-Friday": {0, 1, 2, 3, 4},
                                    "Mon-Sat": {0, 1, 2, 3, 4, 5},
                                    "Monday-Saturday": {0, 1, 2, 3, 4, 5},
                                    "Mon-Sun": set(range(7)),
                                }
                                allowed_days = _WORK_DAY_CONFIGS.get(days_str, {0, 1, 2, 3, 4})
                                if weekday not in allowed_days:
                                    log.info(
                                        "Operating hours: skipping execution (weekend)",
                                        run=run_id[:8],
                                        local_time=now_local.strftime("%Y-%m-%d %H:%M %Z"),
                                    )
                                    # Store approved drafts for later execution, skip for now
                                    accumulated_context[node_id] = {
                                        "emails_queued": 0,
                                        "actions_taken": [],
                                        "_skipped_reason": "outside_operating_hours",
                                        "_local_time": now_local.isoformat(),
                                        "_scheduled_for": "next_business_day",
                                    }
                                    i += 1
                                    continue
                            except Exception as _tz_err:
                                log.debug("Operating hours check failed (non-fatal)", error=str(_tz_err))
                    # ── Phase 3: Strict Runtime Tool Isolation based on trigger_signal.source ─────
                    req_source = (trigger_signal or {}).get("source") or accumulated_context.get("trigger_signal", {}).get("source")
                    if workflow_name == "email_summarizer" or node_id == "fetch_emails":
                        if req_source == "real_gmail":
                            if "gmail_read_messages" not in self._tools._tools:
                                log.error("GMAIL_SOURCE_UNAVAILABLE: Real Gmail requested but gmail_read_messages missing from registry", run=run_id[:8])
                                raise RuntimeError("GMAIL_SOURCE_UNAVAILABLE: Real Gmail could not be accessed. No synthetic data was used.")
                            node = {**node, "tools": ["gmail_read_messages"]}
                        elif req_source == "synthetic_demo":
                            node = {**node, "tools": ["email_get_synthetic_messages"]}

                    # ── Build input & run agent ───────────────────────────────────────
                    agent_input = AgentInput(
                        workflow_instance_id=run_id,
                        tenant_id=tenant_id,
                        tenant_config=tenant_config,
                        accumulated_context=pruned,
                        node_specific_data={**node, "trigger_signal": trigger_signal, "_max_tokens_override": _adaptive_max_tokens},
                        llm_overrides=tenant_config.get("llm_overrides", {}),
                    )
                    agent = self._spawn_agent(agent_type)
                    # Inject context for live broadcasting
                    agent._current_node_id = node_id
                    agent._current_run_id  = run_id
                    node_start = time.time()

                    # Pre-flight cost estimate
                    try:
                        ctx_str              = json.dumps(pruned, default=str)
                        est_tokens_in        = len(ctx_str) // 4
                        agent_tier           = self._llm._agent_defaults.get(agent_type, {}).get("tier", "balanced")
                        est_model            = self._llm._task_models.get(agent_tier, {}).get("model", "")
                        est_input_cost       = self._llm._calculate_cost(est_model, est_tokens_in, 0)
                        output_rate          = self._llm._cost_rates.get(est_model, {}).get("output", 0.0)
                        output_cost_per_token = round(output_rate / 1_000_000, 9)
                    except Exception:
                        est_tokens_in, est_input_cost, est_model, output_cost_per_token = 0, 0.0, "", 0.0

                    await self._broadcast("agent_started", {
                        "run_id":                run_id,
                        "node_id":               node_id,
                        "agent_type":            agent_type,
                        "tenant_id":             tenant_id,
                        "model_estimate":        est_model,
                        "tokens_in_estimate":    est_tokens_in,
                        "input_cost_estimate":   round(est_input_cost, 6) if est_input_cost is not None else None,
                        "output_cost_per_token": output_cost_per_token,
                    })

                    try:
                        output: AgentOutput = await agent.receive(agent_input)
                    except Exception as e:
                        log.error("Agent raised exception", node=node_id, error=str(e))
                        recovery = await self._rag.get_error_recovery_hints(tenant_id, str(e)) if self._rag else ""
                        output = AgentOutput(
                            success=False, confidence=0.0,
                            output_data={"recovery_hints": recovery},
                            reasoning_chain="", error=str(e),
                            provider_attempts=getattr(e, "attempts", None),
                        )

                    # ── Phase 3 & 9: Strict Real Gmail Failure Check (Zero Synthetic Fallback) ──────
                    if (workflow_name == "email_summarizer" or node_id == "fetch_emails") and req_source == "real_gmail":
                        _is_synth = isinstance(output.output_data, dict) and output.output_data.get("data_origin") == "synthetic"
                        if not output.success or output.error or _is_synth:
                            err_msg = output.error or ("Returned synthetic data instead of Real Gmail" if _is_synth else "Gmail API failure")
                            log.error("GMAIL_SOURCE_UNAVAILABLE: Real Gmail execution failed", run=run_id[:8], error=err_msg)
                            raise RuntimeError(f"GMAIL_SOURCE_UNAVAILABLE: Real Gmail could not be accessed ({err_msg}). No synthetic data was used.")
                    
                    # ── Parse-error self-healing: retry once with conciseness hint ──────
                    # If the LLM hit max_tokens and output was truncated (even after
                    # recovery), we get parse_error=True OR _json_recovered=True.
                    # For _json_recovered we continue (partial data is usable).
                    # For parse_error we retry once with an explicit conciseness hint.
                    _out_data = output.output_data if output.success else {}
                    _is_parse_error = (
                        isinstance(_out_data, dict)
                        and _out_data.get("parse_error")
                        and not agent_input.node_specific_data.get("_parse_error_retry")
                    )
                    if _is_parse_error:
                        log.warning(
                            "Agent JSON parse error — retrying with conciseness hint",
                            node=node_id,
                            agent=agent_type,
                        )
                        _retry_input = AgentInput(
                            workflow_instance_id=agent_input.workflow_instance_id,
                            tenant_id=agent_input.tenant_id,
                            tenant_config=agent_input.tenant_config,
                            accumulated_context=agent_input.accumulated_context,
                            node_specific_data={
                                **agent_input.node_specific_data,
                                "_parse_error_retry": True,
                                "_recovery_hint": (
                                    "CRITICAL: Your previous response was too long and was "
                                    "cut off before the JSON was complete.\n"
                                    "Rules for this retry:\n"
                                    "1. Return ONLY valid, complete JSON — no other text.\n"
                                    "2. Limit every list to a MAXIMUM of 5 items. "
                                    "   Choose the most important ones.\n"
                                    "3. Keep string values SHORT (under 100 chars each).\n"
                                    "4. Omit optional/verbose fields — keep only what the "
                                    "   schema requires.\n"
                                    "5. The JSON object MUST end with a closing '}'."
                                ),
                            },
                            llm_overrides=agent_input.llm_overrides,
                        )
                        try:
                            output = await agent.receive(_retry_input)
                            log.info(
                                "Parse-error retry succeeded",
                                node=node_id,
                                parse_error_still=output.output_data.get("parse_error", False),
                            )
                        except Exception as _retry_exc:
                            log.error(
                                "Parse-error retry raised exception",
                                node=node_id,
                                error=str(_retry_exc),
                            )
                            # Keep the original failed output; it will be handled below

                    node_dur_ms = int((time.time() - node_start) * 1000)

                    # Build a concise output preview for the live card
                    _output_preview = ""
                    if output.success and isinstance(output.output_data, dict):
                        _preview_keys = [
                            "situation_summary", "urgency", "summary",
                            "patterns_updated", "emails_queued", "actions_taken",
                            "passed", "delta_vs_history", "consensus",
                        ]
                        _preview_data = {k: output.output_data[k] for k in _preview_keys if k in output.output_data}
                        if not _preview_data:
                            _preview_data = dict(list(output.output_data.items())[:5])
                        _output_preview = json.dumps(_preview_data, default=str)[:350]

                    # Classify error for developer visibility
                    _error_info = None
                    if output.error:
                        try:
                            from core.llm_router import LLMRouter
                            _error_info = LLMRouter.classify_llm_error(Exception(output.error))
                        except Exception:
                            _error_info = {"error_type": "unknown", "error_message": str(output.error)[:200], "provider": "unknown", "safe_detail": str(output.error)[:300]}

                    await self._broadcast("agent_completed", {
                        "run_id":              run_id,
                        "node_id":             node_id,
                        "agent_type":          agent_type,
                        "success":             output.success,
                        "confidence":          output.confidence,
                        "cost_usd":            output.cost_usd,
                        "tokens_in":           output.tokens_in,
                        "tokens_out":          output.tokens_out,
                        "model_used":          output.model_used,
                        "tenant_id":           tenant_id,
                        "output_preview":      _output_preview,
                        "tools_used":          list(node.get("tools", [])),
                        "duration_ms":         node_dur_ms,
                        "error":               output.error,
                        "error_type":          _error_info.get("error_type") if _error_info else None,
                        "error_message":       _error_info.get("error_message") if _error_info else None,
                        "error_provider":      _error_info.get("provider") if _error_info else None,
                        "error_safe_detail":   _error_info.get("safe_detail") if _error_info else None,
                        "llm_attempted":       output.model_used is not None and output.model_used != "",
                        "_prosecutor_issues":  output.output_data.get("_prosecutor_issues") if output.success and isinstance(output.output_data, dict) else None,
                        "_judge_verdict":      output.output_data.get("_judge_verdict")     if output.success and isinstance(output.output_data, dict) else None,
                        "delta_analysis":      output.output_data.get("delta_analysis")     if output.success and isinstance(output.output_data, dict) else None,
                        "delta_vs_history":    output.output_data.get("delta_vs_history")   if output.success and isinstance(output.output_data, dict) else None,
                        "delta_trend":         output.output_data.get("delta_trend")        if output.success and isinstance(output.output_data, dict) else None,
                    })
                    try:
                        await epi_ctx.log_agent_run(
                            node_id=node_id, agent_type=agent_type,
                            input_summary={"context_keys": list(pruned.keys())},
                            output_summary=output.output_data,
                            confidence=output.confidence,
                            reasoning=output.reasoning_chain,
                            tokens_in=output.tokens_in, tokens_out=output.tokens_out,
                            cost_usd=output.cost_usd, model=output.model_used,
                        )
                    except Exception as _epi_err:
                        log.warning(
                            "EPI agent-step recording skipped (non-fatal)",
                            node=node_id,
                            error_type=type(_epi_err).__name__,
                            error=str(_epi_err)[:200],
                        )
                    # Streaming evidence: persist agent step immediately
                    try:
                        from api import crud as _crud
                        if self._state and self._state._db:
                            await self._state._db.execute(
                                __import__("sqlalchemy").text(
                                    "UPDATE workflow_instances "
                                    "SET outcome = jsonb_set(COALESCE(outcome, '{}'), "
                                    "'{_epi_steps}', COALESCE(outcome->'_epi_steps', '[]') || CAST(:step AS JSONB)) "
                                    "WHERE id = :rid"
                                ),
                                {
                                    "step": __import__("json").dumps({
                                        "node_id": node_id,
                                        "agent_type": agent_type,
                                        "cost_usd": output.cost_usd,
                                        "confidence": output.confidence,
                                        "ts": __import__("datetime").datetime.utcnow().isoformat(),
                                    }),
                                    "rid": run_id,
                                }
                            )
                            await self._state._db.commit()
                    except Exception:
                        pass  # Non-fatal

                    _persisted_output = _prepare_output_for_persistence(output.output_data)
                    if isinstance(_persisted_output, dict):
                        _persisted_output["_runtime"] = {
                            "provider": output.provider,
                            "model": output.model_used or None,
                            "input_tokens": output.tokens_in,
                            "output_tokens": output.tokens_out,
                            "cached_tokens": output.cached_tokens,
                            "cost_usd": output.cost_usd,
                            "latency_ms": node_dur_ms,
                            "fallback_used": output.fallback_used,
                            "fallback_from": output.fallback_from,
                            "fallback_reason": output.fallback_reason,
                            "provider_attempts": output.provider_attempts,
                        }
                    agent_run_record = {
                        "node_id": node_id, "agent_type": agent_type,
                        "status": "success" if output.success else "failed",
                        "confidence": output.confidence,
                        "tokens_in": output.tokens_in, "tokens_out": output.tokens_out,
                        "cost_usd": output.cost_usd, "model_used": output.model_used,
                        "provider": output.provider,
                        "cached_tokens": output.cached_tokens,
                        "fallback_used": output.fallback_used,
                        "fallback_from": output.fallback_from,
                        "fallback_reason": output.fallback_reason,
                        "provider_attempts": output.provider_attempts,
                        "output_data": _persisted_output,
                        "duration_ms": node_dur_ms, "error": output.error,
                        "error_type": _error_info.get("error_type") if _error_info else None,
                        "error_message": _error_info.get("error_message") if _error_info else None,
                        "error_provider": _error_info.get("provider") if _error_info else None,
                        "error_safe_detail": _error_info.get("safe_detail") if _error_info else None,
                        "llm_attempted": output.model_used is not None and output.model_used != "",
                        "completed_at": datetime.utcnow().isoformat(),
                        "tools_used": list(node.get("tools", [])),
                        "node_description": node.get("description", ""),
                    }
                    # Attach per-agent UI metadata (surfaced in WorkflowDetail)
                    if output.success and isinstance(output.output_data, dict):
                        if agent_type == "memory_agent":
                            agent_run_record["delta_analysis"]   = output.output_data.get("delta_analysis")
                            agent_run_record["delta_vs_history"] = output.output_data.get("delta_vs_history")
                            agent_run_record["delta_trend"]      = output.output_data.get("delta_trend")
                        elif agent_type == "verification_agent":
                            agent_run_record["_prosecutor_issues"] = output.output_data.get("_prosecutor_issues")
                            agent_run_record["_judge_verdict"]     = output.output_data.get("_judge_verdict")
                            agent_run_record["_prosecutor_faults"] = output.output_data.get("_prosecutor_faults", [])
                    self._agent_run_log.append(agent_run_record)
                    if self._state:
                        try:
                            await self._state.write_agent_run_record(run_id, agent_run_record)
                        except Exception as _we:
                            log.warning("Failed to write agent run record to DB", error=str(_we))
                    if self._agent_run_cb:
                        try:
                            await self._agent_run_cb(run_id, agent_run_record)
                        except Exception as cb_e:
                            log.warning("agent_run_callback error", error=str(cb_e))

                    # ── HITL Action Center Approval Items ───────────────────────
                    if output.success and isinstance(output.output_data, dict):
                        appr_list = [] if node.get("suppress_approval_creation") else output.output_data.get("approval_items") or []
                        if isinstance(appr_list, dict):
                            appr_list = [appr_list]
                        for appr in appr_list:
                            if isinstance(appr, dict) and self._state:
                                try:
                                    created_appr = await self._state.create_approval_item(
                                        organization_id=tenant_id,
                                        instance_id=run_id,
                                        node_id=node_id,
                                        review_type=appr.get("action_type", "email_response"),
                                        reason=appr.get("reason", "AI identified item requiring human approval"),
                                        context_brief=appr.get("title", f"Approval required at {node_id}"),
                                        payload=appr,
                                        required_signatures=appr.get("required_signatures", 1),
                                    )
                                    await self._broadcast("approval_created", {
                                        "approval_id": str(created_appr.id),
                                        "id": str(created_appr.id),
                                        "run_id": run_id,
                                        "organization_id": tenant_id,
                                        "tenant_id": tenant_id,
                                        "review_type": created_appr.review_type,
                                        "title": created_appr.context_brief,
                                        "reason": created_appr.reason,
                                    })
                                except Exception as _ae:
                                    log.warning("Failed to create ApprovalItem from agent output", error=str(_ae))

                    accumulated_context[node_id] = output.output_data

                    # ── GraphRAG knowledge graph update ────────────────────
                    if output.success and self._graph_rag:
                        await self._update_graph_rag(
                            agent_type=agent_type,
                            tenant_id=tenant_id,
                            run_id=run_id,
                            output_data=output.output_data,
                            workflow_name=workflow_name,
                        )
                    # Get max_a2a_attempts from DAG meta (default 3)
                    max_a2a = dag.get("_meta", {}).get("max_a2a_attempts", 3)   
                    # ── A2A Protocol — event-driven, NO POLLING ──────────
                    a2a_req = output.output_data.get("a2a_request")
                    if a2a_req and isinstance(a2a_req, dict) and a2a_enabled:
                        # Check loop limit
                        current_loops = await self._state.increment_loop_count(run_id)
                        if current_loops > max_a2a:
                            log.warning(
                                "A2A loop limit reached — forcing hard escalation",
                                run_id=run_id,
                                loops=current_loops,
                                max_loops=max_a2a,
                            )
                            output.escalate = True
                            output.escalation_reason = (
                                f"A2A loop limit ({max_a2a}) reached. "
                                "Underlying prompt or tool issue requires admin review. "
                                "Original A2A reason: " + a2a_req.get("reason", "")
                            )# Fall through to escalation handling below
                        else:
                            target_node_id = a2a_req.get("target_agent_node_id", "research")
                            new_tools = a2a_req.get("new_tools", [])   # Feature 1
                            a2a_record = await self._state.create_a2a_request(
                                instance_id=run_id, tenant_id=tenant_id,
                                requesting_agent=agent_type,
                                target_agent=a2a_req.get("target_agent", "research_agent"),
                                target_node_id=target_node_id,
                                reason=a2a_req.get("reason", ""),
                                refinement_note=a2a_req.get("refinement_note", ""),
                                estimated_cost_usd=a2a_req.get("estimated_cost_usd", 0.001),
                                new_tools=new_tools,                   # Feature 1
                            )
                            # Resume point: go back to the target agent node
                            resume_from = target_node_id
                            await self._state.suspend_workflow(
                                instance_id=run_id,
                                resume_from_node=resume_from,
                                context=_prune_context_for_storage(accumulated_context),
                                status=WorkflowStatus.PENDING_A2A,
                                extra={
                                    "a2a_id": str(a2a_record.id),
                                    "new_tools": new_tools,
                                },
                            )
                            await self._broadcast("a2a_permission_requested", {
                                "a2a_id": str(a2a_record.id),
                                "run_id": run_id, "tenant_id": tenant_id,
                                "requesting_agent": agent_type,
                                "target_agent": a2a_req.get("target_agent"),
                                "reason": a2a_req.get("reason", ""),
                                "refinement_note": a2a_req.get("refinement_note", ""),
                                "estimated_cost_usd": a2a_req.get("estimated_cost_usd", 0.001),
                                "new_tools": new_tools,                 # Feature 1
                            })
                            workflow_status = WorkflowStatus.PENDING_A2A
                            outcome = {"status": "pending_a2a", "a2a_id": str(a2a_record.id),
                                    "at_node": node_id, "agent_runs": self._agent_run_log}
                            break  # Exit segment — API will resume on decision

                    # ── Escalation — event-driven, NO POLLING ────────────
                    if output.escalate and not node.get("suppress_approval_creation"):
                        esc_id = await self._create_escalation(
                            run_id=run_id, tenant_id=tenant_id, node_id=node_id,
                            output=output, accumulated_context=accumulated_context, dag=dag,
                        )
                        # Resume point: the node AFTER the escalating one
                        next_node_id = nodes[i + 1]["id"] if i + 1 < len(nodes) else None
                        await self._state.suspend_workflow(
                            instance_id=run_id,
                            resume_from_node=next_node_id,
                            context=_prune_context_for_storage(accumulated_context),
                            status=WorkflowStatus.ESCALATED,
                            extra={"escalation_id": esc_id},
                        )
                        if self._escalation_cb:
                            try:
                                # Provide esc_data to callback
                                from core.orchestrator import _pending_escalations
                                await self._escalation_cb(esc_id, _pending_escalations.get(esc_id, {}))
                            except Exception:
                                pass
                        workflow_status = WorkflowStatus.ESCALATED
                        outcome = {"status": "escalated", "escalation_id": esc_id,
                                   "at_node": node_id, "reason": output.escalation_reason,
                                   "agent_runs": self._agent_run_log}
                        break  # Exit segment — API will resume on decision

                    # ── Failure check + Reflexion Self-Healing ─────────────────────────────
                    if not output.success:
                        if output.error in ("AI_PROVIDER_UNAVAILABLE", "INPUT_CONTEXT_MISSING"):
                            workflow_status = WorkflowStatus.FAILED
                            outcome = {
                                "error": output.error,
                                "failed_node": node_id,
                                "status": output.error,
                            }
                            break
                        MAX_REFLEXION = 3
                        last_error    = output.error or "unknown error"

                        for _reflex_attempt in range(MAX_REFLEXION):
                            _rag_hint = ""
                            if self._rag:
                                try:
                                    _rag_hint = await self._rag.get_error_recovery_hints(
                                        tenant_id, last_error
                                    )
                                except Exception:
                                    pass

                            _reflex_input = AgentInput(
                                workflow_instance_id=agent_input.workflow_instance_id,
                                tenant_id=agent_input.tenant_id,
                                tenant_config=agent_input.tenant_config,
                                accumulated_context=agent_input.accumulated_context,
                                node_specific_data={
                                    **agent_input.node_specific_data,
                                    "_recovery_hint": (
                                        f"REFLEXION ATTEMPT {_reflex_attempt + 1}/{MAX_REFLEXION}\n"
                                        f"Your previous attempt failed with this exact error:\n"
                                        f"[Error]: {last_error}\n\n"
                                        + (f"RAG recovery hint: {_rag_hint}\n\n" if _rag_hint else "")
                                        + "Study the error carefully. Correct your approach and try again.\n"
                                        "If the error is a JSON parse issue, return shorter, simpler JSON.\n"
                                        "If a tool failed, try a different argument or skip that tool."
                                    ),
                                    "_reflexion_attempt": _reflex_attempt + 1,
                                },
                                llm_overrides=agent_input.llm_overrides,
                            )
                            try:
                                output = await agent.receive(_reflex_input)
                            except Exception as _re:
                                last_error = str(_re)
                                log.warning(
                                    "Reflexion attempt raised exception",
                                    node=node_id,
                                    attempt=_reflex_attempt + 1,
                                    error=last_error[:100],
                                )
                                continue

                            if output.success:
                                log.info(
                                    "Reflexion succeeded",
                                    node=node_id,
                                    attempt=_reflex_attempt + 1,
                                )
                                break

                            last_error = output.error or "unknown error"
                            log.warning(
                                "Reflexion attempt failed",
                                node=node_id,
                                attempt=_reflex_attempt + 1,
                                error=last_error[:100],
                            )

                        if not output.success:
                            # Store final failure pattern for future runs
                            if self._rag:
                                try:
                                    await self._rag.store_error_context(
                                        tenant_id=tenant_id,
                                        run_id=run_id,
                                        workflow_name=workflow_name,
                                        error_description=f"[{agent_type}:{node_id}] {last_error}",
                                        recovery_action=f"Reflexion failed after {MAX_REFLEXION} attempts",
                                    )
                                except Exception:
                                    pass
                            workflow_status = WorkflowStatus.FAILED
                            outcome = {"error": last_error, "failed_node": node_id}
                            break

                    i += 1

                # ── Segment complete ───────────────────────────────────────
                if workflow_status == WorkflowStatus.RUNNING:
                    workflow_status = WorkflowStatus.COMPLETED
                    live = self._llm.get_live_stats()
                    reasoning_out = accumulated_context.get("reasoning", {})
                    execution_out = accumulated_context.get("execution", {})
                    memory_out    = accumulated_context.get("memory", {})
                    verification_out = accumulated_context.get("verification", {})
                    outcome = {
                        "status": "completed",
                        "nodes_completed": len([n for n in nodes if n["id"] in accumulated_context]),
                        "total_tokens_in": live["total_tokens_in"],
                        "total_tokens_out": live["total_tokens_out"],
                        "total_cost_usd": round(lc, 6) if (lc := live.get("total_cost_usd")) is not None else None,
                        "cache_hits": live.get("cache_hits", 0),
                        "optimization_level": live.get("optimization_level", 1),
                        "by_agent": live["by_agent"],
                        "completed_at": datetime.utcnow().isoformat(),
                        "agent_runs": self._agent_run_log,
                        # Analysis summary fields for WorkflowSummary UI
                        "situation_summary": reasoning_out.get("situation_summary", ""),
                        "urgency": reasoning_out.get("urgency", ""),
                        "reasoning_confidence": reasoning_out.get("reasoning_confidence"),
                        "memory_summary": memory_out.get("summary", "") if isinstance(memory_out, dict) else "",
                        "delta_analysis": memory_out.get("delta_analysis") if isinstance(memory_out, dict) else None,
                        "actions_summary": (
                            [{"action": a.get("action", ""), "status": a.get("status", ""), "account_id": a.get("account_id", "")}
                             for a in (execution_out.get("actions_taken") or [])[:10]]
                            if isinstance(execution_out, dict) else []
                        ),
                        "verification_summary": {
                            "passed": verification_out.get("passed"),
                            "approved_count": len(verification_out.get("approved_drafts") or []),
                            "rejected_count": len(verification_out.get("rejected_drafts") or []),
                            "prosecutor_issues": verification_out.get("_prosecutor_issues", 0),
                        } if isinstance(verification_out, dict) else {},
                    }
                    
                    # Store accumulated_context in DB for Time-Travel fork capability
                    if self._state and self._state._db:
                        try:
                            await self._state.update_context(
                                run_id,
                                _prune_context_for_storage(accumulated_context),
                            )
                        except Exception as _ctx_e:
                            log.debug("Context storage for Time-Travel failed (non-fatal)", error=str(_ctx_e))
                    if self._rag:
                        reasoning_out = accumulated_context.get("reasoning", {})
                        execution_out = accumulated_context.get("execution", {})
                        await self._rag.store_workflow_outcome(
                            tenant_id=tenant_id, run_id=run_id,
                            workflow_name=workflow_name,
                            situation_summary=reasoning_out.get("situation_summary", ""),
                            reasoning_chain=reasoning_out.get("reasoning_chain", ""),
                            actions_taken=execution_out.get("actions_taken", []),
                            outcome_indicator="positive" if execution_out else "escalated",
                            cost_usd=live["total_cost_usd"],
                        )
                    await self._broadcast("workflow_completed", {
                        "run_id": run_id, "tenant_id": tenant_id,
                        "workflow": workflow_name, "cost_usd": outcome.get("total_cost_usd", 0),
                    })

            except Exception as e:
                log.error(
                    "Workflow engine error",
                    error=str(e),
                    workflow=workflow_name,
                    traceback=traceback.format_exc(limit=8),
                )
                workflow_status = WorkflowStatus.FAILED
                outcome = {
                    "error": str(e),
                    "status": "engine_error",
                    "traceback": traceback.format_exc(limit=8),
                }
                await self._broadcast("workflow_failed",
                                      {"run_id": run_id, "error": str(e), "tenant_id": tenant_id})
            finally:
                self._pause_events.pop(run_id, None)

        return {
            "run_id": run_id,
            "workflow": workflow_name,
            "tenant_id": tenant_id,
            "status": workflow_status,
            "outcome": outcome,
            "llm_stats": self._llm.get_live_stats(),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Admin Controls
    # ─────────────────────────────────────────────────────────────────────

    def signal_pause(self, run_id: str) -> None:
        if run_id in self._pause_events:
            self._pause_events[run_id].clear()
        self._state.signal_pause(run_id)

    def signal_resume(self, run_id: str) -> None:
        if run_id in self._pause_events:
            self._pause_events[run_id].set()
        self._state.signal_resume(run_id)

    def signal_stop(self, run_id: str) -> None:
        self._state.signal_stop(run_id)
        if run_id in self._pause_events:
            self._pause_events[run_id].set()

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    async def _needs_tool_reindex(self, tenant_id: str) -> bool:
        """
        Return True if tool schemas should be re-indexed into RAG.
 
        Short-circuits when:
        - The exact same set of tool names was indexed in this process instance, AND
        - No CustomTool row has been created after the last index.
        """
        current_tools = frozenset(self._tools._tools.keys())
        cached = _tool_index_cache.get(tenant_id)
 
        if cached is None:
            return True  # Never indexed in this process
 
        cached_time, cached_tools = cached
 
        # Registered tool names changed (new integration connected mid-session)
        if cached_tools != current_tools:
            return True
 
        # Check if any tenant-specific CustomTool was added since last index
        if self._state and self._state._db is not None:
            try:
                from sqlalchemy import select, func
                from core.state_manager import CustomTool
                result = await self._state._db.execute(
                    select(func.max(CustomTool.created_at)).where(
                        CustomTool.tenant_id == tenant_id
                    )
                )
                max_created = result.scalar_one_or_none()
                if max_created and max_created.timestamp() > cached_time:
                    return True
            except Exception as _e:
                log.debug("Tool version check failed, re-indexing conservatively", error=str(_e))
                return True
 
        return False
 
    def _spawn_agent(self, agent_type: str) -> BaseAgent:
        if agent_type == "discovery_agent":
            cls = _get_discovery_agent()
        elif agent_type == "consensus_agent":
            from agents.consensus_agent import ConsensusAgent
            cls = ConsensusAgent
        else:
            cls = AGENT_MAP.get(agent_type)
        if not cls:
            raise ValueError(f"Unknown agent type: {agent_type}")
        # Pass rag_engine so MemoryAgent (and future agents) can store directly to RAG
        return cls(self._llm, self._state, self._tools, self._ws_broadcast, self._rag)

    async def _load_dag(self, workflow_name: str) -> Optional[dict]:
        path = Path("workflows/dags") / f"{workflow_name}.json"
        if not path.exists():
            return None
        async with aiofiles.open(path) as f:
            return json.loads(await f.read())

    def _prune_context(self, node: dict, ctx: dict) -> dict:
        depends_on = node.get("depends_on", [])
        if not depends_on:
            return dict(ctx)
        pruned = {
            "trigger_signal": ctx.get("trigger_signal"),
            "tenant_id": ctx.get("tenant_id"),
            "workflow_name": ctx.get("workflow_name"),
            "patterns": ctx.get("patterns", []),
            "_rag_historical_context": ctx.get("_rag_historical_context", ""),
            "_a2a_refinement_note": ctx.get("_a2a_refinement_note", ""),
        }
        for dep in depends_on:
            if dep in ctx:
                pruned[dep] = ctx[dep]
        if "_research_summary" in ctx:
            pruned["_research_summary"] = ctx["_research_summary"]
        return pruned

    def _should_run_node(self, node_id: str, edges: dict, ctx: dict) -> bool:
        edge = edges.get(node_id)
        if not edge:
            return True
            
        condition = edge.get("condition")
        if not condition:
            return True
            
        if condition not in ALLOWED_EDGE_CONDITIONS:
            # Unknown condition: log it and default to True (run the node)
            # This prevents arbitrary code execution via crafted DAG JSON (SEC-006)
            log.warning(
                "DAG edge condition not in whitelist — defaulting to True. "
                "Add to ALLOWED_EDGE_CONDITIONS in base_agent.py if intentional.",
                condition=condition,
                node_id=node_id,
            )
            return True
 
        # Build eval context: wrap every dict value in _AttrDict so that
        # attribute access like 'output.escalate' returns None (falsy) instead
        # of raising AttributeError when the key is absent.
        eval_ctx: dict = {}
        for k, v in ctx.items():
            if isinstance(v, dict):
                eval_ctx[k] = _AttrDict(v)
 
        # 'output' is the most-recent non-meta agent result
        non_meta = [
            k for k in ctx
            if not k.startswith("_")
            and k not in ("trigger_signal", "tenant_id", "workflow_name",
                          "patterns", "started_at")
            and isinstance(ctx[k], dict)
        ]
        if non_meta:
            eval_ctx["output"] = _AttrDict(ctx[non_meta[-1]])
 
        # If the last agent produced a parse_error and the condition checks
        # output.escalate, treat escalate as False (don't block the pipeline
        # on a JSON parse failure — let downstream agents try to recover).
        last_output = ctx.get(non_meta[-1], {}) if non_meta else {}
        if (isinstance(last_output, dict)
                and last_output.get("parse_error")
                and "escalate" in condition):
            log.warning(
                "Edge condition: upstream parse_error — treating escalate=False",
                condition=condition,
                node=node_id,
            )
            # 'not output.escalate' → True (run the node)
            # 'output.escalate'     → False (skip the node)
            return "not" in condition
 
        # --- Try simpleeval first (handles complex expressions) ---
        try:
            from simpleeval import EvalWithCompoundTypes
            return bool(EvalWithCompoundTypes(names=eval_ctx).eval(condition))
        except ImportError:
            pass
        except Exception as e:
            log.debug("simpleeval failed", condition=condition, error=str(e))
            # Fall through to string-pattern fallbacks
 
        # --- String pattern fallbacks (order matters) ---
        if "not output.escalate" in condition:
            return not any(
                isinstance(v, dict) and v.get("escalate", False)
                for v in ctx.values()
            )
        if condition in ("output.escalate", "output['escalate']"):
            return any(
                isinstance(v, dict) and v.get("escalate", False)
                for v in ctx.values()
            )
        if "output.passed" in condition:
            negate = "not " in condition
            passed = bool((ctx.get("verification") or {}).get("passed", False))
            return not passed if negate else passed
        if "output.success" in condition:
            negate = "not " in condition
            last = eval_ctx.get("output", _AttrDict())
            success = bool(last.get("success", True))
            return not success if negate else success
 
        log.warning(
            "Unrecognised edge condition — defaulting to True", condition=condition
        )
        return True

    async def _create_escalation(
        self,
        run_id: str,
        tenant_id: str,
        node_id: str,
        output: AgentOutput,
        accumulated_context: dict,
        dag: dict,
    ) -> str:
        esc_id = str(uuid.uuid4())
        reasoning = accumulated_context.get("reasoning", {})
        research = accumulated_context.get("research", {})

        accounts_sample = []
        if isinstance(research, dict):
            for acc in (research.get("accounts", []) or [])[:3]:
                if isinstance(acc, dict):
                    accounts_sample.append(
                        f"  • {acc.get('company_name', acc.get('id', '?'))}: "
                        f"churn_score={acc.get('churn_score', '?')} mrr=${acc.get('mrr', 0):,}"
                    )

        brief_lines = [
            f"ESCALATION at node: {node_id}",
            f"Reason: {output.escalation_reason}",
            f"Situation: {reasoning.get('situation_summary', 'See context')}",
            f"Confidence: {output.confidence:.0%}",
        ]
        if accounts_sample:
            brief_lines.append("Sample accounts:")
            brief_lines.extend(accounts_sample)

        rec_action = (
            (reasoning.get("recommended_actions") or [{}])[0].get("action_id")
            or reasoning.get("recommended_action")
        )

        esc_data = {
            "id": esc_id, "instance_id": run_id, "tenant_id": tenant_id,
            "node_id": node_id, "reason": output.escalation_reason,
            "context_brief": "\n".join(brief_lines),
            "recommended_action": rec_action,
            "reasoning_output": reasoning,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        # Keep a local reference for the escalation_callback (transient)
        _pending_escalations[esc_id] = esc_data

        # Collect prosecutor faults from VerificationAgent (if any)
        prosecutor_faults: list = []
        if isinstance(output.output_data, dict):
            prosecutor_faults = output.output_data.get("_prosecutor_faults", [])[:20]

        # Persist via StateManager
        await self._state.create_escalation(
            instance_id=run_id, tenant_id=tenant_id, node_id=node_id,
            reason=output.escalation_reason,
            context_brief="\n".join(brief_lines),
            recommended_action=rec_action,
            options=[{"prosecutor_faults": prosecutor_faults}] if prosecutor_faults else [],
        )

        await self._broadcast("escalation_created", {
            "run_id": run_id, "id": esc_id, "escalation_id": esc_id,
            "node_id": node_id, "reason": output.escalation_reason,
            "context_brief": "\n".join(brief_lines[:4]),
            "recommended_action": rec_action, "tenant_id": tenant_id,
        })
        return esc_id

    async def _broadcast(self, event_type: str, data: dict) -> None:
        if self._ws_broadcast:
            try:
                await self._ws_broadcast(event_type, data)
            except Exception as e:
                log.debug("WS broadcast failed", error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Module-level transient stores (legacy compat — no longer primary source of truth)
# These exist only for the escalation_callback bridge during the run.
# The canonical state lives in PostgreSQL.
# ─────────────────────────────────────────────────────────────────────────────

_pending_escalations: dict[str, dict] = {}
_pending_a2a_requests: dict[str, dict] = {}  # kept for any legacy compat references
