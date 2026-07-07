"""Mock MCP server for organ registry operations."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import List, Optional, Any, Dict
from pydantic import TypeAdapter

from src.config import Config
from src.data.repository import DataRepository
from src.models.organ import OrganRegistryQuery, OrganRegistryResponse, OrganUnit, OrganType
from src.mcp_servers.remote_client import RemoteMCPClient


class OrganRegistryMCPServer:
    """Mock MCP server for organ registry queries."""
    
    def __init__(
        self,
        repository: DataRepository = None,
        fallback: "RegionalFallbackMCPServer" = None,
        remote_client: RemoteMCPClient = None,
    ):
        """Initialize the organ registry server."""
        self.repository = repository or DataRepository()
        self.fallback = fallback
        self.remote_client = remote_client or (
            RemoteMCPClient(Config.EXTERNAL_MCP_SSE_URL) if Config.EXTERNAL_MCP_ENABLED else None
        )

    def _normalize_remote_organs(self, organs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized_organs = []

        for organ in organs:
            if not isinstance(organ, dict):
                continue

            normalized_organ = dict(organ)
            if "organ_id" not in normalized_organ and "id" in normalized_organ:
                normalized_organ["organ_id"] = normalized_organ.pop("id")
            if "current_location" not in normalized_organ:
                normalized_organ["current_location"] = normalized_organ.get("hospital_id", "External MCP")
            if "expected_arrival_at_recipient" not in normalized_organ:
                normalized_organ["expected_arrival_at_recipient"] = None

            normalized_organs.append(normalized_organ)

        return normalized_organs

    def _build_response(
        self,
        query: OrganRegistryQuery,
        matching_organs: List[Dict[str, Any]],
        best_match: Optional[Dict[str, Any]],
        viability_risk: str,
        fallback_available: bool,
    ) -> OrganRegistryResponse:
        adapter = TypeAdapter(List[OrganUnit])
        validated_organs = adapter.validate_python(self._normalize_remote_organs(matching_organs))
        validated_best_match = None

        if best_match is not None:
            validated_best_match = TypeAdapter(OrganUnit).validate_python(self._normalize_remote_organs([best_match])[0])

        return OrganRegistryResponse(
            query_id=f"ORQ-{datetime.utcnow().timestamp()}",
            organ_type=query.organ_type,
            available=bool(validated_organs),
            matching_organs=validated_organs,
            best_match=validated_best_match,
            time_to_procurement_hours=None,
            viability_risk_level=viability_risk,
            timestamp=datetime.utcnow(),
        )
    
    def query_organ_availability(self, query: OrganRegistryQuery) -> OrganRegistryResponse:
        """
        Query organ availability and compatibility.
        
        Returns:
            OrganRegistryResponse with matching organs and compatibility info.
        """
        if self.remote_client is not None:
            remote_result = self.remote_client.search_organ_registry(query.organ_type.value)
            remote_organs = remote_result.get("data") if remote_result.get("success") else None
            if remote_organs:
                if isinstance(remote_organs, dict):
                    remote_organs = [remote_organs]

                best_match = None
                viability_risk = "LOW"

                for organ in remote_organs:
                    if not isinstance(organ, dict):
                        continue

                    if best_match is None or organ.get("donor_age", 0) < best_match.get("donor_age", 0):
                        best_match = organ

                    cold_start_value = organ.get("cold_storage_started")
                    viability_window_minutes = organ.get("viability_window_minutes", 0)
                    if cold_start_value:
                        cold_start = datetime.fromisoformat(str(cold_start_value).replace('Z', '+00:00'))
                        now = datetime.utcnow()
                        cold_time = (now - cold_start).total_seconds() / 60
                        viability_remaining = viability_window_minutes - cold_time

                        if viability_remaining < 60:
                            viability_risk = "HIGH"
                        elif viability_remaining < 180 and viability_risk != "HIGH":
                            viability_risk = "MEDIUM"

                fallback_available = self.fallback.has_organ(query.organ_type.value) if self.fallback else False
                return self._build_response(query, remote_organs, best_match, viability_risk, fallback_available)

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
        
        fallback_available = False
        if not best_match and self.fallback:
            fallback_available = self.fallback.has_organ(query.organ_type.value)

        return self._build_response(query, available_organs, best_match, viability_risk, fallback_available)
    
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
