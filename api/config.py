"""Configuration for ArchEO-Agent API."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
UPLOADS_DIR = PROJECT_ROOT / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

TOOLS_DIR = str(PROJECT_ROOT / "agent" / "tools")
VENV_PYTHON = str(PROJECT_ROOT / ".venv" / "bin" / "python")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4")

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".img", ".hdf"}

SYSTEM_PROMPT = (
    "You are ArchEO-Agent, an AI assistant specialized in archaeological analysis "
    "of satellite and aerial imagery. You combine computer vision analysis with "
    "Earth observation tools to detect geoglyphs, ancient structures, and landscape "
    "modifications. You have access to edge detection, pattern analysis, terrain "
    "analysis, spectral indices, and statistical tools via MCP. Analyze images "
    "step-by-step: first describe what you observe visually, then apply appropriate "
    "tools for quantitative analysis, then interpret results in archaeological "
    "context. Always explain your reasoning and what each tool result means."
)
