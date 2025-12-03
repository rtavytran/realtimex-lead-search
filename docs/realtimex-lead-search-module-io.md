# realtimex-lead-search Module IO Map
Quick reference for this package: roles, inputs, and outputs for each Python module. Runs inside RealtimeX flows via `uv run -m realtimex_lead_search.lead_search_agent` (no pip/CLI install inside the flow).

## realtimex_lead_search/lead_search_agent.py
- **Role**: Orchestrate an entire run.
- **Input**: Search intent (keywords, locations, vertical, filters), allowed sources, scrape limits (pages/timeouts), LLM settings (provider, model, base URL, API key), storage prefs (DB path, JSON export toggle), feature flags (anti-detection, screenshots).
- **Output**: Run metadata (start/end, sources attempted, errors), aggregated normalized+scored leads, file/DB references, cache-hit stats, per-source logs.

## realtimex_lead_search/lead_search/search_strategies.py
- **Role**: Build ordered strategy steps per source.
- **Input**: Intent + filters, allowed sources, pagination/limit rules, regional hints, throttling preferences.
- **Output**: Strategy step list (source id, query templates, pagination plan, throttle/delay guidance, parser hints).

## realtimex_lead_search/lead_search/playwright_scraper.py
- **Role**: Execute strategy steps with Playwright.
- **Input**: Strategy steps, anti-detection settings, optional source credentials, timeouts, capture flags (HTML/JSON/screenshots).
- **Output**: Scrape artifacts per step (HTML/JSON, optional screenshot paths), fetch metadata (status, timings), scrape errors (non-fatal aggregation).

## realtimex_lead_search/lead_search/anti_detection.py
- **Role**: Harden Playwright contexts/pages.
- **Input**: Playwright context/page objects, anti-bot config (headers, UA, viewport, proxy hooks, delay ranges, stealth toggles).
- **Output**: Prepared contexts/pages with applied mitigations and a record of what was set.

## realtimex_lead_search/lead_search/lead_extractor.py
- **Role**: Turn raw artifacts into normalized lead candidates.
- **Input**: Scrape artifacts (HTML/JSON text, optional screenshots), extraction prompts/parsers, LLM adapter handle, source parsing hints.
- **Output**: Normalized lead candidates (company/contact fields, source refs, timestamps) plus extraction errors and confidence signals.

## realtimex_lead_search/lead_search/lead_scorer.py
- **Role**: Score and rank leads.
- **Input**: Normalized leads, scoring configuration (weights, disqualifiers), optional LLM rationale prompts.
- **Output**: Leads annotated with scores, rank ordering, rationales, and disqualification flags.

## realtimex_lead_search/lead_search/lead_cache_manager.py
- **Role**: Deduplicate and track cache hits.
- **Input**: Candidate/scored leads, cache keys (domain/phone/email), existing cache state.
- **Output**: Deduplicated leads, cache-hit stats, updated cache snapshot ready to persist.

## realtimex_lead_search/lead_search/lead_data_manager.py
- **Role**: Persist outputs and load prior runs.
- **Input**: Final leads, run metadata, persistence options (SQLite path default `./data/lead_search.db`, JSON export toggle/path), schema/version info.
- **Output**: Persistence result (rows written, file paths), loaded prior runs (when requested), migration/setup status for idempotent DB creation.

## realtimex_lead_search/lead_search/llm_adapter.py
- **Role**: Single-provider LLM calls (no auto-fallback).
- **Input**: Provider/model/base URL/API key from user, prompt payloads (messages or extraction instructions), temperature/top_p/max_tokens, optional response schema.
- **Output**: LLM responses or parsed structured data; surfaced provider errors (no cross-provider retries).

## realtimex_lead_search/lead_search/prompts.py
- **Role**: Store prompt templates and parsing expectations.
- **Input**: Access requests by name/context with optional variables for templating.
- **Output**: Rendered prompt text/structures and parsing expectations; no side effects.

## realtimex_lead_search/lead_search/models.py
- **Role**: Define data models.
- **Input**: Construction from incoming payloads or intermediate data.
- **Output**: Typed objects for requests, strategies, artifacts, leads, scores, metadata, and errors with dict/JSON serialization helpers.

## tests/
- **Role**: Unit/integration coverage.
- **Input**: Fixtures for sample HTML/JSON, mock LLM responses, strategy inputs.
- **Output**: Validation of strategy selection, scraping mocks, extraction, scoring, caching, and persistence behavior.