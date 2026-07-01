"""Mock MCP server for organ registry operations."""

from datetime import datetime, timedelta
from typing import List, Optional
from src.data.repository import DataRepository
from src.models.organ import OrganRegistryQuery, OrganRegistryResponse


class OrganRegistryMCPServer:
    """Mock MCP server for organ registry queries."""
    
    def __init__(self, repository: DataRepository = None, fallback: "RegionalFallbackMCPServer" = None):
        """Initialize the organ registry server."""
        self.repository = repository or DataRepository()
        self.fallback = fallback
    
    def query_organ_availability(self, query: OrganRegistryQuery) -> OrganRegistryResponse:
        """
        Query organ availability and compatibility.
        
        Returns:
            OrganRegistryResponse with matching organs and compatibility info.
        """
        # Get patient data
        patient = self.repository.get_patient(query.recipient_patient_id)
        if not patient:
            return OrganRegistryResponse(
                query_id=f"ORQ-{datetime.utcnow().timestamp()}",
                organ_type=query.organ_type,
                available=False,
                matching_organs=[],
                timestamp=datetime.utcnow()
            )
        
        # Get available organs of requested type
        available_organs = self.repository.get_available_organs(query.organ_type.value)
        
        best_match = None
        viability_risk = "LOW"
        
        for organ in available_organs:
            # Check viability window
            cold_start = datetime.fromisoformat(organ['cold_storage_started'].replace('Z', '+00:00'))
            now = datetime.utcnow()
            cold_time = (now - cold_start).total_seconds() / 60
            viability_remaining = organ['viability_window_minutes'] - cold_time
            
            # Check for viability risk (less than 60 minutes remaining)
            if viability_remaining < 60:
                viability_risk = "HIGH"
            elif viability_remaining < 180:
                viability_risk = "MEDIUM"
            
            # Simple compatibility check (blood type)
            if best_match is None or organ['donor_age'] < best_match['donor_age']:
                best_match = organ
        
        # Check if fallback can help
        fallback_available = False
        if not best_match and self.fallback:
            fallback_available = self.fallback.has_organ(query.organ_type.value)
        
        response = OrganRegistryResponse(
            query_id=f"ORQ-{datetime.utcnow().timestamp()}",
            organ_type=query.organ_type,
            available=best_match is not None,
            matching_organs=available_organs,
            best_match=best_match,
            time_to_procurement_hours=None,
            viability_risk_level=viability_risk,
            timestamp=datetime.utcnow()
        )
        
        return response
    
    def get_organs(self, organ_type: str, count: int = None) -> List[dict]:
        """
        Get available organs of a specific type.
        
        Returns:
            List of available organs.
        """
        organs = self.repository.get_available_organs(organ_type)
        if count:
            return organs[:count]
        return organs
    
    def check_donor_compatibility(self, organ_id: str, patient_id: str) -> dict:
        """
        Check donor-recipient compatibility.
        
        Returns:
            Compatibility information.
        """
        organ = None
        for o in self.repository.get_all_organs():
            if o['organ_id'] == organ_id:
                organ = o
                break
        
        patient = self.repository.get_patient(patient_id)
        
        if not organ or not patient:
            return {"success": False, "message": "Organ or patient not found"}
        
        # Simple blood type matching
        blood_type_match = organ['donor_blood_type'] == patient['blood_type']
        
        return {
            "success": True,
            "organ_id": organ_id,
            "patient_id": patient_id,
            "compatible": blood_type_match,
            "blood_type_match": blood_type_match,
            "tissue_type_match": True,  # Mock - assume compatible
            "size_compatible": True,  # Mock - assume compatible
            "crossmatch_result": "COMPATIBLE" if blood_type_match else "INCOMPATIBLE",
            "notes": "Basic compatibility check performed"
        }
    
    def get_viability_estimate(self, organ_id: str) -> dict:
        """
        Get viability time estimate for an organ.
        
        Returns:
            Viability information.
        """
        organ = None
        for o in self.repository.get_all_organs():
            if o['organ_id'] == organ_id:
                organ = o
                break
        
        if not organ:
            return {"success": False, "message": "Organ not found"}
        
        cold_start = datetime.fromisoformat(organ['cold_storage_started'].replace('Z', '+00:00'))
        now = datetime.utcnow()
        cold_time_minutes = (now - cold_start).total_seconds() / 60
        viability_remaining = organ['viability_window_minutes'] - cold_time_minutes
        
        risk_level = "LOW"
        if viability_remaining < 60:
            risk_level = "HIGH"
        elif viability_remaining < 180:
            risk_level = "MEDIUM"
        
        return {
            "success": True,
            "organ_id": organ_id,
            "total_viability_window_minutes": organ['viability_window_minutes'],
            "cold_storage_time_elapsed_minutes": cold_time_minutes,
            "viability_remaining_minutes": max(0, viability_remaining),
            "risk_level": risk_level,
            "timestamp": datetime.utcnow().isoformat()
        }
