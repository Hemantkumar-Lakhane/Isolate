"""
agents/consensus_agent.py
==========================
Meta-Debate Consensus Node.

Spawns TWO reasoning agents with opposing "personalities":
  - Risk-Averse Auditor: focuses on downside, caution, compliance
  - Growth-Focused Strategist: focuses on upside, opportunity, action

If they AGREE → confidence boosted, autonomous action possible.
If they DISAGREE → mandatory escalation to human.

Use in DAG: { "agent": "consensus_agent", ... }

The node automatically reads research output from accumulated_context
and writes a merged analysis in the same format as reasoning_agent output.

CONSTANT — do not modify for business customization.
CONFIGURE — via dag node: consensus_config.high_value_threshold
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

import structlog

from agents.base_agent import AgentInput, AgentOutput, BaseAgent, LLMMessage

log = structlog.get_logger()

# Boost factor when both agents agree (multiplied by min confidence)
AGREEMENT_CONFIDENCE_BOOST = 1.15
# Minimum similarity score to consider "agreement"
AGREEMENT_THRESHOLD = 0.80

_ACTION_CATEGORIES: dict[str, str] = {
    # Email outreach
    "send_csm_outreach_email":        "email_outreach",
    "send_executive_escalation":      "email_outreach",
    "send_reengage_email":            "email_outreach",
    "send_manager_alert":             "email_outreach",
    "send_wellness_check_message":    "email_outreach",
    "send_appointment_reminder":      "email_outreach",
    # CRM / task creation
    "create_hubspot_task":            "crm_task",
    "flag_for_renewal_team":          "crm_task",
    "schedule_buyer_review":          "crm_task",
    "schedule_manager_review":        "crm_task",
    "log_activity":                   "crm_task",
    # Notifications
    "post_slack_alert":               "notification",
    "post_inventory_digest":          "notification",
    "post_sales_digest":              "notification",
    # Escalation
    "escalate_to_cfo":                "escalation",
    "send_executive_escalation":      "escalation",
    "flag_for_clinical_review":       "escalation",
    # Phone / call
    "schedule_care_coordinator_call": "call_action",
    "schedule_call":                  "call_action",
}
 
def _action_category(action_id: str) -> str:
    return _ACTION_CATEGORIES.get(action_id, f"custom_{action_id}")

class ConsensusAgent(BaseAgent):
    """
    Meta-Debate Consensus Node.

    Two sub-agents debate the situation from opposing angles.
    Consensus → boosted confidence, auto-action possible.
    Disagreement → mandatory escalation.

    This is intended for high-stakes decisions (configurable via
    consensus_config.high_value_threshold in the DAG node).
    """

    agent_type = "consensus_agent"

    async def receive(self, input: AgentInput) -> AgentOutput:
        start = time.time()
        cfg = input.tenant_config
        node_data = input.node_specific_data
        consensus_config = node_data.get("consensus_config", {})
        high_value_threshold = consensus_config.get("high_value_threshold", 50_000)

        research_data = input.accumulated_context.get("research", {})
        rag_ctx = input.accumulated_context.get(
            "_rag_historical_context",
            "No historical context available yet.",
        )
        # ── Pre-gate: check if orchestrator already bypassed us ───────────────
        # If accumulated_context already has our node_id (meaning orchestrator's
        # consensus gate injected the reasoning output), return immediately.
        node_id = node_data.get("id", "consensus")
        if (input.accumulated_context.get(node_id, {}).get("_gate_bypassed")):
            log.info("ConsensusAgent: orchestrator gate already handled this node", node_id=node_id)
            existing = input.accumulated_context[node_id]
            return AgentOutput(
                success=True,
                confidence=existing.get("reasoning_confidence", 0.9),
                output_data=existing,
                reasoning_chain="Gate bypassed by orchestrator — high confidence from ReasoningAgent",
                escalate=False,
                duration_ms=0,
            )

        # ── Run both sub-agents in parallel ──────────────────────────────
        try:
            auditor_result, strategist_result = await asyncio.gather(
                self._run_auditor(cfg, research_data, rag_ctx, input),
                self._run_strategist(cfg, research_data, rag_ctx, input, high_value_threshold),
            )
        except Exception as e:
            log.error("ConsensusAgent parallel run failed", error=str(e))
            return AgentOutput(
                success=False, confidence=0.0, output_data={}, reasoning_chain="",
                error=str(e), duration_ms=int((time.time() - start) * 1000),
            )

        # ── Calculate agreement score ─────────────────────────────────────
        agreement_score = self._calculate_agreement(auditor_result, strategist_result)
        agreed = agreement_score >= AGREEMENT_THRESHOLD

        # ── Merge outputs ─────────────────────────────────────────────────
        merged = self._merge_outputs(auditor_result, strategist_result, agreed)

        # Boost confidence if agreed
        if agreed:
            raw_conf = min(
                auditor_result.get("reasoning_confidence", 0.7),
                strategist_result.get("reasoning_confidence", 0.7),
            )
            merged["reasoning_confidence"] = min(0.98, raw_conf * AGREEMENT_CONFIDENCE_BOOST)
            merged["consensus"] = True
            merged["agreement_score"] = round(agreement_score, 3)
            should_escalate = False
            escalation_reason = ""
        else:
            merged["reasoning_confidence"] = 0.5
            merged["consensus"] = False
            merged["agreement_score"] = round(agreement_score, 3)
            should_escalate = True
            escalation_reason = (
                f"Consensus agents disagree (agreement score: {agreement_score:.0%}). "
                f"Auditor recommends: {auditor_result.get('recommended_actions', [{}])[0].get('action_id', 'caution')}. "
                f"Strategist recommends: {strategist_result.get('recommended_actions', [{}])[0].get('action_id', 'proceed')}. "
                f"Human decision required."
            )

        # Accumulate costs
        total_tokens_in = auditor_result.pop("_tokens_in", 0) + strategist_result.pop("_tokens_in", 0)
        total_tokens_out = auditor_result.pop("_tokens_out", 0) + strategist_result.pop("_tokens_out", 0)
        aud_cost = auditor_result.get("_cost_usd", 0.0)
        str_cost = strategist_result.get("_cost_usd", 0.0)

        total_cost = aud_cost + str_cost

        # Now pop once (optional cleanup)
        auditor_result.pop("_cost_usd", None)
        strategist_result.pop("_cost_usd", None)

        # Log to WorkflowSystemLogger (attribute is on _workflow_logger, not on _llm)
        if hasattr(self._llm, '_workflow_logger') and self._llm._workflow_logger:
            self._llm._workflow_logger.log_cost_source("consensus_auditor",    aud_cost)
            self._llm._workflow_logger.log_cost_source("consensus_strategist", str_cost)
        last_model = auditor_result.pop("_model_used", "")

        return AgentOutput(
            success=True,
            confidence=merged["reasoning_confidence"],
            output_data=merged,
            reasoning_chain=(
                f"META-DEBATE RESULT\n"
                f"Agreement score: {agreement_score:.0%} ({'AGREED' if agreed else 'DISAGREED'})\n\n"
                f"AUDITOR VIEW:\n{json.dumps(auditor_result.get('situation_summary', ''), indent=2)}\n\n"
                f"STRATEGIST VIEW:\n{json.dumps(strategist_result.get('situation_summary', ''), indent=2)}"
            ),
            escalate=should_escalate,
            escalation_reason=escalation_reason,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            cost_usd=total_cost,
            model_used=last_model,
            duration_ms=int((time.time() - start) * 1000),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Sub-agent runners
    # ─────────────────────────────────────────────────────────────────────

    async def _run_auditor(
        self,
        cfg: dict,
        research_data: dict,
        rag_ctx: str,
        input: AgentInput,
    ) -> dict:
        """Risk-Averse Auditor — emphasises caution, compliance, downside."""
        system = (
            f"You are a RISK-AVERSE COMPLIANCE AUDITOR for {cfg.get('client_name', 'the company')}. "
            "Your job is to challenge proposed actions and identify every possible risk, "
            "policy violation, or negative consequence. You are deliberately cautious. "
            "Apply the highest standards before recommending any action.\n\n"
            f"Business rules: {json.dumps(cfg.get('business_rules', {}), indent=2)}\n\n"
            f"Historical context: {rag_ctx[:800]}\n\n"
            "Return ONLY valid JSON with: situation_summary, urgency, reasoning_confidence (0-1), "
            "recommended_actions (list with action_id, confidence, reasoning, expected_outcome), "
            "escalate (bool), escalation_reason, key_risks (list of strings)."
        )
        user = (
            f"Research data:\n{json.dumps(research_data, indent=2, default=str)[:4000]}\n\n"
            "Assess from a RISK-AVERSE perspective. What are the risks? What could go wrong? "
            "What is the minimal safe action? Return ONLY valid JSON."
        )
        #   # FIX: Auditor role is adversarial chain-of-thought → DeepSeek R1 is purpose-built
        # for this. Strategist stays on Sonnet (nuanced opportunity assessment).
        # Savings: ~$0.14/run (DeepSeek R1 $0.55/$2.19 vs Sonnet $3.00/$15.00)
        auditor_tier = self._llm._consensus_config.get("auditor_tier", "reasoning")
        text, call = await self._simple_call(system, user, input, tier_override=auditor_tier)
        parsed = self._parse_json_output(text)
        parsed["_tokens_in"] = call.tokens_in
        parsed["_tokens_out"] = call.tokens_out
        parsed["_cost_usd"] = call.cost_usd
        parsed["_model_used"] = call.model
        parsed["_perspective"] = "auditor"
        return parsed

    async def _run_strategist(
        self,
        cfg: dict,
        research_data: dict,
        rag_ctx: str,
        input: AgentInput,
        high_value_threshold: float,
    ) -> dict:
        """Growth-Focused Strategist — emphasises opportunity, revenue protection, action."""
        system = (
            f"You are a GROWTH-FOCUSED SALES STRATEGIST for {cfg.get('client_name', 'the company')}. "
            "Your job is to identify the best opportunities for growth and revenue protection. "
            "You lean towards taking decisive action. The cost of inaction often exceeds the cost of action.\n\n"
            f"Business context: {json.dumps(cfg.get('company_profile', {}), indent=2)}\n\n"
            f"High-value threshold: ${high_value_threshold:,}\n\n"
            f"Historical context: {rag_ctx[:800]}\n\n"
            "Return ONLY valid JSON with: situation_summary, urgency, reasoning_confidence (0-1), "
            "recommended_actions (list with action_id, confidence, reasoning, expected_outcome), "
            "escalate (bool), escalation_reason, key_opportunities (list of strings)."
        )
        user = (
            f"Research data:\n{json.dumps(research_data, indent=2, default=str)[:4000]}\n\n"
            "Assess from a GROWTH-FOCUSED perspective. What opportunities exist? "
            "What revenue is at risk? What is the boldest safe action? Return ONLY valid JSON."
        )
        text, call = await self._simple_call(system, user, input, tier_override="heavy")
        parsed = self._parse_json_output(text)
        parsed["_tokens_in"] = call.tokens_in
        parsed["_tokens_out"] = call.tokens_out
        parsed["_cost_usd"] = call.cost_usd
        parsed["_model_used"] = call.model
        parsed["_perspective"] = "strategist"
        return parsed

    # ─────────────────────────────────────────────────────────────────────
    # Agreement scoring
    # ─────────────────────────────────────────────────────────────────────

    def _calculate_agreement(self, auditor: dict, strategist: dict) -> float:
        """
        Score how much two agents agree (0.0 = complete disagreement, 1.0 = identical).
    
        Components (must sum to 1.0):
        +0.40 — Same escalate decision (primary gate)
        +0.20 — Action overlap (action_id intersection ratio)
        +0.20 — Urgency alignment (close urgency levels)
        +0.20 — Intervention TYPE agreement (autonomous vs human-required) [NEW]
    
        FIX: Original 3-component version (0.5/0.3/0.2) allowed two agents to score
        0.50 from escalate agreement alone, reaching the 0.70 threshold with minimal
        urgency overlap even when their action recommendations were completely different.
        
        New 4-component version (0.40/0.20/0.20/0.20) requires genuine alignment
        across multiple dimensions to reach 0.80.
        """
        score = 0.0
    
        # Component 1: Escalation agreement (40%)
        if auditor.get("escalate") == strategist.get("escalate"):
            score += 0.40
    
        # Component 2: Urgency alignment (20%)
        urgency_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        aud_urg = urgency_map.get(str(auditor.get("urgency", "medium")).lower(), 2)
        str_urg = urgency_map.get(str(strategist.get("urgency", "medium")).lower(), 2)
        urg_diff = abs(aud_urg - str_urg)
        if urg_diff == 0:
            score += 0.20
        elif urg_diff == 1:
            score += 0.10
        # urg_diff >= 2 → 0 points
    
        # Component 3: Action overlap (20%)
        aud_categories = {
            _action_category(a.get("action_id", ""))
            for a in auditor.get("recommended_actions", [])
            if a.get("action_id")
        }
        str_categories = {
            _action_category(a.get("action_id", ""))
            for a in strategist.get("recommended_actions", [])
            if a.get("action_id")
        }
        if aud_categories and str_categories:
            overlap_ratio = (
                len(aud_categories & str_categories)
                / max(len(aud_categories | str_categories), 1)
            )
            score += 0.20 * overlap_ratio
    
        # Component 4: Intervention TYPE agreement (20%) [NEW]
        # "autonomous" = no escalation, use action library
        # "human_required" = escalate=True or high-stakes executive action needed
        def _intervention_type(agent_out: dict) -> str:
            if agent_out.get("escalate"):
                return "human_required"
            actions = agent_out.get("recommended_actions") or []
            if any("executive" in str(a.get("action_id", "")).lower() or
                "escalate" in str(a.get("action_id", "")).lower()
                for a in actions):
                return "human_required"
            return "autonomous"
    
        aud_type = _intervention_type(auditor)
        str_type = _intervention_type(strategist)
        if aud_type == str_type:
            score += 0.20
    
        return min(1.0, score)

    def _merge_outputs(self, auditor: dict, strategist: dict, agreed: bool) -> dict:
        """Produce a merged reasoning output from both perspectives."""
        # Take the more cautious urgency if disagreeing, strategist's if agreed
        urgency_order = ["low", "medium", "high", "critical"]

        def urgency_rank(d: dict) -> int:
            return urgency_order.index(str(d.get("urgency", "medium")).lower())
            
        if agreed:
            urgency = strategist.get("urgency", "medium")
        else:
            # Disagreed — take the higher urgency for safety
            urgency = urgency_order[max(urgency_rank(auditor), urgency_rank(strategist))]

        # Merge recommended_actions: de-dupe by action_id, prefer strategist's ordering
        actions_map: dict = {}
        for action in auditor.get("recommended_actions", []):
            actions_map[action.get("action_id", "")] = action
        for action in strategist.get("recommended_actions", []):
            aid = action.get("action_id", "")
            if aid in actions_map:
                # Blend confidence
                old_conf = actions_map[aid].get("confidence", 0.5)
                new_conf = action.get("confidence", 0.5)
                actions_map[aid]["confidence"] = (old_conf + new_conf) / 2
                actions_map[aid]["reasoning"] = (
                    f"[Auditor] {actions_map[aid].get('reasoning', '')} | "
                    f"[Strategist] {action.get('reasoning', '')}"
                )
            else:
                actions_map[aid] = action

        return {
            "situation_summary": (
                f"[AUDITOR] {auditor.get('situation_summary', 'N/A')}\n\n"
                f"[STRATEGIST] {strategist.get('situation_summary', 'N/A')}"
            ),
            "urgency": urgency,
            "recommended_actions": list(actions_map.values()),
            "key_risks": auditor.get("key_risks", []),
            "key_opportunities": strategist.get("key_opportunities", []),
            "auditor_escalate": auditor.get("escalate", False),
            "strategist_escalate": strategist.get("escalate", False),
        }