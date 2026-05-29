from __future__ import annotations

from io import BytesIO
from typing import Any

import cv2
import numpy as np
import requests
from PIL import Image

from app.core.config import settings

AI_LABEL_HINTS = (
    "fake",
    "ai",
    "aigc",
    "generated",
    "synthetic",
    "deepfake",
    "diffusion",
    "label_1",
)
AUTHENTIC_LABEL_HINTS = (
    "real",
    "human",
    "authentic",
    "original",
    "natural",
    "photograph",
    "label_0",
)
GENERATOR_BYTE_HINTS = (
    "openai",
    "chatgpt",
    "dall-e",
    "dalle",
    "gpt-image",
    "midjourney",
    "stable diffusion",
    "stablediffusion",
    "comfyui",
    "automatic1111",
    "firefly",
    "imagen",
    "flux",
    "leonardo",
    "c2pa",
)


def analyze_vlm(image_matrix) -> float:
    model_score = _model_score(image_matrix)
    if model_score is not None:
        return model_score

    heuristic_score, _, _ = _heuristic_image_score(image_matrix)
    return max(50.0, heuristic_score)


def analyze_image_generation_signals(
    image_matrix,
    data: bytes | None = None,
    content_type: str = "",
    filename: str = "",
) -> tuple[float, list[str]]:
    model_score = _model_score(image_matrix)
    heuristic_score, heuristic_evidence, strong_trace = _heuristic_image_score(
        image_matrix,
        data=data,
        content_type=content_type,
        filename=filename,
    )

    evidence: list[str] = []
    if model_score is None:
        score = max(50.0, heuristic_score)
        evidence.append(
            "Transformer image detector is unavailable or not configured; using review-weighted forensic fallback."
        )
    else:
        evidence.append(f"Transformer synthetic-image detector score: {model_score:.2f}/100.")
        if strong_trace:
            score = max(model_score, heuristic_score)
        elif model_score < 35.0:
            score = max(model_score, min(42.0, heuristic_score * 0.65))
        else:
            score = max(model_score, heuristic_score * 0.85)

    evidence.extend(heuristic_evidence)
    score = max(0.0, min(100.0, score))
    return score, evidence[:7]


def _model_score(image_matrix) -> float | None:
    if settings.USE_LOCAL_MODEL:
        from app.main import ml_models

        rgb_image = cv2.cvtColor(image_matrix, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)

        classifier = ml_models.get("vlm")
        if not classifier:
            return None

        try:
            results = classifier(pil_image)
        except Exception as exc:
            print(f"Local image detector error: {exc}")
            return None
        return _extract_score(results)

    if not settings.HUGGINGFACE_API_KEY:
        print("HF API Error: HUGGINGFACE_API_KEY is not set.")
        return None

    success, encoded_image = cv2.imencode(".jpg", image_matrix)
    if not success:
        return None

    headers = {
        "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
        "Content-Type": "image/jpeg",
        "x-wait-for-model": "true",
    }

    try:
        response = requests.post(
            settings.HF_API_URL,
            headers=headers,
            data=encoded_image.tobytes(),
            timeout=settings.HF_API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return _extract_score(response.json())
    except Exception as exc:
        print(f"HF API Error: {exc}")
        return None


def _extract_score(results: Any) -> float | None:
    candidates = _flatten_classifier_result(results)
    if not candidates:
        return None

    best_ai = None
    best_authentic = None
    for result in candidates:
        label = str(result.get("label", "")).strip().lower()
        try:
            score = float(result.get("score", 0.0)) * 100.0
        except (TypeError, ValueError):
            continue

        if any(hint in label for hint in AI_LABEL_HINTS):
            best_ai = max(best_ai or 0.0, score)
        elif any(hint in label for hint in AUTHENTIC_LABEL_HINTS):
            best_authentic = max(best_authentic or 0.0, score)

    if best_ai is not None:
        return max(0.0, min(100.0, best_ai))
    if best_authentic is not None:
        return max(0.0, min(100.0, 100.0 - best_authentic))
    return None


def _flatten_classifier_result(results: Any) -> list[dict[str, Any]]:
    if isinstance(results, dict):
        return [results]
    if not isinstance(results, list):
        return []

    flattened: list[dict[str, Any]] = []
    for item in results:
        if isinstance(item, dict):
            flattened.append(item)
        elif isinstance(item, list):
            flattened.extend(entry for entry in item if isinstance(entry, dict))
    return flattened


def _heuristic_image_score(
    image_matrix,
    data: bytes | None = None,
    content_type: str = "",
    filename: str = "",
) -> tuple[float, list[str], bool]:
    evidence: list[str] = []
    score = 18.0
    strong_trace = False

    trace_hits = [] if content_type == "application/pdf" else _generator_trace_hits(data, filename)
    if trace_hits:
        score = max(score, 92.0)
        strong_trace = True
        evidence.append(f"AI-generator container trace detected: {', '.join(trace_hits[:3])}.")

    camera_evidence = _camera_metadata_evidence(data)
    if camera_evidence:
        evidence.append(camera_evidence)
    elif content_type.startswith("image/") and content_type != "image/png":
        score = max(score, 32.0)
        evidence.append("No camera EXIF make/model metadata was found.")
    elif content_type == "image/png":
        score = max(score, 35.0)
        evidence.append("PNG container has no camera-origin EXIF signal.")

    gray = cv2.cvtColor(image_matrix, cv2.COLOR_BGR2GRAY)
    noise_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    edge_density = float(np.count_nonzero(cv2.Canny(gray, 70, 170)) / gray.size)
    height, width = gray.shape[:2]

    if noise_variance < 18.0:
        score = max(score, 48.0)
        evidence.append(f"Very low sensor-noise variance: {noise_variance:.2f}.")
    elif noise_variance < 45.0:
        score = max(score, 40.0)
        evidence.append(f"Low sensor-noise variance: {noise_variance:.2f}.")
    else:
        evidence.append(f"Sensor-noise variance: {noise_variance:.2f}.")

    if edge_density < 0.012:
        score = max(score, 42.0)
        evidence.append(f"Low natural edge density: {edge_density:.4f}.")

    if min(width, height) >= 768 and (
        width == height or width in {1024, 1536, 1792, 2048} or height in {1024, 1536, 1792, 2048}
    ):
        score = max(score, 38.0)
        evidence.append(f"Canvas dimensions ({width}x{height}) match common generated-image sizes.")

    if not evidence:
        evidence.append("Local image heuristics did not find strong AI-generator traces.")

    return max(0.0, min(100.0, score)), evidence, strong_trace


def _generator_trace_hits(data: bytes | None, filename: str = "") -> list[str]:
    if not data:
        return []

    head = data[:2_000_000]
    tail = data[-1_000_000:] if len(data) > 2_000_000 else b""
    haystack = (filename.encode("utf-8", errors="ignore") + b" " + head + b" " + tail).decode(
        "latin-1",
        errors="ignore",
    ).lower()
    return [hint for hint in GENERATOR_BYTE_HINTS if hint in haystack]


def _camera_metadata_evidence(data: bytes | None) -> str:
    if not data:
        return ""

    try:
        image = Image.open(BytesIO(data))
        exif = image.getexif()
        make = str(exif.get(271, "")).strip()
        model = str(exif.get(272, "")).strip()
        lens = str(exif.get(42036, "")).strip()
    except Exception:
        return ""

    parts = [part for part in (make, model, lens) if part]
    if not parts:
        return ""
    return f"Camera-origin EXIF signal present: {' / '.join(parts[:3])}."
