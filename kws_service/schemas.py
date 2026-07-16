from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class KwsDetection(BaseModel):
    detected: bool
    keyword: str | None = None
    language: str | None = None
    confidence: float = 0.0
    risk_type: str | None = None
    transcript_hint: str | None = None
    detector: str = "simulation"


class KwsEvent(BaseModel):
    event_id: str
    source: Literal["kws"] = "kws"
    risk_type: str
    object: str = "컨베이어"
    equipment: str = "컨베이어"
    location: str = "미지정 구역"
    description: str
    kws_keywords: list[str] = Field(default_factory=list)
    language: str | None = None
    confidence: float
    timestamp: str
    action_required: Literal["emergency_stop"] = "emergency_stop"
    extra: dict[str, Any] = Field(default_factory=dict)


class SimulateKwsRequest(BaseModel):
    text: str
    location: str | None = None
    equipment: str | None = None
    line_id: str | None = None
    force_stop: bool = True
    call_rag: bool = False


class StopCommandResult(BaseModel):
    accepted: bool
    mode: str
    command_id: str
    reason: str
    timestamp: str
    detail: dict[str, Any] = Field(default_factory=dict)


class SimulateKwsResponse(BaseModel):
    detection: KwsDetection
    event: KwsEvent | None = None
    stop_command: StopCommandResult | None = None
    rag_report: dict[str, Any] | None = None


class StopTestRequest(BaseModel):
    reason: str = "manual_stop_test"
    location: str | None = None
    equipment: str | None = None

