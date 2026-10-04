"""
core/prompt_enhancer.py
========================
AI-powered image prompt enhancer for SMBFlow product launch visuals.

Given a product brief, visual role, desired visual style, tone, and platform:
  1. Builds a structured brand context from the campaign brief
  2. Applies style presets (Realistic, 3D Render, Animated Illustration, Minimalist, Cinematic, Cyberpunk)
  3. Applies tone presets (Witty, Funny, Professional, Bold, Casual)
  4. Uses Gemini / LLMRouter to generate:
     - Rich positive image generation prompt tailored to the visual role and selected style
     - Targeted negative prompt
     - Contextual suggested caption / hook matching the tone
  5. Includes structured fallback if LLM is unavailable
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, Optional
import structlog

log = structlog.get_logger()

# ─── Platform image size specs ─────────────────────────────────────────────────
PLATFORM_SPECS = {
    "linkedin":    {"width": 1280, "height": 720,  "ratio": "16:9",  "hint": "professional, polished, B2B audience"},
    "x":           {"width": 1280, "height": 720,  "ratio": "16:9",  "hint": "punchy, bold, scroll-stopping"},
    "twitter":     {"width": 1280, "height": 720,  "ratio": "16:9",  "hint": "punchy, bold, scroll-stopping"},
    "instagram":   {"width": 1080, "height": 1080, "ratio": "1:1",   "hint": "vibrant, visually striking"},
    "facebook":    {"width": 1280, "height": 720,  "ratio": "16:9",  "hint": "clear, engaging, community feel"},
    "newsletter":  {"width": 1280, "height": 720,  "ratio": "16:9",  "hint": "clean, professional, editorial"},
    "default":     {"width": 1280, "height": 720,  "ratio": "16:9",  "hint": "professional, modern, clean"},
}

# ─── Visual Style Presets ──────────────────────────────────────────────────────
STYLE_PRESETS = {
    "photorealistic": {
        "name": "Realistic",
        "description": "Hyper-realistic commercial photography, 8k resolution, authentic studio or natural lighting, shallow depth of field, real materials, Hasselblad/Leica camera aesthetics, crisp reflections.",
        "keywords": "photorealistic commercial product photography, 8k resolution, sharp focus, studio lighting, natural depth of field, lifelike textures",
        "negative": "cartoon, 3d render, illustration, CGI, drawing, sketch, anime",
    },
    "3d": {
        "name": "3D Render",
        "description": "Ultra-detailed 3D render, Pixar/Blender/Octane render style, isometric perspective, clean glossy surfaces, soft ambient occlusion, vibrant clay or glassmorphism shaders, playful tactile feel, studio rim lighting.",
        "keywords": "3D isometric render, Octane render, Blender 3D, glossy translucent materials, ambient occlusion, smooth clay shaders, vibrant studio rim lighting, 4k 3D digital art",
        "negative": "photograph, grainy film, flat 2d, real life photo, desaturated, noisy photo",
    },
    "animated": {
        "name": "Animated / Illustration",
        "description": "Premium modern vector/digital illustration, clean bold linework, editorial tech art style like Stripe or Notion, rich harmonious color palette, flat shaded with subtle depth, dynamic composition.",
        "keywords": "modern vector illustration, digital tech editorial artwork, clean linework, vibrant flat colors, contemporary character illustration, stylish graphic design aesthetic",
        "negative": "photorealistic photo, 3d render, gritty textures, grainy film, washed out",
    },
    "minimalist": {
        "name": "Minimalist",
        "description": "Clean minimalist aesthetic, generous negative space, sleek Bauhaus composition, soft pastel or monochrome palette, elegant subtle shadows, Scandinavian design ethos.",
        "keywords": "minimalist aesthetic, clean composition, generous negative space, elegant soft shadows, sleek geometric layout, Scandinavian modern design, subdued refined color palette",
        "negative": "cluttered, busy, chaotic, high contrast, oversaturated, neon, loud",
    },
    "cinematic": {
        "name": "Cinematic",
        "description": "Cinematic wide-angle movie shot, dramatic volumetric lighting, anamorphic lens flares, rich color grading (teal & orange / filmic), atmospheric haze, high-contrast emotional visual storytelling.",
        "keywords": "cinematic film still, 35mm anamorphic lens, dramatic volumetric lighting, rich cinematic color grading, atmospheric depth, high contrast visual storytelling, movie aesthetic",
        "negative": "flat lighting, stock photo, bright cartoon, boring composition, amateur photo",
    },
    "cyberpunk": {
        "name": "Cyberpunk / Tech",
        "description": "Futuristic cyberpunk sci-fi aesthetic, glowing neon cyan and magenta accents, dark reflective wet surfaces, holographic UI overlays, high-tech dystopian or futuristic vibe.",
        "keywords": "futuristic cyberpunk aesthetic, glowing neon cyan and purple accents, dark reflective surfaces, glowing holographic UI displays, high-tech futuristic environment, vibrant synthwave lighting",
        "negative": "daylight, natural sunlight, vintage, rustic, pastel, cartoon",
    },
}

# ─── Tone Presets (Influences vibe & suggested captions) ────────────────────────
TONE_PRESETS = {
    "witty": {
        "name": "Witty & Clever",
        "vibe": "Clever, sharp, intellectual humor, relatable tech insight",
        "prompt_hint": "clever visual metaphor, smart contrasting elements, witty detail in the background",
    },
    "funny": {
        "name": "Funny & Humorous",
        "vibe": "Playful, humorous, laugh-out-loud funny observation about everyday struggles that this solves",
        "prompt_hint": "lighthearted humorous situation, exaggerated relatable emotion, fun playful energy",
    },
    "professional": {
        "name": "Professional",
        "vibe": "Authoritative, polished, executive-ready, highly credible, institutional-grade",
        "prompt_hint": "crisp professional atmosphere, executive aesthetic, premium craftsmanship, high credibility",
    },
    "bold": {
        "name": "Bold & Inspiring",
        "vibe": "Disruptive, ambitious, high-energy, confident, visionary",
        "prompt_hint": "heroic perspective, dynamic upward angle, radiant golden lighting, triumphant breakthrough mood",
    },
    "casual": {
        "name": "Casual & Friendly",
        "vibe": "Warm, conversational, approachable, authentic, no corporate jargon",
        "prompt_hint": "cozy welcoming atmosphere, warm natural sunlight, genuine relaxed interaction, approachable lifestyle",
    },
}

# ─── Visual role directions ────────────────────────────────────────────────────
ROLE_DIRECTIONS = {
    "product hero": (
        "HERO SHOT: High-impact commercial product showcase. The product itself is the unmistakable center of attention. "
        "Showcase a sleek modern device (e.g. bezel-less smartphone, tablet, or display) featuring a vibrant, beautiful, "
        "detailed UI screen with colorful interactive elements and subtle screen glow. "
        "Crisp reflections, natural depth of field, bold commercial aesthetic."
    ),
    "product / workflow / feature": (
        "FEATURE IN ACTION: Detailed close-up showing the key feature or workflow in active use. "
        "Show hands interacting with the device or a focused user engaging with the feature. "
        "The screen interface must be rich, colorful, and clearly communicate the specific value. "
        "Crisp macro view, intuitive controls, modern aesthetic."
    ),
    "customer problem / founder context": (
        "HUMAN CONTEXT & OUTCOME: An authentic, relatable story-driven editorial photograph. "
        "Show the target user experiencing the positive transformation or breakthrough moment. "
        "Natural daylight, genuine emotion, beautifully styled environment matching the industry."
    ),
}

# ─── Universal negative prompt ─────────────────────────────────────────────────
BASE_NEGATIVE = (
    "blurry, low quality, lowres, distorted, deformed, watermark, signature, "
    "garbled text, gibberish text, misspelled text, typos, wrong spelling, "
    "extra limbs, extra fingers, mutated hands, poorly drawn, jpeg artifacts, "
    "empty blank screen, plain grey display, monochrome screen, "
    "cluttered, oversaturated, overexposed, underexposed, flat lighting, "
    "stock photo cliché, amateur, ugly, dull, boring, generic"
)


def _get_platform_key(platform: str) -> str:
    p = (platform or "default").lower()
    for key in PLATFORM_SPECS:
        if key in p:
            return key
    return "default"


def _normalize_style(style: Optional[str]) -> str:
    s = (style or "photorealistic").lower().strip()
    if "3d" in s:
        return "3d"
    if "animat" in s or "illustrat" in s or "cartoon" in s or "vector" in s:
        return "animated"
    if "minimal" in s:
        return "minimalist"
    if "cinema" in s or "dramat" in s:
        return "cinematic"
    if "cyber" in s or "neon" in s or "futur" in s:
        return "cyberpunk"
    return "photorealistic"


def _normalize_tone(tone: Optional[str]) -> str:
    t = (tone or "professional").lower().strip()
    if "wit" in t or "smart" in t:
        return "witty"
    if "fun" in t or "humor" in t or "playful" in t or "joke" in t:
        return "funny"
    if "bold" in t or "inspir" in t or "energy" in t:
        return "bold"
    if "cas" in t or "friend" in t or "warm" in t:
        return "casual"
    return "professional"


def _get_role_direction(visual_role: str, industry: str = "") -> str:
    role_lower = (visual_role or "").lower()
    ind_lower = (industry or "").lower()

    if any(word in role_lower for word in ["hero"]):
        if any(w in ind_lower for w in ["edtech", "education", "learning", "student"]):
            return (
                "HERO SHOT: Commercial hero showcase of an educational product. "
                "A sleek smartphone resting on a stylish student desk beside modern notebooks, "
                "screen glowing with a vibrant interactive learning UI featuring colorful concept diagrams, "
                "gamified badges, and clear progress charts. Soft morning lighting, shallow depth of field."
            )
        return ROLE_DIRECTIONS["product hero"]

    if any(word in role_lower for word in ["workflow", "feature", "product"]):
        if any(w in ind_lower for w in ["edtech", "education", "learning", "student"]):
            return (
                "FEATURE IN ACTION: Close-up shot of hands holding a smartphone, actively using the educational app. "
                "The screen displays interactive practice questions, dynamic 3D concept visualizations, and achievement streaks. "
                "Crisp details, warm study lighting, engaging learning environment."
            )
        return ROLE_DIRECTIONS["product / workflow / feature"]

    if any(word in role_lower for word in ["problem", "founder", "context"]):
        if any(w in ind_lower for w in ["edtech", "education", "learning", "student"]):
            return (
                "LEARNER CONTEXT: An inspiring scene of a high school or university student at a study desk, "
                "smiling with genuine confidence as they master a challenging lesson using their mobile phone or tablet. "
                "Authentic atmosphere, natural light from a window, textbooks and stationery."
            )
        return ROLE_DIRECTIONS["customer problem / founder context"]

    return ROLE_DIRECTIONS["product hero"]


async def enhance_image_prompt(
    product_brief: Dict[str, Any],
    visual_role: str,
    raw_prompt: str,
    aspect_ratio: str = "16:9",
    platform: str = "LinkedIn",
    style: Optional[str] = "photorealistic",
    tone: Optional[str] = "professional",
    custom_modifications: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Uses Gemini LLM or LLMRouter to generate an enhanced, highly-specific image prompt
    tailored to the product brief, visual role, chosen visual style, and tone.
    """
    brief = product_brief or {}
    product_name = (brief.get("productName") or brief.get("product_name") or "SMBFlow").strip()
    short_desc = (brief.get("shortDescription") or brief.get("product_description") or brief.get("launchDescription") or "").strip()
    target_audience = (brief.get("targetAudience") or brief.get("audience") or "professionals and users").strip()
    value_prop = (brief.get("valueProposition") or brief.get("primaryBenefit") or "").strip()
    industry = (brief.get("industry") or brief.get("industrySegment") or "Technology").strip()

    platform_key = _get_platform_key(platform)
    specs = PLATFORM_SPECS[platform_key]
    role_direction = _get_role_direction(visual_role, industry)

    style_key = _normalize_style(style)
    tone_key = _normalize_tone(tone)
    style_info = STYLE_PRESETS[style_key]
    tone_info = TONE_PRESETS[tone_key]

    system_prompt = f"""You are a world-class commercial visual art director and AI prompt engineer.
Your task is to transform a product concept into a visually stunning, highly tailored image generation prompt AND a catchy social caption.

TARGET VISUAL STYLE: {style_info['name'].upper()}
Style Guide: {style_info['description']}
Keywords to emphasize: {style_info['keywords']}

TARGET TONE & VIBE: {tone_info['name'].upper()}
Vibe Guide: {tone_info['vibe']}
Visual mood hint: {tone_info['prompt_hint']}

INDUSTRY: {industry}
TARGET AUDIENCE: {target_audience}

CRITICAL RULES:
1. Output ONLY a valid JSON object with keys:
   - "positive_prompt": 50-85 words rich in visual composition, subject, lighting, materials, colors, camera framing, and background details. Strictly follow the {style_info['name']} style.
   - "negative_prompt": 10-15 specific artifacts or flaws to avoid, including style-specific negatives.
   - "suggested_caption": 1-2 punchy sentences tailored for {platform} matching the {tone_info['name']} tone (funny/witty/bold/etc.) and highlighting {product_name}.
2. For digital products / software / apps: ALWAYS describe an actual physical device (e.g. bezel-less smartphone, tablet, or display) with a vibrant, detailed UI screen (graphs, cards, interactive buttons). NEVER leave the screen blank.
3. No gibberish text in the image. Describe visual icons, cards, and UI illustrations rather than literal words.
4. Strictly return JSON only."""

    user_prompt = f"""Craft the enhanced prompt and caption for this campaign visual:

PRODUCT NAME: {product_name}
DESCRIPTION: {short_desc or 'Digital product for ' + industry}
CORE BENEFIT: {value_prop or short_desc}
VISUAL ROLE: {visual_role}
PLATFORM: {platform} (Aspect Ratio: {specs['ratio']})
CHOSEN VISUAL STYLE: {style_info['name']}
CHOSEN TONE: {tone_info['name']}

BASE PROMPT / CONCEPT:
{raw_prompt or 'Showcase the product effectively in action'}
{f'USER CUSTOM TWEAKS: {custom_modifications}' if custom_modifications else ''}

ROLE GUIDELINE:
{role_direction}

Output JSON only with keys: "positive_prompt", "negative_prompt", "suggested_caption"."""

    # ── Strategy 1: Google GenAI Client ──────────────────────────────────────
    google_api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if google_api_key:
        configured_model = os.environ.get("PROMPT_ENHANCER_MODEL")
        candidate_models = [m for m in [configured_model, "gemini-2.5-flash", "gemini-1.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview"] if m]
        for cand_model in candidate_models:
            try:
                from google import genai
                client = genai.Client(api_key=google_api_key)

                combined_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
                res = await asyncio.to_thread(
                    client.models.generate_content,
                    model=cand_model,
                    contents=combined_prompt,
                )

                if res and res.text:
                    cleaned = res.text.strip()
                    if "```json" in cleaned:
                        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                    elif "```" in cleaned:
                        cleaned = cleaned.split("```")[1].split("```")[0].strip()

                    data = json.loads(cleaned)
                    positive = str(data.get("positive_prompt", "")).strip()
                    negative = str(data.get("negative_prompt", "")).strip()
                    caption = str(data.get("suggested_caption", "")).strip()

                    if positive:
                        if style_key == "3d" and "3d" not in positive.lower():
                            positive = f"3D isometric render, {positive}"
                        elif style_key == "animated" and "illustration" not in positive.lower():
                            positive = f"Modern vector illustration, {positive}"
                        elif style_key == "photorealistic" and "photorealistic" not in positive.lower() and "photography" not in positive.lower():
                            positive = f"Photorealistic product photography, {positive}"

                        full_neg = f"{negative}, {style_info['negative']}, {BASE_NEGATIVE}" if negative else f"{style_info['negative']}, {BASE_NEGATIVE}"

                        log.info(
                            "PromptEnhancer: Gemini LLM enhancement successful",
                            model=cand_model,
                            style=style_key,
                            tone=tone_key,
                            product=product_name,
                        )

                        return {
                            "positive_prompt": positive,
                            "negative_prompt": full_neg,
                            "style": style_key,
                            "tone": tone_key,
                            "suggested_caption": caption or f"Introducing {product_name}: engineered for seamless {industry} execution.",
                            "width": specs["width"],
                            "height": specs["height"],
                            "enhancement_used": True,
                            "model_used": cand_model,
                        }
            except Exception as gem_err:
                log.warning(
                    "PromptEnhancer: Google GenAI model candidate failed, trying next",
                    model=cand_model,
                    error=str(gem_err),
                )

    # ── Strategy 2: LLMRouter Fallback ───────────────────────────────────────
    try:
        from core.llm_router import LLMRouter, LLMMessage
        llm = LLMRouter()
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]
        raw_response, _ = await llm.call(
            agent_name="prompt_enhancer",
            messages=messages,
            tier_override="mini",
        )
        cleaned = raw_response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned)
        positive = str(data.get("positive_prompt", "")).strip()
        negative = str(data.get("negative_prompt", "")).strip()
        caption = str(data.get("suggested_caption", "")).strip()

        if positive:
            full_neg = f"{negative}, {style_info['negative']}, {BASE_NEGATIVE}" if negative else f"{style_info['negative']}, {BASE_NEGATIVE}"
            return {
                "positive_prompt": positive,
                "negative_prompt": full_neg,
                "style": style_key,
                "tone": tone_key,
                "suggested_caption": caption,
                "width": specs["width"],
                "height": specs["height"],
                "enhancement_used": True,
                "model_used": "llm_router",
            }
    except Exception as llm_err:
        log.warning("PromptEnhancer: LLMRouter failed, using rule-based structured generator", error=str(llm_err))

    # ── Strategy 3: Rule-Based Structured Fallback Generator ──────────────────
    style_prefix = {
        "photorealistic": "Photorealistic commercial product showcase of",
        "3d": "High-fidelity 3D isometric digital render of",
        "animated": "Vibrant modern vector tech illustration of",
        "minimalist": "Minimalist Scandinavian design visual featuring",
        "cinematic": "Cinematic dramatic wide-angle shot highlighting",
        "cyberpunk": "Futuristic cyberpunk neon tech visualization of",
    }.get(style_key, "Photorealistic commercial product showcase of")

    tone_hook = {
        "witty": f"Built for teams tired of overcomplicated software. Meet {product_name}.",
        "funny": f"Remember doing this manually? Neither do we. {product_name} is here.",
        "professional": f"Accelerate your workflow with {product_name}. Enterprise-grade execution.",
        "bold": f"The future of {industry} starts today. Experience {product_name}.",
        "casual": f"Say goodbye to repetitive busywork. {product_name} makes it effortless.",
    }.get(tone_key, f"Experience {product_name} today.")

    fallback_positive = (
        f"{style_prefix} {product_name} ({industry}), {role_direction.split(':')[0].lower()} theme, "
        f"{style_info['keywords']}, {specs['hint']}, "
        f"clean composition, generous negative space, vibrant balanced colors, "
        f"hyper-detailed craftsmanship, 8k resolution"
    )

    full_neg = f"{style_info['negative']}, {BASE_NEGATIVE}"

    return {
        "positive_prompt": fallback_positive,
        "negative_prompt": full_neg,
        "style": style_key,
        "tone": tone_key,
        "suggested_caption": tone_hook,
        "width": specs["width"],
        "height": specs["height"],
        "enhancement_used": False,
        "model_used": "structured_fallback",
    }
