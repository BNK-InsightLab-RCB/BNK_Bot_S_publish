import json

import httpx

from backend.app.foundry.agent_client import (
    FoundryCitation,
    _extract_citations,
    _extract_text,
    _requires_semantic_retry,
)
from backend.app.storage.azure_search import _hit_from_payload, _search_body, dumps_schema_preview


def test_foundry_citation_hides_source_path_for_branch_users():
    citation = FoundryCitation(title="CustomerService.java", url="https://example.com/source")

    branch_source = citation.to_source(0, user_role="branch")
    it_source = citation.to_source(0, user_role="it")

    assert branch_source["title"] == "Foundry 검색 근거"
    assert branch_source["source_path"] == ""
    assert it_source["title"] == "CustomerService.java"
    assert it_source["source_path"] == "https://example.com/source"


def test_foundry_response_helpers_extract_text_and_citations():
    body = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "검색 근거 기반 답변입니다.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "title": "업무 규칙",
                                "url": "https://example.com/rule",
                            }
                        ],
                    }
                ],
            }
        ]
    }

    assert _extract_text(body) == "검색 근거 기반 답변입니다."
    citations = _extract_citations(body)
    assert len(citations) == 1
    assert citations[0].title == "업무 규칙"
    assert citations[0].url == "https://example.com/rule"


def test_foundry_semantic_retry_detects_integrated_vectorizer_error():
    request = httpx.Request("POST", "https://example.test/openai/v1/responses")
    response = httpx.Response(
        400,
        request=request,
        json={
            "error": {
                "message": "Query type vector_semantic_hybrid requires a vector field with integrated vectorizer"
            }
        },
    )

    assert _requires_semantic_retry(response)


def test_azure_search_schema_has_required_foundry_fields():
    schema = json.loads(dumps_schema_preview(embedding_dim=384))
    field_names = {field["name"] for field in schema["fields"]}

    assert "content" in field_names
    assert "source_url" in field_names
    assert "business_name" in field_names
    assert "api_description" in field_names
    assert "dto_fields" in field_names
    assert "validation_conditions" in field_names
    assert "exception_types" in field_names
    assert "content_vector" in field_names
    vector_field = next(field for field in schema["fields"] if field["name"] == "content_vector")
    assert vector_field["dimensions"] == 384
    assert vector_field["vectorSearchProfile"] == "ops-vector-profile"
    assert schema["vectorSearch"]["algorithms"][0]["hnswParameters"]["metric"] == "cosine"
    assert schema["vectorSearch"]["profiles"]
    assert schema["semantic"]["configurations"]
    assert schema["defaultScoringProfile"] == "ops-source-priority"


def test_azure_search_hybrid_body_uses_vector_and_semantic_reranker():
    body = _search_body("자동이체 오류", top_k=5, vector=[0.1, 0.2, 0.3])

    assert body["search"] == "자동이체 오류"
    assert body["queryType"] == "semantic"
    assert body["semanticConfiguration"] == "ops-semantic-config"
    assert body["top"] == 5
    assert body["vectorQueries"][0]["kind"] == "vector"
    assert body["vectorQueries"][0]["fields"] == "content_vector"
    assert body["vectorQueries"][0]["k"] == 50
    assert "content_vector" not in body["select"]


def test_azure_search_hit_payload_converts_to_knowledge_document():
    hit = _hit_from_payload(
        {
            "@search.score": 3.2,
            "@search.rerankerScore": 2.1,
            "id": "doc-1",
            "doc_type": "frontend_event",
            "title": "AutoDebitRegister.vue > registerAutoDebit",
            "business_name": "자동이체 등록",
            "screen_name": "자동이체 등록",
            "api_description": "등록 버튼에서 자동이체 등록 API를 호출한다.",
            "dto_fields": ["withdrawAccountNo", "payerNo"],
            "validation_conditions": ["!form.withdrawAccountNo"],
            "exception_types": ["BizException"],
            "error_messages": ["납부자번호 형식을 확인하세요."],
            "branch_guide": "납부자번호 형식을 먼저 확인해야 합니다.",
            "source_path": "backend/examples/bank_sample/frontend/ops_scenarios/AutoDebitRegister.vue",
            "start_line": 10,
            "end_line": 20,
        }
    )

    assert hit.score == 3.2
    assert hit.reranker_score == 2.1
    assert hit.document.id == "doc-1"
    assert hit.document.business_name == "자동이체 등록"
    assert hit.document.screen_name == "자동이체 등록"
    assert hit.document.api_description == "등록 버튼에서 자동이체 등록 API를 호출한다."
    assert hit.document.dto_fields == ["withdrawAccountNo", "payerNo"]
    assert hit.document.validation_conditions == ["!form.withdrawAccountNo"]
    assert hit.document.exception_types == ["BizException"]
    assert hit.document.error_messages == ["납부자번호 형식을 확인하세요."]
    assert hit.document.metadata["retrieval_backend"] == "azure_ai_search"
