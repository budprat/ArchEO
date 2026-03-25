# ArchEO-Agent

Archaeological image analysis platform — AI agent with MCP tools for geoglyph detection and Earth observation.

## Quick Start

### Prerequisites
- Python 3.14 with venv at `.venv/`
- Node.js (for frontend)
- `ANTHROPIC_API_KEY` set in `.env` (copy from `.env.example`)

### Start Backend (FastAPI + MCP tools)
```bash
cd api && ../.venv/bin/uvicorn main:app --port 8000
```
This boots 6 MCP tool servers (110 tools) at startup. Health check: `curl http://localhost:8000/api/health`

### Start Frontend (Next.js)
```bash
cd frontend && npm run dev
```
Opens at http://localhost:3000

### Run Tests
```bash
.venv/bin/python -m pytest tests/ -v
```

## Architecture

- **Frontend:** Next.js 16 + Tailwind CSS + shadcn/ui (in `frontend/`)
- **Backend:** FastAPI + LangGraph ReAct agent + Claude Haiku 4.5 vision (in `api/`)
- **MCP Tools:** 5 existing + 1 new Archaeology server (in `agent/tools/`)
- **Streaming:** SSE from FastAPI through Next.js API proxy routes

## Key Directories

| Directory | Purpose |
|-----------|---------|
| `api/` | FastAPI backend (main.py, agent_service.py, file_service.py) |
| `frontend/` | Next.js app (app/, components/, lib/) |
| `agent/tools/` | MCP tool servers (Analysis, Index, Inversion, Perception, Statistics, Archaeology) |
| `uploads/` | File storage for uploaded images and results (gitignored) |
| `tests/` | Python tests (pytest) |
| `docs/superpowers/` | Design spec and implementation plan |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check with MCP status |
| `/api/upload` | POST | Upload image file (multipart) |
| `/api/chat` | POST | Chat with agent (SSE stream) |
| `/api/files/{id}` | GET | Serve uploaded files |
| `/api/results/{id}/{name}` | GET | Serve analysis result images |

## Environment Variables

```
ANTHROPIC_API_KEY=             # Required for Claude
ANTHROPIC_MODEL=claude-haiku-4-5-20251001  # Default model
```
