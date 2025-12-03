"""Data models for lead search."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _ts() -> str:
    """ISO timestamp helper."""
    return datetime.utcnow().isoformat() + "Z"


@dataclass
class LLMSettings:
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: Optional[int] = None


@dataclass
class SearchFilters:
    categories: List[str] = field(default_factory=list)
    must_have_email: bool = False
    must_have_phone: bool = False
    custom: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchRequest:
    keywords: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    vertical: Optional[str] = None
    filters: SearchFilters = field(default_factory=SearchFilters)
    sources: List[str] = field(default_factory=lambda: ["google_maps"])
    max_results: int = 50
    pages_per_source: int = 3
    timeout_seconds: int = 30
    llm: LLMSettings = field(default_factory=LLMSettings)
    storage: Dict[str, Any] = field(
        default_factory=lambda: {"sqlite_path": "./data/lead_search.db", "json_export": False}
    )
    features: Dict[str, Any] = field(
        default_factory=lambda: {"anti_detection": True, "capture_screenshots": False}
    )
    passthrough: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "SearchRequest":
        """Create from flexible JSON payload (extra fields ignored)."""
        keywords = payload.get("keywords") or []
        locations = payload.get("locations") or []
        vertical = payload.get("vertical")
        filters_payload = payload.get("filters") or {}
        filters = SearchFilters(
            categories=filters_payload.get("categories") or [],
            must_have_email=bool(filters_payload.get("must_have_email", False)),
            must_have_phone=bool(filters_payload.get("must_have_phone", False)),
            custom={
                k: v
                for k, v in filters_payload.items()
                if k not in {"categories", "must_have_email", "must_have_phone"}
            },
        )
        sources = payload.get("sources") or ["google_maps"]
        max_results = int(payload.get("max_results", 50))
        pages_per_source = int(payload.get("pages_per_source", 3))
        timeout_seconds = int(payload.get("timeout_seconds", 30))
        llm_payload = payload.get("llm") or {}
        llm = LLMSettings(
            provider=llm_payload.get("provider", "openai"),
            model=llm_payload.get("model", "gpt-4.1-mini"),
            base_url=llm_payload.get("base_url"),
            api_key=llm_payload.get("api_key"),
            temperature=float(llm_payload.get("temperature", 0.0)),
            top_p=float(llm_payload.get("top_p", 1.0)),
            max_tokens=llm_payload.get("max_tokens"),
        )
        storage = payload.get("storage") or {"sqlite_path": "./data/lead_search.db", "json_export": False}
        features = payload.get("features") or {"anti_detection": True, "capture_screenshots": False}
        passthrough = payload.get("passthrough") or {}
        return cls(
            keywords=keywords,
            locations=locations,
            vertical=vertical,
            filters=filters,
            sources=sources,
            max_results=max_results,
            pages_per_source=pages_per_source,
            timeout_seconds=timeout_seconds,
            llm=llm,
            storage=storage,
            features=features,
            passthrough=passthrough,
        )


@dataclass
class StrategyStep:
    source: str
    query: str
    location: Optional[str] = None
    page: int = 1
    max_pages: int = 1
    throttle_seconds: float = 1.0
    parser_hint: Optional[str] = None
    step_id: str = field(default_factory=lambda: f"step-{_ts()}")


@dataclass
class ScrapeArtifact:
    source: str
    step_id: str
    status: str
    html: Optional[str] = None
    json_blob: Optional[Any] = None
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    fetched_at: str = field(default_factory=_ts)


@dataclass
class LeadCandidate:
    company_name: str
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    category: Optional[str] = None
    contact_name: Optional[str] = None
    contact_title: Optional[str] = None
    confidence: float = 0.0
    source_url: Optional[str] = None
    source: Optional[str] = None
    captured_at: str = field(default_factory=_ts)


@dataclass
class ScoredLead:
    lead: LeadCandidate
    score: float
    rationale: str = ""


@dataclass
class CacheStats:
    hits: int = 0
    deduped: int = 0
    kept: int = 0


@dataclass
class PersistenceResult:
    saved_rows: int
    db_path: Optional[str] = None
    json_path: Optional[str] = None


@dataclass
class RunMetadata:
    start_time: str = field(default_factory=_ts)
    end_time: Optional[str] = None
    sources_attempted: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LeadSearchResponse:
    metadata: RunMetadata
    leads: List[ScoredLead]
    persistence: Optional[PersistenceResult] = None
    cache: Optional[CacheStats] = None
    logs: List[str] = field(default_factory=list)
    passthrough: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        def encode(obj: Any) -> Any:
            if isinstance(obj, list):
                return [encode(x) for x in obj]
            if dataclass_isinstance(obj):
                return {k: encode(v) for k, v in asdict(obj).items()}
            return obj

        return encode(self)


def dataclass_isinstance(obj: Any) -> bool:
    """Return True if obj is an instance of a dataclass."""
    return hasattr(obj, "__dataclass_fields__")
