"""now entry point for the FastAPI backend.

Vercel looks for a callable named `app` in api/index.py.
We just import the existing FastAPI app — no changes to src/ needed.
"""
import sys
from pathlib import Path

# Make `src` importable from the Vercel function context
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.main import app  # noqa: F401  — Vercel picks this up as the ASGI app
