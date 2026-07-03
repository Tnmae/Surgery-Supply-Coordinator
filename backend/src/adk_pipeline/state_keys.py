"""Session state key constants shared across ADK pipeline stages."""

SURGERY_ID = "surgery_id"
USER_ROLE = "user_role"
REQUESTED_AT = "requested_at"
SURGERY_DICT = "surgery_dict"

PATIENT_EXTRACTION_OK = "patient_extraction_ok"
PATIENT_DATA = "patient_data"
PATIENT_MISSING_FIELDS = "patient_missing_fields"
PATIENT_WARNINGS = "patient_warnings"

SAFETY_PASSED = "safety_passed"
SAFETY_BLOCKERS = "safety_blockers"
SAFETY_WARNINGS = "safety_warnings"

BLOOD_AVAILABLE = "blood_available"
BLOOD_STATUS = "blood_status"
BLOOD_BLOCKERS = "blood_blockers"

ORGAN_AVAILABLE = "organ_available"
ORGAN_STATUS = "organ_status"
ORGAN_BLOCKERS = "organ_blockers"

EQUIPMENT_AVAILABLE = "equipment_available"
EQUIPMENT_STATUS = "equipment_status"
EQUIPMENT_BLOCKERS = "equipment_blockers"

VALIDATION_PASSED = "validation_passed"
VALIDATION_BLOCKERS = "validation_blockers"
VALIDATION_WARNINGS = "validation_warnings"

LOGISTICS = "logistics"
LOGISTICS_WARNINGS = "logistics_warnings"

FINAL_STATUS = "final_status"
ALL_BLOCKERS = "all_blockers"
ALL_WARNINGS = "all_warnings"
PREOP_CHECKLIST = "preop_checklist"

COORDINATOR_NARRATIVE = "coordinator_narrative"
PIPELINE_ERROR = "pipeline_error"

# --- LLM-per-agent pipeline (each agent is its own LLM API call) ---
PATIENT_LLM_RESULT = "patient_llm_result"
SAFETY_LLM_RESULT = "safety_llm_result"
BLOOD_LLM_RESULT = "blood_llm_result"
ORGAN_LLM_RESULT = "organ_llm_result"
EQUIPMENT_LLM_RESULT = "equipment_llm_result"
VALIDATION_LLM_RESULT = "validation_llm_result"
LOGISTICS_LLM_RESULT = "logistics_llm_result"
COORDINATOR_LLM_RESULT = "coordinator_llm_result"
