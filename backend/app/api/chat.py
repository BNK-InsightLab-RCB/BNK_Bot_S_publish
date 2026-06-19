"""Chat API."""

from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter

from backend.app.agents.supervisor import SupervisorAgent
from backend.app.runtime_store import RuntimeStore
from backend.app.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    """Answer a branch-support question."""
    started = perf_counter()
    response = SupervisorAgent().handle(
        question=request.question,
        user_role=request.user_role,
        screen_id=request.screen_id,
        screen_name=request.screen_name,
    )
    duration_ms = int((perf_counter() - started) * 1000)
    metadata = response.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata["duration_ms"] = duration_ms
    if not request.include_sources:
        response["sources"] = []
    RuntimeStore().append_chat(request.question, request.user_role, response, duration_ms=duration_ms)
    return response
