import pytest

from realtimex_lead_search.lead_search.models import SearchRequest
from realtimex_lead_search.lead_search import search_strategies


def test_google_maps_strategy_builds_pages_per_keyword_location():
    payload = {
        "keywords": ["plumber", "electrician"],
        "locations": ["seattle", "portland"],
        "pages_per_source": 2,
        "sources": ["google_maps"],
    }
    req = SearchRequest.from_payload(payload)
    steps = search_strategies.build_strategies(req)
    # 2 keywords * 2 locations * 2 pages = 8
    assert len(steps) == 8
    assert all(step.source == "google_maps" for step in steps)
    assert steps[0].page == 1
    assert steps[1].page == 2
