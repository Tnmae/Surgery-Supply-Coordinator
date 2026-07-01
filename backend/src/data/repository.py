"""Data repository for managing mock data."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


class DataRepository:
    """Repository for managing mock data in JSON format."""
    
    def __init__(self, data_file: Path = None):
        """Initialize the repository."""
        if data_file is None:
            # Get the data file from the same directory as this module
            data_file = Path(__file__).parent / "mock_data.json"
        
        self.data_file = data_file
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load mock data from JSON file."""
        with open(self.data_file, 'r') as f:
            return json.load(f)
    
    def _save_data(self) -> None:
        """Save data to JSON file."""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)
    
    # ===== Surgery methods =====
    
    def get_surgery(self, surgery_id: str) -> Optional[Dict]:
        """Get a surgery by ID."""
        for surg in self.data.get('surgeries', []):
            if surg['surgery_id'] == surgery_id:
                return surg
        return None
    
    def get_all_surgeries(self) -> List[Dict]:
        """Get all surgeries."""
        return self.data.get('surgeries', [])
    
    def get_pending_surgeries(self) -> List[Dict]:
        """Get all pending surgeries."""
        return [s for s in self.data.get('surgeries', []) if s.get('status') == 'PENDING']
    
    # ===== Patient methods =====
    
    def get_patient(self, patient_id: str) -> Optional[Dict]:
        """Get a patient by ID."""
        for pat in self.data.get('patients', []):
            if pat['patient_id'] == patient_id:
                return pat
        return None
    
    # ===== Blood unit methods =====
    
    def get_blood_units_by_type(self, blood_type: str) -> List[Dict]:
        """Get all blood units of a specific type."""
        return [b for b in self.data.get('blood_units', []) if b['blood_type'] == blood_type]
    
    def get_available_blood_units(self, blood_type: str) -> List[Dict]:
        """Get available (not expired, not in use) blood units of a specific type."""
        units = self.get_blood_units_by_type(blood_type)
        available = []
        now = datetime.utcnow()
        
        for unit in units:
            # Check if not expired and not in problematic status
            exp_date = datetime.fromisoformat(unit['expiration_date'].replace('Z', '+00:00'))
            if exp_date > now and unit['status'] in ['AVAILABLE', 'PENDING_CROSSMATCH']:
                available.append(unit)
        
        return available
    
    def get_all_blood_units(self) -> List[Dict]:
        """Get all blood units."""
        return self.data.get('blood_units', [])
    
    # ===== Organ methods =====
    
    def get_organs_by_type(self, organ_type: str) -> List[Dict]:
        """Get all organs of a specific type."""
        return [o for o in self.data.get('organs', []) if o['organ_type'] == organ_type]
    
    def get_available_organs(self, organ_type: str) -> List[Dict]:
        """Get available organs of a specific type."""
        organs = self.get_organs_by_type(organ_type)
        return [o for o in organs if o['status'] == 'AVAILABLE']
    
    def get_all_organs(self) -> List[Dict]:
        """Get all organs."""
        return self.data.get('organs', [])
    
    # ===== Equipment methods =====
    
    def get_equipment_by_name(self, name: str) -> Optional[Dict]:
        """Get equipment by name."""
        for eq in self.data.get('equipment', []):
            if eq['name'] == name:
                return eq
        return None
    
    def get_available_equipment(self, name: str) -> Optional[Dict]:
        """Get available equipment by name."""
        eq = self.get_equipment_by_name(name)
        if eq and eq['status'] == 'AVAILABLE':
            return eq
        return None
    
    def get_equipment_list(self, names: List[str]) -> Dict[str, Optional[Dict]]:
        """Get a list of equipment by names."""
        result = {}
        for name in names:
            result[name] = self.get_equipment_by_name(name)
        return result
    
    def get_available_equipment_list(self, names: List[str]) -> Dict[str, Optional[Dict]]:
        """Get a list of available equipment by names."""
        result = {}
        for name in names:
            result[name] = self.get_available_equipment(name)
        return result
    
    def get_all_equipment(self) -> List[Dict]:
        """Get all equipment."""
        return self.data.get('equipment', [])
