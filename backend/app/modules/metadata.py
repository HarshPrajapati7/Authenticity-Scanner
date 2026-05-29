from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

from PIL import Image, UnidentifiedImageError

from app.schemas.responses import ModuleFinding

EDITOR_TRACES = (
    "photoshop",
    "illustrator",
    "gimp",
    "canva",
    "acrobat",
    "pdf editor",
    "libreoffice",
    "microsoft",
)
AI_GENERATOR_TRACES = (
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


def analyze_metadata(data: bytes, content_type: str, filename: str) -> ModuleFinding:
    evidence: list[str] = []
    score = 10.0

    suffix = Path(filename).suffix.lower()
    if content_type == "application/pdf":
        metadata = _pdf_metadata(data)
        evidence.extend(_metadata_evidence(metadata))
    else:
        metadata = _image_metadata(data)
        evidence.extend(_metadata_evidence(metadata))

    if suffix and not _extension_matches_content_type(suffix, content_type):
        score += 35.0
        evidence.append("File extension does not match the declared content type.")

    software = " ".join(
        str(metadata.get(key, "")) for key in ("software", "creator", "producer", "prompt", "parameters")
    ).lower()
    trace_hits = _generator_trace_hits(data, software, content_type)
    if trace_hits:
        score = max(score, 90.0)
        evidence.append(f"AI-generator metadata/container trace detected: {', '.join(trace_hits[:3])}.")

    if any(trace in software for trace in EDITOR_TRACES):
        score += 25.0
        evidence.append("Metadata contains traces of editing or document generation software.")

    if _has_date_conflict(metadata):
        score += 30.0
        evidence.append("Creation and modification dates appear inconsistent.")

    if not evidence:
        evidence.append("No obvious metadata inconsistencies were found.")

    return ModuleFinding(
        id="metadata",
        title="Metadata Analysis",
        score=min(score, 100.0),
        status=_status(score),
        summary=_summary(score, "metadata consistency"),
        evidence=evidence[:5],
    )


def _image_metadata(data: bytes) -> Dict[str, Any]:
    try:
        image = Image.open(BytesIO(data))
        exif = image.getexif()
        return {
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "make": exif.get(271, ""),
            "model": exif.get(272, ""),
            "software": exif.get(305, ""),
            "created": exif.get(306, ""),
            **{f"info_{key}".lower(): value for key, value in image.info.items() if isinstance(value, str)},
        }
    except UnidentifiedImageError:
        return {}


def _pdf_metadata(data: bytes) -> Dict[str, Any]:
    try:
        import fitz

        with fitz.open(stream=data, filetype="pdf") as document:
            metadata = document.metadata or {}
            metadata["pages"] = document.page_count
            return metadata
    except Exception:
        return {"error": "PDF metadata could not be parsed."}


def _metadata_evidence(metadata: Dict[str, Any]) -> list[str]:
    evidence = []
    if metadata.get("format"):
        evidence.append(
            f"Image container: {metadata['format']} at {metadata.get('width')}x{metadata.get('height')}."
        )
    if metadata.get("pages"):
        evidence.append(f"PDF page count: {metadata['pages']}.")
    for key in ("software", "creator", "producer"):
        if metadata.get(key):
            evidence.append(f"{key.title()} metadata: {metadata[key]}.")
    if metadata.get("make") or metadata.get("model"):
        evidence.append(
            f"Camera metadata: {metadata.get('make', '')} {metadata.get('model', '')}.".strip()
        )
    if metadata.get("error"):
        evidence.append(str(metadata["error"]))
    return evidence


def _extension_matches_content_type(suffix: str, content_type: str) -> bool:
    allowed = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    return allowed.get(suffix) == content_type


def _has_date_conflict(metadata: Dict[str, Any]) -> bool:
    created = _parse_date(metadata.get("creationDate") or metadata.get("created"))
    modified = _parse_date(metadata.get("modDate") or metadata.get("modified"))
    return bool(created and modified and modified < created)


def _generator_trace_hits(data: bytes, metadata_text: str, content_type: str) -> list[str]:
    head = data[:2_000_000]
    tail = data[-1_000_000:] if len(data) > 2_000_000 else b""
    raw_context = b"" if content_type == "application/pdf" else head + b" " + tail
    haystack = (metadata_text + " ").encode("utf-8", errors="ignore") + raw_context
    text = haystack.decode("latin-1", errors="ignore").lower()
    return [trace for trace in AI_GENERATOR_TRACES if trace in text]


def _parse_date(value: Any):
    if not value:
        return None
    text = str(value).replace("D:", "")[:14]
    for fmt in ("%Y%m%d%H%M%S", "%Y:%m:%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _status(score: float):
    if score >= 70:
        return "risk"
    if score >= 35:
        return "review"
    return "pass"


def _summary(score: float, subject: str) -> str:
    if score >= 70:
        return f"High-risk {subject} signals were found."
    if score >= 35:
        return f"Some {subject} signals deserve review."
    return f"{subject.title()} looks stable."
