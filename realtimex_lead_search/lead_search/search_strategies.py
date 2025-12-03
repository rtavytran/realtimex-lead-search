"""Search strategies: query builders and source-specific routines."""

from __future__ import annotations

from typing import List

from .models import SearchRequest, StrategyStep


def build_strategies(request: SearchRequest) -> List[StrategyStep]:
    """Dispatch to source-specific strategy builders."""
    steps: List[StrategyStep] = []
    for source in request.sources:
        if source.lower() in {"google_maps", "maps", "google-maps"}:
            steps.extend(build_google_maps_strategies(request))
    return steps


def build_google_maps_strategies(request: SearchRequest) -> List[StrategyStep]:
    """Create strategy steps for Google Maps search."""
    steps: List[StrategyStep] = []
    if not request.keywords:
        return steps

    locations = request.locations or [None]
    max_pages = max(1, request.pages_per_source)

    for kw in request.keywords:
        for loc in locations:
            query = kw if not loc else f"{kw} {loc}"
            for page in range(1, max_pages + 1):
                steps.append(
                    StrategyStep(
                        source="google_maps",
                        query=query,
                        location=loc,
                        page=page,
                        max_pages=max_pages,
                        throttle_seconds=1.5,
                        parser_hint="maps_listing",
                    )
                )
    return steps
