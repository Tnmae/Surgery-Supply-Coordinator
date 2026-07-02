import logging
import sys
from pathlib import Path

# Add project root to path to ensure modules are importable in Vercel serverless environment
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tools.mcp_tools import mcp

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-api-server")

# Create FastAPI application
app = FastAPI(
    title="External Medical Resources API",
    description="Standalone medical resources registry exposing blood bank, organ registries, and drug catalgues via Model Context Protocol (MCP)",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the MCP HTTP server endpoints
# Exposes /sse and /messages under /mcp prefix (e.g. /mcp/sse, /mcp/messages)
app.mount("/mcp", mcp.sse_app())

@app.get("/")
@app.get("/health")
def health_check():
    """Service health and connection summary."""
    return {
        "status": "healthy",
        "service": "External Medical Resources MCP Server",
        "mcp_version": "1.0.0",
        "sse_endpoint": "/mcp/sse",
        "messages_endpoint": "/mcp/messages"
    }
