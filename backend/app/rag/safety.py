"""Role-based answer safety."""

from __future__ import annotations

import re
from typing import Dict

from backend.app.parsers.base import KnowledgeDocument
from backend.app.utils.text import mask_sensitive


GLOBAL_FORBIDDEN_PATTERNS = [
    re.compile(r"권한\s*우회"),
    re.compile(r"보안\s*로직\s*우회"),
    re.compile(r"운영\s*DB.*직접\s*수정"),
    re.compile(r"비밀번호|패스워드|토큰|시크릿|secret|private_key|api[_-]?key", re.IGNORECASE),
    re.compile(r"admin\s*key|connection\s*string|sas\s*token|\.env", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"시스템\s*프롬프트|개발자\s*메시지|숨겨진\s*지시"),
]

BRANCH_SCOPE_TERMS = {
    "업무",
    "화면",
    "오류",
    "문구",
    "저장",
    "조회",
    "등록",
    "수정",
    "승인",
    "발급",
    "변경",
    "해제",
    "연장",
    "환매",
    "송금",
    "권한",
    "고객",
    "계좌",
    "전표",
    "이체",
    "자동이체",
    "납부자",
    "출금",
    "입금",
    "잔액",
    "카드",
    "대출",
    "펀드",
    "외화",
    "현금",
    "인증",
    "한도",
    "해지",
    "휴면",
}


def is_forbidden_question(question: str, user_role: str = "branch") -> bool:
    """Return true when the question requests disallowed guidance."""
    _ = user_role
    if any(pattern.search(question) for pattern in GLOBAL_FORBIDDEN_PATTERNS):
        return True
    return False


def is_out_of_scope_question(question: str, user_role: str = "branch") -> bool:
    """Scope blocking is disabled for the demo so every non-forbidden question reaches RAG."""
    _ = (question, user_role)
    return False


def refusal_answer() -> str:
    """Return a role-safe refusal with a normal support path."""
    return (
        "[가능한 원인]\n"
        "요청하신 내용은 내부 정보 또는 보안 정책과 관련되어 저는 알려드릴 수 없습니다.\n\n"
        "[먼저 확인할 사항]\n"
        "1. 화면에 표시된 오류 문구와 수행한 업무를 기준으로 다시 문의해 주세요.\n"
        "2. 권한, 고객 상태, 입력값처럼 실제 업무 처리에 필요한 확인 항목만 요청해 주세요.\n\n"
        "[계속 오류가 발생하는 경우]\n"
        "정상 장애 문의로 접수하면 IT부서가 필요한 내부 정보는 별도 권한으로 확인합니다.\n\n"
        "[IT부서 전달용 정보]\n"
        "- 화면명\n"
        "- 수행 작업\n"
        "- 오류 문구\n"
        "- 발생 시각\n"
        "- 재시도 여부\n\n"
        "[근거]\n"
        "보안 정책상 소스코드, 비밀값, 내부 경로, 우회 방법은 제공하지 않습니다.\n\n"
        "[조치 후 재시도]\n"
        "위 조건을 확인한 뒤 업무 오류 내용으로 다시 문의해 주세요. "
        "동일 오류가 계속되면 화면명, 오류 문구, 발생 시각을 정리해 IT부서에 전달해 주세요."
    )


def out_of_scope_answer() -> str:
    """Return a branch-safe response for unrelated questions."""
    return (
        "[가능한 원인]\n"
        "이 챗봇은 영업점 업무 화면의 오류, 처리 조건, 권한 확인을 돕기 위한 도구입니다. "
        "현재 질문은 업무 처리 근거를 찾기 어렵습니다.\n\n"
        "[먼저 확인할 사항]\n"
        "1. 화면명 또는 업무명을 함께 적어 주세요.\n"
        "2. 화면에 표시된 오류 문구를 그대로 적어 주세요.\n"
        "3. 입력한 정보와 누른 버튼을 함께 적어 주세요.\n\n"
        "[계속 오류가 발생하는 경우]\n"
        "업무 화면 오류가 맞다면 화면명, 오류 문구, 발생 시각을 정리해 다시 문의해 주세요.\n\n"
        "[IT부서 전달용 정보]\n"
        "- 화면명\n"
        "- 수행 작업\n"
        "- 오류 문구\n"
        "- 발생 시각\n\n"
        "[근거]\n"
        "영업점 업무 지원 범위를 벗어난 질문은 답변하지 않습니다."
    )


def sanitize_answer(answer: str, user_role: str) -> str:
    """Mask credential-like strings without role-specific answer rewriting."""
    _ = user_role
    return mask_sensitive(answer)


def sanitize_source(doc: KnowledgeDocument, user_role: str) -> Dict[str, object]:
    """Serialize a source citation with the same detail for every role."""
    _ = user_role
    data = {
        "doc_id": doc.id,
        "title": doc.title,
        "business_name": doc.business_name or doc.screen_name or "",
        "screen_id": doc.screen_id,
        "screen_name": doc.screen_name or "",
        "source_path": doc.source_path,
        "line_range": f"{doc.start_line}-{doc.end_line}",
        "reason": _safe_reason(doc, user_role),
        "error_codes": doc.error_codes,
        "error_messages": doc.error_messages,
        "input_fields": doc.input_fields,
        "retrieval_backend": doc.metadata.get("retrieval_backend"),
        "api_path": doc.api_path,
        "http_method": doc.http_method,
        "api_description": doc.api_description,
        "class_name": doc.class_name,
        "method_name": doc.method_name,
        "sql_id": doc.sql_id,
        "tables": doc.tables,
        "columns": doc.columns,
        "dto_names": doc.dto_names,
        "dto_fields": doc.dto_fields,
        "validation_conditions": doc.validation_conditions,
        "exception_types": doc.exception_types,
        "auth_codes": doc.auth_codes,
        "call_chain": doc.call_chain,
    }
    return data

def _safe_reason(doc: KnowledgeDocument, user_role: str) -> str:
    details = [doc.summary]
    if doc.api_description:
        details.append(f"API 역할: {doc.api_description}")
    if doc.validation_conditions:
        details.append("검증조건: " + "; ".join(doc.validation_conditions[:5]))
    if doc.exception_types:
        details.append("예외: " + ", ".join(doc.exception_types))
    return sanitize_answer(" ".join(detail for detail in details if detail), user_role)
