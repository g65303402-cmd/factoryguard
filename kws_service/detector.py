from __future__ import annotations

from dataclasses import dataclass
import re
import time

from .config import KwsSettings, KeywordSpec
from .schemas import KwsDetection


def normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    return re.sub(r"\s+", " ", lowered)


@dataclass
class SimulationKeywordDetector:
    settings: KwsSettings
    name: str = "simulation"
    _last_fire_at: float = 0.0

    def detect_text(self, text: str) -> KwsDetection:
        normalized = normalize_text(text)
        now = time.monotonic()
        if now - self._last_fire_at < self.settings.cooldown_seconds:
            return KwsDetection(
                detected=False,
                confidence=0.0,
                transcript_hint=text,
                detector=self.name,
            )

        for spec in self.settings.keywords:
            confidence = self._match_confidence(normalized, spec)
            if confidence >= self.settings.threshold:
                self._last_fire_at = now
                return KwsDetection(
                    detected=True,
                    keyword=spec.keyword,
                    language=spec.language,
                    confidence=confidence,
                    risk_type=spec.risk_type,
                    transcript_hint=text,
                    detector=self.name,
                )
        return KwsDetection(detected=False, transcript_hint=text, detector=self.name)

    def _match_confidence(self, normalized: str, spec: KeywordSpec) -> float:
        candidates = (spec.keyword, *spec.aliases)
        normalized_candidates = [normalize_text(candidate) for candidate in candidates]
        for candidate in normalized_candidates:
            if candidate and candidate in normalized:
                return 0.95
        # Very small typo tolerance for Korean spacing or English shout strings in demos.
        compact = normalized.replace(" ", "")
        for candidate in normalized_candidates:
            if candidate.replace(" ", "") in compact:
                return 0.88
        return 0.0


class OpenWakeWordDetector:
    """Placeholder adapter for the real streaming KWS model.

    The project can keep the API stable while the model owner swaps this adapter
    with openWakeWord microphone inference.
    """

    def __init__(self, settings: KwsSettings) -> None:
        self.settings = settings
        try:
            import openwakeword  # noqa: F401
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "openWakeWord is not installed. Use simulation mode or install/configure the real KWS model."
            ) from exc

