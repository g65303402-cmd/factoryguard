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
    detail: dict[str, Any] = Field(default_factory=dict)


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
    """Deprecated text-only test helper. Use microphone endpoints for real KWS flow."""

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


class MicrophoneDevice(BaseModel):
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float


class MicListenRequest(BaseModel):
    duration_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    location: str | None = None
    equipment: str | None = None
    line_id: str | None = None
    device: int | str | None = None
    force_stop: bool = True
    call_rag: bool = False


class MicListenResponse(BaseModel):
    sample_rate: int
    duration_seconds: float
    device: int | str | None = None
    detection: KwsDetection
    event: KwsEvent | None = None
    stop_command: StopCommandResult | None = None
    rag_report: dict[str, Any] | None = None


class MicCaptureCheckRequest(BaseModel):
    duration_seconds: float = Field(default=1.0, ge=0.2, le=10.0)
    device: int | str | None = None


class MicCaptureCheckResponse(BaseModel):
    ok: bool
    sample_rate: int
    duration_seconds: float
    device: int | str | None = None
    captured_frames: int = 0
    rms: float = 0.0
    peak: float = 0.0
    detail: dict[str, Any] = Field(default_factory=dict)
