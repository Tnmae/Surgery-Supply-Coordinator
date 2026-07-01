"""Basic tests for the readiness workflow."""

import pytest
from datetime import datetime
from src.data.repository import DataRepository
from src.workflows.readiness_workflow import ReadinessWorkflow
from src.security.audit_logger import AuditLogger


class TestReadinessWorkflow:
    """Tests for the readiness workflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow instance for testing."""
        repository = DataRepository()
        audit_logger = AuditLogger()
        return ReadinessWorkflow(repository, audit_logger)
    
    def test_all_clear_scenario(self, workflow):
        """Test the all-clear scenario (SURG001)."""
        result = workflow.run_readiness_check("SURG001", "OR_COORDINATOR")
        
        assert result["status"] == "READY"
        assert result["blood_available"] == True
        assert result["safety_passed"] == True
    
    def test_missing_consent_scenario(self, workflow):
        """Test the missing consent scenario (SURG006)."""
        result = workflow.run_readiness_check("SURG006", "OR_COORDINATOR")
        
        assert result["status"] == "BLOCKED"
        assert any(b["category"] == "CONSENT" for b in result.get("blockers", []))
    
    def test_surgery_not_found(self, workflow):
        """Test with non-existent surgery."""
        result = workflow.run_readiness_check("INVALID_SURG", "OR_COORDINATOR")
        
        assert "error" in result
    
    def test_execution_time_recorded(self, workflow):
        """Test that execution time is recorded."""
        result = workflow.run_readiness_check("SURG001", "OR_COORDINATOR")
        
        assert "execution_time_ms" in result
        assert result["execution_time_ms"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
