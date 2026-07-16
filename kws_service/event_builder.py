from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .config import KwsSettings
from .schemas import KwsDetection, KwsEvent


KST = timezone.utc


def build_kws_event(
    detection: KwsDetection,
    settings: KwsSettings,
    location: str | None = None,
    equipment: str | None = None,
    line_id: str | None = None,
) -> KwsEvent:
    if not detection.detected or not detection.keyword:
        raise ValueError("Cannot build a KWS event without a positive detection.")

    selected_equipment = equipment or settings.default_equipment
    selected_location = location or settings.default_location
    timestamp = datetime.now(KST).astimezone().isoformat(timespec="milliseconds")
    event_id = f"kws_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    keyword = detection.keyword
    description = f"작업자가 긴급 정지 음성을 발화함: {keyword}"
    return KwsEvent(
        event_id=event_id,
        risk_type=detection.risk_type or "비상정지",
        object="컨베이어",
        equipment=selected_equipment,
        location=selected_location,
        description=description,
        kws_keywords=[keyword],
        language=detection.language,
        confidence=detection.confidence,
        timestamp=timestamp,
        extra={
            "line_id": line_id,
            "detector": detection.detector,
            "transcript_hint": detection.transcript_hint,
        },
    )

