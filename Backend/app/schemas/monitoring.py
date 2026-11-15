"""Proactive health intelligence (contract 2.6.0): baselines, detection results, monitoring concerns."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import Attention, CaseState, Priority, Strict

DetectionGate = Literal["passed", "excluded_poor_quality", "excluded_stale"]
DetectionOutcome = Literal["excluded_poor_quality", "excluded_stale", "not_monitored", "no_baseline",
                           "within_baseline", "deviation_not_sustained", "concern_opened", "concern_updated",
                           "within_baseline_concern_open", "reassessment_completed", "concern_ready_for_review"]
ConcernStatus = Literal["open", "awaiting_review", "closed"]
DISCLAIMER = ("Configured demonstration rule. A deviation from a synthetic individual baseline is not a diagnosis.")


class DetectionResult(BaseModel):
    """What DET-1.0 did with one reading, stored with the observation at ingestion."""
    ruleset_version: str
    rule_id: Optional[str]
    gate: DetectionGate = Field(description="Data-quality gate. Only `passed` readings are compared with a baseline.")
    outcome: DetectionOutcome
    baseline_id: Optional[str]
    baseline_version: Optional[int]
    baseline_centre: Optional[float]
    baseline_spread: Optional[float]
    threshold: Optional[float] = Field(description="Absolute difference from the centre that counts as a deviation.")
    difference: Optional[float] = Field(description="Reading minus baseline centre, in the reading's unit.")
    deviation_direction: Optional[Literal["above", "below"]]
    deviating_count: int
    required_count: Optional[int]
    concern_id: Optional[str]
    case_id: Optional[str]
    alert_raised: bool
    alert_suppressed: bool
    explanation: str
    disclaimer: str
    evaluated_at: datetime


class BaselineOut(BaseModel):
    baseline_id: str
    astronaut_id: str
    type: str
    unit: str
    version: int
    status: Literal["active", "superseded"]
    method_id: str
    centre: float
    spread: float
    sample_count: int
    excluded_count: int = Field(description="Readings left out because they were observed while a monitoring "
                                            "concern was open.")
    window_start: datetime
    window_end: datetime
    source_observation_ids: list[str]
    created_at: datetime
    created_by: str
    reason: str
    superseded_at: Optional[datetime]
    frozen: bool = Field(description="True while a monitoring concern for this type is not closed; recompute is "
                                     "refused.")
    frozen_by_concern_id: Optional[str]
    data_category: Literal["SIMULATED_ASTRONAUT"] = "SIMULATED_ASTRONAUT"


class BaselineList(BaseModel):
    astronaut_id: str
    method_id: str
    method_description: str
    baselines: list[BaselineOut]


class BaselineRecompute(Strict):
    actor_id: str = Field(examples=["DEMO-002"])
    reason: str = Field(min_length=3, max_length=500, examples=["Two weeks of new routine readings"])


class ReassessmentOut(BaseModel):
    follow_up_id: str
    status: str
    due_at: datetime
    completed_at: Optional[datetime]
    completion_evidence_id: Optional[str]


class ConcernOut(BaseModel):
    concern_id: str
    annotation_kind: Literal["monitoring_concern"] = "monitoring_concern"
    astronaut_id: str
    type: str
    unit: str
    rule_id: str
    rule_title: Optional[str]
    ruleset_version: str
    baseline_id: str
    baseline_version: int
    baseline_frozen: bool
    direction: Literal["above", "below"]
    status: ConcernStatus
    case_id: str
    opened_at: datetime
    first_evidence_at: datetime
    last_triggered_at: datetime
    trigger_count: int
    suppressed_count: int = Field(description="Equivalent triggers that did not raise a new alert.")
    evidence_observation_ids: list[str]
    consecutive_within_baseline: int
    recovery_count: Optional[int]
    reassessment_passed: bool
    reassessment: Optional[ReassessmentOut]
    closed_at: Optional[datetime]
    closed_by: Optional[str]
    review_note: Optional[str]
    automatic_resolution: Literal[False] = False
    disclaimer: str = DISCLAIMER


class ConcernReview(Strict):
    actor_id: str = Field(examples=["DEMO-002"])
    decision: Literal["continue_monitoring", "close"]
    note: str = Field(min_length=3, max_length=1000)


class TrendOut(BaseModel):
    readings: int
    window_minutes: int
    slope_per_hour: Optional[float]
    description: Literal["insufficient_readings", "stable", "rising", "falling"]
    note: str = "Descriptive only. No rule acts on the trend."


class DataQualityItem(BaseModel):
    type: str
    issue: Literal["missing", "stale", "recent_poor_quality", "baseline_insufficient",
                   "baseline_not_created"]
    note: str


class TypeMonitoring(BaseModel):
    type: str
    unit: str
    freshness: Literal["current", "stale", "missing"]
    rule_id: Optional[str]
    baseline: Optional[BaselineOut]
    latest_value: Optional[float]
    latest_observed_at: Optional[datetime]
    latest_quality: Optional[str]
    difference_from_baseline: Optional[float]
    latest_detection: Optional[DetectionResult]
    trend: TrendOut
    open_concern_id: Optional[str]


class MonitoringOut(BaseModel):
    astronaut_id: str
    ruleset_version: str
    baseline_method_id: str
    generated_at: datetime
    types: list[TypeMonitoring]
    concerns: list[ConcernOut]
    data_quality: list[DataQualityItem] = Field(description="Data problems. They never open a case or a concern.")
    disclaimer: str = DISCLAIMER


class DetectionRuleOut(BaseModel):
    rule_id: str
    type: str
    title: str
    direction: Literal["above", "below", "either"]
    k_spread: float
    min_abs_change: float
    window_minutes: int
    required_consecutive: int
    assessment_procedure_id: Optional[str]
    reassessment_minutes: int
    recovery_count: int
    suppression_minutes: int


class DetectionRulesetOut(BaseModel):
    ruleset_version: str
    baseline_method_id: str
    disclaimer: str
    rules: list[DetectionRuleOut]


class PriorityProtection(BaseModel):
    urgent_since: Optional[datetime]
    reason: Optional[str]
    urgent_instruction: Optional[str]
    automatic_downgrade_allowed: Literal[False] = False
    note: str = ("Urgent priority is never lowered automatically, including when a routine assessment or follow-up "
                 "finishes.")


class UrgentEvent(BaseModel):
    case_id: str
    kind: Literal["routine", "emergency"]
    state: CaseState
    priority: Priority
    attention: Attention
    urgent_since: Optional[datetime]
    reason: Optional[str]
    next_action: str
