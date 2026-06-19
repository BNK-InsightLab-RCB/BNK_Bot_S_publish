"""Admin and health API."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.config import settings
from backend.app.schemas import HealthResponse
from backend.app.storage.elastic import KnowledgeIndex


router = APIRouter(prefix="/api", tags=["admin"])


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Return backend health."""
    azure_ready = bool(settings.azure_search_endpoint)
    foundry_ready = bool(settings.foundry_project_endpoint and settings.foundry_model_deployment)
    foundry_tool_ready = bool(settings.foundry_ai_search_connection_id or settings.foundry_agent_name)
    return {
        "status": "ok",
        "index_name": settings.elastic_index,
        "rag_provider": settings.rag_provider,
        "azure_search_configured": azure_ready,
        "foundry_configured": foundry_ready,
        "foundry_search_tool_configured": foundry_tool_ready,
        "ms_route": _ms_route(azure_ready, foundry_ready, foundry_tool_ready),
    }


@router.post("/admin/reset")
def reset_index() -> dict:
    """Reset local and Elasticsearch indexes."""
    KnowledgeIndex().reset()
    return {"status": "reset"}


def _ms_route(azure_ready: bool, foundry_ready: bool, foundry_tool_ready: bool) -> str:
    if azure_ready and foundry_ready and foundry_tool_ready:
        return "foundry_search_tool"
    if azure_ready and foundry_ready:
        return "azure_search_then_foundry_context"
    if azure_ready:
        return "azure_search_local_answer"
    return "local"
