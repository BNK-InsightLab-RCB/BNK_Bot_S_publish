"""Azure Storage upload API."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.app.config import settings
from backend.app.runtime_store import RuntimeStore
from backend.app.schemas import StorageUploadResponse
from backend.app.storage.azure_blob import AzureBlobConfigError, AzureBlobStorage


router = APIRouter(prefix="/api/storage", tags=["storage"])

ALLOWED_LOCAL_UPLOAD_EXTENSIONS = {
    ".csv",
    ".json",
    ".md",
    ".pdf",
    ".sql",
    ".txt",
    ".vue",
    ".xml",
    ".xlsx",
    ".java",
}


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
    local_saved = _save_local_uploads(payload)
    try:
        result = AzureBlobStorage().upload_files(payload, prefix=prefix, overwrite=overwrite)
    except AzureBlobConfigError as exc:
        RuntimeStore().append_storage_upload(
            file_names=[item[0] for item in payload],
            blob_names=[],
            local_paths=[item["local_path"] for item in local_saved],
            total_size=sum(len(item[1]) for item in payload),
            container=settings.azure_storage_container,
            status="azure_config_error",
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        RuntimeStore().append_storage_upload(
            file_names=[item[0] for item in payload],
            blob_names=[],
            local_paths=[item["local_path"] for item in local_saved],
            total_size=sum(len(item[1]) for item in payload),
            container=settings.azure_storage_container,
            status="azure_upload_failed",
        )
        raise HTTPException(
            status_code=502,
            detail=f"Azure Blob upload failed with status {exc.response.status_code}.",
        ) from exc
    except httpx.HTTPError as exc:
        RuntimeStore().append_storage_upload(
            file_names=[item[0] for item in payload],
            blob_names=[],
            local_paths=[item["local_path"] for item in local_saved],
            total_size=sum(len(item[1]) for item in payload),
            container=settings.azure_storage_container,
            status="azure_upload_failed",
        )
        raise HTTPException(status_code=502, detail="Azure Blob upload request failed.") from exc
    local_by_name = {item["file_name"]: item["local_path"] for item in local_saved}
    uploaded = [
        {**item.__dict__, "local_path": local_by_name.get(item.file_name, "")}
        for item in result.uploaded
    ]
    RuntimeStore().append_storage_upload(
        file_names=[item.file_name for item in result.uploaded],
        blob_names=[item.blob_name for item in result.uploaded],
        local_paths=[local_by_name.get(item.file_name, "") for item in result.uploaded],
        total_size=sum(item.size for item in result.uploaded),
        container=result.container,
        status="uploaded",
    )
    return {
        "status": "uploaded",
        "container": result.container,
        "uploaded": uploaded,
    }


def _save_local_uploads(files: List[tuple[str, bytes, str]]) -> List[dict]:
    """Save uploaded artifacts into the local sample document directory."""
    root = _local_upload_dir()
    root.mkdir(parents=True, exist_ok=True)
    saved = []
    for file_name, content, _content_type in files:
        safe_name = _safe_local_file_name(file_name)
        suffix = Path(safe_name).suffix.lower()
        if suffix and suffix not in ALLOWED_LOCAL_UPLOAD_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported upload extension: {suffix}")
        path = root / safe_name
        path.write_bytes(content)
        saved.append({"file_name": file_name, "local_path": str(path)})
    return saved


def _local_upload_dir() -> Path:
    return Path(settings.admin_upload_local_dir)


def _safe_local_file_name(file_name: str) -> str:
    name = Path(file_name or "upload.bin").name
    name = re.sub(r"[^A-Za-z0-9가-힣._ -]+", "_", name).strip(" .")
    return name or "upload.bin"
