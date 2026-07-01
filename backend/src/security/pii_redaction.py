"""PII (Personally Identifiable Information) redaction utilities."""

import re
from typing import Any, Dict, Optional


class PIIRedactor:
    """Utility for redacting PII from logs and outputs."""
    
    # Common PII patterns
    PATTERNS = {
        'patient_id': r'PAT\d+',
        'donor_id': r'DONOR\d+',
        'ssn': r'\d{3}-\d{2}-\d{4}',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'date_of_birth': r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
        'blood_type': r'\b[AB]?O[+-]\b',
    }
    
    # Fields to always redact
    SENSITIVE_FIELDS = {
        'patient_id',
        'donor_id',
        'date_of_birth',
        'ssn',
        'phone',
        'email',
        'witness',
        'performed_by',
        'created_by'
    }
    
    @staticmethod
    def redact_text(text: str) -> str:
        """Redact PII from plain text."""
        if not isinstance(text, str):
            return text
        
        redacted = text
        redacted = re.sub(PIIRedactor.PATTERNS['ssn'], '[SSN]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['phone'], '[PHONE]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['email'], '[EMAIL]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['patient_id'], '[PATIENT_ID]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['donor_id'], '[DONOR_ID]', redacted)
        
        return redacted
    
    @staticmethod
    def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact PII from a dictionary."""
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        for key, value in data.items():
            if key in PIIRedactor.SENSITIVE_FIELDS:
                # Redact entire value for sensitive fields
                if isinstance(value, str):
                    redacted[key] = f"[{key.upper()}]"
                elif isinstance(value, list):
                    redacted[key] = [f"[{key.upper()}]" for _ in value]
                else:
                    redacted[key] = f"[{key.upper()}]"
            elif isinstance(value, dict):
                redacted[key] = PIIRedactor.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [PIIRedactor.redact_dict(item) if isinstance(item, dict) else PIIRedactor.redact_text(str(item)) if isinstance(item, str) else item for item in value]
            elif isinstance(value, str):
                redacted[key] = PIIRedactor.redact_text(value)
            else:
                redacted[key] = value
        
        return redacted
    
    @staticmethod
    def redact_json(json_str: str) -> str:
        """Redact PII from JSON string."""
        redacted = json_str
        redacted = re.sub(PIIRedactor.PATTERNS['patient_id'], '[PATIENT_ID]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['donor_id'], '[DONOR_ID]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['ssn'], '[SSN]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['phone'], '[PHONE]', redacted)
        redacted = re.sub(PIIRedactor.PATTERNS['email'], '[EMAIL]', redacted)
        
        return redacted
