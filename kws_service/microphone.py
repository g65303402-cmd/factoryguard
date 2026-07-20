from __future__ import annotations

from typing import Any
import queue
import time

import numpy as np

from .config import KwsSettings


def require_sounddevice():
    try:
        import sounddevice as sd
    except ModuleNotFoundError as exc:
        raise RuntimeError("sounddevice is not installed. Install requirements-kws or add sounddevice.") from exc
    return sd


def list_input_devices() -> list[dict[str, Any]]:
    sd = require_sounddevice()
    devices = sd.query_devices()
    result = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) > 0:
            result.append(
                {
                    "index": index,
                    "name": str(device.get("name", "")),
                    "max_input_channels": int(device.get("max_input_channels", 0)),
                    "default_samplerate": float(device.get("default_samplerate", 0.0)),
                }
            )
    return result


def record_microphone(
    settings: KwsSettings,
    duration_seconds: float,
    device: int | str | None = None,
) -> np.ndarray:
    sd = require_sounddevice()
    selected_device = device if device is not None else settings.microphone_device
    capture_rate = resolve_capture_sample_rate(sd, selected_device, settings.microphone_sample_rate)
    target_rate = settings.microphone_sample_rate
    block_size = max(1, int(capture_rate * settings.microphone_block_ms / 1000))
    target_frames = int(duration_seconds * capture_rate)
    chunks: queue.Queue[np.ndarray] = queue.Queue()

    def callback(indata, frames, time_info, status):  # noqa: ANN001
        if status:
            # Keep recording; status is surfaced through returned audio length in tests.
            pass
        chunks.put(np.asarray(indata[:, 0], dtype="float32").copy())

    deadline = time.monotonic() + duration_seconds + 2.0
    collected = 0
    captured: list[np.ndarray] = []
    with sd.InputStream(
        samplerate=capture_rate,
        channels=1,
        dtype="float32",
        device=selected_device,
        blocksize=block_size,
        callback=callback,
    ):
        while collected < target_frames:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                chunk = chunks.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            captured.append(chunk)
            collected += len(chunk)

    if collected == 0:
        raise RuntimeError("No microphone audio was captured before timeout.")
    audio = np.concatenate(captured)
    audio = audio[:target_frames]
    if capture_rate != target_rate:
        audio = resample_audio(audio, capture_rate, target_rate)
    return audio.astype("float32", copy=False)


def audio_stats(audio: np.ndarray) -> dict[str, float | int]:
    if audio.size == 0:
        return {"captured_frames": 0, "rms": 0.0, "peak": 0.0}
    return {
        "captured_frames": int(audio.size),
        "rms": float(np.sqrt(np.mean(np.square(audio.astype("float32"))))),
        "peak": float(np.max(np.abs(audio))),
    }


def resolve_capture_sample_rate(sd, device: int | str | None, fallback: int) -> int:  # noqa: ANN001
    if device is None:
        device_info = sd.query_devices(kind="input")
    else:
        device_info = sd.query_devices(device, kind="input")
    default_rate = int(float(device_info.get("default_samplerate") or fallback))
    return default_rate or fallback


def resample_audio(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return audio
    try:
        from scipy.signal import resample_poly
    except ModuleNotFoundError as exc:
        raise RuntimeError("scipy is required to resample microphone audio to 16 kHz.") from exc
    from math import gcd

    divisor = gcd(source_rate, target_rate)
    up = target_rate // divisor
    down = source_rate // divisor
    return resample_poly(audio, up, down).astype("float32")
