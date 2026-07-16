from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests
from fastapi import APIRouter, FastAPI, HTTPException

from .actuator import get_actuator
from .config import KwsSettings, get_settings
from .detector import SimulationKeywordDetector
from .event_builder import build_kws_event
from .schemas import SimulateKwsRequest, SimulateKwsResponse, StopTestRequest, StopCommandResult


@lru_cache(maxsize=1)
def settings() -> KwsSettings:
    return get_settings()


@lru_cache(maxsize=1)
def detector() -> SimulationKeywordDetector:
    return SimulationKeywordDetector(settings())


router = APIRouter(prefix="/kws", tags=["kws"])


@router.get("/health")
def health() -> dict[str, Any]:
    cfg = settings()
    return {
        "status": "ok",
        "detector": "simulation",
        "threshold": cfg.threshold,
        "cooldown_seconds": cfg.cooldown_seconds,
        "actuator_mode": cfg.actuator_mode,
        "keywords": [
            {"keyword": item.keyword, "language": item.language, "aliases": list(item.aliases)}
            for item in cfg.keywords
        ],
    }


@router.post("/simulate", response_model=SimulateKwsResponse)
def simulate(request: SimulateKwsRequest) -> SimulateKwsResponse:
    cfg = settings()
    detection = detector().detect_text(request.text)
    if not detection.detected:
        return SimulateKwsResponse(detection=detection)

    event = build_kws_event(
        detection,
        cfg,
        location=request.location,
        equipment=request.equipment,
        line_id=request.line_id,
    )
    stop_result = None
    if request.force_stop:
        stop_result = get_actuator(cfg.actuator_mode).stop(event, reason="kws_detected")

    rag_report = None
    if request.call_rag:
        rag_report = call_rag_report(cfg.rag_report_url, event.model_dump())

    return SimulateKwsResponse(
        detection=detection,
        event=event,
        stop_command=stop_result,
        rag_report=rag_report,
    )


@router.post("/stop-test", response_model=StopCommandResult)
def stop_test(request: StopTestRequest) -> StopCommandResult:
    cfg = settings()
    try:
        return get_actuator(cfg.actuator_mode).stop(None, reason=request.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def call_rag_report(url: str, event: dict[str, Any]) -> dict[str, Any]:
    payload = {"event": event, "top_k": 5, "include_markdown": True}
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


app = FastAPI(
    title="Factory Guard KWS API",
    description="Keyword spotting event adapter for conveyor emergency-stop demos.",
    version="0.1.0",
)
app.include_router(router)

