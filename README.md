# Document Trust Engine

[Live Demo](https://authenticity-scannerhp.vercel.app) • [Demo Video](https://youtu.be/0PzUFaTTdGw?si=nvzHc5v-GEwGPj0g)

> A multi-modal document authenticity and forgery detection platform for analyzing text, PDFs, images, video, and audio through explainable digital forensics and machine learning.

## Overview

Document Trust Engine is a production-oriented forensic analysis system designed to assess the authenticity of digital content across multiple modalities. The platform combines classical digital forensics, statistical heuristics, and modern machine learning models to detect signs of manipulation, synthetic generation, and document fraud.

The system is built around a decoupled architecture: a Next.js frontend handles user interaction and file submission, while a FastAPI backend executes analysis through modality-specific pipelines. An asynchronous job workflow keeps the UI responsive during long-running analysis tasks and allows results to be retrieved after processing completes.

The goal of the project is not only to classify content as genuine or forged, but also to provide evidence that is interpretable, reproducible, and useful in real-world review workflows.

## Why this project matters

Digital content can now be generated, edited, and recombined with very little visual evidence. That makes authenticity verification a practical requirement in domains such as academic submission review, legal document validation, media verification, and general trust and safety workflows.

Document Trust Engine addresses this problem by combining independent forensic signals into a single report, allowing users to see both the final verdict and the supporting evidence behind it.

## System architecture

```text
Frontend (Next.js + TypeScript)
    ↓
POST /api/documents/analyze
    ↓
FastAPI backend
    ↓
Modality routing and validation
    ↓
Text / PDF / Image / Video / Audio pipelines
    ↓
Evidence fusion and scoring
    ↓
Explainable report generation
    ↓
GET /api/documents/{id}/result
```

## End-to-end workflow

### 1. Content submission

The user either uploads a file or pastes text into the interface. Supported inputs include:

* Plain text: pasted text, TXT, MD
* Documents: PDF
* Images: JPG, JPEG, PNG
* Video: MP4, WEBM, MOV
* Audio: MP3, WAV, M4A

Before analysis begins, the backend validates file type, size, and structural integrity to reject unsupported or unsafe inputs early.

### 2. Job creation

Analysis is handled asynchronously. When a request arrives, the backend creates a unique job ID, stores the request status, and immediately returns control to the client. The actual forensic processing runs in the background.

This design prevents request blocking and allows the frontend to poll for results while the backend completes heavier computations.

### 3. Modality detection and routing

Once the input is accepted, the backend determines which analysis pipeline should process it:

* text or pasted content → text pipeline
* PDF → PDF pipeline
* image → image pipeline
* video → video pipeline
* audio → audio pipeline

Each pipeline extracts the most informative signals for that modality and contributes them to the final report.

## Text analysis pipeline

Text content is examined for machine-generated patterns, structural regularity, and linguistic anomalies.

### Step-by-step

1. **Extraction**

   * Text is accepted from pasted input, text files, or extracted PDF text.

2. **Normalization**

   * Content is cleaned, trimmed, and prepared for model inference.

3. **Chunking**

   * Long text is split into smaller segments to stay within transformer token limits.
   * This avoids inference failures on large inputs and improves stability for long documents.

4. **AI text detection**

   * Transformer-based detectors estimate whether the text resembles generated output.
   * Multiple models can be combined to reduce bias from any single detector.

5. **Linguistic heuristics**

   * The system inspects sentence structure, repetition, predictability, and consistency.

6. **Text verdict contribution**

   * The resulting score is normalized and passed to the evidence fusion layer.

## PDF analysis pipeline

PDFs contain both text and embedded visual information, so they are treated as structured forensic containers rather than flat images.

### Step-by-step

1. **Structural parsing**

   * The document is opened with PyMuPDF.
   * Pages, metadata, and embedded assets are enumerated.

2. **Text extraction**

   * Extracted text is forwarded to the text analysis pipeline.

3. **Embedded image extraction**

   * Raster images inside the PDF are isolated and analyzed separately.

4. **Metadata inspection**

   * Creation software, modification history, producer data, and timestamp consistency are reviewed.

5. **Document-level scoring**

   * Text, metadata, and embedded image evidence are fused into a single PDF trust score.

## Image forensics pipeline

The image pipeline combines classical forensic analysis with deep learning-based classification.

### Step-by-step

1. **Metadata analysis**

   * EXIF and file metadata are checked for editing traces, missing fields, and generator fingerprints.

2. **Error Level Analysis (ELA)**

   * The image is recompressed and compared against the original to reveal regions with abnormal compression artifacts.

3. **FFT frequency analysis**

   * Frequency-domain patterns are inspected for unusual spectral behavior that may indicate synthetic generation or editing.

4. **Laplacian noise assessment**

   * Local noise consistency and edge behavior are measured to identify smoothing, tampering, or generation artifacts.

5. **Vision-language model inference**

   * A Hugging Face vision model is used to detect deepfake or synthetic image patterns.

6. **Heatmap generation**

   * Suspicious regions are combined into a visual heatmap for interpretability.

## Video analysis pipeline

Video files are analyzed through integrity checks and representative frame sampling.

### Step-by-step

1. **Container and metadata validation**

   * The backend checks file structure, codec details, and metadata consistency.

2. **Representative frame sampling**

   * A fixed number of frames is extracted from the video for downstream inspection.

3. **Frame-level analysis**

   * Sampled frames are routed through the image pipeline.

4. **Video-level reporting**

   * Results from individual frames are aggregated into a unified video assessment.

## Audio analysis pipeline

Audio files are processed through integrity-oriented checks that inspect file structure, metadata, and consistency signals.

### Step-by-step

1. **Format validation**

   * The file is checked for supported encoding and container integrity.

2. **Metadata analysis**

   * The backend inspects available audio metadata for inconsistencies.

3. **Structural checks**

   * File-level anomalies are recorded for inclusion in the report.

4. **Future extensibility**

   * The architecture is prepared for future deepfake speech detection integration.

## Evidence fusion and fraud scoring

Each forensic module outputs a partial score or confidence value. These values are normalized and combined through a weighted aggregation framework to produce the final fraud confidence score.

### Final score

Let the module scores be:

* text score: (S_t)
* metadata score: (S_m)
* visual score: (S_v)
* deepfake score: (S_d)
* security score: (S_s)

The final score is computed as:

[
F = \sum_{i=1}^{n} w_i S_i
]

subject to:

[
\sum_{i=1}^{n} w_i = 1
]

where each (w_i) is a reliability weight assigned to a forensic module.

### Verdict mapping

* **0–34** → `Genuine`
* **35–69** → `Suspicious`
* **70–100** → `Likely Forged`

## Explainable reporting

The report generated by the system is designed to be readable and defensible. It includes:

* overall fraud confidence score
* final verdict
* reasoning summary
* evidence breakdown by pipeline
* suspicious regions heatmap
* JSON export

The explainability layer helps users understand *why* content was flagged instead of only seeing a binary classification result.

## Frontend

The frontend is built with:

* Next.js
* React
* TypeScript
* Tailwind CSS

Key responsibilities:

* mobile-first verification interface
* authentication gate with Google Identity login
* file upload and pasted text submission
* job status polling
* result visualization and report rendering

## Backend

The backend is built with:

* FastAPI
* OpenCV
* Pillow
* PyMuPDF
* Hugging Face inference APIs

Key responsibilities:

* request validation
* async job management
* modality routing
* forensic analysis execution
* result persistence
* JSON report generation

## API endpoints

### Create analysis job

`POST /api/documents/analyze`

Form data:

* `file`

Supported types:

* PDF, TXT, MD, JPG, JPEG, PNG, MP4, WEBM, MOV, MP3, WAV, M4A

### Create pasted text analysis job

`POST /api/documents/analyze-text`

Form data:

* `text`
* `filename` (optional)

### Retrieve result

`GET /api/documents/{id}/result`

## Local setup

### Backend

```powershell
cd backend
copy .env.example .env
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

Set `HUGGINGFACE_API_KEY` in `backend/.env` and keep real secrets out of version-controlled example files.

### Frontend

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open `http://127.0.0.1:3000` in your browser.

## Environment variables

### Backend

| Name                  | Description                                      | Example                                           |
| --------------------- | ------------------------------------------------ | ------------------------------------------------- |
| `USE_LOCAL_MODEL`     | Enables local model execution when set to `true` | `false`                                           |
| `HUGGINGFACE_API_KEY` | Hugging Face token for REST inference            | `hf_...`                                          |
| `VLM_MODEL_ID`        | Vision model identifier                          | `prithivMLmods/Deepfake-Detect-Siglip2`           |
| `TEXT_MODEL_ID`       | Local text detector model ID                     | `openai-community/roberta-base-openai-detector`   |
| `HF_TEXT_API_URL`     | Hugging Face text inference URL                  | `https://api-inference.huggingface.co/models/...` |
| `MAX_UPLOAD_MB`       | Maximum upload size                              | `10`                                              |
| `MAX_TEXT_CHARS`      | Maximum text length for analysis                 | `12000`                                           |
| `VIDEO_SAMPLE_FRAMES` | Number of frames sampled from video              | `4`                                               |
| `CORS_ORIGINS`        | Allowed frontend origins                         | `http://localhost:3000`                           |

### Frontend

| Name                           | Description                        | Example                          |
| ------------------------------ | ---------------------------------- | -------------------------------- |
| `NEXT_PUBLIC_BACKEND_URL`      | Backend URL used by the frontend   | `http://127.0.0.1:8010`          |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google Identity Services client ID | `123.apps.googleusercontent.com` |

## Deployment

### Recommended deployment split

* **Frontend:** Vercel
* **Backend:** Render, Railway, AWS, or any Docker-compatible host

### Deployment notes

* Set `USE_LOCAL_MODEL=false` for cloud environments with limited memory.
* Point `NEXT_PUBLIC_BACKEND_URL` to the public backend URL.
* Use Docker or Docker Compose for reproducible builds.
