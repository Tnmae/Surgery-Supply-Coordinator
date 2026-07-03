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
from src.models.report import ReadinessCheckRequest, ReadinessCheckResponse, ReadinessReport, BlockerDecisionRequest
from src.models.surgery import Surgery, SurgeryDetail
from src.security.rbac import RBAC, Permission
from src.security.audit_logger import AuditLogger
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
    Check surgery readiness using the LLM-per-agent Google ADK orchestration pipeline:

    Patient Data -> Safety/Consent -> [Blood | Organ | Equipment] (parallel)
    -> Validation -> Logistics -> Coordinator -> human review.

    Agents fire automatically in this sequence; every stage is its own call
    to the configured LLM endpoint (gpt-oss-120b via OpenRouter - see
    backend/.env), guided by that agent's own rules file under
    src/adk_pipeline/prompts/. The resulting report still requires review by
    qualified clinical personnel before any action is taken. Requires
    OPENROUTER_API_KEY to be set in backend/.env.

    Required header: user-role (must be OR_COORDINATOR or SUPPLY_ADMIN)
    """
    surgery_id = request.surgery_id

    audit_logger.log_action(
        action="CHECK_READINESS_REQUESTED",
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


@app.post("/surgeries/{surgery_id}/blockers/decision")
async def record_blocker_decision(
    surgery_id: str,
    request: BlockerDecisionRequest,
    user_role: str = Depends(check_readiness_permission),
) -> dict:
    """
    Record a clinician's accept/reject decision on a single blocker from a
    readiness report. This does not recompute readiness_status - the pipeline's
    verdict stands as-is. It is purely a human sign-off, appended to the
    existing immutable audit trail (see GET /audit/{surgery_id}).

    Required header: user-role (must be OR_COORDINATOR or SUPPLY_ADMIN)
    """
    entry_id = audit_logger.log_action(
        action="BLOCKER_DECISION",
        actor_role=user_role,
        entity_type="SURGERY",
        entity_id=surgery_id,
        details=request.model_dump(),
        result=request.decision,
    )

    return add_disclaimer({
        "success": True,
        "entry_id": entry_id,
        "surgery_id": surgery_id,
        "category": request.category,
        "decision": request.decision,
        "timestamp": datetime.utcnow().isoformat(),
    })


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
