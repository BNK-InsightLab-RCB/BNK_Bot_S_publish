"""Chat API."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.agents.supervisor import SupervisorAgent
from backend.app.runtime_store import RuntimeStore
from backend.app.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    """Answer a branch-support question."""
    response = SupervisorAgent().handle(
        question=request.question,
        user_role=request.user_role,
        screen_id=request.screen_id,
        screen_name=request.screen_name,
    )
    if not request.include_sources:
        response["sources"] = []
    RuntimeStore().append_chat(request.question, request.user_role, response)
    return response
