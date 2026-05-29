from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Tuple

import cv2
import numpy as np

from app.core.config import settings
from app.modules.deepfake import analyze_image_generation_signals, analyze_vlm
from app.modules.fusion import calculate_weighted_fraud_score, verdict_from_score
from app.modules.media import analyze_audio_media, video_finding_from_scores
from app.modules.metadata import analyze_metadata
from app.modules.security import analyze_security_features
from app.modules.spectral import detect_spectral_anomalies
from app.modules.text_ai import analyze_ai_text
from app.modules.text_font import analyze_text_and_fonts
from app.modules.visual import analyze_noise, calculate_ela, generate_suspicion_heatmap
from app.schemas.responses import ForensicReport, ModuleFinding


def build_forensic_report(
    job_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> ForensicReport:
    if content_type in {"text/plain", "text/markdown"}:
        return _build_text_report(job_id, filename, content_type, data)
    if content_type.startswith("audio/"):
        return _build_audio_report(job_id, filename, content_type, data)
    if content_type.startswith("video/"):
        return _build_video_report(job_id, filename, content_type, data)
    if content_type == "application/pdf":
        return _build_pdf_report(job_id, filename, content_type, data)

    metadata = analyze_metadata(data, content_type, filename)
    image_matrix = _document_to_image(data, content_type)
    visual, heatmap = _analyze_visual(image_matrix)
    ai_generated = _analyze_ai(image_matrix, data, content_type, filename)
    text_font = analyze_text_and_fonts(image_matrix)
    security = analyze_security_features(image_matrix)

    findings = [metadata, visual, ai_generated, text_font, security]

    overall_score = calculate_weighted_fraud_score(
        {finding.id: finding.score for finding in findings}
    )
    verdict = verdict_from_score(overall_score)

    return ForensicReport(
        job_id=job_id,
        filename=filename,
        content_type=content_type,
        overall_score=round(overall_score, 2),
        verdict=verdict,
        reasoning=_reasoning(verdict, findings),
        findings=findings,
        heatmap=heatmap,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_pdf_report(
    job_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> ForensicReport:
    metadata = analyze_metadata(data, content_type, filename)
    page_matrices = _pdf_pages_to_images(data, max_pages=settings.PDF_SAMPLE_PAGES)
    if not page_matrices:
        raise ValueError("PDF pages could not be rendered for visual analysis.")

    visual, heatmap = _analyze_visual_batch(page_matrices)
    ai_generated = _analyze_ai_batch(page_matrices, data, content_type, filename)
    text_font = analyze_text_and_fonts(page_matrices[0])
    security = analyze_security_features(page_matrices[0])

    findings = [metadata, visual, ai_generated, text_font, security]
    extracted_text = _extract_pdf_text(data)
    if extracted_text:
        findings.append(analyze_ai_text(extracted_text, source="pdf"))
    else:
        findings.append(
            ModuleFinding(
                id="text_ai",
                title="AI Text Detection",
                score=35.0,
                status="review",
                summary="No selectable PDF text was available for AI-writing analysis.",
                evidence=["The PDF may be scanned, image-only, or text extraction returned no content."],
            )
        )

    embedded_images = _analyze_pdf_embedded_images(data)
    if embedded_images:
        findings.append(embedded_images)

    overall_score = calculate_weighted_fraud_score(
        {finding.id: finding.score for finding in findings}
    )
    verdict = verdict_from_score(overall_score)

    return ForensicReport(
        job_id=job_id,
        filename=filename,
        content_type=content_type,
        overall_score=round(overall_score, 2),
        verdict=verdict,
        reasoning=_reasoning(verdict, findings),
        findings=findings,
        heatmap=heatmap,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_text_report(
    job_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> ForensicReport:
    text = data.decode("utf-8", errors="replace")
    text_ai = analyze_ai_text(text, source="text")
    findings = [text_ai]
    overall_score = calculate_weighted_fraud_score({text_ai.id: text_ai.score})
    verdict = verdict_from_score(overall_score)

    return ForensicReport(
        job_id=job_id,
        filename=filename,
        content_type=content_type,
        overall_score=round(overall_score, 2),
        verdict=verdict,
        reasoning=_reasoning(verdict, findings),
        findings=findings,
        heatmap=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_audio_report(
    job_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> ForensicReport:
    audio = analyze_audio_media(data, content_type, filename)
    findings = [audio]
    overall_score = calculate_weighted_fraud_score({audio.id: audio.score})
    verdict = verdict_from_score(overall_score)

    return ForensicReport(
        job_id=job_id,
        filename=filename,
        content_type=content_type,
        overall_score=round(overall_score, 2),
        verdict=verdict,
        reasoning=_reasoning(verdict, findings),
        findings=findings,
        heatmap=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_video_report(
    job_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> ForensicReport:
    frames = _sample_video_frames(data, filename)
    frame_scores: list[float] = []
    heatmap = None

    for frame in frames:
        visual_score, _, _ = _visual_signal_score(frame)
        synthetic_score = analyze_vlm(frame)
        frame_scores.append((visual_score * 0.55) + (synthetic_score * 0.45))
        if heatmap is None:
            heatmap = generate_suspicion_heatmap(frame)

    video = video_finding_from_scores(frame_scores, len(frames))
    findings = [video]
    overall_score = calculate_weighted_fraud_score({video.id: video.score})
    verdict = verdict_from_score(overall_score)

    return ForensicReport(
        job_id=job_id,
        filename=filename,
        content_type=content_type,
        overall_score=round(overall_score, 2),
        verdict=verdict,
        reasoning=_reasoning(verdict, findings),
        findings=findings,
        heatmap=heatmap,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _document_to_image(data: bytes, content_type: str) -> np.ndarray:
    if content_type == "application/pdf":
        return _pdf_first_page_to_image(data)

    file_bytes = np.frombuffer(data, np.uint8)
    image_matrix = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if image_matrix is None:
        raise ValueError("Uploaded image could not be decoded.")
    return image_matrix


def _pdf_first_page_to_image(data: bytes) -> np.ndarray:
    pages = _pdf_pages_to_images(data, max_pages=1)
    if not pages:
        raise ValueError("PDF has no renderable pages.")
    return pages[0]


def _pdf_pages_to_images(data: bytes, max_pages: int) -> list[np.ndarray]:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("PDF support requires PyMuPDF. Install backend requirements.") from exc

    matrices: list[np.ndarray] = []
    with fitz.open(stream=data, filetype="pdf") as document:
        if document.page_count == 0:
            raise ValueError("PDF has no pages.")
        for page_index in range(min(document.page_count, max(1, max_pages))):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height,
                pixmap.width,
                3,
            )
            matrices.append(cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    return matrices


def _analyze_visual(image_matrix: np.ndarray) -> Tuple[ModuleFinding, str]:
    score, evidence, summary = _visual_signal_score(image_matrix)
    finding = ModuleFinding(
        id="visual",
        title="Visual Forensics",
        score=round(score, 2),
        status=_status(score),
        summary=summary,
        evidence=evidence,
    )
    return finding, generate_suspicion_heatmap(image_matrix)


def _analyze_visual_batch(image_matrices: list[np.ndarray]) -> Tuple[ModuleFinding, str]:
    scores: list[float] = []
    evidence = [f"Rendered and sampled {len(image_matrices)} PDF page(s) for visual forensics."]
    summaries: list[str] = []

    for index, matrix in enumerate(image_matrices, start=1):
        score, page_evidence, summary = _visual_signal_score(matrix)
        scores.append(score)
        summaries.append(summary)
        evidence.append(f"Page {index}: visual risk {score:.1f}/100.")
        evidence.extend(page_evidence[:1])

    average_score = sum(scores) / len(scores)
    score = max(average_score, max(scores) * 0.85)
    if score >= 70:
        summary = "One or more rendered PDF pages show strong visual-generation or editing signals."
    elif score >= 35:
        summary = "Rendered PDF pages show mixed visual authenticity signals."
    else:
        summary = "Rendered PDF page visuals are within a normal range."

    finding = ModuleFinding(
        id="visual",
        title="Rendered PDF Page Analysis",
        score=round(score, 2),
        status=_status(score),
        summary=summary,
        evidence=evidence[:7],
    )
    return finding, generate_suspicion_heatmap(image_matrices[0])


def _visual_signal_score(image_matrix: np.ndarray) -> Tuple[float, list[str], str]:
    spectral_score = detect_spectral_anomalies(image_matrix) * 100.0
    ela_score = calculate_ela(image_matrix)
    noise_variance = analyze_noise(image_matrix)

    ela_risk = min(100.0, ela_score * 4.0)
    if noise_variance < 35:
        noise_risk = 70.0
    elif noise_variance > 900:
        noise_risk = 55.0
    else:
        noise_risk = 15.0

    score = min(100.0, (spectral_score * 0.36) + (ela_risk * 0.34) + (noise_risk * 0.30))
    evidence = [
        f"FFT high-frequency anomaly score: {spectral_score:.2f}/100.",
        f"Error level intensity: {ela_score:.2f}.",
        f"Laplacian noise variance: {noise_variance:.2f}.",
    ]
    if score >= 70:
        summary = "Compression, edge, and spectral artifacts are strongly suspicious."
    elif score >= 35:
        summary = "Visual artifacts show mild-to-moderate inconsistencies."
    else:
        summary = "Visual forensic signals are within a normal range."

    return score, evidence, summary


def _analyze_ai(
    image_matrix: np.ndarray,
    data: bytes | None = None,
    content_type: str = "",
    filename: str = "",
) -> ModuleFinding:
    vlm_score, evidence = analyze_image_generation_signals(image_matrix, data, content_type, filename)

    if vlm_score >= 70:
        summary = "The deepfake detector reports high synthetic-content risk."
    elif vlm_score >= 35:
        summary = "The deepfake detector reports an ambiguous synthetic-content signal."
    else:
        summary = "The deepfake detector does not report strong synthetic-content risk."

    return ModuleFinding(
        id="ai_generated",
        title="AI-Generated / Deepfake Detection",
        score=round(vlm_score, 2),
        status=_status(vlm_score),
        summary=summary,
        evidence=evidence,
    )


def _analyze_ai_batch(
    image_matrices: list[np.ndarray],
    data: bytes | None,
    content_type: str,
    filename: str,
) -> ModuleFinding:
    scores: list[float] = []
    evidence = [f"Sampled {len(image_matrices)} rendered PDF page(s) with the synthetic-image detector."]

    for index, matrix in enumerate(image_matrices, start=1):
        score, page_evidence = analyze_image_generation_signals(matrix, data, content_type, filename)
        scores.append(score)
        evidence.append(f"Page {index}: synthetic-image risk {score:.1f}/100.")
        evidence.extend(page_evidence[:1])

    average_score = sum(scores) / len(scores)
    score = max(average_score, max(scores) * 0.9)
    if score >= 70:
        summary = "Rendered PDF pages strongly resemble synthetic or AI-composed visuals."
    elif score >= 35:
        summary = "Rendered PDF pages have mixed synthetic-image signals."
    else:
        summary = "Rendered PDF pages do not show strong synthetic-image risk."

    return ModuleFinding(
        id="ai_generated",
        title="PDF Synthetic Visual Detection",
        score=round(score, 2),
        status=_status(score),
        summary=summary,
        evidence=evidence[:8],
    )


def _extract_pdf_text(data: bytes) -> str:
    try:
        import fitz
    except ImportError:
        return ""

    chunks: list[str] = []
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            for page in document:
                text = page.get_text("text").strip()
                if text:
                    chunks.append(text)
    except Exception:
        return ""
    return "\n\n".join(chunks)


def _analyze_pdf_embedded_images(data: bytes) -> ModuleFinding | None:
    matrices = _extract_pdf_embedded_images(data, max_images=settings.PDF_EMBEDDED_IMAGE_SAMPLE_LIMIT)
    if not matrices:
        return None

    scores: list[float] = []
    evidence = [f"Found {len(matrices)} embedded raster image(s) sampled from the PDF."]
    for index, matrix in enumerate(matrices, start=1):
        visual_score, _, _ = _visual_signal_score(matrix)
        synthetic_score, synthetic_evidence = analyze_image_generation_signals(matrix, data, "application/pdf", "embedded-image")
        image_score = (visual_score * 0.55) + (synthetic_score * 0.45)
        scores.append(image_score)
        evidence.append(
            f"Embedded image {index}: visual risk {visual_score:.1f}/100, synthetic-image risk {synthetic_score:.1f}/100."
        )
        evidence.extend(synthetic_evidence[:1])

    score = max(sum(scores) / len(scores), max(scores) * 0.9)
    if score >= 70:
        summary = "Embedded PDF images show strong synthetic or editing signals."
    elif score >= 35:
        summary = "Embedded PDF images show mixed authenticity signals."
    else:
        summary = "Embedded PDF images do not show strong synthetic-content risk."

    return ModuleFinding(
        id="embedded_images",
        title="Embedded Image Analysis",
        score=round(score, 2),
        status=_status(score),
        summary=summary,
        evidence=evidence[:5],
    )


def _extract_pdf_embedded_images(data: bytes, max_images: int) -> list[np.ndarray]:
    try:
        import fitz
    except ImportError:
        return []

    matrices: list[np.ndarray] = []
    seen: set[int] = set()
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            for page in document:
                for image_ref in page.get_images(full=True):
                    xref = int(image_ref[0])
                    if xref in seen:
                        continue
                    seen.add(xref)
                    extracted = document.extract_image(xref)
                    image_bytes = extracted.get("image")
                    if not image_bytes:
                        continue
                    file_bytes = np.frombuffer(image_bytes, np.uint8)
                    matrix = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                    if matrix is not None:
                        matrices.append(matrix)
                    if len(matrices) >= max_images:
                        return matrices
    except Exception:
        return matrices
    return matrices


def _sample_video_frames(data: bytes, filename: str) -> list[np.ndarray]:
    suffix = Path(filename).suffix or ".mp4"
    frames: list[np.ndarray] = []

    with NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(data)
        temp_path = temp.name

    try:
        capture = cv2.VideoCapture(temp_path)
        if not capture.isOpened():
            return frames

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count <= 0:
            positions = [0]
        else:
            samples = max(1, settings.VIDEO_SAMPLE_FRAMES)
            positions = np.linspace(0, max(frame_count - 1, 0), num=samples, dtype=int).tolist()

        for position in positions:
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(position))
            ok, frame = capture.read()
            if ok and frame is not None:
                frames.append(frame)
        capture.release()
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass

    return frames


def _reasoning(verdict: str, findings: list[ModuleFinding]) -> list[str]:
    sorted_findings = sorted(findings, key=lambda item: item.score, reverse=True)
    reasons = [
        f"Final verdict is {verdict} based on the weighted forensic ensemble.",
        f"Highest contributing module: {sorted_findings[0].title} ({sorted_findings[0].score:.2f}/100).",
    ]
    for finding in sorted_findings[:3]:
        reasons.append(f"{finding.title}: {finding.summary}")
    return reasons


def _status(score: float):
    if score >= 70:
        return "risk"
    if score >= 35:
        return "review"
    return "pass"
