"""Logistics Agent - estimates transport times and total procedure timeline."""

from typing import Dict, List, Optional, Tuple
from src.models.report import ResourceStatus
from src.security.audit_logger import AuditLogger

# Regional fallback ETAs, kept in sync with RegionalFallbackMCPServer's mock estimates.
BLOOD_TRANSFER_ETA_HOURS = 4.0
ORGAN_TRANSFER_ETA_HOURS = 6.0


class LogisticsAgent:
    """Agent responsible for estimating transport times and total procedure timeline."""

    def __init__(self, audit_logger: AuditLogger = None):
        """Initialize the logistics agent."""
        self.audit_logger = audit_logger or AuditLogger()
        self.name = "LogisticsAgent"

    def estimate_logistics(
        self,
        surgery_dict: dict,
        blood_status: ResourceStatus,
        organ_status: Optional[ResourceStatus],
        equipment_status: ResourceStatus,
        surgery_id: str
    ) -> Tuple[Dict, List[str]]:
        """
        Estimate transport time and total timeline, and flag time-critical constraints.

        Args:
            surgery_dict: Surgery record
            blood_status: Result of the blood bank check
            organ_status: Result of the organ check, or None if not required
            equipment_status: Result of the equipment check
            surgery_id: ID of the surgery

        Returns:
            Tuple of (logistics: dict, warnings: List[str])
        """
        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="ESTIMATE_LOGISTICS",
        )

        warnings = []
        notes = []
        transport_hours = 0.0
        time_critical = False
        estimated_duration = surgery_dict.get('estimated_duration_minutes', 0)

        if blood_status.data and blood_status.data.get("fallback_available"):
            transport_hours = max(transport_hours, BLOOD_TRANSFER_ETA_HOURS)
            notes.append(f"Regional blood transfer estimated at {BLOOD_TRANSFER_ETA_HOURS:.1f}h")

        if organ_status and organ_status.data:
            if organ_status.data.get("available") is False:
                transport_hours = max(transport_hours, ORGAN_TRANSFER_ETA_HOURS)
                notes.append(f"Regional organ transfer estimated at {ORGAN_TRANSFER_ETA_HOURS:.1f}h")
                time_critical = True
            if organ_status.data.get("viability_risk_level") == "HIGH":
                time_critical = True
                notes.append("Organ viability window is the binding time constraint")

        total_timeline_minutes = estimated_duration + int(transport_hours * 60)

        if transport_hours > 0:
            warnings.append(
                f"Regional transport required — adds ~{transport_hours:.1f}h before the procedure can start"
            )

        logistics = {
            "estimated_duration_minutes": estimated_duration,
            "transport_time_hours": transport_hours,
            "total_timeline_minutes": total_timeline_minutes,
            "time_critical": time_critical,
            "notes": notes,
        }

        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="ESTIMATE_LOGISTICS",
            output_data=logistics,
            result="SUCCESS"
        )

        return logistics, warnings
