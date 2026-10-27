"""Optional OpenAI-compatible client. AI is opt-in and uses only AGV-specific environment variables."""
from __future__ import annotations
import base64
import json
import os
import re
from urllib.parse import urlsplit
import httpx


def _safe_base(url: str) -> bool:
    # The API key travels in a header, so plain http is allowed only for a model served on this machine.
    parts = urlsplit(url)
    if parts.scheme == "https":
        return bool(parts.hostname)
    return parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "::1"}


_BASE = os.environ.get("AGV_LLM_BASE_URL", "").rstrip("/")
_KEY = os.environ.get("AGV_LLM_API_KEY", "")
_MODEL = os.environ.get("AGV_LLM_MODEL", "")
_ENABLED_REQUESTED = os.environ.get("AGV_AI_ENABLED", "").lower() in {"1", "true", "yes"}
LLM_ENABLED = bool(_ENABLED_REQUESTED and _safe_base(_BASE) and _KEY and _MODEL)
LLM_VISION_MODEL = os.environ.get("AGV_LLM_VISION_MODEL", "") if LLM_ENABLED else ""

async def _request(model: str, content, temperature: float = 0.2, max_tokens: int = 900):
    if not LLM_ENABLED:
        return None
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "temperature": temperature, "max_tokens": max_tokens}
    try:
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
            response = await client.post(_BASE + "/chat/completions",
                headers={"Authorization": "Bearer " + _KEY}, json=body)
            response.raise_for_status()
            return response.json()["choices"][0]["message"].get("content")
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return None

async def chat(prompt: str, model=None, temperature=0.2, max_tokens=900):
    return await _request(model or _MODEL, prompt, temperature, max_tokens)

async def chat_json(prompt: str, model=None, max_tokens=2000):
    text = await chat(prompt, model=model, max_tokens=max_tokens)
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None

async def vision(image_bytes: bytes, prompt: str):
    if not LLM_VISION_MODEL:
        return None
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    elif image_bytes.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif image_bytes.startswith(b"GIF8"):
        mime = "image/gif"
    elif image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        return None
    encoded = base64.b64encode(image_bytes).decode("ascii")
    content = [{"type": "text", "text": prompt}, {"type": "image_url",
               "image_url": {"url": f"data:{mime};base64,{encoded}"}}]
    return await _request(LLM_VISION_MODEL, content)
