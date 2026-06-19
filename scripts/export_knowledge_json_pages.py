"""Export local KnowledgeDocument index into per-chunk Korean JSON pages."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.storage.elastic import KnowledgeIndex  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export one source-aware summary JSON file per KnowledgeDocument chunk."
    )
    parser.add_argument("--local-index-path", default="data/ops_knowledge.json")
    parser.add_argument(
        "--output-dir",
        default="backend/examples/bank_sample/docs/admin_uploads/bnk_hackathon_json_pages",
    )
    parser.add_argument("--reset-output", action="store_true")
    args = parser.parse_args()

    docs = KnowledgeIndex(local_path=args.local_index_path).load_documents()
    if not docs:
        raise SystemExit(f"No documents found in {args.local_index_path}")

    output_dir = Path(args.output_dir)
    if args.reset_output and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest: List[Dict[str, Any]] = []
    exported_index = 0
    for doc in docs:
        if _is_manifest_doc(doc.source_path, doc.title):
            continue
        exported_index += 1
        payload = _document_page(doc.to_dict(include_code=False))
        file_name = _file_name(exported_index, payload, doc.id or "")
        path = output_dir / file_name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest.append(
            {
                "file": file_name,
                "id": payload["근거"]["문서ID"],
                "doc_type": payload["근거"]["문서유형"],
                "title": payload["근거"]["제목"],
                "source_path": payload["근거"]["소스경로"],
            }
        )

    manifest_payload = {
        "format": "source-aware-json-pages",
        "document_count": len(manifest),
        "fields": [
            "업무명",
            "화면번호",
            "화면정보",
            "API",
            "dto",
            "error",
            "exception",
            "업무규칙",
            "요약",
            "근거",
        ],
        "documents": manifest,
    }
    (output_dir / "_manifest.json").write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Exported {len(manifest)} JSON pages to {output_dir}")


def _document_page(doc: Dict[str, Any]) -> Dict[str, Any]:
    screen_info = _dict(doc.get("screen_info"))
    input_fields = _list(doc.get("input_fields"))
    if input_fields:
        screen_info = {**screen_info, "input_fields": input_fields}
    if doc.get("menu_id") or doc.get("menu_name"):
        screen_info = {
            **screen_info,
            "menu_id": doc.get("menu_id") or "",
            "menu_name": doc.get("menu_name") or "",
        }
    return {
        "업무명": doc.get("business_name") or doc.get("screen_name") or doc.get("title") or "",
        "화면번호": doc.get("screen_id") or "",
        "화면명": doc.get("screen_name") or "",
        "화면정보": screen_info,
        "API": {
            "path": doc.get("api_path") or "",
            "method": doc.get("http_method") or "",
            "role": doc.get("api_description") or "",
            "call_chain": _list(doc.get("call_chain")),
        },
        "dto": {
            "names": _list(doc.get("dto_names")),
            "fields": _list(doc.get("dto_fields")),
            "input_fields": input_fields,
        },
        "error": {
            "codes": _list(doc.get("error_codes")),
            "messages": _list(doc.get("error_messages")),
            "possible": _list(doc.get("possible_errors")),
            "validation_conditions": _list(doc.get("validation_conditions")),
        },
        "exception": _list(doc.get("exception_types")),
        "업무규칙": _list(doc.get("business_rules")),
        "요약": doc.get("summary") or "",
        "근거": {
            "문서ID": doc.get("id") or "",
            "문서유형": doc.get("doc_type") or "",
            "제목": doc.get("title") or "",
            "소스경로": doc.get("source_path") or "",
            "라인": _line_range(doc),
            "클래스": doc.get("class_name") or "",
            "메서드": doc.get("method_name") or "",
            "SQL_ID": doc.get("sql_id") or "",
            "테이블": _list(doc.get("tables")),
            "컬럼": _list(doc.get("columns")),
            "auth_codes": _list(doc.get("auth_codes")),
        },
    }


def _is_manifest_doc(source_path: str, title: str) -> bool:
    path_name = Path(source_path or "").name.lower()
    return path_name == "_manifest.json" or title == "_manifest"


def _file_name(index: int, payload: Dict[str, Any], doc_id: str) -> str:
    title = payload["근거"]["제목"] or payload["업무명"] or "document"
    stem = _safe_name(f"{index:04d}_{payload['근거']['문서유형']}_{title}")
    suffix = _safe_name(doc_id[-8:] if doc_id else "")
    return f"{stem}_{suffix}.json" if suffix else f"{stem}.json"


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9가-힣._ -]+", "_", value).strip(" ._")
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized[:140] or "document"


def _line_range(doc: Dict[str, Any]) -> str:
    start = doc.get("start_line") or 1
    end = doc.get("end_line") or start
    return f"{start}-{end}" if end != start else str(start)


def _list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return [value]


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    main()
