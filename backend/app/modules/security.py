import cv2
import numpy as np

from app.schemas.responses import ModuleFinding


def analyze_security_features(image_matrix: np.ndarray) -> ModuleFinding:
    evidence: list[str] = []
    score = 25.0

    detector = cv2.QRCodeDetector()
    decoded, points, _ = detector.detectAndDecode(image_matrix)
    if points is not None:
        evidence.append("Machine-readable QR-like security marker detected.")
        score -= 10.0
        if decoded:
            evidence.append("QR marker decoded successfully.")
    else:
        evidence.append("No QR-like machine-readable marker detected.")

    gray = cv2.cvtColor(image_matrix, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 70, 170)
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.4,
        minDist=80,
        param1=90,
        param2=30,
        minRadius=18,
        maxRadius=160,
    )

    if circles is not None:
        evidence.append("Circular seal or stamp-like structure detected.")
        score -= 5.0
    else:
        evidence.append("No obvious seal or stamp-like structure detected.")

    edge_density = float(np.count_nonzero(edges) / edges.size)
    if edge_density < 0.015:
        score += 15.0
        evidence.append("Document has unusually low edge detail for many security-marked forms.")
    else:
        evidence.append("Edge detail is present across the document.")

    score = max(0.0, min(score, 100.0))
    return ModuleFinding(
        id="security",
        title="Security Feature Scan",
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
        return "Expected security indicators are missing or visually weak."
    if score >= 35:
        return "Security feature signals are limited and should be checked manually."
    return "Security feature signals do not raise major concerns."
