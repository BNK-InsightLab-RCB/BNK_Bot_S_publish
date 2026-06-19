"""Build role-aware context for RAG answers."""

from __future__ import annotations

from typing import Iterable, List

from backend.app.config import settings
from backend.app.parsers.base import KnowledgeDocument
from backend.app.utils.text import mask_sensitive


class ContextBuilder:
    """Prepare compact answer context."""

    def __init__(self, max_chars: int = 0) -> None:
        self.max_chars = max_chars or settings.max_context_chars

    def build(self, docs: Iterable[KnowledgeDocument], user_role: str = "branch") -> str:
        """Return text context for answer generation."""
        chunks: List[str] = []
        used = 0
        for doc in docs:
            chunk = self._doc_context(doc, user_role)
            if used + len(chunk) > self.max_chars:
                break
            chunks.append(chunk)
            used += len(chunk)
        return "\n\n".join(chunks)

    def _doc_context(self, doc: KnowledgeDocument, user_role: str) -> str:
        lines = [
            f"title: {doc.title}",
            f"doc_type: {doc.doc_type}",
            f"business_name: {doc.business_name or ''}",
            f"summary: {doc.summary}",
        ]
        if doc.screen_id or doc.screen_name:
            lines.append(f"screen: {doc.screen_id or ''} {doc.screen_name or ''}".strip())
        if doc.input_fields:
            lines.append("input_fields: " + " | ".join(doc.input_fields))
        if doc.error_codes:
            lines.append("error_codes: " + " | ".join(doc.error_codes))
        if doc.business_rules:
            lines.append("business_rules: " + " | ".join(doc.business_rules))
        if doc.error_messages:
            lines.append("error_messages: " + " | ".join(doc.error_messages))
        if doc.branch_guide:
            lines.append("branch_guide: " + doc.branch_guide)
        if doc.api_path:
            lines.append(f"api_path: {doc.http_method or ''} {doc.api_path}".strip())
        if doc.api_description:
            lines.append("api_description: " + doc.api_description)
        if doc.dto_names:
            lines.append("dto_names: " + ", ".join(doc.dto_names))
        if doc.dto_fields:
            lines.append("dto_fields: " + ", ".join(doc.dto_fields))
        if doc.validation_conditions:
            lines.append("validation_conditions: " + " | ".join(doc.validation_conditions))
        if doc.exception_types:
            lines.append("exception_types: " + ", ".join(doc.exception_types))
        if doc.auth_codes:
            lines.append("auth_codes: " + ", ".join(doc.auth_codes))
        if doc.call_chain:
            lines.append("call_chain: " + " -> ".join(doc.call_chain))
        if doc.class_name or doc.method_name:
            lines.append(f"method: {doc.class_name or ''}.{doc.method_name or ''}")
        if doc.sql_id:
            lines.append(f"sql_id: {doc.sql_id}")
        if doc.tables:
            lines.append("tables: " + ", ".join(doc.tables))
        if doc.it_guide:
            lines.append("it_guide: " + doc.it_guide)
        if doc.code_text and user_role == "admin":
            lines.append("code_text: " + doc.code_text[:2000])
        lines.append(f"source: {doc.source_path}:{doc.start_line}-{doc.end_line}")
        return mask_sensitive("\n".join(lines))
