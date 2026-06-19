"""JSON-backed demo authentication store."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from backend.app.utils.hashing import stable_id


DATA_DIR = Path("data")
USERS_PATH = DATA_DIR / "users.json"
PBKDF2_ITERATIONS = 210_000

ROLE_BY_CODE = {
    "01": {"role": "branch", "role_label": "영업점 직원"},
    "02": {"role": "it", "role_label": "IT 개발직원"},
    "03": {"role": "admin", "role_label": "관리자"},
}


class AuthStoreError(RuntimeError):
    """Raised when demo auth cannot complete."""


class AuthStore:
    """Persist demo users without storing plaintext passwords."""

    def __init__(self, path: Path = USERS_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create_user(
        self,
        real_name: str,
        employee_id: str,
        password: str,
        role_code: str,
    ) -> dict:
        """Create a user and return public profile fields."""
        real_name = _clean(real_name)
        employee_id = _clean(employee_id)
        role_code = _clean(role_code)
        if not real_name:
            raise AuthStoreError("실명을 입력해 주세요.")
        if not employee_id:
            raise AuthStoreError("행번을 입력해 주세요.")
        if len(password) < 4:
            raise AuthStoreError("비밀번호는 4자 이상 입력해 주세요.")
        if role_code not in ROLE_BY_CODE:
            raise AuthStoreError("권한코드가 올바르지 않습니다.")

        users = self._read()
        if any(user.get("employee_id") == employee_id for user in users):
            raise AuthStoreError("이미 등록된 행번입니다.")

        role_info = ROLE_BY_CODE[role_code]
        salt = secrets.token_bytes(16)
        user = {
            "id": stable_id("user", employee_id),
            "real_name": real_name,
            "employee_id": employee_id,
            "role": role_info["role"],
            "role_code": role_code,
            "role_label": role_info["role_label"],
            "password_hash": _hash_password(password, salt),
            "password_salt": base64.b64encode(salt).decode("ascii"),
            "created_at": _now(),
        }
        users.append(user)
        self._write(users)
        return _public_user(user)

    def authenticate(self, employee_id: str, password: str) -> dict:
        """Authenticate by employee id and password."""
        employee_id = _clean(employee_id)
        users = self._read()
        for user in users:
            if user.get("employee_id") != employee_id:
                continue
            salt = base64.b64decode(str(user.get("password_salt") or ""))
            expected = str(user.get("password_hash") or "")
            if hmac.compare_digest(_hash_password(password, salt), expected):
                return _public_user(user)
            break
        raise AuthStoreError("행번 또는 비밀번호가 올바르지 않습니다.")

    def _read(self) -> List[Dict[str, object]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _write(self, users: List[Dict[str, object]]) -> None:
        self.path.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return base64.b64encode(digest).decode("ascii")


def _public_user(user: Dict[str, object]) -> dict:
    return {
        "id": str(user.get("id") or ""),
        "real_name": str(user.get("real_name") or ""),
        "employee_id": str(user.get("employee_id") or ""),
        "role": str(user.get("role") or ""),
        "role_code": str(user.get("role_code") or ""),
        "role_label": str(user.get("role_label") or ""),
    }


def _clean(value: str) -> str:
    return " ".join((value or "").split())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
