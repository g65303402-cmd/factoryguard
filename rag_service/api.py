from __future__ import annotations

from fastapi import FastAPI

from .engine import get_engine
from .schemas import ReportRequest, ReportResponse, SearchRequest, SearchResponse


app = FastAPI(
    title="Factory Guard Conveyor RAG API",
    description="Law/evidence search and report-basis generator for conveyor safety events.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    engine = get_engine()
    return {
        "status": "ok",
        "indexes": {route: len(rows) for route, rows in engine.metadata.items()},
    }


@app.post("/rag/search", response_model=SearchResponse)
def rag_search(request: SearchRequest) -> SearchResponse:
    engine = get_engine()
    return engine.search(
        event=request.event.to_search_dict(),
        route=request.route,
        top_k=request.top_k,
        candidate_multiplier=request.candidate_multiplier,
    )


@app.post("/rag/report", response_model=ReportResponse)
def rag_report(request: ReportRequest) -> ReportResponse:
    engine = get_engine()
    return engine.build_report_basis(
        event=request.event.to_search_dict(),
        route=request.route,
        top_k=request.top_k,
        candidate_multiplier=request.candidate_multiplier,
        include_markdown=request.include_markdown,
    )

