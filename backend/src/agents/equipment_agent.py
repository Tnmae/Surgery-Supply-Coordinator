"""Equipment Agent - checks equipment availability, sterilization, and maintenance status."""

from typing import List, Tuple
from src.data.repository import DataRepository
from src.mcp_servers.equipment_inventory_mcp import EquipmentInventoryMCPServer
from src.models.report import Blocker, BlockerSeverity, ResourceStatus
from src.security.audit_logger import AuditLogger


class EquipmentAgent:
    """Agent responsible for checking equipment availability, sterilization, and maintenance."""

    def __init__(
        self,
        repository: DataRepository = None,
        audit_logger: AuditLogger = None
    ):
        """Initialize the equipment agent."""
        self.repository = repository or DataRepository()
        self.equipment_server = EquipmentInventoryMCPServer(self.repository)
        self.audit_logger = audit_logger or AuditLogger()
        self.name = "EquipmentAgent"

    def check_equipment_availability(
        self,
        equipment_list: List[str],
        surgery_id: str
    ) -> Tuple[bool, ResourceStatus, List[Blocker]]:
        """
        Check availability, sterilization status, and maintenance schedule for required equipment.

        Args:
            equipment_list: List of required equipment names
            surgery_id: ID of the surgery

        Returns:
            Tuple of (all_available: bool, resource_status: ResourceStatus, blockers: List[Blocker])
        """
        blockers = []

        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="CHECK_EQUIPMENT_AVAILABILITY",
            input_data={"equipment_list": equipment_list}
        )

        if not equipment_list:
            resource_status = ResourceStatus(
                resource_type="EQUIPMENT",
                status="OK",
                details="No equipment required for this surgery",
                data={"requested": [], "unavailable": []}
            )
            return True, resource_status, blockers

        try:
            response = self.equipment_server.query_equipment_availability(equipment_list)

            unavailable = response["unavailable_equipment"]
            maintenance_concerns = response["maintenance_concerns"]
            all_available = response["all_available"]

            if unavailable:
                status_type = "BLOCKED"
                status_msg = f"✗ Unavailable/unsterile equipment: {', '.join(unavailable)}"
                for item in unavailable:
                    blockers.append(Blocker(
                        category="EQUIPMENT",
                        severity=BlockerSeverity.CRITICAL,
                        message=f"Equipment unavailable or not sterile: {item}",
                        details={"equipment": item},
                        suggested_action=f"Source or sterilize a replacement for {item}"
                    ))
            elif maintenance_concerns:
                status_type = "WARNING"
                status_msg = f"⚠️  Maintenance concerns: {'; '.join(maintenance_concerns)}"
            else:
                status_type = "OK"
                status_msg = f"✓ All equipment available and sterile: {', '.join(equipment_list)}"

            resource_status = ResourceStatus(
                resource_type="EQUIPMENT",
                status=status_type,
                details=status_msg,
                data={
                    "requested": equipment_list,
                    "unavailable": unavailable,
                    "maintenance_concerns": maintenance_concerns,
                }
            )

            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="CHECK_EQUIPMENT_AVAILABILITY",
                output_data={"all_available": all_available, "status": status_type},
                result="SUCCESS" if all_available else "BLOCKED"
            )

            return all_available, resource_status, blockers

        except Exception as e:
            error_msg = f"Error checking equipment availability: {str(e)}"

            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="CHECK_EQUIPMENT_AVAILABILITY",
                result="FAILURE"
            )

            blocker = Blocker(
                category="EQUIPMENT",
                severity=BlockerSeverity.HIGH,
                message=error_msg,
                suggested_action="Contact supply admin for manual equipment check"
            )

            resource_status = ResourceStatus(
                resource_type="EQUIPMENT",
                status="BLOCKED",
                details=error_msg
            )

            return False, resource_status, [blocker]
