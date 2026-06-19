"""Ingestion API."""

from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter

from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.runtime_store import RuntimeStore
from backend.app.schemas import IngestRequest, IngestResponse
from backend.app.storage.elastic import KnowledgeIndex


router = APIRouter(prefix="/api/ingest", tags=["ingest"])

_last_status = {"status": "idle", "indexed_count": 0}


@router.post("/run", response_model=IngestResponse)
def run_ingest(request: IngestRequest) -> dict:
    """Run source ingestion."""
    global _last_status
    _last_status = {"status": "running", "indexed_count": 0}
    started = perf_counter()
    result = IngestionPipeline().run(
        source_dir=request.source_dir,
        reset_index=request.reset_index,
        generate_summaries=request.generate_summaries,
        upload_azure_search=request.upload_azure_search,
    )
    _last_status = {"status": "completed", "indexed_count": result.indexed_count}
    RuntimeStore().append_ingest(
        indexed_count=result.indexed_count,
        upload_azure_search=request.upload_azure_search,
        duration_ms=int((perf_counter() - started) * 1000),
        status="completed",
    )
    return _last_status


@router.get("/status")
def ingest_status() -> dict:
    """Return last ingestion status."""
    docs = KnowledgeIndex().load_documents()
    return {**_last_status, "local_index_count": len(docs)}
