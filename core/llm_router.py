"""
core/llm_router.py
==================
Multi-LLM router with Budget Governor for cost optimization.

Budget Levels:
  0 - Max Accuracy: Default models, no optimization
  1 - Balanced: Downgrade Research + Verification to mini; enable caching
  2 - Aggressive: Downgrade Reasoning/Drafting by one tier; truncate reasoning chain
  3 - Budget First: Force all to mini; summarize accumulated_context before passing

Also implements:
  - Redis semantic caching (hash of system+user prompt → cached response)
  - Context pruning (only pass depends_on data, not full accumulated context)
  - Summarization Bridge (L>1: summarize large research output before sending to Reasoning)
  - Just-in-Time Accuracy: auto-retry with heavy model if cheap model confidence < threshold

CONSTANT — do not modify for business customization.
Modify config/templates/llm_config.json and budget_settings per tenant.
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False
import litellm
import structlog
from litellm import acompletion

log = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Budget Governor — Tier Downgrade Maps
# ─────────────────────────────────────────────────────────────────────────────

# Maps optimization_level → {agent → forced_tier}
# None means "use the default from llm_config.json"
BUDGET_TIER_MAPS: dict[int, dict] = {
    0: {},  # Default — loaded from config at runtime in _load_config
    1: {"research_agent": "mini", "verification_agent": "mini", "memory_agent": "balanced"},
    2: {"research_agent": "mini", "reasoning_agent": "budget_heavy", "drafting_agent": "budget_heavy",
        "verification_agent": "mini", "execution_agent": "mini", "memory_agent": "balanced"},
    3: {"research_agent": "mini", "reasoning_agent": "mini", "drafting_agent": "balanced",
        "verification_agent": "mini", "execution_agent": "mini", "memory_agent": "mini", "orchestrator": "mini"},
}

# Max reasoning chain chars to pass when level >= 2 (truncation)
REASONING_CHAIN_TRUNCATE = {2: 500, 3: 300}
LOGIC_HEAVY_AGENTS = {"reasoning_agent", "consensus_agent"}
# Agents that should NEVER be downgraded below balanced even in Budget mode
# (Safety net — verification catches errors)
NEVER_DOWNGRADE_BELOW = {
    "verification_agent": "mini",  # Already mini but never below
}


def _extract_provider(err_str: str) -> str:
    """Extract provider name from error string without exposing keys."""
    for prov in ("anthropic", "openai", "openrouter", "groq", "gemini", "google"):
        if prov in err_str:
            return prov
    return "unknown"


@dataclass
class LLMCall:
    call_id: str
    agent_name: str
    model: str
    tier: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    success: bool
    cache_hit: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    # True when this "call" is NOT a real model response but a deterministic
    # mock/fallback produced because every provider in the chain failed (e.g.
    # auth/401) or the router is in mock mode. Downstream must NOT treat a
    # fallback as a genuine AI result — the UI labels it as degraded.
    is_fallback: bool = False
    provider: Optional[str] = None
    cached_tokens: Optional[int] = None
    fallback_used: bool = False
    fallback_from: Optional[str] = None
    fallback_reason: Optional[str] = None
    tool_calls: Optional[int] = None


class LLMProviderUnavailableError(RuntimeError):
    """Raised when no real provider returned an LLM response."""

    def __init__(self, agent_name: str, attempts: list[dict]):
        self.agent_name = agent_name
        self.attempts = attempts
        super().__init__("AI_PROVIDER_UNAVAILABLE")


@dataclass
class LLMMessage:
    role: str
    content: str


class LLMRouter:
    """
    Routes LLM calls to the correct model with:
    - Budget Governor (optimization_level 0-3)
    - Redis semantic caching
    - Automatic model selection + fallback chain
    - Real-time token + cost tracking
    - Summarization Bridge for large contexts
    """

    def __init__(
        self,
        config_path: str = "config/templates/llm_config.json",
        redis_client=None,
    ):
        self._config = self._load_config(config_path)
        self._cost_rates = self._config["cost_rates"]
        self._task_models = self._config["task_models"]
        self._agent_defaults = self._config["agent_defaults"]
        self._fallback_chain = self._config["fallback_chain"]

        # Load budget tier maps from config if present (allows config-driven overrides)
        config_maps = self._config.get("budget_tier_maps", {})
        if config_maps:
            for level_str, level_map in config_maps.items():
                try:
                    level = int(level_str)
                    BUDGET_TIER_MAPS[level] = level_map
                except (ValueError, TypeError):
                    pass
        
        # Load consensus config
        self._consensus_config = self._config.get("consensus_model_config", {})
        self._consensus_pre_gate_threshold = float(
            self._consensus_config.get("pre_gate_confidence_threshold", 0.90)
        )
        # Live tracking
        self._calls: list[LLMCall] = []
        self._agent_totals: dict[str, dict] = {}
        self._cache_hits = 0

        # Redis for semantic caching
        self._redis = redis_client

        # Budget Governor — set per run by orchestrator
        self._optimization_level: int = 1
        self._budget_config: dict = {}
        self._cache_ttl: int = 3600
        self._enable_map_reduce: bool = False   # set per-run by set_budget_config
        litellm.set_verbose = False
        litellm.drop_params = True
        self._token_encoder = None
        if _TIKTOKEN_AVAILABLE:
            try:
                self._token_encoder = tiktoken.get_encoding("cl100k_base")
            except Exception:
                pass

        log.info("LLMRouter initialized", models=list(self._task_models.keys()))

    # ─────────────────────────────────────────────────────────────────────────
    # Budget Governor Control
    # ─────────────────────────────────────────────────────────────────────────

    def set_budget_config(self, budget_settings: dict, tenant_id: str = "") -> None:
        """Called by orchestrator with tenant's budget_settings before each run."""
        self._optimization_level = int(budget_settings.get("optimization_level", 1))
        self._cache_ttl = int(budget_settings.get("cache_ttl_seconds", 3600))
        self._current_tenant_id = tenant_id          # Fix D: scope cache to tenant
        enable_caching = budget_settings.get("enable_caching", True)
        if not enable_caching:
            self._redis = None  # Disable caching for this run
        self._enable_map_reduce = bool(
            budget_settings.get("enable_map_reduce_summarization", False)
        )
        self._budget_config = budget_settings
        log.info(
            "Budget governor set",
            level=self._optimization_level,
            strategy=budget_settings.get("strategy", "balanced"),
            map_reduce=self._enable_map_reduce,
        )
    
    def set_workflow_logger(self, logger) -> None:
        """Attach a WorkflowSystemLogger for per-run feature tracking."""
        self._workflow_logger = logger
    # ─────────────────────────────────────────────────────────────────────────
    # Main Call API
    # ─────────────────────────────────────────────────────────────────────────

    async def call(
        self,
        agent_name: str,
        messages: list[LLMMessage],
        tools: Optional[list[dict]] = None,
        tier_override: Optional[str] = None,
        model_override: Optional[str] = None,
        client_overrides: Optional[dict] = None,
        streaming_callback: Optional[callable] = None,
        max_tokens_override: Optional[int] = None,
    ) -> tuple[str, LLMCall]:
        """
        Make an LLM call with budget governance, caching, and fallback.
        Returns (response_text, LLMCall record).
        """
        # Resolve model with budget governance applied
        model, tier = self._resolve_model_with_budget(
            agent_name, tier_override, model_override, client_overrides
        )

        # Build messages list
        lm_messages = [{"role": m.role, "content": m.content} for m in messages]
        model_config = self._task_models.get(tier, self._task_models["balanced"])

        if not any(
            message.get("role") == "user" and str(message.get("content", "")).strip()
            for message in lm_messages
        ):
            raise ValueError("INPUT_CONTEXT_MISSING: at least one non-empty user message is required")

        # Fast mock mode check for testing/offline execution
        if os.getenv("MOCK_LLM", "false").lower() in ("true", "1"):
            raise LLMProviderUnavailableError(
                agent_name,
                [{"attempt": 1, "model": model,
                  "provider": self._provider_for_model(model),
                  "error_type": "mock_mode_disabled"}],
            )

        # ── Cache check (Level >= 1) ──────────────────────────────────────
        if self._optimization_level >= 1 and self._redis and not tools:
            cache_key = self._build_cache_key(agent_name, lm_messages)
            cached = await self._get_cached_response(cache_key)
            if cached:
                self._cache_hits += 1
                log.debug("Cache HIT", agent=agent_name, key=cache_key[:16])
                fake_call = LLMCall(
                    call_id="cached",
                    agent_name=agent_name,
                    model=model,
                    tier=tier,
                    tokens_in=0,
                    tokens_out=0,
                    cost_usd=0.0,
                    duration_ms=1,
                    success=True,
                    cache_hit=True,
                )
                return cached, fake_call
            
        # ── Pre-flight token count (prevent 400 errors from oversized prompts) ──
        if _TIKTOKEN_AVAILABLE:
            try:
                enc = tiktoken.get_encoding("cl100k_base")
                prompt_tokens = sum(
                    len(enc.encode(m.get("content", "") if isinstance(m, dict) else ""))
                    for m in lm_messages
                )
                model_limit = model_config.get("context_window", 200_000)
                max_tokens = model_config.get("max_tokens", 2048)
                # Reserve space for output
                available = model_limit - max_tokens - 100
                if prompt_tokens > available:
                    log.warning(
                        "Pre-flight: prompt exceeds context window, applying emergency pruning",
                        agent=agent_name,
                        prompt_tokens=prompt_tokens,
                        available=available,
                        model=model,
                    )
                    # Emergency prune: truncate the largest message (usually system or user with data)
                    for i, msg in enumerate(lm_messages):
                        content = msg.get("content", "") if isinstance(msg, dict) else ""
                        if len(enc.encode(content)) > 2000:
                            # Truncate to fit
                            ratio = available / max(prompt_tokens, 1)
                            target_chars = int(len(content) * ratio * 0.9)
                            lm_messages[i] = {**msg, "content": content[:target_chars] + "\\n[TRUNCATED FOR CONTEXT LIMIT]"}
                            log.info("Emergency pruning applied", msg_index=i, original_len=len(content), new_len=target_chars)
                            break
            except Exception as e:
                log.debug("Tiktoken pre-flight failed (non-fatal)", error=str(e))

        # ── Try models in fallback chain ──────────────────────────────────
        fallback_models = self._get_fallback_chain(model, tier)
        attempts: list[dict] = []
        for attempt, attempt_model in enumerate(fallback_models):
            start_ms = int(time.time() * 1000)
            call_id = str(uuid.uuid4())[:8]

            try:
                kwargs: dict[str, Any] = {
                    "model": attempt_model,
                    "messages": lm_messages,
                    "max_tokens": max_tokens_override or model_config.get("max_tokens", 2048),
                    "temperature": model_config.get("temperature", 0.2),
                    "timeout": model_config.get("timeout_seconds", 60),
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                # ── Streaming path — only when callback provided and no tools ─
                use_streaming = (streaming_callback is not None) and (not tools)
    
                if use_streaming:
                    kwargs["stream"] = True
                    try:
                        stream_gen = await acompletion(**kwargs)
                        full_text = ""
                        token_buffer = ""
                        # Estimate input tokens from message lengths
                        tokens_in= self._count_tokens_exact(lm_messages)
                        tokens_out = 0
    
                        async for chunk in stream_gen:
                            delta = ""
                            if chunk.choices:
                                delta_obj = getattr(chunk.choices[0], "delta", None)
                                if delta_obj:
                                    delta = getattr(delta_obj, "content", None) or ""
                            if delta:
                                full_text += delta
                                token_buffer += delta
                                tokens_out += 1
                                # Flush every 5 chars or on word/sentence boundary
                                if len(token_buffer) >= 5 or (
                                    token_buffer and token_buffer[-1] in " \\n\\t.,!?;:"
                                ):
                                    try:
                                        await streaming_callback(token_buffer)
                                    except Exception:
                                        pass
                                    token_buffer = ""
                            # Capture usage when provider sends it in stream
                            if hasattr(chunk, "usage") and chunk.usage:
                                if getattr(chunk.usage, "prompt_tokens", 0):
                                    tokens_in = chunk.usage.prompt_tokens
                                if getattr(chunk.usage, "completion_tokens", 0):
                                    tokens_out = chunk.usage.completion_tokens
    
                        # Flush remaining buffer
                        if token_buffer:
                            try:
                                await streaming_callback(token_buffer)
                            except Exception:
                                pass
    
                        cost = self._calculate_cost(attempt_model, tokens_in, tokens_out)
                        duration_ms = int(time.time() * 1000) - start_ms
                        call = LLMCall(
                            call_id=call_id,
                            agent_name=agent_name,
                            model=attempt_model,
                            tier=tier,
                            tokens_in=tokens_in,
                            tokens_out=tokens_out,
                            cost_usd=cost,
                            duration_ms=duration_ms,
                            success=True,
                            provider=self._provider_for_model(attempt_model),
                        )
                        self._record_call(call)
                        text = full_text
    
                        # Cache the streamed result if caching is enabled
                        if self._optimization_level >= 1 and self._redis:
                            _ck = self._build_cache_key(agent_name, lm_messages)
                            await self._set_cached_response(_ck, text)
    
                        # JIT accuracy retry applies to streamed responses too
                        if (
                            self._optimization_level >= 2
                            and self._budget_config.get("auto_retry_on_low_confidence", True)
                        ):
                            confidence = self._extract_confidence(text)
                            threshold = self._budget_config.get("confidence_retry_threshold", 0.6)
                            if (
                                confidence is not None
                                and confidence < threshold
                                and tier != "heavy"
                            ):
                                log.info(
                                    "JIT Accuracy: retrying with heavy model (streamed)",
                                    agent=agent_name,
                                    confidence=confidence,
                                )
                                return await self.call(
                                    agent_name=agent_name,
                                    messages=messages,
                                    tools=tools,
                                    tier_override="heavy",
                                    streaming_callback=streaming_callback,
                                )
    
                        return text, call
    
                    except Exception as stream_err:
                        log.warning(
                            "Streaming call failed — falling back to non-streaming",
                            agent=agent_name,
                            model=attempt_model,
                            error=str(stream_err)[:120],
                        )
                        # Remove stream kwarg and fall through
                        kwargs.pop("stream", None)
                        
                if self._optimization_level >= 0:
                    lm_messages = self._inject_anthropic_cache_control(lm_messages, attempt_model)
    
                # ── Non-streaming path (existing, unchanged) ──────────────────
                response = await acompletion(**kwargs)

                usage = response.usage
                tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
                tokens_out = getattr(usage, "completion_tokens", None) if usage else None

                # Unified cost calculation logic (Fixes BUG-001)
                if usage:
                    cache_read_tokens  = getattr(usage, 'cache_read_input_tokens',  0) or 0
                    cache_write_tokens = getattr(usage, 'cache_creation_input_tokens', 0) or 0
                    cost = self._calculate_cost(
                        attempt_model, tokens_in, tokens_out,
                        cache_read_tokens=cache_read_tokens,
                        cache_write_tokens=cache_write_tokens,
                    )
                    # Track savings AFTER cost is correct
                    if cache_read_tokens > 0 and hasattr(self, '_workflow_logger') and self._workflow_logger:
                        rates = self._cost_rates.get(attempt_model, {})
                        savings = (rates.get('input', 0) - rates.get('cache_read', 0)) * cache_read_tokens / 1e6
                        self._workflow_logger.mark_provider_cache_hit(cache_read_tokens, savings)
                else:
                    cost = None

                duration_ms = int(time.time() * 1000) - start_ms
    
                call = LLMCall(
                    call_id=call_id,
                    agent_name=agent_name,
                    model=attempt_model,
                    tier=tier,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost,
                    duration_ms=duration_ms,
                    success=True,
                    provider=self._provider_for_model(attempt_model),
                )
                self._record_call(call)
    
                text = response.choices[0].message.content or ""

                # ── Handle structured tool calls (LiteLLM native format) ──────────
                # When a model uses native tool calling, results are in message.tool_calls
                # NOT in message.content. This is the critical fix.
                raw_tool_calls = getattr(response.choices[0].message, 'tool_calls', None)
                if raw_tool_calls:
                    tc_list = []
                    for tc in raw_tool_calls:
                        try:
                            fn = tc.function
                            raw_args = fn.arguments if fn.arguments else "{}"
                            if isinstance(raw_args, str):
                                try:
                                    args = json.loads(raw_args)
                                except Exception:
                                    args = {"raw": raw_args}
                            else:
                                args = raw_args if isinstance(raw_args, dict) else {}
                            tc_list.append({
                                "id": getattr(tc, "id", "") or "",
                                "name": fn.name,
                                "args": args,
                            })
                        except Exception as e:
                            log.warning("Structured tool call parse error", error=str(e))
                    if tc_list:
                        # Encode as JSON envelope — base_agent._extract_tool_calls reads this format
                        text = json.dumps({"tool_calls": tc_list, "content": text or ""})
                        log.debug("Structured tool calls extracted", count=len(tc_list),
                                agent=agent_name, tools=[t["name"] for t in tc_list])
                # ── END structured tool call handling ─────────────────────────────

                # Cache the response if caching enabled
                if self._optimization_level >= 1 and self._redis and not tools:
                    await self._set_cached_response(cache_key, text)

                # ── Just-in-Time Accuracy: auto-retry with heavy if low confidence ──
                if (self._optimization_level >= 2
                        and self._budget_config.get("auto_retry_on_low_confidence", True)):
                    confidence = self._extract_confidence(text)
                    threshold = self._budget_config.get("confidence_retry_threshold", 0.6)
                    if confidence is not None and confidence < threshold and tier != "heavy":
                        log.info(
                            "JIT Accuracy: retrying with heavy model",
                            agent=agent_name,
                            confidence=confidence,
                            threshold=threshold,
                        )
                        return await self.call(
                            agent_name=agent_name,
                            messages=messages,
                            tools=tools,
                            tier_override="heavy",
                            model_override=None,
                            client_overrides=None,
                        )

                return text, call

            except Exception as e:
                duration_ms = int(time.time() * 1000) - start_ms
                log.warning("LLM call failed", agent=agent_name, model=attempt_model,
                            error=str(e), attempt=attempt + 1)
                call = LLMCall(
                    call_id=call_id, agent_name=agent_name, model=attempt_model,
                    tier=tier, tokens_in=None, tokens_out=None, cost_usd=None,
                    duration_ms=duration_ms, success=False, error=str(e),
                    provider=self._provider_for_model(attempt_model),
                )
                self._record_call(call)
                classified = self.classify_llm_error(e)
                attempts.append({
                    "attempt": attempt + 1,
                    "model": attempt_model,
                    "provider": self._provider_for_model(attempt_model),
                    "error_type": classified.get("error_type"),
                    "safe_detail": classified.get("safe_detail"),
                })
                if attempt == len(fallback_models) - 1:
                    log.warning(
                        "All real LLM providers failed",
                        agent=agent_name,
                        attempts=[
                            {"provider": a["provider"], "model": a["model"], "error_type": a["error_type"]}
                            for a in attempts
                        ],
                    )
                    raise LLMProviderUnavailableError(agent_name, attempts) from e
                continue

        raise RuntimeError(f"Exhausted fallback models for {agent_name}")

    def _generate_mock_fallback_response(
        self,
        agent_name: str,
        lm_messages: list[dict],
        tools: Optional[list[dict]],
        attempt_model: str,
        tier: str,
        start_ms: int,
        call_id: str,
    ) -> tuple[str, LLMCall]:
        raise LLMProviderUnavailableError(
            agent_name,
            [{"attempt": 1, "model": attempt_model,
              "provider": self._provider_for_model(attempt_model),
              "error_type": "deterministic_fallback_disabled"}],
        )

        # Check if conversation already contains tool results
        has_tool_result = any(
            isinstance(m, dict) and (m.get("role") == "tool" or "Tool:" in str(m.get("content", "")))
            for m in lm_messages
        )

        if tools and not has_tool_result:
            tool_name = tools[0]["function"]["name"] if tools and "function" in tools[0] else "email_get_synthetic_messages"
            content = json.dumps({
                "tool_calls": [
                    {
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "name": tool_name,
                        "args": {"limit": 40},
                    }
                ],
                "content": "Fetching data via tool...",
            })
        elif agent_name == "summarizer_agent" or "summariz" in agent_name.lower():
            content = json.dumps({
                "total_emails_processed": 40,
                "summary_by_category": {
                    "healthcare": "Medical tourism bookings, post-op inquiries, consent forms.",
                    "real_estate": "Lease renewals, maintenance requests, showing schedules.",
                    "saas": "API rate limits, subscription upgrades, bug reports.",
                    "retail": "Inventory orders, shipment tracking, refund requests.",
                    "finance": "Invoice processing, expense approvals, tax documentation."
                },
                "key_urgent_issues": [
                    "Post-op patient fever report (High Priority)",
                    "Server 500 error on API endpoint (Urgent)",
                    "Water leak reported in Apartment 4B (Maintenance)"
                ],
                "sentiment_distribution": {
                    "positive": 15,
                    "neutral": 18,
                    "urgent_negative": 7
                },
                "action_items": [
                    "Forward post-op fever report to duty nurse immediately",
                    "Escalate API 500 error to devops on-call",
                    "Dispatch plumber to Apartment 4B"
                ]
            })
        elif agent_name == "drafting_agent" or "draft" in agent_name.lower():
            content = json.dumps({
                "proposed_actions": [
                    {
                        "action_type": "send_email_draft",
                        "requires_approval": True,
                        "urgency_score": 9,
                        "recipient": "cto@enterprise-client.com",
                        "to_address": "cto@enterprise-client.com",
                        "subject": "CRITICAL SLA Notice — Payment API Latency Incident",
                        "reason": "AI identified high-urgency SLA notice requiring executive response.",
                        "draft_reply": "Dear Partner,\n\nWe have detected an unexpected latency spike on the payment gateway API. Our engineering team has already deployed mitigation measures, and normal operations are being restored.\n\nBest regards,\nSMBFlow Enterprise Support",
                        "context_brief": "Enterprise client SLA breach warning on payment API response times."
                    }
                ],
                "approval_items": [
                    {
                        "review_type": "approval",
                        "node_id": "evaluate_actions",
                        "reason": "AI identified high-urgency SLA notice requiring executive response.",
                        "context_brief": "Enterprise client SLA breach warning on payment API response times.",
                        "payload": {
                            "action_type": "send_email_draft",
                            "to_address": "cto@enterprise-client.com",
                            "subject": "CRITICAL SLA Notice — Payment API Latency Incident",
                            "urgency_score": 9,
                            "draft_reply": "Dear Partner,\n\nWe have detected an unexpected latency spike on the payment gateway API. Our engineering team has already deployed mitigation measures, and normal operations are being restored.\n\nBest regards,\nSMBFlow Enterprise Support"
                        }
                    }
                ],
                "summary": "Generated 1 urgent response draft for executive approval.",
            })
        elif agent_name == "memory_agent" or "memory" in agent_name.lower():
            content = json.dumps({
                "patterns_to_store": [
                    {
                        "key": "email_summary_execution",
                        "description": "Batch processing of synthetic inbox and SLA detection",
                        "outcome_indicator": "positive",
                        "value": {"emails_processed": 40, "actionable_found": True},
                    }
                ],
                "outcomes_to_log": ["40 synthetic emails summarized", "SLA approval draft generated"],
                "delta_analysis": {
                    "summary": "Email summarization executed with automated event detection and HITL safeguards.",
                    "vs_history": "better",
                    "new_signals": ["Automated SLA draft approval workflow"],
                    "trend": "improving",
                },
                "summary": "Email summary workflow executed successfully with 40 synthetic emails processed.",
            })
        else:
            content = json.dumps({
                "status": "success",
                "emails_retrieved": 40,
                "data_origin": "synthetic",
                "is_test_data": True,
                "summary": "Synthetic email messages retrieved successfully for execution verification."
            })

        duration_ms = int(time.time() * 1000) - start_ms
        call = LLMCall(
            call_id=call_id,
            agent_name=agent_name,
            model=attempt_model,
            tier=tier,
            tokens_in=self._count_tokens_exact(lm_messages),
            tokens_out=len(content) // 4,
            cost_usd=0.0,
            duration_ms=duration_ms,
            success=True,
        )
        self._record_call(call)
        return content, call

    # ─────────────────────────────────────────────────────────────────────────
    # Summarization Bridge (Level >= 2)
    # ─────────────────────────────────────────────────────────────────────────
    
    async def _compress_tool_results(self, tool_results_text: str) -> str:
        """
        Compress accumulated tool results mid-loop to prevent context inflation.
        
        Called when tool results in a single _call_with_tools loop exceed 6000 chars.
        Uses a mini model to extract the essential data (IDs, key metrics, anomalies)
        and discard verbose API response boilerplate.
        """
        from core.llm_router import LLMMessage
        
        system = (
            "You are a data compressor. The following are tool call results from a data-gathering agent. "
            "Extract ONLY the essential data:\n"
            "- Account/record IDs\n"
            "- Contact fields: contact_email, contact_name, recipient_email, csm_name, manager_email, manager, email, phone\n"
            "- Key numeric metrics (scores, amounts, dates, mrr, deal_value)\n"
            "- Risk/status labels and health indicators\n"
            "- Any explicitly flagged anomalies\n"
            "NEVER discard contact_email, contact_name, or csm_name — these are required for downstream agents.\n"
            "Discard: verbose descriptions, null fields, metadata, redundant wrappers.\n"
            "Return as compact JSON preserving all essential numeric, ID, and contact data."
        )
        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=f"Tool results to compress:\n{tool_results_text[:12000]}"),
        ]
        text, call = await self.call(
            agent_name="tool_result_compressor",
            messages=messages,
            tier_override="mini",
        )
        return f"[COMPRESSED TOOL RESULTS]\n{text}"

    @staticmethod
    def classify_llm_error(error: Exception) -> dict:
        """
        Classify an LLM/SDK exception into a developer-friendly error type.
        Returns {error_type, error_message, provider, safe_detail}.
        Never exposes API keys, tokens, or credentials.
        """
        err_str = str(error).lower()
        err_type = type(error).__name__

        # ── Rate limit / quota ──────────────────────────────────────────────
        if any(kw in err_str for kw in ("rate limit", "ratelimit", "429", "quota", "too many requests", "tpm", "rpm")):
            return {
                "error_type": "rate_limit",
                "error_message": "Rate limit / quota exceeded",
                "provider": _extract_provider(err_str),
                "safe_detail": str(error)[:300],
            }
        # ── Model not found / unavailable ───────────────────────────────────
        if any(kw in err_str for kw in ("model not found", "model not available", "does not exist", "model_not_found", "not_found", "404")) or ("model" in err_str and "not found" in err_str):
            return {
                "error_type": "model_unavailable",
                "error_message": "Model unavailable",
                "provider": _extract_provider(err_str),
                "safe_detail": str(error)[:300],
            }
        # ── Authentication / invalid key ────────────────────────────────────
        if any(kw in err_str for kw in ("auth", "invalid key", "invalid api key", "unauthorized", "401", "api_key", "invalid_request_error")):
            return {
                "error_type": "invalid_api_key",
                "error_message": "Invalid or expired API key",
                "provider": _extract_provider(err_str),
                "safe_detail": str(error)[:300],
            }
        # ── Timeout ─────────────────────────────────────────────────────────
        if any(kw in err_str for kw in ("timeout", "timed out", "deadline exceeded", "context deadline")):
            return {
                "error_type": "timeout",
                "error_message": "Provider timeout",
                "provider": _extract_provider(err_str),
                "safe_detail": str(error)[:300],
            }
        # ── Overloaded / 503 ────────────────────────────────────────────────
        if any(kw in err_str for kw in ("overloaded", "503", "service unavailable", "server is overloaded")):
            return {
                "error_type": "provider_overloaded",
                "error_message": "Provider overloaded — try again shortly",
                "provider": _extract_provider(err_str),
                "safe_detail": str(error)[:300],
            }
        # ── Content policy / safety ─────────────────────────────────────────
        if any(kw in err_str for kw in ("content_policy", "safety", "blocked", "content filter", "nsfw")):
            return {
                "error_type": "content_policy",
                "error_message": "Content policy violation — output blocked by provider",
                "provider": _extract_provider(err_str),
                "safe_detail": str(error)[:300],
            }
        # ── Context length ──────────────────────────────────────────────────
        if any(kw in err_str for kw in ("context length", "context_length", "max_tokens", "token limit", "too long")):
            return {
                "error_type": "context_length_exceeded",
                "error_message": "Input exceeds model context window",
                "provider": _extract_provider(err_str),
                "safe_detail": str(error)[:300],
            }
        # ── Generic LLM / provider error ────────────────────────────────────
        return {
            "error_type": "provider_error",
            "error_message": "LLM provider error",
            "provider": _extract_provider(err_str),
            "safe_detail": str(error)[:300],
        }

    def _inject_anthropic_cache_control(self, messages: list[dict], model: str) -> list[dict]:
        """
        Inject Anthropic cache_control breakpoints for provider-level prompt caching.
        
        Anthropic caches system prompt tokens at 90% discount (cache_read: $0.30/M vs $3.00/M).
        This is the single highest-ROI optimization available — bigger than the entire Budget Governor.
        
        STRATEGY: Mark the system message as cacheable. Subsequent calls with the same
        system prompt (company profile, business rules, tone profile, action library) pay
        cache_read rate on those tokens even with different user messages.
        
        Only applies to Anthropic models that support caching.
        """
        if "anthropic" not in model.lower() and "claude" not in model.lower():
            return messages
        
        # Find the system message — mark it as cacheable
        result = []
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                result.append(msg)
                continue
            
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str) and len(content) > 100:
                    # Wrap in Anthropic's cache_control format
                    result.append({
                        "role": "system",
                        "content": [
                            {
                                "type": "text",
                                "text": content,
                                "cache_control": {"type": "ephemeral"},  # 5-min cache
                            }
                        ],
                    })
                    continue
            result.append(msg)
        return result

    def _count_tokens_exact(self, messages: list[dict], model: str = "") -> int:
        """
        Count tokens using tiktoken when available (exact),
        falling back to character-based approximation.
        Always uses the cached encoder — no repeated initialisation cost.
        """
        if self._token_encoder:
            try:
                total = 0
                for msg in messages:
                    content = msg.get("content", "") if isinstance(msg, dict) else ""
                    if isinstance(content, list):  # Anthropic cache_control format
                        for block in content:
                            if isinstance(block, dict):
                                total += len(self._token_encoder.encode(
                                    block.get("text", "")
                                ))
                    elif content:
                        total += len(self._token_encoder.encode(str(content)))
                    total += 4  # per-message overhead
                return total
            except Exception:
                pass
        # Fallback: character-based (rough but ~30% faster for very large payloads)
        return sum(
            len(str(m.get("content", "") if isinstance(m, dict) else ""))
            for m in messages
        ) // 4
        
    async def summarize_for_context(
        self,
        large_data: dict,
        context_hint: str = "anomalies and key findings",
        force: bool = False,
    ) -> str:
        """
        Map-Reduce Summarization Engine.

        Activation priority:
          1. force=True              — always summarise (bypasses optimisation level).
                                       Lets Level-0 / Max-Accuracy users still opt in.
          2. _enable_map_reduce      — per-run toggle set via budget_settings.
          3. optimisation_level >= 2 — legacy automatic path.

        Algorithm (recursive Map-Reduce):
          MAP   — split raw JSON into CHUNK_SIZE pieces; summarise each in parallel.
          REDUCE — join summaries; if still oversized, recurse (up to max_depth=4).
          FINAL  — one consolidation pass → structured Consolidated Anomaly Report.
        """
        should_summarize = force or self._enable_map_reduce or self._optimization_level >= 2

        raw_json = json.dumps(large_data, default=str)

        if not should_summarize:
            max_chars = self._budget_config.get("max_context_tokens", 10_000) * 4
            return raw_json[:max_chars]

        if len(raw_json) < 2_000:
            return raw_json  # too small to bother

        original_len = len(raw_json)
        result = await self._map_reduce_summarize(raw_json, context_hint, depth=0)
        log.info(
            "Map-Reduce complete",
            original_chars=original_len,
            result_chars=len(result),
            savings_pct=f"{(1 - len(result) / max(original_len, 1)) * 100:.0f}%",
        )
        return result

    # ── Map-Reduce internals ──────────────────────────────────────────────────

    async def _map_reduce_summarize(
        self,
        text: str,
        context_hint: str,
        depth: int = 0,
        max_depth: int = 4,
    ) -> str:
        """Recursive Map-Reduce driver. Each level halves the data volume.
        Uses JSON-object-aware splitting to avoid cutting objects mid-parse."""
        CHUNK_SIZE = 12_000   # ~3 000 tokens — comfortable for mini models
        TARGET_SIZE = 6_000   # desired output size per iteration

        if len(text) <= TARGET_SIZE or depth >= max_depth:
            return await self._summarize_chunk(text, context_hint, is_final=(depth > 0))

        # ── MAP: JSON-aware chunk splitting ──────────────────────────────────
        try:
            data = json.loads(text)
            chunks = self._chunk_json_data(data, max_chars_per_chunk=CHUNK_SIZE)
        except (json.JSONDecodeError, Exception):
            # Fallback: character-based splitting (last resort)
            chunks = [text[i: i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

        if len(chunks) <= 1:
            # Single chunk — no need to map, just summarize
            return await self._summarize_chunk(text[:TARGET_SIZE * 2], context_hint, is_final=True)

        log.debug(
            "Map-Reduce MAP phase",
            depth=depth,
            chunks=len(chunks),
            input_chars=len(text),
        )

        results = await asyncio.gather(
            *[self._summarize_chunk(c, context_hint, is_final=False) for c in chunks],
            return_exceptions=True,
        )
        summaries = [r for r in results if isinstance(r, str) and r.strip()]

        if not summaries:
            return text[:TARGET_SIZE]

        combined = "\n\n--- CHUNK BOUNDARY ---\n\n".join(summaries)

        # ── REDUCE: recurse if still oversized ───────────────────────────────
        if len(combined) > TARGET_SIZE:
            log.debug("Map-Reduce REDUCE recursion", depth=depth + 1)
            return await self._map_reduce_summarize(
                combined, context_hint, depth=depth + 1, max_depth=max_depth
            )

        # Final consolidation pass
        return await self._summarize_chunk(combined, context_hint, is_final=True)

    def _chunk_json_data(self, data: any, max_chars_per_chunk: int = 12_000) -> list[str]:
        """
        Split JSON data into logical chunks by object boundaries, not raw characters.
        Prevents sending malformed JSON fragments to the LLM during Map-Reduce.

        - For dicts: finds the largest list value and chunks that list.
        - For lists: chunks the list items directly.
        - Falls back to raw text splitting if objects are too large.
        """
        if isinstance(data, list):
            if not data:
                return [json.dumps([], default=str)]
            chunks: list[str] = []
            current_batch: list = []
            current_size = 0
            for item in data:
                item_str = json.dumps(item, default=str)
                item_size = len(item_str)
                # If a single item exceeds the chunk size, prune it recursively
                # (never raw-slice — that produces malformed JSON)
                if item_size > max_chars_per_chunk:
                    if current_batch:
                        chunks.append(json.dumps(current_batch, default=str))
                        current_batch = []
                        current_size = 0
                    pruned = self._prune_large_object(item, max_chars_per_chunk)
                    chunks.append(json.dumps(pruned, default=str))
                    continue
                if current_size + item_size > max_chars_per_chunk and current_batch:
                    chunks.append(json.dumps(current_batch, default=str))
                    current_batch = []
                    current_size = 0
                current_batch.append(item)
                current_size += item_size
            if current_batch:
                chunks.append(json.dumps(current_batch, default=str))
            return chunks or [json.dumps(data, default=str)]

        if isinstance(data, dict):
            # Find the key with the largest list value to chunk on
            best_key = None
            best_len = 0
            for k, v in data.items():
                if isinstance(v, list) and len(v) > best_len:
                    best_key = k
                    best_len = len(v)

            if best_key and best_len > 1:
                item_chunks = self._chunk_json_data(data[best_key], max_chars_per_chunk)
                result = []
                base = {k: v for k, v in data.items() if k != best_key}
                for chunk_str in item_chunks:
                    try:
                        chunk_data = dict(base)
                        chunk_data[best_key] = json.loads(chunk_str)
                        result.append(json.dumps(chunk_data, default=str))
                    except json.JSONDecodeError:
                        result.append(chunk_str)
                return result

            # No suitable list found — return as single chunk
            return [json.dumps(data, default=str)]

        # Scalar or unknown type
        return [json.dumps(data, default=str)]

    def _prune_large_object(self, obj: any, max_chars: int) -> any:
        """
        Recursively prune an object to fit within max_chars by trimming
        the deepest/longest fields first. Never produces malformed JSON.
        """
        serialized = json.dumps(obj, default=str)
        if len(serialized) <= max_chars:
            return obj

        if isinstance(obj, list):
            # Halve the list and mark truncation
            half = max(1, len(obj) // 2)
            result = obj[:half]
            if len(obj) > half:
                result.append({"_truncated": True, "items_omitted": len(obj) - half})
            # Recurse if still too large
            if len(json.dumps(result, default=str)) > max_chars:
                return self._prune_large_object(result[:max(1, half // 2)], max_chars)
            return result

        if isinstance(obj, dict):
            # Sort fields by value length descending, trim the longest first
            result = {}
            # First pass: keep all short values intact
            for k, v in obj.items():
                v_str = json.dumps(v, default=str)
                if len(v_str) <= 300:
                    result[k] = v
                elif isinstance(v, str):
                    result[k] = v[:200] + " …[truncated]"
                elif isinstance(v, list):
                    result[k] = self._prune_large_object(v, max(100, max_chars // 4))
                elif isinstance(v, dict):
                    result[k] = self._prune_large_object(v, max(100, max_chars // 4))
                else:
                    result[k] = v
            return result

        # Scalar — return as-is (it's already small)
        return obj
    async def _summarize_chunk(
        self,
        text: str,
        context_hint: str,
        is_final: bool = False,
    ) -> str:
        """Summarise a single chunk. Used by both MAP and REDUCE phases."""
        if is_final:
            system = (
                "You are a data consolidation expert. Multiple chunk summaries are provided.\n"
                f"Produce a final CONSOLIDATED ANOMALY REPORT focused on: {context_hint}.\n"
                "Merge duplicates, resolve conflicts, keep only the most critical findings.\n"
                "Return valid JSON: "
                '{ "anomalies": [...], "key_metrics": {}, '
                '"top_priorities": ["...", "...", "..."], "summary_note": "..." }'
            )
        else:
            system = (
                "You are a data summarizer. Extract ONLY the most important anomalies, "
                f"outliers, and key findings. Focus on: {context_hint}. "
                "Ignore healthy / normal items. Be concise. Return valid JSON."
            )

        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=f"Data chunk:\n{text[:15_000]}"),
        ]
        # MAP phase uses mini (cheap / parallel); REDUCE / final consolidation
        # uses balanced so structured IDs are not dropped during merging.
        tier = "balanced" if is_final else "mini"
        try:
            result_text, _ = await self.call(
                agent_name="map_reduce_summarizer",
                messages=messages,
                tier_override=tier,
            )
            return result_text
        except Exception as e:
            log.warning("Map-Reduce chunk summarisation failed", error=str(e))
            return text[:4_000]   # graceful degradation
        
        
    async def truncate_reasoning_chain(self, reasoning_chain: str) -> str:
        """
        Summarize reasoning chain using a mini model call instead of naive character truncation.
        
        FIX: Original code did reasoning_chain[-max_chars:] which discards the BEGINNING
        (situation summary, top findings) and keeps only the tail (low-priority accounts).
        This is backwards — the start contains the most important information.
        
        New approach: Use a mini model to distill key decisions, top accounts, and
        escalation reasoning into ~500 tokens.
        """
        max_chars = REASONING_CHAIN_TRUNCATE.get(self._optimization_level)
        if not max_chars or len(reasoning_chain) <= max_chars:
            return reasoning_chain
    
        # Don't truncate — summarize
        try:
            from core.llm_router import LLMMessage  # avoid circular
            system = (
                "You are a reasoning chain distiller. Extract ONLY:\n"
                "1. The overall situation summary (1-2 sentences)\n"
                "2. Top 3 highest-priority accounts/items with their risk scores\n"
                "3. The recommended actions for each\n"
                "4. The escalation decision and reason (if any)\n"
                "Discard verbose step-by-step reasoning. Be extremely concise."
            )
            user = f"Reasoning chain to distill:\n{reasoning_chain[:8000]}"
            
            messages = [
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=user),
            ]
            text, call = await self.call(
                agent_name="reasoning_chain_distiller",
                messages=messages,
                tier_override="mini",
            )
            log.debug(
                "Reasoning chain distilled",
                original_chars=len(reasoning_chain),
                distilled_chars=len(text),
                cost=f"${call.cost_usd:.5f}",
            )
            return text + "\n[DISTILLED — original chain summarized to preserve key decisions]"
        except Exception as e:
            log.warning("Reasoning chain distillation failed, using safe truncation from end", error=str(e))
            # Fallback: truncate from END (safer than start — summary is usually at the beginning)
            return reasoning_chain[:max_chars] + "... [truncated - beginning preserved]"

    # ─────────────────────────────────────────────────────────────────────────
    # Stats + Reporting
    # ─────────────────────────────────────────────────────────────────────────

    def get_live_stats(self) -> dict:
        total_in = sum(c.tokens_in for c in self._calls)
        total_out = sum(c.tokens_out for c in self._calls)
        total_cost = sum(c.cost_usd for c in self._calls)

        return {
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "total_cost_usd": total_cost,
            "total_calls": len(self._calls),
            "cache_hits": self._cache_hits,
            "optimization_level": self._optimization_level,
            "by_agent": dict(self._agent_totals),
            "recent_calls": [
                {
                    "call_id": c.call_id,
                    "agent": c.agent_name,
                    "model": c.model,
                    "tokens_in": c.tokens_in,
                    "tokens_out": c.tokens_out,
                    "cost": f"${c.cost_usd:.5f}",
                    "ms": c.duration_ms,
                    "ok": c.success,
                    "cached": c.cache_hit,
                }
                for c in self._calls[-10:]
            ],
        }

    def get_cost_table_rows(self) -> list[dict]:
        return [
            {
                "agent": name,
                "model": t.get("last_model", "—"),
                "calls": t.get("calls", 0),
                "tokens_in": f"{t.get('tokens_in', 0):,}",
                "tokens_out": f"{t.get('tokens_out', 0):,}",
                "cost": f"${t.get('cost_usd', 0.0):.4f}",
            }
            for name, t in self._agent_totals.items()
        ]

    def reset_session(self) -> None:
        self._calls.clear()
        self._agent_totals.clear()
        self._cache_hits = 0
        self._fallback_call_count = 0

    def get_fallback_call_count(self) -> int:
        """Cumulative number of deterministic fallback/mock responses returned
        this session. The orchestrator samples this before/after each node to
        detect whether that node ran on degraded (non-LLM) output."""
        return getattr(self, "_fallback_call_count", 0)

    def get_predicted_savings(self, level: int) -> dict:
        """Return estimated savings and accuracy impact for a given optimization level."""
        savings_map = {
            0: {"savings_pct": 0, "accuracy_impact": "None", "description": "Default models"},
            1: {"savings_pct": 25, "accuracy_impact": "Negligible", "description": "Research/Verification on mini"},
            2: {"savings_pct": 55, "accuracy_impact": "Low/Moderate", "description": "Reasoning/Drafting downgraded + context truncation"},
            3: {"savings_pct": 80, "accuracy_impact": "Moderate", "description": "All mini + context summarization"},
        }
        return savings_map.get(level, savings_map[1])

    # ─────────────────────────────────────────────────────────────────────────
    # Private Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_model_with_budget(
        self,
        agent_name: str,
        tier_override: Optional[str],
        model_override: Optional[str],
        client_overrides: Optional[dict],
    ) -> tuple[str, str]:
        """Resolve model string AND tier, applying budget governance."""

        # 1. Explicit model override (highest priority)
        if model_override:
            return model_override, tier_override or "balanced"

        # 2. Client-level config override
        if client_overrides and agent_name in client_overrides:
            override = client_overrides[agent_name]
            if override:
                tier = self._get_tier_for_model(override)
                return override, tier

        # 3. Tier override (explicit)
        if tier_override:
            return self._task_models[tier_override]["model"], tier_override

        # 4. Budget Governor: apply tier downgrade map
        budget_map = BUDGET_TIER_MAPS.get(self._optimization_level, {})
        if agent_name in budget_map:
            governed_tier = budget_map[agent_name]
            return self._task_models[governed_tier]["model"], governed_tier
        default_agent_tier = self._agent_defaults.get(agent_name, {}).get("tier", "balanced")
        governed_tier = budget_map.get(agent_name, default_agent_tier)
        # 4.5. Dynamic Tier Protection for logic-heavy agents
        if agent_name in LOGIC_HEAVY_AGENTS:
            # Never downgrade reasoning/consensus below 'balanced'
            tier_order = ["mini", "balanced", "fast", "heavy"]
            current_idx = tier_order.index(governed_tier) if governed_tier in tier_order else 3
            min_idx = tier_order.index("balanced")
            if current_idx < min_idx:
                governed_tier = "balanced"
                log.debug(
                    "Budget governor: protected logic-heavy agent from mini downgrade",
                    agent=agent_name,
                    enforced_tier="balanced",
                )
            return self._task_models[governed_tier]["model"], governed_tier

        # 5. Default per-agent config
        tier = self._agent_defaults.get(agent_name, {}).get("tier", "balanced")
        return self._task_models[tier]["model"], tier

    def _get_tier_for_model(self, model: str) -> str:
        for tier, config in self._task_models.items():
            # Add the isinstance check here
            if isinstance(config, dict) and config.get("model") == model:
                return tier
        return "balanced"

    @staticmethod
    def _provider_for_model(model: str) -> str:
        return model.split("/", 1)[0] if "/" in model else "anthropic"

    def _get_fallback_chain(self, primary_model: str, tier: str) -> list[str]:
        """
        Build fallback chain from config.
        
        FIX: Original code put the primary model first then appended all fallbacks.
        This caused budget_heavy (DeepSeek) to fall back to Llama-8B for complex
        structured outputs — much worse than the original model.
        """
        chain_models = self._fallback_chain.get(tier, [])
        # Primary model is first; then all fallbacks that aren't the primary
        full_chain = [primary_model] + [m for m in chain_models if m != primary_model]
        # Never include llama-3.1-8b-instant as fallback for logic-heavy agents
        # (it cannot reliably output complex JSON schemas)
        if tier in ("heavy", "budget_heavy", "balanced"):
            full_chain = [m for m in full_chain if "8b-instant" not in m.lower()]
        return full_chain

    def _calculate_cost(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> float:
        """
        Multi-dimensional cost calculation supporting:
        - Standard input tokens
        - Cache read tokens (90% cheaper for Anthropic, ~90% for DeepSeek)
        - Cache write tokens (slight premium for Anthropic)
        - Output tokens
        
        FIX: Original code only had input/output rates, ignoring cache pricing.
        """
        rates = self._cost_rates.get(model, {"input": 0.0, "output": 0.0})
        
        input_rate = rates.get("input", 0.0)
        output_rate = rates.get("output", 0.0)
        cache_read_rate = rates.get("cache_read", input_rate)    # default to input rate if not defined
        cache_write_rate = rates.get("cache_write", input_rate)  # default to input rate if not defined
        
        # Regular input tokens (excluding cache hits/writes)
        regular_tokens = max(0, tokens_in - cache_read_tokens - cache_write_tokens)
        
        cost = (
            (regular_tokens * input_rate)
            + (cache_read_tokens * cache_read_rate)
            + (cache_write_tokens * cache_write_rate)
            + (tokens_out * output_rate)
        ) / 1_000_000
        
        return round(cost, 6)

    def _record_call(self, call: LLMCall) -> None:
        self._calls.append(call)
        if getattr(call, "is_fallback", False):
            self._fallback_call_count = getattr(self, "_fallback_call_count", 0) + 1
        agent = call.agent_name
        if agent not in self._agent_totals:
            self._agent_totals[agent] = {"calls": 0, "tokens_in": 0, "tokens_out": 0,
                                          "cost_usd": 0.0, "last_model": ""}
        t = self._agent_totals[agent]
        t["calls"] += 1
        t["tokens_in"] += call.tokens_in or 0
        t["tokens_out"] += call.tokens_out or 0
        t["cost_usd"] += call.cost_usd or 0.0
        t["last_model"] = call.model

    def _build_cache_key(self, agent_name: str, messages: list[dict]) -> str:
        # Include tenant_id so cached reasoning never leaks between tenants.
        tenant_salt = getattr(self, "_current_tenant_id", "")
        content = tenant_salt + agent_name + json.dumps(messages, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    async def _get_cached_response(self, key: str) -> Optional[str]:
        if not self._redis:
            return None
        try:
            val = await self._redis.get(f"llm_cache:{key}")
            return val.decode() if val else None
        except Exception:
            return None

    async def _set_cached_response(self, key: str, value: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.setex(f"llm_cache:{key}", self._cache_ttl, value.encode())
        except Exception:
            pass

    def _extract_confidence(self, text: str) -> Optional[float]:
        """Try to extract a confidence score from LLM output."""
        import re
        for pattern in [r'"reasoning_confidence"\s*:\s*([0-9.]+)',
                         r'"confidence"\s*:\s*([0-9.]+)',
                         r'confidence[:\s]+([0-9.]+)']:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1))
                except ValueError:
                    pass
        return None

    def _load_config(self, config_path: str) -> dict:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"LLM config not found: {config_path}")
        with open(path) as f:
            return json.load(f)

    def _generate_mock_fallback_response(
        self,
        agent_name: str,
        lm_messages: list[dict],
        tools: Optional[list[dict]],
        attempt_model: str,
        tier: str,
        start_ms: int,
        call_id: str,
    ) -> tuple[str, LLMCall]:
        raise LLMProviderUnavailableError(
            agent_name,
            [{"attempt": 1, "model": attempt_model,
              "provider": self._provider_for_model(attempt_model),
              "error_type": "deterministic_fallback_disabled"}],
        )

        """Generate deterministic mock response when MOCK_LLM=true or offline."""
        has_tool_result = any("Tool:" in m.get("content", "") or "Result:" in m.get("content", "") for m in lm_messages if isinstance(m, dict))

        if tools and not has_tool_result:
            tool_name = tools[0].get("function", {}).get("name") if isinstance(tools[0], dict) else "email_get_synthetic_messages"
            content = f'```json\n{{"tool_calls": [{{"name": "{tool_name}", "args": {{}}}}]\n}}```'
        else:
            if agent_name in ("research_agent", "fetch_emails"):
                content = json.dumps({
                    "messages": [
                        {
                            "id": "msg-synth-001",
                            "subject": "Urgent: Payment Gateway Failure",
                            "sender": "alerts@paymentprovider.com",
                            "category": "critical_incident",
                            "body": "Payment processing failing for 15% of checkout transactions."
                        }
                    ],
                    "emails_fetched": 40,
                    "status": "success"
                })
            elif agent_name in ("summarizer_agent", "summarize_emails"):
                content = json.dumps({
                    "situation_summary": "High-priority operational email summary: 40 emails ingested across 20 operational scenarios.",
                    "urgent_action_required": [
                        "Investigate Payment Gateway Timeout (15% checkout failures)",
                        "Respond to Enterprise SLA warning from Acme Corp"
                    ],
                    "categorized_summaries": {
                        "critical_incidents": ["Payment Gateway Timeout (15% failures)", "Database Primary Failover Warning"],
                        "customer_support": ["Login authentication loop ticket #402", "CSM Onboarding delay"],
                        "general_updates": ["Q3 Product Roadmap Review", "Vendor Invoice Received"]
                    },
                    "overall_sentiment": "mixed_requires_attention",
                    "confidence": 0.95,
                    "reasoning_confidence": 0.95
                })
            elif agent_name in ("humanizer_agent", "humanize_draft"):
                content = json.dumps({
                    "approval_items": [
                        {
                            "action_type": "email_response",
                            "status": "pending",
                            "title": "Customer response required: Enterprise SLA Warning from Acme Corp",
                            "reason": "AI identified high-urgency SLA notice requiring executive response.",
                            "category": "sla_risk",
                            "category_label": "SLA Risk",
                            "urgency_score": 9,
                            "detected_sentiment": "urgent_negative",
                            "trigger_keywords": ["URGENT", "SLA warning", "latency issue"],
                            "source": {
                                "message_id": "msg-synth-002",
                                "subject": "URGENT: Enterprise SLA warning",
                                "sender": "cto@acmecorp.com"
                            },
                            "proposed_action": {
                                "type": "gmail_draft",
                                "recipient": "cto@acmecorp.com",
                                "subject": "Re: URGENT: Enterprise SLA warning - Investigation Update",
                                "body": "Hi Acme Team,\n\nThank you for flagging this so quickly. I understand how disruptive latency can be for your team, especially under your SLA commitments.\n\nOur senior engineering team is actively investigating the issue now, and Customer Success is coordinating updates from the incident lead. We will send you a clear status update within 60 minutes, including current impact, next steps, and the path to resolution.\n\nBest,\nSMBFlow Enterprise Support"
                            },
                            "xai_explanation": {
                                "trigger_rationale": "The email contained urgent SLA language and referenced a customer-impacting latency issue.",
                                "strategy_rationale": "The safest response is an accountable incident acknowledgement with a near-term update window and no unverified root-cause claims.",
                                "confidence_metrics": {
                                    "intent_match": 0.96,
                                    "sentiment_confidence": 0.94,
                                    "safety_boundary_cleared": 0.98
                                }
                            },
                            "confidence": 0.96
                        },
                        {
                            "action_type": "email_response",
                            "status": "pending",
                            "title": "Billing dispute response required for finance partner",
                            "reason": "Invoice dispute mentions duplicate charge and renewal risk.",
                            "category": "billing_dispute",
                            "category_label": "Billing Dispute",
                            "urgency_score": 8,
                            "detected_sentiment": "concerned",
                            "trigger_keywords": ["duplicate charge", "invoice", "renewal"],
                            "source": {
                                "message_id": "msg-synth-014",
                                "subject": "Duplicate charge on enterprise invoice",
                                "sender": "finance@northstar.example"
                            },
                            "proposed_action": {
                                "type": "gmail_draft",
                                "recipient": "finance@northstar.example",
                                "subject": "Re: Duplicate charge on enterprise invoice",
                                "body": "Hi Northstar Finance Team,\n\nThanks for calling this out. I can see why a possible duplicate charge needs quick attention, especially this close to renewal.\n\nWe are reviewing the invoice and payment records now. I will follow up with a confirmed adjustment path or a clear explanation of the charge by end of business today.\n\nBest,\nSMBFlow Billing Support"
                            },
                            "xai_explanation": {
                                "trigger_rationale": "The message references a duplicate charge and renewal timing, which increases business risk.",
                                "strategy_rationale": "Billing disputes need a calm acknowledgement, ownership, and a concrete review timeline before making financial commitments.",
                                "confidence_metrics": {
                                    "intent_match": 0.93,
                                    "sentiment_confidence": 0.91,
                                    "safety_boundary_cleared": 0.97
                                }
                            },
                            "confidence": 0.93
                        }
                    ],
                    "routine_items_count": 38,
                    "batch_intelligence": {
                        "total_volume": 40,
                        "sentiment_distribution": {
                            "positive": 9,
                            "neutral": 20,
                            "concerned": 8,
                            "urgent_negative": 3
                        },
                        "category_breakdown": {
                            "sla_risk": 1,
                            "billing_dispute": 1,
                            "service_outage": 1,
                            "routine_inquiry": 37
                        },
                        "critical_kpis": {
                            "pending_approval_count": 2,
                            "avg_urgency_score": 8.5,
                            "highest_urgency_score": 9,
                            "estimated_response_sla_minutes": 60
                        }
                    },
                    "summary": "Humanized 2 urgent customer response drafts and attached explainability metadata."
                })
            elif agent_name in ("drafting_agent", "evaluate_actions"):
                content = json.dumps({
                    "approval_items": [
                        {
                            "action_type": "email_response",
                            "status": "pending",
                            "title": "Customer response required: Enterprise SLA Warning from Acme Corp",
                            "reason": "AI identified high-urgency SLA notice requiring executive response.",
                            "source": {
                                "message_id": "msg-synth-002",
                                "subject": "URGENT: Enterprise SLA warning",
                                "sender": "cto@acmecorp.com"
                            },
                            "proposed_action": {
                                "type": "gmail_draft",
                                "recipient": "cto@acmecorp.com",
                                "subject": "Re: URGENT: Enterprise SLA warning - SMBFlow Investigation Update",
                                "body": "Hi Acme Team,\n\nWe have received your SLA warning and our senior engineering team is already investigating the latency issue. We will provide an updated incident report within 60 minutes.\n\nBest regards,\nCustomer Success Team"
                            },
                            "confidence": 0.96
                        }
                    ],
                    "routine_items_count": 38,
                    "summary": "Identified 1 high-priority escalation requiring human review and draft approval."
                })
            elif agent_name in ("memory_agent", "persist_results"):
                content = json.dumps({
                    "patterns_to_store": [
                        {
                            "key": "email_workflow_summary_digest",
                            "pattern_data": {
                                "dataset": "email_workflow_demo",
                                "total_processed": 40,
                                "critical_count": 2
                            },
                            "success_rate": 1.0
                        }
                    ],
                    "summary": "Email summary patterns persisted to local memory store.",
                    "delta_analysis": "Email activity within normal operational baseline.",
                    "confidence": 0.98
                })
            else:
                content = json.dumps({
                    "status": "completed",
                    "confidence": 0.90,
                    "summary": f"Mock output for agent {agent_name}"
                })

        duration_ms = max(1, int(time.time() * 1000) - start_ms)
        call = LLMCall(
            call_id=call_id,
            agent_name=agent_name,
            model=attempt_model,
            tier=tier,
            tokens_in=100,
            tokens_out=150,
            cost_usd=0.0,
            duration_ms=duration_ms,
            success=True,
            is_fallback=True,   # deterministic mock — NOT a real model response
        )
        self._record_call(call)
        return content, call
