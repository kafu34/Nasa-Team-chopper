"""Shared schema types."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..db import as_utc

DataCategory = Literal["NASA_RESEARCH", "SIMULATED_ASTRONAUT", "SIMULATED_ENVIRONMENT_OR_DEVICE"]
DatasetStatus = Literal["NOT_DOWNLOADED", "READY_TO_IMPORT", "IMPORTED", "IMPORT_FAILED", "UNSUPPORTED_FORMAT"]
# v2.2 scientific classification of a data source (what kind of evidence it is).
StudyType = Literal[
    "HUMAN_SPACEFLIGHT",        # measurements from humans who flew (samples may be collected on the ground pre/post flight)
    "HUMAN_GROUND_ANALOGUE",    # human volunteers in a ground analogue such as bed rest; nobody flew
    "HUMAN_DERIVED_CELLS",      # human cells or tissue (in flight or on ground), not a person
    "ANIMAL_RESEARCH",          # non-human organisms; never used for astronaut-specific findings
    "SPACEFLIGHT_ENVIRONMENT",  # spacecraft environment, telemetry, radiation or microbiome; not a body measurement
    "FICTIONAL_DEMONSTRATION",  # SENTINEL's fictional demo astronaut, habitat and device data
]
HumanHealthAnalysis = Literal["PRIMARY_HUMAN_RESEARCH", "SEPARATE_ANIMAL_RESEARCH", "ENVIRONMENT_CONTEXT"]
CaseState = Literal[
    "detected",
    "investigating",
    "awaiting_assessment",
    "awaiting_results",
    "action_required",
    "monitoring",
    "follow_up_due",
    "escalated",
    "resolved",
]
Priority = Literal["routine", "urgent"]
Laterality = Literal["left", "right", "bilateral", "midline", "not_applicable"]


class Strict(BaseModel):
    """Request models reject unknown fields so contract drift is caught early."""

    model_config = ConfigDict(extra="forbid")


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def require_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be ISO 8601 with a timezone offset, e.g. 2026-11-14T09:30:00Z")
    return as_utc(value)


class TzModel(Strict):
    @field_validator("*", mode="after")
    @classmethod
    def _tz(cls, v: Any):
        if isinstance(v, datetime):
            return require_tz(v)
        return v


class ErrorBody(BaseModel):
    code: str = Field(examples=["NOT_FOUND"])
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_responses(*codes: int) -> dict:
    desc = {
        404: "Resource not found",
        409: "Conflict with current workflow state",
        422: "Validation error",
        503: "Dataset unavailable",
    }
    return {c: {"model": ErrorResponse, "description": desc.get(c, "Error")} for c in codes}


class Attention(BaseModel):
    priority: Priority
    interrupt: bool = Field(description="True only for urgent items; routine items are noninterruptive.")
    reason: str
