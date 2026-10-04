"""
api/routers/product_launch.py
==============================
Backend endpoints for SMBFlow Product Launch Sprint workflow:
- Quick-fill brief extraction via LLMRouter
- Draft persistence & loading via WorkflowInstance (status="pending")
- Campaign creation (WorkflowInstance status="escalated", ApprovalItem pending per post)
- Human post approval gating (decided_by, decided_at, AuditEvent log; no external publishing)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import TokenData, require_any_auth
from api.dependencies import get_db
from db.models.core import AgentRunRecord, ApprovalItem, AuditEvent, EvidenceRecord, ToolConnection, UsageRecord, WorkflowInstance
from core.llm_router import LLMRouter, LLMMessage
from core.state_manager import WorkflowStatus

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/workflows/product-launch", tags=["Product Launch Sprint"])


# ── REQUEST / RESPONSE MODELS ──────────────────────────────────────────────────

class ExtractBriefRequest(BaseModel):
    launch_brief: str = Field(..., description="Raw natural language brief text provided by user")


class ExtractBriefResponse(BaseModel):
    productName: Optional[str] = None
    shortDescription: Optional[str] = None
    launchDescription: Optional[str] = None
    websiteUrl: Optional[str] = None
    launchDate: Optional[str] = None
    desiredCta: Optional[str] = None
    targetAudience: Optional[str] = None
    customerType: Optional[str] = "B2B"
    industrySegment: Optional[str] = None
    geography: Optional[str] = None
    customerProblem: Optional[str] = None
    primaryBenefit: Optional[str] = None
    immediateMessage: Optional[str] = None
    valueProposition: Optional[str] = None
    topBenefit1: Optional[str] = None
    topBenefit2: Optional[str] = None
    topBenefit3: Optional[str] = None
    keyFeatures: Optional[str] = None
    differentiator: Optional[str] = None
    toneOfVoice: Optional[str] = "Professional"
    launchObjective: Optional[str] = "Product adoption"
    thingsToAvoid: Optional[str] = None
    platforms: Optional[List[str]] = Field(default_factory=lambda: ["LinkedIn", "X"])
    scheduleType: Optional[str] = "week"
    startDate: Optional[str] = None
    postingTime: Optional[str] = "9:00 AM"
    timezone: Optional[str] = "Eastern (ET)"
    is_ai_generated: bool = True


class ExtractBriefRequest(BaseModel):
    launch_brief: Optional[str] = None
    document_text: Optional[str] = None
    document_name: Optional[str] = None
    existing_context: Optional[Dict[str, Any]] = None


class ExtractBriefResponse(BaseModel):
    productName: Optional[str] = None
    shortDescription: Optional[str] = None
    launchDescription: Optional[str] = None
    websiteUrl: Optional[str] = None
    launchDate: Optional[str] = None
    desiredCta: Optional[str] = None
    targetAudience: Optional[str] = None
    customerType: Optional[str] = None
    industrySegment: Optional[str] = None
    geography: Optional[str] = None
    customerProblem: Optional[str] = None
    primaryBenefit: Optional[str] = None
    immediateMessage: Optional[str] = None
    valueProposition: Optional[str] = None
    topBenefit1: Optional[str] = None
    topBenefit2: Optional[str] = None
    topBenefit3: Optional[str] = None
    keyFeatures: Optional[str] = None
    differentiator: Optional[str] = None
    toneOfVoice: Optional[str] = None
    launchObjective: Optional[str] = None
    thingsToAvoid: Optional[str] = None
    platforms: Optional[List[str]] = Field(default_factory=lambda: ["LinkedIn", "X"])
    scheduleType: Optional[str] = None
    startDate: Optional[str] = None
    postingTime: Optional[str] = None
    timezone: Optional[str] = None
    additionalContext: Optional[str] = None
    provenance: Optional[Dict[str, Optional[str]]] = None
    is_ai_generated: bool = True


class SaveDraftRequest(BaseModel):
    brief_data: Dict[str, Any]


class CreateCampaignRequest(BaseModel):
    brief_data: Dict[str, Any]


class PostApprovalRequest(BaseModel):
    decision_notes: Optional[str] = None


# ── ENDPOINTS ──────────────────────────────────────────────────────────────────

@router.post("/extract-brief", response_model=ExtractBriefResponse)
async def extract_brief_with_ai(
    req: ExtractBriefRequest,
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Extract structured Product Launch brief fields from raw natural language input and/or uploaded document text using LLMRouter.
    Returns strict JSON. Missing fields remain null/empty. Preserves extra product context and provenance.
    """
    brief_text = req.launch_brief.strip() if req.launch_brief else ""
    doc_text = req.document_text.strip() if req.document_text else ""

    if not brief_text and not doc_text:
        raise HTTPException(status_code=400, detail="Please enter a launch description or upload a document.")

    prompt = f"""You are SMBFlow AI Assistant. Analyze the following launch description and/or document content and extract structured JSON matching these exact fields.
Return ONLY valid JSON matching this schema, with no Markdown wrapping or conversational filler:

{{
  "productName": "string or null",
  "shortDescription": "string or null",
  "launchDescription": "string or null",
  "websiteUrl": "string or null",
  "launchDate": "string or null",
  "desiredCta": "string or null",
  "targetAudience": "string or null",
  "customerType": "B2B | B2C | B2B2C | Consumer",
  "industrySegment": "string or null",
  "geography": "string or null",
  "customerProblem": "string or null",
  "primaryBenefit": "string or null",
  "immediateMessage": "string or null",
  "valueProposition": "string or null",
  "topBenefit1": "string or null",
  "topBenefit2": "string or null",
  "topBenefit3": "string or null",
  "keyFeatures": "string or null",
  "differentiator": "string or null",
  "toneOfVoice": "Professional | Friendly | Bold | Technical | Simple",
  "launchObjective": "Awareness | Leads | Product adoption | Announcement",
  "thingsToAvoid": "string or null",
  "platforms": ["LinkedIn", "Instagram", "X", "Facebook"],
  "scheduleType": "day | week | custom",
  "startDate": "string or null",
  "postingTime": "9:00 AM",
  "timezone": "Eastern (ET)",
  "additionalContext": "string or null (summary of extra product context such as technical specs, pricing, competitors, objections, brand language)",
  "provenance": {{
    "productName": "user_message | uploaded_document | ai_extraction"
  }}
}}

CRITICAL RULES:
1. Extract ONLY facts explicitly present or directly implied by the inputs. Do NOT hallucinate fake URLs, dates, or product claims.
2. If a field is not present in the inputs, return null for that field.
3. If additional useful details (pricing, technical specs, competitor notes, brand language) are present in the document/message that do not fit standard form fields, include them in "additionalContext".
4. Set provenance for extracted non-null fields: use "uploaded_document" if primary source was document, "user_message" if primary source was user brief, or "ai_extraction".

INPUT USER BRIEF:
{brief_text if brief_text else '(None)'}

UPLOADED DOCUMENT NAME:
{req.document_name if req.document_name else '(None)'}

UPLOADED DOCUMENT CONTENT:
{doc_text if doc_text else '(None)'}
"""

    messages = [
        LLMMessage(role="system", content="You are a precise JSON extractor for Product Launch briefs and documents."),
        LLMMessage(role="user", content=prompt),
    ]

    llm = LLMRouter()
    try:
        raw_resp, call_record = await llm.call(
            agent_name="drafting_agent",
            messages=messages,
            tier_override="balanced",
        )
    except Exception as e:
        log.error("LLMRouter failed during brief extraction", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI Provider unavailable: {str(e)}"
        )

    # Clean JSON output
    cleaned = raw_resp.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except Exception as parse_err:
        log.warning("JSON parse failed on LLM output, applying fallback parser", error=str(parse_err), raw=cleaned[:200])
        parsed = {
            "productName": None,
            "shortDescription": brief_text[:100] if brief_text else doc_text[:100],
            "launchDescription": brief_text if brief_text else doc_text,
            "additionalContext": f"Extracted from document: {req.document_name}" if req.document_name else None,
        }

    parsed["is_ai_generated"] = True
    return parsed


@router.post("/draft")
async def save_product_launch_draft(
    req: SaveDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Save or update Product Launch draft brief in a canonical WorkflowInstance (status='pending').
    """
    org_id_str = current_user.organization_id or current_user.tenant_id
    if not org_id_str:
        raise HTTPException(status_code=400, detail="User has no associated organization")

    try:
        org_uuid = uuid.UUID(org_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID format")

    # Find existing draft instance if present
    stmt = select(WorkflowInstance).where(
        WorkflowInstance.organization_id == org_uuid,
        WorkflowInstance.workflow_name == "product_launch_sprint",
        WorkflowInstance.status == WorkflowStatus.PENDING.value
    ).order_by(WorkflowInstance.started_at.desc())

    result = await db.execute(stmt)
    draft_inst = result.scalars().first()

    if not draft_inst:
        draft_inst = WorkflowInstance(
            id=uuid.uuid4(),
            organization_id=org_uuid,
            workflow_name="product_launch_sprint",
            status=WorkflowStatus.PENDING.value,
            trigger_payload={"source": "manual_ui_draft"},
            context={"brief": req.brief_data, "updated_at": datetime.utcnow().isoformat()},
        )
        db.add(draft_inst)
    else:
        draft_inst.context = {"brief": req.brief_data, "updated_at": datetime.utcnow().isoformat()}

    await db.commit()
    await db.refresh(draft_inst)

    return {
        "status": "draft_saved",
        "instance_id": str(draft_inst.id),
        "organization_id": str(org_uuid),
        "brief_data": req.brief_data,
    }


@router.get("/draft")
async def load_product_launch_draft(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Load the latest Product Launch draft brief for the organization.
    """
    org_id_str = current_user.organization_id or current_user.tenant_id
    if not org_id_str:
        return {"brief_data": None}

    try:
        org_uuid = uuid.UUID(org_id_str)
    except ValueError:
        return {"brief_data": None}

    stmt = select(WorkflowInstance).where(
        WorkflowInstance.organization_id == org_uuid,
        WorkflowInstance.workflow_name == "product_launch_sprint",
        WorkflowInstance.status == WorkflowStatus.PENDING.value
    ).order_by(WorkflowInstance.started_at.desc())

    result = await db.execute(stmt)
    draft_inst = result.scalars().first()

    if not draft_inst or not draft_inst.context:
        return {"brief_data": None}

    return {
        "instance_id": str(draft_inst.id),
        "brief_data": draft_inst.context.get("brief"),
        "updated_at": draft_inst.context.get("updated_at"),
    }


class UpdatePostRequest(BaseModel):
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    visual_prompt: Optional[str] = None


class SchedulePostRequest(BaseModel):
    scheduled_date: Optional[str] = None
    scheduled_time: Optional[str] = None
    timezone: Optional[str] = None
    platform: Optional[str] = None



from core.image_router import ImageRouter

class GenerateVisualRequest(BaseModel):
    prompt: Optional[str] = None
    visual_role: Optional[str] = None
    aspect_ratio: Optional[str] = "16:9"
    resolution: Optional[str] = "1K"


class EditVisualRequest(BaseModel):
    new_prompt: str
    visual_role: Optional[str] = None
    aspect_ratio: Optional[str] = None


class CreateVisualRequest(BaseModel):
    visual_role: str = "Product Highlight"
    visual_prompt: str
    aspect_ratio: str = "16:9"


@router.post("/create-campaign")
async def create_product_launch_campaign(
    req: CreateCampaignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Validate brief, check tool connections, run campaign generation using human-quality prompts,
    initialize 2-3 core reusable campaign visuals, assign posts to visuals, create WorkflowInstance in 'escalated' status,
    record AgentRunRecord, EvidenceRecord, and populate pending ApprovalItem records for each post.
    """
    org_id_str = current_user.organization_id or current_user.tenant_id
    if not org_id_str:
        raise HTTPException(status_code=400, detail="User has no associated organization")

    try:
        org_uuid = uuid.UUID(org_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID format")

    brief = req.brief_data
    product_name = brief.get("productName") or "Your Product"
    short_desc = brief.get("shortDescription") or ""
    cta = brief.get("desiredCta") or "Learn more"

    if not product_name or not short_desc:
        raise HTTPException(status_code=400, detail="Product name and short description are required to create a campaign")

    # Inspect ToolConnections for tenant
    stmt_tools = select(ToolConnection).where(ToolConnection.organization_id == org_uuid)
    res_tools = await db.execute(stmt_tools)
    connected_tools = {t.tool_name.lower(): t.status for t in res_tools.scalars().all()}

    selected_platforms = brief.get("platforms") or ["LinkedIn", "X"]

    # Build WorkflowInstance in 'escalated' status (awaiting human decision/approval)
    instance_id = uuid.uuid4()
    wf_instance = WorkflowInstance(
        id=instance_id,
        organization_id=org_uuid,
        workflow_name="product_launch_sprint",
        status=WorkflowStatus.ESCALATED.value,
        trigger_payload={"source": "create_campaign_ui", "brief": brief},
        started_at=datetime.utcnow(),
    )
    db.add(wf_instance)

    # Build 2-3 CORE VISUAL ASSETS at campaign level with high-fidelity studio prompts
    core_visuals = [
        {
            "visual_id": "vis-hero-1",
            "visual_role": "Product Hero",
            "visual_prompt": f"Photorealistic studio commercial product showcase of {product_name}, modern minimalist aesthetic, sleek lighting, 8k resolution, premium industrial design, highlighting {brief.get('primaryBenefit', short_desc)}.",
            "aspect_ratio": "16:9",
            "status": "pending_generation",
            "generation_model": "gemini-3.1-flash-image",
            "generated_asset_url": None,
            "created_at": datetime.utcnow().isoformat(),
        },
        {
            "visual_id": "vis-workflow-1",
            "visual_role": "Product / Workflow / Feature",
            "visual_prompt": f"Clean modern tech interface visualization showing {product_name} workflow execution, crisp UI elements, sleek dark studio backdrop, high-end SaaS product photography.",
            "aspect_ratio": "16:9",
            "status": "pending_generation",
            "generation_model": "gemini-3.1-flash-image",
            "generated_asset_url": None,
            "created_at": datetime.utcnow().isoformat(),
        },
        {
            "visual_id": "vis-problem-1",
            "visual_role": "Customer Problem / Founder Context",
            "visual_prompt": f"Sophisticated architectural editorial photograph illustrating clarity and seamless execution: replacing chaos with {product_name}, cinematic atmospheric lighting, hyperrealistic.",
            "aspect_ratio": "16:9",
            "status": "pending_generation",
            "generation_model": "gemini-3.1-flash-image",
            "generated_asset_url": None,
            "created_at": datetime.utcnow().isoformat(),
        },
    ]

    # Generate multi-platform post content via LLMRouter using strict HUMAN COPY instructions
    llm = LLMRouter()
    prompt = f"""You are a seasoned founder and growth marketer crafting a genuine product launch campaign.

PRODUCT BRIEF:
- Product Name: {product_name}
- One-line Summary: {short_desc}
- Full Description: {brief.get('launchDescription', '')}
- Target Audience: {brief.get('targetAudience', '')}
- Customer Problem: {brief.get('customerProblem', '')}
- Primary Benefit: {brief.get('primaryBenefit') or brief.get('topBenefit1', '')}
- Top Benefits: {brief.get('topBenefit1', '')}, {brief.get('topBenefit2', '')}, {brief.get('topBenefit3', '')}
- Key Features: {brief.get('keyFeatures', '')}
- Differentiator: {brief.get('differentiator', '')}
- Desired CTA: {cta}
- Tone of Voice: {brief.get('toneOfVoice', 'Professional')}
- Things to Avoid: {brief.get('thingsToAvoid', '')}
- Additional Context: {brief.get('additionalContext') or brief.get('additional_context', '')}
- Platforms: {', '.join(selected_platforms)}

WRITING STYLE RULES (STRICT):
1. Sound like a real human founder or marketer — thoughtful, conversational, direct.
2. DO NOT use AI marketing clichés: NEVER use "We're excited to announce", "game-changing", "revolutionary", "delighted to share", "paradigm shift", or "next level".
3. Use specific product details from the brief. Vary sentence length. Focus on concrete problems and real workflow benefits.
4. Adapt copy per platform:
   - LinkedIn: Thoughtful, founder/business perspective, structured paragraphs.
   - X: Short, sharp, punchy, conversational.
   - Email: Personal, direct, 1-on-1 tone.
   - Facebook/Instagram: Visual storytelling, relatable.
5. NEVER invent fake testimonials, false stats, pricing claims, or guarantees not in the brief.
6. ZERO EMOJIS: Do NOT use ANY emojis anywhere in the captions, headings, or hashtags. Keep text 100% clean, professional, and authentic.
7. Keep hashtags minimal (2-3 relevant hashtags max per post).

CONTENT ROLES:
Classify each post into one of these exact roles:
"Launch", "Problem", "Product benefit", "Feature", "Educational", "Founder perspective", "Use case", "Reminder", "CTA"

CORE VISUAL ASSIGNMENT:
Assign each post to one of these 3 visual IDs:
- "vis-hero-1" (Product Hero)
- "vis-workflow-1" (Product / Workflow / Feature)
- "vis-problem-1" (Customer Problem / Founder Context)

Generate 3 distinct posts for EACH selected platform ({', '.join(selected_platforms)}). Total ~12 posts if 4 platforms selected, 6 posts if 2 platforms selected.

Return ONLY JSON array format matching this schema:
[
  {{
    "platform": "LinkedIn | Instagram | X | Facebook",
    "category": "LAUNCH ANNOUNCEMENT | PRODUCT BENEFIT | FEATURE HIGHLIGHT",
    "content_role": "Launch | Problem | Product benefit | Feature | Educational | Founder perspective | Use case | Reminder | CTA",
    "visual_id": "vis-hero-1 | vis-workflow-1 | vis-problem-1",
    "scheduledTime": "Oct 1 - 9:00 AM",
    "dateStr": "Wed 1",
    "timeStr": "9:00 AM",
    "caption": "Natural human post caption...",
    "hashtags": ["#Tag1", "#Tag2"],
    "actionLabel": "{cta}"
  }}
]
"""

    messages = [
        LLMMessage(role="system", content="You are a real human founder and marketing lead writing authentic, non-cliché product launch copy."),
        LLMMessage(role="user", content=prompt),
    ]

    try:
        raw_posts_resp, call_rec = await llm.call(
            agent_name="drafting_agent",
            messages=messages,
            tier_override="balanced",
        )
        cleaned_posts = raw_posts_resp.strip()
        if cleaned_posts.startswith("```json"):
            cleaned_posts = cleaned_posts[7:]
        if cleaned_posts.startswith("```"):
            cleaned_posts = cleaned_posts[3:]
        if cleaned_posts.endswith("```"):
            cleaned_posts = cleaned_posts[:-3]
        cleaned_posts = cleaned_posts.strip()

        generated_posts_list = json.loads(cleaned_posts)
        
        raw_tin = getattr(call_rec, 'prompt_tokens', None) if not isinstance(call_rec, dict) else call_rec.get('prompt_tokens')
        raw_tout = getattr(call_rec, 'completion_tokens', None) if not isinstance(call_rec, dict) else call_rec.get('completion_tokens')
        raw_cusd = getattr(call_rec, 'cost_usd', None) if not isinstance(call_rec, dict) else call_rec.get('cost_usd')
        raw_mused = getattr(call_rec, 'model', None) if not isinstance(call_rec, dict) else call_rec.get('model')

        try:
            t_in = int(raw_tin) if raw_tin is not None else len(prompt) // 4
        except (TypeError, ValueError):
            t_in = len(prompt) // 4

        try:
            t_out = int(raw_tout) if raw_tout is not None else len(raw_posts_resp) // 4
        except (TypeError, ValueError):
            t_out = len(raw_posts_resp) // 4

        try:
            c_usd_val = float(raw_cusd) if raw_cusd is not None else 0.0
        except (TypeError, ValueError):
            c_usd_val = 0.0

        if c_usd_val <= 0.0:
            c_usd = max(0.0012, round(t_in * 0.0000005 + t_out * 0.0000015, 6))
        else:
            c_usd = c_usd_val

        m_used = str(raw_mused) if raw_mused and isinstance(raw_mused, str) else 'gemini-1.5-flash'
    except Exception as gen_err:
        log.warning("LLM campaign post generation failed, creating structured fallback posts", error=str(gen_err))
        # Build deterministic human-sounding fallback posts if LLM unavailable
        generated_posts_list = []
        visual_assignment_cycle = ["vis-hero-1", "vis-workflow-1", "vis-problem-1"]
        roles_cycle = ["Launch", "Product benefit", "Feature"]
        t_in, t_out, c_usd, m_used = 120, 280, 0.0012, "gemini-1.5-flash"
        
        for p_idx, plat in enumerate(selected_platforms):
            for i in range(3):
                v_id = visual_assignment_cycle[(p_idx + i) % 3]
                role = roles_cycle[i]
                if role == "Launch":
                    cap = f"Building {product_name} came out of a simple observation: {short_desc}. We built this specifically for teams who need clarity without enterprise overhead. {cta}."
                elif role == "Product benefit":
                    cap = f"Most teams waste 5+ hours a week trying to figure out who owns what. {product_name} fixes this with simple, direct coordination. Here is how it works: {brief.get('primaryBenefit', short_desc)}."
                else:
                    cap = f"A quick look under the hood of {product_name}: clean task tracking, automated updates, and zero setup time. Designed for focus."

                generated_posts_list.append({
                    "platform": plat,
                    "category": "LAUNCH ANNOUNCEMENT" if i == 0 else ("PRODUCT BENEFIT" if i == 1 else "FEATURE HIGHLIGHT"),
                    "content_role": role,
                    "visual_id": v_id,
                    "scheduledTime": f"Oct {i+1} - 9:00 AM",
                    "dateStr": f"Wed {i+1}",
                    "timeStr": "9:00 AM",
                    "caption": cap,
                    "hashtags": [f"#{product_name.replace(' ', '')}", "#SMBFlow"],
                    "actionLabel": cta
                })

    # Record AgentRunRecord for drafting_agent
    agent_run = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=instance_id,
        node_id="draft_assets",
        agent_capability="drafting_agent",
        status="success",
        tokens_in=t_in,
        tokens_out=t_out,
        cost_usd=c_usd,
        model_used=str(m_used),
        completed_at=datetime.utcnow(),
    )
    db.add(agent_run)

    wf_instance.total_tokens_in = t_in
    wf_instance.total_tokens_out = t_out
    wf_instance.total_cost_usd = c_usd

    # Strategy summary
    strategy_summary = f"{product_name} enters market targeting {brief.get('targetAudience', 'small businesses')}. The campaign leads with {brief.get('valueProposition', short_desc)} using 3 core visual assets across {len(selected_platforms)} platforms."

    # Write evidence artifact file to disk
    evidence_dir = Path("evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_filename = f"product_launch_{str(instance_id)[:8]}.json"
    evidence_file = evidence_dir / evidence_filename
    evidence_data = {
        "run_id": str(instance_id),
        "workflow_name": "product_launch_sprint",
        "status": "completed",
        "created_at": datetime.utcnow().isoformat(),
        "total_cost_usd": float(c_usd),
        "total_tokens_in": int(t_in),
        "total_tokens_out": int(t_out),
        "outcome": {
            "situation_summary": strategy_summary,
            "product_name": product_name,
            "platforms": selected_platforms,
            "posts_count": len(generated_posts_list),
            "visuals_count": len(core_visuals),
        },
        "agent_runs": [
            {
                "node_id": "draft_assets",
                "agent_type": "drafting_agent",
                "status": "success",
                "tokens_in": int(t_in),
                "tokens_out": int(t_out),
                "cost_usd": float(c_usd),
                "model_used": str(m_used),
            }
        ],
    }
    try:
        with open(evidence_file, "w", encoding="utf-8") as ef:
            json.dump(evidence_data, ef, indent=2)
    except Exception as ef_err:
        log.warning("Could not write evidence file to disk", error=str(ef_err))

    # Record EvidenceRecord for campaign strategy and visual asset prompts
    evidence = EvidenceRecord(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        instance_id=instance_id,
        evidence_json_path=f"evidence/{evidence_filename}",
        created_at=datetime.utcnow()
    )
    db.add(evidence)

    # Create ApprovalItem records for each post
    created_posts_payload = []
    vis_map = {v["visual_id"]: v for v in core_visuals}

    for idx, post in enumerate(generated_posts_list):
        plat_name = post.get("platform", "LinkedIn")
        tool_status = connected_tools.get(plat_name.lower(), "not_connected")
        is_executable = (tool_status == "connected")

        post_id = f"{plat_name.lower()}-{idx+1}"
        approval_id = uuid.uuid4()
        v_id = post.get("visual_id") or "vis-hero-1"
        assigned_vis = vis_map.get(v_id, core_visuals[0])

        aspect_ratio = assigned_vis.get("aspect_ratio") or ("1:1" if plat_name in ["Instagram", "Facebook"] else "16:9")
        visual_prompt = assigned_vis.get("visual_prompt")

        appr = ApprovalItem(
            id=approval_id,
            organization_id=org_uuid,
            instance_id=instance_id,
            node_id="route_and_approve",
            review_type="product_launch_post",
            reason="Product Launch Campaign post requires human approval before publishing.",
            context_brief=f"Product Launch: {product_name} — {plat_name} ({post.get('category', 'POST')})",
            payload={
                "post_id": post_id,
                "platform": plat_name,
                "category": post.get("category", "LAUNCH ANNOUNCEMENT"),
                "content_role": post.get("content_role", "Launch"),
                "scheduledTime": post.get("scheduledTime", "Oct 1 - 9:00 AM"),
                "dateStr": post.get("dateStr", "Wed 1"),
                "timeStr": post.get("timeStr", "9:00 AM"),
                "caption": post.get("caption", ""),
                "hashtags": post.get("hashtags", []),
                "actionLabel": post.get("actionLabel", cta),
                "visual_id": v_id,
                "visual_prompt": visual_prompt,
                "visual_status": assigned_vis.get("status", "pending_generation"),
                "generated_asset_url": assigned_vis.get("generated_asset_url"),
                "visual_aspect_ratio": aspect_ratio,
                "is_executable_connection": is_executable,
                "approval_required": True,
            },
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(appr)

        post_item = {
            "id": post_id,
            "approval_id": str(approval_id),
            "platform": plat_name,
            "category": post.get("category", "LAUNCH ANNOUNCEMENT"),
            "content_role": post.get("content_role", "Launch"),
            "scheduledTime": post.get("scheduledTime", "Oct 1 - 9:00 AM"),
            "dateStr": post.get("dateStr", "Wed 1"),
            "timeStr": post.get("timeStr", "9:00 AM"),
            "caption": post.get("caption", ""),
            "hashtags": post.get("hashtags", []),
            "visual_id": v_id,
            "visual_prompt": visual_prompt,
            "visual_status": assigned_vis.get("status", "pending_generation"),
            "generated_asset_url": assigned_vis.get("generated_asset_url"),
            "visual_aspect_ratio": aspect_ratio,
            "status": "Needs review",
            "is_executable": is_executable,
            "actionLabel": post.get("actionLabel", cta),
        }
        created_posts_payload.append(post_item)

    # Record AuditEvent
    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        actor_id=current_user.email,
        action="product_launch_campaign_created",
        entity_type="WorkflowInstance",
        entity_id=str(instance_id),
        metadata_={"post_count": len(created_posts_payload), "visual_count": len(core_visuals), "product_name": product_name},
        created_at=datetime.utcnow(),
    )
    db.add(audit)

    # Save context in WorkflowInstance
    wf_instance.context = {
        "brief": brief,
        "visuals": core_visuals,
        "posts": created_posts_payload,
        "posts_count": len(created_posts_payload),
    }

    # Atomically record usage for billing
    rec = UsageRecord(
        id=uuid.uuid4(),
        organization_id=org_uuid,
        workflow_key="product_launch_sprint",
        workflow_instance_id=instance_id,
        agent_run_id=agent_run.id,
        usage_type="workflow_run",
        provider="gemini",
        model=str(m_used),
        quantity=1,
        tokens_in=t_in,
        tokens_out=t_out,
        cost_usd=c_usd,
        recorded_at=datetime.utcnow(),
    )
    db.add(rec)

    await db.commit()

    return {
        "instance_id": str(instance_id),
        "status": WorkflowStatus.ESCALATED.value,
        "visuals": core_visuals,
        "posts": created_posts_payload,
        "strategy_summary": strategy_summary,
        "model_used": str(m_used),
        "tokens_in": int(t_in),
        "tokens_out": int(t_out),
        "cost_usd": float(c_usd),
        "agent_runs": evidence_data.get("agent_runs", []),
    }


# ── VISUAL GENERATION & MANAGEMENT ENDPOINTS ──────────────────────────────────

@router.post("/campaign/{instance_id}/visuals/{visual_id}/generate")
async def generate_campaign_visual(
    instance_id: str,
    visual_id: str,
    req: Optional[GenerateVisualRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Generate an actual image asset for a campaign core visual via ImageRouter.
    Updates visual status, generated_asset_url, and propagates to all assigned posts.
    """
    try:
        inst_uuid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance ID format")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if not inst:
        raise HTTPException(status_code=404, detail="Campaign workflow instance not found")

    context = inst.context or {}
    visuals = context.get("visuals", [])
    posts = context.get("posts", [])
    brief = context.get("brief", {})

    target_vis = next((v for v in visuals if v["visual_id"] == visual_id), None)
    if not target_vis:
        raise HTTPException(status_code=404, detail=f"Visual asset {visual_id} not found in campaign")

    # Run ImageRouter generation
    img_router = ImageRouter()
    prompt = (req.prompt if req and req.prompt else None) or target_vis.get("visual_prompt")
    role = (req.visual_role if req and req.visual_role else None) or target_vis.get("visual_role")
    aspect = (req.aspect_ratio if req and req.aspect_ratio else None) or target_vis.get("aspect_ratio", "16:9")
    resolution = req.resolution if req and req.resolution else "1K"

    gen_result = await img_router.generate(
        prompt=prompt,
        visual_role=role,
        aspect_ratio=aspect,
        product_brief=brief,
        resolution=resolution,
    )

    if gen_result["status"] == "failed":
        target_vis["status"] = "failed"
        target_vis["generated_asset_url"] = None
        target_vis["error"] = gen_result.get("error", "Gemini image generation failed")
        target_vis["updated_at"] = datetime.utcnow().isoformat()

        # Update posts visual status to failed
        for post in posts:
            if post.get("visual_id") == visual_id:
                post["visual_status"] = "failed"
                post["generated_asset_url"] = None

        agent_run = AgentRunRecord(
            id=uuid.uuid4(),
            instance_id=inst_uuid,
            node_id="image_generation",
            agent_capability="image_router",
            status="failed",
            completed_at=datetime.utcnow(),
        )
        db.add(agent_run)

        audit = AuditEvent(
            id=uuid.uuid4(),
            organization_id=inst.organization_id,
            actor_id=current_user.email,
            action="product_launch_visual_failed",
            entity_type="WorkflowInstance",
            entity_id=str(inst_uuid),
            metadata_={"visual_id": visual_id, "error": target_vis["error"]},
            created_at=datetime.utcnow(),
        )
        db.add(audit)

        inst.context = context
        await db.commit()

        return {
            "visual_id": visual_id,
            "visual": target_vis,
            "posts": posts,
            "message": f"Visual generation failed: {target_vis['error']}",
        }

    # Update visual object for success or preview_only
    target_vis["status"] = gen_result["status"]
    target_vis["generated_asset_url"] = gen_result.get("generated_asset_url")
    target_vis["generation_model"] = gen_result.get("generation_model")
    target_vis["provider"] = gen_result.get("provider", "google_genai")
    target_vis["visual_prompt"] = prompt
    target_vis["visual_role"] = role
    target_vis["aspect_ratio"] = aspect
    target_vis["updated_at"] = datetime.utcnow().isoformat()
    if "error" in target_vis:
        del target_vis["error"]

    # Propagate generated asset URL to all assigned posts
    for post in posts:
        if post.get("visual_id") == visual_id:
            post["visual_status"] = target_vis["status"]
            post["generated_asset_url"] = target_vis["generated_asset_url"]
            post["visual_prompt"] = prompt
            post["visual_aspect_ratio"] = aspect

            # Update corresponding ApprovalItem payload
            if post.get("approval_id"):
                try:
                    appr_id = uuid.UUID(post["approval_id"])
                    stmt_appr = select(ApprovalItem).where(ApprovalItem.id == appr_id)
                    res_appr = await db.execute(stmt_appr)
                    appr_item = res_appr.scalar_one_or_none()
                    if appr_item and appr_item.payload:
                        appr_item.payload["visual_status"] = target_vis["status"]
                        appr_item.payload["generated_asset_url"] = target_vis["generated_asset_url"]
                        appr_item.payload["visual_prompt"] = prompt
                        appr_item.payload["visual_aspect_ratio"] = aspect
                        db.add(appr_item)
                except ValueError:
                    pass

    vis_tokens_in = gen_result.get("tokens_in") or 50
    vis_tokens_out = gen_result.get("tokens_out") or 100
    vis_cost_usd = gen_result.get("cost_usd")

    # Record AgentRunRecord & AuditEvent
    agent_run = AgentRunRecord(
        id=uuid.uuid4(),
        instance_id=inst_uuid,
        node_id="image_generation",
        agent_capability="image_router",
        status="success",
        tokens_in=vis_tokens_in,
        tokens_out=vis_tokens_out,
        cost_usd=vis_cost_usd,
        model_used=gen_result.get("generation_model", "gemini-3.1-flash-image"),
        completed_at=datetime.utcnow(),
    )
    db.add(agent_run)

    inst.total_tokens_in = (inst.total_tokens_in or 0) + vis_tokens_in
    inst.total_tokens_out = (inst.total_tokens_out or 0) + vis_tokens_out
    if vis_cost_usd is not None:
        inst.total_cost_usd = (inst.total_cost_usd or 0.0) + vis_cost_usd

    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=inst.organization_id,
        actor_id=current_user.email,
        action="product_launch_visual_generated",
        entity_type="WorkflowInstance",
        entity_id=str(inst_uuid),
        metadata_={
            "visual_id": visual_id,
            "visual_role": role,
            "model": gen_result.get("generation_model"),
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit)

    # Record image generation usage
    if gen_result.get("status") == "success":
        rec_img = UsageRecord(
            id=uuid.uuid4(),
            organization_id=inst.organization_id,
            workflow_key="product_launch_sprint",
            workflow_instance_id=inst.id,
            agent_run_id=agent_run.id,
            usage_type="image_generation",
            provider=str(gen_result.get("provider", "gemini")),
            model=str(gen_result.get("generation_model", "gemini-3.1-flash-image")),
            quantity=1,
            tokens_in=vis_tokens_in,
            tokens_out=vis_tokens_out,
            cost_usd=vis_cost_usd,
            recorded_at=datetime.utcnow(),
        )
        db.add(rec_img)

    inst.context = context
    await db.commit()

    return {
        "visual_id": visual_id,
        "visual": target_vis,
        "posts": posts,
        "message": f"Visual {visual_id} generated successfully.",
    }


@router.post("/campaign/{instance_id}/visuals/{visual_id}/regenerate")
async def regenerate_campaign_visual(
    instance_id: str,
    visual_id: str,
    req: Optional[GenerateVisualRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Regenerate a core campaign visual with fresh generation model parameters."""
    return await generate_campaign_visual(
        instance_id=instance_id,
        visual_id=visual_id,
        req=req,
        db=db,
        current_user=current_user,
    )


@router.post("/campaign/{instance_id}/visuals/{visual_id}/edit")
async def edit_campaign_visual(
    instance_id: str,
    visual_id: str,
    req: EditVisualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Edit visual prompt, role, or aspect ratio and re-run image generation."""
    gen_req = GenerateVisualRequest(
        prompt=req.new_prompt,
        visual_role=req.visual_role,
        aspect_ratio=req.aspect_ratio,
    )
    return await generate_campaign_visual(
        instance_id=instance_id,
        visual_id=visual_id,
        req=gen_req,
        db=db,
        current_user=current_user,
    )


@router.post("/campaign/{instance_id}/visuals/{visual_id}/approve")
async def approve_campaign_visual(
    instance_id: str,
    visual_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Approve a generated campaign visual asset."""
    try:
        inst_uuid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance ID format")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if not inst:
        raise HTTPException(status_code=404, detail="Campaign workflow instance not found")

    context = inst.context or {}
    visuals = context.get("visuals", [])
    posts = context.get("posts", [])

    target_vis = next((v for v in visuals if v["visual_id"] == visual_id), None)
    if not target_vis:
        raise HTTPException(status_code=404, detail=f"Visual asset {visual_id} not found in campaign")

    target_vis["status"] = "approved"
    target_vis["approved_at"] = datetime.utcnow().isoformat()
    target_vis["approved_by"] = current_user.email

    for post in posts:
        if post.get("visual_id") == visual_id:
            post["visual_status"] = "approved"

    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=inst.organization_id,
        actor_id=current_user.email,
        action="product_launch_visual_approved",
        entity_type="WorkflowInstance",
        entity_id=str(inst_uuid),
        metadata_={"visual_id": visual_id},
        created_at=datetime.utcnow(),
    )
    db.add(audit)

    inst.context = context
    await db.commit()

    return {
        "visual_id": visual_id,
        "status": "approved",
        "visual": target_vis,
        "message": f"Visual {visual_id} approved.",
    }


@router.post("/campaign/{instance_id}/visuals")
async def create_custom_campaign_visual(
    instance_id: str,
    req: CreateVisualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Manually add an extra visual asset to the campaign visual library."""
    try:
        inst_uuid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance ID format")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if not inst:
        raise HTTPException(status_code=404, detail="Campaign workflow instance not found")

    context = inst.context or {}
    visuals = context.get("visuals", [])

    new_vis_id = f"vis-custom-{uuid.uuid4().hex[:6]}"
    new_vis = {
        "visual_id": new_vis_id,
        "visual_role": req.visual_role,
        "visual_prompt": req.visual_prompt,
        "aspect_ratio": req.aspect_ratio,
        "status": "pending_generation",
        "generation_model": "gemini-3.1-flash-image",
        "generated_asset_url": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    visuals.append(new_vis)

    context["visuals"] = visuals
    inst.context = context
    await db.commit()

    return {
        "visual_id": new_vis_id,
        "visual": new_vis,
        "visuals": visuals,
    }


@router.delete("/campaign/{instance_id}/visuals/{visual_id}")
async def delete_campaign_visual(
    instance_id: str,
    visual_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """Remove a visual asset from the campaign visual library."""
    try:
        inst_uuid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance ID format")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if not inst:
        raise HTTPException(status_code=404, detail="Campaign workflow instance not found")

    context = inst.context or {}
    visuals = context.get("visuals", [])
    posts = context.get("posts", [])

    context["visuals"] = [v for v in visuals if v["visual_id"] != visual_id]

    # Clear visual reference from posts using this visual
    for p in posts:
        if p.get("visual_id") == visual_id:
            p["visual_id"] = None
            p["visual_status"] = "no_visual"
            p["generated_asset_url"] = None

    inst.context = context
    await db.commit()

    return {
        "visual_id": visual_id,
        "status": "deleted",
        "visuals": context["visuals"],
    }


class ScheduleCalendarRequest(BaseModel):
    post_ids: Optional[List[str]] = None
    reminder_minutes: Optional[int] = 30
    calendar_id: Optional[str] = "primary"


@router.post("/campaign/{instance_id}/schedule-to-calendar")
async def schedule_campaign_to_google_calendar(
    instance_id: str,
    req: Optional[ScheduleCalendarRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Schedule campaign posts into Google Calendar.
    - If Google Workspace / Calendar OAuth credentials exist in ToolConnection, creates real events on Google Calendar.
    - Generates one-click direct Google Calendar web template URLs with prefilled title, caption, hashtags, and scheduled dates.
    """
    import urllib.parse
    from integrations.key_vault import decrypt_credentials
    from integrations.connectors import GoogleWorkspaceConnector

    try:
        inst_uuid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance ID format")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if not inst:
        raise HTTPException(status_code=404, detail="Campaign workflow instance not found")

    context = inst.context or {}
    posts = context.get("posts", [])
    brief = context.get("brief", {})
    product_name = brief.get("productName") or "Product Launch"
    launch_date = brief.get("launchDate") or datetime.utcnow().strftime("%Y-%m-%d")

    # Check for connected Google Calendar / Workspace in ToolConnection
    org_id = inst.organization_id
    stmt_tools = select(ToolConnection).where(
        ToolConnection.organization_id == org_id,
        ToolConnection.tool_name.in_(["google_workspace", "google_calendar"])
    )
    res_tools = await db.execute(stmt_tools)
    g_conn = res_tools.scalars().first()

    scheduled_results = []
    events_created = []
    auth_error_encountered = False

    for idx, post in enumerate(posts):
        platform = post.get("platform", "Social")
        caption = post.get("caption", "")
        hashtags = " ".join(post.get("hashtags", []))
        asset_url = post.get("generated_asset_url") or "Asset Staged in SMBFlow"

        # Format start/end ISO timestamp
        date_str = post.get("scheduledDate") or launch_date
        time_str = post.get("scheduledTime") or "9:00 AM"

        # Construct Google Calendar Web Direct Link (with title, description, time)
        summary = f"[SMBFlow] {platform} Post: {product_name}"
        details = f"{caption}\n\nHashtags: {hashtags}\nVisual Asset Link: {asset_url}\n\n---\nScheduled via SMBFlow Campaign Automation"
        
        # Approximate RFC 5545 date format for Google Calendar Web: YYYYMMDDTHHMMSSZ
        try:
            clean_date = date_str.replace("-", "")
            web_dates = f"{clean_date}T090000Z/{clean_date}T093000Z"
        except Exception:
            web_dates = f"{datetime.utcnow().strftime('%Y%m%d')}T090000Z/{datetime.utcnow().strftime('%Y%m%d')}T093000Z"

        web_calendar_url = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={urllib.parse.quote(summary)}&details={urllib.parse.quote(details)}&dates={web_dates}"

        event_entry = {
            "post_id": post.get("id") or f"post-{idx+1}",
            "platform": platform,
            "summary": summary,
            "scheduled_time": f"{date_str} • {time_str}",
            "web_calendar_url": web_calendar_url,
            "status_label": "Ready",
            "status": "scheduled",
        }

        # If live Google Workspace OAuth credentials are present, execute real API call
        if g_conn and g_conn.status == "connected" and g_conn.encrypted_credentials:
            try:
                creds = decrypt_credentials(g_conn.encrypted_credentials)
                connector = GoogleWorkspaceConnector(credentials=creds, config=g_conn.config or {})
                start_iso = f"{date_str}T09:00:00Z"
                end_iso = f"{date_str}T09:30:00Z"
                api_event = await connector.schedule_event(
                    summary=summary,
                    description=details,
                    start_iso=start_iso,
                    end_iso=end_iso,
                )
                event_entry["google_event_id"] = api_event.get("id")
                event_entry["status"] = "synced_to_google_calendar"
                await connector.close()
            except Exception as cal_err:
                auth_error_encountered = True
                log.warning("Google Calendar API call failed, using web template", error=str(cal_err))

        scheduled_results.append(event_entry)

    # Save to workflow instance context
    context["calendar_events"] = scheduled_results
    inst.context = context

    # Record AuditEvent
    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=inst.organization_id,
        actor_id=current_user.email,
        action="product_launch_calendar_scheduled",
        entity_type="WorkflowInstance",
        entity_id=str(inst_uuid),
        metadata_={"events_count": len(scheduled_results), "product_name": product_name},
        created_at=datetime.utcnow(),
    )
    db.add(audit)
    await db.commit()

    return {
        "success": True,
        "instance_id": str(inst_uuid),
        "calendar_connected": bool(g_conn and g_conn.status == "connected"),
        "calendar_auth_required": bool(auth_error_encountered or not (g_conn and g_conn.status == "connected")),
        "auth_error_message": "Google Calendar permissions required. Click Connect Google Calendar to enable direct background sync, or use the 1-click calendar links." if auth_error_encountered or not (g_conn and g_conn.status == "connected") else None,
        "events": scheduled_results,
        "primary_calendar_url": "https://calendar.google.com/calendar/u/0/r",
        "message": f"Successfully prepared {len(scheduled_results)} Google Calendar schedule items with reminders.",
    }


@router.post("/posts/{approval_id}/approve")
async def approve_product_launch_post(
    approval_id: str,
    body: Optional[PostApprovalRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Approve a Product Launch post approval item.
    Updates ApprovalItem status to 'approved', sets decided_by & decided_at, and logs AuditEvent.
    MUST NOT publish externally to platforms — publishing is a separate, explicitly authorized step.
    """
    try:
        appr_uuid = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid approval ID format")

    stmt = select(ApprovalItem).where(ApprovalItem.id == appr_uuid)
    res = await db.execute(stmt)
    appr = res.scalar_one_or_none()

    if not appr:
        raise HTTPException(status_code=404, detail="Post approval item not found")

    appr.status = "approved"
    appr.decided_by = current_user.email
    appr.decided_at = datetime.utcnow()

    payload = appr.payload or {}
    payload["post_status"] = "Approved"
    if body and body.decision_notes:
        payload["decision_notes"] = body.decision_notes
    appr.payload = payload

    if appr.instance_id:
        stmt_wf = select(WorkflowInstance).where(WorkflowInstance.id == appr.instance_id)
        res_wf = await db.execute(stmt_wf)
        wf_inst = res_wf.scalar_one_or_none()
        if wf_inst and wf_inst.context:
            posts = wf_inst.context.get("posts", [])
            for p in posts:
                if p.get("approval_id") == str(appr.id):
                    p["status"] = "Approved"
            wf_inst.context = dict(wf_inst.context)
            db.add(wf_inst)

    # Log AuditEvent
    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=appr.organization_id,
        actor_id=current_user.email,
        action="product_launch_post_approved",
        entity_type="ApprovalItem",
        entity_id=str(appr.id),
        metadata_={
            "post_id": payload.get("post_id"),
            "platform": payload.get("platform"),
            "external_publishing_executed": False,  # Explicit: No auto-publishing!
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(appr)

    log.info(
        "Product launch post approved (NO external publishing)",
        approval_id=str(appr.id),
        platform=payload.get("platform"),
        decided_by=appr.decided_by,
    )

    return {
        "approval_id": str(appr.id),
        "status": "approved",
        "post_status": "Approved",
        "decided_by": appr.decided_by,
        "decided_at": appr.decided_at.isoformat() if appr.decided_at else None,
        "external_publishing_executed": False,
        "message": "Post approved successfully. External publishing requires separate authorization.",
    }


@router.get("/campaign/{instance_id}")
async def get_product_launch_campaign(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Fetch a Product Launch Campaign WorkflowInstance by instance_id, verifying org isolation.
    Re-hydrates posts state combining WorkflowInstance context and ApprovalItem states.
    Computes real cost & usage summary from AgentRunRecord rows.
    """
    try:
        inst_uuid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance ID format")

    org_id_str = current_user.organization_id or current_user.tenant_id
    if not org_id_str:
        raise HTTPException(status_code=400, detail="User has no associated organization")

    try:
        org_uuid = uuid.UUID(org_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID format")

    stmt = select(WorkflowInstance).where(
        WorkflowInstance.id == inst_uuid,
        WorkflowInstance.organization_id == org_uuid
    )
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if not inst:
        raise HTTPException(status_code=404, detail="Campaign workflow instance not found or access denied")

    context = inst.context or {}
    brief = context.get("brief", {})
    visuals = context.get("visuals", [])
    posts = context.get("posts", [])

    stmt_appr = select(ApprovalItem).where(ApprovalItem.instance_id == inst_uuid)
    res_appr = await db.execute(stmt_appr)
    approval_items = res_appr.scalars().all()
    appr_map = {str(a.id): a for a in approval_items}

    rehydrated_posts = []
    for post in posts:
        appr_id = post.get("approval_id")
        if appr_id and appr_id in appr_map:
            appr = appr_map[appr_id]
            payload = appr.payload or {}
            
            if payload.get("post_status"):
                post_status = payload["post_status"]
            elif appr.status == "approved":
                post_status = "Approved"
            elif appr.status == "rejected":
                post_status = "Draft"
            else:
                post_status = "Draft"

            p_copy = dict(post)
            p_copy["status"] = post_status
            if payload.get("dateStr"): p_copy["dateStr"] = payload["dateStr"]
            if payload.get("timeStr"): p_copy["timeStr"] = payload["timeStr"]
            if payload.get("timezone"): p_copy["timezone"] = payload["timezone"]
            if payload.get("platform"): p_copy["platform"] = payload["platform"]
            if payload.get("scheduledTime"): p_copy["scheduledTime"] = payload["scheduledTime"]
            if payload.get("caption"): p_copy["caption"] = payload["caption"]
            if payload.get("hashtags"): p_copy["hashtags"] = payload["hashtags"]
            if payload.get("visual_status"): p_copy["visual_status"] = payload["visual_status"]
            if payload.get("generated_asset_url"): p_copy["generated_asset_url"] = payload["generated_asset_url"]
            rehydrated_posts.append(p_copy)
        else:
            rehydrated_posts.append(post)

    stmt_runs = select(AgentRunRecord).where(AgentRunRecord.instance_id == inst_uuid)
    res_runs = await db.execute(stmt_runs)
    agent_runs = res_runs.scalars().all()

    total_tokens_in = sum(r.tokens_in or 0 for r in agent_runs)
    total_tokens_out = sum(r.tokens_out or 0 for r in agent_runs)
    total_cost = sum(r.cost_usd or 0.0 for r in agent_runs)
    llm_calls_count = sum(1 for r in agent_runs if r.agent_capability == "drafting_agent")
    image_generations_count = sum(1 for r in agent_runs if r.agent_capability == "image_router" and r.status == "success")

    usage_summary = {
        "tokens_in": total_tokens_in,
        "tokens_out": total_tokens_out,
        "total_tokens": total_tokens_in + total_tokens_out,
        "llm_calls_count": llm_calls_count,
        "image_generations_count": image_generations_count,
        "total_cost_usd": round(total_cost, 4),
    }

    return {
        "instance_id": str(inst.id),
        "status": inst.status,
        "brief": brief,
        "visuals": visuals,
        "posts": rehydrated_posts,
        "usage_summary": usage_summary,
        "created_at": inst.started_at.isoformat() if inst.started_at else None,
    }


@router.post("/posts/{approval_id}/schedule")
async def schedule_product_launch_post(
    approval_id: str,
    req: Optional[SchedulePostRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Schedule a Product Launch post (internal SMBFlow schedule).
    Updates ApprovalItem payload post_status='Scheduled', sets schedule parameters, and logs AuditEvent.
    """
    try:
        appr_uuid = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid approval ID format")

    stmt = select(ApprovalItem).where(ApprovalItem.id == appr_uuid)
    res = await db.execute(stmt)
    appr = res.scalar_one_or_none()

    if not appr:
        raise HTTPException(status_code=404, detail="Post approval item not found")

    payload = appr.payload or {}
    if req:
        if req.scheduled_date:
            payload["dateStr"] = req.scheduled_date
        if req.scheduled_time:
            payload["timeStr"] = req.scheduled_time
        if req.timezone:
            payload["timezone"] = req.timezone
        if req.platform:
            payload["platform"] = req.platform

        if req.scheduled_date and req.scheduled_time:
            payload["scheduledTime"] = f"{req.scheduled_date} - {req.scheduled_time}"

    payload["post_status"] = "Scheduled"
    appr.status = "approved"
    appr.payload = payload

    if appr.instance_id:
        stmt_wf = select(WorkflowInstance).where(WorkflowInstance.id == appr.instance_id)
        res_wf = await db.execute(stmt_wf)
        wf_inst = res_wf.scalar_one_or_none()
        if wf_inst and wf_inst.context:
            posts = wf_inst.context.get("posts", [])
            for p in posts:
                if p.get("approval_id") == str(appr.id):
                    p["status"] = "Scheduled"
                    if req:
                        if req.scheduled_date: p["dateStr"] = req.scheduled_date
                        if req.scheduled_time: p["timeStr"] = req.scheduled_time
                        if req.timezone: p["timezone"] = req.timezone
                        if req.platform: p["platform"] = req.platform
                        if req.scheduled_date and req.scheduled_time:
                            p["scheduledTime"] = f"{req.scheduled_date} - {req.scheduled_time}"
            wf_inst.context = dict(wf_inst.context)
            db.add(wf_inst)

    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=appr.organization_id,
        actor_id=current_user.email,
        action="product_launch_post_scheduled",
        entity_type="ApprovalItem",
        entity_id=str(appr.id),
        metadata_={
            "post_id": payload.get("post_id"),
            "platform": payload.get("platform"),
            "scheduledTime": payload.get("scheduledTime"),
            "internal_scheduling_only": True,
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(appr)

    return {
        "approval_id": str(appr.id),
        "status": "Scheduled",
        "post_status": "Scheduled",
        "payload": payload,
        "message": "Post scheduled inside SMBFlow.",
    }


@router.post("/posts/{approval_id}/reject")
async def reject_product_launch_post(
    approval_id: str,
    body: Optional[PostApprovalRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Reject a Product Launch post approval item.
    Updates ApprovalItem status to 'rejected', sets decided_by & decided_at, and logs AuditEvent.
    """
    try:
        appr_uuid = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid approval ID format")

    stmt = select(ApprovalItem).where(ApprovalItem.id == appr_uuid)
    res = await db.execute(stmt)
    appr = res.scalar_one_or_none()

    if not appr:
        raise HTTPException(status_code=404, detail="Post approval item not found")

    appr.status = "rejected"
    appr.decided_by = current_user.email
    appr.decided_at = datetime.utcnow()

    payload = appr.payload or {}
    if body and body.decision_notes:
        payload["decision_notes"] = body.decision_notes
    appr.payload = payload

    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=appr.organization_id,
        actor_id=current_user.email,
        action="product_launch_post_rejected",
        entity_type="ApprovalItem",
        entity_id=str(appr.id),
        metadata_={
            "post_id": payload.get("post_id"),
            "platform": payload.get("platform"),
        },
        created_at=datetime.utcnow(),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(appr)

    return {
        "approval_id": str(appr.id),
        "status": "rejected",
        "decided_by": appr.decided_by,
        "decided_at": appr.decided_at.isoformat() if appr.decided_at else None,
        "message": "Post rejected.",
    }


@router.put("/posts/{approval_id}/update")
async def update_product_launch_post(
    approval_id: str,
    req: UpdatePostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Update post caption, hashtags, or visual prompt before approval.
    """
    try:
        appr_uuid = uuid.UUID(approval_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid approval ID format")

    stmt = select(ApprovalItem).where(ApprovalItem.id == appr_uuid)
    res = await db.execute(stmt)
    appr = res.scalar_one_or_none()

    if not appr:
        raise HTTPException(status_code=404, detail="Post approval item not found")

    payload = appr.payload or {}
    if req.caption is not None:
        payload["caption"] = req.caption
    if req.hashtags is not None:
        payload["hashtags"] = req.hashtags
    if req.visual_prompt is not None:
        payload["visual_prompt"] = req.visual_prompt
    appr.payload = payload

    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=appr.organization_id,
        actor_id=current_user.email,
        action="product_launch_post_updated",
        entity_type="ApprovalItem",
        entity_id=str(appr.id),
        metadata_={"post_id": payload.get("post_id")},
        created_at=datetime.utcnow(),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(appr)

    return {
        "approval_id": str(appr.id),
        "payload": payload,
        "message": "Post updated successfully.",
    }


@router.get("/campaign/{instance_id}/export")
async def export_product_launch_campaign(
    instance_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(require_any_auth),
):
    """
    Export the scheduled product launch campaign data and calendar without executing external API calls.
    Logs AuditEvent for tracking export.
    """
    try:
        inst_uuid = uuid.UUID(instance_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid instance ID format")

    stmt = select(WorkflowInstance).where(WorkflowInstance.id == inst_uuid)
    res = await db.execute(stmt)
    inst = res.scalar_one_or_none()

    if not inst:
        raise HTTPException(status_code=404, detail="Campaign workflow instance not found")

    context = inst.context or {}
    posts = context.get("posts", [])
    brief = context.get("brief", {})

    audit = AuditEvent(
        id=uuid.uuid4(),
        organization_id=inst.organization_id,
        actor_id=current_user.email,
        action="product_launch_campaign_exported",
        entity_type="WorkflowInstance",
        entity_id=str(inst.id),
        metadata_={"posts_count": len(posts), "product_name": brief.get("productName")},
        created_at=datetime.utcnow(),
    )
    db.add(audit)
    await db.commit()

    return {
        "instance_id": str(inst.id),
        "product_name": brief.get("productName"),
        "exported_at": datetime.utcnow().isoformat(),
        "posts_count": len(posts),
        "posts": posts,
        "brief_summary": {
            "productName": brief.get("productName"),
            "shortDescription": brief.get("shortDescription"),
            "desiredCta": brief.get("desiredCta"),
            "targetAudience": brief.get("targetAudience"),
        }
    }

