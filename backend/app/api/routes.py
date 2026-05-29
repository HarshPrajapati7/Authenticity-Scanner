import logging
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.storage import create_job, get_job, update_job
from app.modules.explain import generate_explanation
from app.modules.pipeline import build_forensic_report
from app.schemas.responses import JobAcceptedResponse, JobResultResponse

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "application/pdf": {".pdf"},
    "text/plain": {".txt", ".md", ".text"},
    "text/markdown": {".md"},
    "audio/mpeg": {".mp3"},
    "audio/mp3": {".mp3"},
    "audio/wav": {".wav"},
    "audio/x-wav": {".wav"},
    "audio/mp4": {".m4a"},
    "audio/x-m4a": {".m4a"},
    "video/mp4": {".mp4", ".m4v"},
    "video/webm": {".webm"},
    "video/quicktime": {".mov"},
}


@router.post(
    "/analyze",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    data = await file.read()
    filename = Path(file.filename or "document").name
    content_type = file.content_type or "application/octet-stream"

    _validate_upload(filename, content_type, data)

    job_id = uuid4().hex
    create_job(job_id, filename, content_type)
    background_tasks.add_task(_run_analysis_job, job_id, filename, content_type, data)

    return JobAcceptedResponse(
        job_id=job_id,
        status="queued",
        result_url=f"/api/documents/{job_id}/result",
    )


@router.post(
    "/analyze-text",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze_text(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    filename: str = Form("pasted-text.txt"),
):
    normalized = " ".join(text.split())
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text is empty.")
    if len(normalized) > settings.MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Text exceeds {settings.MAX_TEXT_CHARS} character limit.",
        )

    safe_filename = Path(filename or "pasted-text.txt").name
    if Path(safe_filename).suffix.lower() not in ALLOWED_TYPES["text/plain"]:
        safe_filename = "pasted-text.txt"

    job_id = uuid4().hex
    create_job(job_id, safe_filename, "text/plain")
    background_tasks.add_task(
        _run_analysis_job,
        job_id,
        safe_filename,
        "text/plain",
        normalized.encode("utf-8"),
    )

    return JobAcceptedResponse(
        job_id=job_id,
        status="queued",
        result_url=f"/api/documents/{job_id}/result",
    )


@router.get("/{job_id}/result", response_model=JobResultResponse)
async def get_document_result(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    return JobResultResponse(
        job_id=job_id,
        status=job["status"],
        report=job.get("report"),
        error=job.get("error"),
    )


def _run_analysis_job(job_id: str, filename: str, content_type: str, data: bytes) -> None:
    update_job(job_id, status="processing")
    try:
        report = build_forensic_report(job_id, filename, content_type, data)
        try:
            report.explanation = generate_explanation(report)
        except Exception:
            logger.exception("Explanation generation failed for job %s", job_id)
        payload = report.model_dump() if hasattr(report, "model_dump") else report.dict()
        update_job(job_id, status="completed", report=payload, error=None)
    except Exception as exc:
        logger.exception("Document analysis failed for job %s", job_id)
        update_job(job_id, status="failed", error=str(exc))


def _validate_upload(filename: str, content_type: str, data: bytes) -> None:
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only text, PDF, image, audio, and video files are supported.",
        )

    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_TYPES[content_type]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension does not match the uploaded content type.",
        )

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty.")

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_UPLOAD_MB} MB limit.",
        )

    if content_type == "application/pdf":
        if not data.startswith(b"%PDF"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PDF file.")
        return

    if content_type in {"text/plain", "text/markdown"}:
        decoded = data.decode("utf-8", errors="ignore").strip()
        if not decoded:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text file is empty.")
        if len(decoded) > settings.MAX_TEXT_CHARS:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Text exceeds {settings.MAX_TEXT_CHARS} character limit.",
            )
        return

    if content_type.startswith(("audio/", "video/")):
        return

    try:
        Image.open(BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file.",
        ) from exc
