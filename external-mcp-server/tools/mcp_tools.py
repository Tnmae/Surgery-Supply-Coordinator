import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from pydantic import TypeAdapter

from repository.database_repo import MedicalRepository
from models.schemas import (
    BloodUnit, OrganRegistry, Medicine, DrugInteraction, 
    EquipmentItem, HospitalBase, Supplier, LogisticsVehicle
)

logger = logging.getLogger("mcp-tools")

# Initialize FastMCP
mcp = FastMCP("Critical-Medical-Resources")

# Initialize Repository
repo = MedicalRepository()

# ==========================================
# MCP TOOLS DEFINITIONS
# ==========================================

@mcp.tool()
def search_blood_inventory(blood_type: str, hospital_id: Optional[str] = None) -> list:
    """
    Search the real-time blood bank inventory by ABO blood type and optionally hospital.
    
    Args:
        blood_type: The required blood type (e.g. O+, O-, A+, A-, B+, B-, AB+, AB-)
        hospital_id: Optional hospital identifier (e.g. HOSP001) to filter results
    """
    logger.info(f"Querying blood inventory for type: {blood_type}, hospital_id: {hospital_id}")
    raw_units = repo.get_blood_inventory(blood_type, hospital_id)
    
    # Validate with Pydantic
    adapter = TypeAdapter(List[BloodUnit])
    units = adapter.validate_python(raw_units)
    
    return [unit.model_dump() for unit in units]


@mcp.tool()
def search_organ_registry(organ_type: str, hospital_id: Optional[str] = None) -> list:
    """
    Search active organ registries by organ type and optionally hospital.
    
    Args:
        organ_type: Type of organ (e.g. HEART, LIVER, KIDNEY, PANCREAS, LUNG, CORNEA)
        hospital_id: Optional hospital identifier (e.g. HOSP001) to filter results
    """
    logger.info(f"Querying organ registry for type: {organ_type}, hospital_id: {hospital_id}")
    raw_organs = repo.get_organs(organ_type, hospital_id)
    
    adapter = TypeAdapter(List[OrganRegistry])
    organs = adapter.validate_python(raw_organs)
    
    return [organ.model_dump() for organ in organs]


@mcp.tool()
def search_medicine(query: str) -> list:
    """
    Search the medicine catalogue by generic name, brand name, or drug class.
    
    Args:
        query: Generic or brand name of the drug (e.g. Warfarin, Aspirin, Plavix, Metformin)
    """
    logger.info(f"Searching medicine catalog with query: {query}")
    raw_meds = repo.get_medicines(query)
    
    adapter = TypeAdapter(List[Medicine])
    medicines = adapter.validate_python(raw_meds)
    
    return [med.model_dump() for med in medicines]


@mcp.tool()
def check_drug_interactions(medications: List[str]) -> dict:
    """
    Validate pairwise drug-drug interactions for a patient's medication list.
    
    Args:
        medications: List of generic drug names (e.g. ['WARFARIN', 'ASPIRIN'])
    """
    logger.info(f"Checking drug interactions for medications: {medications}")
    interactions = []
    normalized_meds = [med.upper().strip() for med in medications]
    
    # Check pairwise combinations
    for i in range(len(normalized_meds)):
        for j in range(i + 1, len(normalized_meds)):
            med_a = normalized_meds[i]
            med_b = normalized_meds[j]
            match = repo.get_interactions(med_a, med_b)
            if match:
                interactions.append({
                    "drug_a": match["drug_a"],
                    "drug_b": match["drug_b"],
                    "severity": match["severity"],
                    "description": match["description"]
                })
                
    return {
        "medications_checked": medications,
        "interactions_found": len(interactions) > 0,
        "interactions": interactions
    }


@mcp.tool()
def search_equipment(name: Optional[str] = None, hospital_id: Optional[str] = None) -> list:
    """
    Search the surgical equipment inventory by name and optionally hospital.
    
    Args:
        name: Name of the equipment (e.g. VENTILATOR, BYPASS_MACHINE, ANESTHESIA_MACHINE)
        hospital_id: Optional hospital identifier (e.g. HOSP001) to filter results
    """
    logger.info(f"Querying equipment inventory for name: {name}, hospital_id: {hospital_id}")
    raw_equipment = repo.get_equipment(name, hospital_id)
    
    adapter = TypeAdapter(List[EquipmentItem])
    equipment = adapter.validate_python(raw_equipment)
    
    return [item.model_dump() for item in equipment]


@mcp.tool()
def search_hospital(query: str) -> list:
    """
    Search hospital network facilities by name or address.
    
    Args:
        query: Hospital name or location query
    """
    logger.info(f"Searching hospital network facilities with query: {query}")
    raw_hospitals = repo.get_hospitals(query)
    
    adapter = TypeAdapter(List[HospitalBase])
    hospitals = adapter.validate_python(raw_hospitals)
    
    return [h.model_dump() for h in hospitals]


@mcp.tool()
def search_supplier(query: str) -> list:
    """
    Search medical suppliers by name, supplied blood types, organs, or equipment.
    
    Args:
        query: Supplier search query (e.g. Blood, Organ, Ventilator, Alpha)
    """
    logger.info(f"Searching suppliers with query: {query}")
    raw_suppliers = repo.get_suppliers(query)
    
    adapter = TypeAdapter(List[Supplier])
    suppliers = adapter.validate_python(raw_suppliers)
    
    return [s.model_dump() for s in suppliers]


@mcp.tool()
def get_storage_requirements(resource_type: str, item_id: str) -> dict:
    """
    Retrieve clinical storage, temperature compliance, and packaging requirements for a resource.
    
    Args:
        resource_type: Type of resource ('BLOOD', 'ORGAN', or 'EQUIPMENT')
        item_id: Unique resource ID
    """
    logger.info(f"Querying storage requirements for resource_type: {resource_type}, item_id: {item_id}")
    reqs = repo.get_storage_requirements(resource_type, item_id)
    if not reqs:
        return {
            "success": False,
            "message": f"Storage requirements not found for {resource_type} item: {item_id}"
        }
    return reqs


@mcp.tool()
def check_resource_availability(resource_type: str, identifier: str) -> dict:
    """
    General endpoint to check if a resource unit is active and available.
    
    Args:
        resource_type: Type of resource ('BLOOD', 'ORGAN', or 'EQUIPMENT')
        identifier: Resource identifier (e.g. BLOOD-O-POS-01)
    """
    logger.info(f"Checking resource availability: {resource_type} -> {identifier}")
    status = "UNKNOWN"
    details = {}
    
    if resource_type.upper() == "BLOOD":
        all_units = repo.get_all_blood_units()
        unit = next((u for u in all_units if u['id'] == identifier), None)
        if unit:
            status = "AVAILABLE" if unit['status'] == "AVAILABLE" else "BLOCKED"
            details = unit
    elif resource_type.upper() == "ORGAN":
        all_organs = repo.get_all_organs()
        organ = next((o for o in all_organs if o['id'] == identifier), None)
        if organ:
            status = "AVAILABLE" if organ['status'] == "AVAILABLE" else "BLOCKED"
            details = organ
    elif resource_type.upper() == "EQUIPMENT":
        all_eq = repo.get_all_equipment()
        eq = next((e for e in all_eq if e['id'] == identifier), None)
        if eq:
            status = "AVAILABLE" if eq['status'] == "AVAILABLE" else "BLOCKED"
            details = eq
            
    return {
        "resource_type": resource_type,
        "identifier": identifier,
        "status": status,
        "details": details
    }


@mcp.tool()
def get_transport_information(source_hospital_id: str, destination_hospital_id: str) -> dict:
    """
    Calculate logistics constraints, transport methods, and ETA between two hospital facilities.
    
    Args:
        source_hospital_id: Starting hospital facility ID
        destination_hospital_id: Destination hospital facility ID
    """
    logger.info(f"Querying transport details between {source_hospital_id} and {destination_hospital_id}")
    
    # Retrieve hospital info
    hospitals = repo.get_hospitals()
    src = next((h for h in hospitals if h['id'] == source_hospital_id), None)
    dest = next((h for h in hospitals if h['id'] == destination_hospital_id), None)
    
    if not src or not dest:
        return {
            "success": False,
            "message": f"One or both hospitals not found: source={source_hospital_id}, dest={destination_hospital_id}"
        }
        
    # Check if we have an active travel route in our database log
    vehicles = repo.get_logistics_vehicles()
    active_route = next((
        v for v in vehicles 
        if v['base_hospital_id'] == source_hospital_id and v['destination_hospital_id'] == destination_hospital_id
    ), None)
    
    travel_time = 0
    vehicle_id = "N/A"
    vehicle_type = "GROUND_COURIER"
    has_blood_cooler = True
    has_organ_preservation = False
    
    if active_route:
        travel_time = active_route['estimated_travel_time_minutes']
        vehicle_id = active_route['id']
        vehicle_type = active_route['vehicle_type']
        has_blood_cooler = bool(active_route['has_blood_cooler'])
        has_organ_preservation = bool(active_route['has_organ_preservation'])
    else:
        # Fallback travel time calculation using mock distance estimation
        # Simply calculating distance based on lat/lng coordinates
        lat1, lon1 = src['latitude'], src['longitude']
        lat2, lon2 = dest['latitude'], dest['longitude']
        
        # Simple Euclidean approximation for speed
        dist = ((lat1 - lat2)**2 + (lon1 - lon2)**2)**0.5
        # Assume average velocity
        travel_time = int(max(15, dist * 100))
        
        # Select first available logistics ambulance/helicopter
        avail_vehicle = next((v for v in vehicles if v['status'] == 'AVAILABLE'), None)
        if avail_vehicle:
            vehicle_id = avail_vehicle['id']
            vehicle_type = avail_vehicle['vehicle_type']
            has_blood_cooler = bool(avail_vehicle['has_blood_cooler'])
            has_organ_preservation = bool(avail_vehicle['has_organ_preservation'])
            
    return {
        "success": True,
        "source": src['name'],
        "destination": dest['name'],
        "vehicle_id": vehicle_id,
        "vehicle_type": vehicle_type,
        "estimated_travel_time_minutes": travel_time,
        "has_blood_cooler": has_blood_cooler,
        "has_organ_preservation": has_organ_preservation,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
