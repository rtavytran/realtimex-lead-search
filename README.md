## realtimex-lead-search

Lead discovery and qualification flows for RealtimeX. Local-first scraping and storage; user-selected LLM (cloud or local). No auto-switching: cloud failures surface to the user.

### Structure
- `realtimex_lead_search/lead_search_agent.py` — entry point (run via `uv run -m realtimex_lead_search.lead_search_agent`).
- `realtimex_lead_search/lead_search/` — modules for scraping, LLM, extraction, scoring, data, cache, strategies, anti-detection, models, prompts.
- `docs/realtimex-lead-search-module-io.md` — module IO reference.
- `tests/` — pytest coverage for strategies, extraction/scoring, and persistence.

### Getting started
1) Use `uv run -m realtimex_lead_search.lead_search_agent --payload payload.json` to execute (or pipe JSON to stdin). No pip install inside RealtimeX flows.
2) Payload shape (extra fields ignored):
```json
{
  "keywords": ["plumber near me"],
  "locations": ["seattle"],
  "sources": ["google_maps"],
  "pages_per_source": 2,
  "filters": {"categories": ["plumbing"], "must_have_phone": true},
  "llm": {"provider": "openai", "model": "gpt-4.1-mini", "base_url": "https://api.openai.com", "api_key": "sk-..."},
  "storage": {"sqlite_path": "./data/lead_search.db", "json_export": true}
}
```
3) Optional: `use_llm_extraction: true` or CLI `--use-llm` to enable LLM parsing in addition to heuristics.
4) Keep LLM selection user-driven; do not auto-fallback between providers.

### Notes
- Keep everything local except the user-selected LLM call.
- Respect robots/delays; skip captchas rather than solving.
