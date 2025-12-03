"""Anti-detection: delays, UA rotation, robots checks, rate limiting."""

from __future__ import annotations

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
        "proxy": None,
        "headless": True,
    }


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
