"""Surgery domain models."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SurgeryStatus(str, Enum):
    """Surgery status enumeration."""
    PENDING = "PENDING"
    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SurgeryType(str, Enum):
    """Types of surgeries."""
    ORGAN_TRANSPLANT = "ORGAN_TRANSPLANT"
    CARDIAC = "CARDIAC"
    TRAUMA = "TRAUMA"
    ONCOLOGY = "ONCOLOGY"
    GENERAL = "GENERAL"


class SurgeryRequest(BaseModel):
    """Incoming surgery request from OR coordinator."""
    surgery_id: str
    patient_id: str
    surgery_type: SurgeryType
    scheduled_time: datetime
    required_blood_type: str
    required_blood_units: int
    organ_type: Optional[str] = None  # e.g., "HEART", "LIVER"
    equipment_list: List[str] = Field(default_factory=list)
    special_requirements: Optional[str] = None
    estimated_duration_minutes: int


class Surgery(SurgeryRequest):
    """Surgery record with additional metadata."""
    created_at: datetime
    status: SurgeryStatus = SurgeryStatus.PENDING
    created_by_role: str  # e.g., "OR_COORDINATOR"
    notes: Optional[str] = None


class SurgeryDetail(Surgery):
    """Extended surgery detail for API responses."""
    last_updated: datetime
    readiness_report: Optional[dict] = None
    readiness_review_status: Optional[str] = None
    blocker_decisions: List[dict] = Field(default_factory=list)
    readiness_reviewed_at: Optional[datetime] = None
    reviewed_by_role: Optional[str] = None
    audit_trail: List[dict] = Field(default_factory=list)
