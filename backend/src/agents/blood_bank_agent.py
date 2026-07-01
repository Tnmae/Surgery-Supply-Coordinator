"""Blood Bank Agent - checks blood unit availability and compatibility."""

from datetime import datetime
from typing import List, Tuple
from src.data.repository import DataRepository
from src.mcp_servers.blood_bank_mcp import BloodBankMCPServer
from src.mcp_servers.regional_fallback_mcp import RegionalFallbackMCPServer
from src.models.blood import BloodBankQuery, BloodType
from src.models.report import Blocker, BlockerSeverity, ResourceStatus
from src.security.audit_logger import AuditLogger


class BloodBankAgent:
    """Agent responsible for checking blood unit availability and compatibility."""
    
    def __init__(
        self,
        repository: DataRepository = None,
        fallback_server: RegionalFallbackMCPServer = None,
        audit_logger: AuditLogger = None
    ):
        """Initialize the blood bank agent."""
        self.repository = repository or DataRepository()
        self.fallback_server = fallback_server or RegionalFallbackMCPServer()
        self.blood_bank_server = BloodBankMCPServer(self.repository, self.fallback_server)
        self.audit_logger = audit_logger or AuditLogger()
        self.name = "BloodBankAgent"
    
    def check_blood_availability(
        self,
        blood_type: str,
        units_needed: int,
        surgery_id: str,
        patient_id: str = None
    ) -> Tuple[bool, ResourceStatus, List[Blocker]]:
        """
        Check blood unit availability and compatibility.
        
        Args:
            blood_type: Required blood type
            units_needed: Number of units needed
            surgery_id: ID of the surgery
            patient_id: Optional patient ID for crossmatch
        
        Returns:
            Tuple of (all_available: bool, resource_status: ResourceStatus, blockers: List[Blocker])
        """
        blockers = []
        
        # Log the action
        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="CHECK_BLOOD_AVAILABILITY",
            input_data={"blood_type": blood_type, "units_needed": units_needed}
        )
        
        try:
            # Query blood bank
            query = BloodBankQuery(
                blood_type=BloodType(blood_type),
                units_needed=units_needed,
                patient_id=patient_id
            )
            
            response = self.blood_bank_server.query_blood_availability(query)
            
            # Analyze results
            status_msg = ""
            status_type = "OK"
            available_units = response.units_available
            
            if response.all_requirements_met:
                status_msg = f"✓ Blood available: {available_units}/{units_needed} units of {blood_type}"
                status_type = "OK"
            elif response.fallback_available:
                status_msg = f"⚠️  Local stock insufficient ({available_units}/{units_needed}), fallback available"
                status_type = "WARNING"
            else:
                status_msg = f"✗ Blood NOT available: only {available_units}/{units_needed} units of {blood_type}"
                status_type = "BLOCKED"
                
                blocker = Blocker(
                    category="BLOOD",
                    severity=BlockerSeverity.CRITICAL,
                    message=f"Insufficient blood units: {blood_type}",
                    details={
                        "units_available": available_units,
                        "units_needed": units_needed,
                        "blood_type": blood_type
                    },
                    suggested_action=f"Obtain {units_needed - available_units} additional units from fallback"
                )
                blockers.append(blocker)
            
            # Check for expiration concerns
            if response.earliest_expiration:
                exp_date = response.earliest_expiration
                now = datetime.utcnow()
                hours_until_expiry = (exp_date - now).total_seconds() / 3600
                
                if hours_until_expiry < 24:
                    status_msg += f" (WARNING: expires in {hours_until_expiry:.1f} hours)"
            
            # Check crossmatch status
            if response.units_pending_crossmatch > 0:
                status_msg += f" ({response.units_pending_crossmatch} pending crossmatch)"
                status_type = "WARNING"
            
            resource_status = ResourceStatus(
                resource_type="BLOOD",
                status=status_type,
                details=status_msg,
                data={
                    "blood_type": blood_type,
                    "units_available": available_units,
                    "units_needed": units_needed,
                    "units_pending_crossmatch": response.units_pending_crossmatch,
                    "fallback_available": response.fallback_available
                }
            )
            
            # Log the result
            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="CHECK_BLOOD_AVAILABILITY",
                output_data={
                    "all_available": response.all_requirements_met,
                    "status": status_type,
                    "units_available": available_units
                },
                result="SUCCESS" if (response.all_requirements_met or response.fallback_available) else "BLOCKED"
            )
            
            return (response.all_requirements_met or response.fallback_available), resource_status, blockers
            
        except Exception as e:
            error_msg = f"Error checking blood availability: {str(e)}"
            
            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="CHECK_BLOOD_AVAILABILITY",
                result="FAILURE"
            )
            
            blocker = Blocker(
                category="BLOOD",
                severity=BlockerSeverity.HIGH,
                message=error_msg,
                suggested_action="Contact blood bank for manual check"
            )
            
            resource_status = ResourceStatus(
                resource_type="BLOOD",
                status="BLOCKED",
                details=error_msg
            )
            
            return False, resource_status, [blocker]
    
    def check_crossmatch(
        self,
        unit_id: str,
        patient_id: str,
        surgery_id: str
    ) -> dict:
        """
        Check crossmatch compatibility for a blood unit and patient.
        
        Returns:
            Crossmatch result
        """
        result = self.blood_bank_server.check_crossmatch(unit_id, patient_id)
        
        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="CHECK_CROSSMATCH",
            input_data={"unit_id": unit_id, "patient_id": patient_id},
            output_data=result
        )
        
        return result
    
    def get_blood_inventory_summary(self) -> dict:
        """Get a summary of blood inventory status."""
        blood_types = ["O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"]
        summary = {}
        
        for blood_type in blood_types:
            units = self.repository.get_available_blood_units(blood_type)
            summary[blood_type] = len(units)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "blood_inventory": summary,
            "total_available": sum(summary.values())
        }
