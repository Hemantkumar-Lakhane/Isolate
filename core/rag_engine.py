"""
core/rag_engine.py
==================
Retrieval-Augmented Generation (RAG) engine.
 
Embedding priority:
  1. Local sentence-transformers (free, offline, dim=384 by default)
  2. OpenAI text-embedding-3-small (cloud, requires OPENAI_API_KEY, dim=1536)
  3. SHA-256 hash fallback (deterministic, NOT semantic — dev only)
 
Set LOCAL_EMBEDDING_MODEL env var to change model (default: all-MiniLM-L6-v2).
Set PREFER_LOCAL_EMBEDDINGS=false to force OpenAI when available.
 
CONSTANT — do not modify for business customization.
"""
 
from __future__ import annotations
 
import asyncio
import json
import os
import struct
import hashlib
from typing import Any, Optional
 
import structlog
 
log = structlog.get_logger()
 
 
import concurrent.futures

# ── Dedicated thread pool for ML inference ───────────────────────────────────
# Using the default asyncio pool (run_in_executor(None, ...)) causes CPU-heavy
# sentence-transformer inference to compete with I/O tasks (DB, network) and
# starve background orchestration tasks. A size-limited dedicated pool isolates
# ML work from the rest of the event loop.
_ML_THREAD_POOL: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("ML_THREAD_WORKERS", "2")),
    thread_name_prefix="opsgrid_embed",
)
TOOL_REGISTRY_ID = "00000000-0000-0000-0000-000000000000"
# ─────────────────────────────────────────────────────────────────────────────
# Embedding Configuration
# ─────────────────────────────────────────────────────────────────────────────
 
_LOCAL_MODEL_NAME = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_PREFER_LOCAL = os.getenv("PREFER_LOCAL_EMBEDDINGS", "true").lower() != "false"
_USE_OPENAI = bool(os.getenv("OPENAI_API_KEY")) and not _PREFER_LOCAL
 
# These are updated at runtime when the model loads
_EMBEDDING_DIM = 384       # Default for all-MiniLM-L6-v2
_OPENAI_DIM = 1536         # OpenAI text-embedding-3-small
 
# Global model cache (loaded once per process)
_local_encoder = None
_encoder_loaded = False
 
 
def _load_local_encoder():
    """Load sentence-transformers model (cached after first call)."""
    global _local_encoder, _encoder_loaded, _EMBEDDING_DIM
 
    if _encoder_loaded:
        return _local_encoder
 
    _encoder_loaded = True  # Mark as attempted even if it fails
 
    # Ensure the HF token is visible to the sentence-transformers / huggingface_hub
    # libraries regardless of which env-var name the operator used.
    _hf_token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_API_KEY")
        or os.getenv("HUGGINGFACE_TOKEN")
    )
    if _hf_token:
        os.environ.setdefault("HF_TOKEN", _hf_token)
        os.environ.setdefault("HUGGINGFACE_TOKEN", _hf_token)
 
    try:
        from sentence_transformers import SentenceTransformer
 
        # Pass token kwarg directly so the library doesn't need to re-read env
        kwargs = {}
        if _hf_token:
            kwargs["token"] = _hf_token
 
        _local_encoder = SentenceTransformer(_LOCAL_MODEL_NAME, **kwargs)
 
        # Probe actual output dimension
        test_emb = _local_encoder.encode("probe", show_progress_bar=False)
        _EMBEDDING_DIM = len(test_emb)
 
        log.info(
            "Local embedding model loaded",
            model=_LOCAL_MODEL_NAME,
            dim=_EMBEDDING_DIM,
        )
        return _local_encoder
 
    except ImportError:
        log.warning(
            "sentence-transformers not installed — local embeddings disabled. "
            "Run: pip install sentence-transformers"
        )
        return None
    except Exception as e:
        log.warning("Failed to load local embedding model", error=str(e))
        return None
 
async def _get_embedding(text: str) -> list[float]:
    """
    Generate a text embedding vector.
 
    Priority:
      1. Local sentence-transformers (free, fast, offline)
      2. OpenAI API (requires OPENAI_API_KEY and PREFER_LOCAL_EMBEDDINGS=false)
      3. Deterministic hash fallback (not semantic — development only)
    """
    # ── 1. Local sentence-transformers ────────────────────────────────────
    if _PREFER_LOCAL:
        encoder = _load_local_encoder()
        if encoder is not None:
            try:
                loop = asyncio.get_event_loop()
                embedding = await loop.run_in_executor(
                    _ML_THREAD_POOL,          # dedicated pool — never steals from I/O pool
                    lambda: encoder.encode(
                        text[:8192],
                        show_progress_bar=False,
                        normalize_embeddings=True,
                    ).tolist(),
                )
                return embedding
            except Exception as e:
                log.warning("Local embedding inference failed", error=str(e))
 
    # ── 2. OpenAI (cloud) ─────────────────────────────────────────────────
    if bool(os.getenv("OPENAI_API_KEY")):
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],
            )
            return response.data[0].embedding
        except Exception as e:
            log.warning("OpenAI embedding failed, using hash fallback", error=str(e))
 
    # ── 3. Hash fallback — deterministic but NOT semantic ─────────────────
    # Hash-based fallback removed — it produced semantically meaningless vectors
    # that caused cosine similarity to return garbage context to the Reasoning agent.
    # If both local and OpenAI embeddings fail, return empty list so callers
    # can skip RAG gracefully rather than inject misleading context.
    log.error(
        "All embedding methods failed. RAG will return empty results for this query. "
        "Install sentence-transformers: pip install sentence-transformers"
    )
    return []

# ─────────────────────────────────────────────────────────────────────────────
# RAG Engine
# ─────────────────────────────────────────────────────────────────────────────

class RAGEngine:
    """
    Manages semantic memory storage and retrieval for OpsGrid workflows.

    The "Lessons" Store:
      When MemoryAgent finishes → embed (situation + reasoning + outcome)
      Before ReasoningAgent starts → retrieve top-K similar past situations

    This enables:
      - Cross-workflow intelligence
      - Autonomous error recovery from past failures
      - Contextual tone matching for drafts
    """

    def __init__(self, db_session=None, llm_router=None):
        self._db = db_session
        self._llm = llm_router          # ← NEW: used for HyDE hypothesis generation
        self._in_memory_store: list[dict] = []
        self._use_db = db_session is not None
        self._workflow_logger = None

    
    def set_workflow_logger(self, logger) -> None:
        """Attach WorkflowSystemLogger for HyDE cost tracking."""
        self._workflow_logger = logger
    # ─────────────────────────────────────────────────────────────────────
    # Storage
    # ─────────────────────────────────────────────────────────────────────

    async def store_workflow_outcome(
        self,
        tenant_id: str,
        run_id: str,
        workflow_name: str,
        situation_summary: str,
        reasoning_chain: str,
        actions_taken: list[dict],
        outcome_indicator: str,   # "positive" | "negative" | "escalated"
        cost_usd: float = 0.0,
    ) -> None:
        """
        Store a completed workflow run as a RAG 'Lesson'.
        This is what makes OpsGrid learn from every run.
        """
        # Build rich content for embedding
        content = self._build_lesson_content(
            situation_summary, reasoning_chain, actions_taken, outcome_indicator
        )

        try:
            embedding = await _get_embedding(content)
        except Exception as e:
            log.warning("Embedding generation failed", error=str(e))
            embedding = [0.0] * _EMBEDDING_DIM
        if embedding:  # only deduplicate when we have a real embedding
            try:
                existing = await self.retrieve_similar_situations(
                    tenant_id=tenant_id,
                    query=content,
                    top_k=1,
                    content_type="outcome",
                )
                if existing and existing[0].get("similarity", 0) > 0.95:
                    log.debug(
                        "RAG: skipping near-duplicate lesson",
                        similarity=existing[0]["similarity"],
                        workflow=workflow_name,
                    )
                    return
            except Exception as _dup_e:
                log.debug("RAG dedup check failed (non-fatal)", error=str(_dup_e))

        metadata = {
            "workflow_name": workflow_name,
            "outcome": outcome_indicator,
            "actions": [a.get("action_id", str(a)) if isinstance(a, dict) else str(a) for a in (actions_taken or [])[:3]],
            "cost_usd": cost_usd,
        }

        if self._use_db:
            await self._db_store(
                tenant_id=tenant_id,
                run_id=run_id,
                workflow_name=workflow_name,
                content_type="outcome",
                content_text=content,
                embedding=embedding,
                metadata=metadata,
            )
        else:
            import time as _t
            self._in_memory_store.append({
                "tenant_id": tenant_id,
                "content_type": "outcome",
                "content_text": content,
                "embedding": embedding,
                "metadata": metadata,
                "workflow_name": workflow_name,
                "_stored_at": _t.time(),
            })

        log.info("RAG: Workflow outcome stored", tenant=tenant_id[:8], workflow=workflow_name)

    def _build_lesson_content(
        self,
        situation_summary: str,
        reasoning_chain: str,
        actions_taken: list,
        outcome_indicator: str,
    ) -> str:
        actions_str = ", ".join(
            a.get("action_id", str(a)) if isinstance(a, dict) else str(a)
            for a in (actions_taken or [])
        )
        return (
            f"OUTCOME: {outcome_indicator}\n"
            f"SITUATION: {situation_summary}\n"
            f"REASONING: {reasoning_chain}\n"
            f"ACTIONS: {actions_str}"
        )
    
    async def store_workflow_outcome_background(
        self,
        tenant_id: str,
        run_id: str,
        workflow_name: str,
        situation_summary: str,
        reasoning_chain: str,
        actions_taken: list,
        outcome_indicator: str,
        cost_usd: float = 0.0,
    ) -> None:
        """
        Non-blocking version of store_workflow_outcome.
        Fire-and-forget — does not block the workflow completion path.
        """
        asyncio.create_task(
            self.store_workflow_outcome(
                tenant_id=tenant_id,
                run_id=run_id,
                workflow_name=workflow_name,
                situation_summary=situation_summary,
                reasoning_chain=reasoning_chain,
                actions_taken=actions_taken,
                outcome_indicator=outcome_indicator,
                cost_usd=cost_usd,
            )
        )

    async def store_error_context(
        self,
        tenant_id: str,
        run_id: str,
        workflow_name: str,
        error_description: str,
        recovery_action: str,
    ) -> None:
        """Store error context so future runs can avoid the same failure."""
        content = f"ERROR CONTEXT: {error_description}\nRECOVERY: {recovery_action}"
        try:
            embedding = await _get_embedding(content)
        except Exception:
            embedding = [0.0] * _EMBEDDING_DIM

        if self._use_db:
            await self._db_store(
                tenant_id=tenant_id,
                run_id=run_id,
                workflow_name=workflow_name,
                content_type="error",
                content_text=content,
                embedding=embedding,
                metadata={"error": error_description[:200]},
            )
        else:
            self._in_memory_store.append({
                "tenant_id": tenant_id,
                "content_type": "error",
                "content_text": content,
                "embedding": embedding,
                "metadata": {"error": error_description[:200]},
            })
 
    async def store_human_correction(
        self,
        tenant_id: str,
        run_id: str,
        escalation_id: str,
        original_recommendation: str,
        human_action: str,
        context_brief: str,
        notes: str = "",
    ) -> None:
        """
        Store a human override as a high-priority 'Correction' lesson in RAG.
 
        When a human disagrees with the agent's recommended_action and picks
        a different action, that judgment is embedded and surfaced to future
        ReasoningAgent runs via get_historical_context_for_reasoning().
 
        This closes the human-in-the-loop feedback loop: agents learn what
        humans actually prefer for each type of situation.
        """
        content = (
            f"HUMAN_CORRECTION\n"
            f"Context: {context_brief[:600]}\n"
            f"Agent recommended: {original_recommendation or 'none'}\n"
            f"Human chose: {human_action}\n"
            f"Human notes: {notes or 'none'}\n"
            f"LESSON: For situations matching the above context, prefer "
            f"'{human_action}' over '{original_recommendation}'."
        )
 
        try:
            embedding = await _get_embedding(content)
        except Exception as e:
            log.warning("Human correction embedding failed", error=str(e))
            embedding = [0.0] * _EMBEDDING_DIM
 
        metadata = {
            "correction_type": "human_override",
            "original_recommendation": original_recommendation,
            "human_action": human_action,
            "escalation_id": escalation_id,
        }
 
        if self._use_db:
            await self._db_store(
                tenant_id=tenant_id,
                run_id=run_id,
                workflow_name="human_correction",
                content_type="correction",
                content_text=content,
                embedding=embedding,
                metadata=metadata,
            )
        else:
            self._in_memory_store.append({
                "tenant_id": tenant_id,
                "content_type": "correction",
                "content_text": content,
                "embedding": embedding,
                "metadata": metadata,
                "workflow_name": "human_correction",
            })
 
        log.info(
            "Human correction stored in RAG",
            tenant=tenant_id[:8],
            escalation_id=escalation_id,
            human_action=human_action,
            original=original_recommendation,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Retrieval
    # ─────────────────────────────────────────────────────────────────────

    async def retrieve_similar_situations(
        self,
        tenant_id: str,
        query: str,
        top_k: int = 3,
        content_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Semantic search: find past situations most similar to the current query.
        Uses HyDE (Hypothetical Document Embeddings) when an LLM is available
        to improve retrieval quality before falling back to cosine similarity.
        """
        # ── HyDE: embed a hypothetical answer, not the raw question ──────────
        hyde_query, hyde_cost = await self._generate_hypothetical_answer(query)
        # Track HyDE cost in workflow logger if available
        if hyde_cost > 0 and hasattr(self, '_workflow_logger') and self._workflow_logger:
            self._workflow_logger.mark_hyde(hyde_cost)
    
        try:
            query_embedding = await _get_embedding(hyde_query)
        except Exception as e:
            log.warning("HyDE query embedding failed — retrying with raw query", error=str(e))
            try:
                query_embedding = await _get_embedding(query)
            except Exception as e2:
                log.warning("Query embedding failed", error=str(e2))
                return []
    
        if self._use_db:
            return await self._db_search(tenant_id, query_embedding, top_k, content_type)
        else:
            return self._memory_search(tenant_id, query_embedding, top_k, content_type)

    async def get_historical_context_for_reasoning(
        self,
        tenant_id: str,
        situation_description: str,
        workflow_name: str,
    ) -> str:
        """
        Build a formatted historical context string for injection into ReasoningAgent prompt.
        Returns the top 3 most relevant past situations + what worked, plus any
        human correction lessons (highest priority — agent must follow these).
        """
        results = await self.retrieve_similar_situations(
            tenant_id=tenant_id,
            query=situation_description,
            top_k=3,
            content_type="outcome",
        )
 
        # Human corrections are surfaced separately and marked as HIGH PRIORITY
        corrections = await self.retrieve_similar_situations(
            tenant_id=tenant_id,
            query=situation_description,
            top_k=2,
            content_type="correction",
        )
 
        if results is None and corrections is None:
            return (
                "⚠️ HISTORICAL CONTEXT UNAVAILABLE — embedding service failed. "
                "Proceeding without learned patterns. "
                "Check sentence-transformers installation: pip install sentence-transformers"
            )
        if not results and not corrections:
            return "No historical context available for this tenant yet (early run)."
        # Log RAG retrieval stats for system logger
        total_found = len(results) + len(corrections)
        if hasattr(self, '_workflow_logger') and self._workflow_logger and total_found > 0:
            self._workflow_logger.mark_rag_injection(total_found)
        lines = ["=== HISTORICAL CONTEXT FROM PAST WORKFLOW RUNS ===",
                 "Use these lessons to inform your reasoning:\n"]
 
        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            similarity = r.get("similarity", 0.0)
            lines.append(f"Past Situation #{i} (similarity: {similarity:.0%}):")
            lines.append(r.get("content_text", "")[:500])
            if meta.get("outcome"):
                lines.append(f"Outcome: {meta['outcome']}")
            if meta.get("actions"):
                lines.append(f"Actions taken: {', '.join(meta['actions'])}")
            lines.append("")
 
        # Human correction lessons — highest-priority signal
        if corrections:
            lines.append("=== ⚠️ HUMAN OVERRIDE LESSONS — FOLLOW THESE ABOVE ALL ELSE ===")
            lines.append(
                "A human previously disagreed with an AI recommendation in a similar "
                "situation. You MUST weigh this guidance heavily:\n"
            )
            for i, c in enumerate(corrections, 1):
                similarity = c.get("similarity", 0.0)
                lines.append(f"Human Correction #{i} (similarity: {similarity:.0%}):")
                lines.append(c.get("content_text", "")[:500])
                lines.append("")
            lines.append("=== END HUMAN OVERRIDE LESSONS ===\n")
 
        lines.append("=== END HISTORICAL CONTEXT ===")
        return "\n".join(lines)

    async def get_error_recovery_hints(
        self,
        tenant_id: str,
        current_error: str,
    ) -> str:
        """Retrieve past error recovery patterns to help the current agent."""
        results = await self.retrieve_similar_situations(
            tenant_id=tenant_id,
            query=f"ERROR: {current_error}",
            top_k=2,
            content_type="error",
        )

        if not results:
            return ""

        if not results:
            return ""

        hints = ["Past error recovery context:"]
        for r in results:
            hints.append(f"- {r.get('content_text', '')[:300]}")
        return "\n".join(hints)

    # ── Tool RAG ──────────────────────────────────────────────────────────

    async def store_tool_schema(self, tool_name: str, description: str, tenant_id: str = "global") -> None:
        """
        Index a tool's name + description so DiscoveryAgent can retrieve
        the most relevant tools via semantic search instead of sending every
        schema to the LLM.

        Idempotent: duplicate tool_name entries in the in-memory store are
        silently skipped; the DB upsert relies on the run_id='tool_registry'
        sentinel so old entries are naturally overwritten per restart.
        """
        content = f"TOOL: {tool_name}\nDESCRIPTION: {description}"
        try:
            embedding = await _get_embedding(content)
        except Exception as e:
            log.warning("Tool schema embedding failed", tool=tool_name, error=str(e))
            return

        metadata = {"tool_name": tool_name}

        if self._use_db:
            await self._db_store(
                tenant_id=tenant_id,
                run_id=None, # FIX: Pass None so the DB sees NULL instead of a fake UUID
                workflow_name="tool_registry",
                content_type="tool_schema",
                content_text=content,
                embedding=embedding,
                metadata=metadata,
            )
        else:
            # Avoid duplicates in the in-memory store
            already = any(
                r.get("content_type") == "tool_schema"
                and r.get("metadata", {}).get("tool_name") == tool_name
                and r.get("tenant_id") == tenant_id
                for r in self._in_memory_store
            )
            if not already:
                self._in_memory_store.append({
                    "tenant_id": tenant_id,
                    "content_type": "tool_schema",
                    "content_text": content,
                    "embedding": embedding,
                    "metadata": metadata,
                    "workflow_name": "tool_registry",
                })

    async def retrieve_relevant_tools(
        self,
        query: str,
        tenant_id: str = "global",
        top_k: int = 8,
    ) -> list[str]:
        """
        Semantic search against the tool_schema index.
        Returns a list of tool *names* (not full schemas) ordered by relevance.
        Falls back to empty list on any error so callers can use the full list.
        """
        try:
            results = await self.retrieve_similar_situations(
                tenant_id=tenant_id,
                query=query,
                top_k=top_k,
                content_type="tool_schema",
            )
            names = [
                r["metadata"]["tool_name"]
                for r in results
                if r.get("metadata", {}).get("tool_name")
            ]
            log.debug("Tool RAG retrieval", query_preview=query[:60], found=names)
            return names
        except Exception as e:
            log.warning("retrieve_relevant_tools failed", error=str(e))
            return []

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    async def _generate_hypothetical_answer(self, query: str) -> tuple[str, float]:
        """
        HyDE step: generate a hypothetical 'Lesson Learned' document for the query.
        
        CHANGED: Now returns (hypothesis_text, cost_usd) so callers can track costs.
        Previously returned only the text — cost was invisibly lost (untracked leakage).
        
        Falls back to (raw query, 0.0) if the LLM is unavailable or fails.
        """
        if not self._llm:
            return query, 0.0
    
        from core.llm_router import LLMMessage
    
        system = (
            "You are a workflow outcome synthesizer. "
            "Given a business situation description, write a concise hypothetical "
            "'Lesson Learned' entry (3-5 sentences) as if a past workflow run had "
            "already handled this situation successfully. "
            "Include: what situation was detected, what action was taken, and what "
            "the measurable outcome was. Be specific and use business language. "
            "Do NOT say 'hypothetically' — write it as a factual past record."
        )
        user = (
            f"Situation: {query[:600]}\n\n"
            "Write the hypothetical past lesson for this situation."
        )
        messages = [
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=user),
        ]
        try:
            text, call = await self._llm.call(
                agent_name="hyde_rag",
                messages=messages,
                tier_override="mini",
            )
            cost = call.cost_usd
            log.debug(
                "HyDE hypothesis generated",
                original_len=len(query),
                hypo_len=len(text),
                cost=f"${cost:.5f}",
            )
            return text.strip() or query, cost
        except Exception as e:
            log.debug("HyDE generation failed — using raw query", error=str(e))
            return query, 0.0
    
    def _build_lesson_content(
        self,
        situation: str,
        reasoning: str,
        actions: list[dict],
        outcome: str,
    ) -> str:
        """Build rich textual content for embedding."""
        action_summary = "; ".join(
            a.get("action_id", "") for a in (actions or [])[:3]
        )
        return (
            f"SITUATION: {situation}\n"
            f"REASONING: {reasoning[:400] if reasoning else 'N/A'}\n"
            f"ACTIONS: {action_summary}\n"
            f"OUTCOME: {outcome}"
        )

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _memory_search(
        self,
        tenant_id: str,
        query_embedding: list[float],
        top_k: int,
        content_type: Optional[str],
    ) -> list[dict]:
        """In-memory cosine similarity search with Ebbinghaus time-decay."""
        import time as _time
        candidates = [
            r for r in self._in_memory_store
            if r.get("tenant_id") == tenant_id
            and (not content_type or r.get("content_type") == content_type)
        ]

        now = _time.time()
        scored = []
        for c in candidates:
            sim = self._cosine_similarity(query_embedding, c.get("embedding", []))
            # Time-decay: patterns not used/updated in >90 days decay to 10%
            age_days = (now - c.get("_stored_at", now)) / 86400
            decay = max(0.1, 1.0 - (age_days / 90) * 0.9) if age_days > 0 else 1.0
            scored.append({**c, "similarity": sim * decay, "_raw_similarity": sim})

        return sorted(scored, key=lambda x: x["similarity"], reverse=True)[:top_k]

    async def _db_store(self, tenant_id, run_id, workflow_name, content_type, content_text, embedding, metadata) -> None:
        try:
            from sqlalchemy import text
            from sqlalchemy.exc import IntegrityError
            embedding_str = f"[{','.join(str(v) for v in embedding)}]"
            
            # Ensure run_id is a string/UUID and not a "tool_registry" literal if it's the sentinel
            rid = str(run_id) if run_id else None
            
            # FIX: Handle "global" string by converting to None so Postgres accepts it as NULL
            tid = str(tenant_id) if tenant_id and tenant_id != "global" else None

            query = text("""
                INSERT INTO rag_embeddings 
                    (tenant_id, content_type, content_text, embedding, metadata, workflow_name, run_id)
                VALUES 
                    (:tid, :ct, :txt, CAST(:emb AS vector), CAST(:meta AS jsonb), :wf, :rid)
            """)
            params = {
                "tid": tid,
                "ct": content_type,
                "txt": content_text,
                "emb": embedding_str,
                "meta": json.dumps(metadata),
                "wf": workflow_name,
                "rid": rid,
            }

            try:
                await self._db.execute(query, params)
                await self._db.commit()
            except IntegrityError as e:
                await self._db.rollback()
                if "rag_embeddings_tenant_id_fkey" in str(e):
                    # Tenant doesn't exist in DB (e.g., CLI mock run). Retry with NULL tenant_id.
                    params["tid"] = None
                    try:
                        await self._db.execute(query, params)
                        await self._db.commit()
                    except Exception:
                        await self._db.rollback()
                else:
                    log.debug("RAG DB store integrity error (non-fatal)", error=str(e))
            except Exception as e:
                await self._db.rollback()
                log.debug("RAG DB store skipped (non-fatal)", error=str(e))
        except Exception as e:
            if self._db:
                await self._db.rollback()
            log.debug("RAG DB store error", error=str(e))

    async def _db_search(self, tenant_id, query_embedding, top_k, content_type):
        """
        Two-pass search: ANN via IVFFlat index, then Python re-rank with time decay.
        
        BUG-003 FIX: The previous single-pass ORDER BY with a computed expression
        (embedding_distance * time_decay) prevented the IVFFlat index from being used,
        causing a full sequential scan. Now:
          Pass 1 — use the index to get top_k * 4 candidates (fast, O(log n))
          Pass 2 — re-rank in Python with time decay (no index penalty)
        """
        if not query_embedding:
            return []
        try:
            from sqlalchemy import text
            from datetime import datetime as _dt
            embedding_str = f"[{','.join(str(v) for v in query_embedding)}]"
 
            # Build filter clause — tool_schema queries also search "global" tenant
            if content_type == "tool_schema":
                ct_filter = "AND content_type = 'tool_schema' AND (tenant_id = :tid OR tenant_id = 'global')"
            elif content_type:
                ct_filter = "AND content_type = :ct AND tenant_id = :tid"
            else:
                ct_filter = "AND tenant_id = :tid"
 
            # Pass 1: fast ANN — retrieve more candidates than needed for re-ranking
            candidates_sql = text(f"""
                SELECT id, content_type, content_text, metadata, workflow_name,
                       created_at,
                       1 - (embedding <=> CAST(:qvec AS vector)) AS raw_similarity
                FROM rag_embeddings
                WHERE 1=1 {ct_filter}
                ORDER BY embedding <=> CAST(:qvec AS vector)
                LIMIT :k
            """)
            result = await self._db.execute(
                candidates_sql,
                {"qvec": embedding_str, "tid": tenant_id, "k": top_k * 4, "ct": content_type},
            )
            rows = result.fetchall()
 
            if not rows:
                return []
 
            # Pass 2: Python re-rank with Ebbinghaus time decay
            now = _dt.utcnow()
            scored = []
            for r in rows:
                # FIX: SELECT order is id(0), content_type(1), content_text(2),
                # metadata(3), workflow_name(4), created_at(5), raw_similarity(6)
                raw_sim = float(r[6]) if r[6] is not None else 0.0
                created_at = r[5]

                age_days = 0.0
                if created_at:
                    try:
                        age_days = (now - created_at.replace(tzinfo=None)).total_seconds() / 86400
                    except Exception:
                        pass
                decay = max(0.1, 1.0 - (age_days / 90) * 0.9) if age_days > 0 else 1.0
                final_score = raw_sim * decay
                scored.append((final_score, r))
 
            scored.sort(key=lambda x: x[0], reverse=True)
 
            return [
                {
                    "id": str(r[0]),
                    "content_type": r[1],
                    "content_text": r[2],
                    "metadata": r[3] or {},
                    "workflow_name": r[4],
                    "similarity": round(score, 4),
                }
                for score, r in scored[:top_k]
            ]
        except Exception as e:
            log.error("RAG DB search failed", error=str(e))
            return []