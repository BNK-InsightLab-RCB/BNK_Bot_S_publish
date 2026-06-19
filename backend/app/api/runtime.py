"""Runtime logs and IT escalation APIs."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.runtime_store import RuntimeStore
from backend.app.schemas import SupportTicketRequest


router = APIRouter(prefix="/api/runtime", tags=["runtime"])


@router.get("/logs")
def runtime_logs(limit: int = Query(default=80, ge=1, le=200)) -> dict:
    """Return recent chat/ticket execution logs for administrators."""
    return {"logs": RuntimeStore().list_logs(limit=limit)}


@router.get("/tickets")
def support_tickets(limit: int = Query(default=80, ge=1, le=200)) -> dict:
    """Return branch escalation tickets for IT users."""
    return {"tickets": RuntimeStore().list_tickets(limit=limit)}


@router.post("/tickets")
def create_support_ticket(request: SupportTicketRequest) -> dict:
    """Create a support ticket from the branch chatbot screen."""
    return {"ticket": RuntimeStore().create_ticket(request.model_dump())}
