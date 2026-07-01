"""Organ registry domain models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class OrganType(str, Enum):
    """Types of transplantable organs."""
    HEART = "HEART"
    LIVER = "LIVER"
    KIDNEY = "KIDNEY"
    PANCREAS = "PANCREAS"
    LUNG = "LUNG"
    CORNEA = "CORNEA"


class OrganStatus(str, Enum):
    """Status of an organ."""
    AVAILABLE = "AVAILABLE"
    ALLOCATED = "ALLOCATED"
    IN_TRANSIT = "IN_TRANSIT"
    IN_USE = "IN_USE"
    NOT_VIABLE = "NOT_VIABLE"


class DonorCompatibility(BaseModel):
    """Donor-recipient compatibility check."""
    compatible: bool
    blood_type_match: bool
    tissue_type_match: Optional[bool] = None
    size_compatible: bool
    crossmatch_result: Optional[str] = None
    notes: Optional[str] = None


class OrganUnit(BaseModel):
    """Individual organ record."""
    organ_id: str
    organ_type: OrganType
    donor_id: str
    procurement_time: datetime
    viability_window_minutes: int
    status: OrganStatus
    current_location: str
    cold_storage_started: datetime
    expected_arrival_at_recipient: Optional[datetime] = None
    donor_blood_type: str
    donor_age: int
    notes: Optional[str] = None


class OrganRegistryQuery(BaseModel):
    """Query for organ availability."""
    organ_type: OrganType
    recipient_patient_id: str
    urgency_level: str = "STANDARD"  # "URGENT", "STANDARD", "ELECTIVE"


class OrganRegistryResponse(BaseModel):
    """Response from organ registry query."""
    query_id: str
    organ_type: OrganType
    available: bool
    matching_organs: list[OrganUnit] = Field(default_factory=list)
    best_match: Optional[OrganUnit] = None
    donor_compatibility: Optional[DonorCompatibility] = None
    time_to_procurement_hours: Optional[float] = None
    viability_risk_level: str = "LOW"  # "LOW", "MEDIUM", "HIGH"
    timestamp: datetime
