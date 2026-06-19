"""Source synchronization API for admin automation and Foundry tools."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Header, HTTPException

from backend.app.config import settings
from backend.app.ingestion.source_sync import SourceSyncConfigError, run_source_sync
from backend.app.schemas import SourceSyncRequest, SourceSyncResponse
from backend.app.storage.azure_blob import AzureBlobConfigError


router = APIRouter(prefix="/api/source-sync", tags=["source-sync"])

_last_status: dict[str, object] = {"status": "idle"}


@router.post("/run", response_model=SourceSyncResponse)
def run_source_sync_api(
    request: SourceSyncRequest,
    x_source_sync_token: str = Header(default=""),
) -> dict:
    """Run source sync from an admin API or Foundry OpenAPI tool."""
    _authorize(x_source_sync_token)
    global _last_status
    _last_status = {
        "status": "running",
        "department": request.department or request.source_dir.rstrip("/").split("/")[-1],
    }
    try:
        summary = run_source_sync(
            source_dir=request.source_dir,
            department=request.department,
            storage_prefix=request.storage_prefix,
            skip_storage=request.skip_storage,
            skip_azure_search=request.skip_azure_search,
            generate_summaries=request.generate_summaries,
            reset_index=request.reset_index,
            prune_storage=request.prune_storage,
        )
    except SourceSyncConfigError as exc:
        _last_status = {"status": "failed", "error": str(exc)}
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AzureBlobConfigError as exc:
        _last_status = {"status": "failed", "error": str(exc)}
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        detail = f"Azure request failed with status {exc.response.status_code}."
        _last_status = {"status": "failed", "error": detail}
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.HTTPError as exc:
        detail = "Azure request failed."
        _last_status = {"status": "failed", "error": detail}
        raise HTTPException(status_code=502, detail=detail) from exc
    _last_status = summary
    return summary


@router.get("/status")
def source_sync_status(
    x_source_sync_token: str = Header(default=""),
) -> dict[str, object]:
    """Return the last source sync status."""
    _authorize(x_source_sync_token)
    return _last_status


def _authorize(x_source_sync_token: str) -> None:
    token = settings.source_sync_admin_token
    if token and x_source_sync_token != token:
        raise HTTPException(status_code=401, detail="Invalid source sync admin token.")
