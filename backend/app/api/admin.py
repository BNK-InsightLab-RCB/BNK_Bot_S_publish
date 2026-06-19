"""Admin and health API."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.config import settings
from backend.app.monitoring.azure_monitor import AzureMonitorMetricsClient
from backend.app.runtime_store import RuntimeStore
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


@router.get("/admin/dashboard")
def admin_dashboard() -> dict:
    """Return local and Microsoft route telemetry for the admin dashboard."""
    azure_ready = bool(settings.azure_search_endpoint)
    foundry_ready = bool(settings.foundry_project_endpoint and settings.foundry_model_deployment)
    foundry_tool_ready = bool(settings.foundry_ai_search_connection_id or settings.foundry_agent_name)
    dashboard = RuntimeStore().admin_dashboard()
    docs = KnowledgeIndex().load_documents()
    azure_monitor = AzureMonitorMetricsClient().dashboard_summary()
    return {
        **dashboard,
        "azure": {
            "route": _ms_route(azure_ready, foundry_ready, foundry_tool_ready),
            "azure_search_configured": azure_ready,
            "foundry_configured": foundry_ready,
            "foundry_search_tool_configured": foundry_tool_ready,
            "storage_configured": bool(
                settings.azure_storage_container
                and (
                    settings.azure_storage_account_key
                    or settings.azure_storage_connection_string
                    or settings.azure_storage_sas_token
                )
            ),
            "search_index": settings.azure_search_index,
            "storage_container": settings.azure_storage_container,
            "foundry_model": settings.foundry_model_deployment,
            "monitor": azure_monitor,
        },
        "local": {
            "index_name": settings.elastic_index,
            "local_index_path": settings.local_index_path,
            "local_index_count": len(docs),
            "upload_dir": settings.admin_upload_local_dir,
            "llm_model": settings.llm_model,
            "llm_chat_enabled": settings.enable_llm_chat,
        },
        "monitoring_notes": [
            "Foundry Agent Monitor: token usage, latency, run success rate, evaluation results",
            "Foundry Traces/Application Insights: prompt, retrieval operation, latency, exception trace",
            "Azure AI Search Metrics: QPS, search latency, throttled query percentage",
            "App Runtime Log: local Qwen/local index route and MS Foundry/Azure route are normalized together",
        ],
    }


def _ms_route(azure_ready: bool, foundry_ready: bool, foundry_tool_ready: bool) -> str:
    if azure_ready and foundry_ready and foundry_tool_ready:
        return "foundry_search_tool"
    if azure_ready and foundry_ready:
        return "azure_search_then_foundry_context"
    if azure_ready:
        return "azure_search_local_answer"
    return "local"
