from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .common import Attention, CaseState, DataCategory, TzModel


class EmergencyCreate(TzModel):
    astronaut_id: str = Field(examples=["DEMO-001"])
    responder_id: str = Field(examples=["DEMO-002"])
    trigger: Literal["crew_collapse", "chest_pain_reported", "manual_activation"]


class CrewAlert(BaseModel):
    status: Literal["simulated_alert_raised"]
    message: str


class FlightSurgeonEscalation(BaseModel):
    status: Literal["queued_for_transmission"]
    note: str
    message_id: Optional[str] = Field(default=None, description="The urgent to_ground message in the "
                                      "communications queue (2.10.0). Track it with GET /comms/messages/{id}.")


class EmergencyInformation(BaseModel):
    reviewed_procedure_available: bool
    limitation: str
    crew_actions: list[str] = Field(description="Escalation and coordination actions only. No treatment steps.")


class EquipmentAssistance(BaseModel):
    available: bool
    required_to_start_response: Literal[False] = False
    endpoint: str
    suggested_capabilities: list[str]
    note: str


class EmergencyOut(BaseModel):
    emergency_id: str
    case_id: str
    case_state: CaseState
    priority: Literal["urgent"]
    attention: Attention
    astronaut_id: str
    responder_id: str
    trigger: str
    activated_at: datetime
    duplicate: bool = Field(description="True when an emergency for this astronaut was already active (<10 min).")
    localisation_required: Literal[False] = False
    crew_alert: CrewAlert
    flight_surgeon_escalation: FlightSurgeonEscalation
    emergency_information: EmergencyInformation
    equipment_assistance: EquipmentAssistance
    next_action: str
    data_category: DataCategory = "SIMULATED_ASTRONAUT"
    disclaimer: str = "Simulated emergency workflow in a research prototype. Not a medical device."
