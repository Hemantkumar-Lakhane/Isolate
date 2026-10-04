"""
core/image_router.py
====================
Multi-Provider Intelligent Image Generation Router for SMBFlow.

Supported Providers:
  1. OpenAI DALL-E 3 (Highest commercial fidelity via OPENAI_API_KEY)
  2. Google Gemini / Imagen (Official google-genai SDK via GEMINI_API_KEY)
  3. Hugging Face Inference API (FLUX.1-schnell / SDXL via HUGGINGFACE_API_KEY or HF_TOKEN)
  4. Pollinations AI (Flux / SDXL resilient fallback)

Features:
  - Agent Security Firewall integration to reject prompt injection / malicious exploit generation
  - AI Prompt Enhancement (Style & Tone synthesis via Groq / OpenAI / Gemini)
  - Automatic quota exhaustion recovery (429 gracefully cascades to next provider)
  - Base64 local artifact persistence + data URL delivery
"""

import asyncio
import base64
import json
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from core.security_firewall import AgentSecurityFirewall

log = structlog.get_logger()


class ImageRouter:
    """
    Multi-Provider Image Generation Router for Product Launch & Marketing visuals.
    Cascades through configured providers: OpenAI DALL-E 3 -> Gemini -> Hugging Face -> Pollinations.
    Never returns fake placeholders. Real images only.
    """

    def __init__(
        self,
        default_model: str = "dall-e-3",
        pollinations_model: str = "flux",
    ):
        self.default_model = default_model
        self.pollinations_model = pollinations_model

    async def generate(
        self,
        prompt: str,
        visual_role: str,
        aspect_ratio: str = "16:9",
        product_brief: Optional[Dict[str, Any]] = None,
        brand_context: Optional[Dict[str, Any]] = None,
        reference_images: Optional[List[str]] = None,
        resolution: str = "1K",
        model_override: Optional[str] = None,
        preview_only: bool = False,
        style: Optional[str] = None,
        tone: Optional[str] = None,
        enhanced_prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate image asset from prompt, visual role, brief, and brand context.
        Enhances prompt with style and tone if not already enhanced.
        Cascades through OpenAI DALL-E 3 -> Google Gemini -> Hugging Face -> Pollinations AI.
        """
        brief = product_brief or {}
        product_name = brief.get("productName") or brief.get("product_name") or "SMBFlow Launch"
        platform = brief.get("platform") or (brief.get("platforms")[0] if isinstance(brief.get("platforms"), list) and brief.get("platforms") else "LinkedIn")

        # ── 1. Security Firewall Gate ─────────────────────────────────────────
        AgentSecurityFirewall.assert_safe(f"{product_name} {visual_role} {prompt} {enhanced_prompt or ''}", agent_name="image_router")

        from core.prompt_enhancer import enhance_image_prompt, PLATFORM_SPECS, _get_platform_key

        platform_key = _get_platform_key(platform)
        specs = PLATFORM_SPECS[platform_key]
        img_width = specs["width"]
        img_height = specs["height"]
        applied_style = style or "photorealistic"
        applied_tone = tone or "professional"
        suggested_caption = None

        if enhanced_prompt and enhanced_prompt.strip():
            positive_prompt = enhanced_prompt.strip()
            negative_prompt = (negative_prompt or "").strip()
            log.info("ImageRouter: using user-refined enhanced prompt", prompt_preview=positive_prompt[:80])
        else:
            enhanced = await enhance_image_prompt(
                product_brief=brief,
                visual_role=visual_role,
                raw_prompt=prompt or "",
                aspect_ratio=aspect_ratio,
                platform=platform,
                style=style,
                tone=tone,
            )
            positive_prompt = enhanced["positive_prompt"]
            negative_prompt = enhanced["negative_prompt"]
            img_width = enhanced.get("width", img_width)
            img_height = enhanced.get("height", img_height)
            applied_style = enhanced.get("style", applied_style)
            applied_tone = enhanced.get("tone", applied_tone)
            suggested_caption = enhanced.get("suggested_caption")

        log.info(
            "ImageRouter.generate starting",
            role=visual_role,
            aspect_ratio=aspect_ratio,
            product_name=product_name,
            resolution=resolution,
            style=applied_style,
            tone=applied_tone,
            preview_only=preview_only,
        )

        if preview_only:
            preview_url = self._generate_preview_svg_url(product_name, visual_role, positive_prompt, aspect_ratio, resolution)
            return {
                "status": "preview_only",
                "generated_asset_url": preview_url,
                "generation_model": "svg_preview",
                "provider": "preview",
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "visual_role": visual_role,
                "visual_prompt": prompt,
                "enhanced_prompt": positive_prompt,
                "negative_prompt": negative_prompt,
                "style": applied_style,
                "tone": applied_tone,
                "suggested_caption": suggested_caption,
                "created_at": datetime.utcnow().isoformat(),
            }

        provider_errors = []

        # ── 1. PROVIDER: OpenAI DALL-E 3 ───────────────────────────────────────
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if openai_api_key:
            try:
                dall_res = await self._generate_openai_dalle(
                    prompt=positive_prompt,
                    visual_role=visual_role,
                    aspect_ratio=aspect_ratio,
                    product_name=product_name,
                    api_key=openai_api_key,
                )
                if dall_res and dall_res.get("status") == "generated":
                    log.info("Image generation (OpenAI DALL-E 3) succeeded", role=visual_role)
                    dall_res.update({
                        "enhanced_prompt": positive_prompt,
                        "negative_prompt": negative_prompt,
                        "style": applied_style,
                        "tone": applied_tone,
                        "suggested_caption": suggested_caption,
                    })
                    return dall_res
                provider_errors.append(f"OpenAI: {dall_res.get('error') if dall_res else 'empty response'}")
            except Exception as e:
                provider_errors.append(f"OpenAI Exception: {str(e)}")
                log.warning("OpenAI DALL-E generation failed, cascading to next provider", error=str(e))

        # ── 2. PROVIDER: Google Gemini / Imagen ───────────────────────────────
        gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if gemini_api_key:
            try:
                gem_res = await self._generate_gemini(
                    prompt=positive_prompt,
                    visual_role=visual_role,
                    aspect_ratio=aspect_ratio,
                    product_name=product_name,
                    model=model_override or "gemini-2.0-flash",
                    resolution=resolution,
                    api_key=gemini_api_key,
                )
                if gem_res and gem_res.get("status") == "generated":
                    log.info("Image generation (Gemini) succeeded", role=visual_role, model=gem_res.get("generation_model"))
                    gem_res.update({
                        "enhanced_prompt": positive_prompt,
                        "negative_prompt": negative_prompt,
                        "style": applied_style,
                        "tone": applied_tone,
                        "suggested_caption": suggested_caption,
                    })
                    return gem_res
                provider_errors.append(f"Gemini: {gem_res.get('error') if gem_res else 'empty response'}")
            except Exception as e:
                provider_errors.append(f"Gemini Exception: {str(e)}")
                log.warning("Gemini image generation failed, cascading to next provider", error=str(e))

        # ── 3. PROVIDER: Hugging Face Inference API (FLUX.1-schnell / SDXL) ──
        hf_token = os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN")
        if hf_token:
            try:
                hf_res = await self._generate_huggingface(
                    prompt=positive_prompt,
                    visual_role=visual_role,
                    aspect_ratio=aspect_ratio,
                    product_name=product_name,
                    api_key=hf_token,
                    negative_prompt=negative_prompt or "",
                )
                if hf_res and hf_res.get("status") == "generated":
                    log.info("Image generation (Hugging Face) succeeded", role=visual_role)
                    hf_res.update({
                        "enhanced_prompt": positive_prompt,
                        "negative_prompt": negative_prompt,
                        "style": applied_style,
                        "tone": applied_tone,
                        "suggested_caption": suggested_caption,
                    })
                    return hf_res
                provider_errors.append(f"HuggingFace: {hf_res.get('error') if hf_res else 'empty response'}")
            except Exception as e:
                provider_errors.append(f"HuggingFace Exception: {str(e)}")
                log.warning("HuggingFace image generation failed, cascading to next provider", error=str(e))

        # ── 4. PROVIDER: Pollinations AI (Flux / SDXL Resilient Fallback) ───────
        pollinations_api_key = os.environ.get("POLLINATIONS_API_KEY") or ""
        try:
            poll_res = await self._generate_pollinations(
                prompt=positive_prompt,
                visual_role=visual_role,
                aspect_ratio=aspect_ratio,
                product_name=product_name,
                model=self.pollinations_model,
                resolution=resolution,
                api_key=pollinations_api_key,
                negative_prompt=negative_prompt or "",
                width=img_width,
                height=img_height,
            )
            if poll_res and poll_res.get("status") == "generated":
                log.info("Image generation (Pollinations AI) succeeded", role=visual_role, model=poll_res.get("generation_model"))
                poll_res["fallback_used"] = len(provider_errors) > 0
                poll_res["previous_provider_errors"] = provider_errors
                poll_res.update({
                    "enhanced_prompt": positive_prompt,
                    "negative_prompt": negative_prompt,
                    "style": applied_style,
                    "tone": applied_tone,
                    "suggested_caption": suggested_caption,
                })
                return poll_res

            poll_err = poll_res.get("error", "Pollinations generation failed") if poll_res else "Empty response"
            provider_errors.append(f"Pollinations: {poll_err}")
        except Exception as poll_exc:
            provider_errors.append(f"Pollinations Exception: {str(poll_exc)}")
            log.error("Pollinations fallback exception", error=str(poll_exc))

        log.error("All image generation providers failed", errors=provider_errors)
        return {
            "status": "failed",
            "generated_asset_url": None,
            "error": " | ".join(provider_errors),
            "generation_model": self.pollinations_model,
            "provider": "multi_provider_fallback",
            "enhanced_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "style": applied_style,
            "tone": applied_tone,
            "created_at": datetime.utcnow().isoformat(),
        }

    async def _generate_openai_dalle(
        self,
        prompt: str,
        visual_role: str,
        aspect_ratio: str,
        product_name: str,
        api_key: str,
    ) -> Dict[str, Any]:
        """Generate high-resolution commercial asset using OpenAI DALL-E 3 API."""
        try:
            import litellm
            size = "1792x1024" if aspect_ratio == "16:9" else ("1024x1792" if aspect_ratio == "9:16" else "1024x1024")
            dalle_prompt = f"Commercial product visual for '{product_name}'. Role: {visual_role}. {prompt}"
            
            response = await litellm.aimage_generation(
                model="dall-e-3",
                prompt=dalle_prompt,
                size=size,
                quality="standard",
                n=1,
                api_key=api_key,
            )

            image_url = response.data[0]["url"] if response and hasattr(response, "data") and response.data else None
            if not image_url:
                return {"status": "failed", "error": "OpenAI DALL-E returned no image URL"}

            def fetch_url(url: str) -> bytes:
                req = urllib.request.Request(url, headers={"User-Agent": "SMBFlow/1.0"})
                with urllib.request.urlopen(req, timeout=40) as resp:
                    return resp.read()

            loop = asyncio.get_running_loop()
            img_bytes = await loop.run_in_executor(None, fetch_url, image_url)

            storage_dir = Path("evidence/generated_assets")
            storage_dir.mkdir(parents=True, exist_ok=True)
            filename = f"vis_dalle_{uuid.uuid4().hex[:8]}.png"
            file_path = storage_dir / filename
            file_path.write_bytes(img_bytes)

            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            asset_url = f"data:image/png;base64,{b64_img}"

            return {
                "status": "generated",
                "generated_asset_url": asset_url,
                "storage_path": str(file_path),
                "generation_model": "dall-e-3",
                "provider": "openai",
                "aspect_ratio": aspect_ratio,
                "visual_role": visual_role,
                "visual_prompt": prompt,
                "cost_usd": 0.04,
                "created_at": datetime.utcnow().isoformat(),
            }
        except Exception as err:
            return {"status": "failed", "error": str(err)}

    async def _generate_huggingface(
        self,
        prompt: str,
        visual_role: str,
        aspect_ratio: str,
        product_name: str,
        api_key: str,
        negative_prompt: str = "",
    ) -> Dict[str, Any]:
        """Generate image using Hugging Face Serverless Inference API."""
        try:
            model_id = "black-forest-labs/FLUX.1-schnell"
            api_url = f"https://api-inference.huggingface.co/models/{model_id}"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = json.dumps({"inputs": f"Product marketing for '{product_name}': {prompt}"}).encode("utf-8")

            def sync_hf_request() -> bytes:
                req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=50) as resp:
                    return resp.read()

            loop = asyncio.get_running_loop()
            img_bytes = await loop.run_in_executor(None, sync_hf_request)

            if not img_bytes or len(img_bytes) < 1000:
                return {"status": "failed", "error": "Hugging Face returned invalid byte payload"}

            storage_dir = Path("evidence/generated_assets")
            storage_dir.mkdir(parents=True, exist_ok=True)
            filename = f"vis_hf_{uuid.uuid4().hex[:8]}.png"
            file_path = storage_dir / filename
            file_path.write_bytes(img_bytes)

            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            asset_url = f"data:image/png;base64,{b64_img}"

            return {
                "status": "generated",
                "generated_asset_url": asset_url,
                "storage_path": str(file_path),
                "generation_model": model_id,
                "provider": "huggingface",
                "aspect_ratio": aspect_ratio,
                "visual_role": visual_role,
                "visual_prompt": prompt,
                "cost_usd": 0.001,
                "created_at": datetime.utcnow().isoformat(),
            }
        except Exception as err:
            return {"status": "failed", "error": str(err)}

    async def _generate_gemini(
        self,
        prompt: str,
        visual_role: str,
        aspect_ratio: str,
        product_name: str,
        model: str,
        resolution: str,
        api_key: str,
    ) -> Dict[str, Any]:
        """Real Gemini / Imagen image generation using official google-genai SDK."""
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            enhanced_prompt = (
                f"Marketing visual for product '{product_name}'. Role: {visual_role}. Aspect ratio: {aspect_ratio}. "
                f"Prompt: {prompt}. High resolution commercial product marketing visual, clean composition."
            )

            img_bytes = None

            try:
                content_res = client.models.generate_content(
                    model=model,
                    contents=f"Generate a high-quality product image: {enhanced_prompt}",
                )
                if content_res and content_res.candidates and len(content_res.candidates) > 0:
                    for part in content_res.candidates[0].content.parts:
                        if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                            img_bytes = part.inline_data.data
                            break
            except Exception as content_err:
                log.info("Gemini generate_content image call error", error=str(content_err))
                return {"status": "failed", "error": str(content_err)}

            if not img_bytes:
                return {
                    "status": "failed",
                    "generated_asset_url": None,
                    "error": "Gemini API returned no image data",
                    "generation_model": model,
                    "provider": "google_genai",
                }

            storage_dir = Path("evidence/generated_assets")
            storage_dir.mkdir(parents=True, exist_ok=True)
            filename = f"vis_{uuid.uuid4().hex[:8]}.png"
            file_path = storage_dir / filename
            file_path.write_bytes(img_bytes)

            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            asset_url = f"data:image/png;base64,{b64_img}"

            log.info("Gemini image generation succeeded", role=visual_role, model=model, bytes_saved=len(img_bytes))

            return {
                "status": "generated",
                "generated_asset_url": asset_url,
                "storage_path": str(file_path),
                "generation_model": model,
                "provider": "google_genai",
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "visual_role": visual_role,
                "visual_prompt": prompt,
                "tokens_in": 50,
                "tokens_out": 100,
                "cost_usd": 0.02,
                "created_at": datetime.utcnow().isoformat(),
            }
        except Exception as api_err:
            log.error("Gemini image generation API error", error=str(api_err))
            return {
                "status": "failed",
                "generated_asset_url": None,
                "error": f"Gemini API error: {str(api_err)}",
                "generation_model": model,
                "provider": "google_genai",
                "created_at": datetime.utcnow().isoformat(),
            }

    async def _generate_pollinations(
        self,
        prompt: str,
        visual_role: str,
        aspect_ratio: str,
        product_name: str,
        model: str,
        resolution: str,
        api_key: str,
        negative_prompt: str = "",
        width: int = 1280,
        height: int = 720,
    ) -> Dict[str, Any]:
        """Generate image via Pollinations AI (Authenticated Flux or Resilient Public Fallback)."""
        if not width or not height:
            size_map = {
                "1:1":  {"width": 1024, "height": 1024},
                "16:9": {"width": 1280, "height": 720},
                "9:16": {"width": 720,  "height": 1280},
                "4:3":  {"width": 1024, "height": 768},
            }
            sz = size_map.get(aspect_ratio, {"width": 1280, "height": 720})
            width, height = sz["width"], sz["height"]

        encoded_prompt = urllib.parse.quote(prompt)

        def sync_fetch_image() -> bytes:
            if api_key and api_key not in ("dummy", "", "null"):
                auth_url = f"https://gen.pollinations.ai/image/{encoded_prompt}?key={api_key}&model={model}&width={width}&height={height}&nologo=true"
                if negative_prompt:
                    auth_url += f"&negative={urllib.parse.quote(negative_prompt[:250])}"
                try:
                    req = urllib.request.Request(auth_url, headers={"Authorization": f"Bearer {api_key}", "User-Agent": "SMBFlow/1.0"})
                    with urllib.request.urlopen(req, timeout=40) as resp:
                        data = resp.read()
                        if data and len(data) > 1000:
                            return data
                except Exception as auth_err:
                    log.warning("Pollinations auth key failed, using resilient public fallback", error=str(auth_err))

            candidate_sizes = [(width, height), (1024, 576), (800, 450), (640, 360), (512, 512)]
            last_err = None
            for w, h in candidate_sizes:
                pub_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={w}&height={h}&safe=false"
                try:
                    req = urllib.request.Request(pub_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    with urllib.request.urlopen(req, timeout=35) as resp:
                        data = resp.read()
                        if data and len(data) > 1000:
                            return data
                except Exception as err:
                    last_err = err

            raise last_err or RuntimeError("All candidate resolutions failed")

        loop = asyncio.get_running_loop()
        img_bytes = await loop.run_in_executor(None, sync_fetch_image)

        storage_dir = Path("evidence/generated_assets")
        storage_dir.mkdir(parents=True, exist_ok=True)
        filename = f"vis_poll_{uuid.uuid4().hex[:8]}.png"
        file_path = storage_dir / filename
        file_path.write_bytes(img_bytes)

        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        asset_url = f"data:image/png;base64,{b64_img}"

        log.info("Pollinations image generation succeeded", role=visual_role, model=model, bytes_saved=len(img_bytes))

        return {
            "status": "generated",
            "generated_asset_url": asset_url,
            "storage_path": str(file_path),
            "generation_model": model,
            "provider": "pollinations",
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "visual_role": visual_role,
            "visual_prompt": prompt,
            "enhanced_prompt": prompt,
            "negative_prompt": negative_prompt,
            "tokens_in": 50,
            "tokens_out": 100,
            "cost_usd": 0.00,
            "created_at": datetime.utcnow().isoformat(),
        }

    async def regenerate(
        self,
        visual_id: str,
        prompt: str,
        visual_role: str,
        aspect_ratio: str = "16:9",
        product_brief: Optional[Dict[str, Any]] = None,
        resolution: str = "1K",
        preview_only: bool = False,
        style: Optional[str] = None,
        tone: Optional[str] = None,
        enhanced_prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self.generate(
            prompt=prompt,
            visual_role=visual_role,
            aspect_ratio=aspect_ratio,
            product_brief=product_brief,
            resolution=resolution,
            preview_only=preview_only,
            style=style,
            tone=tone,
            enhanced_prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
        )
        result["visual_id"] = visual_id
        result["regenerated_at"] = datetime.utcnow().isoformat()
        return result

    async def edit(
        self,
        visual_id: str,
        new_prompt: str,
        visual_role: str,
        aspect_ratio: str = "16:9",
        preview_only: bool = False,
        style: Optional[str] = None,
        tone: Optional[str] = None,
        enhanced_prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = await self.generate(
            prompt=new_prompt,
            visual_role=visual_role,
            aspect_ratio=aspect_ratio,
            preview_only=preview_only,
            style=style,
            tone=tone,
            enhanced_prompt=enhanced_prompt,
            negative_prompt=negative_prompt,
        )
        result["visual_id"] = visual_id
        result["edited_at"] = datetime.utcnow().isoformat()
        return result

    def _generate_preview_svg_url(
        self,
        product_name: str,
        role: str,
        prompt: str,
        aspect_ratio: str,
        resolution: str,
    ) -> str:
        width = 1200
        height = 1200 if aspect_ratio == "1:1" else 675
        svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="#1e1b4b"/><text x="60" y="100" fill="#ffffff" font-size="24">{role}</text><text x="60" y="200" fill="#818cf8" font-size="40">{product_name}</text></svg>"""
        b64_svg = base64.b64encode(svg_content.encode("utf-8")).decode("utf-8")
        return f"data:image/svg+xml;base64,{b64_svg}"
