"""Sync a department source folder to Azure Storage and Azure AI Search."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.ingestion.source_sync import SourceSyncConfigError, run_source_sync  # noqa: E402
from backend.app.storage.azure_blob import AzureBlobConfigError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Upload source files to Azure Blob Storage, rebuild the local index, "
            "and upload the searchable documents to Azure AI Search."
        )
    )
    parser.add_argument("--source-dir", default="backend/examples/bank_sample")
    parser.add_argument("--department", default="")
    parser.add_argument("--storage-prefix", default="")
    parser.add_argument("--skip-storage", action="store_true")
    parser.add_argument("--skip-azure-search", action="store_true")
    parser.add_argument("--generate-summaries", action="store_true")
    parser.add_argument("--no-reset-index", action="store_true")
    parser.add_argument("--no-prune-storage", action="store_true")
    args = parser.parse_args()

    try:
        summary = run_source_sync(
            source_dir=args.source_dir,
            department=args.department,
            storage_prefix=args.storage_prefix,
            skip_storage=args.skip_storage,
            skip_azure_search=args.skip_azure_search,
            generate_summaries=args.generate_summaries,
            reset_index=not args.no_reset_index,
            prune_storage=not args.no_prune_storage,
        )
    except AzureBlobConfigError as exc:
        raise SystemExit(f"Azure Storage sync is not configured: {exc}") from exc
    except SourceSyncConfigError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
