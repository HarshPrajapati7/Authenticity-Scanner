"""Generates a short, human-readable explanation of a forensic report.

Uses a chat LLM via the Hugging Face router (OpenAI-compatible endpoint). If the
LLM is unavailable, falls back to a deterministic template built from the same
findings, so the explanation panel always has content.
"""
from __future__ import annotations

import requests

from app.core.config import settings
from app.schemas.responses import ForensicReport


def generate_explanation(report: ForensicReport) -> str:
    llm_text = _llm_explanation(report)
    if llm_text:
        return llm_text
    return _template_explanation(report)


def _findings_block(report: ForensicReport) -> str:
    lines = []
    for finding in report.findings:
        lines.append(f"- {finding.title}: {finding.score:.0f}/100 ({finding.status}) - {finding.summary}")
    return "\n".join(lines)


def _content_label(report: ForensicReport) -> str:
    ct = report.content_type
    if ct == "application/pdf":
        return "PDF document"
    if ct.startswith("audio/"):
        return "audio clip"
    if ct.startswith("video/"):
        return "video clip"
    if ct.startswith("image/"):
        return "image"
    return "text"


def _llm_explanation(report: ForensicReport) -> str:
    if not settings.HUGGINGFACE_API_KEY or not settings.LLM_MODEL_ID:
        return ""

    prompt = (
        "You are a forensic AI-content analyst. Based ONLY on the detection results below, "
        "write a clear, calm explanation for a non-technical user in 2-4 short sentences. "
        "State plainly whether the content appears AI-generated/manipulated and the key reasons. "
        "Do not invent details or numbers beyond what is provided. Do not use markdown headers.\n\n"
        f"Content type: {_content_label(report)}\n"
        f"Overall AI probability: {report.overall_score:.0f}%\n"
        f"Verdict: {report.verdict}\n"
        f"Module findings:\n{_findings_block(report)}\n"
    )

    headers = {
        "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.LLM_MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": settings.LLM_MAX_TOKENS,
        "temperature": 0.3,
    }

    try:
        response = requests.post(
            settings.LLM_API_URL,
            headers=headers,
            json=body,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"].strip()
        return content
    except Exception as exc:
        print(f"LLM explanation error: {exc}")
        return ""


def _template_explanation(report: ForensicReport) -> str:
    label = _content_label(report)
    score = report.overall_score
    top = sorted(report.findings, key=lambda f: f.score, reverse=True)
    drivers = ", ".join(f.title for f in top[:2]) if top else "the combined forensic signals"

    if score >= 75:
        stance = f"This {label} shows strong signs of being AI-generated or manipulated"
    elif score >= 40:
        stance = f"This {label} shows mixed signals and should be reviewed carefully"
    else:
        stance = f"This {label} looks more consistent with authentic, human-origin content"

    return (
        f"{stance}. The overall AI probability is {score:.0f}% ({report.verdict}). "
        f"The strongest contributing signals were {drivers}. "
        "This is an automated estimate — treat borderline results as advisory, not definitive."
    )
