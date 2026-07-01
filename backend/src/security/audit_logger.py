"""Audit logging utilities."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from src.security.pii_redaction import PIIRedactor


class AuditLogger:
    """Immutable audit logger for tracking all agent actions."""
    
    def __init__(self, log_file: Path = None):
        """Initialize the audit logger."""
        if log_file is None:
            log_file = Path(__file__).parent.parent / "logs" / "audit.log"
        
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.audit_trail = []
    
    def log_action(
        self,
        action: str,
        actor_role: str,
        entity_type: str,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
        result: str = "SUCCESS",
        error: Optional[str] = None
    ) -> str:
        """
        Log an action to the audit trail.
        
        Args:
            action: Type of action (e.g., "CHECK_READINESS", "QUERY_BLOOD")
            actor_role: Role of the actor performing the action
            entity_type: Type of entity (e.g., "SURGERY", "BLOOD_UNIT")
            entity_id: ID of the entity
            details: Additional details about the action
            result: Result status (SUCCESS, FAILURE, BLOCKED)
            error: Error message if applicable
        
        Returns:
            Audit log entry ID
        """
        entry_id = f"AUDIT-{datetime.utcnow().timestamp()}"
        
        # Redact PII from details
        redacted_details = PIIRedactor.redact_dict(details) if details else None
        
        entry = {
            "entry_id": entry_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "actor_role": actor_role,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details": redacted_details,
            "result": result,
            "error": error
        }
        
        self.audit_trail.append(entry)
        self._write_to_file(entry)
        
        return entry_id
    
    def log_agent_action(
        self,
        agent_name: str,
        surgery_id: str,
        action: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        result: str = "SUCCESS"
    ) -> str:
        """
        Log an agent action.
        
        Args:
            agent_name: Name of the agent
            surgery_id: ID of the surgery being processed
            action: Action performed
            input_data: Input to the agent
            output_data: Output from the agent
            result: Result status
        
        Returns:
            Audit log entry ID
        """
        redacted_input = PIIRedactor.redact_dict(input_data) if input_data else None
        redacted_output = PIIRedactor.redact_dict(output_data) if output_data else None
        
        entry_id = f"AGENT-AUDIT-{datetime.utcnow().timestamp()}"
        
        entry = {
            "entry_id": entry_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent": agent_name,
            "surgery_id": surgery_id,
            "action": action,
            "input": redacted_input,
            "output": redacted_output,
            "result": result
        }
        
        self.audit_trail.append(entry)
        self._write_to_file(entry)
        
        return entry_id
    
    def _write_to_file(self, entry: Dict[str, Any]) -> None:
        """Write entry to immutable audit log file."""
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry, default=str) + '\n')
    
    def get_audit_trail(self, entity_id: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get audit trail entries.
        
        Args:
            entity_id: Optional entity ID to filter by
            limit: Optional limit on number of entries
        
        Returns:
            List of audit trail entries
        """
        trail = self.audit_trail
        
        if entity_id:
            trail = [e for e in trail if e.get('entity_id') == entity_id or e.get('surgery_id') == entity_id]
        
        if limit:
            trail = trail[-limit:]
        
        return trail
