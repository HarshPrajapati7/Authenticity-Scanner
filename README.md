# Document Trust Engine

Production-ready document forgery and deepfake detection module built with FastAPI, OpenCV, Hugging Face, and Next.js.

## Features

- Mobile-first verification UI for pasted text, TXT/MD, PDF, JPG, JPEG, PNG, video, and audio
- Google Identity login gate with local demo fallback for development
- Async analysis workflow with job creation and result retrieval
- Explainable forensic modules:
  - Metadata analysis
  - Visual forensics with FFT, ELA, and Laplacian noise
  - AI-generated/deepfake detection through Hugging Face
  - AI-written text detection for pasted text, text files, and selectable PDF text
  - Text and font consistency heuristics
  - QR, seal, and security feature checks
- Overall fraud confidence score from 0-100
- Final verdict: `Genuine`, `Suspicious`, or `Likely Forged`
- Suspicion heatmap for visual artifact review
- JSON report export
- Docker and Docker Compose support

## Architecture

```text
frontend/ Next.js + TypeScript
    -> POST /api/documents/analyze
    -> GET  /api/documents/{id}/result

backend/ FastAPI + OpenCV + Pillow + Hugging Face
    -> validates upload or pasted text
    -> stores job status
    -> routes text, PDFs, images, video, and audio through the matching forensic pipeline
    -> persists reports in backend/storage/results
```

## Local Setup

### Backend

```powershell
cd backend
copy .env.example .env
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

Set `HUGGINGFACE_API_KEY` in `backend/.env`. Keep real tokens out of `.env.example`.

### Frontend

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## Environment Variables

### Backend

| Name | Description | Example |
| --- | --- | --- |
| `USE_LOCAL_MODEL` | `true` loads the model locally, `false` uses HF REST API | `false` |
| `HUGGINGFACE_API_KEY` | Hugging Face token for REST inference | `hf_...` |
| `VLM_MODEL_ID` | Hugging Face model ID | `prithivMLmods/Deepfake-Detect-Siglip2` |
| `TEXT_MODEL_ID` | Local text detector model ID | `openai-community/roberta-base-openai-detector` |
| `HF_TEXT_API_URL` | Hugging Face text detector REST URL | `https://api-inference.huggingface.co/models/...` |
| `MAX_UPLOAD_MB` | Upload size limit | `10` |
| `MAX_TEXT_CHARS` | Maximum pasted/extracted text sent to text analysis | `12000` |
| `VIDEO_SAMPLE_FRAMES` | Number of representative frames sampled from videos | `4` |
| `CORS_ORIGINS` | Comma-separated frontend origins | `http://localhost:3000` |

### Frontend

| Name | Description | Example |
| --- | --- | --- |
| `NEXT_PUBLIC_BACKEND_URL` | FastAPI backend URL for Next rewrites | `http://127.0.0.1:8010` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google Identity Services OAuth client ID | `123.apps.googleusercontent.com` |

## API Docs

### Create Analysis Job

`POST /api/documents/analyze`

Form data:

- `file`: PDF, TXT, MD, JPG, JPEG, PNG, MP4, WEBM, MOV, MP3, WAV, or M4A

### Create Pasted Text Analysis Job

`POST /api/documents/analyze-text`

Form data:

- `text`: raw text to verify
- `filename`: optional display filename

Response:

```json
{
  "job_id": "abc123",
  "status": "queued",
  "result_url": "/api/documents/abc123/result"
}
```

### Retrieve Result

`GET /api/documents/{id}/result`

Response while running:

```json
{
  "job_id": "abc123",
  "status": "processing",
  "report": null,
  "error": null
}
```

Completed response includes the full report with `overall_score`, `verdict`, `reasoning`, `findings`, and `heatmap`.

## Deployment

- Frontend: Vercel
- Backend: Render, Railway, AWS, or Docker host
- Set `USE_LOCAL_MODEL=false` for memory-constrained cloud deployments.
- Set `NEXT_PUBLIC_BACKEND_URL` in the frontend deployment to the public backend URL.

## Demo Video Checklist

1. Problem choice and why document trust matters
2. Architecture: Next.js frontend, FastAPI backend, async jobs
3. Pipeline: metadata, visual forensics, AI detection, text/font, security checks
4. Security: file validation, size limits, CORS, ignored secrets
5. Performance: cloud REST inference toggle and persisted result retrieval

## Improvements With More Time

- Add OCR with DocTR or PaddleOCR for richer text-level evidence
- Add database-backed job storage with PostgreSQL
- Add PDF report export
- Add user authentication and audit logs
- Fine-tune the ensemble weights on a labeled forged-document dataset
