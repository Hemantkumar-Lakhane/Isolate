"""
core/graph_rag.py
=================
GraphRAG: Knowledge Graph augmented retrieval using NetworkX.

Instead of storing flat text chunks, we build a typed knowledge graph where:
  - Nodes = entities (accounts, patterns, agents, actions, outcomes)
  - Edges = relationships (similar_to, led_to, preceded_by, escalated_to)

This enables the Reasoning Agent to query: "find accounts structurally similar
to this one" and get accounts that share the same risk profile, not just ones
that appeared in similar text.

Integration:
  1. Call graph_rag.add_entity() after each MemoryAgent run.
  2. Call graph_rag.find_similar_entities() before ReasoningAgent to enrich context.
  3. Graph is per-tenant and stored in-memory (persisted to DB optionally).

Usage:
    from core.graph_rag import GraphRAGEngine

    graph = GraphRAGEngine()
    await graph.add_workflow_outcome(tenant_id, outcome_data)
    similar = await graph.find_similar_accounts(tenant_id, current_account_data)

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Optional

import structlog

log = structlog.get_logger()

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False
    log.warning("networkx not installed — GraphRAG disabled. Run: pip install networkx")


class GraphRAGEngine:
    """
    Knowledge graph for cross-workflow intelligence.

    Stores typed nodes (accounts, patterns, outcomes, agents) and edges
    (relationships between them). Enables structural similarity queries
    that raw text-embedding RAG cannot answer.

    Example queries:
      - "Find accounts similar to this one based on churn signal structure"
      - "What patterns led to positive outcomes in the past?"
      - "Which agent decisions correlated with escalation?"
    """

    def __init__(self):
        if not _NX_AVAILABLE:
            self._graph: Any = None
            return
        self._graphs: dict[str, Any] = {}  # tenant_id -> nx.DiGraph

    def _get_graph(self, tenant_id: str):
        if not _NX_AVAILABLE:
            return None
        if tenant_id not in self._graphs:
            self._graphs[tenant_id] = nx.DiGraph()
        return self._graphs[tenant_id]

    # ─────────────────────────────────────────────────────────────────────
    # Entity storage
    # ─────────────────────────────────────────────────────────────────────

    async def add_account(
        self,
        tenant_id: str,
        account_id: str,
        account_data: dict,
    ) -> None:
        """
        Add or update an account node with its risk features.
        Features are normalized for structural similarity comparison.
        """
        G = self._get_graph(tenant_id)
        if G is None:
            return

        features = self._extract_account_features(account_data)
        node_id = f"account:{account_id}"

        G.add_node(
            node_id,
            type="account",
            entity_id=account_id,
            label=account_data.get("company_name", account_id),
            features=features,
            mrr=account_data.get("mrr", 0),
            tier=account_data.get("tier", "unknown"),
            health_label=account_data.get("health_label", account_data.get("_health_label", "unknown")),
            updated_at=datetime.utcnow().isoformat(),
        )
        log.debug("GraphRAG: account node added", account=account_id, tenant=tenant_id[:8])

    async def add_pattern(
        self,
        tenant_id: str,
        pattern_key: str,
        pattern_data: dict,
    ) -> None:
        """Add a learned pattern node."""
        G = self._get_graph(tenant_id)
        if G is None:
            return

        node_id = f"pattern:{pattern_key}"
        G.add_node(
            node_id,
            type="pattern",
            entity_id=pattern_key,
            label=pattern_data.get("description", pattern_key)[:80],
            outcome=pattern_data.get("outcome_indicator", "neutral"),
            value=pattern_data.get("value"),
            updated_at=datetime.utcnow().isoformat(),
        )
        
    async def add_listing(
        self,
        tenant_id: str,
        listing_id: str,
        listing_data: dict,
    ) -> None:
        """
        Add or update a listing node with RE-specific risk features.
        Features are normalized for structural similarity comparison.
        """
        G = self._get_graph(tenant_id)
        if G is None:
            return

        features = self._extract_listing_features(listing_data)
        node_id = f"listing:{listing_id}"

        G.add_node(
            node_id,
            type="listing",
            entity_id=listing_id,
            label=listing_data.get("address", listing_id),
            features=features,
            price=listing_data.get("price", 0),
            status=listing_data.get("status", "active"),
            risk_label=listing_data.get("_risk_label", "active"),
            updated_at=datetime.utcnow().isoformat(),
        )
        log.debug("GraphRAG: listing node added", listing=listing_id, tenant=tenant_id[:8])

    async def add_workflow_outcome(
        self,
        tenant_id: str,
        run_id: str,
        outcome_data: dict,
        account_ids: Optional[list[str]] = None,
        pattern_keys: Optional[list[str]] = None,
    ) -> None:
        """
        Add a workflow outcome node and connect it to related accounts/patterns.
        This builds the causal edges: account → outcome, pattern → outcome.
        """
        G = self._get_graph(tenant_id)
        if G is None:
            return

        outcome_node = f"outcome:{run_id}"
        G.add_node(
            outcome_node,
            type="outcome",
            entity_id=run_id,
            label=outcome_data.get("situation_summary", "Workflow outcome")[:80],
            status=outcome_data.get("status", "unknown"),
            urgency=outcome_data.get("urgency", "unknown"),
            cost_usd=outcome_data.get("total_cost_usd", 0),
            created_at=datetime.utcnow().isoformat(),
        )

        # Connect accounts to this outcome
        for acc_id in (account_ids or []):
            acc_node = f"account:{acc_id}"
            if G.has_node(acc_node):
                G.add_edge(acc_node, outcome_node, relation="involved_in",
                           weight=1.0, at=datetime.utcnow().isoformat())

        # Connect patterns that were active during this run
        for pk in (pattern_keys or []):
            pat_node = f"pattern:{pk}"
            if G.has_node(pat_node):
                G.add_edge(pat_node, outcome_node, relation="applied_in",
                           weight=1.0, at=datetime.utcnow().isoformat())

    # ─────────────────────────────────────────────────────────────────────
    # Similarity queries
    # ─────────────────────────────────────────────────────────────────────

    async def find_similar_accounts(
        self,
        tenant_id: str,
        query_account: dict,
        top_k: int = 5,
        min_similarity: float = 0.4,
    ) -> list[dict]:
        """
        Find accounts structurally similar to the query account.

        Similarity is computed over normalized risk features:
        churn_score, usage_trend, support_tickets, nps_score, mrr_tier.
        This is a feature-vector similarity, not text similarity.

        Returns list of {account_id, company_name, similarity, health_label, ...}
        """
        G = self._get_graph(tenant_id)
        if G is None:
            return []

        query_features = self._extract_account_features(query_account)
        results = []

        for node_id, attrs in G.nodes(data=True):
            if attrs.get("type") != "account":
                continue
            stored_features = attrs.get("features", {})
            if not stored_features:
                continue

            sim = self._feature_similarity(query_features, stored_features)
            if sim >= min_similarity:
                results.append({
                    "account_id":    attrs.get("entity_id"),
                    "company_name":  attrs.get("label"),
                    "health_label":  attrs.get("health_label"),
                    "mrr":           attrs.get("mrr"),
                    "tier":          attrs.get("tier"),
                    "similarity":    round(sim, 3),
                    "graph_context": self._get_account_context(G, node_id),
                })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    async def find_successful_patterns(
        self,
        tenant_id: str,
        context_description: str = "",
        top_k: int = 5,
    ) -> list[dict]:
        """
        Find patterns that historically led to positive outcomes.
        Returns patterns sorted by their connection to successful outcomes.
        """
        G = self._get_graph(tenant_id)
        if G is None:
            return []

        pattern_scores: dict[str, dict] = {}

        for node_id, attrs in G.nodes(data=True):
            if attrs.get("type") != "pattern":
                continue
            # Count successfull outcomes connected to this pattern
            positive = 0
            negative = 0
            for successor in G.successors(node_id):
                succ_attrs = G.nodes[successor]
                if succ_attrs.get("type") == "outcome":
                    if succ_attrs.get("status") in ("completed", "positive"):
                        positive += 1
                    else:
                        negative += 1

            total = positive + negative
            if total == 0:
                continue

            success_rate = positive / total
            pattern_scores[node_id] = {
                "pattern_key":   attrs.get("entity_id"),
                "description":   attrs.get("label"),
                "outcome":       attrs.get("outcome"),
                "success_rate":  round(success_rate, 3),
                "total_applied": total,
                "value":         attrs.get("value"),
            }

        sorted_patterns = sorted(pattern_scores.values(), key=lambda x: x["success_rate"], reverse=True)
        return sorted_patterns[:top_k]

    async def get_graph_context_for_reasoning(
        self,
        tenant_id: str,
        current_accounts: list[dict],
        top_k_similar: int = 3,
    ) -> str:
        """
        Build a structured graph context string for injection into the Reasoning Agent.
        Finds structurally similar past accounts and what interventions worked.
        """
        if not _NX_AVAILABLE:
            return ""

        G = self._get_graph(tenant_id)
        if G is None or G.number_of_nodes() == 0:
            return ""

        lines = ["=== GRAPHRAG STRUCTURAL CONTEXT ===",
                 "Accounts structurally similar to current at-risk accounts:\n"]

        for acc in current_accounts[:5]:
            similar = await self.find_similar_accounts(tenant_id, acc, top_k=top_k_similar)
            if not similar:
                continue
            lines.append(f"For {acc.get('company_name', acc.get('id', '?'))}:")
            for s in similar:
                ctx = s.get("graph_context", {})
                lines.append(
                    f"  • {s['company_name']} (similarity: {s['similarity']:.0%}, "
                    f"label: {s['health_label']}, mrr: ${s['mrr']:,})"
                )
                if ctx.get("past_outcomes"):
                    lines.append(f"    → Past outcomes: {', '.join(ctx['past_outcomes'][:3])}")
            lines.append("")

        successful = await self.find_successful_patterns(tenant_id, top_k=3)
        if successful:
            lines.append("Patterns with highest historical success rate:")
            for p in successful:
                lines.append(
                    f"  • {p['description']} "
                    f"(success: {p['success_rate']:.0%}, n={p['total_applied']})"
                )

        lines.append("=== END GRAPHRAG CONTEXT ===")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────
    # Graph statistics
    # ─────────────────────────────────────────────────────────────────────

    def get_graph_stats(self, tenant_id: str) -> dict:
        G = self._get_graph(tenant_id)
        if G is None:
            return {"available": False}
        return {
            "available": True,
            "nodes":   G.number_of_nodes(),
            "edges":   G.number_of_edges(),
            "accounts": sum(1 for _, d in G.nodes(data=True) if d.get("type") == "account"),
            "patterns": sum(1 for _, d in G.nodes(data=True) if d.get("type") == "pattern"),
            "outcomes": sum(1 for _, d in G.nodes(data=True) if d.get("type") == "outcome"),
        }

    # ─────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────

    def _extract_account_features(self, account: dict) -> dict:
        """
        Extract and normalize risk features from an account dict.
        Returns a fixed-dimension feature vector as a dict.
        """
        usage  = account.get("usage", {})
        support = account.get("support", {})
        nps    = account.get("nps", {})
        mrr    = account.get("mrr", 0) or 0

        # Normalize MRR to a 0-1 scale (cap at 20k)
        mrr_norm = min(1.0, mrr / 20_000)

        # DAU trend: normalize from [-1, 1] range
        dau_trend = (usage.get("dau_trend_pct", 0) or 0) / 100.0
        dau_trend_norm = (dau_trend + 1.0) / 2.0  # shift to [0, 1]

        # Last login: normalize to [0, 1] where 1 = 30+ days ago
        last_login = min(30, usage.get("last_login_days_ago", 0) or 0) / 30.0

        # Support tickets: normalize (cap at 10)
        tickets = min(10, support.get("tickets_30d", 0) or 0) / 10.0

        # NPS: normalize from [0, 10] to [0, 1]
        nps_score = (nps.get("score", 7) if isinstance(nps, dict) else nps or 7)
        nps_norm = (nps_score or 7) / 10.0

        # Features adoption
        features = account.get("usage", {})
        adopted = features.get("features_adopted", 5) if isinstance(features, dict) else 5
        available = features.get("features_available", 15) if isinstance(features, dict) else 15
        adoption_norm = min(1.0, (adopted or 5) / max(1, available or 15))

        return {
            "mrr_norm":        mrr_norm,
            "dau_trend_norm":  max(0.0, min(1.0, dau_trend_norm)),
            "last_login_norm": last_login,
            "tickets_norm":    tickets,
            "nps_norm":        nps_norm,
            "adoption_norm":   adoption_norm,
        }
    
    def _extract_listing_features(self, listing: dict) -> dict:
        """
        Extract and normalize risk features from a real estate listing.
        Returns a fixed-dimension feature vector for structural similarity.
        """
        dom = listing.get("days_on_market", 0) or 0
        showings = listing.get("showing_count", 0) or 0
        price_reductions = listing.get("price_reductions", 0) or 0
        list_price = listing.get("price", 0) or 1  # avoid div/zero
        orig_price = listing.get("original_price", list_price) or list_price
        showing_feedback_negative = listing.get("negative_feedback_count", 0) or 0
        offers_received = listing.get("offers_received", 0) or 0

        # Normalize all features to [0, 1]
        dom_norm = min(1.0, dom / 180.0)                         # cap at 180 days
        showings_norm = min(1.0, showings / 30.0)                # 30+ = fully shown
        price_drop_pct = max(0.0, (orig_price - list_price) / orig_price)
        price_drop_norm = min(1.0, price_drop_pct / 0.20)        # 20% drop = max
        neg_feedback_norm = min(1.0, showing_feedback_negative / max(showings, 1))
        offers_norm = min(1.0, offers_received / 3.0)            # 3+ offers = max

        return {
            "dom_norm":          dom_norm,
            "showings_norm":     showings_norm,
            "price_drop_norm":   price_drop_norm,
            "neg_feedback_norm": neg_feedback_norm,
            "offers_norm":       offers_norm,
        }

    @staticmethod
    def _feature_similarity(a: dict, b: dict) -> float:
        """Cosine similarity between two feature dicts."""
        keys = set(a) | set(b)
        if not keys:
            return 0.0
        vec_a = [a.get(k, 0.0) for k in keys]
        vec_b = [b.get(k, 0.0) for k in keys]
        dot   = sum(x * y for x, y in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(x * x for x in vec_a))
        norm_b = math.sqrt(sum(x * x for x in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _get_account_context(self, G, node_id: str) -> dict:
        """Get the outcome history connected to an account node."""
        past_outcomes = []
        for successor in G.successors(node_id):
            attrs = G.nodes[successor]
            if attrs.get("type") == "outcome":
                past_outcomes.append(attrs.get("status", "unknown"))
        return {"past_outcomes": past_outcomes}