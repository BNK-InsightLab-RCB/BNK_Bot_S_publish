"""Parser for administrator-uploaded JSON, PDF, and text evidence files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.app.parsers.base import BaseParser, KnowledgeDocument, SourceFile
from backend.app.utils.text import normalize_ws, unique_keep_order


class UploadedDocumentParser(BaseParser):
    """Turn uploaded support artifacts into compact searchable documents."""

    supported_extensions = [".json", ".pdf", ".txt"]

    def parse(self, source: SourceFile) -> List[KnowledgeDocument]:
        suffix = source.path.suffix.lower()
        if suffix == ".json":
            return [self._parse_json(source)]
        if suffix == ".pdf":
            return [self._parse_pdf(source)]
        return [self._parse_text(source)]

    def _parse_json(self, source: SourceFile) -> KnowledgeDocument:
        payload = _load_json(source.text)
        business_name = _first(payload, "업무명", "business_name", "businessName") or source.path.stem
        screen_id = _first(payload, "화면번호", "screen_id", "screenId")
        screen_name = _first(payload, "화면명", "screen_name", "screenName") or business_name
        screen_info = _as_dict(_first(payload, "화면정보", "screen_info", "screenInfo"))
        api_value = _first(payload, "API", "api", "api_path", "apiPath")
        dto_value = _first(payload, "dto", "DTO", "dtos", "dto_names", "dtoNames")
        error_value = _first(payload, "error", "errors", "error_codes", "errorCodes")
        exception_value = _first(payload, "exception", "exceptions", "exception_types", "exceptionTypes")
        evidence_value = _as_dict(_first(payload, "근거", "evidence"))
        rules = _to_list(_first(payload, "업무규칙", "business_rules", "businessRules"))
        summary = normalize_ws(
            str(_first(payload, "summary", "요약", "description", "설명") or "")
            or json.dumps(payload, ensure_ascii=False)
        )[:900]
        return KnowledgeDocument(
            doc_type="uploaded_json",
            title=f"{business_name} 업로드 JSON 근거",
            business_name=str(business_name),
            screen_id=str(screen_id or "") or None,
            screen_name=str(screen_name or "") or None,
            screen_info=screen_info,
            api_path=_api_path(api_value),
            api_description=_api_description(api_value),
            class_name=str(evidence_value.get("클래스") or evidence_value.get("class_name") or "") or None,
            method_name=str(evidence_value.get("메서드") or evidence_value.get("method_name") or "") or None,
            sql_id=str(evidence_value.get("SQL_ID") or evidence_value.get("sql_id") or "") or None,
            tables=_to_list(evidence_value.get("테이블") or evidence_value.get("tables")),
            columns=_to_list(evidence_value.get("컬럼") or evidence_value.get("columns")),
            dto_names=_dto_names(dto_value),
            dto_fields=_dto_fields(dto_value),
            input_fields=_to_list(_as_dict(dto_value).get("input_fields")),
            validation_conditions=_error_validation_conditions(error_value),
            error_codes=_error_codes(error_value),
            error_messages=_error_messages(error_value),
            possible_errors=_error_possible(error_value),
            exception_types=_to_list(exception_value),
            business_rules=rules or _derive_rules(payload),
            branch_guide=f"{business_name} 관련 업무 문의 시 화면명, 오류 문구, 처리 단계를 확인합니다.",
            it_guide=f"{business_name} 업로드 JSON에서 API, DTO, error, exception 단서를 확인합니다.",
            summary=summary,
            source_path=str(source.path),
            code_text=json.dumps(payload, ensure_ascii=False, indent=2) if payload else source.text,
            end_line=max(1, len(source.text.splitlines())),
            metadata={"uploaded_artifact": True, "artifact_type": "json"},
        )

    def _parse_pdf(self, source: SourceFile) -> KnowledgeDocument:
        text = _read_pdf_text(source.path)
        compact = normalize_ws(text)[:1200]
        return KnowledgeDocument(
            doc_type="uploaded_pdf",
            title=f"{source.path.stem} PDF 업로드 문서",
            business_name=source.path.stem,
            summary=compact or "관리자 업로드 PDF 문서입니다. 원문은 로컬 테스트 디렉토리와 Azure Storage에 보관됩니다.",
            source_path=str(source.path),
            business_rules=[compact[:260]] if compact else [],
            branch_guide="PDF 문서 근거가 필요한 업무 문의는 문서명과 화면명을 함께 확인합니다.",
            it_guide="PDF 업로드 문서의 원문 보관 위치와 추출 텍스트를 확인합니다.",
            code_text=compact,
            metadata={
                "uploaded_artifact": True,
                "artifact_type": "pdf",
                "text_extracted": bool(compact),
            },
        )

    def _parse_text(self, source: SourceFile) -> KnowledgeDocument:
        compact = normalize_ws(source.text)
        return KnowledgeDocument(
            doc_type="uploaded_text",
            title=f"{source.path.stem} 업로드 문서",
            business_name=source.path.stem,
            summary=compact[:900],
            source_path=str(source.path),
            business_rules=[line.strip("- ") for line in source.text.splitlines() if line.strip()][:8],
            branch_guide="업로드 문서에 있는 업무 기준을 확인합니다.",
            it_guide="업로드 문서의 텍스트 근거를 확인합니다.",
            code_text=source.text,
            end_line=max(1, len(source.text.splitlines())),
            metadata={"uploaded_artifact": True, "artifact_type": "text"},
        )


def _load_json(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    if isinstance(data, dict):
        return data
    return {"items": data}


def _first(payload: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in payload:
            continue
        value = payload[key]
        if value is not None and value != "":
            return value
    return None


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return unique_keep_order(str(item) for item in value if item)
    if isinstance(value, dict):
        return unique_keep_order(f"{key}: {item}" for key, item in value.items() if item)
    return unique_keep_order(part.strip() for part in str(value).replace("\n", ",").split(",") if part.strip())


def _dto_names(value: Any) -> List[str]:
    if isinstance(value, dict):
        return _to_list(value.get("names") or value.get("dto_names") or value.get("DTO"))
    return _to_list(value)


def _dto_fields(value: Any) -> List[str]:
    if isinstance(value, dict):
        return _to_list(value.get("fields") or value.get("dto_fields"))
    return []


def _error_codes(value: Any) -> List[str]:
    if isinstance(value, dict):
        return _to_list(value.get("codes") or value.get("error_codes"))
    return _to_list(value)


def _error_messages(value: Any) -> List[str]:
    if isinstance(value, dict):
        return _to_list(value.get("messages") or value.get("error_messages"))
    return []


def _error_validation_conditions(value: Any) -> List[str]:
    if isinstance(value, dict):
        return _to_list(value.get("validation_conditions") or value.get("conditions"))
    return []


def _error_possible(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    possible = value.get("possible")
    if not isinstance(possible, list):
        return []
    normalized = []
    for item in possible:
        if isinstance(item, dict):
            normalized.append(item)
        elif item:
            normalized.append({"message": str(item)})
    return normalized


def _api_path(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("path", "api_path", "url", "endpoint"):
            if value.get(key):
                return str(value[key])
    if isinstance(value, str) and "/" in value:
        return value.strip()
    return None


def _api_description(value: Any) -> str:
    if isinstance(value, dict):
        return normalize_ws(
            " ".join(str(value.get(key) or "") for key in ("role", "description", "역할", "설명"))
        )
    return normalize_ws(str(value or ""))


def _derive_rules(payload: Dict[str, Any]) -> List[str]:
    rules = []
    for key in ("화면정보", "API", "dto", "error", "exception"):
        value = payload.get(key)
        if value:
            rules.append(f"{key}: {normalize_ws(str(value))[:220]}")
    return rules


def _read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception:
            return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""
