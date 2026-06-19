from backend.app.agents.sql_intent_classifier import SQLIntentClassifier


class FakeClient:
    def __init__(self, answer):
        self.answer = answer

    def chat(self, messages, temperature=0.1, enable_thinking=False):
        assert temperature == 0
        assert enable_thinking is False
        return self.answer


def test_sql_intent_classifier_accepts_qwen_yes():
    decision = SQLIntentClassifier(client=FakeClient("yes")).classify(
        "고객별 잔액 조회 SQL을 만들어줘"
    )

    assert decision.is_sql_generation is True
    assert decision.raw_answer == "yes"
    assert decision.source == "qwen"


def test_sql_intent_classifier_accepts_qwen_no():
    decision = SQLIntentClassifier(client=FakeClient("no")).classify(
        "자동이체 등록 화면 오류의 API, 서비스, SQL 근거를 요약해줘"
    )

    assert decision.is_sql_generation is False
    assert decision.raw_answer == "no"
    assert decision.source == "qwen"


def test_sql_intent_classifier_falls_back_to_generation_heuristic():
    decision = SQLIntentClassifier(client=FakeClient(None)).classify(
        "최근 3개월 고객별 잔액을 조회하는 쿼리 작성해줘"
    )

    assert decision.is_sql_generation is True
    assert decision.raw_answer == "yes"
    assert decision.source == "heuristic"


def test_sql_intent_classifier_handles_korean_particle_after_sql():
    decision = SQLIntentClassifier(client=FakeClient(None)).classify(
        "고객별 잔액을 조회하는 SQL을 만들어줘"
    )

    assert decision.is_sql_generation is True
    assert decision.raw_answer == "yes"
    assert decision.source == "heuristic"


def test_sql_intent_classifier_falls_back_to_rag_heuristic():
    decision = SQLIntentClassifier(client=FakeClient(None)).classify(
        "자동이체 등록 화면 오류의 API, 서비스, SQL 근거를 요약해줘"
    )

    assert decision.is_sql_generation is False
    assert decision.raw_answer == "no"
    assert decision.source == "heuristic"
