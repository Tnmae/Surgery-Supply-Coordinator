"""Mock MCP server for equipment inventory operations."""

from datetime import datetime
from typing import List, Optional
from src.data.repository import DataRepository


class EquipmentInventoryMCPServer:
    """Mock MCP server for equipment inventory queries."""
    
    def __init__(self, repository: DataRepository = None):
        """Initialize the equipment inventory server."""
        self.repository = repository or DataRepository()
    
    def query_equipment_availability(self, equipment_names: List[str], sterile_required: bool = True) -> dict:
        """
        Query equipment availability.
        
        Args:
            equipment_names: List of equipment names to check
            sterile_required: Whether sterile equipment is required
        
        Returns:
            Dictionary with availability status and equipment details.
        """
        available = {}
        unavailable = []
        maintenance_concerns = []
        
        equipment_map = self.repository.get_available_equipment_list(equipment_names)
        
        for name, equipment in equipment_map.items():
            if equipment is None:
                unavailable.append(name)
            else:
                # Check sterilization status if required
                if sterile_required:
                    if equipment['sterilization_status'] != 'STERILE' and equipment['sterilization_status'] != 'NOT_APPLICABLE':
                        unavailable.append(name)
                        continue
                
                # Check maintenance status
                next_maint = datetime.fromisoformat(equipment['next_maintenance_due'].replace('Z', '+00:00'))
                if next_maint < datetime.utcnow():
                    maintenance_concerns.append(f"{name} - maintenance overdue")
                
                available[name] = equipment
        
        all_available = len(unavailable) == 0 and len(maintenance_concerns) == 0
        
        return {
            "query_id": f"EQQ-{datetime.utcnow().timestamp()}",
            "requested_equipment": equipment_names,
            "available_equipment": available,
            "unavailable_equipment": unavailable,
            "all_available": all_available,
            "maintenance_concerns": maintenance_concerns,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_equipment(self, name: str) -> Optional[dict]:
        """
        Get equipment by name.
        
        Returns:
            Equipment details or None if not found.
        """
        return self.repository.get_equipment_by_name(name)
    
    def get_available_equipment(self, name: str) -> Optional[dict]:
        """
        Get available equipment by name.
        
        Returns:
            Available equipment details or None if not available.
        """
        return self.repository.get_available_equipment(name)
    
    def check_sterilization_status(self, equipment_id: str) -> dict:
        """
        Check sterilization status for a specific equipment.
        
        Returns:
            Sterilization status and details.
        """
        for eq in self.repository.get_all_equipment():
            if eq['equipment_id'] == equipment_id:
                return {
                    "success": True,
                    "equipment_id": equipment_id,
                    "name": eq['name'],
                    "status": eq['sterilization_status'],
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return {"success": False, "message": "Equipment not found"}
    
    def check_maintenance_status(self, equipment_id: str) -> dict:
        """
        Check maintenance status for a specific equipment.
        
        Returns:
            Maintenance status and next due date.
        """
        for eq in self.repository.get_all_equipment():
            if eq['equipment_id'] == equipment_id:
                next_maint = datetime.fromisoformat(eq['next_maintenance_due'].replace('Z', '+00:00'))
                is_overdue = next_maint < datetime.utcnow()
                
                return {
                    "success": True,
                    "equipment_id": equipment_id,
                    "name": eq['name'],
                    "last_maintenance": eq['last_maintenance_date'],
                    "next_maintenance_due": eq['next_maintenance_due'],
                    "is_overdue": is_overdue,
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return {"success": False, "message": "Equipment not found"}
