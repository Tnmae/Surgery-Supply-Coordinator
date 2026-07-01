"""Validation Agent - cross-checks resource compatibility and timing constraints."""

from datetime import datetime
from typing import List, Optional, Tuple
from src.models.report import Blocker, BlockerSeverity, ResourceStatus
from src.security.audit_logger import AuditLogger


class ValidationAgent:
    """Agent responsible for cross-checking resource compatibility and timing constraints."""

    def __init__(self, audit_logger: AuditLogger = None):
        """Initialize the validation agent."""
        self.audit_logger = audit_logger or AuditLogger()
        self.name = "ValidationAgent"

    def validate(
        self,
        surgery_dict: dict,
        blood_status: ResourceStatus,
        organ_status: Optional[ResourceStatus],
        equipment_status: ResourceStatus,
        requested_at: datetime,
        surgery_id: str
    ) -> Tuple[bool, List[Blocker], List[str]]:
        """
        Cross-check resource compatibility and timing constraints across all resource checks.

        Args:
            surgery_dict: Surgery record
            blood_status: Result of the blood bank check
            organ_status: Result of the organ check, or None if not required
            equipment_status: Result of the equipment check
            requested_at: Time the readiness check was requested
            surgery_id: ID of the surgery

        Returns:
            Tuple of (passed: bool, blockers: List[Blocker], warnings: List[str])
        """
        blockers = []
        warnings = []

        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="VALIDATE_CROSS_RESOURCE",
        )

        # Timing constraint: flag if the surgery is scheduled before the check was requested
        scheduled_time = self._parse_datetime(surgery_dict.get('scheduled_time'))
        if scheduled_time and scheduled_time < requested_at:
            warnings.append(
                f"Scheduled time {scheduled_time.isoformat()} is earlier than the readiness check time"
            )

        # Cross-check: organ viability window against estimated procedure duration
        if organ_status and organ_status.data:
            viability_risk = organ_status.data.get("viability_risk_level")
            if viability_risk == "HIGH":
                blockers.append(Blocker(
                    category="VALIDATION",
                    severity=BlockerSeverity.CRITICAL,
                    message="Organ viability risk combined with procedure timeline creates high risk of a non-viable organ at transplant time",
                    details={"viability_risk_level": viability_risk},
                    suggested_action="Expedite organ transport/procurement or source an alternate organ"
                ))
            elif viability_risk == "MEDIUM":
                warnings.append("Organ viability risk is MEDIUM; monitor transport/procurement timing closely")

        # Cross-check: pending crossmatch blood used in an organ transplant case
        if organ_status is not None and blood_status.data and blood_status.data.get("units_pending_crossmatch", 0) > 0:
            warnings.append(
                "Blood units pending crossmatch for an organ transplant case — confirm crossmatch before organ arrival"
            )

        # Surface any resource that is still BLOCKED at validation time
        for status, label in [(blood_status, "BLOOD"), (organ_status, "ORGAN"), (equipment_status, "EQUIPMENT")]:
            if status is not None and status.status == "BLOCKED":
                warnings.append(f"{label} check reported BLOCKED — readiness cannot proceed until resolved")

        passed = len(blockers) == 0

        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="VALIDATE_CROSS_RESOURCE",
            output_data={"passed": passed, "blockers": len(blockers), "warnings": len(warnings)},
            result="SUCCESS" if passed else "BLOCKED"
        )

        return passed, blockers, warnings

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        """Parse a datetime-like value, returning None if not parseable."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00')).replace(tzinfo=None)
        except ValueError:
            return None
