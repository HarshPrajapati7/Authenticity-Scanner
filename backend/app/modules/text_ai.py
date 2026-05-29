from __future__ import annotations

import re
from typing import Any

import requests

from app.core.config import settings
from app.schemas.responses import ModuleFinding


AI_LABEL_HINTS = ("ai", "generated", "synthetic", "fake", "chatgpt", "gpt", "machine", "label_1")
HUMAN_LABEL_HINTS = ("human", "real", "original", "natural", "label_0")
AI_PHRASES = (
    "it is important to note",
    "in conclusion",
    "moreover",
    "furthermore",
    "additionally",
    "as an ai",
    "delve",
    "underscore",
    "plays a crucial role",
)


def analyze_ai_text(text: str, source: str = "text") -> ModuleFinding:
    normalized = _normalize_text(text)
    if not normalized:
        return ModuleFinding(
            id="text_ai",
            title="AI Text Detection",
            score=20.0,
            status="pass",
            summary="No readable text was available for AI-writing analysis.",
            evidence=["Readable text extraction returned an empty result."],
        )

    model_scores = _model_scores(normalized)
    model_score = _combine_model_scores(model_scores)
    heuristic_score, heuristic_evidence = _heuristic_score(normalized)
    if model_score is not None:
        # The transformer detector is the primary signal; the heuristic only
        # nudges it upward slightly so a confident model verdict is preserved.
        score = max(model_score, heuristic_score * 0.45)
    else:
        score = heuristic_score

    word_count = len(normalized.split())
    model_confident = model_score is not None and (model_score >= 80.0 or model_score <= 20.0)

    evidence = []
    if model_score is not None:
        evidence.append(
            f"Transformer text detector evaluated {len(model_scores)} chunk(s); strongest chunk {max(model_scores):.1f}/100."
        )
        evidence.extend(heuristic_evidence[:3])
    else:
        evidence.append("Transformer text detector is not configured; used local writing-pattern checks.")
        evidence.extend(heuristic_evidence)

    if word_count < settings.MIN_TEXT_WORDS:
        if model_confident:
            # A confident transformer verdict on short text is still meaningful;
            # only soften it slightly rather than collapsing it to "review".
            evidence.append("Text is short, but the detector gave a confident verdict.")
            if score >= 50.0:
                score = max(60.0, score * 0.92)
        else:
            evidence.append("Text is short, so this signal should be treated as lower confidence.")
            score = min(score, 45.0)

    return ModuleFinding(
        id="text_ai",
        title="AI Text Detection",
        score=round(max(0.0, min(100.0, score)), 2),
        status=_status(score),
        summary=_summary(score, source),
        evidence=evidence[:6],
    )


def _model_scores(text: str) -> list[float]:
    chunks = _text_chunks(text, max_chunks=settings.TEXT_MODEL_CHUNKS)
    scores: list[float] = []

    if settings.USE_LOCAL_MODEL:
        from app.main import ml_models

        classifier = ml_models.get("text")
        if classifier:
            for chunk in chunks:
                result = classifier(chunk)
                extracted = _extract_text_detector_score(result)
                if extracted is not None:
                    scores.append(extracted)
            if scores:
                return scores

    if not settings.HUGGINGFACE_API_KEY or not settings.HF_TEXT_API_URL:
        return []

    headers = {
        "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json",
        "x-wait-for-model": "true",
    }

    endpoints = [(settings.HF_TEXT_API_URL, settings.TEXT_PRIMARY_WEIGHT)]
    secondary = getattr(settings, "HF_TEXT_API_URL_2", "")
    if secondary:
        endpoints.append((secondary, max(0.0, 1.0 - settings.TEXT_PRIMARY_WEIGHT)))

    for chunk in chunks:
        payload = {"inputs": chunk, "parameters": {"truncation": True}}
        weighted_sum = 0.0
        weight_total = 0.0
        for url, weight in endpoints:
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=settings.HF_API_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                extracted = _extract_text_detector_score(response.json())
                if extracted is not None:
                    weighted_sum += extracted * weight
                    weight_total += weight
            except Exception as exc:
                print(f"HF text detector error ({url.rsplit('/', 1)[-1]}): {exc}")
                continue
        if weight_total > 0:
            scores.append(weighted_sum / weight_total)

    return scores


def _combine_model_scores(scores: list[float]) -> float | None:
    if not scores:
        return None
    strongest = max(scores)
    average = sum(scores) / len(scores)
    return max(average, strongest * 0.88)


def _text_chunks(text: str, max_chunks: int) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not sentences:
        return [text[: settings.MAX_TEXT_CHARS]]

    chunks: list[str] = []
    current = ""
    # RoBERTa detectors cap at ~512 tokens (~1400 chars). Keep chunks under that
    # so each is classified in full instead of being truncated and losing signal.
    target_size = min(1400, max(900, settings.MAX_TEXT_CHARS // max(max_chunks, 1)))
    for sentence in sentences:
        next_value = f"{current} {sentence}".strip()
        if current and len(next_value) > target_size:
            chunks.append(current[: settings.MAX_TEXT_CHARS])
            current = sentence
            if len(chunks) >= max_chunks:
                break
        else:
            current = next_value

    if current and len(chunks) < max_chunks:
        chunks.append(current[: settings.MAX_TEXT_CHARS])

    return chunks or [text[: settings.MAX_TEXT_CHARS]]


def _extract_text_detector_score(result: Any) -> float | None:
    candidates = _flatten_classifier_result(result)
    if not candidates:
        return None

    best_ai = None
    best_human = None
    for item in candidates:
        label = str(item.get("label", "")).strip().lower()
        try:
            score = float(item.get("score", 0.0)) * 100.0
        except (TypeError, ValueError):
            continue

        if any(hint in label for hint in AI_LABEL_HINTS):
            best_ai = max(best_ai or 0.0, score)
        elif any(hint in label for hint in HUMAN_LABEL_HINTS):
            best_human = max(best_human or 0.0, score)

    if best_ai is not None:
        return best_ai
    if best_human is not None:
        return 100.0 - best_human
    return None


def _flatten_classifier_result(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        return [result]
    if not isinstance(result, list):
        return []

    flattened: list[dict[str, Any]] = []
    for item in result:
        if isinstance(item, dict):
            flattened.append(item)
        elif isinstance(item, list):
            flattened.extend(entry for entry in item if isinstance(entry, dict))
    return flattened


def _heuristic_score(text: str) -> tuple[float, list[str]]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())
    sentences = [
        part.strip()
        for part in re.split(r"[.!?]+", text)
        if len(part.strip().split()) >= 3
    ]
    if not words:
        return 15.0, ["No word-level signal was available."]

    word_count = len(words)
    unique_ratio = len(set(words)) / max(word_count, 1)
    sentence_lengths = [len(re.findall(r"[A-Za-z][A-Za-z'-]*", sentence)) for sentence in sentences]
    avg_sentence = sum(sentence_lengths) / max(len(sentence_lengths), 1)
    if len(sentence_lengths) > 1:
        mean_len = avg_sentence or 1.0
        variance = sum((length - mean_len) ** 2 for length in sentence_lengths) / len(sentence_lengths)
        burstiness = (variance**0.5) / mean_len
    else:
        burstiness = 0.5

    repeated_stems = _repetition_ratio(words)
    phrase_hits = sum(1 for phrase in AI_PHRASES if phrase in text.lower())

    uniformity_score = max(0.0, (0.55 - burstiness) / 0.55) * 30.0
    repetition_score = min(25.0, repeated_stems * 90.0)
    vocabulary_score = max(0.0, (0.48 - unique_ratio) / 0.48) * 20.0
    phrase_score = min(18.0, phrase_hits * 6.0)
    length_confidence = min(1.0, word_count / max(settings.MIN_TEXT_WORDS, 1))

    score = 18.0 + (uniformity_score + repetition_score + vocabulary_score + phrase_score) * (
        0.65 + 0.35 * length_confidence
    )

    evidence = [
        f"Readable word count: {word_count}.",
        f"Sentence rhythm consistency score: {max(0.0, 100.0 - burstiness * 100.0):.1f}/100.",
        f"Vocabulary variety score: {unique_ratio * 100.0:.1f}/100.",
    ]
    if repeated_stems > 0.18:
        evidence.append("Repeated wording patterns were stronger than expected.")
    if phrase_hits:
        evidence.append("Common AI-style transition phrases were present.")
    if avg_sentence > 32:
        evidence.append("Average sentence length is unusually high.")

    return score, evidence


def _repetition_ratio(words: list[str]) -> float:
    if not words:
        return 0.0

    counts: dict[str, int] = {}
    for word in words:
        if len(word) < 5:
            continue
        stem = word[:7]
        counts[stem] = counts.get(stem, 0) + 1

    repeated = sum(count - 1 for count in counts.values() if count > 1)
    return repeated / max(len(words), 1)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _status(score: float):
    if score >= 70:
        return "risk"
    if score >= 35:
        return "review"
    return "pass"


def _summary(score: float, source: str) -> str:
    label = "document text" if source == "pdf" else "text"
    if score >= 70:
        return f"The {label} strongly resembles AI-generated writing."
    if score >= 35:
        return f"The {label} has mixed AI-writing signals."
    return f"The {label} looks more consistent with human writing."
