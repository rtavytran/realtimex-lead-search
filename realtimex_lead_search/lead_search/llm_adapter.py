"""LLM adapter for user-selected provider/model (cloud or local)."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional
from urllib import request

from .models import LLMSettings

Transport = Callable[[str, Dict[str, str], bytes], Dict[str, Any]]


def _default_transport(url: str, headers: Dict[str, str], body: bytes) -> Dict[str, Any]:
    """Minimal HTTP transport using urllib to avoid extra deps."""
    req = request.Request(url, data=body, headers=headers, method="POST")
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat_completion(
    messages: List[Dict[str, str]],
    settings: LLMSettings,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    transport: Optional[Transport] = None,
    extra_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Call an OpenAI-compatible chat completion endpoint.
    Only one provider/model is used; no auto-fallback.
    """
    base_url = settings.base_url or "https://api.openai.com"
    url = f"{base_url.rstrip('/')}/v1/chat/completions"

    payload = {
        "model": settings.model or "gpt-4.1-mini",
        "messages": messages,
        "temperature": temperature if temperature is not None else settings.temperature,
        "top_p": top_p if top_p is not None else settings.top_p,
    }
    if max_tokens is not None or settings.max_tokens is not None:
        payload["max_tokens"] = max_tokens or settings.max_tokens
    if extra_payload:
        payload.update(extra_payload)

    headers = {
        "Content-Type": "application/json",
    }
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"

    body = json.dumps(payload).encode("utf-8")
    runner = transport or _default_transport
    return runner(url, headers, body)
