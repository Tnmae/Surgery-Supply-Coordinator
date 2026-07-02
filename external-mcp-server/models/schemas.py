from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class HospitalBase(BaseModel):
    id: str
    name: str
    state: str
    address: Optional[str] = None
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class BloodUnit(BaseModel):
    id: str
    blood_type: str
    unit_volume_ml: int
    status: str
    crossmatch_status: str
    collected_date: str
    expiration_date: str
    hospital_id: str

class OrganRegistry(BaseModel):
    id: str
    organ_type: str
    donor_id: str
    donor_blood_type: str
    donor_age: int
    procurement_time: str
    viability_window_minutes: int
    cold_storage_started: str
    status: str
    hospital_id: str

class Medicine(BaseModel):
    id: int
    generic_name: str
    brand_names: str
    drug_class: str
    indication: Optional[str] = None
    surgical_precautions: str
    holding_period_days: float
    reverse_agent: Optional[str] = None

class DrugInteraction(BaseModel):
    id: int
    drug_a: str
    drug_b: str
    severity: str
    description: str

class EquipmentItem(BaseModel):
    id: str
    name: str
    equipment_type: str
    status: str
    sterilization_status: str
    last_maintenance_date: str
    next_maintenance_due: str
    serial_number: str
    hospital_id: str

class Supplier(BaseModel):
    id: str
    name: str
    contact_info: str
    blood_types_supplied: Optional[str] = None
    organs_supplied: Optional[str] = None
    equipment_supplied: Optional[str] = None
    lead_time_hours: int

class LogisticsVehicle(BaseModel):
    id: str
    vehicle_type: str
    status: str
    base_hospital_id: Optional[str] = None
    destination_hospital_id: Optional[str] = None
    estimated_travel_time_minutes: Optional[int] = None
    has_organ_preservation: bool
    has_blood_cooler: bool
