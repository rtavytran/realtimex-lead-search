from realtimex_lead_search.lead_search import lead_cache_manager, lead_extractor, lead_scorer
from realtimex_lead_search.lead_search.models import ScrapeArtifact, SearchFilters


def test_extract_and_score_heuristics():
    html = """
    <html><body>
    Best Plumbing Co - Call us today! Email: hello@bestplumbing.com Phone: +1 206 555 1234
    </body></html>
    """
    art = ScrapeArtifact(source="google_maps", step_id="s1", status="ok", html=html)
    leads, errors = lead_extractor.extract_leads([art])
    assert not errors
    assert len(leads) == 1
    lead = leads[0]
    assert lead.email == "hello@bestplumbing.com"
    assert "206" in (lead.phone or "")

    deduped, cache_stats = lead_cache_manager.dedupe_leads(leads)
    assert cache_stats.kept == 1

    filters = SearchFilters(categories=["plumbing"], must_have_phone=True)
    scored = lead_scorer.score_leads(deduped, filters)
    assert scored[0].score >= 0.6
