"""Entry point for Realtimex lead search package.

Run via: uv run -m realtimex_lead_search.lead_search_agent
Accepts JSON payload via stdin or --payload path. Extra fields are ignored.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
import hashlib
from typing import Any, Dict, Optional

from .lead_search import (
    anti_detection,
    lead_cache_manager,
    lead_data_manager,
    lead_extractor,
    lead_scorer,
    playwright_scraper,
    search_strategies,
)
from .lead_search.models import LeadSearchResponse, RunMetadata, SearchRequest


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def load_payload(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """Load payload from stdin (if piped) or from --payload file."""
    if not sys.stdin.isatty():
        try:
            return json.load(sys.stdin)
        except Exception:
            pass

    if args.payload:
        with open(args.payload, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(description="RealtimeX lead search agent")
    parser.add_argument("--payload", help="Path to JSON payload (if not piping stdin)")
    parser.add_argument("--use-llm", action="store_true", help="Enable LLM extraction in addition to heuristics")
    args = parser.parse_args(argv)

    payload = load_payload(args)
    if payload is None:
        sys.stderr.write("Provide payload via stdin or --payload path.\n")
        sys.exit(1)

    request = SearchRequest.from_payload(payload)
    logs: list[str] = []
    logs.append(
        f"event=payload.loaded keywords={len(request.keywords)} "
        f"locations={len(request.locations)} sources={request.sources}"
    )

    metadata = RunMetadata()
    metadata.sources_attempted = request.sources
    search_input = _normalize_search_input(request)
    metadata.search_input_json = json.dumps(search_input, ensure_ascii=False, sort_keys=True)
    metadata.search_fingerprint = hashlib.sha256(metadata.search_input_json.encode("utf-8")).hexdigest()

    steps = search_strategies.build_strategies(request)
    logs.append(f"event=strategies.built count={len(steps)}")
    anti_cfg = anti_detection.default_config(enable=bool(request.features.get("anti_detection", True)))

    preloaded_html = payload.get("preloaded_html") if isinstance(payload.get("preloaded_html"), dict) else None
    preloaded_json = payload.get("preloaded_json") if isinstance(payload.get("preloaded_json"), dict) else None

    artifacts = playwright_scraper.scrape_steps(
        steps,
        anti_detection_config=anti_cfg,
        capture_screenshots=bool(request.features.get("capture_screenshots", False)),
        browser_factory=None,  # inject Playwright browser from caller if desired
        preloaded_html=preloaded_html,
        preloaded_json=preloaded_json,
    )
    logs.append(
        f"event=scrape.completed artifacts={len(artifacts)} "
        f"preloaded_html={bool(preloaded_html)} preloaded_json={bool(preloaded_json)}"
    )

    use_llm = args.use_llm or bool(payload.get("use_llm_extraction", False))
    leads, extract_errors = lead_extractor.extract_leads(
        artifacts, llm_settings=request.llm if use_llm else None, use_llm=use_llm
    )
    logs.append(f"event=extract.completed leads_raw={len(leads)} errors={len(extract_errors)} llm={use_llm}")

    deduped, cache_stats = lead_cache_manager.dedupe_leads(leads)
    scored = lead_scorer.score_leads(deduped, request.filters)
    logs.append(
        f"event=dedupe.completed kept={cache_stats.kept} hits={cache_stats.hits} "
        f"scored={len(scored)}"
    )

    metadata.errors.extend(extract_errors)
    metadata.stats.update(
        {
            "strategies": len(steps),
            "artifacts": len(artifacts),
            "leads_raw": len(leads),
            "leads_scored": len(scored),
        }
    )
    metadata.end_time = now_iso()

    persistence_result = None
    storage = request.storage or {}
    if storage.get("sqlite_path") or storage.get("json_export"):
        persistence_result = lead_data_manager.persist(
            scored,
            metadata,
            db_path=storage.get("sqlite_path", "./data/lead_search.db"),
            json_export=bool(storage.get("json_export", False)),
            json_path=storage.get("json_path"),
        )
        logs.append(
            f"event=persist.completed rows={persistence_result.saved_rows} "
            f"db={persistence_result.db_path} json={persistence_result.json_path}"
        )

    response = LeadSearchResponse(
        metadata=metadata,
        leads=scored,
        persistence=persistence_result,
        cache=cache_stats,
        logs=logs,
        passthrough=request.passthrough,
    )

    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))


def _normalize_search_input(request: SearchRequest) -> Dict[str, Any]:
    """Produce a stable, pruned search intent snapshot for fingerprinting."""
    return {
        "keywords": sorted(request.keywords),
        "locations": sorted(request.locations),
        "sources": sorted(request.sources),
        "pages_per_source": request.pages_per_source,
        "filters": {
            "categories": sorted(request.filters.categories),
            "must_have_email": request.filters.must_have_email,
            "must_have_phone": request.filters.must_have_phone,
            "custom": request.filters.custom,
        },
        "features": request.features,
    }


if __name__ == "__main__":
    main()
