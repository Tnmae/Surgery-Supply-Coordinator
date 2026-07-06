# Critical Surgery Supply Coordinator

A **decision-support system** for hospitals to check surgical readiness by coordinating blood bank units, organ availability, and surgical equipment using Google Agent Development Kit (ADK) and a configurable LLM backend.

> ⚠️ **CRITICAL DISCLAIMER**
> This system is for decision-support only. It does **not** authorize surgery, transfusion, organ allocation, or any medical procedure. All outputs must be reviewed and approved by qualified clinical personnel.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [LLM Providers](#llm-providers)
- [API Endpoints](#api-endpoints)
- [Demo Scenarios](#demo-scenarios)
- [Agents](#agents)
- [Security](#security)
- [Deployment](#deployment)
- [Data Models](#data-models)
- [MCP Servers](#mcp-servers)

---

## Overview

The coordinator runs a surgical readiness check end-to-end:

1. **Extracts** patient data and surgery requirements
2. **Verifies** required consents and safety flags
3. **Checks** blood bank availability and compatibility
4. **Checks** organ availability and viability windows (parallel)
5. **Checks** equipment availability and sterilization status (parallel)
6. **Validates** cross-resource compatibility and timing
7. **Estimates** transport and logistics constraints
8. **Produces** a comprehensive pre-operative checklist with a human-readable briefing

Every readiness decision (READY/BLOCKED) is the output of deterministic rules applied to structured agent results. The LLM only narrates and interprets — it never unilaterally decides the status. All findings require **human review** before any clinical action.

---

## Architecture

```
Surgery Request
      │
      ▼
[Patient Data Agent]        ← extracts requirements, validates fields
      │
      ▼
[Safety / Consent Agent]    ← verifies consents, allergies, contraindications
      │
      ▼
┌─────┴──────────────────┐
│     Parallel checks     │
│  [Blood Bank Agent]     │  ← inventory, expiry, crossmatch
│  [Organ Agent]          │  ← registry, compatibility, viability
│  [Equipment Agent]      │  ← availability, sterilization, maintenance
└─────┬──────────────────┘
      │
      ▼
[Validation Agent]          ← cross-resource checks, timing constraints
      │
      ▼
[Logistics Agent]           ← transport ETAs, total timeline
      │
      ▼
[Coordinator Agent]         ← final verdict, checklist, human-readable report
      │
      ▼
  HUMAN REVIEW  (required before any clinical action)
```

Orchestration is a real Google ADK `SequentialAgent` + `ParallelAgent` graph. ADK, not an LLM, decides routing. Each stage's judgment is a single LLM call against that stage's prompt file (`backend/src/adk_pipeline/prompts/*.md`).

---

## Project Structure

```
Surgery-Supply-Coordinator/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── vercel.json                   # Vercel serverless config (optional)
│   ├── api/
│   │   └── index.py                  # Vercel ASGI entry point
│   └── src/
│       ├── main.py                   # FastAPI app & endpoints
│       ├── config.py                 # Configuration (CORS, paths, roles)
│       ├── adk_pipeline/
│       │   ├── llm_client.py         # Multi-provider LLM client
│       │   ├── llm_pipeline.py       # LLM-per-agent pipeline runner
│       │   ├── llm_reasoning_stage.py# Shared BaseAgent for all LLM stages
│       │   ├── llm_stages.py         # Stage factory functions
│       │   ├── pipeline.py           # Deterministic pipeline runner
│       │   ├── coordinator.py        # Coordinator narrator agent
│       │   ├── stages.py             # Deterministic ADK stage wrappers
│       │   ├── state_keys.py         # Session state key constants
│       │   └── prompts/              # Per-agent rules + JSON schemas (8 files)
│       ├── agents/                   # Domain agent implementations (7 files)
│       ├── mcp_servers/              # MCP server wrappers + remote client
│       ├── models/                   # Pydantic models (6 files)
│       ├── data/                     # DataRepository + mock_data.json
│       ├── security/                 # PII redaction, RBAC, audit logger
│       └── logs/
├── frontend/
│   ├── vercel.json                   # Vercel frontend build config
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── App.jsx                   # Single-page React dashboard
│       ├── api.js                    # Fetch wrappers for all backend calls
│       ├── main.jsx
│       └── styles.css
├── external-mcp-server/              # Standalone FastAPI + FastMCP server
│   ├── api/index.py                  # ASGI entry point (also Vercel-ready)
│   ├── tools/mcp_tools.py            # 10 registered MCP tools
│   ├── repository/database_repo.py   # SQLite query layer
│   ├── database/db_setup.py          # Schema + seed script
│   ├── models/schemas.py             # Pydantic schemas
│   └── vercel.json
├── docker-compose.yml
└── demo/
    └── demo_scenarios.json
```

---

## Quick Start

### Option 1 — Docker Compose (recommended for local dev)

```bash
# Copy and fill in credentials
cp backend/.env.example backend/.env

docker compose up --build
# Backend:  http://localhost:8000
# Frontend: http://localhost:5173
```

### Option 2 — Local without Docker

**Backend**
```bash
cd backend
py -3.11 -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
cp .env.example .env          # then fill in LLM credentials
uvicorn src.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
# Create frontend/.env with:  VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

**Verify the LLM endpoint is reachable**
```bash
cd backend
python smoke_test_llm.py
```

---

## LLM Providers

The pipeline makes one LLM call per agent stage (8 calls per readiness check, 3 of which run in parallel). The provider is selected by the `LLM_PROVIDER` environment variable in `backend/.env`. All providers use the same prompt files — only the HTTP client path changes.

### Choosing a provider

| Provider | `LLM_PROVIDER` value | Free tier | Best for |
|---|---|---|---|
| OpenRouter | `openrouter` | ✅ Yes (many free models) | Default; widest model selection |
| Google AI Studio | `google` | ✅ Yes (Gemini 2.0 Flash) | Best JSON output quality |
| Cloudflare Workers AI | `cloudflare` | ✅ Yes (10k neurons/day) | Railway/Vercel deployments |
| Ollama | `ollama` | ✅ Self-hosted | Fully offline / air-gapped |

---

### OpenRouter (default)

OpenRouter proxies 200+ models through a single OpenAI-compatible endpoint. Many are free. Recommended for getting started quickly.

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL=openai/gpt-oss-120b:free
```

**Getting a key:** [openrouter.ai/keys](https://openrouter.ai/keys) — free account, no credit card needed.

**Recommended free models:**

| Model | Notes |
|---|---|
| `openai/gpt-oss-120b:free` | Default; reliable JSON output |
| `meta-llama/llama-3.1-8b-instruct:free` | Faster, lighter |
| `mistralai/mistral-7b-instruct:free` | Good structured output |
| `google/gemma-3-12b-it:free` | Solid alternative |

Browse all free models at [openrouter.ai/models?q=free](https://openrouter.ai/models?q=free).

**Note:** The free tier is rate-limited. The pipeline's parallel stages (blood, organ, equipment) fire 3 concurrent requests — you may see automatic 429 retries in the logs. This is expected and handled with backoff.

---

### Google AI Studio (Gemini)

Gemini is the highest-quality option for structured JSON output. The `responseMimeType: application/json` parameter forces clean JSON with no markdown fences. Recommended if JSON parse failures occur on other providers.

```env
LLM_PROVIDER=google
GOOGLE_AI_API_KEY=AIza...
GOOGLE_AI_MODEL=gemini-2.0-flash
```

**Getting a key:** [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — free, just needs a Google account.

**Available models:**

| Model | Notes |
|---|---|
| `gemini-2.0-flash` | Default; fast, free, excellent JSON |
| `gemini-2.5-flash` | More capable, still free tier |
| `gemini-1.5-pro` | Higher quality, lower rate limits on free |

---

### Cloudflare Workers AI

Cloudflare's inference API runs on their edge network. Good choice when deploying the backend on Railway or Render and you want to avoid OpenRouter rate limits.

```env
LLM_PROVIDER=cloudflare
CLOUDFLARE_API_KEY=cfut_...
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_MODEL=@cf/meta/llama-3.1-8b-instruct
```

**Getting credentials:**
1. [dash.cloudflare.com](https://dash.cloudflare.com) — your Account ID is in the URL after login
2. **Account Settings → API Tokens → Create Token** — use the "Workers AI" template
3. Your model runs at: `https://api.cloudflare.com/client/v4/accounts/{id}/ai/run/{model}`

**Available models** ([full list](https://developers.cloudflare.com/workers-ai/models/)):

| Model | Notes |
|---|---|
| `@cf/meta/llama-3.1-8b-instruct` | Default; fast, free tier |
| `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | More capable, better JSON |
| `@cf/mistral/mistral-7b-instruct-v0.1` | Compact alternative |
| `@cf/google/gemma-7b-it` | Google Gemma on Cloudflare |

**Free tier:** 10,000 neurons/day. Each pipeline run uses ~7-10 requests. That's ~100-150 readiness checks per day before hitting the limit.

---

### Ollama (local / offline)

Ollama runs models entirely on your machine — no API key, no network calls, no rate limits.

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2:latest
OLLAMA_TIMEOUT_SECONDS=60
OLLAMA_MAX_TOKENS=512
```

**Setup:**
1. Download Ollama from [ollama.com](https://ollama.com)
2. Pull a model: `ollama pull llama3.2`
3. Ollama starts automatically on port 11434

**Recommended models:**

| Model | Pull command | Notes |
|---|---|---|
| `llama3.2:latest` | `ollama pull llama3.2` | Default; 3B, fast |
| `llama3.1:8b` | `ollama pull llama3.1:8b` | Better quality |
| `mistral:7b` | `ollama pull mistral:7b` | Good JSON output |
| `qwen2.5:7b` | `ollama pull qwen2.5:7b` | Strong instruction following |

**Note:** Smaller models (3B) may produce inconsistent JSON. If you see parse errors, switch to `llama3.1:8b` or larger. The `OLLAMA_MAX_TOKENS` cap helps prevent runaway generation.

---

### Switching providers at runtime

You only need to change `LLM_PROVIDER` (and ensure the matching credentials are set). No code changes required. Restart the backend after editing `.env`:

```bash
# Docker
docker compose up --build -d backend

# Local
uvicorn src.main:app --reload --port 8000
```

Verify with the smoke test:
```bash
cd backend
python smoke_test_llm.py
```

Or check the health endpoint:
```bash
curl http://localhost:8000/health
# "llm_pipeline_configured": true  ← means credentials are present
```

---

## API Endpoints

### Health
```
GET /health
```
Returns service status plus `llm_pipeline_configured` flag.

### Surgeries
```
GET  /surgeries                          user-role header required
GET  /surgeries/{surgery_id}             user-role header required
```

### Readiness Check
```
POST /check-readiness
Headers: user-role: OR_COORDINATOR
Body:
{
  "surgery_id": "SURG001",
  "user_role": "OR_COORDINATOR",
  "force_rerun": false          // true to bypass cached result
}
```

If a surgery already has a completed review (`RESOLVED` or `HALT_DUE_TO_BLOCKER`), the cached report is returned without re-running the pipeline unless `force_rerun: true` is passed.

### Blocker Decisions
```
POST /surgeries/{surgery_id}/blockers/decision
Headers: user-role: OR_COORDINATOR
Body:
{
  "category": "BLOOD",
  "message": "Blood unit BU-1002 is expired",
  "severity": "CRITICAL",
  "suggested_action": "Request replacement units",
  "decision": "ACCEPT",         // or "REJECT"
  "notes": "Optional freetext"
}
```

This is a pure human sign-off. It does not recompute `readiness_status`. Every decision is permanently appended to the audit trail.

**Review status lifecycle:**
- `PENDING_REVIEW` — report generated, no decisions yet
- `RESOLVED` — all blockers accepted
- `HALT_DUE_TO_BLOCKER` — at least one blocker rejected

### Audit Trail
```
GET /audit/{surgery_id}?limit=100     user-role header required
```

---

## Demo Scenarios

Seven pre-loaded scenarios exercise the full range of pipeline outcomes:

| ID | Scenario | Expected outcome |
|---|---|---|
| SURG001 | All clear | READY |
| SURG002 | Expired blood | BLOCKED |
| SURG003 | Wrong blood type | BLOCKED |
| SURG004 | Organ viability risk | BLOCKED / WARNING |
| SURG005 | Missing equipment | BLOCKED |
| SURG006 | Missing consent | BLOCKED |
| SURG007 | Crossmatch pending | BLOCKED / WARNING |

```bash
# Quick test
curl -X POST http://localhost:8000/check-readiness \
  -H "Content-Type: application/json" \
  -H "user-role: OR_COORDINATOR" \
  -d '{"surgery_id": "SURG001", "user_role": "OR_COORDINATOR"}'
```

---

## Agents

All 8 agents share the same `LlmReasoningStage` base. Each is configured with a different prompt file (`prompts/*.md`) and a deterministic `facts_builder` that gathers ground-truth data before the LLM call.

| Agent | Prompt file | Responsibility |
|---|---|---|
| Patient Data | `patient_data.md` | Extract and validate patient fields |
| Safety / Consent | `safety_consent.md` | Verify consents, allergies, contraindications |
| Blood Bank | `blood_bank.md` | Inventory, expiry, crossmatch |
| Organ | `organ.md` | Registry, compatibility, viability |
| Equipment | `equipment.md` | Availability, sterilization, maintenance |
| Validation | `validation.md` | Cross-resource and timing checks |
| Logistics | `logistics.md` | Transport ETAs, total timeline |
| Coordinator | `coordinator.md` | Final verdict, checklist, narrative |

---

## Security

### PII Redaction
Patient IDs (`PAT\d+`), donor IDs, SSNs, phone numbers, and emails are automatically redacted from anything sent to an external LLM API and from all audit log entries.

### Role-Based Access Control

| Role | Check readiness | View surgeries | Audit trail | Manage inventory |
|---|---|---|---|---|
| `OR_COORDINATOR` | ✅ | ✅ | ✅ | — |
| `SUPPLY_ADMIN` | ✅ | ✅ | ✅ | ✅ |
| `BLOOD_BANK_TECH` | — | ✅ | ✅ | ✅ |
| `ORGAN_COORDINATOR` | — | ✅ | ✅ | ✅ |
| `VIEWER` | — | ✅ | ✅ | — |

Pass the role in the `user-role` request header.

### Audit Log
Append-only JSONL file at `backend/src/logs/audit.log`. Every API call, pipeline run, LLM fallback, and blocker decision is recorded with timestamp, actor role, entity ID, and result. Cannot be modified after creation.

---

## Deployment

### Backend — Railway

1. New Project → Deploy from GitHub → set **Root Directory** to `backend`
2. Railway auto-detects the `Dockerfile`
3. Add environment variables (all from `backend/.env.example`):
   ```
   LLM_PROVIDER=cloudflare          # or openrouter / google
   CLOUDFLARE_API_KEY=...
   CLOUDFLARE_ACCOUNT_ID=...
   CLOUDFLARE_MODEL=@cf/meta/llama-3.1-8b-instruct
   ALLOWED_ORIGINS=https://your-frontend.vercel.app
   ```

### Frontend — Vercel

1. New Project → Import repo → set **Root Directory** to `frontend`
2. `frontend/vercel.json` handles build config automatically
3. Add one environment variable in the Vercel dashboard:
   ```
   VITE_API_BASE_URL=https://your-backend.up.railway.app
   ```
4. Redeploy after adding the variable (Vite bakes it in at build time)

### CORS

Once you have your Vercel URL, add it to the backend's `ALLOWED_ORIGINS` variable on Railway and redeploy:
```
ALLOWED_ORIGINS=http://localhost:5173,https://your-frontend.vercel.app
```

### External MCP Server — Vercel

The `external-mcp-server/` is independently deployable on Vercel:
1. New Project → Import same repo → set **Root Directory** to `external-mcp-server`
2. Seed the database first locally: `python database/db_setup.py`
3. Deploy — SSE endpoint will be at `https://your-mcp.vercel.app/mcp/sse`

---

## Data Models

### Surgery
```json
{
  "surgery_id": "SURG001",
  "patient_id": "PAT001",
  "surgery_type": "Cardiac Bypass",
  "scheduled_time": "2026-07-15T09:00:00",
  "required_blood_type": "O+",
  "required_blood_units": 4,
  "organ_type": null,
  "equipment_list": ["BYPASS_MACHINE", "VENTILATOR"],
  "estimated_duration_minutes": 240,
  "readiness_review_status": "PENDING_REVIEW",
  "blocker_decisions": []
}
```

### Readiness Report Response
```json
{
  "success": true,
  "readiness_status": "BLOCKED",
  "surgery_id": "SURG002",
  "blockers": [
    {
      "category": "BLOOD",
      "severity": "CRITICAL",
      "message": "...",
      "suggested_action": "..."
    }
  ],
  "warnings": [],
  "preop_checklist": [{"item": "...", "completed": false}],
  "human_readable_report": "...",
  "review_required": true,
  "disclaimer": "..."
}
```

---

## MCP Servers

### Internal wrappers (`backend/src/mcp_servers/`)
Python classes that call the external MCP server first, fall back to local `mock_data.json`, then to the in-memory regional fallback:

- **BloodBankMCPServer** — blood unit queries, crossmatch simulation
- **OrganRegistryMCPServer** — organ availability, compatibility, viability
- **EquipmentInventoryMCPServer** — equipment status, sterilization
- **RegionalFallbackMCPServer** — in-memory last-resort regional inventory
- **RemoteMCPClient** — MCP SDK SSE client connecting to the external server

### External server (`external-mcp-server/`)
Standalone FastAPI + FastMCP service, SQLite-backed, with 10 tools:

| Tool | Description |
|---|---|
| `search_blood_inventory` | Blood units by type and hospital |
| `search_organ_registry` | Organs by type and hospital |
| `search_medicine` | Drug catalogue lookup |
| `check_drug_interactions` | Pairwise interaction scan |
| `search_equipment` | Equipment by name and hospital |
| `search_hospital` | Hospital network lookup |
| `search_supplier` | Medical supplier directory |
| `get_storage_requirements` | Temperature and handling requirements |
| `check_resource_availability` | General resource status by ID |
| `get_transport_information` | Vehicle type and ETA between hospitals |

Default URL: `https://external-medical-mcp.vercel.app/mcp/sse`  
Override with: `EXTERNAL_MCP_SSE_URL` in `backend/.env`

---

## Important Notes

1. **No authorization logic** — the system never authorizes any medical procedure
2. **Human review required** — every readiness report has `review_required: true`
3. **LLM fallbacks are safe** — every agent stage has a deterministic fallback if the LLM call fails; the pipeline always completes
4. **Blocker decisions are immutable** — accept/reject decisions are append-only audit entries; they never change the computed `readiness_status`
5. **Writes are ephemeral on serverless** — blocker decisions written to `mock_data.json` persist across requests on Railway (Docker), but are lost on serverless cold starts (Vercel functions). Use a persistent database for production.

---

## License

Provided as-is for educational and demonstration purposes.
