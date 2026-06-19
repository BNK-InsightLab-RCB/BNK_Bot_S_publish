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
