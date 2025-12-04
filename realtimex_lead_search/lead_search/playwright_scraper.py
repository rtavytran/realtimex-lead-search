"""Playwright automation: Google, Maps, directories, company pages."""

from __future__ import annotations

import time
import re
from typing import Any, Dict, Iterable, List, Optional

from .anti_detection import (
    apply_to_context,
    context_options,
    default_config,
    delay_seconds,
    render_wait_ms,
)
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
    anti_config = default_config(True) if anti_detection_config is None else anti_detection_config
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
                    segment_key=step.step_id,
                    segment_level=step.location,
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
            ctx_kwargs = context_options(anti_config)
            if hasattr(browser, "new_context"):
                context = browser.new_context(**ctx_kwargs) if ctx_kwargs else browser.new_context()
            else:
                context = browser
            apply_to_context(context, anti_config)
            page = getattr(context, "new_page")() if hasattr(context, "new_page") else context

            max_retries = max(1, int(anti_config.get("max_retries", 1)))
            last_error = None
            success = False

            for attempt in range(max_retries):
                try:
                    url = build_maps_url(step.query, step.page)
                    pre_delay = delay_seconds(anti_config)
                    if pre_delay > 0:
                        time.sleep(pre_delay)
                    page.goto(url, timeout=anti_config.get("timeout_ms", 30000))
                    # Give Maps a moment to render listings
                    render_delay = render_wait_ms(anti_config)
                    if render_delay > 0 and hasattr(page, "wait_for_timeout"):
                        page.wait_for_timeout(render_delay)

                    try:
                        first_sel = "article[role='article'], div[role='article'], div.Nv2PK"
                        if hasattr(page, "wait_for_selector"):
                            page.wait_for_selector(first_sel, timeout=anti_config.get("render_wait_ms", 3000))
                    except Exception:
                        pass

                    html_text = None
                    try:
                        if hasattr(page, "inner_text"):
                            html_text = page.inner_text("body")
                    except Exception:
                        html_text = None

                    html = html_text or page.content()
                    if _detect_captcha(html):
                        last_error = "captcha detected"
                        continue

                    listings = _extract_listings(page)
                    screenshot_path = None
                    if capture_screenshots and hasattr(page, "screenshot"):
                        screenshot_path = f"screenshot-{step.step_id}.png"
                        page.screenshot(path=screenshot_path, full_page=True)

                    artifacts.append(
                        ScrapeArtifact(
                            source=step.source,
                            step_id=step.step_id,
                            status="ok",
                            segment_key=step.step_id,
                            segment_level=step.location,
                            html=html,
                            json_blob=listings,
                            screenshot_path=screenshot_path,
                        )
                    )
                    success = True
                    break
                except Exception as exc:
                    last_error = str(exc)
                    continue

            if not success:
                artifacts.append(
                    ScrapeArtifact(
                        source=step.source,
                        step_id=step.step_id,
                        status="error",
                        segment_key=step.step_id,
                        segment_level=step.location,
                        error=last_error or "scrape failed",
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


def _extract_listings(page: Any, max_items: int = 20) -> List[Dict[str, Any]]:
    """Parse visible listing cards for cleaner downstream extraction."""
    selectors = ["article[role='article']", "div[role='article']", "div.Nv2PK"]
    cards: List[Any] = []
    for sel in selectors:
        try:
            cards = page.query_selector_all(sel) or []
        except Exception:
            cards = []
        if cards:
            break

    listings: List[Dict[str, Any]] = []
    phone_pattern = re.compile(r"\+?\d[\d\s().-]{7,}")
    category_prefixes = [
        "mobile phone repair shop",
        "cell phone store",
        "computer store",
        "used computer store",
        "electronics store",
        "computer repair service",
    ]

    for card in cards[:max_items]:
        try:
            raw_text = card.inner_text()
        except Exception:
            continue

        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]

        name = None
        for sel in ["[role='heading']", "h1", "h2", "h3", "div.fontHeadlineSmall", "span.DkEaL"]:
            try:
                el = card.query_selector(sel)
                if el:
                    name = (el.inner_text() or "").strip()
                    break
            except Exception:
                continue
        if not name:
            name = lines[0] if lines else None

        phone = None
        matches = phone_pattern.findall(raw_text or "")
        for ph in matches:
            digits = re.sub(r"\D", "", ph)
            if len(digits) >= 7:
                phone = ph.strip()
                break

        website = None
        map_url = None
        try:
            site_link = (
                card.query_selector("a[data-value='Website']")
                or card.query_selector("a[aria-label='Website']")
                or card.query_selector("a:has-text('Website')")
            )
            if site_link:
                website = site_link.get_attribute("href")
            map_link = card.query_selector("a[href*='/maps/place/']") or card.query_selector("a")
            if map_link:
                map_url = map_link.get_attribute("href")
        except Exception:
            website = website or None
            map_url = map_url or None

        # Fallback: look for URLs in raw text if site link missing
        if not website:
            url_match = re.search(r"https?://[^\s]+", raw_text)
            if url_match:
                website = url_match.group(0).strip().rstrip(").,;")

        # Address/category heuristics
        address = None
        category = None
        rating_pattern = re.compile(r"\d\.\d\(\d+\)", re.U)

        addr_match = re.search(r"(?:Address|Địa chỉ|Dia chi)[:\-]\s*(.+)", raw_text, re.I)
        if addr_match:
            address = addr_match.group(1).strip()

        cat_match = re.search(r"(?:Category)[:\-]\s*(.+)", raw_text, re.I)
        if cat_match:
            category = cat_match.group(1).strip()

        def _is_rating(line: str) -> bool:
            return bool(rating_pattern.search(line) or "review" in line.lower())

        if not category:
            for ln in lines:
                if ln == name:
                    continue
                if phone and phone in ln:
                    continue
                if url_match and url_match.group(0) in ln:
                    continue
                low = ln.lower()
                if _is_rating(ln) or "open" in low or "closed" in low or "giờ" in low:
                    continue
                if "website" in low or "directions" in low:
                    continue
                category = ln
                break

        def _clean_address(raw: str, cat: Optional[str]) -> str:
            addr = raw.strip(" ·-–")
            if "·" in addr:
                parts = [p.strip() for p in addr.split("·") if p.strip()]
                # if left part looks like a category, use the right-most part
                if parts and any(pref in parts[0].lower() for pref in category_prefixes):
                    addr = parts[-1]
            prefix_pattern = re.compile(
                r"^(mobile phone repair shop|cell phone store|computer store|used computer store|electronics store|computer repair service)\s*[·\-:–]*\s*",
                re.I,
            )
            addr = prefix_pattern.sub("", addr).strip(" ·-–")
            if cat and addr.lower().startswith(cat.lower()):
                addr = addr[len(cat):].lstrip(" ·-–")
            return addr.strip()

        if not address:
            street_tokens = [
                "st",
                "street",
                "đ",
                "đường",
                "duong",
                "road",
                "rd",
                "ave",
                "ward",
                "quan",
                "quận",
                "district",
                "phường",
                "xã",
                "p.",
                "q.",
            ]
            for ln in lines:
                low = ln.lower()
                if any(tok in low for tok in street_tokens) and re.search(r"\d{1,4}", ln):
                    # skip obvious non-addresses (ratings, category lines)
                    if _is_rating(ln):
                        continue
                    if "category" in low or "call" in low:
                        continue
                    address = _clean_address(ln, category)
                    break
        elif address:
            address = _clean_address(address, category)

        if name and name.lower() == "sponsored":
            continue

        listings.append(
            {
                "name": name,
                "phone": phone,
                "address": address.strip() if address else None,
                "category": category.strip() if category else None,
                "map_url": map_url,
                "website": website,
                "url": map_url,  # backward compatibility for extractor
                "raw_text": raw_text,
            }
        )

    return listings


def _detect_captcha(html: str) -> bool:
    """Lightweight captcha/unusual-traffic detector."""
    lowered = (html or "").lower()
    return any(
        token in lowered
        for token in ["captcha", "unusual traffic", "verify you are human", "recaptcha"]
    )


try:
    from urllib.parse import quote_plus
except ImportError:  # pragma: no cover - Py3 stdlib should always have it
    def quote_plus(value: str) -> str:
        return value.replace(" ", "+")
