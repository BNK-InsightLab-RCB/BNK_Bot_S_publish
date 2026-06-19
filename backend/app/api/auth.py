"""Demo authentication API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.auth_store import AuthStore, AuthStoreError
from backend.app.schemas import AuthResponse, LoginRequest, SignupRequest


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup(request: SignupRequest) -> dict:
    """Create a demo user with a role code."""
    try:
        user = AuthStore().create_user(
            real_name=request.real_name,
            employee_id=request.employee_id,
            password=request.password,
            role_code=request.role_code,
        )
    except AuthStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": user}


@router.post("/login", response_model=AuthResponse)
def login(request: LoginRequest) -> dict:
    """Authenticate a demo user."""
    try:
        user = AuthStore().authenticate(request.employee_id, request.password)
    except AuthStoreError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"user": user}
