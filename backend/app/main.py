from contextlib import asynccontextmanager
import gc
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.core.config import settings

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

ml_models = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.USE_LOCAL_MODEL:
        from transformers import pipeline

        print(f"Loading VLM model locally: {settings.VLM_MODEL_ID}")
        ml_models["vlm"] = pipeline(
            "image-classification",
            model=settings.VLM_MODEL_ID,
        )
        print(f"Loading text detector locally: {settings.TEXT_MODEL_ID}")
        ml_models["text"] = pipeline(
            "text-classification",
            model=settings.TEXT_MODEL_ID,
        )
        print("VLM model loaded successfully.")
    else:
        print("Running in Cloud Mode: Using Hugging Face REST API for VLM inference.")

    try:
        yield
    finally:
        ml_models.clear()
        gc.collect()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(routes.router, prefix="/api/documents", tags=["documents"])


@app.get("/")
def root():
    mode = "local" if settings.USE_LOCAL_MODEL else "cloud"
    return {
        "service": settings.PROJECT_NAME,
        "status": "ok",
        "mode": mode,
        "analyze_endpoint": "/api/documents/analyze",
    }
