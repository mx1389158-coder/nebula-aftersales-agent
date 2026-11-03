from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Principal(BaseModel):
    user_id: str
    tenant_id: str
    role: str = "user"
    access_token: str | None = Field(default=None, exclude=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=256)


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    section: str
    version: str
    page: int | None = None
    score: float
    excerpt: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    thread_id: str | None = None
    device_id: str | None = None
    product_id: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    confirmed: bool = False
    contact: str | None = Field(default=None, max_length=120)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class ResumeRequest(BaseModel):
    confirmed: bool
    message: str | None = Field(default=None, max_length=8000)
    contact: str | None = Field(default=None, max_length=120)


class ChatResponse(BaseModel):
    request_id: str
    message_id: str
    thread_id: str
    decision: Literal["ANSWER", "ASK", "TOOL", "ESCALATE", "REFUSE"]
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)
    tool_result: dict[str, Any] | None = None
    pending_action: dict[str, Any] | None = None
    handoff_id: str | None = None


class MemoryCreate(BaseModel):
    kind: Literal["fact", "preference", "event"] = "fact"
    fact: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(default=1.0, ge=0, le=1)
    valid_to: datetime | None = None
    consent: bool = True


class MemoryUpdate(BaseModel):
    fact: str | None = Field(default=None, min_length=1, max_length=2000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    valid_to: datetime | None = None
    status: Literal["active", "deleted", "expired"] | None = None
    consent: bool | None = None


class MemoryView(ORMModel):
    id: str
    kind: str
    fact: str
    confidence: float
    valid_from: datetime
    valid_to: datetime | None
    status: str
    consent: bool
    created_at: datetime


class TicketCreate(BaseModel):
    summary: str = Field(min_length=5, max_length=4000)
    contact: str = Field(min_length=3, max_length=120)
    device_id: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)
    confirmed: bool = False


class TicketView(ORMModel):
    id: str
    status: str
    summary: str
    contact: str
    device_id: str | None
    created_at: datetime
    updated_at: datetime


class TicketUpdate(BaseModel):
    status: Literal["open", "assigned", "waiting_user", "resolved", "closed"]
    note: str | None = Field(default=None, max_length=2000)


class DocumentView(ORMModel):
    id: str
    title: str
    source: str
    product_id: str
    model: str | None
    firmware_version: str | None
    doc_version: str
    status: str
    created_at: datetime


class PublishDocumentRequest(BaseModel):
    active: bool = True


class JobView(ORMModel):
    id: str
    kind: str
    status: str
    progress: float
    result: dict[str, Any]
    attempts: int
    max_attempts: int
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class EvalRunRequest(BaseModel):
    dataset_version: str = "aftersales-eval-v2"
    retrieval_variant: Literal[
        "no_retrieval",
        "dense",
        "hybrid",
        "hybrid_rerank",
        "lightrag",
        "openviking",
    ] = "hybrid"
    memory_variant: Literal["M0", "M1", "M2", "M3"] = "M3"
    skill_variant: Literal["none", "manual", "extracted", "reviewed"] = "reviewed"


class ExperimentMatrixRequest(BaseModel):
    dataset_version: str = "aftersales-eval-v2"


class SkillCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scope: dict[str, Any] = Field(default_factory=dict)
    steps: list[dict[str, Any]] = Field(min_length=1)
    tests: list[dict[str, Any]] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)


class SkillVersionCreate(BaseModel):
    steps: list[dict[str, Any]] = Field(min_length=1)
    tests: list[dict[str, Any]] = Field(min_length=1)
    constraints: dict[str, Any] = Field(default_factory=dict)


class RolloutRequest(BaseModel):
    percent: int = Field(ge=0, le=100)


class UserSettingsUpdate(BaseModel):
    auto_memory_enabled: bool


class FeedbackCreate(BaseModel):
    message_id: str
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=1000)


class HandoffUpdate(BaseModel):
    status: Literal["waiting", "assigned", "resolved"]
    assigned_to: str | None = Field(default=None, max_length=80)
