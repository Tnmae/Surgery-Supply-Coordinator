"""Readiness report models."""

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ReadinessStatus(str, Enum):
    """Final readiness status."""
    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"


class BlockerSeverity(str, Enum):
    """Severity level of a blocker."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Blocker(BaseModel):
    """A blocker preventing surgery readiness."""
    category: str  # e.g., "CONSENT", "BLOOD", "ORGAN", "EQUIPMENT"
    severity: BlockerSeverity
    message: str
    details: Optional[dict] = None
    suggested_action: Optional[str] = None


class ResourceStatus(BaseModel):
    """Status of a single resource check."""
    resource_type: str  # "BLOOD", "ORGAN", "EQUIPMENT"
    status: str  # "OK", "WARNING", "BLOCKED"
    details: str
    data: Optional[dict] = None


class PreopChecklist(BaseModel):
    """Pre-operative checklist."""
    items: List[dict] = Field(default_factory=list)  # list of {"item": "...", "completed": bool}


class ReadinessReport(BaseModel):
    """Complete readiness report for a surgery."""
    report_id: str
    surgery_id: str
    surgery_type: str
    patient_id: str
    scheduled_time: datetime
    status: ReadinessStatus
    
    # Resource checks
    blood_status: ResourceStatus
    organ_status: Optional[ResourceStatus] = None
    equipment_status: ResourceStatus
    safety_status: ResourceStatus
    
    # Blockers
    blockers: List[Blocker] = Field(default_factory=list)
    
    # Pre-op checklist
    preop_checklist: PreopChecklist = Field(default_factory=PreopChecklist)
    
    # Metadata
    generated_at: datetime
    generated_by_agent: str
    audit_trail_id: str
    
    # Required disclaimer
    disclaimer: str = (
        "This system is for decision-support only. It does not authorize surgery, "
        "transfusion, organ allocation, or any medical procedure. All outputs must be "
        "reviewed and approved by qualified clinical personnel."
    )


class ReadinessCheckRequest(BaseModel):
    """Request to check surgery readiness."""
    surgery_id: str
    user_role: str  # e.g., "OR_COORDINATOR", "SUPPLY_ADMIN"
    requested_at: datetime = Field(default_factory=datetime.utcnow)


class ReadinessCheckResponse(BaseModel):
    """Response to readiness check."""
    success: bool
    message: str
    report: Optional[ReadinessReport] = None
    errors: List[str] = Field(default_factory=list)


class BlockerDecisionRequest(BaseModel):
    """A clinician's accept/reject decision on a single reported blocker."""
    category: str
    message: str
    severity: Optional[str] = None
    suggested_action: Optional[str] = None
    decision: Literal["ACCEPT", "REJECT"]
    notes: Optional[str] = None
