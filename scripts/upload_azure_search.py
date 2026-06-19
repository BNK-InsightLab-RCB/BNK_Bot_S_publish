"""Upload the local KnowledgeDocument index to Azure AI Search."""

from __future__ import annotations

import argparse

from backend.app.storage.azure_search import AzureSearchKnowledgeIndex
from backend.app.storage.elastic import KnowledgeIndex


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload local source-aware docs to Azure AI Search.")
    parser.add_argument("--reset-index", action="store_true")
    parser.add_argument("--local-index-path", default="")
    args = parser.parse_args()

    docs = KnowledgeIndex(local_path=args.local_index_path).load_documents()
    if not docs:
        raise SystemExit(
            "No local documents found. Run `python -m backend.app.ingestion.pipeline "
            "--source-dir backend/examples/bank_sample --reset-index` first."
        )
    result = AzureSearchKnowledgeIndex().upload_documents(docs, reset_index=args.reset_index)
    print(f"Uploaded {result.uploaded_count} documents to Azure AI Search index {result.index_name}")


if __name__ == "__main__":
    main()
