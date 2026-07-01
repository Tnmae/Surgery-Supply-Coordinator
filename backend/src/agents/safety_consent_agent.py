"""Safety and Consent Agent - verifies consents and checks for safety issues."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from src.data.repository import DataRepository
from src.models.patient import PatientData, Consent
from src.models.report import Blocker, BlockerSeverity
from src.security.audit_logger import AuditLogger


class SafetyConsentAgent:
    """Agent responsible for verifying consents and checking safety/medical flags."""
    
    def __init__(self, repository: DataRepository = None, audit_logger: AuditLogger = None):
        """Initialize the safety/consent agent."""
        self.repository = repository or DataRepository()
        self.audit_logger = audit_logger or AuditLogger()
        self.name = "SafetyConsentAgent"
    
    def check_safety_and_consent(
        self,
        patient_data: PatientData,
        surgery_id: str,
        surgery_type: str
    ) -> Tuple[bool, List[Blocker], List[str]]:
        """
        Check patient safety status and required consents.
        
        Args:
            patient_data: Extracted patient data
            surgery_id: ID of the surgery
            surgery_type: Type of surgery
        
        Returns:
            Tuple of (passed: bool, blockers: List[Blocker], warnings: List[str])
        """
        blockers = []
        warnings = []
        passed = True
        
        # Log the action
        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="CHECK_SAFETY_CONSENT",
            input_data={"surgery_type": surgery_type}
        )
        
        # Check required consents
        consent_blockers = self._check_required_consents(patient_data, surgery_type)
        if consent_blockers:
            blockers.extend(consent_blockers)
            passed = False
        
        # Check for allergies
        allergy_warnings = self._check_allergies(patient_data)
        warnings.extend(allergy_warnings)
        
        # Check for contraindications
        contraindication_blockers = self._check_contraindications(patient_data)
        if contraindication_blockers:
            blockers.extend(contraindication_blockers)
            # High/critical contraindications block surgery
            if any(b.severity in [BlockerSeverity.CRITICAL, BlockerSeverity.HIGH] for b in contraindication_blockers):
                passed = False
        
        # Check for medication interactions
        med_warnings = self._check_medication_interactions(patient_data, surgery_type)
        warnings.extend(med_warnings)
        
        # Log the result
        self.audit_logger.log_agent_action(
            agent_name=self.name,
            surgery_id=surgery_id,
            action="CHECK_SAFETY_CONSENT",
            output_data={
                "passed": passed,
                "blockers": len(blockers),
                "warnings": len(warnings)
            },
            result="SUCCESS" if passed else "BLOCKED"
        )
        
        return passed, blockers, warnings
    
    def _check_required_consents(
        self,
        patient_data: PatientData,
        surgery_type: str
    ) -> List[Blocker]:
        """
        Check that all required consents are in place.
        
        Returns:
            List of consent-related blockers
        """
        blockers = []
        now = datetime.utcnow()
        
        # Required consent types by surgery type
        required_consents = {
            "ORGAN_TRANSPLANT": ["SURGERY", "ORGAN_TRANSPLANT"],
            "CARDIAC": ["SURGERY"],
            "TRAUMA": ["SURGERY"],
            "ONCOLOGY": ["SURGERY"],
            "GENERAL": ["SURGERY"]
        }
        
        required_for_surgery = required_consents.get(surgery_type, ["SURGERY"])
        
        # For any surgery with blood transfusion, we need transfusion consent
        required_for_surgery.append("TRANSFUSION")
        
        for consent_type in required_for_surgery:
            # Find consent in patient data
            matching_consent = None
            for consent in patient_data.consents:
                if consent.consent_type == consent_type:
                    matching_consent = consent
                    break
            
            if not matching_consent or not matching_consent.given:
                blockers.append(Blocker(
                    category="CONSENT",
                    severity=BlockerSeverity.CRITICAL,
                    message=f"Missing required consent: {consent_type}",
                    details={"consent_type": consent_type},
                    suggested_action=f"Obtain {consent_type} consent from patient/guardian"
                ))
                continue
            
            # Check if consent is expired
            if matching_consent.expires:
                expires = self._to_naive_utc_datetime(matching_consent.expires)
                if expires < now:
                    blockers.append(Blocker(
                        category="CONSENT",
                        severity=BlockerSeverity.CRITICAL,
                        message=f"Expired consent: {consent_type}",
                        details={"consent_type": consent_type, "expired_at": matching_consent.expires},
                        suggested_action=f"Renew {consent_type} consent"
                    ))
        
        return blockers

    def _to_naive_utc_datetime(self, value: Any) -> datetime:
        """Normalize datetime-like input to a naive UTC datetime for safe comparisons."""
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            raise ValueError(f"Unsupported datetime value type: {type(value)}")

        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    
    def _check_allergies(self, patient_data: PatientData) -> List[str]:
        """Check for allergies and return warnings."""
        warnings = []
        
        for allergy in patient_data.allergies:
            if allergy.severity == "SEVERE":
                warnings.append(f"⚠️  CRITICAL ALLERGY: {allergy.allergen} - {allergy.reaction}")
            elif allergy.severity == "MODERATE":
                warnings.append(f"ALLERGY: {allergy.allergen} - {allergy.reaction}")
        
        return warnings
    
    def _check_contraindications(self, patient_data: PatientData) -> List[Blocker]:
        """Check for contraindications to surgery."""
        blockers = []
        
        for contra in patient_data.contraindications:
            severity = BlockerSeverity.LOW
            if contra.severity == "CRITICAL":
                severity = BlockerSeverity.CRITICAL
            elif contra.severity == "HIGH":
                severity = BlockerSeverity.HIGH
            elif contra.severity == "MEDIUM":
                severity = BlockerSeverity.MEDIUM
            
            blockers.append(Blocker(
                category="CONTRAINDICATION",
                severity=severity,
                message=f"Medical contraindication: {contra.condition}",
                details={"condition": contra.condition, "notes": contra.notes},
                suggested_action="Review with attending physician"
            ))
        
        return blockers
    
    def _check_medication_interactions(
        self,
        patient_data: PatientData,
        surgery_type: str
    ) -> List[str]:
        """Check for potential medication interactions."""
        warnings = []
        
        problematic_medications = {
            "WARFARIN": "Anticoagulant - verify anesthesia plan",
            "ASPIRIN": "Antiplatelet - may increase bleeding risk",
            "METFORMIN": "Diabetes drug - hold before procedure if contrast used",
            "ACE_INHIBITOR": "May cause intraoperative hypotension",
            "IMMUNOSUPPRESSANTS": "For transplant patients - maintain throughout"
        }
        
        for med in patient_data.medications:
            if med in problematic_medications:
                warnings.append(f"⚠️  Medication interaction: {med} - {problematic_medications[med]}")
        
        return warnings
    
    def get_safety_summary(self, patient_id: str) -> Dict[str, Any]:
        """Get a safety summary for a patient."""
        patient_dict = self.repository.get_patient(patient_id)
        
        if not patient_dict:
            return {}
        
        critical_allergies = [
            a for a in patient_dict.get('allergies', [])
            if a.get('severity') == 'SEVERE'
        ]
        
        valid_consents = []
        now = datetime.utcnow()
        for consent in patient_dict.get('consents', []):
            if consent.get('given'):
                expires = consent.get('expires')
                if expires:
                    exp_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                    if exp_dt > now:
                        valid_consents.append(consent['consent_type'])
                else:
                    valid_consents.append(consent['consent_type'])
        
        return {
            "patient_id": patient_id,
            "critical_allergies": len(critical_allergies),
            "allergies_detail": [a['allergen'] for a in critical_allergies],
            "contraindications": len(patient_dict.get('contraindications', [])),
            "valid_consents": valid_consents,
            "medications": patient_dict.get('medications', [])
        }
