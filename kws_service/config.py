from __future__ import annotations

from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class KeywordSpec:
    keyword: str
    language: str
    aliases: tuple[str, ...] = ()
    risk_type: str = "비상정지"


DEFAULT_KEYWORDS: tuple[KeywordSpec, ...] = (
    KeywordSpec("멈춰", "ko", ("멈처", "멈춰줘", "멈추세요")),
    KeywordSpec("정지", "ko", ("중지", "스톱", "스탑")),
    KeywordSpec("살려줘", "ko", ("도와줘", "위험해"), "비상정지"),
    KeywordSpec("stop", "en", ("emergency stop", "help")),
    KeywordSpec("dung lai", "vi", ("dừng lại", "cuu toi", "cứu tôi")),
    KeywordSpec("ting", "zh", ("停", "救命")),
)


@dataclass(frozen=True)
class KwsSettings:
    threshold: float = float(os.getenv("KWS_THRESHOLD", "0.75"))
    cooldown_seconds: float = float(os.getenv("KWS_COOLDOWN_SECONDS", "2.0"))
    default_equipment: str = os.getenv("KWS_DEFAULT_EQUIPMENT", "컨베이어")
    default_location: str = os.getenv("KWS_DEFAULT_LOCATION", "미지정 구역")
    backend_event_url: str | None = os.getenv("BACKEND_EVENT_URL") or None
    rag_report_url: str = os.getenv("RAG_REPORT_URL", "http://localhost:8010/rag/report")
    actuator_mode: str = os.getenv("ACTUATOR_MODE", "dry_run")
    microphone_sample_rate: int = int(os.getenv("KWS_SAMPLE_RATE", "16000"))
    microphone_block_ms: int = int(os.getenv("KWS_BLOCK_MS", "80"))
    microphone_device: str | None = os.getenv("KWS_MIC_DEVICE") or None
    model_paths: tuple[str, ...] = tuple(
        path.strip() for path in os.getenv("KWS_MODEL_PATHS", "").split(";") if path.strip()
    )
    keywords: tuple[KeywordSpec, ...] = field(default_factory=lambda: DEFAULT_KEYWORDS)


def get_settings() -> KwsSettings:
    return KwsSettings()
