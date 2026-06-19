"""Shared parser data structures."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.utils.hashing import stable_id
from backend.app.utils.text import mask_sensitive, unique_keep_order


@dataclass
class SourceFile:
    """Source file loaded by the scanner."""

    path: Path
    language: str
    text: str


@dataclass
class KnowledgeDocument:
    """Searchable knowledge unit generated from source analysis."""

    doc_type: str
    title: str
    source_path: str
    summary: str = ""
    id: Optional[str] = None
    system: str = "bank_sample"
    business_domain: str = "branch_ops"
    business_name: Optional[str] = None
    screen_id: Optional[str] = None
    screen_name: Optional[str] = None
    screen_info: Dict[str, Any] = field(default_factory=dict)
    menu_id: Optional[str] = None
    menu_name: Optional[str] = None
    api_path: Optional[str] = None
    http_method: Optional[str] = None
    api_description: str = ""
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    sql_id: Optional[str] = None
    tables: List[str] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    dto_names: List[str] = field(default_factory=list)
    dto_fields: List[str] = field(default_factory=list)
    input_fields: List[str] = field(default_factory=list)
    validation_conditions: List[str] = field(default_factory=list)
    exception_types: List[str] = field(default_factory=list)
    auth_codes: List[str] = field(default_factory=list)
    call_chain: List[str] = field(default_factory=list)
    error_codes: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)
    possible_errors: List[Dict[str, Any]] = field(default_factory=list)
    branch_guide: str = ""
    it_guide: str = ""
    code_text: str = ""
    start_line: int = 1
    end_line: int = 1
    commit_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: List[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tables = unique_keep_order(self.tables)
        self.columns = unique_keep_order(self.columns)
        self.dto_names = unique_keep_order(self.dto_names)
        self.dto_fields = unique_keep_order(self.dto_fields)
        self.input_fields = unique_keep_order(self.input_fields)
        self.validation_conditions = unique_keep_order(self.validation_conditions)
        self.exception_types = unique_keep_order(self.exception_types)
        self.auth_codes = unique_keep_order(self.auth_codes)
        self.call_chain = unique_keep_order(self.call_chain)
        self.error_codes = unique_keep_order(self.error_codes)
        self.error_messages = unique_keep_order(self.error_messages)
        self.business_rules = unique_keep_order(self.business_rules)
        if self.id is None:
            self.id = stable_id(
                "doc",
                self.doc_type,
                self.source_path,
                self.title,
                self.start_line,
                self.end_line,
            )
        self.code_text = mask_sensitive(self.code_text)

    def searchable_text(self) -> str:
        """Text used for embeddings and fallback BM25."""
        parts = [
            self.title,
            self.business_name or "",
            self.screen_id or "",
            self.screen_name or "",
            json.dumps(self.screen_info, ensure_ascii=False) if self.screen_info else "",
            self.menu_id or "",
            self.api_path or "",
            self.api_description,
            self.class_name or "",
            self.method_name or "",
            self.sql_id or "",
            " ".join(self.tables),
            " ".join(self.columns),
            " ".join(self.dto_names),
            " ".join(self.dto_fields),
            " ".join(self.input_fields),
            " ".join(self.validation_conditions),
            " ".join(self.exception_types),
            " ".join(self.auth_codes),
            " ".join(self.call_chain),
            " ".join(self.error_messages),
            " ".join(self.error_codes),
            " ".join(self.business_rules),
            self.branch_guide,
            self.it_guide,
            self.summary,
        ]
        return "\n".join(part for part in parts if part)

    def to_dict(self, include_code: bool = True) -> Dict[str, Any]:
        """Serialize for JSON, API, and Elasticsearch."""
        data: Dict[str, Any] = {
            "id": self.id,
            "doc_type": self.doc_type,
            "system": self.system,
            "business_domain": self.business_domain,
            "business_name": self.business_name,
            "title": self.title,
            "screen_id": self.screen_id,
            "screen_name": self.screen_name,
            "screen_info": self.screen_info,
            "menu_id": self.menu_id,
            "menu_name": self.menu_name,
            "api_path": self.api_path,
            "http_method": self.http_method,
            "api_description": self.api_description,
            "class_name": self.class_name,
            "method_name": self.method_name,
            "sql_id": self.sql_id,
            "tables": self.tables,
            "columns": self.columns,
            "dto_names": self.dto_names,
            "dto_fields": self.dto_fields,
            "input_fields": self.input_fields,
            "validation_conditions": self.validation_conditions,
            "exception_types": self.exception_types,
            "auth_codes": self.auth_codes,
            "call_chain": self.call_chain,
            "error_codes": self.error_codes,
            "error_messages": self.error_messages,
            "business_rules": self.business_rules,
            "possible_errors": self.possible_errors,
            "branch_guide": self.branch_guide,
            "it_guide": self.it_guide,
            "summary": self.summary,
            "source_path": self.source_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "commit_hash": self.commit_hash,
            "metadata": self.metadata,
            "embedding": self.embedding,
        }
        if include_code:
            data["code_text"] = self.code_text
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeDocument":
        """Deserialize from a dictionary."""
        normalized = dict(data)
        possible_errors = normalized.get("possible_errors")
        if isinstance(possible_errors, list):
            parsed_errors = []
            for error in possible_errors:
                if isinstance(error, str):
                    try:
                        parsed_errors.append(json.loads(error))
                    except json.JSONDecodeError:
                        parsed_errors.append({"message": error})
                else:
                    parsed_errors.append(error)
            normalized["possible_errors"] = parsed_errors
        known = {
            field_name: normalized.get(field_name)
            for field_name in cls.__dataclass_fields__.keys()
            if field_name in normalized
        }
        return cls(**known)


class BaseParser:
    """Base class for source parsers."""

    supported_extensions: List[str] = []

    def can_parse(self, path: Path) -> bool:
        """Return whether this parser handles the file extension."""
        return path.suffix.lower() in self.supported_extensions

    def parse(self, source: SourceFile) -> List[KnowledgeDocument]:
        """Parse a source file."""
        raise NotImplementedError
