"""Readiness workflow orchestration - Phase 1/2 implementation."""

from datetime import datetime
from typing import Dict, Any, List
from src.data.repository import DataRepository
from src.agents.patient_data_agent import PatientDataAgent
from src.agents.safety_consent_agent import SafetyConsentAgent
from src.agents.blood_bank_agent import BloodBankAgent
from src.security.audit_logger import AuditLogger


class ReadinessWorkflow:
    """Orchestrates the readiness check workflow."""
    
    def __init__(
        self,
        repository: DataRepository = None,
        audit_logger: AuditLogger = None
    ):
        """Initialize the workflow."""
        self.repository = repository or DataRepository()
        self.audit_logger = audit_logger or AuditLogger()
        
        # Initialize agents
        self.patient_agent = PatientDataAgent(self.repository, self.audit_logger)
        self.safety_agent = SafetyConsentAgent(self.repository, self.audit_logger)
        self.blood_agent = BloodBankAgent(self.repository, audit_logger=self.audit_logger)
    
    def run_readiness_check(self, surgery_id: str, user_role: str) -> Dict[str, Any]:
        """
        Run the complete readiness check workflow.
        
        Args:
            surgery_id: ID of the surgery to check
            user_role: Role of the user requesting the check
        
        Returns:
            Complete readiness report
        """
        start_time = datetime.utcnow()
        
        # Get surgery
        surgery_dict = self.repository.get_surgery(surgery_id)
        if not surgery_dict:
            return {"error": f"Surgery {surgery_id} not found"}
        
        # Step 1: Extract patient data
        from src.models.surgery import SurgeryRequest
        surgery_request = SurgeryRequest(**surgery_dict)
        extraction_result = self.patient_agent.extract_patient_data(
            surgery_request,
            surgery_id
        )
        
        if not extraction_result.extraction_successful:
            return {
                "status": "BLOCKED",
                "reason": "Patient data extraction failed",
                "blockers": extraction_result.warnings
            }
        
        patient_data = extraction_result.extracted_data
        
        # Step 2: Check safety and consents
        safety_passed, safety_blockers, safety_warnings = self.safety_agent.check_safety_and_consent(
            patient_data,
            surgery_id,
            surgery_dict['surgery_type']
        )
        
        if not safety_passed:
            return {
                "status": "BLOCKED",
                "reason": "Safety/Consent check failed",
                "blockers": [
                    {
                        "category": b.category,
                        "severity": b.severity.value,
                        "message": b.message
                    }
                    for b in safety_blockers
                ]
            }
        
        # Step 3: Check blood availability
        blood_available, blood_status, blood_blockers = self.blood_agent.check_blood_availability(
            surgery_dict['required_blood_type'],
            surgery_dict['required_blood_units'],
            surgery_id,
            surgery_dict['patient_id']
        )
        
        # Determine final status
        if not blood_available or not safety_passed:
            final_status = "BLOCKED"
        else:
            final_status = "READY"
        
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        return {
            "status": final_status,
            "surgery_id": surgery_id,
            "blood_available": blood_available,
            "safety_passed": safety_passed,
            "blood_status": blood_status.model_dump(),
            "blockers": [b.model_dump() for b in blood_blockers + safety_blockers],
            "warnings": safety_warnings + extraction_result.warnings,
            "execution_time_ms": duration_ms,
            "timestamp": start_time.isoformat()
        }
