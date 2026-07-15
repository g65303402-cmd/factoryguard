from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RouteName = Literal["safety", "privacy"]
SourceName = Literal["vision", "kws", "backend", "manual", "unknown"]


class EventPayload(BaseModel):
    event_id: str | None = None
    source: SourceName = "unknown"
    timestamp: str | None = None
    risk_type: str | None = None
    object: str | None = None
    equipment: str | None = None
    location: str | None = None
    description: str | None = None
    observed_action: str | None = None
    hazard_tags: list[str] = Field(default_factory=list)
    kws_keywords: list[str] = Field(default_factory=list)
    vision_labels: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)

    def to_search_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        extra = data.pop("extra", {}) or {}
        return {**data, **extra}


class SearchRequest(BaseModel):
    event: EventPayload
    route: RouteName | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    candidate_multiplier: int = Field(default=8, ge=3, le=20)


class EvidenceItem(BaseModel):
    rank: int
    score: float
    adjusted_score: float
    corpus: str
    chunk_id: str
    parent_id: str
    section: str | None = None
    source_filename: str | None = None
    source_pages: Any = None
    hazard_tags: Any = None
    historical_reference: bool = False
    citation_policy: str | None = None
    text: str
    parent_text: str | None = None


class SearchResponse(BaseModel):
    event_id: str | None
    route: RouteName
    query: str
    inferred_hazard_tags: list[str]
    results: list[EvidenceItem]


class ReportRequest(SearchRequest):
    include_markdown: bool = True


class ActionBasis(BaseModel):
    title: str
    source: str | None = None
    pages: Any = None
    reason: str
    corpus: str
    chunk_id: str
    parent_id: str


class ReportResponse(BaseModel):
    event_id: str | None
    route: RouteName
    event_summary: str
    recommended_action: list[str]
    legal_basis: list[ActionBasis]
    llm_context: dict[str, Any]
    markdown: str | None = None

