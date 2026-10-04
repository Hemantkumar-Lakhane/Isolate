"""
core/workflow_logger.py
=======================
Detailed per-workflow system logger for EPI audit trails and operational monitoring.

Logs per workflow run:
  - Which features were active (cache, map-reduce, HyDE, consensus gate, etc.)
  - Per-agent: model used, tier, tokens, cost, cache hits, success/failure
  - Escalations: reason, was consensus gated, was confidence too low
  - Cost leakage sources: hyde_rag, map_reduce, discovery_tool_selector
  - Reflexion attempts: how many retries, what error, did it recover
  - Context pruning: how much data was trimmed, fork context preserved
  - Config validation: any issues found before run

Surfaced in:
  1. EPI artifact metadata
  2. Admin dashboard "execution log" extended view
  3. /api/v1/workflows/{run_id}/system-log endpoint

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import structlog

log = structlog.get_logger()


@dataclass
class AgentLog:
    node_id: str
    agent_type: str
    model_used: str
    tier: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    success: bool
    cache_hit: bool           # Redis/app cache
    provider_cache_hit: bool  # Anthropic/Google prompt cache
    reflexion_attempts: int
    parse_error: bool
    json_recovered: bool
    features_used: list[str]  # e.g. ["rag_injection", "map_reduce", "tool_parallel"]
    error: Optional[str] = None
    confidence: Optional[float] = None
    escalated: bool = False
    escalation_reason: str = ""


@dataclass
class FeatureUsageLog:
    """Track which advanced features fired and their effect."""
    rag_injection: bool = False
    rag_similarities_found: int = 0
    graph_rag_injection: bool = False
    hyde_generated: bool = False
    hyde_cost_usd: float = 0.0
    map_reduce_triggered: bool = False
    map_reduce_chunks: int = 0
    map_reduce_cost_usd: float = 0.0
    consensus_gate_fired: bool = False        # Was consensus gated by high confidence?
    consensus_gate_passed: bool = False       # Did it actually skip the consensus node?
    provider_cache_used: bool = False
    provider_cache_tokens_saved: int = 0
    provider_cache_savings_usd: float = 0.0
    within_loop_compression_fired: bool = False
    reflexion_total_attempts: int = 0
    reflexion_recoveries: int = 0
    a2a_requests_created: int = 0
    a2a_loop_limit_hit: bool = False
    config_validation_errors: int = 0
    config_validation_warnings: int = 0
    budget_circuit_breaker_fired: bool = False
    discovery_rag_preselection: bool = False  # Fast path used?
    discovery_llm_fallback: bool = False      # Slow LLM path used?


class WorkflowSystemLogger:
    """
    Accumulates structured log data during a workflow run.
    Flushed to EPI artifact and DB at run completion.
    """

    def __init__(self, run_id: str, workflow_name: str, tenant_id: str):
        self._run_id = run_id
        self._workflow_name = workflow_name
        self._tenant_id = tenant_id
        self._start_time = time.time()
        self._agent_logs: list[AgentLog] = []
        self._feature_log = FeatureUsageLog()
        self._events: list[dict] = []
        self._cost_breakdown: dict[str, float] = {}  # source → cost

    # ─────────────────────────────────────────────────────────────────────
    # Agent logging
    # ─────────────────────────────────────────────────────────────────────

    def log_agent(self, agent_log: AgentLog) -> None:
        self._agent_logs.append(agent_log)
        self._cost_breakdown[agent_log.node_id] = (
            self._cost_breakdown.get(agent_log.node_id, 0.0) + agent_log.cost_usd
        )
        log.info(
            "Agent completed",
            run=self._run_id[:8],
            node=agent_log.node_id,
            model=agent_log.model_used.split("/")[-1] if agent_log.model_used else "?",
            cost=f"${agent_log.cost_usd:.5f}",
            ok=agent_log.success,
            cache=agent_log.cache_hit,
            reflexion=agent_log.reflexion_attempts,
            features=agent_log.features_used,
        )

    def log_cost_source(self, source: str, cost_usd: float) -> None:
        """Track unattributed cost sources (HyDE, map-reduce, etc.)."""
        self._cost_breakdown[source] = self._cost_breakdown.get(source, 0.0) + cost_usd

    # ─────────────────────────────────────────────────────────────────────
    # Feature flags
    # ─────────────────────────────────────────────────────────────────────

    def mark_rag_injection(self, similarities_found: int) -> None:
        self._feature_log.rag_injection = True
        self._feature_log.rag_similarities_found = similarities_found
        self._log_event("rag_injection", {"similarities": similarities_found})

    def mark_hyde(self, cost_usd: float) -> None:
        self._feature_log.hyde_generated = True
        self._feature_log.hyde_cost_usd += cost_usd
        self.log_cost_source("hyde_rag", cost_usd)
        self._log_event("hyde_generated", {"cost": f"${cost_usd:.5f}"})

    def mark_map_reduce(self, chunks: int, cost_usd: float) -> None:
        self._feature_log.map_reduce_triggered = True
        self._feature_log.map_reduce_chunks = chunks
        self._feature_log.map_reduce_cost_usd += cost_usd
        self.log_cost_source("map_reduce_summarizer", cost_usd)
        self._log_event("map_reduce_triggered", {"chunks": chunks, "cost": f"${cost_usd:.5f}"})

    def mark_consensus_gate(self, passed: bool, confidence: float) -> None:
        """fired=True means the gate checked; passed=True means consensus was SKIPPED (confidence high)."""
        self._feature_log.consensus_gate_fired = True
        self._feature_log.consensus_gate_passed = passed
        self._log_event(
            "consensus_gate",
            {"skipped_consensus": passed, "confidence": confidence,
             "reason": f"confidence={confidence:.2f} {'>=0.90 → skipped' if passed else '<0.90 → ran consensus'}"}
        )

    def mark_provider_cache_hit(self, tokens: int, savings_usd: float) -> None:
        self._feature_log.provider_cache_used = True
        self._feature_log.provider_cache_tokens_saved += tokens
        self._feature_log.provider_cache_savings_usd += savings_usd
        self._log_event("provider_cache_hit", {"tokens_saved": tokens, "savings": f"${savings_usd:.5f}"})

    def mark_reflexion(self, node_id: str, attempt: int, recovered: bool) -> None:
        self._feature_log.reflexion_total_attempts += 1
        if recovered:
            self._feature_log.reflexion_recoveries += 1
        self._log_event("reflexion", {"node": node_id, "attempt": attempt, "recovered": recovered})

    def mark_within_loop_compression(self, original_chars: int, compressed_chars: int) -> None:
        self._feature_log.within_loop_compression_fired = True
        self._log_event("within_loop_compression", {
            "original": original_chars, "compressed": compressed_chars,
            "reduction_pct": f"{(1-compressed_chars/max(original_chars,1))*100:.0f}%"
        })

    def mark_discovery_agent(self, used_rag_preselection: bool) -> None:
        self._feature_log.discovery_rag_preselection = used_rag_preselection
        self._feature_log.discovery_llm_fallback = not used_rag_preselection
        self._log_event("discovery_agent", {"path": "rag_fast" if used_rag_preselection else "llm_slow"})

    def mark_config_validation(self, errors: int, warnings: int) -> None:
        self._feature_log.config_validation_errors = errors
        self._feature_log.config_validation_warnings = warnings
        if errors:
            log.warning("Config validation issues detected before run", errors=errors, warnings=warnings)

    def mark_budget_circuit_breaker(self, current_cost: float, limit: float) -> None:
        self._feature_log.budget_circuit_breaker_fired = True
        self._log_event("budget_circuit_breaker", {
            "current_cost": f"${current_cost:.5f}",
            "limit": f"${limit:.5f}",
            "action": "forced_escalation"
        })

    # ─────────────────────────────────────────────────────────────────────
    # Summary generation
    # ─────────────────────────────────────────────────────────────────────

    def generate_summary(self) -> dict:
        """Generate the full system log summary for EPI artifact."""
        elapsed = time.time() - self._start_time

        total_cost = sum(a.cost_usd for a in self._agent_logs)
        tracked_cost = sum(self._cost_breakdown.values())

        worked = [a for a in self._agent_logs if a.success]
        failed = [a for a in self._agent_logs if not a.success]
        escalated = [a for a in self._agent_logs if a.escalated]
        reflexion_happened = [a for a in self._agent_logs if a.reflexion_attempts > 0]
        cache_hits = [a for a in self._agent_logs if a.cache_hit]

        summary = {
            "run_id": self._run_id,
            "workflow_name": self._workflow_name,
            "tenant_id": self._tenant_id[:16],
            "duration_seconds": round(elapsed, 1) if elapsed is not None else None,
            "generated_at": datetime.utcnow().isoformat(),

            # Cost breakdown
            "cost_summary": {
                "total_usd": round(tracked_cost, 6) if tracked_cost is not None else None,
                "by_source": {k: (round(v, 6) if v is not None else None) for k, v in self._cost_breakdown.items()},
                "provider_cache_savings_usd": round(pcs, 6) if (pcs := getattr(self._feature_log, "provider_cache_savings_usd", None)) is not None else None,
                "previously_untracked_sources": {
                    "hyde_rag": round(hc, 6) if (hc := getattr(self._feature_log, "hyde_cost_usd", None)) is not None else None,
                    "map_reduce": round(mc, 6) if (mc := getattr(self._feature_log, "map_reduce_cost_usd", None)) is not None else None,
                },
            },

            # Agent results
            "agents": {
                "total": len(self._agent_logs),
                "succeeded": len(worked),
                "failed": len(failed),
                "escalated": len(escalated),
                "cache_hits": len(cache_hits),
                "reflexion_fired": len(reflexion_happened),
                "details": [
                    {
                        "node": a.node_id,
                        "agent": a.agent_type,
                        "model": a.model_used.split("/")[-1] if a.model_used else "?",
                        "tier": a.tier,
                        "ok": a.success,
                        "cost": f"${a.cost_usd:.5f}",
                        "confidence": a.confidence,
                        "cache_hit": a.cache_hit,
                        "reflexion_attempts": a.reflexion_attempts,
                        "features": a.features_used,
                        "error": a.error,
                    }
                    for a in self._agent_logs
                ],
            },

            # Feature audit
            "features_used": {
                "rag_injection": self._feature_log.rag_injection,
                "rag_similarities": self._feature_log.rag_similarities_found,
                "graph_rag": self._feature_log.graph_rag_injection,
                "hyde": self._feature_log.hyde_generated,
                "map_reduce": self._feature_log.map_reduce_triggered,
                "map_reduce_chunks": self._feature_log.map_reduce_chunks,
                "consensus_gate": self._feature_log.consensus_gate_fired,
                "consensus_skipped": self._feature_log.consensus_gate_passed,
                "provider_cache": self._feature_log.provider_cache_used,
                "within_loop_compression": self._feature_log.within_loop_compression_fired,
                "discovery_fast_path": self._feature_log.discovery_rag_preselection,
                "discovery_llm_path": self._feature_log.discovery_llm_fallback,
                "budget_circuit_breaker": self._feature_log.budget_circuit_breaker_fired,
                "config_validation_issues": self._feature_log.config_validation_errors,
            },

            # What worked / what didn't
            "what_worked": self._generate_what_worked(worked),
            "what_failed": self._generate_what_failed(failed),

            # Event timeline
            "event_timeline": self._events[-30:],  # last 30 events
        }

        return summary

    def _generate_what_worked(self, worked: list[AgentLog]) -> list[str]:
        lines = []
        for a in worked:
            feats = ", ".join(a.features_used) if a.features_used else "standard"
            lines.append(
                f"✓ {a.node_id} ({a.agent_type}) → {a.model_used.split('/')[-1] if a.model_used else '?'} "
                f"[{feats}] | ${a.cost_usd:.5f}"
            )
        if self._feature_log.provider_cache_savings_usd > 0:
            lines.append(f"✓ Provider prompt cache saved ${self._feature_log.provider_cache_savings_usd:.5f}")
        if self._feature_log.consensus_gate_passed:
            lines.append("✓ Consensus gate: high confidence → skipped double-Sonnet call (saved ~$0.32)")
        if self._feature_log.map_reduce_triggered:
            lines.append(f"✓ Map-Reduce: compressed research into {self._feature_log.map_reduce_chunks} chunks")
        return lines

    def _generate_what_failed(self, failed: list[AgentLog]) -> list[str]:
        lines = []
        for a in failed:
            lines.append(
                f"✗ {a.node_id} ({a.agent_type}) → {a.error or 'unknown error'} "
                f"[reflexion_attempts={a.reflexion_attempts}]"
            )
        if self._feature_log.budget_circuit_breaker_fired:
            lines.append("✗ Budget circuit breaker fired → run forced to escalate")
        if self._feature_log.config_validation_errors > 0:
            lines.append(f"✗ Config had {self._feature_log.config_validation_errors} validation errors before run")
        return lines

    def _log_event(self, event_type: str, data: dict) -> None:
        self._events.append({
            "ts": datetime.utcnow().isoformat(),
            "type": event_type,
            **data,
        })