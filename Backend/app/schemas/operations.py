"""Operational capability schemas (contracts 2.9.0 and 2.10.0): screening, access, communications, recovery."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import Strict
from .demo import ScheduledAssessmentOut
from .procedures import SessionOut

class CommsSend(Strict):
    sender_id: str = Field(examples=["DEMO-002"])
    direction: Literal["to_ground", "to_crew"]
    priority: Literal["urgent", "routine"] = "routine"
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    case_id: Optional[str] = None
    client_message_id: Optional[str] = Field(default=None, max_length=100, description="Resending with the same "
                                             "value returns the first message (duplicate=true).")


class CommsMessageOut(BaseModel):
    model_config = {"from_attributes": True}
    message_id: str
    client_message_id: Optional[str]
    direction: Literal["to_ground", "to_crew"]
    priority: Literal["urgent", "routine"]
    sender_id: str
    sender_role: str
    recipient_role: str
    case_id: Optional[str]
    subject: str
    body: str
    status: Literal["queued", "in_transit", "delivered", "acknowledged"]
    created_at: datetime
    transmit_at: Optional[datetime]
    deliver_at: Optional[datetime] = Field(description="Expected or actual arrival time.")
    delivered_at: Optional[datetime]
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[str]
    duplicate: bool = False
    simulated: Literal[True] = True


class CommsList(BaseModel):
    messages: list[CommsMessageOut] = Field(description="Urgent first, then oldest first.")
    link_state: Literal["up", "down"]
    one_way_delay_seconds: int
    note: str


class CommsAck(Strict):
    actor_id: str = Field(examples=["GND-FS-01"])


class LinkChange(Strict):
    state: Literal["up", "down"]
    actor_id: str = Field(examples=["DEMO-002"])
    reason: str = Field(min_length=3, max_length=500)


class LinkOut(BaseModel):
    model_config = {"from_attributes": True}
    link_id: str
    state: Literal["up", "down"]
    changed_at: datetime
    changed_by: str
    reason: str
    outage_count: int
    one_way_delay_seconds: int = 300
    transmit_seconds: int = 5
    simulated: Literal[True] = True


class RadiationReading(BaseModel):
    instrument_id: str
    instrument_family: Optional[str]
    spacecraft: Optional[str]
    module: Optional[str]
    metric: str
    value: float
    value_raw: str
    unit: str
    timestamp: datetime
    source_file: str
    source_row_number: int


class RadiationContext(BaseModel):
    dataset_id: str
    status: str
    title: str
    source_url: Optional[str]
    location: str
    is_habitat_reading: Literal[False]
    is_personal_dose: Literal[False]
    latest_readings: list[RadiationReading]
    limitations: list[str]


class AtmosphereContext(BaseModel):
    dataset_id: str
    status: str
    note: str


class EnvironmentContext(BaseModel):
    astronaut_id: Optional[str]
    radiation: RadiationContext
    atmosphere: AtmosphereContext
    health_relationship: Literal["none_inferred"]
    caution: str
    data_category: Literal["NASA_RESEARCH"]


class RecoveryOut(BaseModel):
    server_time: datetime
    contract_version: str
    astronaut_id: str
    open_session_ids: list[str]
    open_concern_ids: list[str]
    open_case_ids: list[str]
    open_reminder_ids: list[str]
    undelivered_message_ids: list[str] = Field(description="queued or in_transit")
    unacknowledged_message_ids: list[str] = Field(description="delivered, waiting for acknowledgement")
    link_state: Literal["up", "down"]
    loss_of_server_behaviour: list[str]


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
