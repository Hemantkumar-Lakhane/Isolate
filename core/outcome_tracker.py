"""
core/outcome_tracker.py
=======================
Outcome-Closed Learning Loop.

After the ExecutionAgent fires actions, this module registers a "follow-up check"
scheduled N days later. On the follow-up date, it pulls the same account data,
compares it to the baseline state, and stores the result (positive/negative) in RAG.

This transforms OpsGrid from task-automation into a self-improving system:
  - Positive: email sent → account recovered / deal closed / patient attended next appt
  - Negative: email sent → account churned anyway / deal lost / patient still disengaged

The RAG context injected into future ReasoningAgent runs will then contain:
  "Action X worked in Y% of similar situations with pattern Z"

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

import structlog

log = structlog.get_logger()


class OutcomeTracker:
    """
    Registers outcome check-ups and processes results into RAG memory.

    Workflow:
      1. ExecutionAgent completes → register_pending_outcome() called
      2. N days later (cron/scheduler) → check_pending_outcomes() pulls account data
      3. Comparison → store result in RAG with label "positive" or "negative"
      4. Future ReasoningAgent runs see "Action X led to recovery" or "Action X failed"
    """

    def __init__(self, state_manager=None, rag_engine=None):
        self._state = state_manager
        self._rag = rag_engine

    # ─────────────────────────────────────────────────────────────────────
    # Registration (called immediately after ExecutionAgent completes)
    # ─────────────────────────────────────────────────────────────────────

    async def register_pending_outcome(
        self,
        tenant_id: str,
        run_id: str,
        workflow_name: str,
        industry: str,
        actions_taken: list[dict],
        baseline_data: dict,          # research output at time of action
        follow_up_days: int = 7,
    ) -> int:
        """
        Register outcome checks for executed actions.

        Returns number of outcomes registered.
        """
        if not actions_taken:
            return 0

        registered = 0
        check_date = (datetime.utcnow() + timedelta(days=follow_up_days)).isoformat()

        for action in actions_taken:
            if action.get("status") != "success":
                continue

            account_id = action.get("account_id") or action.get("deal_id") or action.get("patient_id")
            if not account_id:
                continue

            # Get baseline metrics for comparison
            baseline_metrics = self._extract_baseline_metrics(industry, account_id, baseline_data)

            outcome_record = {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "run_id": run_id,
                "workflow_name": workflow_name,
                "industry": industry,
                "account_id": account_id,
                "action_taken": action.get("action", ""),
                "action_detail": action,
                "baseline_metrics": baseline_metrics,
                "check_date": check_date,
                "follow_up_days": follow_up_days,
                "status": "pending",
                "registered_at": datetime.utcnow().isoformat(),
            }

            if self._state and self._state._db is not None:
                try:
                    await self._state.upsert_pattern(
                        tenant_id=tenant_id,
                        pattern_key=f"outcome_pending_{outcome_record['id']}",
                        pattern_data=outcome_record,
                        success=True,
                        sandbox=False,   # outcomes go directly to active
                    )
                    registered += 1
                    log.debug(
                        "Outcome check registered",
                        account=account_id,
                        action=action.get("action", ""),
                        check_date=check_date,
                    )
                except Exception as e:
                    log.warning("Outcome registration failed", error=str(e))

        log.info(
            "Outcome checks registered",
            tenant=tenant_id[:8],
            run=run_id[:8],
            registered=registered,
            check_date=check_date,
        )
        return registered

    # ─────────────────────────────────────────────────────────────────────
    # Processing (called by scheduler or manual trigger)
    # ─────────────────────────────────────────────────────────────────────

    async def check_pending_outcomes(
        self,
        tenant_id: str,
        tool_registry=None,
    ) -> dict:
        """
        Pull all due outcome checks, fetch current data, compare to baseline,
        store results in RAG, mark as completed.

        Returns summary of processed outcomes.
        """
        if not self._state or not self._rag:
            return {"processed": 0, "error": "state_manager or rag_engine not available"}

        # Load pending outcomes from pattern store
        pending = await self._state.get_patterns(tenant_id, "outcome_pending_")
        now = datetime.utcnow()

        processed = positive = negative = 0

        for pattern in pending:
            record = pattern.pattern_data or {}
            check_date_str = record.get("check_date", "")

            if not check_date_str:
                continue

            try:
                check_date = datetime.fromisoformat(check_date_str)
            except (ValueError, TypeError):
                continue

            if check_date > now:
                # Not due yet
                continue

            account_id = record.get("account_id")
            action_taken = record.get("action_taken", "")
            baseline = record.get("baseline_metrics", {})
            industry = record.get("industry", "")
            workflow_name = record.get("workflow_name", "")

            # Fetch current state
            current_metrics = await self._fetch_current_metrics(
                industry, account_id, tool_registry
            )

            if not current_metrics:
                log.debug("Could not fetch current metrics for outcome check", account=account_id)
                continue

            # Compare
            outcome = self._evaluate_outcome(industry, baseline, current_metrics, action_taken)
            is_positive = outcome.get("is_positive", False)

            # Store in RAG as a labeled lesson
            lesson = (
                f"OUTCOME_RESULT\n"
                f"Workflow: {workflow_name} | Industry: {industry}\n"
                f"Action taken: {action_taken}\n"
                f"Account: {account_id}\n"
                f"Baseline (at action time): {json.dumps(baseline)}\n"
                f"Outcome ({record.get('follow_up_days', 7)} days later): {json.dumps(current_metrics)}\n"
                f"Result: {'POSITIVE' if is_positive else 'NEGATIVE'}\n"
                f"Analysis: {outcome.get('analysis', '')}\n"
                f"LESSON: Action '{action_taken}' was {'EFFECTIVE' if is_positive else 'INEFFECTIVE'} "
                f"in this situation. {outcome.get('lesson', '')}"
            )

            await self._rag.store_workflow_outcome(
                tenant_id=tenant_id,
                run_id=record.get("run_id", ""),
                workflow_name=f"{workflow_name}_outcome",
                situation_summary=lesson,
                reasoning_chain="",
                actions_taken=[{"action_id": action_taken}],
                outcome_indicator="positive" if is_positive else "negative",
                cost_usd=0.0,
            )

            # Mark as completed in pattern store
            try:
                completed_record = {
                    **record,
                    "status": "completed",
                    "outcome": "positive" if is_positive else "negative",
                    "current_metrics": current_metrics,
                    "completed_at": now.isoformat(),
                }
                pattern_key = pattern.pattern_key
                # Replace pending_ with completed_
                new_key = pattern_key.replace("outcome_pending_", "outcome_completed_")
                await self._state.upsert_pattern(
                    tenant_id=tenant_id,
                    pattern_key=new_key,
                    pattern_data=completed_record,
                    success=is_positive,
                    sandbox=False,
                )
            except Exception as e:
                log.warning("Outcome completion storage failed", error=str(e))

            processed += 1
            if is_positive:
                positive += 1
            else:
                negative += 1

        log.info(
            "Outcome checks processed",
            tenant=tenant_id[:8],
            processed=processed,
            positive=positive,
            negative=negative,
        )

        return {
            "processed": processed,
            "positive": positive,
            "negative": negative,
            "pending_remaining": len(pending) - processed,
        }

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    def _extract_baseline_metrics(self, industry: str, account_id: str, research_data: dict) -> dict:
        """Extract the key metrics for an account from research output."""
        accounts = research_data.get("accounts", []) or []
        deals = research_data.get("deals", []) or []
        patients = research_data.get("patients", []) or []

        for acc in accounts + deals + patients:
            if not isinstance(acc, dict):
                continue
            if acc.get("id") == account_id:
                if industry == "saas":
                    return {
                        "churn_score": acc.get("churn_score"),
                        "dau_trend_pct": (acc.get("usage") or {}).get("dau_trend_pct"),
                        "health_label": acc.get("health_label") or acc.get("_health_label"),
                        "mrr": acc.get("mrr"),
                        "nps_score": (acc.get("nps") or {}).get("score"),
                    }
                elif industry == "retail":
                    return {
                        "days_of_supply": acc.get("days_of_supply"),
                        "risk_label": acc.get("_risk_label"),
                        "current_stock": acc.get("current_stock"),
                    }
                elif industry == "healthcare":
                    return {
                        "adherence_score": acc.get("adherence_score"),
                        "days_since_last_visit": acc.get("days_since_last_visit"),
                        "no_shows_90d": acc.get("no_shows_90d"),
                        "risk_label": acc.get("_risk_label"),
                    }
                else:
                    return {"captured_at": datetime.utcnow().isoformat()}
        return {}

    async def _fetch_current_metrics(self, industry: str, account_id: str, tool_registry=None) -> dict:
        """Fetch current state for an account using local dev tools or registry."""
        if not tool_registry:
            return {}

        try:
            if industry == "saas":
                result = await tool_registry.execute("product_api_usage", {"account_id": account_id})
                if result.success:
                    accounts = (result.data or {}).get("accounts", [])
                    for acc in accounts:
                        if acc.get("id") == account_id:
                            return {
                                "dau_trend_pct": (acc.get("usage") or {}).get("dau_trend_pct"),
                                "health_label": acc.get("_health_label"),
                                "nps_score": (acc.get("nps") or {}).get("score"),
                                "last_login_days_ago": (acc.get("usage") or {}).get("last_login_days_ago"),
                            }
        except Exception as e:
            log.debug("Current metrics fetch failed", error=str(e))

        return {}

    def _evaluate_outcome(
        self,
        industry: str,
        baseline: dict,
        current: dict,
        action_taken: str,
    ) -> dict:
        """Compare baseline to current and determine if outcome is positive."""
        if industry == "saas":
            old_health = baseline.get("health_label", "")
            new_health = current.get("health_label", "")
            health_improved = (
                (old_health == "critical" and new_health in ("at_risk", "healthy"))
                or (old_health == "at_risk" and new_health == "healthy")
            )
            old_dau = baseline.get("dau_trend_pct", 0) or 0
            new_dau = current.get("dau_trend_pct", 0) or 0
            dau_improved = new_dau > old_dau

            is_positive = health_improved or (dau_improved and new_dau > -10)
            analysis = (
                f"Health label: {old_health} → {new_health}. "
                f"DAU trend: {old_dau:.1f}% → {new_dau:.1f}%."
            )
            lesson = (
                f"In similar churn situations, '{action_taken}' "
                f"{'recovered' if is_positive else 'did not recover'} the account."
            )

        elif industry == "healthcare":
            old_risk = baseline.get("risk_label", "")
            new_shows = current.get("no_shows_90d", 0) or 0
            old_shows = baseline.get("no_shows_90d", 0) or 0
            is_positive = new_shows <= old_shows or current.get("risk_label") == "stable"
            analysis = f"No-shows: {old_shows} → {new_shows}. Risk: {old_risk} → {current.get('risk_label', '?')}."
            lesson = f"Patient outreach via '{action_taken}' {'improved' if is_positive else 'did not improve'} engagement."

        else:
            # Generic: assume positive if no regression signals found
            is_positive = True
            analysis = "Generic outcome evaluation — no industry-specific metrics."
            lesson = f"Action '{action_taken}' was executed. Follow-up data shows no clear regression."

        return {"is_positive": is_positive, "analysis": analysis, "lesson": lesson}