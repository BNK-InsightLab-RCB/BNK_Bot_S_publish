"""Small JSON-backed runtime store for demo logs and branch-to-IT tickets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.utils.hashing import stable_id


DATA_DIR = Path("data")
LOG_PATH = DATA_DIR / "runtime_events.json"
TICKET_PATH = DATA_DIR / "support_tickets.json"


class RuntimeStore:
    """Persist UI-visible audit data without storing credentials or full answers."""

    def __init__(self, log_path: Path = LOG_PATH, ticket_path: Path = TICKET_PATH) -> None:
        self.log_path = log_path
        self.ticket_path = ticket_path
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def append_chat(
        self,
        question: str,
        user_role: str,
        response: Dict[str, object],
        duration_ms: Optional[int] = None,
    ) -> dict:
        """Record one chat request with backend route metadata."""
        metadata = response.get("metadata", {}) if isinstance(response.get("metadata"), dict) else {}
        sources = response.get("sources", []) if isinstance(response.get("sources"), list) else []
        retrieval_backends = sorted(
            {
                str(source.get("retrieval_backend"))
                for source in sources
                if isinstance(source, dict) and source.get("retrieval_backend")
            }
        )
        event = {
            "id": stable_id("evt", _now(), question, user_role),
            "timestamp": _now(),
            "kind": "chat",
            "user_role": user_role,
            "question_preview": _preview(question),
            "rag_provider": str(metadata.get("rag_provider", "")),
            "answer_backend": str(metadata.get("answer_backend", "")),
            "retrieval_backend": ", ".join(retrieval_backends) or "local_json",
            "confidence": response.get("confidence", 0),
            "source_count": len(sources),
            "duration_ms": duration_ms or metadata.get("duration_ms") or 0,
            "answer_preview": _preview(str(response.get("answer") or ""), limit=240),
            "source_titles": _source_titles(sources),
            "agent_trace": metadata.get("agent_trace", []),
            "foundry_citation_count": _foundry_source_count(sources),
            "status": "blocked"
            if metadata.get("blocked_by_safety") or metadata.get("blocked_by_scope")
            else "answered",
        }
        self._append(self.log_path, event)
        return event

    def append_ingest(
        self,
        indexed_count: int,
        upload_azure_search: bool = False,
        duration_ms: int = 0,
        status: str = "completed",
    ) -> dict:
        """Record an ingestion/index refresh operation."""
        event = {
            "id": stable_id("evt", _now(), "ingest", indexed_count, upload_azure_search),
            "timestamp": _now(),
            "kind": "ingest",
            "user_role": "admin",
            "question_preview": "소스 색인 갱신",
            "rag_provider": "admin",
            "answer_backend": "azure_search" if upload_azure_search else "local_index",
            "retrieval_backend": "azure_ai_search" if upload_azure_search else "local_json",
            "confidence": 0,
            "source_count": indexed_count,
            "duration_ms": duration_ms,
            "answer_preview": "",
            "source_titles": [],
            "agent_trace": [],
            "foundry_citation_count": 0,
            "status": status,
        }
        self._append(self.log_path, event)
        return event

    def append_storage_upload(
        self,
        file_names: List[str],
        blob_names: List[str],
        local_paths: List[str],
        total_size: int,
        container: str,
        status: str = "uploaded",
    ) -> dict:
        """Record administrator source artifact uploads."""
        event = {
            "id": stable_id("evt", _now(), "storage", ",".join(file_names)),
            "timestamp": _now(),
            "kind": "storage",
            "user_role": "admin",
            "question_preview": ", ".join(file_names[:5]),
            "rag_provider": "admin",
            "answer_backend": "azure_blob",
            "retrieval_backend": "local_dir, azure_blob",
            "confidence": 0,
            "source_count": len(file_names),
            "duration_ms": 0,
            "answer_preview": "",
            "source_titles": file_names[:12],
            "agent_trace": [],
            "foundry_citation_count": 0,
            "status": status,
            "storage_container": container,
            "storage_bytes": total_size,
            "blob_names": blob_names[:12],
            "local_paths": local_paths[:12],
        }
        self._append(self.log_path, event)
        return event

    def create_ticket(self, payload: Dict[str, object]) -> dict:
        """Create a branch escalation ticket for IT users."""
        question = str(payload.get("question") or "")
        ticket = {
            "id": stable_id("ticket", _now(), question),
            "timestamp": _now(),
            "updated_at": _now(),
            "status": "new",
            "priority": str(payload.get("priority") or "normal"),
            "screen_name": str(payload.get("screen_name") or ""),
            "sender_name": str(payload.get("sender_name") or ""),
            "sender_employee_id": str(payload.get("sender_employee_id") or ""),
            "sender_role": str(payload.get("sender_role") or "branch"),
            "sender_role_code": str(payload.get("sender_role_code") or "01"),
            "recipient_name": str(payload.get("recipient_name") or ""),
            "recipient_employee_id": str(payload.get("recipient_employee_id") or ""),
            "recipient_role": str(payload.get("recipient_role") or "it"),
            "recipient_role_code": str(payload.get("recipient_role_code") or "02"),
            "question": question,
            "summary": str(payload.get("summary") or ""),
            "answer_backend": str(payload.get("answer_backend") or ""),
            "rag_provider": str(payload.get("rag_provider") or ""),
            "retrieval_backend": str(payload.get("retrieval_backend") or ""),
            "confidence": payload.get("confidence", 0),
            "source_count": int(payload.get("source_count") or 0),
            "sources": _ticket_sources(payload),
            "replies": [],
        }
        ticket["source_count"] = len(ticket["sources"])
        self._append(self.ticket_path, ticket)
        self._append(
            self.log_path,
            {
                "id": stable_id("evt", ticket["id"], "ticket"),
                "timestamp": ticket["timestamp"],
                "kind": "ticket",
                "user_role": "branch",
                "question_preview": _preview(question),
                "rag_provider": ticket["rag_provider"],
                "answer_backend": ticket["answer_backend"],
                "retrieval_backend": ticket["retrieval_backend"],
                "confidence": ticket["confidence"],
                "source_count": ticket["source_count"],
                "status": "sent_to_it",
            },
        )
        return ticket

    def add_ticket_reply(self, ticket_id: str, payload: Dict[str, object]) -> dict:
        """Add a reply to a support ticket and return the updated ticket."""
        rows = [self._normalize_ticket(row) for row in self._read(self.ticket_path)]
        for ticket in rows:
            if ticket.get("id") != ticket_id:
                continue
            reply = {
                "id": stable_id("reply", ticket_id, _now(), str(payload.get("body") or "")),
                "timestamp": _now(),
                "author_name": str(payload.get("author_name") or ""),
                "author_employee_id": str(payload.get("author_employee_id") or ""),
                "author_role": str(payload.get("author_role") or "it"),
                "author_role_code": str(payload.get("author_role_code") or "02"),
                "body": str(payload.get("body") or ""),
            }
            replies = ticket.setdefault("replies", [])
            if isinstance(replies, list):
                replies.append(reply)
            else:
                ticket["replies"] = [reply]
            ticket["updated_at"] = reply["timestamp"]
            ticket["status"] = "replied" if reply["author_role"] in {"it", "admin"} else "branch_updated"
            self._write(self.ticket_path, rows)
            self._append(
                self.log_path,
                {
                    "id": stable_id("evt", reply["id"], "reply"),
                    "timestamp": reply["timestamp"],
                    "kind": "ticket",
                    "user_role": reply["author_role"],
                    "question_preview": _preview(str(ticket.get("question") or "")),
                    "rag_provider": str(ticket.get("rag_provider") or ""),
                    "answer_backend": str(ticket.get("answer_backend") or ""),
                    "retrieval_backend": str(ticket.get("retrieval_backend") or ""),
                    "confidence": ticket.get("confidence", 0),
                    "source_count": ticket.get("source_count", 0),
                    "status": "ticket_replied",
                },
            )
            return ticket
        raise KeyError(ticket_id)

    def list_logs(self, limit: int = 80) -> List[dict]:
        """Return recent runtime events newest first."""
        return list(reversed(self._read(self.log_path)[-limit:]))

    def list_tickets(self, limit: int = 80) -> List[dict]:
        """Return recent support tickets newest first."""
        rows = [self._normalize_ticket(row) for row in self._read(self.ticket_path)]
        return list(reversed(rows[-limit:]))

    def admin_dashboard(self, limit: int = 200) -> dict:
        """Aggregate runtime telemetry for the administrator dashboard."""
        logs = self.list_logs(limit=limit)
        tickets = self.list_tickets(limit=limit)
        chat_logs = [log for log in logs if log.get("kind") == "chat"]
        storage_logs = [log for log in logs if log.get("kind") == "storage"]
        ingest_logs = [log for log in logs if log.get("kind") == "ingest"]
        durations = [float(log.get("duration_ms") or 0) for log in chat_logs if log.get("duration_ms")]
        grounded = [log for log in chat_logs if int(log.get("source_count") or 0) > 0]
        cloud_logs = [log for log in chat_logs if _is_cloud_route(log)]
        blocked = [log for log in chat_logs if log.get("status") == "blocked"]
        total_storage_bytes = sum(int(log.get("storage_bytes") or 0) for log in storage_logs)
        return {
            "generated_at": _now(),
            "window_log_count": len(logs),
            "totals": {
                "chat_count": len(chat_logs),
                "ticket_count": len(tickets),
                "open_ticket_count": len(
                    [ticket for ticket in tickets if ticket.get("status") not in {"replied", "closed"}]
                ),
                "cloud_answer_count": len(cloud_logs),
                "local_answer_count": max(0, len(chat_logs) - len(cloud_logs)),
                "storage_upload_count": len(storage_logs),
                "storage_uploaded_bytes": total_storage_bytes,
                "ingest_count": len(ingest_logs),
                "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0,
                "avg_source_count": round(
                    sum(int(log.get("source_count") or 0) for log in chat_logs) / len(chat_logs), 1
                )
                if chat_logs
                else 0,
            },
            "kpis": [
                _kpi(
                    "근거 포함률",
                    _ratio(len(grounded), len(chat_logs)),
                    "답변 로그 중 1개 이상 근거가 붙은 비율",
                    "90% 이상",
                    "소스/검색 연결 누락 여부 검증",
                ),
                _kpi(
                    "클라우드 경로 사용률",
                    _ratio(len(cloud_logs), len(chat_logs)),
                    "Foundry 또는 Azure AI Search를 거친 답변 비율",
                    "데모 모드 60% 이상",
                    "MS 경로 전환과 fallback 동작 검증",
                ),
                _kpi(
                    "차단/범위외 비율",
                    _ratio(len(blocked), len(chat_logs)),
                    "무관 질문, 보안 위험 질문 차단 비율",
                    "업무 외 질문 100% 차단",
                    "역할별 guardrail 회귀 테스트",
                ),
                _kpi(
                    "미해결 쪽지",
                    str(len([ticket for ticket in tickets if ticket.get("status") not in {"replied", "closed"}])),
                    "IT 답장이 필요한 영업점 쪽지 수",
                    "운영 중 0건 유지",
                    "쪽지 처리 SLA 모니터링",
                ),
            ],
            "route_counts": _count_by(chat_logs, "answer_backend"),
            "retrieval_counts": _count_multi(chat_logs, "retrieval_backend"),
            "role_counts": _count_by(chat_logs, "user_role"),
            "recent_model_events": [
                {
                    "id": log.get("id", ""),
                    "timestamp": log.get("timestamp", ""),
                    "role": log.get("user_role", "unknown"),
                    "question_preview": log.get("question_preview", ""),
                    "answer_preview": log.get("answer_preview", ""),
                    "answer_backend": log.get("answer_backend", ""),
                    "retrieval_backend": log.get("retrieval_backend", ""),
                    "duration_ms": log.get("duration_ms", 0),
                    "source_count": log.get("source_count", 0),
                    "source_titles": log.get("source_titles", []),
                    "agent_trace": log.get("agent_trace", []),
                }
                for log in chat_logs[:10]
            ],
            "recent_storage_events": [
                {
                    "id": log.get("id", ""),
                    "timestamp": log.get("timestamp", ""),
                    "files": log.get("source_titles", []),
                    "blob_names": log.get("blob_names", []),
                    "local_paths": log.get("local_paths", []),
                    "bytes": log.get("storage_bytes", 0),
                    "status": log.get("status", ""),
                }
                for log in storage_logs[:8]
            ],
        }

    def _append(self, path: Path, item: dict) -> None:
        rows = self._read(path)
        rows.append(item)
        self._write(path, rows[-500:])

    def _write(self, path: Path, rows: List[dict]) -> None:
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self, path: Path) -> List[dict]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _normalize_ticket(self, ticket: dict) -> dict:
        normalized = dict(ticket)
        normalized.setdefault("updated_at", normalized.get("timestamp", ""))
        normalized.setdefault("sender_name", "")
        normalized.setdefault("sender_employee_id", "")
        normalized.setdefault("sender_role", "branch")
        normalized.setdefault("sender_role_code", "01")
        normalized.setdefault("recipient_name", "")
        normalized.setdefault("recipient_employee_id", "")
        normalized.setdefault("recipient_role", "it")
        normalized.setdefault("recipient_role_code", "02")
        normalized["sources"] = _safe_sources(normalized.get("sources"))
        replies = normalized.get("replies")
        normalized["replies"] = replies if isinstance(replies, list) else []
        return normalized


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(text: str, limit: int = 140) -> str:
    compact = " ".join((text or "").split())
    return compact[:limit]


def _source_titles(sources: List[object]) -> List[str]:
    titles: List[str] = []
    for source in sources[:12]:
        if isinstance(source, dict):
            title = str(source.get("title") or source.get("source_path") or "")
            if title:
                titles.append(title)
    return titles


def _foundry_source_count(sources: List[object]) -> int:
    return len(
        [
            source
            for source in sources
            if isinstance(source, dict) and str(source.get("retrieval_backend") or "") == "foundry"
        ]
    )


def _is_cloud_route(log: dict) -> bool:
    return str(log.get("answer_backend") or "") == "foundry" or "azure" in str(
        log.get("retrieval_backend") or ""
    ).lower()


def _ratio(part: int, total: int) -> str:
    if total <= 0:
        return "0%"
    return f"{round(part / total * 100)}%"


def _kpi(name: str, value: str, description: str, target: str, verification: str) -> dict:
    return {
        "name": name,
        "value": value,
        "description": description,
        "target": target,
        "verification": verification,
    }


def _count_by(logs: List[dict], key: str) -> List[dict]:
    counts: Dict[str, int] = {}
    for log in logs:
        label = str(log.get(key) or "-")
        counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def _count_multi(logs: List[dict], key: str) -> List[dict]:
    counts: Dict[str, int] = {}
    for log in logs:
        labels = [part.strip() for part in str(log.get(key) or "-").split(",") if part.strip()]
        for label in labels or ["-"]:
            counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": count} for label, count in sorted(counts.items())]


def _safe_sources(value: object) -> List[dict]:
    if not isinstance(value, list):
        return []
    sources: List[dict] = []
    for item in value[:12]:
        if isinstance(item, dict):
            sources.append(
                {
                    "doc_id": str(item.get("doc_id") or ""),
                    "title": str(item.get("title") or ""),
                    "business_name": str(item.get("business_name") or ""),
                    "screen_id": str(item.get("screen_id") or ""),
                    "screen_name": str(item.get("screen_name") or ""),
                    "source_path": str(item.get("source_path") or ""),
                    "line_range": str(item.get("line_range") or ""),
                    "reason": str(item.get("reason") or ""),
                    "api_path": item.get("api_path"),
                    "http_method": item.get("http_method"),
                    "api_description": item.get("api_description"),
                    "class_name": item.get("class_name"),
                    "method_name": item.get("method_name"),
                    "sql_id": item.get("sql_id"),
                    "tables": item.get("tables") if isinstance(item.get("tables"), list) else [],
                    "columns": item.get("columns") if isinstance(item.get("columns"), list) else [],
                    "dto_names": item.get("dto_names") if isinstance(item.get("dto_names"), list) else [],
                    "dto_fields": item.get("dto_fields") if isinstance(item.get("dto_fields"), list) else [],
                    "input_fields": item.get("input_fields") if isinstance(item.get("input_fields"), list) else [],
                    "validation_conditions": item.get("validation_conditions")
                    if isinstance(item.get("validation_conditions"), list)
                    else [],
                    "exception_types": item.get("exception_types") if isinstance(item.get("exception_types"), list) else [],
                    "auth_codes": item.get("auth_codes") if isinstance(item.get("auth_codes"), list) else [],
                    "call_chain": item.get("call_chain") if isinstance(item.get("call_chain"), list) else [],
                    "error_codes": item.get("error_codes") if isinstance(item.get("error_codes"), list) else [],
                    "error_messages": item.get("error_messages") if isinstance(item.get("error_messages"), list) else [],
                    "retrieval_backend": item.get("retrieval_backend"),
                }
            )
    return sources


def _ticket_sources(payload: Dict[str, object]) -> List[dict]:
    """Prefer IT-visible technical citations for branch escalation tickets."""
    fallback = _safe_sources(payload.get("sources"))
    sender_role = str(payload.get("sender_role") or "branch")
    if sender_role != "branch":
        return fallback
    has_chat_route = any(
        str(payload.get(key) or "") for key in ("answer_backend", "rag_provider", "retrieval_backend")
    )
    if not has_chat_route:
        return fallback
    question = str(payload.get("question") or "")
    summary = str(payload.get("summary") or "")
    technical_sources = _retrieve_it_sources(question, summary, str(payload.get("screen_name") or ""))
    return technical_sources or fallback


def _retrieve_it_sources(question: str, summary: str, screen_name: str = "") -> List[dict]:
    """Build technical source citations without making LLM calls."""
    try:
        from backend.app.rag.citation_builder import CitationBuilder
        from backend.app.retrieval.graph_store import GraphExpander
        from backend.app.retrieval.query_analyzer import QueryAnalyzer
        from backend.app.storage.elastic import KnowledgeIndex
    except Exception:
        return []

    query_text = "\n".join(part for part in [question, summary] if part)
    if not query_text.strip():
        return []
    try:
        intent = QueryAnalyzer().analyze(query_text, screen_name=screen_name or None)
        index = KnowledgeIndex()
        docs = index.load_documents()
        ranked = sorted(
            ((doc, _ticket_doc_score(doc, intent)) for doc in docs),
            key=lambda pair: pair[1],
            reverse=True,
        )
        seed_docs = [doc for doc, score in ranked if score > 0][:8]
        if not seed_docs:
            return []
        expanded = GraphExpander().expand(seed_docs, docs)
        technical_docs = [
            doc
            for doc in expanded
            if doc.source_path or doc.api_path or doc.sql_id or doc.tables or doc.dto_names
        ][:8]
        return CitationBuilder().build(technical_docs, "it")
    except Exception:
        return []


def _ticket_doc_score(doc: object, intent: object) -> float:
    """Small deterministic scorer for ticket evidence hydration."""
    searchable = str(getattr(doc, "searchable_text")()).lower()
    score = 0.0
    screen_id = getattr(intent, "screen_id", None)
    screen_name = getattr(intent, "screen_name", None)
    action = getattr(intent, "action", None)
    error_message = getattr(intent, "error_message", None)
    keywords = getattr(intent, "keywords", []) or []
    if screen_id and getattr(doc, "screen_id", "") == screen_id:
        score += 10
    if screen_name and screen_name in str(getattr(doc, "screen_name", "")):
        score += 8
    if action and action in searchable:
        score += 4
    if error_message:
        joined_errors = " ".join(
            list(getattr(doc, "error_messages", []) or []) + list(getattr(doc, "business_rules", []) or [])
        )
        if error_message in joined_errors or error_message in str(getattr(doc, "summary", "")):
            score += 5
    for keyword in keywords:
        if len(str(keyword)) >= 2 and str(keyword).lower() in searchable:
            score += 1
    if getattr(doc, "api_path", ""):
        score += 0.4
    if getattr(doc, "source_path", ""):
        score += 0.2
    return score
