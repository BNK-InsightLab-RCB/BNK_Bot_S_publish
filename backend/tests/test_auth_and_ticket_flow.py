from backend.app.auth_store import AuthStore
from backend.app.runtime_store import RuntimeStore


def test_auth_store_creates_user_with_role_code_and_hash(tmp_path):
    store = AuthStore(path=tmp_path / "users.json")

    user = store.create_user(
        real_name="홍길동",
        employee_id="B001",
        password="pass1234",
        role_code="01",
    )

    assert user["role"] == "branch"
    assert user["role_code"] == "01"
    saved = (tmp_path / "users.json").read_text(encoding="utf-8")
    assert "pass1234" not in saved
    assert store.authenticate("B001", "pass1234")["real_name"] == "홍길동"


def test_runtime_store_adds_ticket_reply(tmp_path):
    store = RuntimeStore(
        log_path=tmp_path / "runtime_events.json",
        ticket_path=tmp_path / "support_tickets.json",
    )
    ticket = store.create_ticket(
        {
            "question": "고객조회 화면에서 저장이 안돼요.",
            "summary": "권한 확인 필요",
            "sender_name": "홍길동",
            "sender_employee_id": "B001",
            "sender_role_code": "01",
            "sources": [{"doc_id": "doc1", "title": "CustomerService.save", "reason": "권한 확인"}],
        }
    )

    updated = store.add_ticket_reply(
        ticket["id"],
        {
            "body": "권한 부여 상태를 확인했습니다.",
            "author_name": "김개발",
            "author_employee_id": "I001",
            "author_role": "it",
            "author_role_code": "02",
        },
    )

    assert updated["status"] == "replied"
    assert updated["sources"][0]["title"] == "CustomerService.save"
    assert updated["replies"][0]["body"] == "권한 부여 상태를 확인했습니다."
    assert store.list_tickets()[0]["sender_employee_id"] == "B001"


def test_runtime_store_admin_dashboard_counts_routes(tmp_path):
    store = RuntimeStore(
        log_path=tmp_path / "runtime_events.json",
        ticket_path=tmp_path / "support_tickets.json",
    )
    store.append_chat(
        "자동이체 등록 오류",
        "it",
        {
            "answer": "가능 원인 확인",
            "confidence": 0.7,
            "metadata": {"answer_backend": "foundry", "rag_provider": "multi_agent"},
            "sources": [{"title": "자동이체 업무 규칙", "retrieval_backend": "azure_ai_search"}],
        },
        duration_ms=1234,
    )
    store.append_storage_upload(
        file_names=["rules.json"],
        blob_names=["source-drop/rules.json"],
        local_paths=["backend/examples/bank_sample/docs/admin_uploads/rules.json"],
        total_size=100,
        container="uhihi",
    )

    dashboard = store.admin_dashboard()

    assert dashboard["totals"]["chat_count"] == 1
    assert dashboard["totals"]["cloud_answer_count"] == 1
    assert dashboard["totals"]["storage_uploaded_bytes"] == 100
    assert dashboard["recent_model_events"][0]["answer_backend"] == "foundry"
