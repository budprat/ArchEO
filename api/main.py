"""FastAPI application for ArchEO-Agent."""

import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from agent_service import get_mcp_status, shutdown_mcp, startup_mcp, stream_agent_response
from config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE, UPLOADS_DIR
from file_service import process_upload

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Lifespan: boot / teardown MCP servers
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_mcp()
    yield
    await shutdown_mcp()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="ArchEO-Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class HistoryEntry(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    file_id: Optional[str] = None
    history: list[HistoryEntry] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    """Health check — returns degraded if MCP servers failed to load."""
    mcp = get_mcp_status()
    status = "ok" if mcp["agent_ready"] else "degraded"
    return {"status": status, "mcp_servers": mcp}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Accept a satellite/aerial image and run the upload pipeline."""
    # Validate extension
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    # Stream to temp file to check size before processing
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        total = 0
        while True:
            chunk = await file.read(1024 * 64)  # 64 KB chunks
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_SIZE:
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE // 1024 // 1024} MB.",
                )
            tmp.write(chunk)

    try:
        result = process_upload(
            file_path=str(tmp_path),
            original_name=file.filename or f"upload{ext}",
            uploads_dir=str(UPLOADS_DIR),
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    return result


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Stream agent response as SSE."""
    history_dicts = [entry.model_dump() for entry in request.history]

    async def event_generator():
        async for chunk in stream_agent_response(
            message=request.message,
            file_id=request.file_id,
            history=history_dicts,
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/files/{file_id}")
async def get_file(
    file_id: str,
    type: str = Query(default="thumbnail", pattern="^(thumbnail|original)$"),
):
    """Serve thumbnail or original file for a given file_id."""
    upload_dir = UPLOADS_DIR / file_id
    if not upload_dir.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    if type == "thumbnail":
        path = upload_dir / "thumbnail.png"
        if not path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail not found.")
        return FileResponse(str(path), media_type="image/png")

    # type == "original" — find the original file (any extension)
    candidates = [
        p for p in upload_dir.iterdir()
        if p.stem == "original" and p.suffix.lower() != ".png"
    ]
    # Fallback: any file named original.*
    if not candidates:
        candidates = [p for p in upload_dir.iterdir() if p.stem == "original"]

    if not candidates:
        raise HTTPException(status_code=404, detail="Original file not found.")

    original = candidates[0]
    return FileResponse(str(original), filename=original.name)


@app.get("/api/results/{file_id}/{result_name}")
async def get_result(file_id: str, result_name: str):
    """Serve an analysis result image."""
    result_path = UPLOADS_DIR / file_id / "results" / result_name
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Result not found.")

    suffix = result_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    media_type = media_types.get(suffix, "application/octet-stream")
    return FileResponse(str(result_path), media_type=media_type)
