"""Application configuration.

The loader intentionally avoids requiring python-dotenv at import time so the
core parser tests can run in a bare Python environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


def _load_dotenv(path: str = ".env") -> Dict[str, str]:
    """Load a tiny subset of dotenv syntax without adding a hard dependency."""
    env_path = Path(path)
    values: Dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _get(name: str, default: str, dotenv_values: Dict[str, str]) -> str:
    return os.getenv(name, dotenv_values.get(name, default))


def _bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings for local PoC services."""

    app_env: str = "local"
    app_port: int = 9000
    elastic_url: str = "http://localhost:9200"
    elastic_username: str = ""
    elastic_password: str = ""
    elastic_index: str = "ops_knowledge"
    sqlite_path: str = "./data/ops_rag.sqlite3"
    local_index_path: str = "./data/ops_knowledge.json"
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "EMPTY"
    llm_model: str = "Qwen/Qwen3-14B-MLX-4bit"
    llm_timeout_seconds: int = 60
    embedding_provider: str = "hash"
    embedding_model: str = "BAAI/bge-m3"
    embedding_batch_size: int = 4
    embedding_cache_path: str = "./data/embedding_cache.sqlite3"
    embedding_fallback_dim: int = 384
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_embedding_deployment: str = "text-embedding-3-large"
    azure_openai_embedding_dimensions: int = 0
    max_retrieved_chunks: int = 12
    max_context_chars: int = 24000
    default_user_role: str = "branch"
    enable_llm_summary: bool = True
    enable_llm_chat: bool = False
    use_elasticsearch_search: bool = True
    enable_thinking_for_summary: bool = True
    enable_thinking_for_chat: bool = False
    mask_source_for_branch: bool = True
    rag_provider: str = "local"
    public_repo_base_url: str = "https://github.com/BNK-InsightLab-RCB/BNK_Bot_S/blob/main"
    azure_search_endpoint: str = ""
    azure_search_index: str = "ops-knowledge"
    azure_search_api_key: str = ""
    azure_search_api_version: str = "2024-07-01"
    azure_search_semantic_config: str = "ops-semantic-config"
    azure_search_vector_profile: str = "ops-vector-profile"
    azure_search_vector_algorithm: str = "ops-hnsw"
    azure_search_vector_metric: str = "cosine"
    azure_search_content_field: str = "content"
    azure_search_vector_field: str = "content_vector"
    azure_search_enable_vector_query: bool = True
    azure_search_hybrid_k: int = 50
    azure_search_vector_weight: float = 1.0
    azure_search_batch_size: int = 500
    azure_storage_account: str = ""
    azure_storage_container: str = ""
    azure_storage_account_key: str = ""
    azure_storage_connection_string: str = ""
    azure_storage_sas_token: str = ""
    azure_storage_upload_prefix: str = "source-drop"
    admin_upload_local_dir: str = "backend/examples/bank_sample/docs/admin_uploads"
    foundry_project_endpoint: str = ""
    foundry_model_deployment: str = "gpt-4.1-mini"
    foundry_api_key: str = ""
    foundry_agent_name: str = ""
    foundry_agent_version: str = ""
    foundry_ai_search_connection_id: str = ""
    foundry_ai_search_query_type: str = "semantic"
    foundry_top_k: int = 5
    foundry_timeout_seconds: int = 90
    foundry_force_search_tool: bool = True
    azure_monitor_resource_id: str = ""
    azure_monitor_metric_names: str = "TokenTransaction,ProcessedPromptTokens,GeneratedTokens,Requests,Latency"
    azure_monitor_api_version: str = "2023-10-01"
    azure_monitor_timespan_minutes: int = 60
    azure_monitor_token_limit: int = 1000000
    source_sync_admin_token: str = ""


def load_settings() -> Settings:
    """Build settings from `.env` and environment variables."""
    dotenv_values = _load_dotenv()
    return Settings(
        app_env=_get("APP_ENV", "local", dotenv_values),
        app_port=int(_get("APP_PORT", "9000", dotenv_values)),
        elastic_url=_get("ELASTIC_URL", "http://localhost:9200", dotenv_values),
        elastic_username=_get("ELASTIC_USERNAME", "", dotenv_values),
        elastic_password=_get("ELASTIC_PASSWORD", "", dotenv_values),
        elastic_index=_get("ELASTIC_INDEX", "ops_knowledge", dotenv_values),
        sqlite_path=_get("SQLITE_PATH", "./data/ops_rag.sqlite3", dotenv_values),
        local_index_path=_get("LOCAL_INDEX_PATH", "./data/ops_knowledge.json", dotenv_values),
        llm_base_url=_get("LLM_BASE_URL", "http://localhost:8000/v1", dotenv_values),
        llm_api_key=_get("LLM_API_KEY", "EMPTY", dotenv_values),
        llm_model=_get("LLM_MODEL", "Qwen/Qwen3-14B-MLX-4bit", dotenv_values),
        llm_timeout_seconds=int(_get("LLM_TIMEOUT_SECONDS", "60", dotenv_values)),
        embedding_provider=_get("EMBEDDING_PROVIDER", "hash", dotenv_values),
        embedding_model=_get("EMBEDDING_MODEL", "BAAI/bge-m3", dotenv_values),
        embedding_batch_size=int(_get("EMBEDDING_BATCH_SIZE", "4", dotenv_values)),
        embedding_cache_path=_get(
            "EMBEDDING_CACHE_PATH", "./data/embedding_cache.sqlite3", dotenv_values
        ),
        embedding_fallback_dim=int(_get("EMBEDDING_FALLBACK_DIM", "384", dotenv_values)),
        azure_openai_endpoint=_get("AZURE_OPENAI_ENDPOINT", "", dotenv_values),
        azure_openai_api_key=_get("AZURE_OPENAI_API_KEY", "", dotenv_values),
        azure_openai_api_version=_get("AZURE_OPENAI_API_VERSION", "2024-06-01", dotenv_values),
        azure_openai_embedding_deployment=_get(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large", dotenv_values
        ),
        azure_openai_embedding_dimensions=int(
            _get("AZURE_OPENAI_EMBEDDING_DIMENSIONS", "0", dotenv_values)
        ),
        max_retrieved_chunks=int(_get("MAX_RETRIEVED_CHUNKS", "12", dotenv_values)),
        max_context_chars=int(_get("MAX_CONTEXT_CHARS", "24000", dotenv_values)),
        default_user_role=_get("DEFAULT_USER_ROLE", "branch", dotenv_values),
        enable_llm_summary=_bool(_get("ENABLE_LLM_SUMMARY", "true", dotenv_values)),
        enable_llm_chat=_bool(_get("ENABLE_LLM_CHAT", "false", dotenv_values)),
        use_elasticsearch_search=_bool(
            _get("USE_ELASTICSEARCH_SEARCH", "true", dotenv_values)
        ),
        enable_thinking_for_summary=_bool(
            _get("ENABLE_THINKING_FOR_SUMMARY", "true", dotenv_values)
        ),
        enable_thinking_for_chat=_bool(_get("ENABLE_THINKING_FOR_CHAT", "false", dotenv_values)),
        mask_source_for_branch=_bool(_get("MASK_SOURCE_FOR_BRANCH", "true", dotenv_values)),
        rag_provider=_get("RAG_PROVIDER", "local", dotenv_values),
        public_repo_base_url=_get(
            "PUBLIC_REPO_BASE_URL",
            "https://github.com/BNK-InsightLab-RCB/BNK_Bot_S/blob/main",
            dotenv_values,
        ),
        azure_search_endpoint=_get("AZURE_SEARCH_ENDPOINT", "", dotenv_values),
        azure_search_index=_get("AZURE_SEARCH_INDEX", "ops-knowledge", dotenv_values),
        azure_search_api_key=_get("AZURE_SEARCH_API_KEY", "", dotenv_values),
        azure_search_api_version=_get("AZURE_SEARCH_API_VERSION", "2024-07-01", dotenv_values),
        azure_search_semantic_config=_get(
            "AZURE_SEARCH_SEMANTIC_CONFIG", "ops-semantic-config", dotenv_values
        ),
        azure_search_vector_profile=_get(
            "AZURE_SEARCH_VECTOR_PROFILE", "ops-vector-profile", dotenv_values
        ),
        azure_search_vector_algorithm=_get(
            "AZURE_SEARCH_VECTOR_ALGORITHM", "ops-hnsw", dotenv_values
        ),
        azure_search_vector_metric=_get("AZURE_SEARCH_VECTOR_METRIC", "cosine", dotenv_values),
        azure_search_content_field=_get("AZURE_SEARCH_CONTENT_FIELD", "content", dotenv_values),
        azure_search_vector_field=_get("AZURE_SEARCH_VECTOR_FIELD", "content_vector", dotenv_values),
        azure_search_enable_vector_query=_bool(
            _get("AZURE_SEARCH_ENABLE_VECTOR_QUERY", "true", dotenv_values)
        ),
        azure_search_hybrid_k=int(_get("AZURE_SEARCH_HYBRID_K", "50", dotenv_values)),
        azure_search_vector_weight=float(_get("AZURE_SEARCH_VECTOR_WEIGHT", "1.0", dotenv_values)),
        azure_search_batch_size=int(_get("AZURE_SEARCH_BATCH_SIZE", "500", dotenv_values)),
        azure_storage_account=_get("AZURE_STORAGE_ACCOUNT", "", dotenv_values),
        azure_storage_container=_get("AZURE_STORAGE_CONTAINER", "", dotenv_values),
        azure_storage_account_key=_get("AZURE_STORAGE_ACCOUNT_KEY", "", dotenv_values),
        azure_storage_connection_string=_get(
            "AZURE_STORAGE_CONNECTION_STRING", "", dotenv_values
        ),
        azure_storage_sas_token=_get("AZURE_STORAGE_SAS_TOKEN", "", dotenv_values),
        azure_storage_upload_prefix=_get(
            "AZURE_STORAGE_UPLOAD_PREFIX", "source-drop", dotenv_values
        ),
        admin_upload_local_dir=_get(
            "ADMIN_UPLOAD_LOCAL_DIR",
            "backend/examples/bank_sample/docs/admin_uploads",
            dotenv_values,
        ),
        foundry_project_endpoint=_get("FOUNDRY_PROJECT_ENDPOINT", "", dotenv_values),
        foundry_model_deployment=_get("FOUNDRY_MODEL_DEPLOYMENT", "gpt-4.1-mini", dotenv_values),
        foundry_api_key=_get("FOUNDRY_API_KEY", "", dotenv_values),
        foundry_agent_name=_get("FOUNDRY_AGENT_NAME", "", dotenv_values),
        foundry_agent_version=_get("FOUNDRY_AGENT_VERSION", "", dotenv_values),
        foundry_ai_search_connection_id=_get(
            "FOUNDRY_AI_SEARCH_CONNECTION_ID", "", dotenv_values
        ),
        foundry_ai_search_query_type=_get(
            "FOUNDRY_AI_SEARCH_QUERY_TYPE", "semantic", dotenv_values
        ),
        foundry_top_k=int(_get("FOUNDRY_TOP_K", "5", dotenv_values)),
        foundry_timeout_seconds=int(_get("FOUNDRY_TIMEOUT_SECONDS", "90", dotenv_values)),
        foundry_force_search_tool=_bool(_get("FOUNDRY_FORCE_SEARCH_TOOL", "true", dotenv_values)),
        azure_monitor_resource_id=_get("AZURE_MONITOR_RESOURCE_ID", "", dotenv_values),
        azure_monitor_metric_names=_get(
            "AZURE_MONITOR_METRIC_NAMES",
            "TokenTransaction,ProcessedPromptTokens,GeneratedTokens,Requests,Latency",
            dotenv_values,
        ),
        azure_monitor_api_version=_get("AZURE_MONITOR_API_VERSION", "2023-10-01", dotenv_values),
        azure_monitor_timespan_minutes=int(
            _get("AZURE_MONITOR_TIMESPAN_MINUTES", "60", dotenv_values)
        ),
        azure_monitor_token_limit=int(_get("AZURE_MONITOR_TOKEN_LIMIT", "1000000", dotenv_values)),
        source_sync_admin_token=_get("SOURCE_SYNC_ADMIN_TOKEN", "", dotenv_values),
    )


settings = load_settings()
