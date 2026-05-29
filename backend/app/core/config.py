import os
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(env_path)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _env_tuple(name: str, default: Tuple[str, ...]) -> Tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Forensic Analysis Engine")
    VLM_MODEL_ID: str = os.getenv(
        "VLM_MODEL_ID",
        "prithivMLmods/Deepfake-Detect-Siglip2",
    )
    TEXT_MODEL_ID: str = os.getenv(
        "TEXT_MODEL_ID",
        "fakespot-ai/roberta-base-ai-text-detection-v1",
    )
    HF_API_URL: str = os.getenv(
        "HF_API_URL",
        "https://router.huggingface.co/hf-inference/models/prithivMLmods/Deepfake-Detect-Siglip2",
    )
    HF_TEXT_API_URL: str = os.getenv(
        "HF_TEXT_API_URL",
        "https://router.huggingface.co/hf-inference/models/fakespot-ai/roberta-base-ai-text-detection-v1",
    )
    # Secondary text detector used for ensemble corroboration. Leave empty to disable.
    HF_TEXT_API_URL_2: str = os.getenv(
        "HF_TEXT_API_URL_2",
        "https://router.huggingface.co/hf-inference/models/Hello-SimpleAI/chatgpt-detector-roberta",
    )
    # Relative weight of the primary text detector when both models respond.
    TEXT_PRIMARY_WEIGHT: float = _env_float("TEXT_PRIMARY_WEIGHT", 0.6)
    # Chat LLM (OpenAI-compatible HF router) used to narrate the report.
    LLM_MODEL_ID: str = os.getenv("LLM_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct")
    LLM_API_URL: str = os.getenv(
        "LLM_API_URL",
        "https://router.huggingface.co/v1/chat/completions",
    )
    LLM_MAX_TOKENS: int = _env_int("LLM_MAX_TOKENS", 220)
    LLM_TIMEOUT_SECONDS: int = _env_int("LLM_TIMEOUT_SECONDS", 30)
    HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")
    USE_LOCAL_MODEL: bool = _env_bool("USE_LOCAL_MODEL", False)
    HF_API_TIMEOUT_SECONDS: int = _env_int("HF_API_TIMEOUT_SECONDS", 45)
    MAX_UPLOAD_MB: int = _env_int("MAX_UPLOAD_MB", 10)
    MAX_TEXT_CHARS: int = _env_int("MAX_TEXT_CHARS", 12000)
    MIN_TEXT_WORDS: int = _env_int("MIN_TEXT_WORDS", 80)
    VIDEO_SAMPLE_FRAMES: int = _env_int("VIDEO_SAMPLE_FRAMES", 4)
    PDF_SAMPLE_PAGES: int = _env_int("PDF_SAMPLE_PAGES", 3)
    PDF_EMBEDDED_IMAGE_SAMPLE_LIMIT: int = _env_int("PDF_EMBEDDED_IMAGE_SAMPLE_LIMIT", 4)
    TEXT_MODEL_CHUNKS: int = _env_int("TEXT_MODEL_CHUNKS", 3)
    RESULT_STORAGE_DIR: str = os.getenv("RESULT_STORAGE_DIR", "storage/results")
    CORS_ORIGINS: Tuple[str, ...] = _env_tuple(
        "CORS_ORIGINS",
        (
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ),
    )

    FFT_ANOMALY_THRESHOLD: float = _env_float("FFT_ANOMALY_THRESHOLD", 0.15)
    ELA_CONFIDENCE_THRESHOLD: float = _env_float("ELA_CONFIDENCE_THRESHOLD", 75.0)


settings = Settings()
