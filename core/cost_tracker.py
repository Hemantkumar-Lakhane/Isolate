"""
core/cost_tracker.py
====================
FinOps module: Run-scoped cost accumulator that captures ALL LLM spend,
including previously-untracked calls:
  - HyDE hypothesis generation in RAG
  - Map-Reduce summarization bridges
  - Discovery Agent tool selection (Step 1)
  - Verification prosecutor turn

Phase 1: Total attribution — every LLM call credits back to its run_id.
Phase 2: Budget circuit breakers — hard/soft limits per run.
Phase 3: Multi-dimensional pricing — cache_write / cache_read / output.

Usage:
    tracker = RunCostTracker(run_id, state_manager, budget_settings)
    await tracker.record(call, source="hyde_rag")
    await tracker.check_budget()  # raises BudgetExceededError if over hard limit

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()


class BudgetExceededError(Exception):
    """Raised when a run exceeds its configured max_spend_per_run."""
    def __init__(self, run_id: str, current: float, limit: float):
        self.run_id = run_id
        self.current = current
        self.limit = limit
        super().__init__(
            f"Run {run_id[:8]} exceeded budget: ${current:.5f} > ${limit:.5f}"
        )


@dataclass
class CallRecord:
    """One LLM call's cost attribution record."""
    source: str              # e.g. "research_agent", "hyde_rag", "map_reduce_summarizer"
    model: str
    tokens_in: int
    tokens_out: int
    cache_read_tokens: int   # tokens served from provider cache (cheaper rate)
    cache_write_tokens: int  # tokens written to provider cache (slight premium)
    cost_usd: float
    duration_ms: int
    cache_hit: bool          # Redis/app-level cache hit (cost=0)
    tier: str
    ts: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RunCostTracker:
    """
    Scoped to one workflow run. Accumulates ALL LLM costs regardless of
    which component made the call — agents, RAG, summarization, etc.

    Persists incremental costs to DB so partial-run costs survive crashes.
    """

    def __init__(
        self,
        run_id: str,
        state_manager=None,
        budget_settings: Optional[dict] = None,
        ws_broadcast=None,
    ):
        self._run_id = run_id
        self._state = state_manager
        self._budget = budget_settings or {}
        self._calls: list[CallRecord] = []
        self._total_cost = 0.0
        self._total_tokens_in = 0
        self._total_tokens_out = 0
        self._cache_savings = 0.0   # cost avoided via cache reads
        self._lock = asyncio.Lock()

        # Budget limits
        self._hard_limit: Optional[float] = self._budget.get("max_spend_per_run")
        self._soft_limit: Optional[float] = (
            self._hard_limit * 0.80 if self._hard_limit else None
        )
        self._soft_warned = False
        self._ws_broadcast = ws_broadcast

    # ─────────────────────────────────────────────────────────────────────
    # Recording
    # ─────────────────────────────────────────────────────────────────────

    async def record(
        self,
        llm_call,                     # LLMCall dataclass from llm_router
        source: str,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> None:
        """
        Record one LLM call against this run.
        Thread-safe — can be called from parallel agent coroutines.

        source: identifies the component (e.g. "research_agent", "hyde_rag",
                "map_reduce_summarizer", "discovery_tool_selector")
        """
        if llm_call.cache_hit:
            # App-level cache hit — zero cost, but record for visibility
            rec = CallRecord(
                source=source,
                model=llm_call.model,
                tokens_in=0,
                tokens_out=0,
                cache_read_tokens=0,
                cache_write_tokens=0,
                cost_usd=0.0,
                duration_ms=llm_call.duration_ms,
                cache_hit=True,
                tier=llm_call.tier,
            )
            async with self._lock:
                self._calls.append(rec)
            return

        rec = CallRecord(
            source=source,
            model=llm_call.model,
            tokens_in=llm_call.tokens_in,
            tokens_out=llm_call.tokens_out,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            cost_usd=llm_call.cost_usd,
            duration_ms=llm_call.duration_ms,
            cache_hit=False,
            tier=llm_call.tier,
        )

        async with self._lock:
            self._calls.append(rec)
            self._total_cost += llm_call.cost_usd
            self._total_tokens_in += llm_call.tokens_in
            self._total_tokens_out += llm_call.tokens_out

        # Persist incremental cost to DB immediately
        if self._state and self._state._db is not None:
            try:
                await self._state.update_cost(
                    self._run_id,
                    tokens_in=llm_call.tokens_in,
                    tokens_out=llm_call.tokens_out,
                    cost_usd=llm_call.cost_usd,
                )
            except Exception as e:
                log.debug("Cost persistence failed (non-fatal)", error=str(e))

        log.debug(
            "Cost recorded",
            run=self._run_id[:8],
            source=source,
            model=llm_call.model.split("/")[-1],
            cost=f"${llm_call.cost_usd:.5f}",
            total=f"${self._total_cost:.5f}",
        )

    async def record_cache_savings(self, tokens: int, model: str, rates: dict) -> None:
        """Record tokens that hit provider-level cache (cache_read rate vs input rate)."""
        input_rate = rates.get("input", 0.0)
        cache_read_rate = rates.get("cache_read", input_rate)
        savings = (input_rate - cache_read_rate) * tokens / 1_000_000
        async with self._lock:
            self._cache_savings += savings

    # ─────────────────────────────────────────────────────────────────────
    # Budget Circuit Breakers
    # ─────────────────────────────────────────────────────────────────────

    async def check_budget(self) -> None:
        """
        Call BEFORE spawning the next expensive agent.
        Raises BudgetExceededError if over hard limit → orchestrator forces escalation.
        Logs warning if over soft limit (80% of hard limit).
        """
        if not self._hard_limit:
            return

        current = self._total_cost

        if current >= self._hard_limit:
            log.warning(
                "BUDGET CIRCUIT BREAKER: hard limit exceeded",
                run=self._run_id[:8],
                current=f"${current:.5f}",
                limit=f"${self._hard_limit:.5f}",
            )
            raise BudgetExceededError(self._run_id, current, self._hard_limit)

        if self._soft_limit and current >= self._soft_limit and not self._soft_warned:
            self._soft_warned = True
            log.warning(
                "Budget soft limit reached (80% of max)",
                run=self._run_id[:8],
                current=f"${current:.5f}",
                soft_limit=f"${self._soft_limit:.5f}",
                hard_limit=f"${self._hard_limit:.5f}",
            )
            # Broadcast WS warning so the dashboard can alert the operator
            if hasattr(self, "_ws_broadcast") and self._ws_broadcast:
                try:
                    asyncio.create_task(self._ws_broadcast("budget_warning", {
                        "run_id":       self._run_id,
                        "current_cost": round(current, 5),
                        "soft_limit":   round(self._soft_limit, 5),
                        "hard_limit":   round(self._hard_limit, 5),
                        "pct_used":     round(current / self._hard_limit * 100, 1),
                    }))
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────────────
    # Reporting
    # ─────────────────────────────────────────────────────────────────────

    def get_breakdown(self) -> dict:
        """Return cost breakdown by source component."""
        by_source: dict[str, dict] = {}
        for rec in self._calls:
            if rec.source not in by_source:
                by_source[rec.source] = {
                    "calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_usd": 0.0,
                    "cache_hits": 0,
                }
            s = by_source[rec.source]
            s["calls"] += 1
            s["tokens_in"] += rec.tokens_in
            s["tokens_out"] += rec.tokens_out
            s["cost_usd"] += rec.cost_usd
            if rec.cache_hit:
                s["cache_hits"] += 1

        return {
            "run_id": self._run_id,
            "total_cost_usd": round(self._total_cost, 6),
            "total_tokens_in": self._total_tokens_in,
            "total_tokens_out": self._total_tokens_out,
            "cache_savings_usd": round(self._cache_savings, 6),
            "total_calls": len(self._calls),
            "by_source": by_source,
            "budget_limit": self._hard_limit,
            "budget_remaining": (
                round(self._hard_limit - self._total_cost, 6)
                if self._hard_limit else None
            ),
        }

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def call_count(self) -> int:
        return len(self._calls)