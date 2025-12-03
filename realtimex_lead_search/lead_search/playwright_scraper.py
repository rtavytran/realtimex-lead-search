"""Playwright automation: Google, Maps, directories, company pages."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .anti_detection import apply_to_context
from .models import ScrapeArtifact, StrategyStep


def scrape_steps(
    steps: Iterable[StrategyStep],
    anti_detection_config: Optional[Dict[str, Any]] = None,
    capture_screenshots: bool = False,
    browser_factory: Optional[Any] = None,
    preloaded_html: Optional[Dict[str, str]] = None,
    preloaded_json: Optional[Dict[str, Any]] = None,
) -> List[ScrapeArtifact]:
    """
    Execute strategy steps. If Playwright/browser is not provided, falls back to preloaded data
    and marks remaining steps as skipped.
    """
    artifacts: List[ScrapeArtifact] = []
    anti_config = anti_detection_config or {}
    preloaded_html = preloaded_html or {}
    preloaded_json = preloaded_json or {}

    for step in steps:
        preload_html = preloaded_html.get(step.step_id) or preloaded_html.get(step.query)
        preload_json = preloaded_json.get(step.step_id) or preloaded_json.get(step.query)

        if preload_html is not None or preload_json is not None:
            artifacts.append(
                ScrapeArtifact(
                    source=step.source,
                    step_id=step.step_id,
                    status="ok",
                    html=preload_html,
                    json_blob=preload_json,
                )
            )
            continue

        if browser_factory is None:
            artifacts.append(
                ScrapeArtifact(
                    source=step.source,
                    step_id=step.step_id,
                    status="skipped",
                    error="Playwright browser_factory not provided; supply preloaded_html or browser.",
                )
            )
            continue

        # Basic Playwright execution if a factory is provided.
        try:
            browser = browser_factory()
            context = getattr(browser, "new_context")() if hasattr(browser, "new_context") else browser
            apply_to_context(context, anti_config)
            page = getattr(context, "new_page")() if hasattr(context, "new_page") else context

            url = build_maps_url(step.query, step.page)
            page.goto(url, timeout=anti_config.get("timeout_ms", 30000))
            # Give Maps a moment to render listings
            if hasattr(page, "wait_for_timeout"):
                page.wait_for_timeout(1500)

            html_text = None
            try:
                if hasattr(page, "inner_text"):
                    html_text = page.inner_text("body")
            except Exception:
                html_text = None

            html = html_text or page.content()
            screenshot_path = None
            if capture_screenshots and hasattr(page, "screenshot"):
                screenshot_path = f"screenshot-{step.step_id}.png"
                page.screenshot(path=screenshot_path, full_page=True)

            artifacts.append(
                ScrapeArtifact(
                    source=step.source,
                    step_id=step.step_id,
                    status="ok",
                    html=html,
                    screenshot_path=screenshot_path,
                )
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            artifacts.append(
                ScrapeArtifact(
                    source=step.source,
                    step_id=step.step_id,
                    status="error",
                    error=str(exc),
                )
            )
        finally:
            try:
                if browser_factory and "browser" in locals() and hasattr(browser, "close"):
                    browser.close()
            except Exception:
                pass

    return artifacts


def build_maps_url(query: str, page: int) -> str:
    """Simple Google Maps search URL generator with pagination support."""
    # Maps pagination uses start offset by 10 results; approximate with page size 20.
    start = max(0, (page - 1) * 20)
    return f"https://www.google.com/maps/search/{quote_plus(query)}?start={start}"


try:
    from urllib.parse import quote_plus
except ImportError:  # pragma: no cover - Py3 stdlib should always have it
    def quote_plus(value: str) -> str:
        return value.replace(" ", "+")
