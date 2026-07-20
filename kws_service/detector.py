from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

import numpy as np

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
    """Adapter for real openWakeWord microphone inference.

    Configure model files with `KWS_MODEL_PATHS`, separated by semicolons.
    """

    def __init__(self, settings: KwsSettings) -> None:
        self.settings = settings
        self.name = "openwakeword"
        if not settings.model_paths:
            raise RuntimeError("KWS_MODEL_PATHS is empty. Provide one or more openWakeWord model files.")
        missing = [path for path in settings.model_paths if not Path(path).exists()]
        if missing:
            raise RuntimeError(f"Missing KWS model file(s): {missing}")
        try:
            from openwakeword.model import Model
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "openWakeWord is not installed. Install it or keep using simulation mode."
            ) from exc
        self.model = Model(wakeword_models=list(settings.model_paths))
        self._last_fire_at = 0.0

    def detect_audio(self, audio: np.ndarray) -> KwsDetection:
        now = time.monotonic()
        if now - self._last_fire_at < self.settings.cooldown_seconds:
            return KwsDetection(detected=False, detector=self.name, detail={"reason": "cooldown"})

        pcm = ensure_int16_mono(audio)
        frame_size = max(1, int(self.settings.microphone_sample_rate * self.settings.microphone_block_ms / 1000))
        best_label = None
        best_score = 0.0
        for start in range(0, len(pcm) - frame_size + 1, frame_size):
            frame = pcm[start : start + frame_size]
            prediction = self.model.predict(frame)
            for label, score in prediction.items():
                if float(score) > best_score:
                    best_label = label
                    best_score = float(score)

        if best_label and best_score >= self.settings.threshold:
            self._last_fire_at = now
            return KwsDetection(
                detected=True,
                keyword=best_label,
                confidence=best_score,
                risk_type="비상정지",
                detector=self.name,
                detail={"model_paths": list(self.settings.model_paths)},
            )
        return KwsDetection(
            detected=False,
            keyword=best_label,
            confidence=best_score,
            detector=self.name,
            detail={"model_paths": list(self.settings.model_paths)},
        )


def ensure_int16_mono(audio: np.ndarray) -> np.ndarray:
    array = np.asarray(audio)
    if array.ndim > 1:
        array = array[:, 0]
    if array.dtype == np.int16:
        return np.ascontiguousarray(array)
    array = np.clip(array.astype("float32"), -1.0, 1.0)
    return np.ascontiguousarray((array * 32767).astype(np.int16))
