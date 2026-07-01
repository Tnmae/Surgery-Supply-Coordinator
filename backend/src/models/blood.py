"""Blood bank domain models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class BloodType(str, Enum):
    """ABO blood types."""
    O_NEG = "O-"
    O_POS = "O+"
    A_NEG = "A-"
    A_POS = "A+"
    B_NEG = "B-"
    B_POS = "B+"
    AB_NEG = "AB-"
    AB_POS = "AB+"


class BloodUnitStatus(str, Enum):
    """Status of a blood unit."""
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    IN_USE = "IN_USE"
    EXPIRED = "EXPIRED"
    CONTAMINATED = "CONTAMINATED"
    PENDING_CROSSMATCH = "PENDING_CROSSMATCH"


class CrossmatchStatus(str, Enum):
    """Crossmatch test result."""
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    PENDING = "PENDING"
    NOT_PERFORMED = "NOT_PERFORMED"


class BloodUnit(BaseModel):
    """Individual blood unit record."""
    unit_id: str
    blood_type: BloodType
    collected_date: datetime
    expiration_date: datetime
    status: BloodUnitStatus
    crossmatch_status: CrossmatchStatus = CrossmatchStatus.NOT_PERFORMED
    unit_volume_ml: int = 450
    location: str = "Blood Bank"
    notes: Optional[str] = None


class BloodBankQuery(BaseModel):
    """Query for blood bank availability."""
    blood_type: BloodType
    units_needed: int
    patient_id: Optional[str] = None


class BloodBankResponse(BaseModel):
    """Response from blood bank query."""
    query_id: str
    blood_type: BloodType
    units_requested: int
    units_available: int
    available_units: list[BloodUnit] = Field(default_factory=list)
    units_pending_crossmatch: int = 0
    earliest_expiration: Optional[datetime] = None
    all_requirements_met: bool
    fallback_available: bool = False
    timestamp: datetime
