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


class SignupRequest(BaseModel):
    """Demo signup request."""

    real_name: str = Field(min_length=1, max_length=40)
    employee_id: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=4, max_length=120)
    role_code: str = Field(pattern="^(01|02|03)$")


class LoginRequest(BaseModel):
    """Demo login request."""

    employee_id: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=120)


class AuthUser(BaseModel):
    """Authenticated demo user profile."""

    id: str
    real_name: str
    employee_id: str
    role: str = Field(pattern="^(branch|it|admin)$")
    role_code: str = Field(pattern="^(01|02|03)$")
    role_label: str


class AuthResponse(BaseModel):
    """Authentication response."""

    user: AuthUser


class SupportTicketRequest(BaseModel):
    """Branch-to-IT escalation request."""

    question: str
    summary: str = ""
    screen_name: str = ""
    priority: str = "normal"
    sender_name: str = ""
    sender_employee_id: str = ""
    sender_role: str = "branch"
    sender_role_code: str = "01"
    answer_backend: str = ""
    rag_provider: str = ""
    retrieval_backend: str = ""
    confidence: float = 0
    source_count: int = 0


class TicketReplyRequest(BaseModel):
    """Reply to a branch-to-IT support ticket."""

    body: str = Field(min_length=1, max_length=3000)
    author_name: str = ""
    author_employee_id: str = ""
    author_role: str = Field(default="it", pattern="^(branch|it|admin)$")
    author_role_code: str = Field(default="02", pattern="^(01|02|03)$")


class HealthResponse(BaseModel):
    """Health response."""

    status: str
    index_name: str
    rag_provider: str = "local"
