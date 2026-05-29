from __future__ import annotations

import math
import wave
from io import BytesIO

import numpy as np

from app.schemas.responses import ModuleFinding


def analyze_audio_media(data: bytes, content_type: str, filename: str) -> ModuleFinding:
    evidence = [
        f"Audio container accepted: {content_type}.",
        f"File size: {len(data) / 1024:.1f} KB.",
    ]
    score = 35.0

    if content_type in {"audio/wav", "audio/x-wav"} or filename.lower().endswith(".wav"):
        wav_score, wav_evidence = _analyze_wav(data)
        score = wav_score
        evidence.extend(wav_evidence)
    else:
        entropy = _byte_entropy(data[: min(len(data), 512_000)])
        evidence.append(f"Container byte entropy: {entropy:.2f}/8.00.")
        if entropy > 7.85:
            score += 18.0
            evidence.append("Audio payload is highly compressed or opaque, limiting local forensic checks.")
        else:
            score -= 8.0

    evidence.append("Dedicated voice deepfake model is not configured; score is a media-integrity signal.")

    return ModuleFinding(
        id="audio_ai",
        title="Audio Authenticity Scan",
        score=round(max(0.0, min(100.0, score)), 2),
        status=_status(score),
        summary=_summary(score, "audio"),
        evidence=evidence[:6],
    )


def video_finding_from_scores(scores: list[float], sampled_frames: int) -> ModuleFinding:
    if not scores:
        score = 35.0
        evidence = ["Video loaded, but no analyzable frames were sampled."]
    else:
        score = sum(scores) / len(scores)
        evidence = [
            f"Sampled {sampled_frames} representative frame(s).",
            f"Average frame authenticity risk: {score:.1f}/100.",
        ]
        if max(scores) - min(scores) > 35:
            evidence.append("Frame-level risk varies sharply across the clip.")

    return ModuleFinding(
        id="video_ai",
        title="Video Authenticity Scan",
        score=round(max(0.0, min(100.0, score)), 2),
        status=_status(score),
        summary=_summary(score, "video"),
        evidence=evidence,
    )


def _analyze_wav(data: bytes) -> tuple[float, list[str]]:
    evidence: list[str] = []
    try:
        with wave.open(BytesIO(data), "rb") as audio:
            channels = audio.getnchannels()
            frame_rate = audio.getframerate()
            sample_width = audio.getsampwidth()
            frame_count = audio.getnframes()
            duration = frame_count / max(frame_rate, 1)
            raw = audio.readframes(min(frame_count, frame_rate * 20))
    except wave.Error:
        return 55.0, ["WAV header could not be parsed cleanly."]

    evidence.extend(
        [
            f"WAV duration: {duration:.1f}s.",
            f"Sample rate: {frame_rate} Hz, channels: {channels}.",
        ]
    )

    score = 24.0
    if duration < 1.0:
        score += 20.0
        evidence.append("Audio is too short for reliable speech authenticity analysis.")
    if frame_rate < 16000:
        score += 12.0
        evidence.append("Sample rate is lower than expected for clear voice analysis.")

    if raw:
        samples = np.frombuffer(raw, dtype=_dtype_for_width(sample_width))
        if samples.size:
            normalized = samples.astype(np.float32)
            peak = float(np.max(np.abs(normalized)))
            rms = float(np.sqrt(np.mean(normalized**2)))
            silence_ratio = float(np.mean(np.abs(normalized) < max(peak * 0.01, 1.0)))
            evidence.append(f"Peak-to-RMS structure: {(peak / max(rms, 1.0)):.2f}.")
            if silence_ratio > 0.82:
                score += 15.0
                evidence.append("Audio contains unusually large low-energy regions.")

    return score, evidence


def _byte_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = np.bincount(np.frombuffer(data, dtype=np.uint8), minlength=256)
    probabilities = counts[counts > 0] / len(data)
    return float(-sum(p * math.log2(p) for p in probabilities))


def _dtype_for_width(width: int):
    if width == 1:
        return np.uint8
    if width == 2:
        return np.int16
    if width == 4:
        return np.int32
    return np.int16


def _status(score: float):
    if score >= 70:
        return "risk"
    if score >= 35:
        return "review"
    return "pass"


def _summary(score: float, media_type: str) -> str:
    if score >= 70:
        return f"The {media_type} contains high-risk authenticity signals."
    if score >= 35:
        return f"The {media_type} has mixed authenticity signals."
    return f"The {media_type} does not show strong local authenticity risk."
