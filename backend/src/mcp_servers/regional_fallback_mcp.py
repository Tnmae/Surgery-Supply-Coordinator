"""Mock MCP server for regional/external fallback inventory."""

from datetime import datetime
from typing import List, Optional


class RegionalFallbackMCPServer:
    """Mock MCP server for regional/external inventory fallback."""
    
    def __init__(self):
        """Initialize the regional fallback server."""
        # Mock external inventory
        self.regional_blood = {
            "O+": 10,
            "O-": 8,
            "A+": 5,
            "A-": 3,
            "B+": 4,
            "B-": 2,
            "AB+": 2,
            "AB-": 1
        }
        
        self.regional_organs = {
            "HEART": 1,
            "LIVER": 2,
            "KIDNEY": 5,
            "PANCREAS": 1,
            "LUNG": 1,
            "CORNEA": 3
        }
    
    def query_blood_availability(self, blood_type: str, units_needed: int) -> dict:
        """
        Query regional blood availability.
        
        Args:
            blood_type: Blood type to query
            units_needed: Number of units needed
        
        Returns:
            Regional blood availability information.
        """
        available = self.regional_blood.get(blood_type, 0)
        can_fulfill = available >= units_needed
        
        return {
            "query_id": f"RFB-BLOOD-{datetime.utcnow().timestamp()}",
            "blood_type": blood_type,
            "units_available": available,
            "units_needed": units_needed,
            "can_fulfill": can_fulfill,
            "estimated_delivery_hours": 4 if can_fulfill else None,
            "source": "Regional Blood Bank Network",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def query_organ_availability(self, organ_type: str) -> dict:
        """
        Query regional organ availability.
        
        Args:
            organ_type: Type of organ to query
        
        Returns:
            Regional organ availability information.
        """
        available = self.regional_organs.get(organ_type, 0)
        
        return {
            "query_id": f"RFB-ORGAN-{datetime.utcnow().timestamp()}",
            "organ_type": organ_type,
            "available": available > 0,
            "organs_in_pool": available,
            "source": "National Organ Transplant Network",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def has_blood(self, blood_type: str, units_needed: int) -> bool:
        """Check if regional inventory has required blood."""
        available = self.regional_blood.get(blood_type, 0)
        return available >= units_needed
    
    def has_organ(self, organ_type: str) -> bool:
        """Check if regional inventory has required organ."""
        available = self.regional_organs.get(organ_type, 0)
        return available > 0
    
    def request_blood_transfer(self, blood_type: str, units: int, destination_hospital: str) -> dict:
        """
        Request blood transfer from regional inventory.
        
        Returns:
            Transfer request status and details.
        """
        available = self.regional_blood.get(blood_type, 0)
        if available < units:
            return {
                "success": False,
                "message": f"Insufficient {blood_type} units in regional inventory"
            }
        
        # Deduct from regional inventory
        self.regional_blood[blood_type] -= units
        
        return {
            "success": True,
            "transfer_id": f"TRANSFER-{datetime.utcnow().timestamp()}",
            "blood_type": blood_type,
            "units": units,
            "destination": destination_hospital,
            "estimated_arrival_hours": 3,
            "status": "APPROVED",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def request_organ_transfer(self, organ_type: str, destination_hospital: str) -> dict:
        """
        Request organ transfer from regional registry.
        
        Returns:
            Transfer request status and details.
        """
        available = self.regional_organs.get(organ_type, 0)
        if available < 1:
            return {
                "success": False,
                "message": f"No {organ_type} available in regional registry"
            }
        
        # Deduct from regional inventory
        self.regional_organs[organ_type] -= 1
        
        return {
            "success": True,
            "transfer_id": f"ORGAN-TRANSFER-{datetime.utcnow().timestamp()}",
            "organ_type": organ_type,
            "destination": destination_hospital,
            "estimated_arrival_hours": 6,
            "status": "APPROVED",
            "timestamp": datetime.utcnow().isoformat()
        }
