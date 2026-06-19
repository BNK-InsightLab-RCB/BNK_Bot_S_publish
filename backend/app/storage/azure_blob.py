"""Azure Blob Storage upload adapter."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import posixpath
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote
from xml.etree import ElementTree

import httpx

from backend.app.config import settings


class AzureBlobConfigError(RuntimeError):
    """Raised when Azure Blob Storage settings are incomplete."""


@dataclass(frozen=True)
class BlobUploadItem:
    """Uploaded blob metadata."""

    file_name: str
    blob_name: str
    url: str
    size: int


@dataclass(frozen=True)
class BlobUploadResult:
    """Upload result for one API request."""

    container: str
    uploaded: List[BlobUploadItem]


@dataclass(frozen=True)
class BlobSyncResult:
    """Directory sync result."""

    container: str
    prefix: str
    uploaded: List[BlobUploadItem]
    deleted: List[str]


class AzureBlobStorage:
    """Upload source artifacts to Azure Blob Storage.

    The browser never receives account keys. Files are posted to FastAPI, then
    this server-side adapter uploads them to Azure Storage with either Shared Key
    auth or a container SAS token.
    """

    def __init__(
        self,
        account: str = "",
        container: str = "",
        account_key: str = "",
        connection_string: str = "",
        sas_token: str = "",
    ) -> None:
        parsed = _parse_connection_string(
            connection_string or settings.azure_storage_connection_string
        )
        self.account = account or settings.azure_storage_account or parsed.get("AccountName", "")
        self.container = (
            container or settings.azure_storage_container or parsed.get("ContainerName", "")
        )
        self.account_key = (
            account_key or settings.azure_storage_account_key or parsed.get("AccountKey", "")
        )
        self.sas_token = sas_token or settings.azure_storage_sas_token
        endpoint_suffix = parsed.get("EndpointSuffix") or "core.windows.net"
        blob_endpoint = parsed.get("BlobEndpoint") or ""
        self.base_url = blob_endpoint.rstrip("/") or f"https://{self.account}.blob.{endpoint_suffix}"

    def upload_files(
        self,
        files: Iterable[tuple[str, bytes, str]],
        prefix: str = "",
        overwrite: bool = True,
    ) -> BlobUploadResult:
        """Upload files as block blobs.

        `files` contains `(file_name, content, content_type)` tuples.
        """
        self._validate()
        uploaded: List[BlobUploadItem] = []
        for file_name, content, content_type in files:
            blob_name = _normalize_blob_name(prefix or settings.azure_storage_upload_prefix, file_name)
            url = self._upload_blob(
                blob_name=blob_name,
                content=content,
                content_type=content_type or "application/octet-stream",
                overwrite=overwrite,
            )
            uploaded.append(
                BlobUploadItem(
                    file_name=file_name,
                    blob_name=blob_name,
                    url=url,
                    size=len(content),
                )
            )
        return BlobUploadResult(container=self.container, uploaded=uploaded)

    def sync_directory(
        self,
        source_dir: str,
        prefix: str,
        prune: bool = True,
    ) -> BlobSyncResult:
        """Upload a source directory and optionally delete stale blobs.

        The resulting prefix is intended to represent the current department
        source snapshot. A generated manifest is uploaded next to the files so
        reset/replay runs can see exactly which files were part of the sync.
        """
        root = Path(source_dir)
        if not root.exists() or not root.is_dir():
            raise AzureBlobConfigError(f"Source directory does not exist: {source_dir}")

        items: List[tuple[str, bytes, str]] = []
        manifest_files = []
        for path in _iter_uploadable_files(root):
            relative_path = path.relative_to(root).as_posix()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            content = path.read_bytes()
            items.append((relative_path, content, content_type))
            manifest_files.append(
                {
                    "path": relative_path,
                    "size": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )

        manifest = {
            "source_dir": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(manifest_files),
            "files": manifest_files,
        }
        items.append(
            (
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                "application/json",
            )
        )

        existing = set(self.list_blob_names(prefix=prefix)) if prune else set()
        upload_result = self.upload_files(items, prefix=prefix, overwrite=True)
        current = {item.blob_name for item in upload_result.uploaded}
        deleted: List[str] = []
        for blob_name in sorted(existing - current):
            self.delete_blob(blob_name)
            deleted.append(blob_name)
        return BlobSyncResult(
            container=upload_result.container,
            prefix=prefix,
            uploaded=upload_result.uploaded,
            deleted=deleted,
        )

    def list_blob_names(self, prefix: str = "") -> List[str]:
        """List blob names under a prefix."""
        self._validate()
        names: List[str] = []
        marker = ""
        while True:
            params = {
                "restype": "container",
                "comp": "list",
                "prefix": prefix.strip("/"),
                "maxresults": "5000",
            }
            if marker:
                params["marker"] = marker
            params.update(_sas_params(self.sas_token))
            headers = self._headers()
            if self.account_key:
                headers["Authorization"] = _shared_key_authorization(
                    account=self.account,
                    account_key=self.account_key,
                    method="GET",
                    container=self.container,
                    blob_name="",
                    headers=headers,
                    params=params,
                )
            response = httpx.get(
                f"{self.base_url}/{self.container}",
                params=params,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.text)
            names.extend(
                element.text or ""
                for element in root.findall(".//Name")
                if element.text
            )
            marker_element = root.find(".//NextMarker")
            marker = marker_element.text if marker_element is not None and marker_element.text else ""
            if not marker:
                break
        return names

    def delete_blob(self, blob_name: str) -> None:
        """Delete one blob, ignoring already-missing blobs."""
        self._validate()
        encoded_blob = _quote_blob_path(blob_name)
        url = f"{self.base_url}/{self.container}/{encoded_blob}"
        params = _sas_params(self.sas_token)
        headers = self._headers()
        if self.account_key:
            headers["Authorization"] = _shared_key_authorization(
                account=self.account,
                account_key=self.account_key,
                method="DELETE",
                container=self.container,
                blob_name=blob_name,
                headers=headers,
                params=params,
            )
        response = httpx.delete(url, params=params, headers=headers, timeout=60)
        if response.status_code == 404:
            return
        response.raise_for_status()

    def _upload_blob(
        self,
        blob_name: str,
        content: bytes,
        content_type: str,
        overwrite: bool,
    ) -> str:
        encoded_blob = _quote_blob_path(blob_name)
        url = f"{self.base_url}/{self.container}/{encoded_blob}"
        params = _sas_params(self.sas_token)
        headers = {
            "Content-Length": str(len(content)),
            "Content-Type": content_type,
            "x-ms-blob-type": "BlockBlob",
            "x-ms-date": format_datetime(datetime.now(timezone.utc), usegmt=True),
            "x-ms-version": "2023-11-03",
        }
        if not overwrite:
            headers["If-None-Match"] = "*"
        if self.account_key:
            headers["Authorization"] = _shared_key_authorization(
                account=self.account,
                account_key=self.account_key,
                method="PUT",
                container=self.container,
                blob_name=blob_name,
                headers=headers,
                params=params,
            )
        response = httpx.put(url, params=params, content=content, headers=headers, timeout=120)
        response.raise_for_status()
        return str(response.url.copy_with(query=None))

    def _headers(self) -> Dict[str, str]:
        return {
            "x-ms-date": format_datetime(datetime.now(timezone.utc), usegmt=True),
            "x-ms-version": "2023-11-03",
        }

    def _validate(self) -> None:
        if not self.account:
            raise AzureBlobConfigError("AZURE_STORAGE_ACCOUNT is required.")
        if not self.container:
            raise AzureBlobConfigError("AZURE_STORAGE_CONTAINER is required.")
        if not self.account_key and not self.sas_token:
            raise AzureBlobConfigError(
                "Set AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_ACCOUNT_KEY, "
                "or AZURE_STORAGE_SAS_TOKEN for server-side Blob upload."
            )


def _parse_connection_string(value: str) -> Dict[str, str]:
    parts: Dict[str, str] = {}
    for raw_part in value.split(";"):
        if not raw_part or "=" not in raw_part:
            continue
        key, part_value = raw_part.split("=", 1)
        parts[key] = part_value
    return parts


def _normalize_blob_name(prefix: str, file_name: str) -> str:
    safe_prefix = _safe_blob_part(prefix).strip("/")
    safe_name = _safe_blob_part(file_name)
    if not safe_name:
        safe_name = "upload.bin"
    if safe_prefix:
        return posixpath.join(safe_prefix, safe_name)
    return safe_name


def _safe_blob_part(value: str) -> str:
    normalized = value.replace("\\", "/").replace("\x00", "").strip()
    parts = [
        part
        for part in normalized.split("/")
        if part and part not in {".", ".."}
    ]
    return "/".join(parts)


def _quote_blob_path(blob_name: str) -> str:
    return "/".join(quote(part, safe="") for part in blob_name.split("/"))


def _sas_params(token: str) -> Dict[str, str]:
    clean = token[1:] if token.startswith("?") else token
    if not clean:
        return {}
    params: Dict[str, str] = {}
    for part in clean.split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        params[key] = value
    return params


def _shared_key_authorization(
    account: str,
    account_key: str,
    method: str,
    container: str,
    blob_name: str,
    headers: Dict[str, str],
    params: Optional[Dict[str, str]] = None,
) -> str:
    string_to_sign = _string_to_sign(
        account=account,
        method=method,
        container=container,
        blob_name=blob_name,
        headers=headers,
        params=params or {},
    )
    decoded_key = base64.b64decode(account_key)
    signature = base64.b64encode(
        hmac.new(decoded_key, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    return f"SharedKey {account}:{signature}"


def _string_to_sign(
    account: str,
    method: str,
    container: str,
    blob_name: str,
    headers: Dict[str, str],
    params: Dict[str, str],
) -> str:
    canonicalized_headers = _canonicalized_headers(headers)
    canonicalized_resource = _canonicalized_resource(account, container, blob_name, params)
    content_length = headers.get("Content-Length", "")
    if content_length == "0":
        content_length = ""
    values = [
        method.upper(),
        headers.get("Content-Encoding", ""),
        headers.get("Content-Language", ""),
        content_length,
        headers.get("Content-MD5", ""),
        headers.get("Content-Type", ""),
        "",
        headers.get("If-Modified-Since", ""),
        headers.get("If-Match", ""),
        headers.get("If-None-Match", ""),
        headers.get("If-Unmodified-Since", ""),
        headers.get("Range", ""),
        canonicalized_headers + canonicalized_resource,
    ]
    return "\n".join(values)


def _canonicalized_headers(headers: Dict[str, str]) -> str:
    normalized = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key.startswith("x-ms-"):
            normalized[lower_key] = " ".join(str(value).split())
    return "".join(f"{key}:{normalized[key]}\n" for key in sorted(normalized))


def _canonicalized_resource(
    account: str,
    container: str,
    blob_name: str,
    params: Dict[str, str],
) -> str:
    resource = f"/{account}/{container}"
    if blob_name:
        resource = f"{resource}/{_quote_blob_path(blob_name)}"
    if not params:
        return resource
    query = []
    for key in sorted(params, key=str.lower):
        query.append(f"{key.lower()}:{params[key]}")
    return resource + "\n" + "\n".join(query)


def _iter_uploadable_files(root: Path) -> Iterable[Path]:
    ignored_dirs = {".git", "node_modules", "dist", "build", ".venv", "__pycache__"}
    ignored_names = {
        ".env",
        ".env.local",
        ".env.production",
        "secrets.json",
        "credentials.json",
    }
    ignored_suffixes = {".key", ".pem", ".p12", ".pfx"}
    for path in sorted(root.rglob("*")):
        if any(part in ignored_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.name in ignored_names or path.suffix.lower() in ignored_suffixes:
            continue
        yield path


def storage_upload_settings_ready() -> bool:
    """Return whether server-side Blob upload can run with current settings."""
    try:
        AzureBlobStorage()._validate()
    except AzureBlobConfigError:
        return False
    return True
