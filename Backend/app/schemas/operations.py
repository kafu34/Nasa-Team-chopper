"""Operational capability schemas (contracts 2.9.0 and 2.10.0): screening, access, communications, recovery."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import Strict
from .demo import ScheduledAssessmentOut
from .procedures import SessionOut

RoleCode = Literal["crew_member", "crew_medical_officer", "flight_surgeon", "ground_support"]


class AssessmentList(BaseModel):
    astronaut_id: str
    assessments: list[ScheduledAssessmentOut]
    note: str = "Fictional demonstration schedule. Not a clinical recommendation."


class ReminderOut(BaseModel):
    model_config = {"from_attributes": True}
    reminder_id: str
    assessment_id: str
    astronaut_id: str
    kind: Literal["due", "overdue"]
    status: Literal["open", "acknowledged", "closed_by_completion"]
    created_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    closed_at: Optional[datetime]
    note: str = "Acknowledging a reminder does not complete the assessment."


class ReminderList(BaseModel):
    astronaut_id: str
    reminders: list[ReminderOut]


class ReminderAck(Strict):
    actor_id: str = Field(examples=["DEMO-001"])


class AssessmentStart(Strict):
    actor_id: str = Field(examples=["DEMO-001"])
    mode: Literal["self", "responder"] = "self"
    equipment_id: Optional[str] = Field(default=None, examples=["EQ-PO-01"])


class AssessmentStartOut(BaseModel):
    assessment: ScheduledAssessmentOut
    case_id: str
    case_state: str
    session: SessionOut
    session_created: bool


class PermissionOut(BaseModel):
    action: str
    allowed_roles: list[RoleCode]
    own_record_allowed: bool = Field(description="A crew_member may perform it on their own record.")
    description: str


class PersonOut(BaseModel):
    person_id: str
    display_name: str
    role_code: RoleCode
    location: str
    kind: Literal["crew", "ground"]


class AccessMatrixOut(BaseModel):
    role_codes: list[RoleCode]
    permissions: list[PermissionOut]
    personnel: list[PersonOut]
    limitation: str
