"""Embedding adapter with deterministic local fallback."""

from __future__ import annotations

import hashlib
import math
import subprocess
from typing import Iterable, List, Optional

import httpx

from backend.app.config import settings
from backend.app.embedding.cache import EmbeddingCache


class EmbeddingConfigError(RuntimeError):
    """Raised when a configured hosted embedding provider is unavailable."""


class Embedder:
    """Generate embeddings using sentence-transformers when available.

    If the configured model cannot be loaded, a deterministic hashing embedder is
    used. The fallback keeps tests and local PoC flows operational without model
    downloads, while preserving the same embedding interface.
    """

    def __init__(
        self,
        model_name: str = "",
        batch_size: int = 4,
        cache_path: str = "",
        fallback_dim: int = 384,
    ) -> None:
        self.provider = settings.embedding_provider.lower().strip() or "local"
        default_model = (
            settings.azure_openai_embedding_deployment
            if self.provider in {"azure", "azure_openai"}
            else settings.embedding_model
        )
        self.model_name = model_name or default_model
        self.batch_size = batch_size or settings.embedding_batch_size
        self.fallback_dim = fallback_dim or settings.embedding_fallback_dim
        self.cache = EmbeddingCache(cache_path or settings.embedding_cache_path)
        self._model: Optional[object] = None
        self._load_attempted = False

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        """Embed texts in configured batches."""
        vectors: List[List[float]] = []
        pending: List[str] = []
        pending_indices: List[int] = []
        text_list = list(texts)
        vectors = [[] for _ in text_list]

        for index, text in enumerate(text_list):
            cached = self.cache.get(self.model_name, text)
            if cached is not None:
                vectors[index] = cached
            else:
                pending.append(text)
                pending_indices.append(index)

        for start in range(0, len(pending), self.batch_size):
            batch = pending[start : start + self.batch_size]
            batch_vectors = self._embed_uncached(batch)
            for local_index, vector in enumerate(batch_vectors):
                original_index = pending_indices[start + local_index]
                vectors[original_index] = vector
                self.cache.set(self.model_name, text_list[original_index], vector)
        return vectors

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text."""
        return self.embed_texts([text])[0]

    def _embed_uncached(self, texts: List[str]) -> List[List[float]]:
        if self.provider in {"hash", "local_hash", "deterministic"}:
            return [self._hash_embedding(text) for text in texts]
        if self.provider in {"azure", "azure_openai"}:
            try:
                return self._embed_azure_openai(texts)
            except (EmbeddingConfigError, httpx.HTTPError, ValueError):
                self.provider = "hash"
                self.model_name = f"hash-fallback-{self.fallback_dim}"
                return [self._hash_embedding(text) for text in texts]
        model = self._load_model()
        if model is not None:
            try:
                vectors = model.encode(texts, normalize_embeddings=True)
                return [list(map(float, vector)) for vector in vectors]
            except Exception:
                pass
        return [self._hash_embedding(text) for text in texts]

    def _load_model(self) -> Optional[object]:
        if self._load_attempted:
            return self._model
        self._load_attempted = True
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        except Exception:
            self._model = None
        return self._model

    def _hash_embedding(self, text: str) -> List[float]:
        vector = [0.0] * self.fallback_dim
        tokens = [token for token in _tokenize(text) if token]
        if not tokens:
            tokens = [text or "empty"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for index, byte in enumerate(digest):
                slot = (byte + index * 31) % self.fallback_dim
                vector[slot] += 1.0 if byte % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _embed_azure_openai(self, texts: List[str]) -> List[List[float]]:
        if not settings.azure_openai_endpoint:
            raise EmbeddingConfigError("AZURE_OPENAI_ENDPOINT is required for azure_openai embeddings.")
        if not settings.azure_openai_embedding_deployment:
            raise EmbeddingConfigError(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT is required for azure_openai embeddings."
            )
        url = (
            f"{settings.azure_openai_endpoint.rstrip('/')}/openai/deployments/"
            f"{settings.azure_openai_embedding_deployment}/embeddings"
        )
        body: dict = {"input": texts}
        if settings.azure_openai_embedding_dimensions > 0:
            body["dimensions"] = settings.azure_openai_embedding_dimensions
        response = httpx.post(
            url,
            params={"api-version": settings.azure_openai_api_version},
            headers=_azure_openai_headers(),
            json=body,
            timeout=60,
        )
        response.raise_for_status()
        data = sorted(response.json().get("data", []), key=lambda item: int(item.get("index", 0)))
        vectors = [_normalize([float(value) for value in item.get("embedding", [])]) for item in data]
        if len(vectors) != len(texts):
            raise EmbeddingConfigError("Azure OpenAI embedding response count did not match input count.")
        return vectors


def _azure_openai_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.azure_openai_api_key:
        headers["api-key"] = settings.azure_openai_api_key
    else:
        headers["Authorization"] = (
            f"Bearer {_azure_cli_token('https://cognitiveservices.azure.com/.default')}"
        )
    return headers


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
        raise EmbeddingConfigError(
            "AZURE_OPENAI_API_KEY is not set and Azure CLI token acquisition failed. "
            "Run `az login` or set AZURE_OPENAI_API_KEY."
        ) from exc
    token = completed.stdout.strip()
    if not token:
        raise EmbeddingConfigError("Azure CLI returned an empty Azure OpenAI token.")
    return token


def _normalize(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def _tokenize(text: str) -> List[str]:
    normalized = text.lower().replace("/", " ").replace("_", " ")
    return [token.strip(".,:;()[]{}'\"") for token in normalized.split()]
