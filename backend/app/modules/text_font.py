import cv2
import numpy as np

from app.schemas.responses import ModuleFinding


def analyze_text_and_fonts(image_matrix: np.ndarray) -> ModuleFinding:
    gray = cv2.cvtColor(image_matrix, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        12,
    )
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    image_area = image_matrix.shape[0] * image_matrix.shape[1]

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if 12 <= h <= image_matrix.shape[0] * 0.15 and 8 <= w and area < image_area * 0.08:
            boxes.append((x, y, w, h))

    evidence = [f"Detected {len(boxes)} text-like connected components."]
    if len(boxes) < 8:
        return ModuleFinding(
            id="text_font",
            title="Text & Font Analysis",
            score=25.0,
            status="pass",
            summary="Limited text structure was available for layout analysis.",
            evidence=evidence,
        )

    heights = np.array([box[3] for box in boxes], dtype=np.float32)
    left_edges = np.array([box[0] for box in boxes], dtype=np.float32)

    height_variance = float(np.std(heights) / (np.mean(heights) + 1e-6))
    alignment_variance = float(np.std(left_edges) / max(image_matrix.shape[1], 1))
    score = min(100.0, (height_variance * 60.0) + (alignment_variance * 140.0))

    if height_variance > 0.75:
        evidence.append("Text component heights vary more than expected for a clean document.")
    else:
        evidence.append("Text component heights are reasonably consistent.")

    if alignment_variance > 0.22:
        evidence.append("Text alignment appears irregular across detected lines.")
    else:
        evidence.append("Detected text alignment is mostly stable.")

    return ModuleFinding(
        id="text_font",
        title="Text & Font Analysis",
        score=round(score, 2),
        status=_status(score),
        summary=_summary(score),
        evidence=evidence,
    )


def _status(score: float):
    if score >= 70:
        return "risk"
    if score >= 35:
        return "review"
    return "pass"


def _summary(score: float) -> str:
    if score >= 70:
        return "Text geometry shows strong signs of layout inconsistency."
    if score >= 35:
        return "Text geometry has mild inconsistencies worth reviewing."
    return "Text and alignment signals look consistent."
