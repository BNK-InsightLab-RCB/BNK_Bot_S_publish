import json

from backend.app.parsers.base import SourceFile
from backend.app.parsers.uploaded_document_parser import UploadedDocumentParser


def test_uploaded_json_parser_maps_admin_schema(tmp_path):
    path = tmp_path / "auto_debit_rule.json"
    path.write_text(
        json.dumps(
            {
                "업무명": "자동이체 등록",
                "화면번호": "AUTO_710",
                "화면정보": {"button": "등록"},
                "API": {"path": "/api/ops/auto-debit/register", "role": "자동이체 등록 처리"},
                "dto": ["AutoDebitRequest"],
                "error": ["ACCOUNT_UNAVAILABLE"],
                "exception": ["BizException"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    docs = UploadedDocumentParser().parse(SourceFile(path=path, language="json", text=path.read_text()))

    assert len(docs) == 1
    doc = docs[0]
    assert doc.business_name == "자동이체 등록"
    assert doc.screen_id == "AUTO_710"
    assert doc.api_path == "/api/ops/auto-debit/register"
    assert doc.dto_names == ["AutoDebitRequest"]
    assert doc.error_codes == ["ACCOUNT_UNAVAILABLE"]
    assert doc.exception_types == ["BizException"]


def test_uploaded_json_parser_maps_exported_json_page_schema(tmp_path):
    path = tmp_path / "card_issue_page.json"
    path.write_text(
        json.dumps(
            {
                "업무명": "카드 발급",
                "화면번호": "CARD_010",
                "화면명": "카드발급 확인",
                "화면정보": {"button": "발급"},
                "API": {
                    "path": "/api/cards/issue",
                    "method": "POST",
                    "role": "카드 발급 신청 처리",
                    "call_chain": ["CardController.issueCard", "CardService.issueCard"],
                },
                "dto": {
                    "names": ["CardIssueRequest"],
                    "fields": ["customerNo", "cardProductCd"],
                    "input_fields": ["customerNo"],
                },
                "error": {
                    "codes": ["CARD_LIMIT_EXCEEDED"],
                    "messages": ["월 재발급 횟수를 초과했습니다."],
                    "possible": [{"message": "재발급 횟수 초과"}],
                    "validation_conditions": ["monthlyCount >= limit"],
                },
                "exception": ["BizException"],
                "업무규칙": ["카드 재발급은 월 제한 횟수를 확인한다."],
                "요약": "카드 발급 처리 로직",
                "근거": {
                    "문서유형": "business_logic",
                    "제목": "CardService.issueCard",
                    "소스경로": "source/CardService.java",
                    "라인": "10-40",
                    "클래스": "CardService",
                    "메서드": "issueCard",
                    "SQL_ID": "CardMapper.insertCard",
                    "테이블": ["TB_CARD"],
                    "컬럼": ["CARD_NO"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    docs = UploadedDocumentParser().parse(SourceFile(path=path, language="json", text=path.read_text()))

    doc = docs[0]
    assert doc.business_name == "카드 발급"
    assert doc.screen_id == "CARD_010"
    assert doc.screen_name == "카드발급 확인"
    assert doc.api_path == "/api/cards/issue"
    assert doc.api_description == "카드 발급 신청 처리"
    assert doc.class_name == "CardService"
    assert doc.method_name == "issueCard"
    assert doc.sql_id == "CardMapper.insertCard"
    assert doc.tables == ["TB_CARD"]
    assert doc.columns == ["CARD_NO"]
    assert doc.dto_names == ["CardIssueRequest"]
    assert doc.dto_fields == ["customerNo", "cardProductCd"]
    assert doc.input_fields == ["customerNo"]
    assert doc.error_codes == ["CARD_LIMIT_EXCEEDED"]
    assert doc.error_messages == ["월 재발급 횟수를 초과했습니다."]
    assert doc.validation_conditions == ["monthlyCount >= limit"]
    assert doc.possible_errors == [{"message": "재발급 횟수 초과"}]
    assert doc.exception_types == ["BizException"]
