"""Patient domain models."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Allergy(BaseModel):
    """Patient allergy record."""
    allergen: str
    severity: str  # "MILD", "MODERATE", "SEVERE"
    reaction: str


class Contraindication(BaseModel):
    """Medical contraindication."""
    condition: str
    severity: str
    notes: Optional[str] = None


class Consent(BaseModel):
    """Consent record."""
    consent_type: str  # e.g., "SURGERY", "TRANSFUSION", "ORGAN_TRANSPLANT"
    given: bool
    date_given: Optional[datetime] = None
    expires: Optional[datetime] = None
    witness: Optional[str] = None
    notes: Optional[str] = None


class PatientData(BaseModel):
    """Extracted patient data for surgery."""
    patient_id: str
    date_of_birth: datetime
    blood_type: str
    allergies: List[Allergy] = Field(default_factory=list)
    contraindications: List[Contraindication] = Field(default_factory=list)
    consents: List[Consent] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    prior_surgeries: int = 0
    special_notes: Optional[str] = None


class PatientDataExtractionResult(BaseModel):
    """Result of patient data extraction."""
    patient_id: str
    extraction_successful: bool
    extracted_data: Optional[PatientData] = None
    missing_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    timestamp: datetime
