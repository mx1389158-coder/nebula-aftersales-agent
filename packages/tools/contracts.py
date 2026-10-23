from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolEvidence(BaseModel):
    type: str
    id: str


class ToolResult(BaseModel):
    status: Literal["success", "not_found", "need_confirm", "failed"]
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    message_for_model: str
    evidence: list[ToolEvidence] = Field(default_factory=list)
    retryable: bool = False
