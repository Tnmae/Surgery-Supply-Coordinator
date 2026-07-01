"""Organ Agent - checks organ availability, compatibility, and viability windows."""

from datetime import datetime
from typing import List, Optional, Tuple
from src.data.repository import DataRepository
from src.mcp_servers.organ_registry_mcp import OrganRegistryMCPServer
from src.mcp_servers.regional_fallback_mcp import RegionalFallbackMCPServer
from src.models.organ import OrganRegistryQuery, OrganType
from src.models.report import Blocker, BlockerSeverity, ResourceStatus
from src.security.audit_logger import AuditLogger


class OrganAgent:
    """Agent responsible for checking organ availability, compatibility, and viability."""

    def __init__(
        self,
        repository: DataRepository = None,
        fallback_server: RegionalFallbackMCPServer = None,
        audit_logger: AuditLogger = None
    ):
        """Initialize the organ agent."""
        self.repository = repository or DataRepository()
        self.fallback_server = fallback_server or RegionalFallbackMCPServer()
        self.organ_registry_server = OrganRegistryMCPServer(self.repository, self.fallback_server)
        self.audit_logger = audit_logger or AuditLogger()
        self.name = "OrganAgent"

    def check_organ_availability(
        self,
        organ_type: Optional[str],
        patient_id: str,
        surgery_id: str
    ) -> Tuple[bool, Optional[ResourceStatus], List[Blocker]]:
        """
        Check organ availability, donor compatibility, and viability window.

        Args:
            organ_type: Required organ type, or None if surgery doesn't need one
            patient_id: Recipient patient ID
            surgery_id: ID of the surgery

        Returns:
            Tuple of (available: bool, resource_status: Optional[ResourceStatus], blockers: List[Blocker])
            resource_status is None when the surgery does not require an organ.
        """
        if not organ_type:
            return True, None, []

        blockers = []

        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="CHECK_ORGAN_AVAILABILITY",
            input_data={"organ_type": organ_type}
        )

        try:
            query = OrganRegistryQuery(
                organ_type=OrganType(organ_type),
                recipient_patient_id=patient_id
            )
            response = self.organ_registry_server.query_organ_availability(query)

            if not response.available:
                fallback_available = self.fallback_server.has_organ(organ_type)
                if fallback_available:
                    status_msg = f"⚠️  No local {organ_type} match, regional fallback available"
                    status_type = "WARNING"
                else:
                    status_msg = f"✗ No {organ_type} available locally or regionally"
                    status_type = "BLOCKED"
                    blockers.append(Blocker(
                        category="ORGAN",
                        severity=BlockerSeverity.CRITICAL,
                        message=f"No {organ_type} available for transplant",
                        details={"organ_type": organ_type},
                        suggested_action="Request organ transfer from regional network or place patient on active wait list"
                    ))
                all_available = fallback_available
            else:
                best_match = response.best_match
                compat = self.organ_registry_server.check_donor_compatibility(
                    best_match.organ_id, patient_id
                )

                status_type = "OK"
                status_msg = f"✓ {organ_type} available: {best_match.organ_id} (donor blood type {best_match.donor_blood_type})"

                if not compat.get("compatible", False):
                    status_type = "BLOCKED"
                    status_msg = f"✗ Donor-recipient incompatibility for {best_match.organ_id}"
                    blockers.append(Blocker(
                        category="ORGAN",
                        severity=BlockerSeverity.CRITICAL,
                        message=f"Donor-recipient incompatibility: {organ_type} {best_match.organ_id}",
                        details=compat,
                        suggested_action="Identify an alternate compatible donor organ"
                    ))

                if response.viability_risk_level == "HIGH":
                    status_type = "BLOCKED" if status_type != "BLOCKED" else status_type
                    status_msg += " (CRITICAL: viability window nearly exhausted)"
                    blockers.append(Blocker(
                        category="ORGAN",
                        severity=BlockerSeverity.CRITICAL,
                        message=f"Organ {best_match.organ_id} viability window nearly exhausted",
                        details={"viability_risk_level": response.viability_risk_level},
                        suggested_action="Expedite procurement/transport or seek an alternate organ"
                    ))
                elif response.viability_risk_level == "MEDIUM":
                    status_msg += " (WARNING: viability window closing)"
                    if status_type == "OK":
                        status_type = "WARNING"

                all_available = status_type != "BLOCKED"

            resource_status = ResourceStatus(
                resource_type="ORGAN",
                status=status_type,
                details=status_msg,
                data={
                    "organ_type": organ_type,
                    "available": response.available,
                    "viability_risk_level": response.viability_risk_level,
                }
            )

            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="CHECK_ORGAN_AVAILABILITY",
                output_data={"all_available": all_available, "status": status_type},
                result="SUCCESS" if all_available else "BLOCKED"
            )

            return all_available, resource_status, blockers

        except Exception as e:
            error_msg = f"Error checking organ availability: {str(e)}"

            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="CHECK_ORGAN_AVAILABILITY",
                result="FAILURE"
            )

            blocker = Blocker(
                category="ORGAN",
                severity=BlockerSeverity.HIGH,
                message=error_msg,
                suggested_action="Contact organ registry for manual check"
            )

            resource_status = ResourceStatus(
                resource_type="ORGAN",
                status="BLOCKED",
                details=error_msg
            )

            return False, resource_status, [blocker]
