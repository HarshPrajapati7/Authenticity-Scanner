from typing import Literal, Optional

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "processing", "completed", "failed"]
Verdict = Literal["Genuine", "Suspicious", "Likely Forged"]
FindingStatus = Literal["pass", "review", "risk"]


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus
    result_url: str


class ModuleFinding(BaseModel):
    id: str
    title: str
    score: float = Field(ge=0.0, le=100.0)
    status: FindingStatus
    summary: str
    evidence: list[str] = Field(default_factory=list)


class ForensicReport(BaseModel):
    job_id: str
    filename: str
    content_type: str
    status: Literal["completed"] = "completed"
    overall_score: float = Field(ge=0.0, le=100.0)
    verdict: Verdict
    reasoning: list[str] = Field(default_factory=list)
    explanation: Optional[str] = None
    findings: list[ModuleFinding]
    heatmap: Optional[str] = None
    created_at: str


class JobResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    report: Optional[ForensicReport] = None
    error: Optional[str] = None
