"""FastAPI main application and endpoints."""

import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

load_dotenv()

from src.config import Config
from src.data.repository import DataRepository
from src.models.report import ReadinessCheckRequest, ReadinessCheckResponse, ReadinessReport, ReadinessStatus
from src.models.surgery import Surgery, SurgeryDetail
from src.security.rbac import RBAC, Permission
from src.security.audit_logger import AuditLogger
from src.agents.patient_data_agent import PatientDataAgent
from src.agents.safety_consent_agent import SafetyConsentAgent
from src.agents.blood_bank_agent import BloodBankAgent
from src.adk_pipeline.pipeline import run_readiness_pipeline, llm_coordinator_available
from src.adk_pipeline.llm_pipeline import run_llm_readiness_pipeline


# Configure logging
logging.basicConfig(level=Config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Ensure directories exist
Config.ensure_directories_exist()

# Initialize application
app = FastAPI(
    title=Config.API_TITLE,
    description=Config.API_DESCRIPTION,
    version=Config.API_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
repository = DataRepository(Config.MOCK_DATA_FILE)
audit_logger = AuditLogger(Config.AUDIT_LOG_FILE)
patient_data_agent = PatientDataAgent(repository, audit_logger)
safety_consent_agent = SafetyConsentAgent(repository, audit_logger)
blood_bank_agent = BloodBankAgent(repository=repository, audit_logger=audit_logger)


# ===== Dependencies =====

async def verify_role(user_role: str = Header(...)) -> str:
    """Verify user role header."""
    if user_role not in Config.VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid user role: {user_role}")
    return user_role


async def check_readiness_permission(user_role: str = Header(...)) -> str:
    """Check if user has permission to check readiness."""
    if not RBAC.can_check_readiness(user_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions to check readiness")
    return user_role


# ===== Utility Functions =====

def add_disclaimer(response_dict: dict) -> dict:
    """Add disclaimer to response."""
    response_dict["disclaimer"] = Config.DISCLAIMER
    return response_dict


# ===== Health Check =====

@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": Config.APP_NAME,
        "version": Config.APP_VERSION,
        "llm_pipeline_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
        "adk_coordinator_llm_configured": llm_coordinator_available()
    }


# ===== Surgery Endpoints =====

@app.get("/surgeries")
async def list_surgeries(user_role: str = Depends(verify_role)) -> dict:
    """
    List all pending surgeries.
    
    Required header: user-role
    """
    if not RBAC.can_view_surgery(user_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    surgeries = repository.get_pending_surgeries()
    
    return add_disclaimer({
        "surgeries": surgeries,
        "count": len(surgeries),
        "timestamp": datetime.utcnow().isoformat()
    })


@app.get("/surgeries/{surgery_id}")
async def get_surgery(surgery_id: str, user_role: str = Depends(verify_role)) -> dict:
    """
    Get details of a specific surgery.
    
    Required header: user-role
    """
    if not RBAC.can_view_surgery(user_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    surgery = repository.get_surgery(surgery_id)
    if not surgery:
        raise HTTPException(status_code=404, detail=f"Surgery {surgery_id} not found")
    
    return add_disclaimer({
        "surgery": surgery,
        "timestamp": datetime.utcnow().isoformat()
    })


@app.post("/check-readiness")
async def check_readiness(
    request: ReadinessCheckRequest,
    user_role: str = Depends(check_readiness_permission)
) -> dict:
    """
    Check if a surgery is ready to proceed.
    
    This endpoint runs the readiness workflow and returns a comprehensive report.
    All outputs require review by qualified clinical personnel.
    
    Required header: user-role (must be OR_COORDINATOR or SUPPLY_ADMIN)
    """
    surgery_id = request.surgery_id
    
    try:
        # Log the check request
        audit_logger.log_action(
            action="CHECK_READINESS_REQUESTED",
            actor_role=user_role,
            entity_type="SURGERY",
            entity_id=surgery_id,
            details={"timestamp": request.requested_at.isoformat()}
        )
        
        # Get surgery
        surgery_dict = repository.get_surgery(surgery_id)
        if not surgery_dict:
            raise HTTPException(status_code=404, detail=f"Surgery {surgery_id} not found")
        
        # PHASE 1: Patient Data Extraction
        from src.models.surgery import SurgeryRequest
        surgery_request = SurgeryRequest(**surgery_dict)
        extraction_result = patient_data_agent.extract_patient_data(surgery_request, surgery_id)
        
        if not extraction_result.extraction_successful:
            return add_disclaimer({
                "success": False,
                "message": "Patient data extraction failed",
                "errors": extraction_result.warnings,
                "readiness_status": "BLOCKED",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # PHASE 2: Safety and Consent Check
        passed, blockers, warnings = safety_consent_agent.check_safety_and_consent(
            extraction_result.extracted_data,
            surgery_id,
            surgery_dict['surgery_type']
        )
        
        if not passed:
            return add_disclaimer({
                "success": False,
                "message": "Safety/Consent check failed",
                "readiness_status": "BLOCKED",
                "blockers": [
                    {
                        "category": b.category,
                        "severity": b.severity,
                        "message": b.message,
                        "suggested_action": b.suggested_action
                    }
                    for b in blockers
                ],
                "warnings": warnings,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # PHASE 3: Blood Bank Check
        blood_available, blood_status, blood_blockers = blood_bank_agent.check_blood_availability(
            surgery_dict['required_blood_type'],
            surgery_dict['required_blood_units'],
            surgery_id,
            surgery_dict['patient_id']
        )
        
        all_blockers = blockers + blood_blockers
        
        # Determine readiness
        if not blood_available or not passed:
            readiness_status = ReadinessStatus.BLOCKED
        else:
            readiness_status = ReadinessStatus.READY
        
        # Build response
        response = {
            "success": True,
            "message": f"Readiness check completed - Status: {readiness_status}",
            "readiness_status": readiness_status,
            "surgery_id": surgery_id,
            "patient_id": surgery_dict['patient_id'],
            "scheduled_time": surgery_dict['scheduled_time'],
            "blood_status": blood_status.model_dump(),
            "blockers": [
                {
                    "category": b.category,
                    "severity": b.severity.value,
                    "message": b.message,
                    "suggested_action": b.suggested_action
                }
                for b in all_blockers
            ],
            "warnings": warnings + extraction_result.warnings,
            "timestamp": datetime.utcnow().isoformat(),
            "review_required": True
        }
        
        audit_logger.log_action(
            action="CHECK_READINESS_COMPLETED",
            actor_role=user_role,
            entity_type="SURGERY",
            entity_id=surgery_id,
            details={"status": readiness_status},
            result="SUCCESS"
        )
        
        return add_disclaimer(response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking readiness for {surgery_id}: {str(e)}")
        
        audit_logger.log_action(
            action="CHECK_READINESS_ERROR",
            actor_role=user_role,
            entity_type="SURGERY",
            entity_id=surgery_id,
            error=str(e),
            result="FAILURE"
        )
        
        return add_disclaimer({
            "success": False,
            "message": "Error checking readiness",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


@app.post("/check-readiness/pipeline")
async def check_readiness_pipeline_llm(
    request: ReadinessCheckRequest,
    user_role: str = Depends(check_readiness_permission)
) -> dict:
    """
    Check surgery readiness using the LLM-per-agent Google ADK orchestration pipeline:

    Patient Data -> Safety/Consent -> [Blood | Organ | Equipment] (parallel)
    -> Validation -> Logistics -> Coordinator -> human review.

    Every stage is its own call to the configured LLM endpoint (gpt-oss-120b
    via OpenRouter - see backend/.env), guided by that agent's own rules
    file under src/adk_pipeline/prompts/. Requires OPENROUTER_API_KEY to be
    set in backend/.env.

    Required header: user-role (must be OR_COORDINATOR or SUPPLY_ADMIN)
    """
    surgery_id = request.surgery_id

    audit_logger.log_action(
        action="LLM_CHECK_READINESS_REQUESTED",
        actor_role=user_role,
        entity_type="SURGERY",
        entity_id=surgery_id,
        details={"timestamp": request.requested_at.isoformat()},
    )

    surgery_dict = repository.get_surgery(surgery_id)
    if not surgery_dict:
        raise HTTPException(status_code=404, detail=f"Surgery {surgery_id} not found")

    report = await run_llm_readiness_pipeline(surgery_id, user_role, repository, audit_logger)
    return add_disclaimer(report)


@app.post("/check-readiness/pipeline/deterministic")
async def check_readiness_pipeline_deterministic(
    request: ReadinessCheckRequest,
    user_role: str = Depends(check_readiness_permission)
) -> dict:
    """
    Check surgery readiness using the deterministic Google ADK orchestration pipeline:

    Patient Data -> Safety/Consent -> [Blood | Organ | Equipment] (parallel)
    -> Validation -> Logistics -> Coordinator -> human review.

    All readiness decisions are made by deterministic ADK BaseAgent stages;
    the coordinator's optional LLM step (only run if GOOGLE_API_KEY is
    configured) only narrates the already-decided result and cannot alter it.

    Required header: user-role (must be OR_COORDINATOR or SUPPLY_ADMIN)
    """
    surgery_id = request.surgery_id

    audit_logger.log_action(
        action="ADK_CHECK_READINESS_REQUESTED",
        actor_role=user_role,
        entity_type="SURGERY",
        entity_id=surgery_id,
        details={"timestamp": request.requested_at.isoformat()},
    )

    surgery_dict = repository.get_surgery(surgery_id)
    if not surgery_dict:
        raise HTTPException(status_code=404, detail=f"Surgery {surgery_id} not found")

    report = await run_readiness_pipeline(surgery_id, user_role, repository, audit_logger)
    return add_disclaimer(report)


@app.get("/audit/{surgery_id}")
async def get_audit_trail(
    surgery_id: str,
    limit: int = Query(100, ge=1, le=1000),
    user_role: str = Depends(verify_role)
) -> dict:
    """
    Get audit trail for a surgery.
    
    Required header: user-role
    """
    if not RBAC.can_view_audit_trail(user_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    trail = audit_logger.get_audit_trail(entity_id=surgery_id, limit=limit)
    
    return add_disclaimer({
        "surgery_id": surgery_id,
        "audit_trail": trail,
        "count": len(trail),
        "timestamp": datetime.utcnow().isoformat()
    })


# ===== Error Handlers =====

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=add_disclaimer({
            "detail": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        })
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
