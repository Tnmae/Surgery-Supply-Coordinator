# Critical Surgery Supply Coordinator

A **decision-support system** for hospitals to check surgical readiness by coordinating blood bank units, organ availability, and surgical equipment using Google Agent Development Kit (ADK).

## ⚠️ CRITICAL DISCLAIMER

**This system is for decision-support only. It does NOT authorize surgery, transfusion, organ allocation, or any medical procedure. All outputs must be reviewed and approved by qualified clinical personnel.**

## Overview

The Critical Surgery Supply Coordinator is a multi-agent system that:

1. **Extracts** patient data and surgery requirements
2. **Verifies** required consents and safety flags
3. **Checks** blood bank availability and compatibility
4. **Checks** organ availability and viability windows
5. **Checks** equipment availability and sterilization status
6. **Validates** resource compatibility and relevance
7. **Estimates** transport and timing constraints
8. **Produces** a comprehensive pre-operative checklist

All decisions are subject to **human review** before any medical action is taken.

## Architecture

```
Surgery Request
    ↓
[Patient Data Agent] → Extract requirements
    ↓
[Safety/Consent Agent] → Verify consents & flags
    ↓
[Parallel Resource Agents]
├─ [Blood Bank Agent] → Check blood availability
├─ [Organ Agent] → Check organ availability
└─ [Equipment Agent] → Check equipment
    ↓
[Validation Agent] → Cross-check compatibility
    ↓
[Logistics Agent] → Time estimation
    ↓
[Coordinator Agent] → Generate report
    ↓
HUMAN REVIEW (REQUIRED)
```

## Project Structure

```
critical-surgery-supply-coordinator/
├── README.md
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── main.py                    # FastAPI entry point
│   │   ├── config.py                  # Configuration
│   │   ├── models/                    # Pydantic models
│   │   ├── agents/                    # Agent implementations
│   │   ├── mcp_servers/               # Mock MCP servers
│   │   ├── data/                      # Data repository & mock data
│   │   ├── security/                  # PII redaction, RBAC, audit
│   │   └── workflows/                 # Workflow orchestration
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── src/                           # React + Vite web frontend
└── demo/
    └── demo_scenarios.json
```

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
cd critical-surgery-supply-coordinator

# Start both backend and frontend
docker compose up --build

# Backend will be at: http://localhost:8000
# Frontend will be at: http://localhost:5173
```

### Option 2: Local Development

#### Backend Setup

```bash
# Install Python 3.11 and verify the interpreter explicitly
py -3.11 --version  # On Windows, confirm Python 3.11 is available

# Navigate to backend
cd backend

# Create virtual environment with Python 3.11
py -3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
uvicorn src.main:app --reload --port 8000
```

Backend will be available at: `http://localhost:8000`

#### Frontend Setup

```bash
# In a separate terminal
cd frontend

# Install dependencies
npm install

# Run frontend
npm run dev
```

Frontend will be available at: `http://localhost:5173`

## API Endpoints

### Health Check
```bash
GET /health
```

### Surgery Management
```bash
# List all pending surgeries
GET /surgeries
Headers: user-role: OR_COORDINATOR

# Get surgery details
GET /surgeries/{surgery_id}
Headers: user-role: OR_COORDINATOR

# Check readiness (deterministic Python workflow, Phase 1 agents only)
POST /check-readiness
Headers: user-role: OR_COORDINATOR
Body: {
  "surgery_id": "SURG001",
  "user_role": "OR_COORDINATOR",
  "requested_at": "2026-06-29T14:00:00"
}

# Check readiness via the full Google ADK orchestration pipeline
# (all 8 agents; SequentialAgent + ParallelAgent; see "ADK Pipeline" below)
POST /check-readiness/pipeline
Headers: user-role: OR_COORDINATOR
Body: (same as above)
```

### Audit Trail
```bash
# Get audit trail for a surgery
GET /audit/{surgery_id}?limit=100
Headers: user-role: OR_COORDINATOR
```

## Demo Scenarios

The system includes 7 pre-configured demo scenarios:

1. **SURG001** - All Clear: All resources available
2. **SURG002** - Expired Blood: Blood available but expired
3. **SURG003** - Wrong Blood Type: Only wrong type available
4. **SURG004** - Organ Viability Risk: Organ approaching viability window limit
5. **SURG005** - Missing Equipment: Required equipment unavailable
6. **SURG006** - Missing Consent: Critical consent not obtained
7. **SURG007** - Crossmatch Pending: Blood units pending crossmatch testing

### Test a Demo Scenario

```bash
curl -X POST http://localhost:8000/check-readiness \
  -H "Content-Type: application/json" \
  -H "user-role: OR_COORDINATOR" \
  -d '{
    "surgery_id": "SURG001",
    "user_role": "OR_COORDINATOR",
    "requested_at": "2026-06-29T14:00:00"
  }'
```

## Agents

### 1. Patient Data Agent
- Extracts patient information from surgery request
- Validates blood type and other requirements
- Checks for missing fields
- Identifies potential medical concerns

### 2. Safety/Consent Agent
- Verifies required consents are in place and valid
- Checks for expired consents
- Identifies allergies and contraindications
- Flags medication interactions

### 3. Blood Bank Agent
- Queries local blood bank inventory
- Checks blood type compatibility
- Verifies unit expiration dates
- Checks crossmatch status
- Falls back to regional inventory if needed

### 4. Organ Agent
- Queries organ registry
- Checks donor-recipient compatibility
- Verifies viability windows
- Falls back to regional network if needed

### 5. Equipment Agent
- Queries equipment inventory
- Verifies sterilization status
- Checks maintenance schedules
- Confirms all required equipment is available

### 6. Validation Agent
- Cross-checks resource compatibility (organ viability vs. procedure duration, pending crossmatch vs. transplant, etc.)
- Validates timing constraints
- Ensures all requirements are met

### 7. Logistics Agent
- Estimates regional transport times for blood/organ fallback
- Calculates total procedure timeline
- Identifies time-critical constraints

### 8. Coordinator Agent
- Deterministically aggregates findings from all agents into the final readiness status (READY/BLOCKED) - never LLM-decided
- Generates the pre-operative checklist
- Optionally uses an LLM (Gemini, via Google ADK) to turn the already-finalized structured result into a human-readable narrative briefing - see "ADK Pipeline" below

## ADK Pipeline

`POST /check-readiness/pipeline` runs the 8-agent architecture above as an
actual Google ADK orchestration graph (`backend/src/adk_pipeline/`):

```
SequentialAgent(
    PatientDataStage, SafetyConsentStage,
    ParallelAgent(BloodBankStage, OrganStage, EquipmentStage),
    ValidationStage, LogisticsStage, AggregatorStage,
    [coordinator_narrator]   # LLM step, gemini-flash-latest
)
```

Every stage through `AggregatorStage` is a deterministic `BaseAgent` - no LLM
involved - so the READY/BLOCKED verdict and blockers can never be
hallucinated. The **only** LLM step is the final `coordinator_narrator`
(`Agent` with `model="gemini-flash-latest"`), which reads the
already-decided, PII-redacted result and writes a short human-readable
briefing. It cannot change the status.

The LLM step only runs if `GOOGLE_API_KEY` (or Vertex AI credentials) is set
in `backend/.env` (see `backend/.env.example`). Without it, the pipeline
still runs end-to-end and returns a template-based narrative instead - check
`adk_coordinator_llm_configured` on `GET /health` or `coordinator_used_llm`
on the pipeline response to see which mode is active.

## Security Features

### PII Redaction
- All personally identifiable information is redacted in logs
- Patient IDs, donor IDs, SSNs, phone numbers, emails are masked
- Audit trails contain only redacted data

### Role-Based Access Control (RBAC)
- **OR_COORDINATOR**: Can check readiness, view surgeries and audit trails
- **SUPPLY_ADMIN**: Full access including inventory management
- **BLOOD_BANK_TECH**: Can manage inventory and view audit trails
- **ORGAN_COORDINATOR**: Can manage inventory and view audit trails
- **VIEWER**: Read-only access to surgeries and audit trails

### Immutable Audit Log
- Every agent action is logged
- Logs are append-only (immutable)
- Cannot be modified after creation
- Includes timestamp, actor, action, and result

### Input Validation
- All inputs validated with Pydantic models
- Type checking on all parameters
- Default values for optional fields

## Data Models

### Surgery
- `surgery_id`: Unique identifier
- `patient_id`: Patient identifier
- `surgery_type`: Type of surgery
- `scheduled_time`: Scheduled surgery time
- `required_blood_type`: Blood type needed
- `required_blood_units`: Number of units
- `organ_type`: Optional organ type for transplants
- `equipment_list`: Required equipment
- `estimated_duration_minutes`: Estimated duration

### Patient
- `patient_id`: Unique identifier
- `blood_type`: ABO blood type
- `allergies`: List of known allergies with severity
- `contraindications`: Medical contraindications
- `consents`: List of valid consents with expiration dates
- `medications`: Current medications
- `prior_surgeries`: Count of previous surgeries

### Blood Unit
- `unit_id`: Unique identifier
- `blood_type`: ABO blood type
- `collected_date`: Collection date
- `expiration_date`: Expiration date
- `status`: AVAILABLE, RESERVED, IN_USE, EXPIRED, etc.
- `crossmatch_status`: COMPATIBLE, INCOMPATIBLE, PENDING, NOT_PERFORMED
- `unit_volume_ml`: Volume in milliliters (typically 450)

### Readiness Report
- `status`: READY, NOT_READY, or BLOCKED
- `blockers`: List of critical issues preventing readiness
- `warnings`: List of non-blocking concerns
- `resource_status`: Status of each resource check
- `preop_checklist`: Pre-operative checklist items
- `disclaimer`: Decision-support disclaimer

## MCP Servers

The system includes mock implementations of these MCP-style servers:

### blood_bank_mcp
- `query_blood_availability()`: Check availability by blood type
- `get_blood_units()`: Get list of available units
- `check_crossmatch()`: Verify crossmatch compatibility

### organ_registry_mcp
- `query_organ_availability()`: Check organ availability
- `get_organs()`: Get list of available organs
- `check_donor_compatibility()`: Verify donor-recipient match
- `get_viability_estimate()`: Check remaining viability time

### equipment_inventory_mcp
- `query_equipment_availability()`: Check equipment availability
- `get_equipment()`: Get equipment details
- `check_sterilization_status()`: Verify sterilization
- `check_maintenance_status()`: Check maintenance schedule

### regional_fallback_mcp
- `query_blood_availability()`: Check regional blood inventory
- `query_organ_availability()`: Check regional organ availability
- `request_blood_transfer()`: Request blood from regional network
- `request_organ_transfer()`: Request organ from regional network

## Configuration

Edit `backend/src/config.py` to customize:
- Application name and version
- API settings
- Security settings
- Data paths
- Logging levels
- Disclaimer text

## Testing

```bash
# Run the health check
curl http://localhost:8000/health

# List surgeries
curl -H "user-role: OR_COORDINATOR" http://localhost:8000/surgeries

# Test readiness check with demo scenario
curl -X POST http://localhost:8000/check-readiness \
  -H "user-role: OR_COORDINATOR" \
  -H "Content-Type: application/json" \
  -d '{
    "surgery_id": "SURG001",
    "user_role": "OR_COORDINATOR",
    "requested_at": "2026-06-29T14:00:00Z"
  }'
```

## Roadmap

### Phase 1 ✅ (Current)
- ✅ Project structure and Pydantic models
- ✅ Mock data with demo scenarios
- ✅ MCP-style mock servers
- ✅ Patient Data Agent
- ✅ Safety/Consent Agent
- ✅ Blood Bank Agent
- ✅ FastAPI skeleton
- ✅ React web frontend (basic)
- ✅ PII redaction and RBAC
- ✅ Audit logging

### Phase 2 ✅
- ✅ Organ Agent (full implementation)
- ✅ Equipment Agent (full implementation)
- ✅ Validation Agent
- ✅ Logistics Agent
- ✅ Coordinator Agent (deterministic aggregation + optional LLM narrative)
- ✅ Google ADK orchestration pipeline (`POST /check-readiness/pipeline`)
- ⬜ Frontend enhancements
- ⬜ Integration tests

### Phase 3 (Future)
- ⬜ Database backend (SQLite or PostgreSQL)
- ⬜ Real MCP server implementation
- ⬜ Advanced reporting and analytics
- ⬜ Performance optimization
- ⬜ Production deployment configuration

## Important Notes

1. **No Authorization Logic**: This system does not authorize any medical procedures
2. **Human Review Required**: All outputs must be reviewed by qualified personnel
3. **Mock Data Only**: Current implementation uses mock data for demonstration
4. **PII Protection**: All personally identifiable information is redacted in logs
5. **Immutable Audit Trail**: All actions are permanently logged
6. **Decision Support Only**: System provides recommendations only

## License

This project is provided as-is for educational and demonstration purposes.

## Support

For issues or questions:
1. Check the audit logs for detailed action history
2. Review the frontend for real-time readiness status
3. Consult with qualified clinical personnel for any medical decisions
