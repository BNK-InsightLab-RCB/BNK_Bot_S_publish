"""Azure AI Search indexing adapter for Foundry demo mode."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Iterable, List, Optional

import httpx

from backend.app.config import settings
from backend.app.embedding.embedder import Embedder, EmbeddingConfigError
from backend.app.parsers.base import KnowledgeDocument


class AzureSearchConfigError(RuntimeError):
    """Raised when Azure AI Search settings are incomplete."""


@dataclass(frozen=True)
class AzureSearchUploadResult:
    """Upload result returned by the Azure AI Search adapter."""

    index_name: str
    uploaded_count: int


@dataclass(frozen=True)
class AzureSearchHit:
    """Search result returned by Azure AI Search."""

    document: KnowledgeDocument
    score: float
    reranker_score: float = 0.0


class AzureSearchKnowledgeIndex:
    """Create and upload source-aware documents to Azure AI Search.

    The adapter uses REST instead of a fast-moving SDK surface so the lab can be
    replayed after Microsoft Foundry test resources are reset.
    """

    def __init__(
        self,
        endpoint: str = "",
        index_name: str = "",
        api_key: str = "",
        api_version: str = "",
    ) -> None:
        self.endpoint = (endpoint or settings.azure_search_endpoint).rstrip("/")
        self.index_name = index_name or settings.azure_search_index
        self.api_key = api_key or settings.azure_search_api_key
        self.api_version = api_version or settings.azure_search_api_version

    def upload_documents(
        self,
        docs: Iterable[KnowledgeDocument],
        reset_index: bool = False,
    ) -> AzureSearchUploadResult:
        """Create the index if needed and upload documents."""
        documents = list(docs)
        self._validate()
        if reset_index:
            self.delete_index(ignore_missing=True)
        dimension = _embedding_dimension(documents)
        self.create_or_update_index(dimension)
        uploaded = 0
        for batch in _chunks(documents, settings.azure_search_batch_size):
            self._upload_batch(batch)
            uploaded += len(batch)
        return AzureSearchUploadResult(index_name=self.index_name, uploaded_count=uploaded)

    def search_documents(self, query: str, top_k: int = 8) -> List[AzureSearchHit]:
        """Search source-aware documents in Azure AI Search."""
        self._validate()
        body = _search_body(query, top_k, vector=self._query_vector(query))
        response = self._request(
            "POST",
            f"/indexes/{self.index_name}/docs/search",
            json_body=body,
        )
        if response.status_code == 400 and body.get("vectorQueries"):
            fallback_body = _search_body(query, top_k, vector=[])
            response = self._request(
                "POST",
                f"/indexes/{self.index_name}/docs/search",
                json_body=fallback_body,
            )
        response.raise_for_status()
        return [_hit_from_payload(value) for value in response.json().get("value", [])]

    def delete_index(self, ignore_missing: bool = True) -> None:
        """Delete the Azure AI Search index."""
        response = self._request("DELETE", f"/indexes/{self.index_name}")
        if response.status_code == 404 and ignore_missing:
            return
        response.raise_for_status()

    def create_or_update_index(self, embedding_dim: int) -> None:
        """Create or replace the Azure AI Search index schema."""
        body = _index_schema(self.index_name, embedding_dim)
        response = self._request("PUT", f"/indexes/{self.index_name}", json_body=body)
        response.raise_for_status()

    def _upload_batch(self, docs: List[KnowledgeDocument]) -> None:
        payload = {"value": [_document_payload(doc) for doc in docs]}
        response = self._request(
            "POST",
            f"/indexes/{self.index_name}/docs/index",
            json_body=payload,
        )
        response.raise_for_status()

    def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> httpx.Response:
        url = f"{self.endpoint}{path}?api-version={self.api_version}"
        response = httpx.request(
            method,
            url,
            headers=self._headers(),
            json=json_body,
            timeout=60,
        )
        return response

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {_azure_cli_token('https://search.azure.com/.default')}"
        return headers

    def _validate(self) -> None:
        if not self.endpoint:
            raise AzureSearchConfigError("AZURE_SEARCH_ENDPOINT is required.")
        if not self.index_name:
            raise AzureSearchConfigError("AZURE_SEARCH_INDEX is required.")

    def _query_vector(self, query: str) -> List[float]:
        if not settings.azure_search_enable_vector_query:
            return []
        try:
            return Embedder().embed_text(query)
        except (EmbeddingConfigError, httpx.HTTPError, ValueError):
            return []


def _azure_cli_token(scope: str) -> str:
    try:
        completed = subprocess.run(
            [
                "az",
                "account",
                "get-access-token",
                "--scope",
                scope,
                "--query",
                "accessToken",
                "-o",
                "tsv",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise AzureSearchConfigError(
            "AZURE_SEARCH_API_KEY is not set and Azure CLI token acquisition failed. "
            "Run `az login` or set AZURE_SEARCH_API_KEY."
        ) from exc
    token = completed.stdout.strip()
    if not token:
        raise AzureSearchConfigError("Azure CLI returned an empty Search token.")
    return token


def _index_schema(index_name: str, embedding_dim: int) -> dict:
    fields = [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True, "retrievable": True},
        {"name": "doc_type", "type": "Edm.String", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "system", "type": "Edm.String", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "business_domain", "type": "Edm.String", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "business_name", "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "title", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "screen_id", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "screen_name", "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "screen_info", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "menu_id", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "menu_name", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "api_path", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "http_method", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "api_description", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "class_name", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "method_name", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "sql_id", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "tables", "type": "Collection(Edm.String)", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "columns", "type": "Collection(Edm.String)", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "dto_names", "type": "Collection(Edm.String)", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "dto_fields", "type": "Collection(Edm.String)", "searchable": True, "retrievable": True},
        {"name": "input_fields", "type": "Collection(Edm.String)", "searchable": True, "retrievable": True},
        {"name": "validation_conditions", "type": "Collection(Edm.String)", "searchable": True, "retrievable": True},
        {"name": "exception_types", "type": "Collection(Edm.String)", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "auth_codes", "type": "Collection(Edm.String)", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "call_chain", "type": "Collection(Edm.String)", "searchable": True, "retrievable": True},
        {"name": "error_codes", "type": "Collection(Edm.String)", "filterable": True, "facetable": True, "retrievable": True},
        {"name": "error_messages", "type": "Collection(Edm.String)", "searchable": True, "retrievable": True},
        {"name": "business_rules", "type": "Collection(Edm.String)", "searchable": True, "retrievable": True},
        {"name": "branch_guide", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "it_guide", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "summary", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True, "analyzer": "ko.microsoft"},
        {"name": "source_path", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "source_url", "type": "Edm.String", "retrievable": True},
        {"name": "start_line", "type": "Edm.Int32", "filterable": True, "retrievable": True},
        {"name": "end_line", "type": "Edm.Int32", "filterable": True, "retrievable": True},
    ]
    if embedding_dim:
        fields.append(
            {
                "name": settings.azure_search_vector_field,
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": False,
                "dimensions": embedding_dim,
                "vectorSearchProfile": settings.azure_search_vector_profile,
            }
        )
    schema = {
        "name": index_name,
        "fields": fields,
        "scoringProfiles": [
            {
                "name": "ops-source-priority",
                "text": {
                    "weights": {
                        "title": 3.0,
                        "business_name": 2.8,
                        "screen_name": 2.4,
                        "menu_name": 2.0,
                        "api_description": 2.0,
                        "error_messages": 2.2,
                        "error_codes": 2.0,
                        "validation_conditions": 1.9,
                        "input_fields": 1.8,
                        "dto_fields": 1.7,
                        "business_rules": 1.8,
                        "branch_guide": 1.4,
                        "it_guide": 1.2,
                        "summary": 1.2,
                    }
                },
            }
        ],
        "defaultScoringProfile": "ops-source-priority",
        "semantic": {
            "configurations": [
                {
                    "name": settings.azure_search_semantic_config,
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "prioritizedContentFields": [
                            {"fieldName": "content"},
                            {"fieldName": "summary"},
                            {"fieldName": "api_description"},
                            {"fieldName": "screen_info"},
                            {"fieldName": "branch_guide"},
                            {"fieldName": "it_guide"},
                        ],
                        "prioritizedKeywordsFields": [
                            {"fieldName": "business_name"},
                            {"fieldName": "input_fields"},
                            {"fieldName": "dto_fields"},
                            {"fieldName": "validation_conditions"},
                            {"fieldName": "error_codes"},
                            {"fieldName": "error_messages"},
                            {"fieldName": "business_rules"},
                        ],
                    },
                }
            ]
        },
    }
    if embedding_dim:
        schema["vectorSearch"] = {
            "algorithms": [
                {
                    "name": settings.azure_search_vector_algorithm,
                    "kind": "hnsw",
                    "hnswParameters": {"metric": settings.azure_search_vector_metric},
                }
            ],
            "profiles": [
                {
                    "name": settings.azure_search_vector_profile,
                    "algorithm": settings.azure_search_vector_algorithm,
                }
            ],
        }
    return schema


def _search_body(query: str, top_k: int, vector: List[float]) -> dict:
    body = {
        "search": query,
        "queryType": "semantic",
        "semanticConfiguration": settings.azure_search_semantic_config,
        "searchFields": ",".join(
            [
                "title",
                "business_name",
                "screen_name",
                "screen_info",
                "menu_name",
                "api_description",
                "input_fields",
                "dto_fields",
                "validation_conditions",
                "error_codes",
                "error_messages",
                "business_rules",
                "branch_guide",
                "it_guide",
                "summary",
                "content",
            ]
        ),
        "answers": "extractive|count-3",
        "captions": "extractive",
        "top": top_k,
        "select": ",".join(
            [
                "id",
                "doc_type",
                "system",
                "business_domain",
                "business_name",
                "title",
                "screen_id",
                "screen_name",
                "screen_info",
                "menu_id",
                "menu_name",
                "api_path",
                "http_method",
                "api_description",
                "class_name",
                "method_name",
                "sql_id",
                "tables",
                "columns",
                "dto_names",
                "dto_fields",
                "input_fields",
                "validation_conditions",
                "exception_types",
                "auth_codes",
                "call_chain",
                "error_codes",
                "error_messages",
                "business_rules",
                "branch_guide",
                "it_guide",
                "summary",
                "source_path",
                "start_line",
                "end_line",
            ]
        ),
    }
    if vector:
        body["vectorQueries"] = [
            {
                "kind": "vector",
                "vector": vector,
                "fields": settings.azure_search_vector_field,
                "k": max(settings.azure_search_hybrid_k, top_k),
                "weight": settings.azure_search_vector_weight,
            }
        ]
    return body


def _document_payload(doc: KnowledgeDocument) -> dict:
    payload = {
        "@search.action": "mergeOrUpload",
        "id": doc.id,
        "doc_type": doc.doc_type,
        "system": doc.system,
        "business_domain": doc.business_domain,
        "business_name": doc.business_name,
        "title": doc.title,
        "screen_id": doc.screen_id,
        "screen_name": doc.screen_name,
        "screen_info": json.dumps(doc.screen_info, ensure_ascii=False) if doc.screen_info else "",
        "menu_id": doc.menu_id,
        "menu_name": doc.menu_name,
        "api_path": doc.api_path,
        "http_method": doc.http_method,
        "api_description": doc.api_description,
        "class_name": doc.class_name,
        "method_name": doc.method_name,
        "sql_id": doc.sql_id,
        "tables": doc.tables,
        "columns": doc.columns,
        "dto_names": doc.dto_names,
        "dto_fields": doc.dto_fields,
        "input_fields": doc.input_fields,
        "validation_conditions": doc.validation_conditions,
        "exception_types": doc.exception_types,
        "auth_codes": doc.auth_codes,
        "call_chain": doc.call_chain,
        "error_codes": doc.error_codes,
        "error_messages": doc.error_messages,
        "business_rules": doc.business_rules,
        "branch_guide": doc.branch_guide,
        "it_guide": doc.it_guide,
        "summary": doc.summary,
        "content": _content(doc),
        "source_path": doc.source_path,
        "source_url": _source_url(doc),
        "start_line": int(doc.start_line or 1),
        "end_line": int(doc.end_line or doc.start_line or 1),
    }
    if doc.embedding:
        payload[settings.azure_search_vector_field] = [float(value) for value in doc.embedding]
    return payload


def _hit_from_payload(payload: dict) -> AzureSearchHit:
    score = float(payload.get("@search.score") or 0.0)
    reranker_score = float(payload.get("@search.rerankerScore") or 0.0)
    doc = KnowledgeDocument(
        id=payload.get("id"),
        doc_type=payload.get("doc_type") or "source",
        system=payload.get("system") or "bank_sample",
        business_domain=payload.get("business_domain") or "branch_ops",
        business_name=payload.get("business_name"),
        title=payload.get("title") or "Azure AI Search result",
        screen_id=payload.get("screen_id"),
        screen_name=payload.get("screen_name"),
        screen_info=_dict(payload.get("screen_info")),
        menu_id=payload.get("menu_id"),
        menu_name=payload.get("menu_name"),
        api_path=payload.get("api_path"),
        http_method=payload.get("http_method"),
        api_description=payload.get("api_description") or "",
        class_name=payload.get("class_name"),
        method_name=payload.get("method_name"),
        sql_id=payload.get("sql_id"),
        tables=_list(payload.get("tables")),
        columns=_list(payload.get("columns")),
        dto_names=_list(payload.get("dto_names")),
        dto_fields=_list(payload.get("dto_fields")),
        input_fields=_list(payload.get("input_fields")),
        validation_conditions=_list(payload.get("validation_conditions")),
        exception_types=_list(payload.get("exception_types")),
        auth_codes=_list(payload.get("auth_codes")),
        call_chain=_list(payload.get("call_chain")),
        error_codes=_list(payload.get("error_codes")),
        error_messages=_list(payload.get("error_messages")),
        business_rules=_list(payload.get("business_rules")),
        branch_guide=payload.get("branch_guide") or "",
        it_guide=payload.get("it_guide") or "",
        summary=payload.get("summary") or "",
        source_path=payload.get("source_path") or "",
        start_line=int(payload.get("start_line") or 1),
        end_line=int(payload.get("end_line") or payload.get("start_line") or 1),
        metadata={
            "retrieval_backend": "azure_ai_search",
            "search_score": score,
            "reranker_score": reranker_score,
            "semantic_captions": _semantic_captions(payload),
        },
    )
    return AzureSearchHit(document=doc, score=score, reranker_score=reranker_score)


def _list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value:
        return [value]
    return []


def _dict(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _semantic_captions(payload: dict) -> List[str]:
    captions = payload.get("@search.captions") or []
    values = []
    for caption in captions:
        if isinstance(caption, dict) and caption.get("text"):
            values.append(str(caption["text"]))
    return values


def _content(doc: KnowledgeDocument) -> str:
    parts = [
        f"문서 유형: {doc.doc_type}",
        f"업무명: {doc.business_name or ''}",
        f"제목: {doc.title}",
        f"화면: {doc.screen_id or ''} {doc.screen_name or ''}".strip(),
        f"화면정보: {json.dumps(doc.screen_info, ensure_ascii=False) if doc.screen_info else ''}",
        f"API: {doc.http_method or ''} {doc.api_path or ''}".strip(),
        f"API 역할: {doc.api_description}",
        f"DTO: {', '.join(doc.dto_names)}",
        f"DTO 필드: {', '.join(doc.dto_fields)}",
        f"입력 필드: {', '.join(doc.input_fields)}",
        f"검증 조건: {' | '.join(doc.validation_conditions)}",
        f"Exception: {', '.join(doc.exception_types)}",
        f"권한 코드: {', '.join(doc.auth_codes)}",
        f"호출 관계: {' -> '.join(doc.call_chain)}",
        f"SQL: {doc.sql_id or ''}",
        f"테이블: {', '.join(doc.tables)}",
        f"컬럼: {', '.join(doc.columns)}",
        f"오류 코드: {' | '.join(doc.error_codes)}",
        f"오류 메시지: {' | '.join(doc.error_messages)}",
        f"업무 규칙: {' | '.join(doc.business_rules)}",
        f"영업점 안내: {doc.branch_guide}",
        f"IT 안내: {doc.it_guide}",
        f"요약: {doc.summary}",
    ]
    return "\n".join(part for part in parts if part and not part.endswith(": "))


def _source_url(doc: KnowledgeDocument) -> str:
    base = settings.public_repo_base_url.rstrip("/")
    path = doc.source_path.lstrip("/")
    line = int(doc.start_line or 1)
    return f"{base}/{path}#L{line}"


def _embedding_dimension(docs: List[KnowledgeDocument]) -> int:
    for doc in docs:
        if doc.embedding:
            return len(doc.embedding)
    return 0


def _chunks(values: List[KnowledgeDocument], size: int) -> Iterable[List[KnowledgeDocument]]:
    size = max(1, size)
    for index in range(0, len(values), size):
        yield values[index : index + size]


def dumps_schema_preview(embedding_dim: int = 384) -> str:
    """Return a readable schema preview for docs and troubleshooting."""
    return json.dumps(_index_schema(settings.azure_search_index, embedding_dim), ensure_ascii=False, indent=2)
