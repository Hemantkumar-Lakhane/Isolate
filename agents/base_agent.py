"""
agents/base_agent.py
====================
Abstract base class for all OpsGrid agents.
Every agent: receives input → calls LLM → uses tools → returns structured output.
Agents never call each other directly — all routing through the orchestrator.

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from core.llm_router import LLMCall, LLMMessage, LLMRouter
from core.state_manager import AgentStatus, StateManager
import aiofiles
import asyncio
log = structlog.get_logger()

MAX_TOOL_ITERATIONS = 10   # Prevent infinite tool loops
ALLOWED_EDGE_CONDITIONS: frozenset[str] = frozenset({
    "not output.escalate",
    "output.escalate",
    "not output.passed",
    "output.passed",
    "not output.success",
    "output.success",
    "output.consensus",
    "not output.consensus",
    # Common shorthand variants
    "output['escalate']",
    "output['passed']",
    "not output['escalate']",
    "not output['passed']",
})
# ─────────────────────────────────────────────────────────────────────────────
# JSON Recovery Utility
# ─────────────────────────────────────────────────────────────────────────────
 
def _recover_truncated_json(text: str) -> Optional[dict]:
    """
    Attempt to recover a truncated JSON object produced when LLM output hits
    the max_tokens limit mid-stream. Uses a robust stack-based approach to
    properly close nested structures.
    """
    start = text.find('{')
    if start == -1:
        return None

    json_text = text[start:]

    # --- Pass 1: track structure depth ---
    stack = []
    in_string = False
    escape_next = False
    last_depth0_close = -1

    for i, ch in enumerate(json_text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            stack.append('}')
        elif ch == '[':
            stack.append(']')
        elif ch in ('}', ']'):
            if stack and stack[-1] == ch:
                stack.pop()
            if not stack:
                last_depth0_close = i

    # Already valid?
    if not stack and not in_string:
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

    # --- Pass 2: try to close open structures ---
    truncated = json_text.rstrip()

    # Walk backwards past any incomplete value: partial string, number, keyword
    while truncated and truncated[-1] not in ('}', ']', '"', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'e', 'l', 'n'):
        truncated = truncated[:-1]
    # Remove trailing comma
    truncated = truncated.rstrip().rstrip(',').rstrip()

    # Re-count to get accurate state at exact truncated position
    stack = []
    in_s = False
    esc = False
    for ch in truncated:
        if esc:
            esc = False
            continue
        if ch == '\\' and in_s:
            esc = True
            continue
        if ch == '"':
            in_s = not in_s
            continue
        if in_s:
            continue
        if ch == '{':
            stack.append('}')
        elif ch == '[':
            stack.append(']')
        elif ch in ('}', ']'):
            if stack and stack[-1] == ch:
                stack.pop()

    if in_s:
        truncated += '"'  # close the open string

    # The stack has the exact closing characters needed, in reverse order.
    closing = ''.join(reversed(stack))
    attempt = truncated + closing

    try:
        result = json.loads(attempt)
        if isinstance(result, dict):
            result["_json_recovered"] = True   # audit flag
            return result
    except json.JSONDecodeError:
        pass

    # --- Pass 3: fall back to the last complete top-level object ---
    if last_depth0_close > 0:
        try:
            result = json.loads(json_text[:last_depth0_close + 1])
            if isinstance(result, dict):
                result["_json_recovered"] = True
                return result
        except json.JSONDecodeError:
            pass

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Data Contracts (shared by all agents)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentInput:
    """Standardized input passed to every agent."""
    workflow_instance_id: str
    tenant_id: str
    tenant_config: dict                 # Full client config JSON
    accumulated_context: dict           # Everything collected so far in this run
    node_specific_data: dict            # Data specific to this agent's current task
    llm_overrides: Optional[dict] = None  # Per-client model overrides


@dataclass
class AgentOutput:
    """Standardized output from every agent."""
    success: bool
    confidence: Optional[float]         # 0.0 to 1.0 when reported by the model
    output_data: dict                   # Structured output for next agent
    reasoning_chain: str                # Claude's thinking — stored for audit
    escalate: bool = False              # True = send to human queue
    escalation_reason: str = ""
    # Cost fields (populated automatically by base class)
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    cost_usd: Optional[float] = None
    model_used: str = ""
    duration_ms: int = 0
    error: Optional[str] = None
    provider: Optional[str] = None
    cached_tokens: Optional[int] = None
    fallback_used: bool = False
    fallback_from: Optional[str] = None
    fallback_reason: Optional[str] = None
    provider_attempts: Optional[list[dict]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Tool Registry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: Any
    error: Optional[str] = None


class ToolRegistry:
    """Holds all available tools for a given workflow context."""

    def __init__(self):
        self._tools: dict[str, callable] = {}

    def register(self, name: str, fn: callable, schema: dict) -> None:
        self._tools[name] = {"fn": fn, "schema": schema}

    def get_schemas(self, tool_names: list[str]) -> list[dict]:
        """Return OpenAI-format tool schemas for specified tools."""
        schemas = []
        for name in tool_names:
            if name in self._tools:
                schemas.append(self._tools[name]["schema"])
        return schemas

    async def execute(self, tool_name: str, args: dict) -> ToolResult:
        """Execute a tool by name."""
        if tool_name not in self._tools:
            return ToolResult(tool_name=tool_name, success=False, data=None,
                              error=f"Tool '{tool_name}' not registered")
        try:
            fn = self._tools[tool_name]["fn"]
            result = await fn(**args)
            return ToolResult(tool_name=tool_name, success=True, data=result)
        except Exception as e:
            error_str = str(e)
            log.error("Tool execution failed", tool=tool_name, error=error_str[:200])
            if len(error_str) > 500:
                error_str = error_str[:500] + "... [truncated]"
            return ToolResult(tool_name=tool_name, success=False, data=None, error=error_str)




class SafeDict(dict):
    """
    Dict subclass that:
    - Returns None (falsy) for missing keys instead of raising KeyError
    - Supports dot-notation access (output.escalate)
    - Supports default values for missing fields
    - Recursively wraps nested dicts
 
    Used by ReasoningAgent to safely access business_rules without
    manually constructing fallback dicts for each field.
    """
    def __getattr__(self, item):
        val = self.get(item)
        if isinstance(val, dict) and not isinstance(val, SafeDict):
            return SafeDict(val)
        return val  # None for missing keys — intentional, keeps conditions clean
 
    def __setattr__(self, key, value):
        self[key] = value
 
    @classmethod
    def from_config(cls, config_section, defaults: dict = None) -> "SafeDict":
        """
        Build a SafeDict from a config section with typed defaults.
        Handles None values from explicit null in JSON.
        """
        merged = {**(defaults or {}), **(config_section or {})}
        return cls(merged)
 
    def get_float(self, key: str, default: float = 0.0) -> float:
        val = self.get(key, default)
        try:
            return float(val) if val is not None else default
        except (TypeError, ValueError):
            return default
 
    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key, default)
        try:
            return int(val) if val is not None else default
        except (TypeError, ValueError):
            return default


# ─────────────────────────────────────────────────────────────────────────────
# Base Agent
# ─────────────────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base for all OpsGrid agents.

    Subclasses must implement:
        - agent_type: str  (e.g. "research_agent")
        - system_prompt_template: str  (can contain {placeholders})
        - receive(input: AgentInput) -> AgentOutput
    """

    agent_type: str = "base_agent"
    system_prompt_template: str = ""

    def __init__(
        self,
        llm_router: LLMRouter,
        state_manager: StateManager,
        tool_registry: ToolRegistry,
        ws_broadcast: Optional[callable] = None,
        rag_engine=None,                          
    ):
        self._llm = llm_router
        self._state = state_manager
        self._tools = tool_registry
        self._rag = rag_engine                    
        self._log = log.bind(agent=self.agent_type)
        self._ws_broadcast: Optional[callable] = ws_broadcast
        self._current_node_id: Optional[str] = None
        self._current_run_id: Optional[str] = None

    @abstractmethod
    async def receive(self, input: AgentInput) -> AgentOutput:
        """Main entry point. Must be implemented by every agent."""
        ...

    # ─────────────────────────────────────────────────────────────────────
    # Protected helpers — use these in subclass implementations
    # ─────────────────────────────────────────────────────────────────────

    async def _call_with_tools(
        self,
        messages: list[LLMMessage],
        available_tools: list[str],
        input: AgentInput,
    ) -> tuple[str, list[LLMCall]]:
        """
        Agentic tool-calling loop. Handles both structured LiteLLM tool calls
        and legacy string-format tool calls. Loops until final text response.
        Returns (final_text, all_llm_calls).
        """
        tool_schemas = self._tools.get_schemas(available_tools)
        all_calls: list[LLMCall] = []
        conversation = list(messages)
        self._last_tool_outputs = []
        iterations = 0
 
        while iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            # Broadcast LLM is now thinking / generating
            if self._ws_broadcast and self._current_node_id:
                try:
                    await self._ws_broadcast("agent_live_output", {
                        "run_id":  self._current_run_id,
                        "node_id": self._current_node_id,
                        "type":    "llm_thinking",
                        "tool":    "",
                        "preview": "",
                    })
                except Exception:
                    pass
            _max_tok = input.node_specific_data.get("_max_tokens_override") if input and input.node_specific_data else None
            text, call = await self._llm.call(
                agent_name=self.agent_type,
                messages=conversation,
                tools=tool_schemas if tool_schemas else None,
                client_overrides=input.llm_overrides,
                max_tokens_override=_max_tok,
            )
            all_calls.append(call)
 
            # Guard: empty response should not loop
            if not text or not text.strip():
                self._log.warning("Empty LLM response in tool loop", iteration=iterations)
                return "", all_calls
 
            # Detect tool calls
            if call.success and self._has_tool_call(text):
                tool_calls = self._extract_tool_calls(text)
 
                if not tool_calls:
                    # No parseable tool calls despite marker — treat as final
                    return text, all_calls
 
                tool_results = []
                # ── Parallelism Governor ─────────────────────────────────────
                budget_level: int = getattr(self._llm, '_optimization_level', 1)
 
                if budget_level < 2:
                    # ── Parallel execution (asyncio.gather) ──────────────────
                    # All tool calls are fired concurrently; order is preserved.
                    async def _run_tool(tc: dict) -> tuple[dict, str]:
                        t_name = tc.get("name", "")
                        t_args = tc.get("args", {})
                        self._log.debug("Executing tool (parallel)", tool=t_name)
                        result = await self._tools.execute(t_name, t_args)
                        if result.success:
                            self._last_tool_outputs.append({"tool": t_name, "data": result.data})
                            text_out = (
                                f"Tool: {t_name}\n"
                                f"Result: {json.dumps(result.data, default=str)[:4000]}"
                            )
                        else:
                            text_out = f"Tool: {t_name}\nERROR: {result.error}"
                        return tc, text_out
                    # Broadcast tool-calling events BEFORE firing (parallel path)
                    if self._ws_broadcast and self._current_node_id:
                        for _tc_pre in tool_calls:
                            try:
                                await self._ws_broadcast("agent_live_output", {
                                    "run_id":  self._current_run_id,
                                    "node_id": self._current_node_id,
                                    "type":    "tool_calling",
                                    "tool":    _tc_pre.get("name", ""),
                                    "preview": "",
                                })
                            except Exception:
                                pass
                    gathered = await asyncio.gather(
                        *[_run_tool(tc) for tc in tool_calls],
                        return_exceptions=True,
                    )
                    
                    # Broadcast live tool results to frontend
                    if self._ws_broadcast and self._current_node_id:
                        for item in gathered:
                            if not isinstance(item, Exception):
                                tc_inner, result_text_inner = item
                                try:
                                    await self._ws_broadcast("agent_live_output", {
                                        "run_id":   self._current_run_id,
                                        "node_id":  self._current_node_id,
                                        "type":     "tool",
                                        "tool":     tc_inner.get("name", ""),
                                        "preview":  result_text_inner[:180],
                                    })
                                except Exception:
                                    pass
                    tool_results = []
                    for item in gathered:
                        if isinstance(item, Exception):
                            error_str = str(item)
                            if len(error_str) > 500:
                                error_str = error_str[:500] + "... [truncated]"
                            tool_results.append(f"Tool ERROR: {error_str}")
                        else:
                            _, result_text = item
                            tool_results.append(result_text)
 
                else:
                    # ── Sequential execution with Early-Exit ─────────────────
                    # Level >= 2: run tools one at a time; stop if the data
                    # gathered already satisfies the goal (non-empty meaningful
                    # result with records > 0 or accounts/transactions keys).
                    tool_results = []
                    for tc in tool_calls:
                        t_name = tc.get("name", "")
                        t_args = tc.get("args", {})
                        self._log.debug("Executing tool (sequential)", tool=t_name)
                        # Broadcast tool is being called
                        if self._ws_broadcast and self._current_node_id:
                            try:
                                await self._ws_broadcast("agent_live_output", {
                                    "run_id":  self._current_run_id,
                                    "node_id": self._current_node_id,
                                    "type":    "tool_calling",
                                    "tool":    t_name,
                                    "preview": "",
                                })
                            except Exception:
                                pass
                        result = await self._tools.execute(t_name, t_args)
                        if result.success:
                            result_text = (
                                f"Tool: {t_name}\n"
                                f"Result: {json.dumps(result.data, default=str)[:4000]}"
                            )
                            tool_results.append(result_text)
                            
                            # Broadcast live update
                            if self._ws_broadcast and self._current_node_id:
                                try:
                                    await self._ws_broadcast("agent_live_output", {
                                        "run_id":  self._current_run_id,
                                        "node_id": self._current_node_id,
                                        "type":    "tool",
                                        "tool":    t_name,
                                        "preview": result_text[:180],
                                    })
                                except Exception:
                                    pass
                            # ── Early-exit check ─────────────────────────────
                            # If we already have substantive data, stop calling
                            # more tools to avoid unnecessary spend.
                            if isinstance(result.data, dict):
                                has_data = any(
                                    isinstance(result.data.get(k), list)
                                    and len(result.data.get(k, [])) > 0
                                    for k in (
                                        "accounts", "transactions", "patients",
                                        "products", "deals", "nps_data",
                                    )
                                )
                                if has_data and len(tool_results) >= 2:
                                    self._log.debug(
                                        "Early exit: goal satisfied",
                                        tool=t_name,
                                        tools_run=len(tool_results),
                                    )
                                    break
                        else:
                            error_str = str(result.error or "unknown error")
                            if len(error_str) > 500:
                                error_str = error_str[:500] + "... [truncated]"
                            tool_results.append(f"Tool: {t_name}\nERROR: {error_str}")
 
                # ── Within-loop tool result compression ──────────────────────────────────
                tool_results_str = "\n\n".join(tool_results)

                if len(tool_results_str) > 6000 and self._llm._optimization_level >= 1:
                    try:
                        compressed = await self._llm._compress_tool_results(tool_results_str)
                        tool_results = [compressed]
                        self._log.debug(
                            "Within-loop tool results compressed",
                            original_chars=len(tool_results_str),
                            compressed_chars=len(compressed)
                        )
                    except Exception as _ce:
                        self._log.debug(
                            "Tool result compression failed, using original",
                            error=str(_ce)
                        )

                # Build content for next turn — extract text portion from JSON if needed
                assistant_content = self._extract_content_from_response(text)
                conversation.append(LLMMessage(role="assistant", content=assistant_content))
                conversation.append(LLMMessage(
                    role="user",
                    content="Tool results:\n" + "\n\n".join(tool_results),
                ))
            else:
                # Final response — cache it if applicable
                final_text = self._extract_content_from_response(text)
                if (hasattr(self, '_llm') and
                        self._llm._optimization_level >= 1 and
                        self._llm._redis and
                        not tool_schemas):
                    _ck = self._llm._build_cache_key(self.agent_type,
                                                     [{"role": m.role, "content": m.content}
                                                      for m in messages])
                    await self._llm._set_cached_response(_ck, final_text)
                # Broadcast the LLM response preview
                if self._ws_broadcast and self._current_node_id and final_text:
                    try:
                        await self._ws_broadcast("agent_live_output", {
                            "run_id":  self._current_run_id,
                            "node_id": self._current_node_id,
                            "type":    "llm",
                            "preview": final_text[:250],
                        })
                    except Exception:
                        pass
                return final_text, all_calls
 
        raise RuntimeError(
            f"Agent {self.agent_type} exceeded {MAX_TOOL_ITERATIONS} tool iterations"
        )

    async def _simple_call(
        self,
        system: str,
        user: str,
        input: AgentInput,
        tier_override: Optional[str] = None,
    ) -> tuple[str, LLMCall]:
        """Single-turn LLM call (no tools), with live token streaming via WebSocket."""
        recovery_hint = input.node_specific_data.get("_recovery_hint", "")
        if recovery_hint:
            system = (
                "=== SELF-HEALING RECOVERY CONTEXT ===\n"
                "A previous attempt at this step failed. "
                "Use the following hint to avoid repeating the same error:\n"
                f"{recovery_hint}\n"
                "=== END RECOVERY CONTEXT ===\n\n"
            ) + system
 
        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]
 
        # ── Broadcast "model is generating" before the call ──────────────
        if self._ws_broadcast and self._current_node_id:
            try:
                await self._ws_broadcast("agent_live_output", {
                    "run_id":  self._current_run_id,
                    "node_id": self._current_node_id,
                    "type":    "llm_thinking",
                    "tool":    "",
                    "preview": "",
                })
            except Exception:
                pass
 
        # ── Build streaming callback ──────────────────────────────────────
        streaming_callback = None
        if self._ws_broadcast and self._current_node_id:
            _run_id  = self._current_run_id
            _node_id = self._current_node_id
            _agent   = self.agent_type
            _ws      = self._ws_broadcast
 
            async def _on_token(token: str) -> None:
                try:
                    await _ws("agent_live_output", {
                        "run_id":  _run_id,
                        "node_id": _node_id,
                        "type":    "llm_token",
                        "token":   token,
                        "tool":    "",
                        "preview": "",
                    })
                except Exception:
                    pass
 
            streaming_callback = _on_token
 
        _max_tok = input.node_specific_data.get("_max_tokens_override") if input and input.node_specific_data else None
        return await self._llm.call(
            agent_name=self.agent_type,
            messages=messages,
            client_overrides=input.llm_overrides if input else None,
            tier_override=tier_override,
            streaming_callback=streaming_callback,
            max_tokens_override=_max_tok,
        )

    def _build_system_prompt(self, input: AgentInput, **extra_vars) -> str:
        """Render the system prompt template with tenant config values."""
        cfg = input.tenant_config
        vars = {
            "tenant_name": cfg.get("client_name", "the company"),
            "industry": cfg.get("industry", "business"),
            "company_profile": json.dumps(cfg.get("company_profile", {}), indent=2),
            "business_rules": json.dumps(cfg.get("business_rules", {}), indent=2),
            "tone_profile": json.dumps(cfg.get("tone_profile", {}), indent=2),
            "action_library": json.dumps(cfg.get("action_library", {}), indent=2),
            "confidence_threshold": cfg.get("business_rules", {}).get("confidence_threshold", 0.75),
            **extra_vars,
        }
        import re
        def replacer(match):
            key = match.group(1)
            parts = key.split('.')
            if parts[0] not in vars:
                return match.group(0)
            
            val = vars[parts[0]]
            for part in parts[1:]:
                if hasattr(val, "get") and callable(val.get):
                    val = val.get(part)
                elif hasattr(val, part):
                    val = getattr(val, part)
                else:
                    return match.group(0)
            return str(val) if val is not None else ""

        try:
            return re.sub(r'\{([a-zA-Z0-9_.]+)\}', replacer, self.system_prompt_template)
        except Exception as e:
            self._log.warning("Prompt template format error", error=str(e))
    async def _call_llm_with_fallback(
        self,
        messages: list[LLMMessage],
        input: AgentInput,
    ) -> tuple[str, LLMCall]:
        """Helper to invoke LLM with conversation messages."""
        return await self._llm.call(
            agent_name=self.agent_type,
            messages=messages,
            client_overrides=input.llm_overrides if input else None,
        )

    def _parse_json(self, text: str) -> Optional[dict]:
        """Helper to parse JSON output safely."""
        res = self._parse_json_output(text)
        return res if res and not res.get("parse_error") else None

    def _parse_json_output(self, text: str) -> dict:
        """
        Safely parse JSON from LLM output, handling:
          - Markdown code fences (```json ... ```)
          - Truncated output (LLM hit max_tokens mid-response)
          - Partial JSON structures
        """
        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?\n?(.*?)```", r"\1", text, flags=re.DOTALL).strip()
 
        # --- Attempt 1: direct parse ---
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
 
        # --- Attempt 2: extract first {...} block ---
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
 
        # --- Attempt 3: intelligent truncation recovery ---
        recovered = _recover_truncated_json(cleaned)
        if recovered is not None:
            self._log.warning(
                "Recovered truncated JSON output — LLM likely hit max_tokens",
                text_len=len(text),
                recovered_keys=list(recovered.keys())[:8],
            )
            return recovered
 
        # --- All attempts failed ---
        self._log.error("Failed to parse JSON output", text_preview=text[:300])
        return {"raw_output": text, "parse_error": True}

    def _aggregate_costs(self, calls: list[LLMCall]) -> dict:
        """Sum up token and cost data from multiple LLM calls."""
        successful = [call for call in calls if call.success]
        usage_calls = [call for call in successful if call.tokens_in is not None or call.tokens_out is not None]
        cost_calls = [call for call in successful if call.cost_usd is not None]
        last_call = successful[-1] if successful else (calls[-1] if calls else None)
        return {
            "tokens_in": sum(c.tokens_in or 0 for c in usage_calls) if usage_calls else None,
            "tokens_out": sum(c.tokens_out or 0 for c in usage_calls) if usage_calls else None,
            "cost_usd": sum(c.cost_usd or 0 for c in cost_calls) if cost_calls else None,
            "model_used": last_call.model if last_call and last_call.success else "",
            "provider": last_call.provider if last_call and last_call.success else None,
            "cached_tokens": sum(c.cached_tokens or 0 for c in successful if c.cached_tokens is not None) or None,
            "fallback_used": any(c.fallback_used for c in calls),
            "fallback_from": next((c.fallback_from for c in calls if c.fallback_from), None),
            "fallback_reason": next((c.fallback_reason for c in calls if c.fallback_reason), None),
        }

    def _has_tool_call(self, text: str) -> bool:
        """
        Detect if LLM response contains a tool call request.
        Handles:
          1. JSON format: {"tool_calls": [...], "content": "..."}  ← from llm_router
          2. LiteLLM string markers
          3. Legacy TOOL_CALL: format
          4. XML-style <tool_call>
        """
        if not text or not text.strip():
            return False
 
        stripped = text.strip()
 
        # Try JSON format first (fastest check)
        if stripped.startswith('{'):
            try:
                parsed = json.loads(stripped)
                if "tool_calls" in parsed and parsed["tool_calls"]:
                    return True
            except (json.JSONDecodeError, TypeError):
                pass
 
        # String marker checks (case-insensitive for robustness)
        markers = [
            "<tool_call>",
            "TOOL_CALL:",
            '"tool_calls"',
            '"function_call"',
            "tool_call:",
        ]
        text_lower = text.lower()
        return any(m.lower() in text_lower for m in markers)

    def _extract_tool_calls(self, text: str) -> list[dict]:
        """
        Parse tool call requests from LLM output.
        Handles multiple formats in priority order.
        """
        calls = []
        stripped = text.strip()
 
        # ── Format 1: JSON {"tool_calls": [...]} ─────────────────────
        # ── Format 1: JSON {"tool_calls": [...]} ─────────────────────
        if stripped.startswith('{'):
            try:
                parsed = json.loads(stripped)
                if "tool_calls" in parsed and parsed["tool_calls"]:
                    
                    # 1. Normalize to list if the LLM hallucinated a single dict
                    tc_data = parsed["tool_calls"]
                    if isinstance(tc_data, dict):
                        tc_data = [tc_data]
                    
                    # 2. Iterate safely
                    if isinstance(tc_data, list):
                        for tc in tc_data:
                            # Skip non-dicts
                            if not isinstance(tc, dict):
                                continue

                            # Support {"name":..,"args":..} and {"function":{"name":..,"arguments":..}}
                            if "function" in tc and isinstance(tc["function"], dict):
                                name = tc["function"].get("name", "")
                                raw_args = tc["function"].get("arguments", "{}")
                            else:
                                name = tc.get("name", "")
                                raw_args = tc.get("arguments", tc.get("args", "{}"))

                            # Parse args (may be JSON string or dict) — INSIDE loop
                            if isinstance(raw_args, str):
                                try:
                                    args = json.loads(raw_args)
                                except json.JSONDecodeError:
                                    args = {"raw": raw_args}
                            else:
                                args = raw_args if isinstance(raw_args, dict) else {}

                            # Append INSIDE loop — each tool call appended individually
                            if name:
                                calls.append({"id": tc.get("id", ""), "name": name, "args": args})

                    if calls:
                        return calls
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
 
        # ── Format 2: TOOL_CALL: name {...} ──────────────────────────
        for match in re.finditer(
            r"TOOL_CALL:\s*(\w+)\s*(\{.*?\})", text, re.DOTALL | re.IGNORECASE
        ):
            try:
                calls.append({
                    "name": match.group(1),
                    "args": json.loads(match.group(2)),
                })
            except json.JSONDecodeError:
                pass
        if calls:
            return calls
 
        # ── Format 3: <tool_call>{"name": ..., "arguments": ...}</tool_call>
        for match in re.finditer(
            r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL
        ):
            try:
                data = json.loads(match.group(1))
                args = data.get("arguments", data.get("parameters", data.get("args", {})))
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                calls.append({
                    "name": data.get("name", ""),
                    "args": args,
                })
            except json.JSONDecodeError:
                pass
 
        return calls
    
    def _extract_content_from_response(self, text: str) -> str:
        """
        Extract the human-readable content portion from a possibly
        JSON-wrapped response. If it contains tool calls, return the entire
        JSON envelope so the LLM remembers its own tool calls in the history.
        """
        if not text:
            return ""
        stripped = text.strip()
        if stripped.startswith('{'):
            try:
                parsed = json.loads(stripped)
                if "tool_calls" in parsed:
                    return stripped # Keep JSON envelope so LLM sees its actions
                if "content" in parsed:
                    return str(parsed["content"]) or ""
            except (json.JSONDecodeError, TypeError):
                pass
        return text

    def _get_relevant_patterns(self, input: AgentInput, pattern_key_prefix: str) -> str:
        """Format historical patterns for injection into prompts."""
        patterns = input.accumulated_context.get("patterns", [])
        rag_context = input.accumulated_context.get("_rag_historical_context", "")
 
        # Prefer RAG context if available (richer semantic search results)
        _no_rag_markers = (
            "No historical context available",
            "No historical context for this tenant",
        )
        if rag_context and not any(m in rag_context for m in _no_rag_markers):
            return rag_context
 
        # Fall back to pattern store
        if not patterns:
            return "No historical patterns available yet — this is an early run."
 
        relevant = [p for p in patterns if p.get("key", "").startswith(pattern_key_prefix)]
        if not relevant:
            return f"No patterns for prefix '{pattern_key_prefix}' yet."
 
        # Sort by success_rate if available, show top 5
        relevant.sort(key=lambda p: p.get("success_rate", 0.0), reverse=True)
        return json.dumps(relevant[:5], indent=2, default=str)
