"""Data repository for managing mock data."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any


class DataRepository:
    """Repository for managing mock data in JSON format.

    On read-only filesystems (Vercel, some container runtimes) writes are
    redirected to /tmp so the process stays alive. Data written there is
    ephemeral (lost on cold start) but prevents hard crashes.
    """

    def __init__(self, data_file: Path = None):
        """Initialize the repository."""
        if data_file is None:
            data_file = Path(__file__).parent / "mock_data.json"

        self.data_file = data_file
        # Writable shadow copy — used when the source file is on a read-only FS
        self._writable_file: Optional[Path] = None
        self.data = self._load_data()

    def _effective_write_path(self) -> Path:
        """Return a path we can actually write to."""
        if self._writable_file:
            return self._writable_file
        try:
            # Test writability with a silent probe
            self.data_file.write_bytes(self.data_file.read_bytes())
            return self.data_file
        except OSError:
            import shutil
            tmp_path = Path("/tmp") / f"mock_data_{self.data_file.stem}.json"
            if not tmp_path.exists():
                shutil.copy2(self.data_file, tmp_path)
            self._writable_file = tmp_path
            return tmp_path

    def _load_data(self) -> Dict[str, Any]:
        """Load mock data — prefer the writable shadow copy if it exists."""
        shadow = Path("/tmp") / f"mock_data_{self.data_file.stem}.json"
        source = shadow if shadow.exists() else self.data_file
        with open(source, "r") as f:
            return json.load(f)

    def _save_data(self) -> None:
        """Save data to the effective write path."""
        write_path = self._effective_write_path()
        with open(write_path, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def _find_surgery_index(self, surgery_id: str) -> Optional[int]:
        """Find the index of a surgery in the backing store."""
        surgeries = self.data.get('surgeries', [])
        for index, surgery in enumerate(surgeries):
            if surgery.get('surgery_id') == surgery_id:
                return index
        return None

    def _update_surgery_record(self, surgery_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply a partial update to a surgery record and persist it."""
        surgery_index = self._find_surgery_index(surgery_id)
        if surgery_index is None:
            return None

        surgery = self.data['surgeries'][surgery_index]
        surgery.update(updates)
        surgery['last_updated'] = datetime.utcnow().isoformat()
        self._save_data()
        return surgery
    
    # ===== Surgery methods =====
    
    def get_surgery(self, surgery_id: str) -> Optional[Dict]:
        """Get a surgery by ID."""
        for surg in self.data.get('surgeries', []):
            if surg['surgery_id'] == surgery_id:
                return surg
        return None

    def save_readiness_report(self, surgery_id: str, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Persist the latest readiness report for a surgery."""
        return self._update_surgery_record(
            surgery_id,
            {
                'readiness_report': report,
                'readiness_review_status': 'PENDING_REVIEW',
                'blocker_decisions': self.get_surgery(surgery_id).get('blocker_decisions', []) if self.get_surgery(surgery_id) else [],
            },
        )

    def record_blocker_decision(
        self,
        surgery_id: str,
        blocker: Dict[str, Any],
        decision: str,
        actor_role: str,
        notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Persist a clinician blocker decision and derive the overall review status."""
        surgery = self.get_surgery(surgery_id)
        if not surgery:
            return None

        decisions = list(surgery.get('blocker_decisions', []))
        decision_entry = {
            'category': blocker.get('category'),
            'message': blocker.get('message'),
            'severity': blocker.get('severity'),
            'suggested_action': blocker.get('suggested_action'),
            'decision': decision,
            'notes': notes,
            'acted_by_role': actor_role,
            'acted_at': datetime.utcnow().isoformat(),
        }

        blocker_key = (
            blocker.get('category'),
            blocker.get('message'),
            blocker.get('severity'),
        )

        filtered_decisions = [
            item for item in decisions
            if (
                item.get('category'),
                item.get('message'),
                item.get('severity'),
            ) != blocker_key
        ]
        filtered_decisions.append(decision_entry)

        readiness_report = surgery.get('readiness_report') or {}
        blockers = readiness_report.get('blockers', []) or []
        blocker_index = {
            (item.get('category'), item.get('message'), item.get('severity')): item
            for item in blockers
        }

        review_status = 'PENDING_REVIEW'
        if any(item.get('decision') == 'REJECT' for item in filtered_decisions):
            review_status = 'HALT_DUE_TO_BLOCKER'
        elif blockers:
            accepted_blockers = {
                (item.get('category'), item.get('message'), item.get('severity'))
                for item in filtered_decisions
                if item.get('decision') == 'ACCEPT'
            }
            if accepted_blockers.issuperset(blocker_index.keys()):
                review_status = 'RESOLVED'
        elif decision == 'ACCEPT':
            review_status = 'RESOLVED'

        return self._update_surgery_record(
            surgery_id,
            {
                'blocker_decisions': filtered_decisions,
                'readiness_review_status': review_status,
                'readiness_reviewed_at': datetime.utcnow().isoformat(),
                'reviewed_by_role': actor_role,
            },
        )
    
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
        now = datetime.now(timezone.utc)
        
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
