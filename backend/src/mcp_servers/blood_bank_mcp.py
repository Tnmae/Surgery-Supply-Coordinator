"""Mock MCP server for blood bank operations."""

from datetime import datetime
from typing import List, Optional
from src.data.repository import DataRepository
from src.models.blood import BloodBankQuery, BloodBankResponse, BloodUnitStatus, CrossmatchStatus


class BloodBankMCPServer:
    """Mock MCP server for blood bank queries."""
    
    def __init__(self, repository: DataRepository = None, fallback: "RegionalFallbackMCPServer" = None):
        """Initialize the blood bank server."""
        self.repository = repository or DataRepository()
        self.fallback = fallback
    
    def query_blood_availability(self, query: BloodBankQuery) -> BloodBankResponse:
        """
        Query blood unit availability.
        
        Returns:
            BloodBankResponse with available units and status.
        """
        # Get available units from local inventory
        local_units = self.repository.get_available_blood_units(query.blood_type)
        
        # Filter by status and validity
        valid_units = [u for u in local_units if u['status'] in ['AVAILABLE', 'PENDING_CROSSMATCH']]
        
        # Count non-expired units
        available_count = 0
        earliest_exp = None
        
        for unit in valid_units:
            exp_date = datetime.fromisoformat(unit['expiration_date'].replace('Z', '+00:00'))
            if unit['status'] == 'AVAILABLE':
                available_count += 1
            if earliest_exp is None or exp_date < earliest_exp:
                earliest_exp = exp_date
        
        # Check if all requirements are met
        all_met = available_count >= query.units_needed
        
        # If not all available locally, check if fallback can help
        fallback_available = False
        if not all_met and self.fallback:
            fallback_available = self.fallback.has_blood(query.blood_type, query.units_needed - available_count)
        
        response = BloodBankResponse(
            query_id=f"BBQ-{datetime.utcnow().timestamp()}",
            blood_type=query.blood_type,
            units_requested=query.units_needed,
            units_available=available_count,
            available_units=valid_units[:query.units_needed],  # Return only what's needed
            units_pending_crossmatch=sum(1 for u in valid_units if u['status'] == 'PENDING_CROSSMATCH'),
            earliest_expiration=earliest_exp,
            all_requirements_met=all_met,
            fallback_available=fallback_available,
            timestamp=datetime.utcnow()
        )
        
        return response
    
    def get_blood_units(self, blood_type: str, count: int = None) -> List[dict]:
        """
        Get available blood units of a specific type.
        
        Returns:
            List of available blood units.
        """
        units = self.repository.get_available_blood_units(blood_type)
        if count:
            return units[:count]
        return units
    
    def check_crossmatch(self, unit_id: str, patient_id: str) -> dict:
        """
        Simulate checking crossmatch status for a blood unit and patient.
        
        Returns:
            Status of crossmatch check.
        """
        all_units = self.repository.get_all_blood_units()
        unit = next((u for u in all_units if u['unit_id'] == unit_id), None)
        
        if not unit:
            return {"success": False, "message": "Unit not found"}
        
        # Simulate crossmatch logic based on patient ID
        if patient_id == "PAT007":  # Crossmatch pending scenario
            return {
                "success": True,
                "unit_id": unit_id,
                "patient_id": patient_id,
                "status": "PENDING",
                "message": "Crossmatch test in progress"
            }
        
        # Default to compatible
        return {
            "success": True,
            "unit_id": unit_id,
            "patient_id": patient_id,
            "status": "COMPATIBLE",
            "message": "Crossmatch compatible"
        }
