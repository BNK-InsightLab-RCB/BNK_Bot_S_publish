"""Azure Storage upload API."""

from __future__ import annotations

from typing import List

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.schemas import StorageUploadResponse
from backend.app.storage.azure_blob import AzureBlobConfigError, AzureBlobStorage


router = APIRouter(prefix="/api/storage", tags=["storage"])


@router.post("/upload", response_model=StorageUploadResponse)
async def upload_to_storage(
    files: List[UploadFile] = File(...),
    prefix: str = Form(""),
    overwrite: bool = Form(True),
) -> dict:
    """Upload dropped files to Azure Blob Storage."""
    if not files:
        raise HTTPException(status_code=400, detail="No files were provided.")
    payload = []
    for file in files:
        content = await file.read()
        if not content:
            continue
        payload.append((file.filename or "upload.bin", content, file.content_type or ""))
    if not payload:
        raise HTTPException(status_code=400, detail="All provided files were empty.")
    try:
        result = AzureBlobStorage().upload_files(payload, prefix=prefix, overwrite=overwrite)
    except AzureBlobConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Azure Blob upload failed with status {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Azure Blob upload request failed.") from exc
    return {
        "status": "uploaded",
        "container": result.container,
        "uploaded": [item.__dict__ for item in result.uploaded],
    }
