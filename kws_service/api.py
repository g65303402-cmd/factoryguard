from __future__ import annotations

from functools import lru_cache
from typing import Any

import requests
from fastapi import APIRouter, FastAPI, HTTPException

from .actuator import get_actuator
from .config import KwsSettings, get_settings
from .detector import OpenWakeWordDetector, SimulationKeywordDetector
from .event_builder import build_kws_event
from .microphone import audio_stats, list_input_devices, record_microphone
from .schemas import (
    KwsDetection,
    MicCaptureCheckRequest,
    MicCaptureCheckResponse,
    MicListenRequest,
    MicListenResponse,
    MicrophoneDevice,
    SimulateKwsRequest,
    SimulateKwsResponse,
    StopCommandResult,
    StopTestRequest,
)


@lru_cache(maxsize=1)
def settings() -> KwsSettings:
    return get_settings()


@lru_cache(maxsize=1)
def detector() -> SimulationKeywordDetector:
    return SimulationKeywordDetector(settings())


@lru_cache(maxsize=1)
def microphone_detector() -> OpenWakeWordDetector:
    return OpenWakeWordDetector(settings())


router = APIRouter(prefix="/kws", tags=["kws"])


@router.get("/health")
def health() -> dict[str, Any]:
    cfg = settings()
    return {
        "status": "ok",
        "detector": "openwakeword" if cfg.model_paths else "not_configured",
        "text_simulation": "available_but_deprecated",
        "threshold": cfg.threshold,
        "cooldown_seconds": cfg.cooldown_seconds,
        "actuator_mode": cfg.actuator_mode,
        "sample_rate": cfg.microphone_sample_rate,
        "block_ms": cfg.microphone_block_ms,
        "model_paths": list(cfg.model_paths),
        "keywords": [
            {"keyword": item.keyword, "language": item.language, "aliases": list(item.aliases)}
            for item in cfg.keywords
        ],
    }


@router.post("/simulate", response_model=SimulateKwsResponse)
def simulate(request: SimulateKwsRequest) -> SimulateKwsResponse:
    """Deprecated text-only helper kept for API smoke tests.

    The real KWS path is `/kws/mic/listen-once`, which records microphone audio
    and runs the configured openWakeWord model.
    """

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


@router.get("/mic/devices", response_model=list[MicrophoneDevice])
def microphone_devices() -> list[MicrophoneDevice]:
    try:
        return [MicrophoneDevice(**device) for device in list_input_devices()]
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/mic/check-capture", response_model=MicCaptureCheckResponse)
def check_capture(request: MicCaptureCheckRequest) -> MicCaptureCheckResponse:
    cfg = settings()
    try:
        audio = record_microphone(cfg, request.duration_seconds, request.device)
        stats = audio_stats(audio)
        return MicCaptureCheckResponse(
            ok=True,
            sample_rate=cfg.microphone_sample_rate,
            duration_seconds=request.duration_seconds,
            device=request.device or cfg.microphone_device,
            captured_frames=int(stats["captured_frames"]),
            rms=float(stats["rms"]),
            peak=float(stats["peak"]),
        )
    except RuntimeError as exc:
        return MicCaptureCheckResponse(
            ok=False,
            sample_rate=cfg.microphone_sample_rate,
            duration_seconds=request.duration_seconds,
            device=request.device or cfg.microphone_device,
            detail={"error": str(exc)},
        )


@router.post("/mic/listen-once", response_model=MicListenResponse)
def listen_once(request: MicListenRequest) -> MicListenResponse:
    cfg = settings()
    if not cfg.model_paths:
        detection = KwsDetection(
            detected=False,
            detector="openwakeword",
            detail={"error": "KWS_MODEL_PATHS is empty.", "hint": "Set KWS_MODEL_PATHS to openWakeWord model files."},
        )
        return MicListenResponse(
            sample_rate=cfg.microphone_sample_rate,
            duration_seconds=request.duration_seconds,
            device=request.device or cfg.microphone_device,
            detection=detection,
        )

    try:
        audio = record_microphone(cfg, request.duration_seconds, request.device)
        detection = microphone_detector().detect_audio(audio)
    except RuntimeError as exc:
        detection = KwsDetection(
            detected=False,
            detector="openwakeword",
            detail={"error": str(exc), "hint": "Install sounddevice/openWakeWord and set KWS_MODEL_PATHS."},
        )

    event = None
    stop_result = None
    rag_report = None
    if detection.detected:
        event = build_kws_event(
            detection,
            cfg,
            location=request.location,
            equipment=request.equipment,
            line_id=request.line_id,
        )
        if request.force_stop:
            stop_result = get_actuator(cfg.actuator_mode).stop(event, reason="kws_detected")
        if request.call_rag:
            rag_report = call_rag_report(cfg.rag_report_url, event.model_dump())

    return MicListenResponse(
        sample_rate=cfg.microphone_sample_rate,
        duration_seconds=request.duration_seconds,
        device=request.device or cfg.microphone_device,
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
