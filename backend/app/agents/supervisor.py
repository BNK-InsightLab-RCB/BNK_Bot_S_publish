"""Supervisor-style orchestration for local and Foundry-backed RAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import httpx

from backend.app.config import settings
from backend.app.foundry.agent_client import FoundryAgentClient
from backend.app.parsers.base import KnowledgeDocument
from backend.app.rag.answer_generator import AnswerGenerator
from backend.app.rag.safety import is_forbidden_question, is_out_of_scope_question, out_of_scope_answer
from backend.app.retrieval.context_builder import ContextBuilder
from backend.app.retrieval.elastic_searcher import HybridSearcher
from backend.app.retrieval.graph_store import GraphExpander
from backend.app.retrieval.query_analyzer import QueryAnalyzer
from backend.app.storage.azure_search import AzureSearchConfigError, AzureSearchKnowledgeIndex
from backend.app.storage.elastic import KnowledgeIndex


@dataclass
class AgentTrace:
    """Human-readable orchestration trace for demo/debug metadata."""

    steps: List[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.steps.append(message)


class SupervisorAgent:
    """Coordinate source retrieval, Foundry generation, and safety workers."""

    def __init__(
        self,
        answer_generator: Optional[AnswerGenerator] = None,
        foundry_client: Optional[FoundryAgentClient] = None,
    ) -> None:
        self.answer_generator = answer_generator or AnswerGenerator()
        self.foundry_client = foundry_client or FoundryAgentClient()

    def handle(
        self,
        question: str,
        user_role: str = "branch",
        screen_id: Optional[str] = None,
        screen_name: Optional[str] = None,
    ) -> Dict[str, object]:
        """Return a structured answer using the configured RAG provider."""
        provider = settings.rag_provider.lower().strip() or "local"
        trace = AgentTrace()
        if is_forbidden_question(question, user_role=user_role):
            trace.add("safety_worker: blocked disallowed request before retrieval")
            response = self.answer_generator.generate(
                question=question,
                docs=[],
                user_role=user_role,
                use_llm=False,
            )
            response["metadata"] = {
                "rag_provider": provider,
                "answer_backend": "safety",
                "local_ranked_count": 0,
                "expanded_doc_count": 0,
                "agent_trace": trace.steps,
                "blocked_by_safety": True,
            }
            return response
        if is_out_of_scope_question(question, user_role=user_role):
            trace.add("safety_worker: blocked out-of-scope branch request before retrieval")
            response = self.answer_generator.generate_from_external_answer(
                answer=out_of_scope_answer(),
                docs=[],
                user_role=user_role,
                confidence=0.1,
            )
            response["metadata"] = {
                "rag_provider": provider,
                "answer_backend": "scope_guard",
                "local_ranked_count": 0,
                "expanded_doc_count": 0,
                "agent_trace": trace.steps,
                "blocked_by_scope": True,
            }
            return response
        if provider in {"foundry", "multi_agent"} and _foundry_tool_configured():
            trace.add("foundry_agent_worker: agent-first route selected")
            foundry_response = self._ask_foundry(
                question,
                user_role,
                docs=[],
                trace=trace,
                agent_first=True,
            )
            if foundry_response:
                response = self.answer_generator.generate_from_external_answer(
                    answer=foundry_response.answer,
                    docs=[],
                    user_role=user_role,
                    confidence=0.82 if foundry_response.citations else 0.66,
                )
                response["sources"] = _merge_sources(
                    foundry_sources=[
                        citation.to_source(index, user_role)
                        for index, citation in enumerate(foundry_response.citations)
                    ],
                    local_sources=[],
                )
                response["metadata"] = {
                    "rag_provider": provider,
                    "answer_backend": "foundry",
                    "workflow": "foundry_agent_search_tool",
                    "local_ranked_count": 0,
                    "expanded_doc_count": 0,
                    "agent_trace": trace.steps,
                }
                return response
            trace.add("foundry_agent_worker: unavailable; falling back to server retrieval")
        if provider in {"foundry", "multi_agent"} and settings.azure_search_endpoint:
            docs, ranked_count = self._retrieve_azure(question, trace)
            if not docs:
                docs, ranked_count = self._retrieve_local(
                    question, screen_id, screen_name, user_role, trace
                )
        else:
            docs, ranked_count = self._retrieve_local(
                question, screen_id, screen_name, user_role, trace
            )
        if provider in {"foundry", "multi_agent"}:
            foundry_response = self._ask_foundry(question, user_role, docs, trace)
            if foundry_response:
                response = self.answer_generator.generate_from_external_answer(
                    answer=foundry_response.answer,
                    docs=docs,
                    user_role=user_role,
                    confidence=0.78 if foundry_response.citations else 0.68,
                )
                response["sources"] = _merge_sources(
                    foundry_sources=[
                        citation.to_source(index, user_role)
                        for index, citation in enumerate(foundry_response.citations)
                    ],
                    local_sources=response.get("sources", []),
                )
                response["metadata"] = {
                    "rag_provider": provider,
                    "answer_backend": "foundry",
                    "local_ranked_count": ranked_count,
                    "expanded_doc_count": len(docs),
                    "agent_trace": trace.steps,
                }
                return response
            trace.add("answer_worker: Foundry unavailable; local fallback selected")
        response = self.answer_generator.generate(
            question=question,
            docs=docs,
            user_role=user_role,
            use_llm=settings.enable_llm_chat,
        )
        response["metadata"] = {
            "rag_provider": provider,
            "answer_backend": "local",
            "local_ranked_count": ranked_count,
            "expanded_doc_count": len(docs),
            "agent_trace": trace.steps,
        }
        return response

    def _retrieve_local(
        self,
        question: str,
        screen_id: Optional[str],
        screen_name: Optional[str],
        user_role: str,
        trace: AgentTrace,
    ) -> Tuple[List[KnowledgeDocument], int]:
        analyzer = QueryAnalyzer()
        intent = analyzer.analyze(question, screen_id=screen_id, screen_name=screen_name)
        trace.add("supervisor: question analyzed")
        ranked = HybridSearcher().search(intent, user_role=user_role, top_k=12)
        seed_docs = [doc for doc, _ in ranked]
        all_docs = KnowledgeIndex().load_documents()
        docs = GraphExpander().expand(seed_docs, all_docs)[:12]
        trace.add(
            f"retrieval_worker: ranked {len(ranked)} docs and expanded to {len(docs)} docs"
        )
        return docs, len(ranked)

    def _retrieve_azure(
        self,
        question: str,
        trace: AgentTrace,
    ) -> Tuple[List[KnowledgeDocument], int]:
        try:
            hits = AzureSearchKnowledgeIndex().search_documents(question, top_k=12)
        except (AzureSearchConfigError, httpx.HTTPError, ValueError) as exc:
            trace.add(f"azure_search_worker: unavailable ({exc.__class__.__name__})")
            return [], 0
        selected_hits = _select_azure_hits(question, hits)
        docs = [hit.document for hit in selected_hits]
        trace.add(
            f"azure_search_worker: retrieved {len(docs)} relevant docs from "
            f"{len(hits)} Azure AI Search hits"
        )
        return docs, len(hits)

    def _ask_foundry(
        self,
        question: str,
        user_role: str,
        docs: List[KnowledgeDocument],
        trace: AgentTrace,
        agent_first: bool = False,
    ):
        context_hint = "" if agent_first else ContextBuilder(max_chars=4000).build(
            docs[:6],
            user_role=user_role,
        )
        if agent_first:
            trace.add("foundry_worker: delegating retrieval to Foundry Agent/Search tool")
        elif not _foundry_tool_configured():
            trace.add("foundry_worker: Search tool connection not configured; using Azure Search context hint")
        trace.add("foundry_worker: calling Microsoft Foundry")
        foundry_response = self.foundry_client.answer(
            question=question,
            user_role=user_role,
            context_hint=context_hint,
            agent_first=agent_first,
        )
        if foundry_response and foundry_response.answer:
            trace.add(
                f"foundry_worker: completed with {len(foundry_response.citations)} citations"
            )
            trace.add("safety_worker: local role guardrail applied")
            return foundry_response
        trace.add("foundry_worker: no usable answer returned")
        return None


def _merge_sources(
    foundry_sources: List[Dict[str, object]],
    local_sources: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    merged: List[Dict[str, object]] = []
    seen = set()
    for source in foundry_sources + local_sources:
        key = (source.get("doc_id"), source.get("title"), source.get("source_path"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(source)
    return merged[:12]


def _foundry_tool_configured() -> bool:
    return bool(settings.foundry_agent_name or settings.foundry_ai_search_connection_id)


def _select_azure_hits(question: str, hits) -> List[object]:
    if not hits:
        return []
    focus_terms = _focus_terms(question)
    if focus_terms:
        focused = [
            hit
            for hit in hits
            if any(term in hit.document.searchable_text().lower() for term in focus_terms)
        ]
        if focused:
            hits = focused
    reranker_scores = [hit.reranker_score for hit in hits if hit.reranker_score]
    if not reranker_scores:
        return hits[:6]
    best_score = max(reranker_scores)
    threshold = max(1.6, best_score - 0.75)
    selected = [hit for hit in hits if hit.reranker_score >= threshold]
    return (selected or hits[:3])[:6]


def _focus_terms(question: str) -> List[str]:
    normalized = question.lower()
    mappings = [
        ("자동이체", ["자동이체", "autodebit", "auto_debit"]),
        ("계좌이체", ["계좌이체", "transfer"]),
        ("잔액증명서", ["잔액증명서", "balancecertificate"]),
        ("휴면계좌", ["휴면계좌", "dormantaccount"]),
        ("카드 재발급", ["카드 재발급", "cardreissue"]),
        ("대출 만기연장", ["대출 만기연장", "loanextension"]),
        ("펀드 환매", ["펀드 환매", "fundredemption"]),
        ("고액현금", ["고액현금", "cashwithdrawal"]),
        ("법인사용자", ["법인사용자", "corporateuser"]),
        ("해외송금", ["해외송금", "foreignremittance"]),
        ("전표", ["전표", "slip"]),
    ]
    for trigger, terms in mappings:
        if trigger in normalized:
            return [term.lower() for term in terms]
    return []
