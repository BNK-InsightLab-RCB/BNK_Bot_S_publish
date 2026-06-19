import httpx

from backend.app.embedding.embedder import Embedder


def test_azure_embedding_failure_falls_back_to_hash(monkeypatch, tmp_path):
    embedder = Embedder(fallback_dim=16, cache_path=str(tmp_path / "embeddings.json"))
    embedder.provider = "azure_openai"
    embedder.model_name = "text-embedding-3-large"

    def fail(_texts):
        raise httpx.ConnectError("dns failed")

    monkeypatch.setattr(embedder, "_embed_azure_openai", fail)

    vectors = embedder.embed_texts(["자동이체 등록 오류"])

    assert embedder.provider == "hash"
    assert embedder.model_name == "hash-fallback-16"
    assert len(vectors) == 1
    assert len(vectors[0]) == 16
