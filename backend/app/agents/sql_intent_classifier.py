"""Local Qwen router for SQL generation requests."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from backend.app.config import settings
from backend.app.llm.qwen_client import QwenClient


@dataclass(frozen=True)
class SQLIntentDecision:
    """Decision returned by the local SQL intent router."""

    is_sql_generation: bool
    raw_answer: str
    source: str


class SQLIntentClassifier:
    """Classify whether an IT question should go to the SQL generator agent."""

    def __init__(self, client: Optional[QwenClient] = None) -> None:
        self.client = client or QwenClient(
            timeout_seconds=min(settings.llm_timeout_seconds, 5)
        )

    def classify(self, question: str) -> SQLIntentDecision:
        """Return yes/no for SQL generation intent using local Qwen first."""
        raw_answer = self._ask_qwen(question)
        parsed = _parse_yes_no(raw_answer or "")
        if parsed is not None:
            return SQLIntentDecision(
                is_sql_generation=parsed,
                raw_answer="yes" if parsed else "no",
                source="qwen",
            )
        fallback = _heuristic_sql_generation(question)
        return SQLIntentDecision(
            is_sql_generation=fallback,
            raw_answer="yes" if fallback else "no",
            source="heuristic",
        )

    def _ask_qwen(self, question: str) -> Optional[str]:
        return self.client.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "너는 라우팅 분류기다. 사용자의 질문이 새 SQL 쿼리 작성, 생성, 수정, "
                        "SELECT/INSERT/UPDATE/DELETE 쿼리 초안 작성 요청이면 yes만 답한다. "
                        "오류 원인 분석, RAG 근거 요약, API/서비스/SQL 근거 확인, 기존 SQL 위치 "
                        "설명 요청이면 no만 답한다. 반드시 소문자 yes 또는 no 한 단어만 출력한다."
                    ),
                },
                {"role": "user", "content": question},
            ],
            temperature=0,
            enable_thinking=False,
        )


def _parse_yes_no(value: str) -> Optional[bool]:
    normalized = re.sub(r"[^a-zA-Z가-힣]", "", value or "").lower()
    if normalized.startswith("yes") or normalized in {"예", "네", "맞음"}:
        return True
    if normalized.startswith("no") or normalized in {"아니오", "아니요", "아님"}:
        return False
    return None


def _heuristic_sql_generation(question: str) -> bool:
    normalized = " ".join((question or "").lower().split())
    if not normalized:
        return False
    negative = [
        "근거",
        "원인",
        "어디서",
        "확인",
        "분석",
        "요약",
    ]
    sql_terms = ["sql", "쿼리", "select", "insert", "update", "delete"]
    generation_verbs = ["만들", "작성", "생성", "짜줘", "짜 줘", "초안"]
    if any(term in normalized for term in sql_terms) and any(
        term in normalized for term in generation_verbs
    ):
        return True
    statement_terms = ["select문", "insert문", "update문", "delete문"]
    if any(term in normalized for term in statement_terms):
        return not any(term in normalized for term in negative)
    return False
