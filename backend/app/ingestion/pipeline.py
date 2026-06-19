"""End-to-end ingestion pipeline CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import List

from backend.app.config import settings
from backend.app.embedding.embedder import Embedder
from backend.app.ingestion.indexer import Indexer
from backend.app.ingestion.scanner import SourceScanner
from backend.app.ingestion.summarizer import Summarizer
from backend.app.parsers.base import BaseParser, KnowledgeDocument, SourceFile
from backend.app.parsers.frontend_parser import FrontendParser
from backend.app.parsers.java_parser import JavaParser
from backend.app.parsers.mybatis_parser import MyBatisParser
from backend.app.parsers.sql_parser import SqlParser
from backend.app.parsers.table_doc_parser import TableDocParser
from backend.app.parsers.uploaded_document_parser import UploadedDocumentParser
from backend.app.storage.azure_search import AzureSearchKnowledgeIndex
from backend.app.storage.elastic import KnowledgeIndex
from backend.app.storage.sqlite import SQLiteGraphStore


@dataclass
class IngestionResult:
    """Ingestion result metadata."""

    indexed_count: int
    docs: List[KnowledgeDocument]


class IngestionPipeline:
    """Scan, parse, summarize, embed, index, and graph source documents."""

    def __init__(
        self,
        index_path: str = "",
        sqlite_path: str = "",
        parsers: List[BaseParser] = None,
    ) -> None:
        self.scanner = SourceScanner()
        self.parsers = parsers or [
            FrontendParser(),
            JavaParser(),
            MyBatisParser(),
            SqlParser(),
            TableDocParser(),
            UploadedDocumentParser(),
        ]
        self.index = KnowledgeIndex(local_path=index_path or settings.local_index_path)
        self.embedder = Embedder()
        self.indexer = Indexer(self.index, self.embedder)
        self.graph_store = SQLiteGraphStore(sqlite_path or settings.sqlite_path)
        self.summarizer = Summarizer()

    def run(
        self,
        source_dir: str,
        reset_index: bool = False,
        generate_summaries: bool = False,
        upload_azure_search: bool = False,
    ) -> IngestionResult:
        """Run the full ingestion pipeline."""
        source_files = self.scanner.scan(source_dir)
        docs = self._parse(source_files)
        docs = self._link_documents(docs)
        docs = self.summarizer.enrich(docs, use_llm=generate_summaries)
        if reset_index:
            self.graph_store.reset()
        indexed = self.indexer.index_documents(docs, reset_index=reset_index)
        self.graph_store.build_from_documents(indexed)
        if upload_azure_search:
            AzureSearchKnowledgeIndex().upload_documents(indexed, reset_index=reset_index)
        return IngestionResult(indexed_count=len(indexed), docs=indexed)

    def _parse(self, source_files: List[SourceFile]) -> List[KnowledgeDocument]:
        docs: List[KnowledgeDocument] = []
        for source in source_files:
            for parser in self.parsers:
                if parser.can_parse(source.path):
                    docs.extend(parser.parse(source))
                    break
        return docs

    def _link_documents(self, docs: List[KnowledgeDocument]) -> List[KnowledgeDocument]:
        frontend_by_api = {
            doc.api_path: doc
            for doc in docs
            if doc.doc_type == "frontend_event" and doc.api_path
        }
        api_to_controller = {
            doc.api_path: doc
            for doc in docs
            if doc.doc_type == "backend_controller" and doc.api_path
        }
        controller_by_method = {
            doc.method_name: doc
            for doc in docs
            if doc.doc_type == "backend_controller" and doc.method_name
        }
        service_by_method = {
            doc.method_name: doc
            for doc in docs
            if doc.doc_type == "business_logic" and doc.method_name
        }
        mapper_by_method = {
            (doc.sql_id or "").split(".")[-1]: doc for doc in docs if doc.doc_type == "sql_mapper" and doc.sql_id
        }
        for doc in docs:
            if doc.doc_type == "frontend_event" and doc.api_path in api_to_controller:
                controller = api_to_controller[doc.api_path]
                doc.metadata["controller"] = controller.title
                doc.call_chain = _unique(doc.call_chain + [controller.title])
            if doc.doc_type == "backend_controller" and doc.api_path in frontend_by_api:
                frontend = frontend_by_api[doc.api_path]
                _inherit_business_context(doc, frontend)
                service = service_by_method.get(doc.method_name or "")
                if service:
                    doc.metadata["service"] = service.title
                    doc.call_chain = _unique(doc.call_chain + [service.title])
            if doc.doc_type == "business_logic":
                controller = controller_by_method.get(doc.method_name or "")
                frontend = frontend_by_api.get(controller.api_path) if controller and controller.api_path else None
                if controller:
                    _inherit_business_context(doc, controller)
                    doc.call_chain = _unique([controller.title] + doc.call_chain)
                if frontend:
                    _inherit_business_context(doc, frontend)
                    doc.call_chain = _unique([frontend.title] + doc.call_chain)
            if doc.doc_type == "business_logic":
                related_sql_ids = []
                related_tables = []
                for call in doc.metadata.get("mapper_calls", []):
                    method = str(call).split(".")[-1]
                    mapper_doc = mapper_by_method.get(method)
                    if mapper_doc:
                        related_sql_ids.append(mapper_doc.sql_id)
                        related_tables.extend(mapper_doc.tables)
                        _inherit_business_context(mapper_doc, doc)
                        mapper_doc.call_chain = _unique([doc.title] + mapper_doc.call_chain)
                doc.metadata["related_sql_ids"] = [value for value in related_sql_ids if value]
                doc.tables = list(dict.fromkeys(doc.tables + related_tables))
                doc.call_chain = _unique(doc.call_chain + [value for value in related_sql_ids if value])
        return docs


def _inherit_business_context(target: KnowledgeDocument, source: KnowledgeDocument) -> None:
    """Copy screen/API business anchors across related source chunks."""
    target.business_name = target.business_name or source.business_name or source.screen_name
    target.screen_id = target.screen_id or source.screen_id
    target.screen_name = target.screen_name or source.screen_name
    target.menu_id = target.menu_id or source.menu_id
    target.menu_name = target.menu_name or source.menu_name
    target.screen_info = target.screen_info or dict(source.screen_info)
    target.api_path = target.api_path or source.api_path
    target.http_method = target.http_method or source.http_method
    target.input_fields = _unique(target.input_fields + source.input_fields)


def _unique(values: List[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest source-aware ops RAG documents.")
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--reset-index", action="store_true")
    parser.add_argument("--generate-summaries", action="store_true")
    parser.add_argument("--upload-azure-search", action="store_true")
    args = parser.parse_args()
    result = IngestionPipeline().run(
        source_dir=args.source_dir,
        reset_index=args.reset_index,
        generate_summaries=args.generate_summaries,
        upload_azure_search=args.upload_azure_search,
    )
    print(f"Indexed {result.indexed_count} documents")


if __name__ == "__main__":
    main()
