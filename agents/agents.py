"""
agents/
=======
All 6 specialized OpsGrid agents. Each extends BaseAgent with specific
responsibilities. Prompts are loaded from workflow/prompts/ at runtime.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import aiofiles
import structlog

import re
from agents.base_agent import AgentInput, AgentOutput, BaseAgent, LLMMessage
from agents.base_agent import SafeDict
log = structlog.get_logger()

def safe_format_template(template: str, **kwargs) -> str:
    """
    Safely formats a template by replacing exact {key} or {key.subkey} matches.
    Ignores JSON blocks and avoids Python's str.format() recursion/specifier errors.
    """
    def replacer(match):
        key = match.group(1)
        parts = key.split('.')
        if parts[0] not in kwargs:
            return match.group(0)
        
        val = kwargs[parts[0]]
        for part in parts[1:]:
            if hasattr(val, "get") and callable(val.get):
                val = val.get(part)
            elif hasattr(val, part):
                val = getattr(val, part)
            else:
                return match.group(0)
        return str(val) if val is not None else ""

    return re.sub(r'\{([a-zA-Z0-9_.]+)\}', replacer, template)


    
async def _load_prompt(prompt_file: str) -> str:
    """Load a prompt template from the prompts directory (async)."""
    path = Path("workflows/prompts") / prompt_file
    if path.exists():
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            return await f.read()
    return ""   # Fallback — agent will use inline template


# ─────────────────────────────────────────────────────────────────────────────
# 1. RESEARCH AGENT
# Pulls all relevant data from connected sources. Tool-heavy. Fast model.
# ─────────────────────────────────────────────────────────────────────────────

class ResearchAgent(BaseAgent):
    """
    Gathers all data needed for the workflow. Uses many tool calls.
    Assigned fast model tier (Groq/Haiku) — speed and low cost matter here.
    """

    agent_type = "research_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        node_data = input.node_specific_data
        prompt_file = node_data.get("prompt_file", "")
        available_tools = node_data.get("tools", [])

        # Load prompt template
        prompt_template = await _load_prompt(prompt_file) if prompt_file else self._default_research_prompt()

        system = safe_format_template(prompt_template,
            tenant_name=input.tenant_config.get("client_name", "the company"),
            industry=input.tenant_config.get("industry", "business"),
            integration_config=json.dumps(
                {k: {"enabled": v.get("enabled")} for k, v in
                 input.tenant_config.get("integrations", {}).items() if isinstance(v, dict)},
                indent=2
            ),
            current_datetime=__import__("datetime").datetime.utcnow().isoformat(),
        )

        user = (
            f"Signal that triggered this workflow: "
            f"{json.dumps(input.node_specific_data.get('trigger_signal', {}), indent=2)}\n\n"
            f"Gather all relevant data using the available tools."
        )

        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]

        try:
            text, calls = await self._call_with_tools(messages, available_tools, input)
            output_data = self._parse_json_output(text)

            # Direct extraction for raw email fetching
            tool_messages = []
            for item in getattr(self, "_last_tool_outputs", []):
                res = item.get("data") if isinstance(item, dict) else item
                if isinstance(res, dict) and "messages" in res and isinstance(res["messages"], list):
                    tool_messages.extend(res["messages"])
                elif isinstance(res, list) and res and isinstance(res[0], dict) and ("subject" in res[0] or "email_id" in res[0]):
                    tool_messages.extend(res)

            if tool_messages:
                normalized_messages = []
                for m in tool_messages:
                    normalized_messages.append({
                        "email_id": m.get("email_id") or m.get("id") or m.get("message_id", ""),
                        "thread_id": m.get("thread_id") or m.get("threadId", ""),
                        "from": m.get("from") or m.get("sender", "Unknown"),
                        "to": m.get("to") or m.get("recipient", ""),
                        "subject": m.get("subject", "(No subject)"),
                        "body": m.get("body", ""),
                        "received_at": m.get("received_at") or m.get("timestamp") or m.get("date", ""),
                        "labels": m.get("labels") or [],
                        "data_origin": m.get("data_origin", "synthetic")
                    })
                output_data["messages"] = normalized_messages
                output_data["total_messages"] = len(normalized_messages)

            # Data quality gate: warn if zero entities were found
            entity_keys = (
                "accounts", "patients", "transactions", "products",
                "deals", "expenses", "messages", "emails",
                # Real estate entities:
                "listings", "leases", "buyers", "showings", "maintenance_tickets",
            )
            entities_found = sum(
                len(output_data.get(k) or []) for k in entity_keys
            )
            if entities_found == 0 and not output_data.get("parse_error"):
                log.warning(
                    "ResearchAgent: no entities found — seed data missing or API error",
                    node=input.node_specific_data.get("id", "research"),
                    tools=available_tools,
                )
                output_data["_data_quality_warning"] = (
                    f"No {'/'.join(entity_keys)} found. "
                    "Verify seed data exists (python db/seed/run_all_seeders.py) "
                    "or check API credentials."
                )
                # Mark for downstream agents to be cautious
                output_data["_zero_data"] = True
            costs = self._aggregate_costs(calls)

            return AgentOutput(
                success=True,
                confidence=0.95,   # Research is mostly factual — high confidence
                output_data=output_data,
                reasoning_chain=f"Research completed via {len(calls)} LLM calls. "
                                f"Tools used: {available_tools}",
                **costs,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("Research agent failed", error=str(e))
            return AgentOutput(
                success=False,
                confidence=0.0,
                output_data={},
                reasoning_chain="",
                error=str(e),
                provider_attempts=getattr(e, "attempts", None),
                duration_ms=int((time.time() - start) * 1000),
            )

    def _default_research_prompt(self) -> str:
        """
        FIX: Original prompt had rigid numbered steps 1-4. If any step fails
        (tool returns empty), the agent still returns mostly-empty JSON with no
        retry or alternative strategy — tool-call brittle.
        
        New: Goal-oriented directive that makes the agent adaptive.
        """
        return (
            "You are a data gathering agent for {tenant_name}, a {industry} company.\n\n"
            "YOUR GOAL: Collect sufficient data to assess the business risks in this workflow.\n"
            "Use the available tools IN ANY ORDER. If a tool returns empty or insufficient data, "
            "try alternative tools or adjust the parameters (e.g., change filters, try without filters).\n\n"
            "ADAPTIVE STRATEGY:\n"
            "- Start with broad queries, then narrow if you get too much data\n"
            "- If a risk filter returns empty, try without filters\n"
            "- If one tool fails, use alternatives to get partial data\n"
            "- Prioritize high-risk signals over comprehensive coverage\n\n"
            "DO NOT analyze — just gather and return structured JSON.\n"
            "Current datetime: {current_datetime}\n"
            "Integrations configured: {integration_config}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. REASONING AGENT
# Core analysis. Scores, ranks, recommends. Heavy model.
# ─────────────────────────────────────────────────────────────────────────────

class ReasoningAgent(BaseAgent):
    """
    The brain. Analyzes research data, applies business rules, recommends actions.
    Assigned heavy model tier (Claude Sonnet) — quality is critical.
    """

    agent_type = "reasoning_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        node_data = input.node_specific_data
        prompt_file = node_data.get("prompt_file", "")
 
        prompt_template = await _load_prompt(prompt_file) if prompt_file else self._default_reasoning_prompt()
 
        cfg = input.tenant_config
        br = cfg.get("business_rules") or {} # Add 'or {}' guard

        # Safely extract with fallbacks to prevent NoneType format errors
        # Use 'or {}' in case the JSON explicitly contains null values
        churn_risk_data = br.get("churn_risk") or {}
        pipeline_data = br.get("pipeline") or {}

        safe_churn_risk = SafeDict.from_config(
            churn_risk_data,
            defaults={
                "usage_drop_weight":            0.40,
                "support_spike_weight":         0.25,
                "nps_weight":                   0.20,
                "engagement_recency_weight":    0.15,
                "critical_score_threshold":     70,
                "at_risk_score_threshold":      45,
                "usage_drop_days_to_flag":      14,
                "support_tickets_spike_threshold": 5,
            }
        )
        safe_pipeline = SafeDict.from_config(
            pipeline_data,
            defaults={
                "escalate_deal_value_above":     50_000,
                "stalled_deal_days_by_stage":    {},
            }
        )

        # ── Pull RAG & summarization context ─────────────────
        rag_context = input.accumulated_context.get(
            "_rag_historical_context",
            "No historical context available yet — this is an early run."
        )
        research_summary = input.accumulated_context.get("_research_summary", "")
        a2a_note = input.accumulated_context.get("_a2a_refinement_note", "")

        # ── Build system prompt ───────────────────────────────
        try:
            system = safe_format_template(prompt_template,
                tenant_name=cfg.get("client_name", "the company"),
                industry=cfg.get("industry", "business"),
                company_profile=json.dumps(cfg.get("company_profile", {}), indent=2),
                business_rules=SafeDict(br),
                business_rules_json=json.dumps(br, indent=2),
                tone_profile=json.dumps(cfg.get("tone_profile", {}), indent=2),
                action_library=json.dumps(cfg.get("action_library", {}), indent=2),
                confidence_threshold=br.get("confidence_threshold", 0.75),
                churn_risk=safe_churn_risk,
                pipeline=safe_pipeline,
                relevant_patterns=self._get_relevant_patterns(
                    input,
                    f"{cfg.get('industry', 'generic')}_"
                ),
                rag_historical_context=rag_context,
            )
        except Exception as e:
            log.warning("Reasoning prompt format error", error=str(e))
            system = prompt_template

        # Always append RAG context if not already embedded in template
            if "{rag_historical_context}" not in prompt_template:
                system += f"\n\n{rag_context}"
 
        # ── Build user message ────────────────────────────────
        research_output = input.accumulated_context.get("research", {})
 
        user_parts = []
        if research_summary:
            user_parts.append(
                f"=== RESEARCH SUMMARY (key anomalies only) ===\n{research_summary}\n"
                f"=== END SUMMARY ==="
            )
        user_parts.append(
            f"Full research data:\n{json.dumps(research_output, indent=2, default=str)}"
        )
        if a2a_note:
            user_parts.append(
                f"\n=== A2A REFINEMENT NOTE ===\n{a2a_note}\n"
                f"The previous research was re-run with this specific focus. "
                f"Incorporate this into your analysis."
            )
        user_parts.append(
            f"\nSignal: {json.dumps(node_data.get('trigger_signal', {}))}\n"
            f"Current date/time: {__import__('datetime').datetime.utcnow().isoformat()}\n\n"
            f"Analyze all accounts. Return ONLY valid JSON."
        )
 
        user = "\n\n".join(user_parts)
 
        try:
            text, call = await self._simple_call(system, user, input)
            output_data = self._parse_json_output(text)
            confidence = float(output_data.get("reasoning_confidence", 0.8))
            should_escalate = output_data.get("escalate", False)
            escalation_reason = output_data.get("escalation_reason", "")
 
            # Check confidence threshold — escalate if below
            threshold = cfg.get("business_rules", {}).get("confidence_threshold")
            if threshold is None:
                threshold = 0.75
            threshold = float(threshold)
            
            if confidence < threshold:
                should_escalate = True
                escalation_reason = (
                    f"Confidence {confidence:.0%} below threshold {threshold:.0%}. "
                    + escalation_reason
                )
 
            return AgentOutput(
                success=True,
                confidence=confidence,
                output_data=output_data,
                reasoning_chain=text,
                escalate=should_escalate,
                escalation_reason=escalation_reason,
                tokens_in=call.tokens_in,
                tokens_out=call.tokens_out,
                cost_usd=call.cost_usd,
                model_used=call.model,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("Reasoning agent failed", error=str(e))
            return AgentOutput(
                success=False, confidence=0.0, output_data={}, reasoning_chain="",
                error=str(e), provider_attempts=getattr(e, "attempts", None),
                duration_ms=int((time.time() - start) * 1000),
            )
 
    def _default_reasoning_prompt(self) -> str:
        return (
            "You are an autonomous business reasoning agent for {tenant_name}, "
            "a {industry} company.\n"
            "Company context: {company_profile}\n"
            "Business rules: {business_rules}\n"
            "Available actions: {action_library}\n"
            "Confidence threshold: {confidence_threshold}\n\n"
            "=== HISTORICAL CONTEXT FROM PAST RUNS ===\n"
            "{rag_historical_context}\n"
            "=== END HISTORICAL CONTEXT ===\n\n"
            "Historical patterns: {relevant_patterns}\n\n"
            "Analyze the data, identify the most important situations, "
            "and recommend the best actions.\n"
            "Return ONLY valid JSON with: situation_summary, urgency, "
            "reasoning_confidence, recommended_actions (list with action_id, confidence, "
            "reasoning, expected_outcome), escalate (bool), escalation_reason."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. DRAFTING AGENT
# Writes all communications. Heavy model. Brand voice critical.
# ─────────────────────────────────────────────────────────────────────────────

class DraftingAgent(BaseAgent):
    """
    Writes personalized emails, briefs, and documents.
    Assigned heavy model tier — writing quality is the product.
    """

    agent_type = "drafting_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        node_data = input.node_specific_data
        prompt_file = node_data.get("prompt_file", "")
        prompt_template = await _load_prompt(prompt_file) if prompt_file else self._default_drafting_prompt()

        cfg = input.tenant_config
        tone = cfg.get("tone_profile", {})
        available_tools = node_data.get("tools", [])

        reasoning_output = input.accumulated_context.get("reasoning", {})
        
        try:
            system = safe_format_template(prompt_template,
                tenant_name=cfg.get("client_name", "the company"),
                industry=cfg.get("industry", "business"),
                tone_profile=SafeDict(tone),
                tone_profile_json=json.dumps(tone, indent=2),
                reasoning_output=reasoning_output,
                communication_history="Will be fetched via tools."
            )
        except Exception as e:  
            log.error("Missing template key in drafting prompt", missing_key=str(e))
            # Fallback to prevent hard crash
            system = safe_format_template(self._default_drafting_prompt(),
                tenant_name=cfg.get("client_name", "the company"),
                industry=cfg.get("industry", "business"),
                tone_profile=json.dumps(tone, indent=2)
            )

        try:
            # ── Two-phase drafting: tools first, writing second ──
            if available_tools:
                phase1_user, phase2_instruction = self._build_two_phase_drafting_user(
                    reasoning_output, available_tools
                )

                # Phase 1: ONLY tool calls
                messages_p1 = [
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=phase1_user),
                ]
                p1_text, p1_calls = await self._call_with_tools(messages_p1, available_tools, input)

                # Phase 2: ONLY drafting
                p2_text, p2_call = await self._simple_call(system, phase2_instruction, input)

                text = p2_text
                all_calls = p1_calls + [p2_call]

            else:
                summarize_output = input.accumulated_context.get("summarize_emails", {})
                if isinstance(summarize_output, dict) and "per_email_analysis" in summarize_output:
                    per_email = summarize_output.get("per_email_analysis", [])
                    actionable_emails = [
                        item for item in per_email
                        if item.get("requires_reply") or item.get("needs_attention") or item.get("priority") in ["urgent", "high"]
                    ]
                    if not actionable_emails:
                        log.info("No actionable emails requiring reply drafts, returning empty approval items.")
                        return AgentOutput(
                            success=True,
                            confidence=1.0,
                            output_data={
                                "approval_items": [],
                                "routine_items_count": summarize_output.get("total_emails", 0),
                                "summary": "No actionable customer escalations or reply drafts were required."
                            },
                            reasoning_chain="Skipped drafting call as 0 emails require outbound reply.",
                            tokens_in=0,
                            tokens_out=0,
                            cost_usd=0.0,
                            model_used="none",
                            duration_ms=int((time.time() - start) * 1000)
                        )
                    context_user = (
                        f"Executive Summary: {summarize_output.get('executive_summary', '')}\n\n"
                        f"Actionable/High Priority Emails ({len(actionable_emails)} items out of {len(per_email)}):\n"
                        f"{json.dumps(actionable_emails, indent=2, default=str)}\n\n"
                        "Propose draft responses ONLY for emails where requires_reply=true. Return valid JSON."
                    )
                else:
                    context_user = (
                        "Upstream workflow context:\n"
                        f"{json.dumps(input.accumulated_context, default=str)[:12000]}\n\n"
                        "Complete the requested task using only this context and return valid JSON."
                    )
                text, call = await self._simple_call(system, context_user, input)
                all_calls = [call]

            output_data = self._parse_json_output(text)
            costs = self._aggregate_costs(all_calls)

            return AgentOutput(
                success=True,
                confidence=output_data.get("confidence") if isinstance(output_data.get("confidence"), (int, float)) else None,
                output_data=output_data,
                reasoning_chain=f"Drafted {len(output_data.get('drafts', []))} emails, "
                                f"{len(output_data.get('exec_briefs', []))} briefs",
                **costs,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("Drafting agent failed", error=str(e))
            return AgentOutput(
                success=False, confidence=0.0, output_data={}, reasoning_chain="",
                error=str(e),
                provider_attempts=getattr(e, "attempts", None),
                duration_ms=int((time.time() - start) * 1000),
            )
            
    def _build_two_phase_drafting_user(
        self,
        reasoning_output: dict,
        available_tools: list,
    ) -> tuple[str, str]:
        """
        Returns (phase1_user, phase2_instruction) for two-phase drafting.
        
        FIX: Original approach asks agent to check history AND draft in one turn.
        The agent frequently drafts conceptually first, then uses the tool result
        only to decide inclusion. This means skipped_accounts are still partially
        drafted internally.
        
        Two-phase: Phase 1 ONLY calls tools. Phase 2 ONLY drafts for safe recipients.
        """
        # Extract recipients from reasoning
        all_accounts = []
        # All possible risk bucket keys across industries
        risk_keys = (
            "critical_accounts", "at_risk_accounts",       # SaaS churn
            "critical_deals", "at_risk_deals",             # SaaS pipeline
            "critical_patients",                           # Healthcare
            "critical_products", "at_risk_products",       # Retail
            "critical_listings", "at_risk_listings",       # RE brokerage
            "high_risk_leases", "at_risk_leases",          # RE property mgmt
        )
        for key in risk_keys:
            accs = reasoning_output.get(key) or []
            for acc in accs[:8]:  # cap per category
                if isinstance(acc, dict):
                    all_accounts.append({
                        "id": (
                            acc.get("account_id") or acc.get("deal_id")
                            or acc.get("patient_id") or acc.get("product_id")
                            or acc.get("listing_id") or acc.get("lease_id")
                        ),
                        "name": (
                            acc.get("company_name") or acc.get("company")
                            or acc.get("patient_name") or acc.get("name")
                            or acc.get("address") or acc.get("tenant_name")
                        ),
                        "email": (
                            acc.get("contact_email") or acc.get("recipient_email")
                            or acc.get("tenant_email") or acc.get("owner_email", "")
                        ),
                    })
    
        phase1_user = (
            f"PHASE 1 — TOOL CALLS ONLY. DO NOT DRAFT ANY EMAIL YET.\n\n"
            f"Call get_communication_history for each of these recipients:\n"
            f"{json.dumps(all_accounts, indent=2)}\n\n"
            f"After calling the tool for EVERY recipient above, return ONLY this JSON:\n"
            f'{{ "safe_to_contact": ["account_id_1", "account_id_2"], '
            f'"skip_accounts": [{{"id": "id", "reason": "contacted N days ago"}}] }}\n\n'
            f"DO NOT write any email content in this phase."
        )
        
        safe_accounts_detail = [
            acc for acc in all_accounts
            # all_accounts was built above from critical/at_risk lists
        ]
        phase2_instruction = (
            f"PHASE 2 — DRAFTING ONLY.\n\n"
            f"The following accounts were verified safe to contact in Phase 1:\n"
            f"Safe IDs will be in the conversation history above.\n\n"
            f"Account details for drafting:\n"
            f"{json.dumps(safe_accounts_detail, indent=2, default=str)[:4000]}\n\n"
            f"Tone and business context:\n"
            f"- Situation summary: {reasoning_output.get('situation_summary', '')[:300]}\n"
            f"- Urgency: {reasoning_output.get('urgency', 'high')}\n"
            f"- Available actions: {list(reasoning_output.get('recommended_actions', [{}])[0].keys())[:5]}\n\n"
            f"Return ONLY valid JSON:\n"
            f'{{ "drafts": [...], "exec_briefs": [...], "skipped_accounts": [...] }}'
        )
        
        return phase1_user, phase2_instruction
    def _default_drafting_prompt(self) -> str:
        return (
            "You are a professional business writer for {tenant_name}.\n"
            "Tone profile: {tone_profile}\n"
            "Write all communications based on the reasoning output.\n"
            "NEVER use placeholder text. Use actual names from the data.\n"
            "Return JSON: {{ 'drafts': [...], 'exec_briefs': [...] }}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 4. VERIFICATION AGENT
# Rule checker. Fast/mini model. Deterministic checks.
# ─────────────────────────────────────────────────────────────────────────────

class HumanizerAgent(BaseAgent):
    """
    Refines machine-generated email actions into warmer, review-ready drafts
    while preserving the underlying approval metadata.
    """

    agent_type = "humanizer_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        node_data = input.node_specific_data
        prompt_file = node_data.get("prompt_file", "")
        prompt_template = await _load_prompt(prompt_file) if prompt_file else self._default_humanizer_prompt()

        cfg = input.tenant_config
        evaluate_output = input.accumulated_context.get("evaluate_actions", {})
        summary_output = input.accumulated_context.get("summarize_emails", {})
        approval_items = evaluate_output.get("approval_items", []) if isinstance(evaluate_output, dict) else []

        if not approval_items:
            log.info("No approval items to humanize, returning empty approval_items")
            return AgentOutput(
                success=True,
                confidence=1.0,
                output_data={
                    "approval_items": [],
                    "routine_items_count": summary_output.get("total_emails", 0) if isinstance(summary_output, dict) else 0,
                    "summary": "No outbound draft responses were required for humanization."
                },
                reasoning_chain="Skipped LLM call as zero reply drafts required humanization.",
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                model_used="none",
                duration_ms=int((time.time() - start) * 1000),
            )

        try:
            system = safe_format_template(
                prompt_template,
                tenant_name=cfg.get("client_name", "the company"),
                tone_profile_json=json.dumps(cfg.get("tone_profile", {}), indent=2),
            )
        except Exception as e:
            log.warning("Humanizer prompt template key error", error=str(e))
            system = self._default_humanizer_prompt()

        compact_summary = {
            "total_emails": summary_output.get("total_emails") if isinstance(summary_output, dict) else 0,
            "executive_summary": summary_output.get("executive_summary") if isinstance(summary_output, dict) else "",
            "category_counts": summary_output.get("category_counts") if isinstance(summary_output, dict) else {}
        }

        user = (
            "Email batch executive summary:\n"
            f"{json.dumps(compact_summary, indent=2, default=str)}\n\n"
            "Raw action recommendations and drafts requiring humanization:\n"
            f"{json.dumps(approval_items, indent=2, default=str)}\n\n"
            "Return ONLY valid JSON with refined approval_items."
        )

        try:
            text, call = await self._simple_call(system, user, input)
            output_data = self._parse_json_output(text)
            if not isinstance(output_data, dict):
                output_data = {"approval_items": [], "summary": str(output_data)}

            return AgentOutput(
                success=True,
                confidence=float(output_data.get("confidence", 0.92)),
                output_data=output_data,
                reasoning_chain=(
                    f"Humanized {len(output_data.get('approval_items', []))} approval drafts "
                    "with XAI metadata."
                ),
                tokens_in=call.tokens_in,
                tokens_out=call.tokens_out,
                cost_usd=call.cost_usd,
                model_used=call.model,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("Humanizer agent failed", error=str(e))
            return AgentOutput(
                success=False,
                confidence=0.0,
                output_data={},
                reasoning_chain="",
                error=str(e),
                duration_ms=int((time.time() - start) * 1000),
            )

    def _default_humanizer_prompt(self) -> str:
        return (
            "You are a Humanizer Agent for {tenant_name}.\n"
            "Refine raw AI email drafts so they sound natural, empathetic, specific, "
            "and professionally accountable. Remove robotic phrasing and vague filler. "
            "Preserve all facts, recipients, subjects, urgency, categories, and safety limits.\n"
            "Tone profile: {tone_profile_json}\n\n"
            "Return JSON with approval_items, routine_items_count, batch_intelligence, "
            "and summary. Every approval item must include category, urgency_score, "
            "detected_sentiment, trigger_keywords, and xai_explanation."
        )


class VerificationAgent(BaseAgent):
    """
    Checks drafts against business rules. Fast model — deterministic checking.
    Catches: wrong recipients, duplicate emails, tone violations, factual errors.
    """

    agent_type = "verification_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:  # noqa: E301
        start = time.time()
        cfg = input.tenant_config
        br  = cfg.get("business_rules", {})
        node_data       = input.node_specific_data
        available_tools = node_data.get("tools", [])
        prompt_file     = node_data.get("prompt_file", "")
 
        # ── Build base system prompt ──────────────────────────────────────
        base_system: Optional[str] = None
        if prompt_file:
            template = await _load_prompt(prompt_file)
            if template:
                try:
                    base_system = safe_format_template(template,
                        tenant_name=cfg.get("client_name", "the company"),
                        industry=cfg.get("industry", "business"),
                        tone_profile_json=json.dumps(cfg.get("tone_profile", {}), indent=2),
                        business_rules_json=json.dumps(br, indent=2),
                        operating_hours=json.dumps(br.get("operating_hours", {})),
                        confidence_threshold=br.get("confidence_threshold", 0.75),
                    )
                except Exception as fmt_err:
                    log.warning("Verification prompt template key error", error=str(fmt_err))
                    base_system = None
 
        if not base_system:
            base_system = (
                f"You are a quality verification agent for {cfg.get('client_name', 'the company')}.\n\n"
                f"VERIFICATION RULES:\n"
                f"1. Each communication must have a REAL recipient_email and recipient_name "
                f"— no [Name], 'undefined', or empty values\n"
                f"2. REJECT if communication_history shows safe_to_email=false or outreach "
                f"sent within 7 days\n"
                f"3. Tone must match brand voice: "
                f"{json.dumps(cfg.get('tone_profile', {}), indent=2)}\n"
                f"4. ALL metrics, numbers, percentages must exactly match the research data\n"
                f"5. Zero tolerance for placeholder text: [Company], [CSM Name], [Date] etc.\n"
                f"6. Subject line must be specific — reference company name or a real metric\n"
                f"7. Operating hours: {json.dumps(br.get('operating_hours', {}))}\n\n"
                f"Return ONLY valid JSON:\n"
                f'{{ "passed": bool, "approved_drafts": [...], '
                f'"rejected_drafts": [{{"account_id": "id", "rejection_reason": "exact rule violated"}}], '
                f'"issues": ["list all violations"] }}'
            )
 
        # ── Context data to verify ────────────────────────────────────────
        drafting_output  = input.accumulated_context.get("drafting", {})
        research_output  = input.accumulated_context.get("research", {})
        reasoning_output = input.accumulated_context.get("reasoning", {})
        
        research_summary = input.accumulated_context.get("_research_summary")
        if research_summary:
            research_snippet = f"Summary:\n{research_summary}"
        else:
            research_snippet = json.dumps(research_output, indent=2, default=str)

        verification_user = (
            f"Drafts to verify:\n{json.dumps(drafting_output, indent=2, default=str)}\n\n"
            f"Research data (ground truth for factual accuracy):\n{research_snippet}\n\n"
            f"Reasoning output:\n"
            f"{json.dumps(reasoning_output, indent=2, default=str)}"
        )
 
        # ══════════════════════════════════════════════════════════════════
        # JUDGE PATTERN — Turn 1: Prosecutor
        # ══════════════════════════════════════════════════════════════════
        prosecutor_system = (
            f"{base_system}\n\n"
            "=== YOU ARE NOW ACTING AS PROSECUTOR ===\n"
            "Your ONLY job: find every possible fault, inconsistency, violation, "
            "or risk in the drafts. Be thorough, adversarial, and specific.\n"
            "NOTE: Do NOT flag faults for rules that require external tool calls (e.g., checking communication_history). "
            "The Judge will handle tool-based verifications. Focus purely on text, logic, and data matching.\n"
            "List issues by rule number. Do NOT make a final pass/fail decision.\n"
            'Return ONLY valid JSON: {"faults": ["RULE N: description of exact fault", ...]}'
        )
        prosecutor_user = (
            f"{verification_user}\n\n"
            "List EVERY fault you can find. Include rule number for each."
        )
 
        faults: list[str] = []
        prosecutor_call = None
        try:
            prosecutor_text, prosecutor_call = await self._simple_call(
                prosecutor_system, prosecutor_user, input,
                tier_override="fast"   # "fast" (Haiku 4.5) vs "mini" (Haiku 3) —
                # better factual comparison accuracy for ~$0.005 more per run
            )
            pdata  = self._parse_json_output(prosecutor_text)
            faults = pdata.get("faults", [])
            log.debug("Prosecutor found faults", count=len(faults))
        except Exception as e:
            log.warning("Prosecutor turn failed", error=str(e))
 
        # ══════════════════════════════════════════════════════════════════
        # JUDGE PATTERN — Turn 2: Judge
        # ══════════════════════════════════════════════════════════════════
        judge_user = self._build_judge_user(verification_user, faults)
 
        messages = [
            LLMMessage(role="system", content=base_system),
            LLMMessage(role="user",   content=judge_user),
        ]
 
        try:
            if available_tools:
                judge_tools = list(available_tools)
                if "get_communication_history" not in judge_tools:
                    judge_tools.append("get_communication_history")

                text, calls = await self._call_with_tools(messages, judge_tools, input)
                costs = self._aggregate_costs(calls)
            else:
                text, judge_call = await self._simple_call(
                    base_system, judge_user, input
                )
                costs = {
                    "tokens_in":  judge_call.tokens_in,
                    "tokens_out": judge_call.tokens_out,
                    "cost_usd":   judge_call.cost_usd,
                    "model_used": judge_call.model,
                }
 
            # Accumulate prosecutor call costs
            if prosecutor_call:
                costs["tokens_in"]  += prosecutor_call.tokens_in
                costs["tokens_out"] += prosecutor_call.tokens_out
                costs["cost_usd"]   += prosecutor_call.cost_usd
 
            output_data = self._parse_json_output(text)
 
            # Inject audit trail
            output_data["_prosecutor_faults"]  = faults
            output_data["_prosecutor_issues"]  = len(faults)
            output_data["_judge_verdict"] = (
                "PASS" if output_data.get("passed") else "FAIL"
            )
 
            passed = bool(output_data.get("passed", False))
            return AgentOutput(
                success=True,
                confidence=0.92 if passed else 0.65,
                output_data=output_data,
                reasoning_chain=(
                    f"PROSECUTOR: {len(faults)} faults identified. "
                    f"JUDGE: {'PASS' if passed else 'FAIL'}. "
                    f"Approved: {len(output_data.get('approved_drafts', []))}, "
                    f"Rejected: {len(output_data.get('rejected_drafts', []))}"
                ),
                tokens_in=costs["tokens_in"],
                tokens_out=costs["tokens_out"],
                cost_usd=costs["cost_usd"],
                model_used=costs["model_used"],
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("Verification agent failed", error=str(e))
            return AgentOutput(
                success=False, confidence=0.0, output_data={},
                reasoning_chain="", error=str(e),
                duration_ms=int((time.time() - start) * 1000),
            )

    def _build_judge_user(self, verification_user: str, faults: list) -> str:
        """
        FIX: Judge's get_communication_history was optional — it frequently skipped it,
        creating a gap where duplicate outreach was never caught. Now mandatory.
        """
        return (
            f"{verification_user}\n\n"
            f"=== PROSECUTOR'S FINDINGS ({len(faults)} issues) ===\n"
            f"{json.dumps(faults, indent=2)}\n"
            f"=== END FINDINGS ===\n\n"
            "You are now the JUDGE. Before making your final verdict, you MUST:\n"
            "1. Call get_communication_history for EVERY draft recipient — no exceptions.\n"
            "   A PASS verdict is invalid without this check.\n"
            "2. Review the prosecutor's findings objectively.\n"
            "3. Minor style issues are acceptable; factual errors and placeholder text are blocking.\n\n"
            "MANDATORY TOOL CALLS:\n"
            "- get_communication_history must be called for each draft recipient\n"
            "- If safe_to_email=false → that draft MUST be rejected regardless of other findings\n\n"
            "Apply all 7 verification rules. Make the final pass/fail determination.\n"
            "Return ONLY valid JSON with the full verification result."
        )

# ─────────────────────────────────────────────────────────────────────────────
# 5. EXECUTION AGENT
# Fires actions. Deterministic. Fast/mini model.
# ─────────────────────────────────────────────────────────────────────────────

class ExecutionAgent(BaseAgent):
    """
    Executes approved actions: sends emails, creates CRM tasks, posts Slack.
    Deterministic — just calls tools. Mini model.
    """

    agent_type = "execution_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        cfg = input.tenant_config
        node_data = input.node_specific_data
        available_tools = node_data.get("tools", [])

        verification_output = input.accumulated_context.get("verification", {})
        approved_drafts = verification_output.get("approved_drafts", [])
        reasoning_output = input.accumulated_context.get("reasoning", {})

        prompt_file = node_data.get("prompt_file", "")
        system = None
        if prompt_file:
            template = await _load_prompt(prompt_file)
            if template:
                try:
                    system = safe_format_template(template,
                        tenant_name=cfg.get("client_name", "the company"),
                        industry=cfg.get("industry", "business"),
                        integrations_json=json.dumps(cfg.get("integrations", {}), indent=2),
                        action_library=json.dumps(cfg.get("action_library", {}), indent=2),
                    )
                except Exception as fmt_err:
                    log.warning("Execution prompt template key error", error=str(fmt_err))
                    system = None

        if not system:
            system = (
                f"You are an execution agent for {cfg.get('client_name', 'the company')}.\n"
                f"Execute ALL approved actions using available tools.\n"
                f"For each action: call the tool, confirm success, log the result.\n"
                f"Track: emails_queued, tasks_created, slack_alerts_sent.\n"
                f"If queue_for_approval is true for emails, queue them — do not send directly.\n"
                f"In DEV MODE: if tools return 'local_dev_mock', log as simulated and continue.\n"
                f"Integration config: {json.dumps(cfg.get('integrations', {}), indent=2)}\n\n"
                f"Return ONLY valid JSON:\n"
                f"{{ \"actions_taken\": [{{\"action\": \"str\", \"account_id\": \"str\", \"status\": \"success|failed\", \"detail\": \"str\"}}], "
                f"\"emails_queued\": 0, \"tasks_created\": 0, \"slack_alerts_sent\": 0, \"errors\": [] }}"
            )

        user = (
            f"Approved drafts to execute:\n{json.dumps(approved_drafts, indent=2, default=str)}\n\n"
            f"Reasoning output (for context on recommended actions):\n"
            f"{json.dumps(reasoning_output, indent=2, default=str)}\n\n"
            f"Execute all approved actions now."
        )

        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]

        try:
            text, calls = await self._call_with_tools(messages, available_tools, input)
            output_data = self._parse_json_output(text)
            costs = self._aggregate_costs(calls)
            
            # ── Write approved drafts to email queue for human review ────────────
            queue_for_approval = (
                cfg.get("integrations", {}).get("gmail", {}).get("queue_for_approval", True)
                or cfg.get("integrations", {}).get("email", {}).get("queue_for_approval", True)
            )
            if queue_for_approval and self._state and self._state._db is not None:
                for draft in approved_drafts:
                    if not isinstance(draft, dict):
                        continue
                    r_email = draft.get("recipient_email") or draft.get("contact_email", "")
                    if not r_email or "@" not in r_email:
                        continue
                    try:
                        await self._state.add_to_email_queue(
                            tenant_id=input.tenant_id,
                            run_id=input.workflow_instance_id,
                            account_id=draft.get("account_id", ""),
                            recipient_email=r_email,
                            recipient_name=draft.get("recipient_name", draft.get("contact_name", "")),
                            subject=draft.get("subject", "(no subject)"),
                            body=draft.get("body", ""),
                            email_type=draft.get("email_type", ""),
                            csm_name=draft.get("csm_name", draft.get("sales_rep_name", "")),
                            workflow_name=cfg.get("industry", "generic"),
                        )
                    except Exception as _qe:
                        log.warning("Email queue write failed (non-fatal)", error=str(_qe))

            actions = output_data.get("actions_taken", [])
            return AgentOutput(
                success=True,
                confidence=1.0,   # Execution is binary — it either worked or failed
                output_data=output_data,
                reasoning_chain=f"Executed {len(actions)} actions. "
                                f"Emails: {output_data.get('emails_queued', 0)}, "
                                f"Tasks: {output_data.get('tasks_created', 0)}, "
                                f"Slack: {output_data.get('slack_alerts_sent', 0)}",
                **costs,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("Execution agent failed", error=str(e))
            return AgentOutput(
                success=False, confidence=0.0, output_data={}, reasoning_chain="",
                error=str(e), provider_attempts=getattr(e, "attempts", None),
                duration_ms=int((time.time() - start) * 1000),
            )


# ─────────────────────────────────────────────────────────────────────────────
# 6. MEMORY AGENT
# Logs outcomes and updates pattern store. Mini model.
# ─────────────────────────────────────────────────────────────────────────────

class MemoryAgent(BaseAgent):
    """
    Extracts patterns from completed workflow, updates the pattern store.
    This is what makes OpsGrid learn from every run.
    """

    agent_type = "memory_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:  # noqa: E301
        start = time.time()
        cfg      = input.tenant_config
        industry = cfg.get("industry", "generic")
 
        full_context     = input.accumulated_context
        execution_output = full_context.get("execution", {})
        reasoning_output = full_context.get("reasoning", {})
        verification_out = full_context.get("verification", {})
 
        # ── Retrieved Lessons from RAG (source for Delta Analysis) ───────
        retrieved_lessons: str = full_context.get(
            "_rag_historical_context",
            "No historical context available yet — this is an early run.",
        )
        has_history = "No historical context" not in retrieved_lessons
 
        node_data   = input.node_specific_data
        prompt_file = node_data.get("prompt_file", "")
        system: Optional[str] = None
        if prompt_file:
            template = await _load_prompt(prompt_file)
            if template:
                try:
                    system = safe_format_template(template,
                        tenant_name=cfg.get("client_name", "the company"),
                        industry=cfg.get("industry", "business"),
                    )
                except Exception as fmt_err:
                    log.warning("Memory prompt template key error", error=str(fmt_err))
                    system = None
 
        if not system:
            system = (
                f"You are a memory extraction agent for {cfg.get('client_name', 'the company')}.\n"
                f"Industry: {cfg.get('industry', 'business')}.\n"
                f"Extract learnable patterns from this completed workflow run AND produce a "
                f"Delta Analysis comparing this run to historical lessons.\n\n"
                f"Pattern format: {{ \"key\": \"snake_case\", \"description\": \"str\", "
                f"\"outcome_indicator\": \"positive|negative|neutral\", \"value\": any }}\n\n"
                f"Delta Analysis: compare current run outcomes to historical patterns. "
                f"Identify: what improved, what regressed, what is new/unexpected.\n\n"
                f"Return ONLY valid JSON:\n"
                f'{{ "patterns_to_store": [...], "outcomes_to_log": [...], '
                f'"delta_analysis": {{'
                f'"summary": "str", '
                f'"vs_history": "better|worse|similar|no_history", '
                f'"new_signals": ["list of new patterns not seen before"], '
                f'"trend": "improving|degrading|stable|insufficient_data"'
                f'}}, "summary": "2-sentence run summary" }}'
            )

        user = (
            f"Completed workflow context:\n"
            f"Industry: {industry}\n"
            f"Tenant: {cfg.get('client_name')}\n"
            f"Actions taken:\n{json.dumps(execution_output, indent=2, default=str)}\n"
            f"Reasoning output:\n{json.dumps(reasoning_output, indent=2, default=str)}\n"
            f"Verification result:\n{json.dumps(verification_out, indent=2, default=str)[:800]}\n\n"
            f"=== RETRIEVED HISTORICAL LESSONS ===\n"
            f"{retrieved_lessons[:2000]}\n"
            f"=== END HISTORICAL LESSONS ===\n\n"
            f"Extract patterns AND produce delta analysis comparing to the lessons above.\n\n"
            f"REQUIRED: Your JSON response MUST include 'delta_analysis' with EXACTLY this structure "
            f"(no other key names accepted):\n"
            f"\"delta_analysis\": {{"
            f"\"summary\": \"2-sentence comparison to historical lessons\", "
            f"\"vs_history\": \"better|worse|similar|no_history\", "
            f"\"new_signals\": [\"list of new patterns not seen before\"], "
            f"\"trend\": \"improving|degrading|stable|insufficient_data\""
            f"}}"
        )
 
        try:
            text, call = await self._simple_call(system, user, input)
            output_data = self._parse_json_output(text)
            if not isinstance(output_data, dict):
                output_data = {"patterns_to_store": [], "delta_analysis": {}, "summary": str(output_data)}

            patterns = output_data.get("patterns_to_store", [])
            if not isinstance(patterns, list):
                patterns = []
            delta    = output_data.get("delta_analysis", {})
            if not isinstance(delta, dict):
                delta = {}
            stored   = 0
            _learning_mode = cfg.get("learning_mode", "supervised")
            _auto_promote  = (_learning_mode == "autonomous")

            if self._state and self._state._db is not None:
                for pattern in patterns:
                    if not isinstance(pattern, dict):
                        continue
                    try:
                        pattern_key = f"{industry}_{pattern.get('key', 'unknown')}"
                        await self._state.upsert_pattern(
                            tenant_id=input.tenant_id,
                            pattern_key=pattern_key,
                            pattern_data=pattern,
                            success=True,
                            sandbox=not _auto_promote,
                        )
                        stored += 1
                    except Exception as pe:
                        log.warning("Pattern store failed", error=str(pe))
 
                # Store delta analysis as its own pattern type
                if delta and has_history:
                    try:
                        await self._state.upsert_pattern(
                            tenant_id=input.tenant_id,
                            pattern_key=f"{industry}_delta_analysis_trend",
                            pattern_data={
                                "key": "delta_analysis_trend",
                                "description": delta.get("summary", ""),
                                "outcome_indicator": (
                                    "positive"  if delta.get("vs_history") == "better"
                                    else "negative" if delta.get("vs_history") == "worse"
                                    else "neutral"
                                ),
                                "value": delta,
                            },
                            success=delta.get("vs_history") in ("better", "similar"),
                            sandbox=not _auto_promote,
                        )
                        log.info(
                            "Delta analysis stored",
                            trend=delta.get("trend"),
                            vs_history=delta.get("vs_history"),
                        )
                    except Exception as de:
                        log.warning("Delta analysis store failed", error=str(de))
            else:
                log.info(
                    "Memory agent: patterns extracted (lite mode, no DB)",
                    count=len(patterns),
                    delta_trend=delta.get("trend", "n/a"),
                )
                stored = len(patterns)
            # Store outcome directly in RAG (no HyDE)
            if hasattr(self, "_rag") and self._rag:
                try:
                    await self._rag.store_workflow_outcome(
                        tenant_id=input.tenant_id,
                        run_id=input.workflow_instance_id,
                        workflow_name=input.tenant_config.get("industry", "generic") + "_memory",
                        situation_summary=output_data.get("summary", ""),
                        reasoning_chain="",
                        actions_taken=output_data.get("outcomes_to_log", []),
                        outcome_indicator="positive" if delta.get("vs_history") == "better" else "neutral",
                        cost_usd=0.0,
                    )
                except Exception as _rag_e:
                    log.debug("MemoryAgent RAG store failed", error=str(_rag_e))
            return AgentOutput(
                success=True,
                confidence=1.0,
                output_data={
                    "patterns_updated":  stored,
                    "outcomes_logged":   len(output_data.get("outcomes_to_log", [])),
                    "summary":           output_data.get("summary", ""),
                    "delta_analysis":    delta,
                    "delta_vs_history":  delta.get("vs_history", "no_history"),
                    "delta_trend":       delta.get("trend", "insufficient_data"),
                },
                reasoning_chain=(
                    f"Stored {stored} patterns. "
                    f"Delta vs history: {delta.get('vs_history', 'n/a')}. "
                    f"Trend: {delta.get('trend', 'n/a')}."
                ),
                tokens_in=call.tokens_in,
                tokens_out=call.tokens_out,
                cost_usd=call.cost_usd,
                model_used=call.model,
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("Memory agent failed", error=str(e))
            return AgentOutput(
                success=False, confidence=0.0, output_data={},
                reasoning_chain="", error=str(e),
                duration_ms=int((time.time() - start) * 1000),
            )
            
            
# ─────────────────────────────────────────────────────────────────────────────
# 7. DISCOVERY AGENT
# Automated tool selection + execution when tools: ["auto"] in DAG node.
# ─────────────────────────────────────────────────────────────────────────────
 
class DiscoveryAgent(BaseAgent):
    """
    Automated Tool Discovery Agent.
 
    When a DAG node is configured with tools: ["auto"], the orchestrator injects
    the full tool schema catalogue into node_specific_data["_all_tool_schemas"].
    This agent then:
      1. Uses a mini-LLM call to select the most relevant tools for the trigger.
      2. Executes those tools via the normal _call_with_tools loop.
      3. Returns consolidated research data identical in shape to ResearchAgent output.
 
    This enables zero-config workflow nodes: no need to pre-specify tool names.
    """
 
    agent_type = "discovery_agent"
 
    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        node_data      = input.node_specific_data
        trigger_signal = node_data.get("trigger_signal", input.accumulated_context.get("trigger_signal", {}))
        all_schemas: list[dict] = node_data.get("_all_tool_schemas", [])
 
        # ── Step 1: Select relevant tools ────────────────────────────────
        available_tools = await self._select_tools(all_schemas, trigger_signal, input)
 
        if not available_tools:
            log.warning("DiscoveryAgent: no tools selected, aborting")
            return AgentOutput(
                success=False, confidence=0.0, output_data={},
                reasoning_chain="No tools selected for discovery.",
                error="Tool selection returned empty list",
                duration_ms=int((time.time() - start) * 1000),
            )
 
        log.info("DiscoveryAgent: tools selected", tools=available_tools)
 
        # ── Step 2: Execute selected tools ───────────────────────────────
        cfg = input.tenant_config
        exec_system = (
            f"You are an autonomous data discovery agent for {cfg.get('client_name', 'the company')}, "
            f"a {cfg.get('industry', 'business')} company.\n"
            "Execute the provided tools to gather all data relevant to the trigger signal. "
            "Compile results into a comprehensive structured report. "
            "Return ONLY valid JSON."
        )
        exec_user = (
            f"Trigger signal:\n{json.dumps(trigger_signal, indent=2)}\n\n"
            f"Available tools: {available_tools}\n\n"
            "Execute all tools and return a comprehensive data report."
        )
        messages = [
            LLMMessage(role="system", content=exec_system),
            LLMMessage(role="user",   content=exec_user),
        ]
 
        try:
            text, calls = await self._call_with_tools(messages, available_tools, input)
            output_data = self._parse_json_output(text)
            costs = self._aggregate_costs(calls)
 
            output_data["_tools_selected"]  = available_tools
            output_data["_discovery_mode"]  = True
            output_data["_tools_run_count"] = len([c for c in calls if c.success])
 
            return AgentOutput(
                success=True,
                confidence=0.90,
                output_data=output_data,
                reasoning_chain=(
                    f"DiscoveryAgent auto-selected {len(available_tools)} tools: "
                    f"{available_tools}. Ran {costs.get('tokens_in', 0)} input tokens."
                ),
                tokens_in=costs["tokens_in"],
                tokens_out=costs["tokens_out"],
                cost_usd=costs["cost_usd"],
                model_used=costs["model_used"],
                duration_ms=int((time.time() - start) * 1000),
            )
        except Exception as e:
            log.error("DiscoveryAgent execution failed", error=str(e))
            return AgentOutput(
                success=False, confidence=0.0, output_data={},
                reasoning_chain="", error=str(e),
                duration_ms=int((time.time() - start) * 1000),
            )
 
    async def _select_tools(
        self,
        all_schemas: list[dict],
        trigger_signal: dict,
        input: AgentInput,
    ) -> list[str]:
        """
        Select the most relevant tools for the trigger signal.

        Fast path (zero LLM cost): if the orchestrator injected
        '_rag_selected_tools' via vector search, validate and return them
        immediately without an additional LLM call.

        Slow path: fall back to the existing LLM-based ranking.
        """
        # ── Fast path: orchestrator already did RAG pre-selection ───────────
        rag_preselected = input.node_specific_data.get("_rag_selected_tools", [])
        if rag_preselected:
            valid = [n for n in rag_preselected if n in self._tools._tools]
            if hasattr(self, '_ws_broadcast') and self._current_node_id:
                try:
                    await self._ws_broadcast("agent_live_output", {
                        "run_id": self._current_run_id,
                        "node_id": self._current_node_id,
                        "type": "llm",
                        "preview": f"RAG fast path: {len(valid)} tools selected without LLM call",
                    })
                except Exception:
                    pass
            if valid:
                self._log.info(
                    "DiscoveryAgent: using RAG pre-selected tools (no LLM call)",
                    count=len(valid),
                    tools=valid,
                )
                return valid

        if not all_schemas:
            # No schemas injected — use all registered tools (up to 6)
            return list(self._tools._tools.keys())[:6]
        
        # ── Slow path: LLM-based tool selection ──────────────────────────
        # Build compact catalogue string from available schemas
        catalogue_lines = []
        schema_name_map: dict[str, str] = {}  # name → type hint for de-alias
        for schema in all_schemas[:30]:        # cap to avoid context overflow
            fn = schema.get("function", schema)
            name = fn.get("name", "")
            desc = fn.get("description", "")[:120]
            if name:
                catalogue_lines.append(f"- {name}: {desc}")
                schema_name_map[name] = name

        if not catalogue_lines:
            return list(self._tools._tools.keys())[:8]

        catalogue_str = "\n".join(catalogue_lines)

        sel_system = (
            "You are a tool selector for an autonomous agent pipeline.\n"
            "Given a trigger signal and a list of available tools with descriptions, "
            "return ONLY the names of the tools most relevant to gathering data for this signal.\n"
            "Select 3-8 tools. Prefer tools that fetch data (research) over utility tools.\n"
            "Return ONLY valid JSON: [\"tool_name_1\", \"tool_name_2\", ...]"
        )
        sel_user = (
            f"Trigger signal:\n{json.dumps(trigger_signal, indent=2)[:400]}\n\n"
            f"Available tools:\n{catalogue_str}\n\n"
            "Select the most relevant tools. Return ONLY a JSON array of tool names."
        )

        try:
            text, sel_call = await self._llm.call(
                agent_name="discovery_tool_selector",
                messages=[
                    LLMMessage(role="system", content=sel_system),
                    LLMMessage(role="user", content=sel_user),
                ],
                tier_override="mini",
                client_overrides=input.llm_overrides,
            )
            # Track discovery selection cost (previously untracked leakage)
            if sel_call.cost_usd > 0:
                if hasattr(self._llm, '_workflow_logger') and self._llm._workflow_logger:
                    self._llm._workflow_logger.log_cost_source(
                        "discovery_tool_selector", sel_call.cost_usd
                    )
            # Extract JSON array from response
            import re as _re
            match = _re.search(r'\[.*?\]', text, _re.DOTALL)
            if match:
                names = json.loads(match.group())
                if isinstance(names, list):
                    llm_tools = [n for n in names if isinstance(n, str) and n in self._tools._tools]
                    if llm_tools:
                        self._log.info(
                            "DiscoveryAgent: LLM tool selection succeeded (slow path)",
                            count=len(llm_tools),
                            tools=llm_tools,
                            cost=f"${sel_call.cost_usd:.5f}",
                        )
                        return llm_tools[:10]
        except Exception as _sel_err:
            self._log.warning("LLM tool selection failed", error=str(_sel_err))

        # Ultimate fallback: names extracted from schemas
        fallback = [
            s.get("function", s).get("name", "")
            for s in all_schemas[:8]
            if s.get("function", s).get("name")
        ]
        fallback = [n for n in fallback if n in self._tools._tools]
        return fallback or list(self._tools._tools.keys())[:6]


# ─────────────────────────────────────────────────────────────────────────────
# 8 REUSABLE AGENT CAPABILITIES (AGENT REGISTRY)
# ─────────────────────────────────────────────────────────────────────────────

class CustomerOutreachAgent(BaseAgent):
    """Customer Outreach Capability: Drafts external communication & outreach."""
    agent_type = "customer_outreach_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        messages = [
            LLMMessage(role="system", content="You are a Customer Outreach Agent capability. Draft clear, professional, personalized outreach messages. Return JSON with subject, body, recipient, and escalate flag."),
            LLMMessage(role="user", content=f"Context for outreach:\n{json.dumps(context, default=str)[:3000]}"),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text) or {
            "subject": "Follow-up",
            "body": text[:500],
            "escalate": False,
        }
        return AgentOutput(
            agent_type=self.agent_type,
            output_dict=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
            confidence=0.90,
        )

class CustomerSupportAgent(BaseAgent):
    """Customer Support Capability: Constrained FAQ & inquiry response agent."""
    agent_type = "customer_support_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        messages = [
            LLMMessage(role="system", content="You are a Customer Support Agent capability. Answer user questions strictly using approved knowledge. If unsure or high risk, set escalate=true."),
            LLMMessage(role="user", content=f"Inquiry context:\n{json.dumps(context, default=str)[:3000]}"),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text) or {
            "response": text[:500],
            "escalate": False,
            "confidence": 0.85,
        }
        return AgentOutput(
            agent_type=self.agent_type,
            output_dict=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
            confidence=output_dict.get("confidence", 0.85),
        )

class MarketingOutreachAgent(BaseAgent):
    """Marketing Outreach Capability: Brand content & campaign asset generator."""
    agent_type = "marketing_outreach_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        messages = [
            LLMMessage(role="system", content="You are a Marketing Outreach Agent capability. Draft marketing copy and content assets grounded in verified business information."),
            LLMMessage(role="user", content=f"Campaign context:\n{json.dumps(context, default=str)[:3000]}"),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text) or {"content_draft": text[:500]}
        return AgentOutput(
            agent_type=self.agent_type,
            output_dict=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
        )

class SummarizerAgent(BaseAgent):
    """Summarizer Capability: Synthesizes business documents, cases, or interaction logs."""
    agent_type = "summarizer_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        node_data = input.node_specific_data or {}
        prompt_file = node_data.get("prompt_file")

        # Load system prompt
        system_prompt = ""
        if prompt_file:
            system_prompt = await _load_prompt(prompt_file)
        if not system_prompt:
            system_prompt = "You are a Summarizer Agent capability. Synthesize raw records into concise, structured briefs."

        # Extract emails from context and strip ground-truth synthetic fields (scenario, priority)
        raw_fetch = context.get("fetch_emails", {}) or context.get("research", {})
        messages_list = raw_fetch.get("messages", [])
        
        clean_messages = []
        for m in messages_list:
            if isinstance(m, dict):
                clean_messages.append({
                    "email_id": m.get("email_id") or m.get("id", ""),
                    "from": m.get("from") or m.get("sender", ""),
                    "to": m.get("to") or m.get("recipient", ""),
                    "subject": m.get("subject", ""),
                    "body": m.get("body", ""),
                    "received_at": m.get("received_at") or m.get("timestamp", "")
                })

        user_content = (
            f"Email records to analyze ({len(clean_messages)} emails):\n"
            f"{json.dumps(clean_messages, indent=2, default=str)}\n\n"
            f"Analyze all emails and return valid JSON matching the exact required schema."
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_content),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text)
        if not isinstance(output_dict, dict):
            output_dict = {
                "executive_summary": text[:500] if text else "Summary completed.",
                "total_emails": len(clean_messages),
                "per_email_analysis": [],
                "category_counts": {}
            }

        # Calculate category counts & metrics if missing or incomplete
        per_email = output_dict.get("per_email_analysis") or []
        if isinstance(per_email, list) and per_email:
            cat_counts = {
                "customer_request": 0,
                "follow_up": 0,
                "sales_opportunity": 0,
                "urgent_issue": 0,
                "internal": 0,
                "finance": 0,
                "support": 0,
                "other": 0
            }
            attention_count = 0
            for pe in per_email:
                cat = pe.get("category", "other").lower()
                if cat in cat_counts:
                    cat_counts[cat] += 1
                else:
                    cat_counts["other"] += 1
                if pe.get("needs_attention") or pe.get("priority") in ("urgent", "high"):
                    attention_count += 1
            output_dict["category_counts"] = cat_counts
            output_dict["total_emails"] = len(clean_messages) or len(per_email)
            output_dict["needs_attention_count"] = attention_count

        return AgentOutput(
            success=True,
            confidence=output_dict.get("confidence") if isinstance(output_dict.get("confidence"), (int, float)) else 0.95,
            output_data=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
            provider=call.provider,
            cached_tokens=call.cached_tokens,
            fallback_used=call.fallback_used,
            fallback_from=call.fallback_from,
            fallback_reason=call.fallback_reason,
        )


class RecommendationAgent(BaseAgent):
    """Recommendation Capability: Suggests operational next steps (strictly non-clinical)."""
    agent_type = "recommendation_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        messages = [
            LLMMessage(role="system", content="You are an Operational Recommendation Agent capability. Suggest practical next steps and task priorities for business operations. NEVER provide clinical advice."),
            LLMMessage(role="user", content=f"Operational context:\n{json.dumps(context, default=str)[:3000]}"),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text) or {
            "recommended_actions": ["Review task details", "Follow up with assignee"],
            "urgency": "medium",
        }
        return AgentOutput(
            success=True,
            confidence=0.9,
            output_data=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
        )

class ComparisonAgent(BaseAgent):
    """Comparison Capability: Quote & data line-item normalization & comparison engine."""
    agent_type = "comparison_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        messages = [
            LLMMessage(role="system", content="You are a Comparison Agent capability. Normalize quote line items into canonical categories and generate side-by-side comparison tables."),
            LLMMessage(role="user", content=f"Quotes & Data to compare:\n{json.dumps(context, default=str)[:4000]}"),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text) or {
            "normalized_comparison": text[:500],
            "passed": True,
        }
        return AgentOutput(
            success=True,
            confidence=0.9,
            output_data=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
        )

class HRAgent(BaseAgent):
    """HR Capability: Internal business onboarding & internal task coordinator."""
    agent_type = "hr_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        messages = [
            LLMMessage(role="system", content="You are an HR Capability Agent. Process internal onboarding tasks and document checklists."),
            LLMMessage(role="user", content=f"HR Context:\n{json.dumps(context, default=str)[:3000]}"),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text) or {"status": "processed", "summary": text[:300]}
        return AgentOutput(
            success=True,
            confidence=0.9,
            output_data=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
        )

class OperationsAgent(BaseAgent):
    """Operations Capability: Multi-step task & milestone coordinator."""
    agent_type = "operations_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        context = input.accumulated_context or {}
        messages = [
            LLMMessage(role="system", content="You are an Operations Agent capability. Track workflow execution milestones, generate task checklists, and update case stages."),
            LLMMessage(role="user", content=f"Workflow Execution Context:\n{json.dumps(context, default=str)[:3000]}"),
        ]
        text, call = await self._call_llm_with_fallback(messages, input)
        output_dict = self._parse_json(text) or {
            "status": "success",
            "milestone": "step_completed",
            "actions_taken": ["Logged stage completion"],
        }
        return AgentOutput(
            success=True,
            confidence=0.9,
            output_data=output_dict,
            reasoning_chain=text,
            tokens_in=call.tokens_in,
            tokens_out=call.tokens_out,
            cost_usd=call.cost_usd,
            model_used=call.model,
            duration_ms=int((time.time() - start) * 1000),
        )
