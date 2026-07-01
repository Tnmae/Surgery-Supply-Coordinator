"""Configuration management."""

from pathlib import Path
from typing import Optional


class Config:
    """Application configuration."""
    
    # Application
    APP_NAME = "Critical Surgery Supply Coordinator"
    APP_VERSION = "1.0.0"
    DEBUG = False
    
    # Paths
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    LOG_DIR = BASE_DIR / "logs"
    
    # API
    API_TITLE = "Surgery Supply Coordination API"
    API_DESCRIPTION = "Decision-support system for surgical readiness"
    API_VERSION = "1.0.0"
    
    # Security
    REQUIRE_AUTH = False
    VALID_ROLES = ["OR_COORDINATOR", "SUPPLY_ADMIN", "BLOOD_BANK_TECH", "ORGAN_COORDINATOR", "VIEWER"]
    
    # Data
    MOCK_DATA_FILE = DATA_DIR / "mock_data.json"
    
    # Disclaimer
    DISCLAIMER = (
        "This system is for decision-support only. It does not authorize surgery, "
        "transfusion, organ allocation, or any medical procedure. All outputs must be "
        "reviewed and approved by qualified clinical personnel."
    )
    
    # Logging
    LOG_LEVEL = "INFO"
    AUDIT_LOG_FILE = LOG_DIR / "audit.log"
    
    @classmethod
    def ensure_directories_exist(cls) -> None:
        """Create necessary directories if they don't exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
