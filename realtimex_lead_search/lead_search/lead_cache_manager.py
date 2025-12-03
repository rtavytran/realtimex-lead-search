"""Cache manager: deduplicate leads and track hits."""

from __future__ import annotations

from typing import Iterable, List, Set, Tuple

from .models import CacheStats, LeadCandidate


def dedupe_leads(leads: Iterable[LeadCandidate]) -> Tuple[List[LeadCandidate], CacheStats]:
    """Deduplicate by email, phone, or website host."""
    seen: Set[str] = set()
    kept: List[LeadCandidate] = []
    hits = 0

    for lead in leads:
        keys = _lead_keys(lead)
        if any(k in seen for k in keys if k):
            hits += 1
            continue
        for k in keys:
            if k:
                seen.add(k)
        kept.append(lead)

    stats = CacheStats(hits=hits, deduped=hits, kept=len(kept))
    return kept, stats


def _lead_keys(lead: LeadCandidate) -> List[str]:
    keys = []
    if lead.email:
        keys.append(f"email:{lead.email.lower()}")
    if lead.phone:
        keys.append(f"phone:{lead.phone}")
    if lead.website:
        keys.append(f"web:{lead.website.lower()}")
    return keys
