"""Patient Data Agent - extracts and validates patient information."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from src.data.repository import DataRepository
from src.models.patient import PatientDataExtractionResult, PatientData, Allergy, Contraindication, Consent
from src.models.surgery import SurgeryRequest
from src.security.audit_logger import AuditLogger


class PatientDataAgent:
    """Agent responsible for extracting and validating patient data."""
    
    def __init__(self, repository: DataRepository = None, audit_logger: AuditLogger = None):
        """Initialize the patient data agent."""
        self.repository = repository or DataRepository()
        self.audit_logger = audit_logger or AuditLogger()
        self.name = "PatientDataAgent"
    
    def extract_patient_data(
        self,
        surgery_request: SurgeryRequest,
        surgery_id: str
    ) -> PatientDataExtractionResult:
        """
        Extract and validate patient data for a surgery.
        
        Args:
            surgery_request: The surgery request
            surgery_id: ID of the surgery
        
        Returns:
            PatientDataExtractionResult with extracted data or errors
        """
        patient_id = surgery_request.patient_id
        
        # Log the action
        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="EXTRACT_PATIENT_DATA",
            input_data={"patient_id": patient_id}
        )
        
        # Get patient from repository
        patient_dict = self.repository.get_patient(patient_id)
        
        if not patient_dict:
            return PatientDataExtractionResult(
                patient_id=patient_id,
                extraction_successful=False,
                missing_fields=["patient_record"],
                warnings=[f"Patient {patient_id} not found in system"],
                timestamp=datetime.utcnow()
            )
        
        # Parse and validate patient data
        try:
            # Extract allergies
            allergies = [
                Allergy(**allergy) 
                for allergy in patient_dict.get('allergies', [])
            ]
            
            # Extract contraindications
            contraindications = [
                Contraindication(**contra) 
                for contra in patient_dict.get('contraindications', [])
            ]
            
            # Extract consents
            consents = [
                Consent(**consent) 
                for consent in patient_dict.get('consents', [])
            ]
            
            # Create patient data model
            patient_data = PatientData(
                patient_id=patient_dict['patient_id'],
                date_of_birth=datetime.fromisoformat(patient_dict['date_of_birth'].replace('Z', '+00:00')),
                blood_type=patient_dict['blood_type'],
                allergies=allergies,
                contraindications=contraindications,
                consents=consents,
                medications=patient_dict.get('medications', []),
                prior_surgeries=patient_dict.get('prior_surgeries', 0),
                special_notes=patient_dict.get('special_notes', None)
            )
            
            # Validate extracted data
            missing_fields = self._validate_patient_data(patient_data, surgery_request)
            warnings = self._check_warnings(patient_data, surgery_request)
            
            result = PatientDataExtractionResult(
                patient_id=patient_id,
                extraction_successful=len(missing_fields) == 0,
                extracted_data=patient_data,
                missing_fields=missing_fields,
                warnings=warnings,
                timestamp=datetime.utcnow()
            )
            
            # Log the result
            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="EXTRACT_PATIENT_DATA",
                output_data={
                    "extraction_successful": result.extraction_successful,
                    "missing_fields": result.missing_fields,
                    "warnings": result.warnings
                },
                result="SUCCESS" if result.extraction_successful else "BLOCKED"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Error extracting patient data: {str(e)}"
            self.audit_logger.log_agent_action(
                agent_name=self.name,
                surgery_id=surgery_id,
                action="EXTRACT_PATIENT_DATA",
                result="FAILURE"
            )
            
            return PatientDataExtractionResult(
                patient_id=patient_id,
                extraction_successful=False,
                missing_fields=["all"],
                warnings=[error_msg],
                timestamp=datetime.utcnow()
            )
    
    def _validate_patient_data(
        self,
        patient_data: PatientData,
        surgery_request: SurgeryRequest
    ) -> List[str]:
        """
        Validate that patient data matches surgery requirements.
        
        Returns:
            List of missing or mismatched fields
        """
        missing = []
        
        # Check blood type match
        if patient_data.blood_type != surgery_request.required_blood_type:
            missing.append(f"blood_type_mismatch: patient has {patient_data.blood_type}, surgery requires {surgery_request.required_blood_type}")
        
        # Check for required fields
        if not patient_data.patient_id:
            missing.append("patient_id")
        if not patient_data.blood_type:
            missing.append("blood_type")
        if not patient_data.date_of_birth:
            missing.append("date_of_birth")
        
        return missing
    
    def _check_warnings(
        self,
        patient_data: PatientData,
        surgery_request: SurgeryRequest
    ) -> List[str]:
        """
        Check for warnings in patient data.
        
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check for critical allergies
        for allergy in patient_data.allergies:
            if allergy.severity == "SEVERE":
                warnings.append(f"CRITICAL ALLERGY: {allergy.allergen} - {allergy.reaction}")
        
        # Check for contraindications
        for contra in patient_data.contraindications:
            if contra.severity in ["HIGH", "CRITICAL"]:
                warnings.append(f"Contraindication: {contra.condition}")
        
        # Check for medications that might interact
        if "WARFARIN" in patient_data.medications:
            warnings.append("Patient on anticoagulant (WARFARIN) - careful with anesthesia")
        
        return warnings
    
    def get_patient_summary(self, patient_id: str) -> Dict[str, Any]:
        """Get a summary of patient information."""
        patient_dict = self.repository.get_patient(patient_id)
        
        if not patient_dict:
            return {}
        
        return {
            "patient_id": patient_dict['patient_id'],
            "blood_type": patient_dict['blood_type'],
            "allergies_count": len(patient_dict.get('allergies', [])),
            "critical_allergies": len([a for a in patient_dict.get('allergies', []) if a.get('severity') == 'SEVERE']),
            "medications": patient_dict.get('medications', []),
            "prior_surgeries": patient_dict.get('prior_surgeries', 0)
        }
