"""
core/auto_eval.py
=================
Automatic prompt evaluation pipeline based on human feedback (DSPy-inspired).

Analyzes human escalation corrections stored in RAG and generates SUGGESTIONS
for prompt improvements. NEVER applies changes without explicit admin approval.

Usage:
    service = AutoEvalService(llm_router=llm, rag_engine=rag)
    suggestions = await service.analyze_and_suggest(tenant_id, "saas_churn_prevention")
    # Admin reviews in /api/v1/admin/auto-eval/suggestions
    service.apply_suggestion(suggestion_id, admin_email)   # Admin-gated

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import structlog

log = structlog.get_logger()

import os as _os
_PROJECT_ROOT = Path(_os.getenv("OPSGRID_ROOT", Path(__file__).parent.parent))
SUGGESTIONS_BASE_DIR = _PROJECT_ROOT / "suggestions"
SUGGESTIONS_BASE_DIR.mkdir(parents=True, exist_ok=True)


class AutoEvalService:
    """
    Analyzes human corrections from RAG and produces prompt improvement suggestions.

    Human corrections are stored by `_store_human_correction_rag` whenever
    an admin overrides an agent's recommendation in an escalation. This service
    finds patterns in those corrections and uses an LLM to propose targeted
    changes to the workflow prompt files.

    All suggestions are stored in suggestions/*.json and require explicit
    admin approval (via apply_suggestion) before touching any prompt file.
    """

    def __init__(self, llm_router=None, rag_engine=None):
        self._llm = llm_router
        self._rag = rag_engine
        
    
    def _tenant_suggestions_dir(self, tenant_id: str) -> Path:
        """Return (and create) the tenant-specific suggestions directory."""
        d = SUGGESTIONS_BASE_DIR / str(tenant_id)
        d.mkdir(parents=True, exist_ok=True)
        return d
 
    def _suggestion_path(self, suggestion_id: str, tenant_id: str) -> Path:
        """Return the path for a specific suggestion file."""
        return self._tenant_suggestions_dir(tenant_id) / f"{suggestion_id}.json"

    # ─────────────────────────────────────────────────────────────────────
    # Analysis
    # ─────────────────────────────────────────────────────────────────────

    async def analyze_and_suggest(
        self,
        tenant_id: str,
        workflow_name: str,
        limit_corrections: int = 15,
    ) -> list[dict]:
        """
        Retrieve recent human corrections and generate prompt improvement suggestions.

        Returns a list of suggestion dicts (NOT yet applied to any prompt).
        Each suggestion requires admin approval before application.
        """
        if not self._rag or not self._llm:
            log.warning("AutoEval: RAG and LLM router are required")
            return []

        # ── Retrieve human correction lessons ─────────────────────────────
        corrections = await self._rag.retrieve_similar_situations(
            tenant_id=tenant_id,
            query=f"workflow human correction agent recommendation override {workflow_name}",
            top_k=limit_corrections,
            content_type="correction",
        )

        if not corrections:
            log.info("AutoEval: no human corrections found", workflow=workflow_name, tenant=tenant_id[:8])
            return []

        log.info("AutoEval: analyzing corrections", count=len(corrections), workflow=workflow_name)

        # ── Build correction summary ───────────────────────────────────────
        correction_text = "\n\n".join(
            f"--- Correction #{i+1} (similarity: {c.get('similarity', 0):.0%}) ---\n"
            f"{c.get('content_text', '')[:500]}"
            for i, c in enumerate(corrections[:10])
        )

        # ── Discover prompt files for this workflow ────────────────────────
        prompts_dir = Path("workflows/prompts")
        workflow_prefix = workflow_name.split("_")[0]
        prompt_files = list(prompts_dir.rglob(f"*{workflow_prefix}*/*.txt"))
        if not prompt_files:
            prompt_files = list(prompts_dir.rglob("*.txt"))

        prompt_catalogue = "\n".join(
            f"- {str(p.relative_to(prompts_dir))}"
            for p in prompt_files[:12]
        )

        # ── Build current prompt snippets for context ──────────────────────
        prompt_snippets = ""
        for p in prompt_files[:4]:
            content = p.read_text(encoding="utf-8")
            # Find escalation policy section for targeted analysis
            section = ""
            for marker in ["ESCALATION POLICY", "escalation", "ESCALATE"]:
                idx = content.find(marker)
                if idx != -1:
                    section = content[idx:idx + 400]
                    break
            if section:
                rel = str(p.relative_to(prompts_dir))
                prompt_snippets += f"\n### {rel} (escalation section):\n{section}\n"

        # ── LLM analysis ──────────────────────────────────────────────────
        from core.llm_router import LLMMessage

        system = (
            "You are a prompt engineering expert specializing in agentic AI systems.\n\n"
            "You will analyze cases where humans OVERRODE an AI agent's recommendation "
            "(escalation corrections). Your job is to identify PATTERNS in these overrides "
            "and suggest SPECIFIC, MINIMAL changes to the agent prompts that would align "
            "the AI behavior with human preferences.\n\n"
            "Guidelines:\n"
            "- Each suggestion must target a SPECIFIC prompt file and section\n"
            "- Suggest the MINIMUM change needed — don't rewrite entire prompts\n"
            "- Focus on escalation policy, action selection, and confidence thresholds\n"
            "- Do NOT suggest changes that would make agents less safe\n"
            "- If corrections are contradictory or unclear, say so\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "pattern_summary": "One paragraph describing the override pattern",\n'
            '  "correction_count_analyzed": 5,\n'
            '  "suggestions": [\n'
            "    {\n"
            '      "prompt_file": "saas/reasoning_churn.txt",\n'
            '      "target_section": "ESCALATION POLICY section",\n'
            '      "current_behavior_problem": "Agent escalates when MRR > $50k even with high confidence",\n'
            '      "suggested_addition": "Add rule: High MRR alone is not sufficient for escalation. Only escalate if confidence < threshold AND MRR > threshold.",\n'
            '      "rationale": "Humans consistently approved autonomous action for high-MRR accounts with clear signals",\n'
            '      "confidence": 0.85,\n'
            '      "risk_level": "low"\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        user = (
            f"Workflow under analysis: {workflow_name}\n"
            f"Tenant: {tenant_id[:16]}\n\n"
            f"=== HUMAN CORRECTION PATTERNS ({len(corrections)} corrections) ===\n"
            f"{correction_text}\n\n"
            f"=== AVAILABLE PROMPT FILES ===\n{prompt_catalogue}\n\n"
            f"=== CURRENT ESCALATION SECTIONS (for reference) ===\n"
            f"{prompt_snippets or '(not found)'}\n\n"
            "Analyze the correction patterns and generate suggestions. "
            "If there are fewer than 3 clear corrections, return an empty suggestions array "
            "and explain in pattern_summary why there's insufficient data."
        )

        try:
            text, call = await self._llm.call(
                agent_name="auto_eval_analyzer",
                messages=[
                    LLMMessage(role="system", content=system),
                    LLMMessage(role="user", content=user),
                ],
                tier_override="heavy",
            )
            log.info("AutoEval LLM analysis complete", cost=f"${call.cost_usd:.5f}")
        except Exception as e:
            log.error("AutoEval LLM call failed", error=str(e))
            return []

        # ── Parse response ─────────────────────────────────────────────────
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if not match:
                log.error("AutoEval: no JSON found in response")
                return []
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            log.error("AutoEval: JSON parse failed", error=str(e))
            return []

        raw_suggestions = data.get("suggestions", [])
        pattern_summary = data.get("pattern_summary", "")
        corrections_analyzed = data.get("correction_count_analyzed", len(corrections))

        if not raw_suggestions:
            log.info("AutoEval: no suggestions generated", summary=pattern_summary[:100])
            return []

        # ── Validate and store suggestions ─────────────────────────────────
        stored: list[dict] = []
        for s in raw_suggestions:
            prompt_file = s.get("prompt_file", "")
            if not prompt_file:
                continue

            # Verify the prompt file exists (safety check)
            full_path = Path("workflows/prompts") / prompt_file
            if not full_path.exists():
                log.warning("AutoEval: prompt file not found, skipping", file=prompt_file)
                continue

            suggestion_id = str(uuid.uuid4())
            suggestion = {
                "id": suggestion_id,
                "tenant_id": tenant_id,
                "workflow_name": workflow_name,
                "prompt_file": prompt_file,
                "target_section": s.get("target_section", ""),
                "current_behavior_problem": s.get("current_behavior_problem", ""),
                "suggested_addition": s.get("suggested_addition", ""),
                "rationale": s.get("rationale", ""),
                "confidence": float(s.get("confidence", 0.5)),
                "risk_level": s.get("risk_level", "medium"),
                "pattern_summary": pattern_summary,
                "corrections_analyzed": corrections_analyzed,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            }

            suggestion_path = self._suggestion_path(suggestion_id, tenant_id)
            suggestion_path.write_text(json.dumps(suggestion, indent=2))
            stored.append(suggestion)

        log.info(
            "AutoEval suggestions stored",
            workflow=workflow_name,
            count=len(stored),
            corrections_analyzed=corrections_analyzed,
        )
        return stored

    # ─────────────────────────────────────────────────────────────────────
    # Retrieval
    # ─────────────────────────────────────────────────────────────────────

    def get_suggestions(
        self,
        status: Optional[str] = None,
        workflow_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Return stored suggestions, filtered by tenant, status, or workflow.
        Now tenant-scoped: if tenant_id provided, only scans that tenant's dir.
        Admins (tenant_id=None) see all suggestions across all tenants.
        """
        suggestions: list[dict] = []
 
        if tenant_id:
            search_dirs = [self._tenant_suggestions_dir(tenant_id)]
        else:
            # Super-admin: scan all tenant subdirectories
            search_dirs = [
                d for d in SUGGESTIONS_BASE_DIR.iterdir() if d.is_dir()
            ]
            # Also include legacy root-level suggestions
            search_dirs.append(SUGGESTIONS_BASE_DIR)
 
        for search_dir in search_dirs:
            for f in sorted(
                search_dir.glob("*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            ):
                try:
                    s = json.loads(f.read_text())
                    if status and s.get("status") != status:
                        continue
                    if workflow_name and s.get("workflow_name") != workflow_name:
                        continue
                    if tenant_id and s.get("tenant_id") != tenant_id:
                        continue
                    suggestions.append(s)
                except Exception:
                    pass
 
        return suggestions

    def get_pending_count(self) -> int:
        """Quick count of pending suggestions — used by dashboard badges."""
        return sum(
            1 for f in SUGGESTIONS_DIR.glob("*.json")
            if json.loads(f.read_text()).get("status") == "pending"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Admin-gated actions
    # ─────────────────────────────────────────────────────────────────────

    def _find_suggestion_file(self, suggestion_id: str) -> Optional[Path]:
        """Find a suggestion file by ID across all tenant directories."""
        # Check all tenant subdirectories
        for path in SUGGESTIONS_BASE_DIR.rglob(f"{suggestion_id}.json"):
            return path
        return None
    def apply_suggestion(self, suggestion_id: str, admin_email: str) -> dict:
        """
        Apply a suggestion by APPENDING the suggested change to the prompt file.
        The original prompt content is preserved; the suggestion is added as a
        clearly marked addendum for human review.

        ONLY callable after explicit admin approval — never invoked automatically.
        """
        suggestion_path = self._find_suggestion_file(suggestion_id)
        if not suggestion_path:
            raise ValueError(f"Suggestion not found: {suggestion_id}")

        suggestion = json.loads(suggestion_path.read_text())

        if suggestion["status"] == "applied":
            raise ValueError("Suggestion already applied")
        if suggestion["status"] == "dismissed":
            raise ValueError("Cannot apply a dismissed suggestion")

        prompt_path = Path("workflows/prompts") / suggestion["prompt_file"]
        if not prompt_path.exists():
            raise ValueError(f"Prompt file not found: {suggestion['prompt_file']}")

        current_content = prompt_path.read_text(encoding="utf-8")
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        # Append as a clearly-marked, human-reviewable block
        addition = (
            f"\n\n# ═══════════════════════════════════════════════════════════\n"
            f"# AUTO-EVAL SUGGESTION — Applied {timestamp} by {admin_email}\n"
            f"# Workflow: {suggestion['workflow_name']}\n"
            f"# Corrections analyzed: {suggestion.get('corrections_analyzed', '?')}\n"
            f"# Confidence: {suggestion.get('confidence', 0):.0%}  Risk: {suggestion.get('risk_level', '?')}\n"
            f"# Pattern: {suggestion.get('pattern_summary', '')[:200]}\n"
            f"# Problem: {suggestion.get('current_behavior_problem', '')[:200]}\n"
            f"# Rationale: {suggestion.get('rationale', '')[:200]}\n"
            f"# ─────────────────────────────────────────────────────────────\n"
            f"# SUGGESTED ADDITION (review and integrate into prompt above):\n"
            f"# {suggestion.get('suggested_addition', '').replace(chr(10), chr(10) + '# ')}\n"
            f"# ═══════════════════════════════════════════════════════════"
        )

        prompt_path.write_text(current_content + addition, encoding="utf-8")

        suggestion["status"] = "applied"
        suggestion["applied_at"] = datetime.utcnow().isoformat()
        suggestion["applied_by"] = admin_email
        suggestion_path.write_text(json.dumps(suggestion, indent=2))

        log.info(
            "AutoEval suggestion applied",
            suggestion_id=suggestion_id,
            prompt_file=suggestion["prompt_file"],
            applied_by=admin_email,
        )
        return suggestion

    def dismiss_suggestion(self, suggestion_id: str) -> dict:
        """Mark suggestion as dismissed (no prompt change made)."""
        suggestion_path = self._find_suggestion_file(suggestion_id)
        if not suggestion_path:
            raise ValueError(f"Suggestion not found: {suggestion_id}")

        suggestion = json.loads(suggestion_path.read_text())
        suggestion["status"] = "dismissed"
        suggestion["dismissed_at"] = datetime.utcnow().isoformat()
        suggestion_path.write_text(json.dumps(suggestion, indent=2))

        log.info("AutoEval suggestion dismissed", suggestion_id=suggestion_id)
        return suggestion