"""Mock MCP server for blood bank operations."""

from datetime import datetime
from typing import List, Optional
from pydantic import TypeAdapter

from src.data.repository import DataRepository
from src.config import Config
from src.models.blood import BloodBankQuery, BloodBankResponse, BloodUnit, BloodUnitStatus, CrossmatchStatus
from src.mcp_servers.remote_client import RemoteMCPClient


class BloodBankMCPServer:
    """Mock MCP server for blood bank queries."""
    
    def __init__(
        self,
        repository: DataRepository = None,
        fallback: "RegionalFallbackMCPServer" = None,
        remote_client: RemoteMCPClient = None,
    ):
        """Initialize the blood bank server."""
        self.repository = repository or DataRepository()
        self.fallback = fallback
        self.remote_client = remote_client or RemoteMCPClient(Config.EXTERNAL_MCP_SSE_URL)

    def _normalize_remote_units(self, available_units: List[dict]) -> List[dict]:
        normalized_units = []

        for unit in available_units:
            if not isinstance(unit, dict):
                continue

            normalized_unit = dict(unit)
            if "unit_id" not in normalized_unit and "id" in normalized_unit:
                normalized_unit["unit_id"] = normalized_unit.pop("id")

            normalized_units.append(normalized_unit)

        return normalized_units

    def _build_response(
        self,
        query: BloodBankQuery,
        available_units: List[dict],
        fallback_available: bool,
    ) -> BloodBankResponse:
        available_units = self._normalize_remote_units(available_units)
        adapter = TypeAdapter(List[BloodUnit])
        validated_units = adapter.validate_python(available_units)

        earliest_exp = None
        available_count = 0

        for unit in validated_units:
            if unit.status == BloodUnitStatus.AVAILABLE:
                available_count += 1
            if earliest_exp is None or unit.expiration_date < earliest_exp:
                earliest_exp = unit.expiration_date

        return BloodBankResponse(
            query_id=f"BBQ-{datetime.utcnow().timestamp()}",
            blood_type=query.blood_type,
            units_requested=query.units_needed,
            units_available=available_count,
            available_units=validated_units[:query.units_needed],
            units_pending_crossmatch=sum(1 for unit in validated_units if unit.status == BloodUnitStatus.PENDING_CROSSMATCH),
            earliest_expiration=earliest_exp,
            all_requirements_met=available_count >= query.units_needed,
            fallback_available=fallback_available,
            timestamp=datetime.utcnow(),
        )
    
    def query_blood_availability(self, query: BloodBankQuery) -> BloodBankResponse:
        """
        Query blood unit availability.
        
        Returns:
            BloodBankResponse with available units and status.
        """
        remote_result = self.remote_client.search_blood_inventory(query.blood_type.value)

        if remote_result.get("success") and remote_result.get("data"):
            fallback_available = False
            if self.fallback:
                fallback_available = self.fallback.has_blood(query.blood_type.value, query.units_needed)

            return self._build_response(query, remote_result["data"], fallback_available)

        # Fall back to local inventory if the external MCP cannot be reached.
        local_units = self.repository.get_available_blood_units(query.blood_type.value)
        valid_units = [u for u in local_units if u['status'] in ['AVAILABLE', 'PENDING_CROSSMATCH']]
        fallback_available = False
        if self.fallback:
            fallback_available = self.fallback.has_blood(query.blood_type.value, query.units_needed)

        return self._build_response(query, valid_units, fallback_available)
    
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
