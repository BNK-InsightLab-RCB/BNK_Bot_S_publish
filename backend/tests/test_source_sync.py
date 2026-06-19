from dataclasses import replace

from backend.app.api import source_sync as source_sync_api
from backend.app.ingestion import source_sync
from backend.app.main import app
from fastapi.testclient import TestClient


def test_source_sync_rejects_paths_outside_project(tmp_path, monkeypatch):
    monkeypatch.setattr(source_sync, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        source_sync,
        "ALLOWED_SOURCE_ROOTS",
        (tmp_path / "source_repositories", tmp_path / "backend" / "examples"),
    )
    outside = tmp_path.parent / "outside_sources"
    outside.mkdir(exist_ok=True)

    try:
        source_sync.run_source_sync(str(outside), skip_storage=True, skip_azure_search=True)
    except source_sync.SourceSyncConfigError as exc:
        assert "source_repositories" in str(exc)
    else:
        raise AssertionError("source sync accepted an unsafe source_dir")


def test_source_sync_runs_storage_and_ingestion(tmp_path, monkeypatch):
    project_root = tmp_path
    source_dir = project_root / "source_repositories" / "card_ops"
    source_dir.mkdir(parents=True)
    (source_dir / "CardService.java").write_text("class CardService {}", encoding="utf-8")

    monkeypatch.setattr(source_sync, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(
        source_sync,
        "ALLOWED_SOURCE_ROOTS",
        (project_root / "source_repositories", project_root / "backend" / "examples"),
    )

    class FakeBlobResult:
        container = "uhihi"
        uploaded = [object(), object()]
        deleted = ["source-live/card_ops/OldService.java"]

    class FakeStorage:
        def sync_directory(self, source_dir, prefix, prune):
            assert source_dir.endswith("source_repositories/card_ops")
            assert prefix == "source-live/card_ops"
            assert prune is True
            return FakeBlobResult()

    class FakePipelineResult:
        indexed_count = 7

    class FakePipeline:
        def run(self, source_dir, reset_index, generate_summaries, upload_azure_search):
            assert source_dir.endswith("source_repositories/card_ops")
            assert reset_index is True
            assert generate_summaries is False
            assert upload_azure_search is True
            return FakePipelineResult()

    monkeypatch.setattr(source_sync, "AzureBlobStorage", FakeStorage)
    monkeypatch.setattr(source_sync, "IngestionPipeline", FakePipeline)

    summary = source_sync.run_source_sync(
        "source_repositories/card_ops",
        department="card_ops",
    )

    assert summary["status"] == "completed"
    assert summary["department"] == "card_ops"
    assert summary["storage"]["uploaded_count"] == 2
    assert summary["storage"]["deleted_count"] == 1
    assert summary["ingestion"]["indexed_count"] == 7
    assert summary["ingestion"]["azure_search_uploaded"] is True


def test_source_sync_api_uses_admin_token(monkeypatch):
    monkeypatch.setattr(
        source_sync_api,
        "settings",
        replace(source_sync_api.settings, source_sync_admin_token="secret"),
    )

    response = TestClient(app).post(
        "/api/source-sync/run",
        json={"source_dir": "backend/examples/bank_sample", "skip_storage": True},
    )

    assert response.status_code == 401
