"""Small JSON-backed runtime store for demo logs and branch-to-IT tickets."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

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

    def append_chat(self, question: str, user_role: str, response: Dict[str, object]) -> dict:
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
            "status": "blocked"
            if metadata.get("blocked_by_safety") or metadata.get("blocked_by_scope")
            else "answered",
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
            "sources": _safe_sources(payload.get("sources")),
            "replies": [],
        }
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
                    "source_path": str(item.get("source_path") or ""),
                    "line_range": str(item.get("line_range") or ""),
                    "reason": str(item.get("reason") or ""),
                    "api_path": item.get("api_path"),
                    "class_name": item.get("class_name"),
                    "method_name": item.get("method_name"),
                    "sql_id": item.get("sql_id"),
                    "tables": item.get("tables") if isinstance(item.get("tables"), list) else [],
                    "retrieval_backend": item.get("retrieval_backend"),
                }
            )
    return sources
