"""Equipment inventory domain models."""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class EquipmentStatus(str, Enum):
    """Status of equipment."""
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    IN_USE = "IN_USE"
    MAINTENANCE = "MAINTENANCE"
    BROKEN = "BROKEN"
    RETIRED = "RETIRED"


class SterilizationStatus(str, Enum):
    """Sterilization status."""
    STERILE = "STERILE"
    NEEDS_STERILIZATION = "NEEDS_STERILIZATION"
    NOT_STERILE = "NOT_STERILE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Equipment(BaseModel):
    """Equipment item."""
    equipment_id: str
    name: str
    equipment_type: str  # e.g., "VENTILATOR", "MONITOR", "PUMP"
    location: str
    status: EquipmentStatus
    sterilization_status: SterilizationStatus
    last_maintenance_date: datetime
    next_maintenance_due: datetime
    serial_number: str
    purchase_date: datetime
    notes: Optional[str] = None


class MaintenanceRecord(BaseModel):
    """Maintenance history for equipment."""
    record_id: str
    equipment_id: str
    maintenance_date: datetime
    maintenance_type: str  # "ROUTINE", "REPAIR", "CALIBRATION"
    performed_by: str
    notes: Optional[str] = None
    next_due_date: datetime


class EquipmentQuery(BaseModel):
    """Query for equipment availability."""
    equipment_names: List[str]
    sterile_required: bool = True
    maintenance_critical: bool = False


class EquipmentQueryResponse(BaseModel):
    """Response from equipment query."""
    query_id: str
    requested_equipment: List[str]
    available_equipment: list[Equipment] = Field(default_factory=list)
    unavailable_equipment: List[str] = Field(default_factory=list)
    all_available: bool
    maintenance_concerns: List[str] = Field(default_factory=list)
    timestamp: datetime
