# ABOUTME: Main package for OpenEO AI Assistant.
# Exports all core classes: Claude client, tools, storage, GeoAI, visualization, and chat interface.

"""
OpenEO AI Assistant

AI-powered Earth Observation analysis using OpenEO and Claude SDK.

Modules:
- sdk: Claude SDK client and session management
- tools: OpenEO tools for process graph generation and job management
- storage: Database models and repositories for AI sessions
- geoai: AI-powered analysis (segmentation, change detection)
- visualization: MCP-UI compatible map and chart components
- chat_interface: Interactive terminal chat for natural language analysis
"""

__version__ = "0.1.0"

# Core SDK exports
from .sdk.client import OpenEOAIClient, OpenEOAIConfig

# Chat interface
from .chat_interface import ChatInterface, run_chat

# Web interface
from .web_interface import app as web_app, run_server

# Tools exports
from .tools.openeo_tools import OpenEOTools
from .tools.job_tools import JobTools
from .tools.validation_tools import ValidationTools

# Storage exports
from .storage.models import AISession, SavedProcessGraph, Tag, ExecutionHistory
from .storage.repositories import (
    SessionRepository,
    ProcessGraphRepository,
    TagRepository,
    ExecutionHistoryRepository
)

# GeoAI exports
from .geoai.inference import GeoAIInference
from .geoai.model_registry import ModelRegistry

# Visualization exports
from .visualization.maps import MapComponent
from .visualization.charts import ChartComponent

__all__ = [
    # Version
    "__version__",
    # SDK
    "OpenEOAIClient",
    "OpenEOAIConfig",
    # Chat Interface
    "ChatInterface",
    "run_chat",
    # Web Interface
    "web_app",
    "run_server",
    # Tools
    "OpenEOTools",
    "JobTools",
    "ValidationTools",
    # Storage
    "AISession",
    "SavedProcessGraph",
    "Tag",
    "ExecutionHistory",
    "SessionRepository",
    "ProcessGraphRepository",
    "TagRepository",
    "ExecutionHistoryRepository",
    # GeoAI
    "GeoAIInference",
    "ModelRegistry",
    # Visualization
    "MapComponent",
    "ChartComponent",
]
