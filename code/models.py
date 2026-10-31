"""Typed contracts shared by the sequential deletion-audit agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Phase = Literal["FINDING", "REMEDIATION", "VERIFICATION"]
DeletionStatus = Literal["COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]


@dataclass(frozen=True)
class DeletionRequest:
    case_id: str
    email: str
    requested_at: datetime
    reported_status: str
    reported_at: datetime
    audit_at: datetime
    request_text: str


@dataclass(frozen=True)
class Identity:
    user_id: str
    identifiers: dict[str, set[str]]
    provenance: dict[str, list[str]]
    confident: bool = True


@dataclass(frozen=True)
class EvidenceFile:
    file_id: str
    relative_path: str
    captured_at: datetime
    origin: str


@dataclass
class Observation:
    """A normalized statement made by participant-visible evidence."""

    system_id: str
    resource_id: str
    category: str
    observed_at: datetime
    evidence_id: str
    present: bool | None = None
    pii_exposed: bool | None = None
    active: bool | None = None
    restore_allowed: bool | None = None
    identifiers: set[str] = field(default_factory=set)
    subject_refs: set[str] = field(default_factory=set)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyFinding:
    system_id: str
    resource_id: str
    category: str
    finding_operation: str
    state: str
    evidence_id: str
    required_action: str


@dataclass(frozen=True)
class AuthorizationResult:
    authorized: bool
    confidence: float
    rationale: str


class GeminiAuthorizationResponse(BaseModel):
    """The only model response shape used by the authorization fallback."""

    authorized: bool
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(max_length=600)


class OutputStep(BaseModel):
    step_no: int = Field(ge=1)
    phase: Phase
    system_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    operation: str
    state: str
    evidence_id: str


@dataclass
class CaseResult:
    case_id: str
    status: DeletionStatus
    steps: list[OutputStep]
    diagnostics: list[str] = field(default_factory=list)

