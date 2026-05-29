import json
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional

from app.core.config import settings

_jobs: Dict[str, Dict[str, Any]] = {}
_lock = RLock()


def create_job(job_id: str, filename: str, content_type: str) -> Dict[str, Any]:
    job = {
        "job_id": job_id,
        "filename": filename,
        "content_type": content_type,
        "status": "queued",
        "report": None,
        "error": None,
    }
    with _lock:
        _jobs[job_id] = job
        _persist(job_id, job)
    return job


def update_job(job_id: str, **updates) -> Dict[str, Any]:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            job = _load(job_id) or {"job_id": job_id}
            _jobs[job_id] = job
        job.update(updates)
        _persist(job_id, job)
        return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        if job_id in _jobs:
            return _jobs[job_id]
        loaded = _load(job_id)
        if loaded:
            _jobs[job_id] = loaded
        return loaded


def _storage_dir() -> Path:
    path = Path(settings.RESULT_STORAGE_DIR)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _persist(job_id: str, job: Dict[str, Any]) -> None:
    path = _storage_dir() / f"{job_id}.json"
    path.write_text(json.dumps(job, indent=2), encoding="utf-8")


def _load(job_id: str) -> Optional[Dict[str, Any]]:
    path = _storage_dir() / f"{job_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
