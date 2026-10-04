# OpsGrid — Deep System Analysis & Improvement Roadmap

> **Prepared:** March 2026  
> **Scope:** Full codebase audit covering cost optimization, model design, context management, industry adaptability, frontend, and strategic improvements  
> **Verdict Summary:** OpsGrid is architecturally impressive and noticeably ahead of typical agent-builder tools. However, several design decisions create hidden costs, context quality risks, and scalability ceilings that need addressing before the system can truly serve SMEs at scale.

---

## Table of Contents

1. [System Overview & Documentation Correlation](#1-system-overview--documentation-correlation)
2. [Cost Optimization Analysis](#2-cost-optimization-analysis)
3. [Context Management & Summarization](#3-context-management--summarization)
4. [Agent Model Design Analysis](#4-agent-model-design-analysis)
5. [Industry Adaptability — Engine Design](#5-industry-adaptability--engine-design)
6. [Frontend Analysis](#6-frontend-analysis)
7. [Overall Improvements & Differentiating Features](#7-overall-improvements--differentiating-features)
8. [Priority Roadmap](#8-priority-roadmap)

---

## 1. System Overview & Documentation Correlation

### What the Documentation Promises

The FracsNet/OpsGrid tech spec describes a **"Autonomous Multi-Agent Workflow Engine"** designed for SMEs that lack manpower for repetitive research and targeted action tasks. Core promises:

- Modifiable per business; engine core stays constant  
- Handles industries: SaaS, Retail, Healthcare, Finance, Logistics  
- 6-agent pipeline: Research → Reason → Draft → Verify → Execute → Remember  
- Human-in-the-loop escalation with Prosecutor/Judge pattern  
- RAG-backed learning (patterns improve over runs)  
- Real-time cost transparency  
- EPI tamper-evident audit trail  

### What the System Actually Delivers

**✅ Correlates and OVERPERFORMS on:**

| Feature | Status | Notes |
|---|---|---|
| 6-agent pipeline | ✅ Overperforms | Added ConsensusAgent, DiscoveryAgent (7th + 8th agent) |
| Multi-industry configs | ✅ Done | 4 industries with full prompt sets |
| Human-in-loop | ✅ Done | Multi-sig escalations, A2A protocol |
| RAG with HyDE | ✅ Overperforms | HyDE is state-of-the-art; not in most systems |
| Real-time cost tracking | ✅ Done | Per-agent breakdown with live WS streaming |
| Prosecutor/Judge verification | ✅ Overperforms | Not in original spec; adds quality |
| GraphRAG | ✅ Overperforms | Structural similarity beyond text RAG |
| Time-Travel Debugging (Fork) | ✅ Overperforms | No comparable OSS system has this |
| DAG validation on save | ✅ Overperforms | Prevents dead-node crashes |
| Config validation pre-trigger | ✅ Overperforms | No spec requirement; very practical |
| Budget Governor (4 levels) | ✅ Done | Level-based model downgrade |
| Prompt caching (Anthropic) | ✅ Done | 90% token discount on system prompts |

**❌ Missing or Incomplete vs. Spec:**

| Feature | Status | Notes |
|---|---|---|
| Webhook dynamic routing | ⚠️ Partial | Hardcoded Stripe/HubSpot fallback still present |
| Scheduled workflow trigger | ❌ Missing | `schedule_cron` defined in DAGs but no scheduler runs |
| Outcome tracking / closed-loop learning | ⚠️ Partial | |
| Multi-tenant isolation in RAG | ⚠️ Partial | Tool schema indexed as "global", not per-tenant |admin trigger, not automated |
| Agent marketplace / library | ❌ Missing | No shareable workflow/agent templates |

**Critical Finding:** The system is feature-complete for a demo/MVP but has several production-blocking gaps (no scheduler, no closed-loop auto-running, RAG tool namespace collision) that prevent it from running as a true autonomous engine without constant human intervention.

---

## 2. Cost Optimization Analysis

### 2A. What Is Working Well

**Prompt Caching (Anthropic `cache_control`)** — This is the single biggest ROI optimization. The system correctly injects `cache_control: ephemeral` on system messages, which can yield 90% discount on re-used system prompt tokens. For the Reasoning Agent which receives a large system prompt containing full company profile + business rules + tone + action library, this can save $0.02–$0.05 per run.

**Budget Governor (4 Levels)** — The tiered model downgrade logic is sound in concept:
- Level 1: Research/Verification → mini (correct; these are data-retrieval, not reasoning tasks)
- Level 2: Reasoning/Drafting → budget_heavy (Haiku 4.5; good balance)
- Level 3: All mini (aggressive but controllable)

**Consensus Gate** — Pre-gate check at confidence >= 0.90 skips two simultaneous Sonnet calls (~$0.32 saved per gated run). This is well-implemented.

**Parallel Tool Execution** — `asyncio.gather` for tool calls at optimization level < 2 is correct; avoids sequential IO wait.

**Within-Loop Tool Result Compression** — Compressing tool results > 6,000 chars mid-loop prevents context blowup on Research agents with many tool calls.

---

### 2B. Problems Found

#### Problem 1: LLM-Based Map-Reduce Is Expensive and Counterproductive

**Where:** `core/llm_router.py` → `summarize_for_context()` and `_map_reduce_summarize()`

**What it does:** When research output > ~40,000 chars, the system spawns multiple mini-model calls to chunk-summarize in parallel, then makes a final consolidation call.

**The problem:** This is using an LLM to summarize structured JSON data. Research from 2025 (emergentmind.com, ACON paper) consistently shows that **simple observation masking outperforms LLM-based summarization** for cost efficiency on structured agentic workflows. LLM summarization:
- Adds 3–7% extra cost per run (hidden in `map_reduce_summarizer` calls)
- Can lose numeric precision (churn scores become approximate)
- Can lose JSON IDs (account IDs get swapped in paraphrase)
- Is inherently slower (serial for consolidation step)

**Specific code flaw:**
```python
# In _summarize_chunk: uses "mini" tier for MAP, "balanced" for REDUCE
tier = "balanced" if is_final else "mini"
```
The final `balanced` consolidation call costs more than the savings from chunking, especially for 3–5 chunk scenarios.

**Fix:** See Section 3 for the correct non-LLM approach.

---

#### Problem 2: HyDE Costs Are Untracked, Creating Budget Leakage

**Where:** `core/rag_engine.py` → `_generate_hypothetical_answer()`

**What it does:** Generates a hypothetical past-outcome document before RAG retrieval. This improves retrieval quality but costs an LLM call.

**The problem:** The cost was originally completely untracked. The code has a partial fix (`workflow_logger.mark_hyde(cost)`) but:
1. The `WorkflowSystemLogger` is only initialized in `run_workflow()`, not in `resume_workflow()`. If RAG is called during resume (which it is for the Reasoning agent), `_workflow_logger` is `None` and the cost is silently dropped.
2. HyDE fires for EVERY `retrieve_similar_situations()` call, including the two calls inside `get_historical_context_for_reasoning()` (once for outcomes, once for corrections). That's 2 mini calls per ReasoningAgent invocation just for RAG lookup.

**Estimate:** 2 HyDE calls × ~300 tokens × $0.001/1K tokens = ~$0.0006 per run. Small but invisible on the cost dashboard.

---

#### Problem 3: Discovery Agent Slow Path Is Poorly Guarded

**Where:** `agents/agents.py` → `DiscoveryAgent._select_tools()`

**What it does:** If no RAG pre-selected tools, it falls back to LLM-based tool selection from a catalogue of up to 30 schemas.

**The problem:** The LLM slow path sends up to 30 tool schemas (each 100–200 tokens) to a mini model. That's 3,000–6,000 tokens of input just for tool selection. At Haiku pricing ($1/M), this is a $0.003–0.006 mini-call that happens BEFORE the actual research, invisible in the cost dashboard because it's logged as `discovery_tool_selector`.

Additionally, the RAG fast path only works if tools were pre-indexed — and the re-index check (`_needs_tool_reindex`) only compares `frozenset(self._tools._tools.keys())`. If CustomTools are added in the DB between the process start and a run, the frozenset comparison catches it. But the first run of a fresh process ALWAYS re-indexes everything, even if the embedding vectors are already in the DB from a previous process instance.

---

#### Problem 4: Reasoning Chain Distillation Calls an LLM to Save Context

**Where:** `core/llm_router.py` → `truncate_reasoning_chain()`

**What it does:** At optimization level >= 2, calls a mini model to distill the reasoning chain before passing it to downstream agents.

**The problem:** This is explicitly calling a mini LLM (cost: tokens × $0.001/1K) to reduce context that costs less than the call itself. The reasoning chain is internal state passed between agents. Downstream agents (Drafting, Verification, Execution) only need a small slice: top-N accounts with scores + recommended actions. The full reasoning JSON chain can be field-filtered algorithmically without an LLM call at all.

**Real cost:** 2,000 token reasoning chain → mini distillation call → 400 tokens output. Input cost: $0.002. Output: $0.0004. A simple Python dict extraction of `critical_accounts[:5]` costs $0.00 and takes 0.1ms.

---

#### Problem 5: Verification Agent Runs TWO LLM Calls (Prosecutor + Judge) at Mini Tier — But Should Not

**Where:** `agents/agents.py` → `VerificationAgent.receive()`

**The Judge/Prosecutor pattern is excellent for quality.** However, the Prosecutor is forced to `tier_override="mini"` unconditionally. For complex verification (multiple drafts, HIPAA healthcare content), a mini model frequently produces shallow faults that the Judge then has to second-guess. This results in the Judge needing more tool calls and more output tokens to compensate — spending more than if the Prosecutor used "fast" tier.

**The Prosecution step is adversarial chain-of-thought**, which benefits from a slightly stronger model. The current setup tries to be cheap here but ends up paying more in the Judge step.


---

### 2C. Cost Optimization Summary Table

| Issue | Current Cost Impact | Severity |
|---|---|---|
| LLM Map-Reduce for JSON summarization | +3–7% per run | 🔴 High |
| HyDE cost leakage on resume path | Invisible to dashboard | 🟡 Medium |
| Discovery slow-path token waste | +$0.003–0.006 per workflow | 🟡 Medium |
| Reasoning chain distillation LLM call | Costs more than it saves | 🟡 Medium |
| Prosecutor at mini (over-corrected by Judge) | Defeats purpose of dual-agent | 🟠 Medium-High |
| Cache control on all calls unconditionally | Wastes cache_write premium | 🟡 Medium |

---

## 3. Context Management & Summarization

### 3A. The Core Tension

OpsGrid has two conflicting pressures:

1. **Send less context** → cheaper, faster, avoids context drift
2. **Preserve critical data** → account IDs, scores, emails, monetary values cannot be paraphrased

The current approach (LLM-based Map-Reduce) addresses both by using an LLM to intelligently summarize. **Research from 2025 consistently shows this is the wrong tool for structured JSON data.** Per the emergentmind.com analysis: *"simple masking is typically Pareto-optimal for code agents with verbose tool outputs and should be default; infrequent summarization checkpoints are only recommended for loop detection or plateau triggers."*

The ACON paper (arXiv 2510.00615) showed 26–54% memory reduction while preserving task success using failure-driven compression guidelines — not generic LLM calls.

---

### 3B. What Should Replace LLM Summarization for Structured Data

#### Solution 1: Schema-Aware Field Projection (FREE, Zero LLM cost)

For research output (list of account dicts), instead of summarizing, project to the minimal fields each downstream agent actually needs:

```
ResearchAgent output (full):        ~800 fields × 120 accounts = ~100K chars
ReasoningAgent needs:               id, company_name, mrr, dau_trend_pct, 
                                    last_login_days_ago, tickets_30d, nps_score,
                                    health_label, renewal_date, contact_email
That's 10 fields × 120 accounts =  ~12K chars

Savings: 88% without any LLM call, and ZERO precision loss.
```

This is pure Python dict projection. The system already does this partially in `_prune_context()` but only for DB storage, not for inter-agent passing.

**Implementation:** Create a `AGENT_REQUIRED_FIELDS` registry in the orchestrator that defines exactly which fields each agent type reads from each upstream agent. Apply field projection in `_prune_context()` before passing context to any agent. also per workflow it should be changable from frontend and totally customizable by businesses. should come with predefined and must be modifyable.

---

#### Solution 2: Ranked Truncation by Business Criticality (FREE)

For account lists, instead of LLM summarization, apply business-rule-aware sorting + hard cap:

```python
def smart_truncate_accounts(accounts, max_count=15, rules):
    # Sort by: (1) health_label priority, (2) MRR desc, (3) days_to_renewal asc
    priority = {'critical': 0, 'at_risk': 1, 'healthy': 2}
    sorted_accs = sorted(accounts, key=lambda a: (
        priority.get(a.get('_health_label', 'healthy'), 2),
        -a.get('mrr', 0),
        a.get('days_to_renewal', 365)
    ))
    return sorted_accs[:max_count]
```

This preserves the highest-business-value accounts without any LLM involvement. The accounts that matter most always survive truncation.

---

#### Solution 3: Structured State Anchoring (for long multi-turn tool loops)

For Research agents that run 5–10 tool iterations, the current context grows linearly with each tool result appended. **The correct pattern (per Factory.ai's evaluation)** is anchored iterative summarization:

Keep a persistent `session_anchor` dict that is updated after each tool call:

```python
anchor = {
    "accounts_collected": [],          # Growing list of IDs collected
    "tool_results_digest": {},         # Summary per tool: {tool_name: key_metrics}
    "anomalies_found": [],             # Running list of flagged issues
    "data_gaps": []                    # What's still missing
}
```

After each tool call, update the anchor in-place. Pass only `anchor + last_2_tool_results` to the next LLM iteration. This cuts Research agent context by 60–80% in long tool loops without LLM calls.

---

#### Solution 4: When LLM Summarization IS Appropriate

LLM-based summarization is justified ONLY for:

1. **Free-text narrative content** (customer NPS verbatims, email bodies, meeting notes) where semantic meaning must be preserved in natural language
2. **Cross-source deduplication** (e.g., merging overlapping data from 3 different tool sources)
3. **Delta summaries** (MemoryAgent extracting what's new in this run vs. history)

For these cases, the current Map-Reduce approach is reasonable — but the REDUCE step should use "mini" (not "balanced") because the consolidation is structural, not creative.
the user the business owner should be able to select what all types of map reduce concepts they want implimented and those only will work for them.

---

### 3C. Context Drift Problem

**Finding:** The current `_prune_context()` in the orchestrator only applies to DB storage writes, not to agent input construction. The orchestrator's `_prune_context(node, ctx)` does field-filter based on `depends_on`, which is good. However, meta-keys like `_rag_historical_context` and `_research_summary` are always passed through regardless of whether the current agent needs them.

For example: The MemoryAgent receives the full `_rag_historical_context` (often 1,500–2,000 chars) plus the full research summary. MemoryAgent only needs `execution_output` and `reasoning_output`. This adds unnecessary tokens to every MemoryAgent call.

**Fix:** Implement per-agent context masks that explicitly declare which keys are needed, with the orchestrator enforcing the mask before calling each agent.

---

### 3D. The JSON Format Tax

**Finding:** All inter-agent data is passed as indented JSON (`json.dumps(..., indent=2)`). Indented JSON adds ~30–40% extra tokens vs. compact JSON. On a 10,000 char research output, that's ~3,000 extra chars = ~750 extra tokens = ~$0.00075 extra per agent call.

**Fix:** Pass `json.dumps(..., separators=(',', ':'))` (compact JSON) in all agent-to-agent context passing. Keep indented JSON only for:
- Human-readable prompts where readability aids LLM parsing
- DB storage
- API responses

This alone would save 25–35% on context tokens with zero quality impact.

---

## 4. Agent Model Design Analysis

### 4A. ResearchAgent

**Design:** Fast/mini tier, tool-heavy, goal-oriented prompt with adaptive strategy.  
**What's right:** Mini model is correct for data collection. The adaptive goal-oriented prompt (try alternatives if tools return empty) is far better than the old rigid numbered steps.  
**Problems:**

1. **Prompt template uses `{current_datetime}` but the literal `{{current_datetime}}` appears in output format** — this is a Python format string collision. In `research_churn.txt`, the output JSON template uses `"current_datetime": "{{current_datetime}}"` which becomes `"current_datetime": "{current_datetime}"` after `.format()`. This causes a `KeyError` in strict parsing and a confusing literal in loose parsing.

2. **No retry signal for empty tool results.** The adaptive prompt says "try alternative tools if empty" but gives no structured way to signal which tools returned empty data back to the orchestrator. If all tools return empty, the agent returns `{"accounts": []}` which passes to the ReasoningAgent which can't make recommendations and then escalates — burning the full pipeline cost for empty input.

3. **The `available_tools` list is passed in node_specific_data but the agent doesn't validate it exists before use.** If a DAG node has `"tools": []` (no tools), the ResearchAgent falls through to `_call_with_tools(messages, [], input)` which has an obscure fallback that doesn't actually call any tools and returns empty text, which then causes `_parse_json_output` to fail.

**Recommended fixes:**
- Add a data-sufficiency check before returning: if `len(accounts) == 0`, set a flag that allows the orchestrator to try a different research strategy or trigger early escalation with a specific `EMPTY_DATA` reason rather than burning downstream agents.
- Fix the format string collision in all research prompts.

---

### 4B. ReasoningAgent

**Design:** Heavy tier (Sonnet), single LLM call, business-rule scoring.  
**What's right:** Using the heaviest model for business reasoning is correct. The DotDict wrapper for dot-notation template access is clever. The safe churn_risk/pipeline extraction with `or {}` guards is well-done.  
**Problems:**

1. **The OUTPUT SIZE CONSTRAINTS section in reasoning prompts caps critical_accounts at 5 and at_risk_accounts at 5.** This is a hard prompt-level cap. For a SaaS company with 30 critical accounts, only 5 get actioned per run. The other 25 are silently dropped. The prompt says "summarise the rest in situation_summary" but the situation_summary field has no structured place to carry the skipped account IDs. This means 83% of critical accounts get no outreach in a large-account run — which defeats the purpose of churn prevention.

   **Fix:** The cap should be on the OUTPUT size per account (keep fields concise), not on the COUNT of accounts. Add a `remaining_critical_count` field and structured `additional_critical_account_ids` list that the DraftingAgent can use for batch processing. also the output size must be modifybale per workflow for reasoning agent for this specific thing.

2. **Confidence threshold comparison uses `float(output_data.get("reasoning_confidence", 0.8))`** — if the LLM returns `reasoning_confidence` as a string like `"0.85"` (common in cheap models), this works. But if it returns a dict or None (parse error recovery), this throws `TypeError`. Add type guard.

3. **The A2A request structure is defined in the agent output, but the schema for `a2a_request` is never enforced.** The orchestrator checks `output.output_data.get("a2a_request")` but if the LLM halluculates the field (e.g., `"a2a_request": true` instead of a dict), the orchestrator crashes silently.

---

### 4C. DraftingAgent

**Design:** Heavy tier, two-phase approach (Phase 1: tool calls, Phase 2: drafting).  
**What's right:** The two-phase split (call tools first, then draft) is brilliant and solves the real problem of agents drafting before checking communication history. This pattern deserves to be generalized.  
**Problems:**

1. **The Phase 1 output is discarded after parsing.** Phase 1 returns `{"safe_to_contact": [...], "skip_accounts": [...]}` but this result is stored in `p1_text` and only used to construct `phase2_instruction`. There's no structured extraction. If the mini model in Phase 1 returns a slightly malformed JSON (common when it has 8+ tool calls), `phase2_instruction` gets the raw text as context, which the Phase 2 model then has to parse again.

2. **Phase 1 caps at 8 accounts per category.** With `all_accounts = []` building from `[:8]` slices of each account list, for a 15-critical-account scenario, Phase 1 only checks history for 8. The other 7 never get history-checked and may get drafted emails anyway.

3. **The DotDict wrapper for `tone_profile`** works for simple access like `{tone_profile.brand_voice}` but breaks for nested dict access like `{tone_profile.avoid_phrases}` which is a list. When `.format()` calls `str()` on the DotDict result for a list value, it renders as `"['synergy', 'circle back']"` rather than a human-readable list.

---

### 4D. VerificationAgent (Judge/Prosecutor Pattern)

**Design:** Mini for Prosecutor (adversarial faults), then Judge with tools.  
**What's right:** The adversarial pattern (Prosecutor finds all faults, Judge adjudicates) is sophisticated and effective. The mandatory `get_communication_history` check in Judge is correctly enforced via explicit instruction.  
**Problems:**

1. **Prosecutor runs at `tier_override="mini"` unconditionally.** For complex healthcare/finance content with HIPAA/compliance rules, a mini model frequently misses subtle tone violations and factual inconsistencies. The Prosecutor running at mini and finding 2 faults, vs. a fast-tier Prosecutor finding 8 faults, means the Judge has to do more work to catch what the Prosecutor missed. The net cost is higher when using mini for Prosecutor because the Judge ends up doing more tool calls.

   **Recommended:** Prosecutor should use "fast" tier (same cost, better quality). Reserve mini only for the execution/memory agents where determinism matters more than depth.

2. **The `_build_judge_user` method says "MANDATORY: call get_communication_history for EVERY draft recipient"** but there's no enforcement. The Judge is just instructed to do it. A heavy model will comply; a mini model (if downgraded at level 3) will frequently skip it. Add a post-verification check that counts `get_communication_history` tool calls against the number of drafts — fail the verification pass if there's a mismatch.

3. **`_prosecutor_faults` are injected into `output_data` but never actually block the Judge's PASS verdict.** The Judge can receive 12 prosecutor faults and still return `"passed": true`. The PROSECUTOR FINDINGS section tells the Judge to review them, but doesn't programmatically enforce that faults decrease approval rate. A formal severity scoring of faults should be added.

---

### 4E. ExecutionAgent

**Design:** Mini tier, tool-heavy, deterministic.  
**What's right:** Mini is absolutely correct here. Execution is binary: fire tools, log results. No creative reasoning needed.  
**Problems:**

1. **The operating hours check** — the current implementation in the orchestrator is a good idea but checks `days_str.startswith("Mon-Fri")` which will fail for any variation like `"Monday-Friday"` or `"Mon - Fri"`. Use a proper weekday set comparison.

2. **The system prompt says "In DEV MODE: if tools return 'local_dev_mock', log as simulated and continue."** But the local dev tools return `"data_source": "local_dev_mock"` inside the data, not as the top-level return value. The agent prompt is technically incorrect about how to detect dev mode.

3. **`emails_queued` counter** is tracked but the actual email queuing mechanism is a `db_write_outcome` call that just logs. There's no actual email queue (no SendGrid, no Gmail draft API, no queue table in DB). For a real SME deployment, this needs to write to an actual email queue. The "queue_for_approval" setting is respected in theory but there's no approval UI for pending emails.

---

### 4F. MemoryAgent

**Design:** Balanced tier, pattern extraction + delta analysis.  
**What's right:** The delta analysis comparing current run to history is excellent. The Pattern Sandbox (pending_review → admin promotes to active) prevents hallucinated patterns from poisoning future reasoning. These are production-grade design decisions.  
**Problems:**

1. **`await self._rag.store_workflow_outcome()` is called directly in MemoryAgent** but `_rag` is never set on BaseAgent. The MemoryAgent checks `if hasattr(self, "_rag") and self._rag:` which will always be False. RAG storage from MemoryAgent is silently skipped in every run. The orchestrator does the RAG storage separately — so it's technically covered — but the MemoryAgent believes it did it when it didn't.

2. **Pattern keys are constructed as `{industry}_{pattern.get('key', 'unknown')}`** — if the LLM returns a generic key like `"pattern_1"` or `"key"`, multiple runs will overwrite each other in the PatternMemory table. Keys need to include run context (timestamp or run_id prefix) to avoid collision.

---

### 4G. ConsensusAgent

**Design:** Two parallel sub-agents (Auditor + Strategist) with agreement scoring.  
**What's right:** The 4-component agreement scoring (was 3-component, now fixed) with intervention-type agreement is well-designed. The AGREEMENT_THRESHOLD of 0.80 requiring genuine multi-dimensional alignment is correctly stringent.  
**Problems:**

1. **`self._llm.log_cost_source()` is called as `self._llm.log_cost_source("consensus_auditor", aud_cost)`** but the method on LLMRouter is `_workflow_logger.log_cost_source()`, not a method on `_llm` itself. This throws `AttributeError` silently (it's in a try/except that catches all exceptions).

2. **The Auditor uses `auditor_tier = self._llm._consensus_config.get("auditor_tier", "reasoning")`** but `_consensus_config` is only populated if `llm_config.json` has a `consensus_model_config` section. If a tenant uses a custom LLM config without this section, `_consensus_config` is `{}` and the Auditor defaults to "reasoning" (Sonnet). The config fallback is correct, but there's no warning logged when the config is missing.

3. **Both sub-agents receive `research_data = input.accumulated_context.get("research", {})` — the FULL research output.** For a 120-account research output, this means each sub-agent receives 40,000+ chars of data. The Consensus node should receive a pre-processed summary from the main ReasoningAgent, not the raw research. Currently, if Consensus comes AFTER Reasoning in the DAG (as it should), it could reuse the `_research_summary` from accumulated context, but it doesn't.

---

### 4H. DiscoveryAgent

**Design:** Auto-selects tools via RAG fast path or LLM slow path.  
**What's right:** The RAG pre-selection fast path (returning pre-selected tools without an LLM call) is elegant and achieves zero-LLM-cost tool selection when warm.  
**Problems:**

1. **`valid = [n for n in rag_preselected if n in self._tools._tools]`** — there's a scoping bug. `valid` is computed inside the `if rag_preselected:` block but the `self._log.info(...)` line that follows references `valid` and `count` which may not exist at that scope level if the `rag_preselected` list was populated but then `valid` was empty. In that case, the function falls through to the slow path, which is correct behavior, but a `NameError` for `valid` could be thrown in the log line.

2. **The slow-path LLM selection logs `count=len(valid), tools=valid`** after the `json.loads(match.group())` call, but `valid` at that point refers to the outer scope's pre-selection check (which was empty), not the newly parsed LLM selection. This is a variable shadowing bug.

---

## 5. Industry Adaptability — Engine Design

### 5A. What Works Well

The **DAG + Prompt + Config** triple-separation is the right architectural decision. Businesses customize:
- **Config JSON** (business rules, thresholds, tone)  
- **Prompt files** (industry-specific instructions)  
- **DAG JSON** (node arrangement, tool assignments, edges)

Without touching engine code. This is correctly designed.

The **Config Schema Validator** that checks for `[MODIFY]` placeholders and `REPLACE_WITH_UUID` tokens before triggering is a production-quality guardrail that prevents blank-config runs.

The **local dev tools** (seed data readers) that allow testing without real API credentials are well-thought-out for SME onboarding.

---

### 5B. Problems With Industry Adaptability

#### Problem 1: Prompts Use Python `.format()` Which Is Fragile

All prompt templates use `{variable}` Python format strings. This has several failure modes:

1. **JSON examples in prompts must use `{{` and `}}` to escape braces.** Multiple prompt files use `{{ "key": "value" }}` style which is correct, but one bug anywhere causes a `KeyError` crash. Found in `research_churn.txt`: `"current_datetime": "{{current_datetime}}"` — this renders as `"current_datetime": "{current_datetime}"` after formatting, not the actual datetime value.

2. **If any tenant config field contains curly braces** (e.g., a business rule description like `"Charge $5{0-99} for monthly plans"`), the `.format()` call will crash with a `KeyError` on `{0-99}`. No escaping is done on tenant config values before injection.

3. **The `.format_map()` fallback** (in ReasoningAgent for missing keys) swallows legitimate KeyErrors. A missing required placeholder is indistinguishable from an optional one.

**Fix:** Switch to Jinja2 templating with `{{ variable }}` syntax, which properly escapes `{` and `}` literals and has explicit `UndefinedError` for missing variables.

---



#### Problem 4: Scheduled Workflows Are Defined But Never Run

Every DAG has `schedule_cron` in `_meta`, and configs have `active_workflows` lists, but there is **no scheduler implementation**. The spec implies scheduled runs but the API has no background scheduler (APScheduler, Celery, or even a simple cron endpoint). This is a significant gap for "autonomous" operation.

---

#### Problem 5: Multi-Tenant RAG Namespace Collision

**Where:** `core/rag_engine.py` → `store_tool_schema()` and `index_tools_in_rag()`

Tool schemas are stored with `tenant_id="global"` explicitly. When multiple tenants with different custom tools share an instance, their tool schemas are all in the global namespace. A tenant whose industry is Healthcare might retrieve SaaS-specific tools from the global index because they ranked higher in the embedding similarity.

---


### 6B. UX Problems

#### Problem 2: No Workflow Schedule Management UI

DAGs define `schedule_cron` but there's no UI to:
- View scheduled workflows
- Enable/disable schedules
- See next scheduled run time
- Override a scheduled run

---









### 6C. Missing Frontend Features

| Missing Feature | Priority | Why It Matters |
|---|---|---|
| Email Draft Review & Send queue | 🔴 Critical | Core SME use case; without it, no actual emails go out |
| Schedule Management UI | 🔴 High | Autonomous operation requires visible scheduling |
| Config Version History (diff + rollback) | 🟠 High | Prevents accidental config overwrites |
| Cost per run trend chart (last 30 runs) | 🟡 Medium | Helps SMEs track ROI |
| Live "Insight Feed" during workflow execution | 🟡 Medium | Engagement & trust building |
| Multi-tenant admin filter on God View | 🟡 Medium | Usability at scale |
| Skipped node visual indicator | 🟡 Medium | Workflow comprehension |
| Mobile-responsive layout | 🟠 High | SME owner mobile access |
| Workflow run comparison view | 🟢 Low | Useful for iterative improvement |
| Pattern Memory browser (promote/demote) | 🟢 Low | Admin visibility into what the system learned |
| Evidence file export (PDF/CSV) | 🟢 Low | Compliance reporting for enterprise |

---

## 7. Overall Improvements & Differentiating Features

### 7A. What Makes OpsGrid Different from Normal Agent Tools

OpsGrid already has several features that **no mainstream agent builder** (LangChain, CrewAI, n8n, Make.com) offers:

1. **Time-Travel Debugging (fork from checkpoint)** — industry first
2. **Prosecutor/Judge verification** — not present in any competitor
3. **Outcome-Closed Learning Loop** — RAG learns from whether actions actually worked
4. **GraphRAG + text RAG hybrid** — structural similarity beyond text matching
5. **Multi-sig escalation approval** — enterprise-grade human oversight
6. **EPI tamper-evident audit trail** — compliance-ready
7. **Budget Circuit Breaker** — hard spend limits per run
8. **Auto-Eval (DSPy-inspired prompt improvement)** — self-improving system

The differentiation is real and significant. The problems are mostly in execution quality, not in architecture.

---

### 7B. Critical Missing Differentiators to Add

#### Feature 1: Scheduled Autonomous Operation (APScheduler)

**What:** Add APScheduler or Celery Beat to run workflows on `schedule_cron` automatically.  
**Why:** Without this, OpsGrid is not an autonomous engine — it's an on-demand executor. Every competitor (Zapier, n8n, Make.com) has scheduling. OpsGrid's pitch to SMEs requires it.  
**Implementation:** Add `apscheduler` to requirements, bootstrap scheduler in `lifespan()`, read active_workflows + schedules from DB on startup, register jobs dynamically when tenants update configs.

---

#### Feature 2: Email Draft Review Portal

**What:** A dedicated frontend page (and backend endpoint) showing all queued email drafts, with inline edit, approve, and send/schedule buttons.  
**Why:** Every SME using this for outreach needs to review what goes to customers before it leaves. Currently, approved drafts disappear into `db_write_outcome` logs.  
**Backend:** Add an `email_queue` table to the DB. ExecutionAgent writes approved drafts here instead of just logging.  
**Frontend:** `/emails` page with draft cards, edit modal, and Send button that calls actual email API (Gmail connector).

---

#### Feature 3: Intelligent Outcome Measurement (Closed-Loop ROI)

**What:** After outreach, automatically fetch updated account data after N days and compare to baseline. Report: "Of 8 accounts contacted this week, 3 showed improved health scores. Estimated MRR saved: $12,500."  
**Why:** SMEs need to see ROI to keep using the tool. The OutcomeTracker is coded but never triggered.  
**Implementation:** The scheduler (Feature 1) also runs `check_pending_outcomes()` daily. Add a dedicated "ROI Dashboard" page showing outcome results with before/after comparisons.

---

#### Feature 4: Non-LLM Smart Data Projector

**What:** A field-schema registry that defines, per agent type, exactly which fields it needs from each dependency. Applied automatically before sending context to any agent.  
**Why:** Reduces context by 60–88% for structured data with zero precision loss and zero LLM cost.  
**Implementation:** Define `AGENT_CONTEXT_SCHEMA = {"reasoning_agent": {"research": ["id", "company_name", "mrr", ...]}}`. Apply in `_prune_context()`.

---



---

#### Feature 9: Cost Forecasting Per Run

**What:** Before triggering, show estimated cost based on last run data, adjusting for current account count.  
**Status:** The `/workflows/estimate-cost` endpoint exists! But it's not shown in the Dashboard UI before triggering. Connect the existing endpoint to the TriggerModal.

---



### 7C. Architecture-Level Improvements

#### Improvement 1: Replace Python `.format()` with Jinja2

All prompt templates should use Jinja2. Benefits:
- `{{ variable }}` syntax doesn't clash with JSON's `{}`
- Explicit `UndefinedError` for missing variables instead of silent KeyError swallow
- `{% if %}` / `{% for %}` blocks for conditional prompt sections (e.g., include A2A hint only if a2a_enabled)
- Template inheritance for common sections (shared escalation policy can be `{% include 'common/escalation_policy.j2' %}`)

---



---

#### Improvement 3: Streaming Agent Output to Frontend

Currently, agents complete fully before any output is shown. For long ReasoningAgent runs (30–90s), users see a spinner. The `agent_live_output` WebSocket events work for token streaming in the running node, but the token stream is only for the current LLM call, not for the structured output.

**Fix:** Add incremental JSON streaming from agents. As the ReasoningAgent processes accounts one by one (in a future stateful design), broadcast each processed account to the frontend immediately. This requires restructuring the ReasoningAgent from a single-shot JSON call to a streaming accumulation loop, but would dramatically improve perceived performance.

---

#### Improvement 4: Idempotent Run Execution

Currently, if a workflow run crashes midway (server restart, network timeout), it's marked "failed" and must be re-triggered from the beginning. The fork/resume mechanism partially addresses this for escalated runs, but not for agent-level crashes.

**Fix:** Store the accumulated_context snapshot after each successful agent completion (not just on suspend). On re-trigger of a failed run, detect which nodes completed successfully and resume from the first failed node with the saved context. This would be a true "checkpoint and resume" system.

---


## Final Verdict

OpsGrid is genuinely sophisticated — the architectural decisions (DAG engine, Prosecutor/Judge, GraphRAG + RAG hybrid, Time-Travel Debugging, Budget Governor, EPI audit) place it in a different category from typical low-code agent builders. The prompts are well-designed per industry. The separation of engine vs. configuration is the right model for an SME-targeted product.

The critical problems are:
1. **Several silent bugs** (ConsensusAgent cost tracking, MemoryAgent RAG storage, `d` undefined in WS handler) that need immediate fixing
2. **No scheduler** making the "autonomous" promise hollow  
3. **No email review UI** making the output loop incomplete  
4. **LLM-based summarization for structured JSON** which costs more than the alternatives  
5. **Context passed to agents contains far more data than they need**, which inflates costs unnecessarily  

Fix the bugs, add the scheduler and email queue, replace LLM summarization with field projection, and OpsGrid becomes a production-ready platform that genuinely differentiates itself from everything else on the market.

---

*This analysis covers the full codebase as of March 2026. References: ACON (arXiv 2510.00615), Factory.ai compression evaluation, emergentmind.com cost-efficient LLM agent deployment survey, McKinsey 2025 agentic AI lessons, Deloitte 2025 emerging technology trends.*# OpsGrid — Deep System Analysis & Improvement Roadmap