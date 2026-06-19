"""Department source synchronization workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from backend.app.ingestion.pipeline import IngestionPipeline
from backend.app.storage.azure_blob import AzureBlobStorage


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_SOURCE_ROOTS = (
    PROJECT_ROOT / "source_repositories",
    PROJECT_ROOT / "backend" / "examples",
)


class SourceSyncConfigError(RuntimeError):
    """Raised when a source sync request is unsafe or incomplete."""


def run_source_sync(
    source_dir: str = "backend/examples/bank_sample",
    department: str = "",
    storage_prefix: str = "",
    skip_storage: bool = False,
    skip_azure_search: bool = False,
    generate_summaries: bool = False,
    reset_index: bool = True,
    prune_storage: bool = True,
) -> Dict[str, object]:
    """Upload a department source snapshot and rebuild searchable knowledge."""
    resolved_source = _resolve_source_dir(source_dir)
    department_code = department or resolved_source.name
    if not _valid_department_code(department_code):
        raise SourceSyncConfigError(
            "department must contain only letters, numbers, underscore, or hyphen."
        )

    prefix = storage_prefix.strip("/") or f"source-live/{department_code}"
    if ".." in Path(prefix).parts:
        raise SourceSyncConfigError("storage_prefix must not contain path traversal.")

    summary: Dict[str, object] = {
        "status": "running",
        "department": department_code,
        "source_dir": str(resolved_source.relative_to(PROJECT_ROOT)),
        "storage_prefix": prefix,
        "reset_index": reset_index,
        "storage": {"status": "skipped"},
        "ingestion": {"status": "not_started"},
    }

    if not skip_storage:
        sync_result = AzureBlobStorage().sync_directory(
            source_dir=str(resolved_source),
            prefix=prefix,
            prune=prune_storage,
        )
        summary["storage"] = {
            "status": "synced",
            "container": sync_result.container,
            "uploaded_count": len(sync_result.uploaded),
            "deleted_count": len(sync_result.deleted),
            "deleted": sync_result.deleted,
        }

    result = IngestionPipeline().run(
        source_dir=str(resolved_source),
        reset_index=reset_index,
        generate_summaries=generate_summaries,
        upload_azure_search=not skip_azure_search,
    )
    summary["ingestion"] = {
        "status": "completed",
        "indexed_count": result.indexed_count,
        "azure_search_uploaded": not skip_azure_search,
    }
    summary["status"] = "completed"
    return summary


def _resolve_source_dir(source_dir: str) -> Path:
    raw_path = Path(source_dir).expanduser()
    candidate = raw_path if raw_path.is_absolute() else PROJECT_ROOT / raw_path
    resolved = candidate.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise SourceSyncConfigError(f"Source directory does not exist: {source_dir}")
    allowed_roots = tuple(root.resolve() for root in ALLOWED_SOURCE_ROOTS)
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise SourceSyncConfigError(
            "source_dir must be under source_repositories/ or backend/examples/."
        )
    return resolved


def _valid_department_code(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in {"_", "-"} for ch in value)
