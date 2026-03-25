"""
OpenEO AI Assistant - Main Entry Point.

ABOUTME: FastAPI application providing AI-powered Earth Observation analysis.
Exposes REST and WebSocket endpoints for chat, tutorials, and knowledge base.
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .sdk.client import OpenEOAIClient, OpenEOAIConfig
from .auth.oidc import OIDCUser, get_current_user, get_optional_user
from .auth.middleware import setup_auth_middleware
from .education import KnowledgeBase, TutorialManager
from .education.tutorials import TutorialDifficulty

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Global instances
_client: Optional[OpenEOAIClient] = None
_knowledge_base: Optional[KnowledgeBase] = None
_tutorial_manager: Optional[TutorialManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize and cleanup resources."""
    global _client, _knowledge_base, _tutorial_manager

    logger.info("Initializing OpenEO AI Assistant...")

    # Initialize components
    config = OpenEOAIConfig()
    _client = OpenEOAIClient(config)
    _knowledge_base = KnowledgeBase()
    _tutorial_manager = TutorialManager()

    logger.info("OpenEO AI Assistant initialized successfully")

    yield

    # Cleanup
    logger.info("Shutting down OpenEO AI Assistant...")
    _client = None


# Create FastAPI app
app = FastAPI(
    title="OpenEO AI Assistant",
    description="AI-powered Earth Observation analysis with OpenEO",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup auth middleware (rate limiting, logging)
setup_auth_middleware(app, rate_limit=True, logging=True)


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model."""
    type: str
    content: Optional[str] = None
    session_id: Optional[str] = None
    tool: Optional[str] = None
    result: Optional[dict] = None


class IndexExplanation(BaseModel):
    """Spectral index explanation."""
    name: str
    abbreviation: str
    formula: str
    description: str
    bands_required: list
    applications: list


class TutorialSummary(BaseModel):
    """Tutorial summary for listing."""
    id: str
    title: str
    description: str
    difficulty: str
    estimated_minutes: int
    tags: list


class TutorialProgress(BaseModel):
    """Tutorial progress state."""
    tutorial_id: str
    current_step: int
    total_steps: int
    completed: bool


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "openeo-ai-assistant",
        "version": "1.0.0",
    }


# Chat endpoints
@app.post("/api/chat", response_model=list)
async def chat(
    request: ChatRequest,
    user: OIDCUser = Depends(get_current_user),
):
    """
    Send a chat message and get AI response.

    Requires authentication.
    """
    if not _client:
        raise HTTPException(status_code=503, detail="Service not initialized")

    responses = await _client.chat_sync(
        prompt=request.message,
        user_id=user.user_id,
        session_id=request.session_id,
    )

    return responses


@app.websocket("/ws/chat")
async def chat_websocket(
    websocket: WebSocket,
    token: Optional[str] = None,
):
    """
    WebSocket endpoint for streaming chat.

    Authenticates via token query parameter.
    """
    await websocket.accept()

    if not _client:
        await websocket.send_json({"type": "error", "content": "Service not initialized"})
        await websocket.close()
        return

    # Authenticate
    user = None
    if token:
        try:
            user = await get_current_user(f"Bearer {token}")
        except HTTPException:
            await websocket.send_json({"type": "error", "content": "Invalid token"})
            await websocket.close()
            return
    else:
        # Allow anonymous in dev mode
        if os.environ.get("OPENEO_DEV_MODE", "").lower() == "true":
            from .auth.oidc import create_dev_user
            user = create_dev_user("websocket-user")
        else:
            await websocket.send_json({"type": "error", "content": "Authentication required"})
            await websocket.close()
            return

    session_id = None

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            message = data.get("message", "")
            session_id = data.get("session_id", session_id)

            # Stream responses
            async for response in _client.chat(
                prompt=message,
                user_id=user.user_id,
                session_id=session_id,
            ):
                await websocket.send_json(response)

                # Update session_id if returned
                if response.get("type") == "session":
                    session_id = response.get("session_id")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user.user_id}")


# Knowledge Base endpoints
@app.get("/api/indices")
async def list_indices(category: Optional[str] = None):
    """List available spectral indices."""
    if not _knowledge_base:
        raise HTTPException(status_code=503, detail="Service not initialized")

    indices = _knowledge_base.list_indices(category=category)

    return [
        {
            "name": idx.name,
            "abbreviation": idx.abbreviation,
            "description": idx.description,
            "applications": idx.applications,
        }
        for idx in indices
    ]


@app.get("/api/indices/{index_name}", response_model=IndexExplanation)
async def get_index(index_name: str):
    """Get details about a spectral index."""
    if not _knowledge_base:
        raise HTTPException(status_code=503, detail="Service not initialized")

    idx = _knowledge_base.get_index(index_name)
    if not idx:
        raise HTTPException(status_code=404, detail=f"Index not found: {index_name}")

    return IndexExplanation(
        name=idx.name,
        abbreviation=idx.abbreviation,
        formula=idx.formula,
        description=idx.description,
        bands_required=idx.bands_required,
        applications=idx.applications,
    )


@app.get("/api/indices/{index_name}/explain")
async def explain_index(index_name: str):
    """Get a human-readable explanation of a spectral index."""
    if not _knowledge_base:
        raise HTTPException(status_code=503, detail="Service not initialized")

    explanation = _knowledge_base.explain_index(index_name)

    return {"index": index_name, "explanation": explanation}


@app.get("/api/concepts")
async def list_concepts(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
):
    """List EO concepts."""
    if not _knowledge_base:
        raise HTTPException(status_code=503, detail="Service not initialized")

    from .education.knowledge_base import ConceptCategory

    cat = None
    if category:
        try:
            cat = ConceptCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

    concepts = _knowledge_base.list_concepts(category=cat, difficulty=difficulty)

    return [
        {
            "id": c.id,
            "title": c.title,
            "category": c.category.value,
            "summary": c.summary,
            "difficulty": c.difficulty,
        }
        for c in concepts
    ]


@app.get("/api/concepts/{concept_id}")
async def get_concept(concept_id: str):
    """Get details about an EO concept."""
    if not _knowledge_base:
        raise HTTPException(status_code=503, detail="Service not initialized")

    concept = _knowledge_base.get_concept(concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"Concept not found: {concept_id}")

    return {
        "id": concept.id,
        "title": concept.title,
        "category": concept.category.value,
        "summary": concept.summary,
        "detailed_explanation": concept.detailed_explanation,
        "examples": concept.examples,
        "related_concepts": concept.related_concepts,
        "code_examples": concept.code_examples,
        "difficulty": concept.difficulty,
        "tags": concept.tags,
    }


@app.get("/api/search")
async def search_knowledge(query: str):
    """Search the knowledge base."""
    if not _knowledge_base:
        raise HTTPException(status_code=503, detail="Service not initialized")

    results = _knowledge_base.search(query)

    return {
        "query": query,
        "indices": [
            {"abbreviation": idx.abbreviation, "name": idx.name}
            for idx in results["indices"]
        ],
        "concepts": [
            {"id": c.id, "title": c.title}
            for c in results["concepts"]
        ],
    }


# Tutorial endpoints
@app.get("/api/tutorials", response_model=list)
async def list_tutorials(
    difficulty: Optional[str] = None,
    tag: Optional[str] = None,
):
    """List available tutorials."""
    if not _tutorial_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    diff = None
    if difficulty:
        try:
            diff = TutorialDifficulty(difficulty)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid difficulty: {difficulty}")

    tutorials = _tutorial_manager.list_tutorials(difficulty=diff, tag=tag)

    return [
        TutorialSummary(
            id=t.id,
            title=t.title,
            description=t.description,
            difficulty=t.difficulty.value,
            estimated_minutes=t.estimated_minutes,
            tags=t.tags,
        )
        for t in tutorials
    ]


@app.get("/api/tutorials/{tutorial_id}")
async def get_tutorial(tutorial_id: str):
    """Get a tutorial with all steps."""
    if not _tutorial_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    tutorial = _tutorial_manager.get_tutorial(tutorial_id)
    if not tutorial:
        raise HTTPException(status_code=404, detail=f"Tutorial not found: {tutorial_id}")

    return tutorial.to_dict()


@app.post("/api/tutorials/{tutorial_id}/start", response_model=TutorialProgress)
async def start_tutorial(
    tutorial_id: str,
    user: OIDCUser = Depends(get_current_user),
):
    """Start a tutorial for the current user."""
    if not _tutorial_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        progress = _tutorial_manager.start_tutorial(tutorial_id, user.user_id)
        tutorial = _tutorial_manager.get_tutorial(tutorial_id)

        return TutorialProgress(
            tutorial_id=tutorial_id,
            current_step=progress["current_step"],
            total_steps=tutorial.total_steps,
            completed=progress["completed"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/tutorials/{tutorial_id}/advance", response_model=TutorialProgress)
async def advance_tutorial(
    tutorial_id: str,
    user: OIDCUser = Depends(get_current_user),
):
    """Advance to the next step in a tutorial."""
    if not _tutorial_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        progress = _tutorial_manager.advance_step(tutorial_id, user.user_id)
        tutorial = _tutorial_manager.get_tutorial(tutorial_id)

        return TutorialProgress(
            tutorial_id=tutorial_id,
            current_step=progress["current_step"],
            total_steps=tutorial.total_steps,
            completed=progress["completed"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/tutorials/{tutorial_id}/progress", response_model=Optional[TutorialProgress])
async def get_tutorial_progress(
    tutorial_id: str,
    user: OIDCUser = Depends(get_current_user),
):
    """Get current progress in a tutorial."""
    if not _tutorial_manager:
        raise HTTPException(status_code=503, detail="Service not initialized")

    progress = _tutorial_manager.get_progress(tutorial_id, user.user_id)
    if not progress:
        return None

    tutorial = _tutorial_manager.get_tutorial(tutorial_id)

    return TutorialProgress(
        tutorial_id=tutorial_id,
        current_step=progress["current_step"],
        total_steps=tutorial.total_steps,
        completed=progress["completed"],
    )


def create_app() -> FastAPI:
    """Factory function to create the FastAPI app."""
    return app


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("OPENEO_AI_PORT", "8001"))
    host = os.environ.get("OPENEO_AI_HOST", "0.0.0.0")

    uvicorn.run(
        "openeo_ai.main:app",
        host=host,
        port=port,
        reload=True,
    )
