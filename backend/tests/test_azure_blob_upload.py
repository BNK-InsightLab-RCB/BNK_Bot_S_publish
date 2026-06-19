from fastapi.testclient import TestClient

from backend.app.api import storage as storage_api
from backend.app.main import app
from backend.app.storage.azure_blob import (
    BlobUploadItem,
    BlobUploadResult,
    AzureBlobStorage,
    _normalize_blob_name,
    _parse_connection_string,
    _sas_params,
)


def test_blob_name_is_normalized_without_path_traversal():
    assert _normalize_blob_name("source-drop/../team", "../../rules.json") == "source-drop/team/rules.json"
    assert _normalize_blob_name("source-live/card", "backend/CardService.java") == "source-live/card/backend/CardService.java"
    assert _normalize_blob_name("", "../") == "upload.bin"


def test_storage_connection_string_is_parsed():
    parsed = _parse_connection_string(
        "DefaultEndpointsProtocol=https;AccountName=pjy1;AccountKey=abc;EndpointSuffix=core.windows.net"
    )

    assert parsed["AccountName"] == "pjy1"
    assert parsed["AccountKey"] == "abc"
    assert parsed["EndpointSuffix"] == "core.windows.net"


def test_sas_token_parsing_removes_leading_question_mark():
    assert _sas_params("?sv=2024&sig=abc") == {"sv": "2024", "sig": "abc"}


def test_storage_upload_endpoint_accepts_dropped_files(monkeypatch):
    class FakeStorage:
        def upload_files(self, files, prefix="", overwrite=True):
            file_name, content, content_type = list(files)[0]
            assert prefix == "source-drop"
            assert overwrite is True
            assert file_name == "sample.txt"
            assert content == b"hello"
            assert content_type == "text/plain"
            return BlobUploadResult(
                container="uhihi",
                uploaded=[
                    BlobUploadItem(
                        file_name=file_name,
                        blob_name="source-drop/sample.txt",
                        url="https://pjy1.blob.core.windows.net/uhihi/source-drop/sample.txt",
                        size=len(content),
                    )
                ],
            )

    monkeypatch.setattr(storage_api, "AzureBlobStorage", FakeStorage)
    response = TestClient(app).post(
        "/api/storage/upload",
        files={"files": ("sample.txt", b"hello", "text/plain")},
        data={"prefix": "source-drop", "overwrite": "true"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "uploaded"
    assert body["container"] == "uhihi"
    assert body["uploaded"][0]["blob_name"] == "source-drop/sample.txt"


def test_storage_directory_sync_uploads_manifest_and_prunes_stale_files(tmp_path, monkeypatch):
    source_dir = tmp_path / "card"
    (source_dir / "backend").mkdir(parents=True)
    (source_dir / "backend" / "CardService.java").write_text("class CardService {}", encoding="utf-8")
    (source_dir / ".env").write_text("SECRET=1", encoding="utf-8")

    storage = AzureBlobStorage(
        account="pjy1",
        container="uhihi",
        sas_token="?sv=2024&sig=test",
    )
    uploaded = []
    deleted = []

    def fake_upload_blob(blob_name, content, content_type, overwrite):
        uploaded.append((blob_name, content_type, overwrite))
        return f"https://pjy1.blob.core.windows.net/uhihi/{blob_name}"

    monkeypatch.setattr(storage, "_upload_blob", fake_upload_blob)
    monkeypatch.setattr(
        storage,
        "list_blob_names",
        lambda prefix="": [
            "source-live/card/backend/CardService.java",
            "source-live/card/backend/OldService.java",
        ],
    )
    monkeypatch.setattr(storage, "delete_blob", lambda blob_name: deleted.append(blob_name))

    result = storage.sync_directory(str(source_dir), prefix="source-live/card", prune=True)

    blob_names = [item.blob_name for item in result.uploaded]
    assert "source-live/card/backend/CardService.java" in blob_names
    assert "source-live/card/manifest.json" in blob_names
    assert all(".env" not in blob_name for blob_name in blob_names)
    assert result.deleted == ["source-live/card/backend/OldService.java"]
    assert deleted == ["source-live/card/backend/OldService.java"]
    assert uploaded[0][2] is True
