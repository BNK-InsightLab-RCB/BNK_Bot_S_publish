"""API schemas."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request body."""

    question: str
    user_role: str = Field(default="branch", pattern="^(branch|it|admin)$")
    screen_id: Optional[str] = None
    screen_name: Optional[str] = None
    include_sources: bool = True


class ChatResponse(BaseModel):
    """Chat response body."""

    answer: str
    branch_guide: Dict[str, object]
    it_summary: Dict[str, object]
    confidence: float
    sources: List[Dict[str, object]]
    metadata: Dict[str, object] = Field(default_factory=dict)


class SearchRequest(BaseModel):
    """Search request body."""

    query: str
    user_role: str = Field(default="branch", pattern="^(branch|it|admin)$")
    filters: Dict[str, object] = Field(default_factory=dict)
    top_k: int = 10


class SearchResponse(BaseModel):
    """Search response body."""

    results: List[Dict[str, object]]


class IngestRequest(BaseModel):
    """Ingest request body."""

    source_dir: str = "backend/examples/bank_sample"
    reset_index: bool = True
    generate_summaries: bool = False
    upload_azure_search: bool = False


class IngestResponse(BaseModel):
    """Ingest response body."""

    status: str
    indexed_count: int


class SourceSyncRequest(BaseModel):
    """Department source sync request body."""

    source_dir: str = "backend/examples/bank_sample"
    department: str = ""
    storage_prefix: str = ""
    skip_storage: bool = False
    skip_azure_search: bool = False
    generate_summaries: bool = False
    reset_index: bool = True
    prune_storage: bool = True


class SourceSyncResponse(BaseModel):
    """Department source sync response body."""

    status: str
    department: str
    source_dir: str
    storage_prefix: str
    reset_index: bool
    storage: Dict[str, object]
    ingestion: Dict[str, object]


class StorageUploadItem(BaseModel):
    """Uploaded Azure Blob item."""

    file_name: str
    blob_name: str
    url: str
    size: int


class StorageUploadResponse(BaseModel):
    """Azure Blob upload response."""

    status: str
    container: str
    uploaded: List[StorageUploadItem]


class SupportTicketRequest(BaseModel):
    """Branch-to-IT escalation request."""

    question: str
    summary: str = ""
    screen_name: str = ""
    priority: str = "normal"
    answer_backend: str = ""
    rag_provider: str = ""
    retrieval_backend: str = ""
    confidence: float = 0
    source_count: int = 0


class HealthResponse(BaseModel):
    """Health response."""

    status: str
    index_name: str
    rag_provider: str = "local"
