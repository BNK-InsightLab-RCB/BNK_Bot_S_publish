# Foundry Agent RAG Workflow

## 확인 결과

- 현재 코드 설정과 Azure AI Search 서비스 모두 `ops-knowledge` index를 사용한다.
- Foundry Agent 화면에서 Azure AI Search tool이 `ops-knowledge`에 연결되어 있으면, 우리가 업로드한 지식문서 index를 Agent가 직접 조회하는 구조가 된다.
- 관리자 화면의 Foundry 모델 모니터링 값은 Foundry portal 화면만 긁는 방식보다 Azure Monitor / Application Insights / Log Analytics 경로로 가져오는 방식이 맞다.

## 기존 방식

기존 `multi_agent` 경로는 서버가 먼저 검색을 담당했다.

```text
사용자 질문
  -> FastAPI /api/chat
  -> SupervisorAgent
  -> 서버가 Azure AI Search 직접 검색
  -> 서버가 검색 결과를 context_hint로 압축
  -> Foundry Responses API 호출
  -> 로컬 guardrail 적용
  -> React UI 반환
```

Foundry Agent 이름이나 Search connection이 없으면 이 경로가 안전한 fallback으로 유지된다.

## 변경 방식

Agent나 Search tool 설정이 있으면 Foundry Agent를 먼저 호출한다.

```text
사용자 질문
  -> FastAPI /api/chat
  -> SupervisorAgent
  -> Foundry Agent 호출
  -> Agent 지침서 적용
  -> Agent가 Azure AI Search tool로 ops-knowledge 검색
  -> Agent가 검색 근거 기반 답변과 citation 반환
  -> 로컬 role guardrail 적용
  -> React UI 반환
```

Foundry 호출이 실패하면 기존 서버 직접 검색 경로로 내려간다.

## 권장 환경값

```bash
RAG_PROVIDER=multi_agent
AZURE_SEARCH_INDEX=ops-knowledge
FOUNDRY_PROJECT_ENDPOINT=https://<foundry-resource>.services.ai.azure.com/api/projects/<project-name>
FOUNDRY_MODEL_DEPLOYMENT=gpt-5.4
FOUNDRY_AGENT_NAME=test-agent
FOUNDRY_AGENT_VERSION=3
FOUNDRY_FORCE_SEARCH_TOOL=true
AZURE_MONITOR_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>
AZURE_MONITOR_METRIC_NAMES=TokenTransaction,ProcessedPromptTokens,GeneratedTokens,Requests,Latency
```

Agent version은 Foundry portal에서 Publish된 버전을 사용한다. 버전 값을 비워두면 Agent 이름만으로 호출한다.

## RAG 지침서 초안

Foundry Agent Instructions에는 아래처럼 넣는 것을 권장한다.

```text
너는 BNK 영업점 운영지원 RAG Agent다.

반드시 연결된 Azure AI Search tool의 ops-knowledge 지식문서를 먼저 검색한 뒤 답변한다.
검색 근거가 없거나 약하면 원인을 단정하지 말고 추가 확인 항목을 안내한다.

사용자 역할이 영업점 직원이면 다음을 숨긴다:
- 소스코드
- 내부 API 경로
- DB 테이블명, 컬럼명, SQL ID
- 클래스명, 메서드명, 파일명
- 비밀값, 토큰, 연결 문자열
- 권한 우회, 보안 우회, 직접 DB 수정 방법

IT 개발자나 관리자에게는 장애 분석에 필요한 파일, 메서드, SQL, 테이블 단서를 요약하되 비밀값은 마스킹한다.

답변 형식:
[가능한 원인]
[먼저 확인할 사항]
[계속 오류가 발생하는 경우]
[IT부서 전달용 정보]
[근거]
[조치 후 재시도]

근거는 반드시 검색된 문서 citation을 포함한다.
업무와 무관한 질문, 보안 우회, 고객 민감정보 노출 요청은 거절하고 정상 접수 절차만 안내한다.
```

## Foundry 모델 모니터링 연동

Foundry portal의 Monitor/Metrics 화면은 대시보드 UI이고, 앱 대시보드로 가져오려면 아래 중 하나를 사용한다.

1. Azure Monitor Metrics REST API
   - 모델 deployment / Azure OpenAI 또는 Foundry 관련 resource id 기준으로 token, request, latency, error metric을 조회한다.
   - 이 PoC는 `AZURE_MONITOR_RESOURCE_ID`가 설정되면 `/api/admin/dashboard`의 `azure.monitor`에 token, request, latency, error, throttle 요약을 내려준다.
   - 관리자 대시보드의 `MS Azure / Foundry` 카드가 해당 값을 우선 표시하고, 연결 전에는 demo 값으로 유지된다.

2. Diagnostic settings + Log Analytics
   - Azure OpenAI / Foundry 관련 resource logs를 Log Analytics workspace로 보낸다.
   - KQL로 prompt token, completion token, latency, result code, throttling, error를 집계한다.
   - Observability Agent 화면에는 KQL 결과를 요약해서 보여준다.

3. Application Insights tracing
   - FastAPI에서 request id, user role, answer backend, retrieval backend, duration, source count를 span/log로 남긴다.
   - Foundry trace와 서버 trace를 같은 correlation id로 묶는다.

## 관리자 대시보드에 표시할 KPI

- 모델 요청 수
- 총 token 사용량
- 평균 / P95 latency
- 실패율과 throttling 수
- Azure AI Search query latency
- citation 포함률
- fallback 비율
- Agent 답변 중 지침서 위반 차단률
