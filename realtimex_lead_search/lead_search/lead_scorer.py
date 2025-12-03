"""Lead scoring: rules + LLM scoring; status assignment."""

from __future__ import annotations

from typing import List, Optional

from .models import LeadCandidate, ScoredLead, SearchFilters


def score_leads(leads: List[LeadCandidate], filters: Optional[SearchFilters] = None) -> List[ScoredLead]:
    """Simple heuristic scorer."""
    filters = filters or SearchFilters()
    scored: List[ScoredLead] = []

    for lead in leads:
        score = 0.2  # base
        rationale_parts = []

        if lead.email:
            score += 0.3
            rationale_parts.append("has_email")
        if lead.phone:
            score += 0.2
            rationale_parts.append("has_phone")
        if lead.category and filters.categories:
            if lead.category.lower() in [c.lower() for c in filters.categories]:
                score += 0.2
                rationale_parts.append("category_match")
        if filters.must_have_email and not lead.email:
            score -= 0.3
            rationale_parts.append("missing_required_email")
        if filters.must_have_phone and not lead.phone:
            score -= 0.2
            rationale_parts.append("missing_required_phone")

        score = max(0.0, min(1.0, score))
        rationale = ", ".join(rationale_parts) if rationale_parts else "baseline"
        scored.append(ScoredLead(lead=lead, score=score, rationale=rationale))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
