"""
core/visual_brief_builder.py
=============================
Visual Brief Builder for SMBFlow Product Launch image generation.

Enforces Source Priority:
1. Approved User Input (highest priority ground truth)
2. Approved / Extracted Document Facts
3. Visual Direction / Prompt Instructions (lowest priority)

Separates Product Facts from Visual Direction.
Preserves exact product and feature names verbatim.
"""

from typing import Any, Dict, List, Optional
import structlog

log = structlog.get_logger()


class VisualBriefBuilder:
    """
    Constructs a grounded, structured visual brief from approved Product Launch data.
    Ensures provider prompts (Gemini & Pollinations) are strictly grounded in fact.
    """

    @staticmethod
    def build_brief(
        product_brief: Dict[str, Any],
        visual_role: str,
        platform: str = "LinkedIn",
        aspect_ratio: str = "16:9",
        visual_prompt: Optional[str] = None,
        placement: Optional[str] = None,
    ) -> Dict[str, Any]:
        brief = product_brief or {}

        # ── 1. SOURCE PRIORITY 1: APPROVED USER INPUT ─────────────────────────
        product_name = (
            brief.get("productName")
            or brief.get("product_name")
            or "SMB Product Launch"
        ).strip()

        short_desc = (brief.get("shortDescription") or brief.get("product_description") or "").strip()
        target_audience = (brief.get("targetAudience") or brief.get("audience") or "").strip()
        customer_type = (brief.get("customerType") or "B2B").strip()
        value_prop = (brief.get("valueProposition") or "").strip()
        cta = (brief.get("desiredCta") or brief.get("cta") or "").strip()

        # Features & Benefits
        features = []
        raw_features = brief.get("keyFeatures") or brief.get("approved_features") or []
        if isinstance(raw_features, str):
            features = [f.strip() for f in raw_features.split(",") if f.strip()]
        elif isinstance(raw_features, list):
            features = [str(f).strip() for f in raw_features if str(f).strip()]

        benefits = []
        raw_benefits = brief.get("topBenefit1") or brief.get("approved_benefits") or []
        if isinstance(raw_benefits, str):
            benefits = [b.strip() for b in raw_benefits.split(",") if b.strip()]
        elif isinstance(raw_benefits, list):
            benefits = [str(b).strip() for b in raw_benefits if str(b).strip()]

        source_fields = ["productName"]
        if short_desc: source_fields.append("shortDescription")
        if target_audience: source_fields.append("targetAudience")
        if value_prop: source_fields.append("valueProposition")
        if features: source_fields.append("keyFeatures")
        if benefits: source_fields.append("topBenefit1")

        # ── 2. SOURCE PRIORITY 2: EXTRACTED DOCUMENT FACTS ───────────────────
        doc_text = brief.get("document_text") or ""
        doc_facts = []
        if doc_text:
            source_fields.append("uploaded_document")
            doc_lines = [line.strip() for line in doc_text.splitlines() if line.strip() and len(line.strip()) > 10]
            doc_facts = doc_lines[:3]

        # ── 3. SOURCE PRIORITY 3: VISUAL DIRECTION ───────────────────────────
        direction = (visual_prompt or "").strip()

        # Visual Role Intelligence
        role_key = (visual_role or "Product Hero").strip()
        objective, composition = VisualBriefBuilder._get_role_composition(role_key, product_name, platform, aspect_ratio)

        # Exact text rules
        exact_text = [product_name] if product_name else []

        structured_brief = {
            "product": {
                "name": product_name,
                "short_description": short_desc,
                "approved_features": features,
                "approved_benefits": benefits,
                "value_proposition": value_prop,
            },
            "audience": {
                "target_audience": target_audience,
                "customer_type": customer_type,
            },
            "visual_meta": {
                "visual_role": role_key,
                "platform": platform,
                "aspect_ratio": aspect_ratio,
                "placement": placement or f"{platform} campaign post visual",
            },
            "grounded_facts": {
                "approved_claims": [value_prop] + benefits if value_prop else benefits,
                "document_facts": doc_facts,
                "exact_text": exact_text,
                "cta": cta,
            },
            "visual_direction": {
                "objective": objective,
                "composition": composition,
                "raw_direction": direction,
            },
            "negative_constraints": [
                f"Do not misspell, alter, or paraphrase product name '{product_name}'.",
                "Do not invent unapproved features, pricing, statistics, partner logos, or fake claims.",
                "Prefer clean visual design with minimal typography when text rendering cannot be guaranteed.",
                "Do not place floating random text or hallucinated bullet points inside the image.",
            ],
            "source_fields": source_fields,
        }

        # Format provider-agnostic grounded prompt
        grounded_prompt = VisualBriefBuilder.format_grounded_prompt(structured_brief)
        structured_brief["formatted_grounded_prompt"] = grounded_prompt

        log.info("VisualBriefBuilder created brief", product=product_name, role=role_key, platform=platform)
        return structured_brief

    @staticmethod
    def _get_role_composition(role: str, product_name: str, platform: str, aspect_ratio: str) -> (str, str):
        """Generates composition instructions tailored to visual role and platform placement."""
        role_lower = role.lower()
        
        if "hero" in role_lower or "launch" in role_lower:
            objective = f"Hero announcement visual introducing {product_name}."
            composition = (
                f"Sleek commercial product hero presentation for {platform} ({aspect_ratio}). "
                f"Central prominent focus on {product_name} with premium studio lighting, subtle depth of field, clean background."
            )
        elif "workflow" in role_lower or "feature" in role_lower:
            objective = f"Feature visualization for {product_name}."
            composition = (
                f"Clean modern UI interface graphic for {platform} ({aspect_ratio}). "
                f"Clear visual representation of software workflow cards, automation paths, or product dashboard elements."
            )
        elif "problem" in role_lower or "context" in role_lower:
            objective = f"Problem-solution context for {product_name}."
            composition = (
                f"Contextual workplace scene for {platform} ({aspect_ratio}). "
                f"Professional atmosphere showing productivity enhancement, modern office or remote setup."
            )
        else:
            objective = f"Marketing visual for {product_name}."
            composition = (
                f"High-quality commercial marketing graphic for {platform} ({aspect_ratio}) with clean balance and modern aesthetic."
            )

        return objective, composition

    @staticmethod
    def format_grounded_prompt(structured_brief: Dict[str, Any], provider: str = "default") -> str:
        """
        Formats structured brief into grounded prompt text.
        Identical core factual intent across providers, with minimal optional formatting if needed.
        """
        prod = structured_brief["product"]
        name = prod["name"]
        vis = structured_brief["visual_meta"]
        direct = structured_brief["visual_direction"]

        parts = []

        # 1. Product Grounding (Verbatim product name + approved description)
        parts.append(f"Product: '{name}'.")
        if prod.get("short_description"):
            parts.append(f"Description: {prod['short_description']}.")
        if prod.get("approved_features"):
            features_str = ", ".join(prod["approved_features"][:3])
            parts.append(f"Key Features: {features_str}.")

        # 2. Visual Role & Placement
        parts.append(f"Role: {vis['visual_role']}.")
        parts.append(f"Platform: {vis['platform']} ({vis['aspect_ratio']}).")

        # 3. Visual Direction
        if direct.get("composition"):
            parts.append(f"Composition: {direct['composition']}")
        if direct.get("raw_direction"):
            parts.append(f"Visual details: {direct['raw_direction']}")

        # 4. Strict Text & Fact Grounding Rules
        parts.append(f"Text rule: Use exact spelling '{name}'. Do not alter, paraphrase, or misspell '{name}'.")
        parts.append("Negative constraints: Do not invent fake statistics, unapproved features, pricing, or hallucinated claims.")

        return " ".join(parts)
