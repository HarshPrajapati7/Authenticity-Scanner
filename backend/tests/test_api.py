from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import wave

from fastapi.testclient import TestClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo

os.environ["USE_LOCAL_MODEL"] = "false"
os.environ["HUGGINGFACE_API_KEY"] = ""
os.environ["RESULT_STORAGE_DIR"] = tempfile.mkdtemp(prefix="forensic-results-")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def _png_bytes() -> bytes:
    image = Image.new("RGB", (120, 160), color=(242, 239, 221))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _openai_tagged_png_bytes() -> bytes:
    image = Image.new("RGB", (1024, 1024), color=(180, 120, 200))
    metadata = PngInfo()
    metadata.add_text("Software", "OpenAI gpt-image synthetic generation")
    metadata.add_text("Prompt", "Generated image test fixture")
    buffer = BytesIO()
    image.save(buffer, format="PNG", pnginfo=metadata)
    return buffer.getvalue()


def _pdf_bytes() -> bytes:
    import fitz

    document = fitz.open()
    for page_number in range(2):
        page = document.new_page(width=420, height=595)
        page.insert_text(
            (48, 80),
            f"AI document analysis fixture page {page_number + 1}. "
            "This PDF contains selectable text and rendered page visuals.",
            fontsize=14,
        )
        page.draw_rect((48, 140, 340, 260), color=(0.9, 0.1, 0.1), fill=(0.9, 0.1, 0.1))
    payload = document.tobytes()
    document.close()
    return payload


def test_document_analysis_job_flow():
    with TestClient(app) as client:
        created = client.post(
            "/api/documents/analyze",
            files={"file": ("sample.png", _png_bytes(), "image/png")},
        )

        assert created.status_code == 202
        accepted = created.json()
        assert accepted["status"] == "queued"
        assert accepted["result_url"].endswith("/result")

        result = client.get(accepted["result_url"])
        assert result.status_code == 200
        payload = result.json()
        assert payload["status"] == "completed"
        assert payload["report"]["verdict"] in {"Genuine", "Suspicious", "Likely Forged"}
        assert len(payload["report"]["findings"]) >= 5


def test_rejects_unsupported_file_type():
    with TestClient(app) as client:
        response = client.post(
            "/api/documents/analyze",
            files={"file": ("notes.docx", b"hello", "application/octet-stream")},
        )

        assert response.status_code == 415


def test_text_analysis_job_flow():
    text = (
        "Authentic writing can vary in rhythm and detail. "
        "This sample includes short sentences, longer observations, and a few uneven transitions. "
        "The detector should accept pasted text and return a completed report."
    )

    with TestClient(app) as client:
        created = client.post(
            "/api/documents/analyze-text",
            data={"text": text, "filename": "sample.txt"},
        )

        assert created.status_code == 202
        accepted = created.json()

        result = client.get(accepted["result_url"])
        assert result.status_code == 200
        payload = result.json()
        assert payload["status"] == "completed"
        assert payload["report"]["content_type"] == "text/plain"
        assert payload["report"]["findings"][0]["id"] == "text_ai"


def test_audio_analysis_job_flow():
    buffer = BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 16000)

    with TestClient(app) as client:
        created = client.post(
            "/api/documents/analyze",
            files={"file": ("voice.wav", buffer.getvalue(), "audio/wav")},
        )

        assert created.status_code == 202
        result = client.get(created.json()["result_url"])
        assert result.status_code == 200
        payload = result.json()
        assert payload["status"] == "completed"
        assert payload["report"]["findings"][0]["id"] == "audio_ai"


def test_pdf_analysis_combines_text_and_rendered_pages():
    with TestClient(app) as client:
        created = client.post(
            "/api/documents/analyze",
            files={"file": ("paper.pdf", _pdf_bytes(), "application/pdf")},
        )

        assert created.status_code == 202
        result = client.get(created.json()["result_url"])
        assert result.status_code == 200
        payload = result.json()
        report = payload["report"]
        finding_ids = {finding["id"] for finding in report["findings"]}

        assert payload["status"] == "completed"
        assert report["content_type"] == "application/pdf"
        assert {"visual", "ai_generated", "text_ai"}.issubset(finding_ids)


def test_ai_generator_png_trace_is_not_marked_genuine():
    with TestClient(app) as client:
        created = client.post(
            "/api/documents/analyze",
            files={"file": ("generated.png", _openai_tagged_png_bytes(), "image/png")},
        )

        assert created.status_code == 202
        result = client.get(created.json()["result_url"])
        assert result.status_code == 200
        payload = result.json()
        report = payload["report"]
        metadata = next(finding for finding in report["findings"] if finding["id"] == "metadata")

        assert payload["status"] == "completed"
        assert report["verdict"] in {"Suspicious", "Likely Forged"}
        assert metadata["score"] >= 85
