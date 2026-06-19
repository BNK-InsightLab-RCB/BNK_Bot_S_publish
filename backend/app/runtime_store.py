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
            "status": "blocked" if metadata.get("blocked_by_safety") else "answered",
        }
        self._append(self.log_path, event)
        return event

    def create_ticket(self, payload: Dict[str, object]) -> dict:
        """Create a branch escalation ticket for IT users."""
        question = str(payload.get("question") or "")
        ticket = {
            "id": stable_id("ticket", _now(), question),
            "timestamp": _now(),
            "status": "new",
            "priority": str(payload.get("priority") or "normal"),
            "screen_name": str(payload.get("screen_name") or ""),
            "question": question,
            "summary": str(payload.get("summary") or ""),
            "answer_backend": str(payload.get("answer_backend") or ""),
            "rag_provider": str(payload.get("rag_provider") or ""),
            "retrieval_backend": str(payload.get("retrieval_backend") or ""),
            "confidence": payload.get("confidence", 0),
            "source_count": int(payload.get("source_count") or 0),
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

    def list_logs(self, limit: int = 80) -> List[dict]:
        """Return recent runtime events newest first."""
        return list(reversed(self._read(self.log_path)[-limit:]))

    def list_tickets(self, limit: int = 80) -> List[dict]:
        """Return recent support tickets newest first."""
        return list(reversed(self._read(self.ticket_path)[-limit:]))

    def _append(self, path: Path, item: dict) -> None:
        rows = self._read(path)
        rows.append(item)
        path.write_text(json.dumps(rows[-500:], ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self, path: Path) -> List[dict]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(text: str, limit: int = 140) -> str:
    compact = " ".join((text or "").split())
    return compact[:limit]
