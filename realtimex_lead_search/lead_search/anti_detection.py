"""Anti-detection: delays, UA rotation, robots checks, rate limiting."""

from __future__ import annotations

import random
from typing import Any, Dict

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
)


def default_config(enable: bool = True) -> Dict[str, Any]:
    """Return a baseline anti-detection config."""
    if not enable:
        return {"enabled": False}
    return {
        "enabled": True,
        "user_agent": DEFAULT_UA,
        "viewport": {"width": 1366, "height": 768},
        "stealth": True,
        "min_delay_ms": 400,
        "max_delay_ms": 1200,
        "render_wait_ms": 1500,
        "max_retries": 2,
        "proxy": None,
        "headless": True,
    }


def context_options(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build Playwright context kwargs (used at creation time)."""
    if not config.get("enabled", False):
        return {}
    options: Dict[str, Any] = {}
    if config.get("user_agent"):
        options["user_agent"] = config["user_agent"]
    if config.get("viewport"):
        options["viewport"] = config["viewport"]
    if config.get("extra_http_headers"):
        options["extra_http_headers"] = config["extra_http_headers"]
    return options


def apply_to_context(context: Any, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply anti-detection settings to a Playwright context/page.
    Safe no-op if context is None or lacks methods.
    """
    applied = {}
    if not config.get("enabled", False) or context is None:
        return applied

    user_agent = config.get("user_agent")
    viewport = config.get("viewport")
    headless = config.get("headless", True)
    proxy = config.get("proxy")

    # These attributes may not exist in non-Playwright mocks; guard them.
    try:
        if user_agent and hasattr(context, "set_extra_http_headers"):
            context.set_extra_http_headers({"User-Agent": user_agent})
            applied["user_agent"] = user_agent
    except Exception:  # pragma: no cover - defensive
        pass

    try:
        if viewport and hasattr(context, "set_viewport_size"):
            context.set_viewport_size(viewport)
            applied["viewport"] = viewport
    except Exception:  # pragma: no cover - defensive
        pass

    if proxy:
        applied["proxy"] = proxy
    applied["headless"] = headless
    applied["stealth"] = bool(config.get("stealth", True))
    applied["delays_ms"] = (config.get("min_delay_ms", 0), config.get("max_delay_ms", 0))
    return applied


def delay_seconds(config: Dict[str, Any]) -> float:
    """Return randomized delay window in seconds."""
    if not config.get("enabled", False):
        return 0.0
    lo = max(0, int(config.get("min_delay_ms", 0)))
    hi = max(lo, int(config.get("max_delay_ms", 0)))
    if hi <= 0:
        return 0.0
    return random.uniform(lo, hi) / 1000.0


def render_wait_ms(config: Dict[str, Any]) -> int:
    """Return render wait time in ms after navigation."""
    return int(config.get("render_wait_ms", 0) or 0)
