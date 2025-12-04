"""Lead extraction: parses scraped artifacts and normalizes leads."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import llm_adapter
from .models import LeadCandidate, LLMSettings, ScrapeArtifact


def extract_leads(
    artifacts: Iterable[ScrapeArtifact],
    llm_settings: Optional[LLMSettings] = None,
    use_llm: bool = False,
    llm_transport=None,
) -> Tuple[List[LeadCandidate], List[str]]:
    """
    Extract leads from artifacts. Falls back to heuristic parsing; optionally uses LLM.
    Returns (leads, errors).
    """
    leads: List[LeadCandidate] = []
    errors: List[str] = []

    for art in artifacts:
        if art.status != "ok":
            if art.error:
                errors.append(art.error)
            continue

        json_leads: List[LeadCandidate] = []
        if art.json_blob is not None:
            json_leads = _extract_from_json_blob(art.json_blob, art.source)
            leads.extend(json_leads)

        # Only fall back to HTML heuristics if we did not get structured listings.
        if not json_leads:
            html = art.html or ""
            text = _html_to_text(html)
            parsed = _heuristic_extract(text, art.source)
            leads.extend(parsed)

        # Propagate segment metadata when available
        for lead in leads:
            if lead.segment_key is None:
                lead.segment_key = getattr(art, "segment_key", None)
            if lead.segment_level is None:
                lead.segment_level = getattr(art, "segment_level", None)

        if use_llm and llm_settings:
            llm_leads, llm_err = _llm_extract(text, llm_settings, llm_transport)
            leads.extend(llm_leads)
            if llm_err:
                errors.append(llm_err)

    return leads, errors


def _heuristic_extract(text: str, source: Optional[str]) -> List[LeadCandidate]:
    """Lightweight regex-based extraction for Maps-like content."""
    leads: List[LeadCandidate] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
    phone_pattern = re.compile(r"(\+?\d[\d\s().-]{7,})")

    for line in lines:
        if len(leads) > 20:  # safeguard per page
            break
        emails = email_pattern.findall(line)
        phones = phone_pattern.findall(line)
        if not emails and not phones:
            continue
        company = line.split(" - ")[0][:120] if " - " in line else line[:120]
        leads.append(
            LeadCandidate(
                company_name=_clean_text(company),
                email=emails[0] if emails else None,
                phone=phones[0] if phones else None,
                source=source,
                confidence=0.4 + 0.1 * bool(emails),
            )
        )

    # Fallback: search across full text if line-based parse failed
    if not leads:
        phones = phone_pattern.findall(text)
        for ph in phones[:5]:
            idx = text.find(ph)
            window = text[max(0, idx - 60): idx + 20]
            # crude company guess from preceding words
            parts = window.split()
            company_guess = " ".join(parts[-6:-1]) if len(parts) >= 6 else window[:120]
            leads.append(
                LeadCandidate(
                    company_name=_clean_text(company_guess) or "Unknown",
                    phone=ph,
                    source=source,
                    confidence=0.3,
                )
            )
    return leads


def _llm_extract(
    text: str, llm_settings: LLMSettings, transport
) -> Tuple[List[LeadCandidate], Optional[str]]:
    """Use an LLM to extract structured leads from text."""
    try:
        response = llm_adapter.chat_completion(
            messages=[
                {"role": "system", "content": "Extract lead details as JSON list."},
                {"role": "user", "content": text[:6000]},
            ],
            settings=llm_settings,
            transport=transport,
            extra_payload={"response_format": {"type": "json_object"}},
        )
        choices = response.get("choices") or []
        content = choices[0]["message"]["content"] if choices else ""
        data = json.loads(content) if content else {}
        items = data if isinstance(data, list) else data.get("leads") or []
        leads: List[LeadCandidate] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            leads.append(
                LeadCandidate(
                    company_name=item.get("company_name") or "Unknown",
                    website=item.get("website"),
                    phone=item.get("phone"),
                    email=item.get("email"),
                    address=item.get("address"),
                    category=item.get("category"),
                    contact_name=item.get("contact_name"),
                    contact_title=item.get("contact_title"),
                    confidence=float(item.get("confidence", 0.6)),
                    source_url=item.get("source_url"),
                    source=item.get("source"),
                )
            )
        return leads, None
    except Exception as exc:  # pragma: no cover - depends on provider
        return [], str(exc)


def _html_to_text(html: str) -> str:
    """Strip tags and decode entities in a minimal way."""
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_from_json_blob(blob: Any, source: Optional[str]) -> List[LeadCandidate]:
    """Parse structured listings emitted by the scraper."""
    items: List[Any]
    if isinstance(blob, list):
        items = blob
    elif isinstance(blob, dict):
        items = blob.get("listings") or blob.get("results") or []
    else:
        return []

    leads: List[LeadCandidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        company = _clean_text(
            item.get("name")
            or item.get("title")
            or item.get("company_name")
            or item.get("raw_text")
            or ""
        )
        if not company:
            continue
        if company.lower() == "sponsored":
            continue
        phone_raw = item.get("phone") or ""
        phone_match = re.search(r"\+?\d[\d\s().-]{7,}", phone_raw)
        phone = phone_match.group(0).strip() if phone_match else None
        if phone:
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 7:
                phone = None

        address = _clean_text(item.get("address") or "")
        map_url = item.get("map_url") or item.get("url") or item.get("source_url")
        website_field = item.get("website") or item.get("homepage")
        website = website_field if website_field else None
        leads.append(
            LeadCandidate(
                company_name=company,
                website=website,
                phone=phone,
                email=item.get("email"),
                address=address or None,
                category=item.get("category"),
                contact_name=item.get("contact_name"),
                contact_title=item.get("contact_title"),
                confidence=float(item.get("confidence", 0.55)),
                source_url=map_url,
                source=source,
            )
        )
    return leads


def _clean_text(value: str) -> str:
    """Normalize text by trimming whitespace and removing control glyphs."""
    text = value or ""
    text = text.replace("·", " ").strip()
    text = re.sub(r"\s+", " ", text)
    # Drop control chars and private-use glyphs (keeps Unicode like Vietnamese accents)
    text = re.sub(r"[\u0000-\u001f\u007f]", "", text)
    text = re.sub(r"[\ue000-\uf8ff]", "", text)
    return text.strip(" -\t\r\n")
