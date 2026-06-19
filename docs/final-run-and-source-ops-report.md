# 최종 실행 및 부서 소스 운영 보고서

## 1. 현재 완료 상태

영업점 직원이 챗봇 화면에서 질문하면 다음 경로로 답변을 생성한다.

```text
React chatbot UI
  -> FastAPI /api/chat
  -> SupervisorAgent
  -> Azure AI Search ops-knowledge 검색
  -> Microsoft Foundry Responses API / Agent 답변 생성
  -> 영업점 역할 guardrail 적용
  -> UI 출력
```

현재 `.env` 기준 답변 LLM은 Qwen이 아니라 Microsoft Foundry 모델이다. Qwen은 로컬 fallback 모드로 남아 있으며,
`RAG_PROVIDER=local`, `ENABLE_LLM_CHAT=true`, Qwen local server 실행 조건에서 사용한다.

## 2. 최종 챗봇 UI 실행 명령

레포 루트에서 아래 한 줄을 실행한다.

```bash
./scripts/run_chatbot.sh
```

동작:

- FastAPI backend: `http://127.0.0.1:9000`
- React chatbot UI: `http://127.0.0.1:5173`
- macOS에서는 브라우저가 자동으로 열린다.

주의:

- `.env`가 있어야 한다.
- 현재 Foundry/MS Search 데모 모드는 Azure AI Search, Azure OpenAI embedding, Microsoft Foundry 설정이 필요하다.
- 프론트 의존성이 없으면 스크립트가 `npm install`을 먼저 수행한다.

## 3. 부서 소스 파일 위치와 형식

새로운 부서나 업무팀 소스는 다음 표준 위치에 올린다.

```text
source_repositories/<department_code>/
  frontend/
  backend/
  mapper/
  docs/
```

예시:

```text
source_repositories/card_ops/
  frontend/CardReissue.vue
  backend/CardReissueController.java
  backend/CardReissueService.java
  mapper/CardReissueMapper.xml
  docs/TB_CARD_table.md
  docs/error_codes.md
```

지원 확장자:

```text
.vue, .ts, .tsx, .js, .jsx, .jsp, .html, .java, .xml, .sql, .md, .csv, .xlsx
```

금지:

- `.env`
- API key, Search admin key, Foundry key
- `.pem`, `.key`, `.p12`, `.pfx`
- `credentials.json`, `secrets.json`
- 고객 실명, 주민번호, 계좌번호 등 실제 개인정보가 포함된 원본 데이터

## 4. 파일 추가/수정/삭제 후 자동 반영

파일을 추가, 수정, 삭제한 뒤 아래 배치를 실행한다.

```bash
./scripts/sync_sources.sh \
  --source-dir source_repositories/<department_code> \
  --department <department_code>
```

배치 처리 순서:

```text
source_repositories/<department_code>
  -> Azure Blob Storage source-live/<department_code> 업로드
  -> Storage stale blob prune
  -> source parser 실행
  -> KnowledgeDocument 생성
  -> embedding 생성
  -> local JSON/SQLite index 갱신
  -> Azure AI Search ops-knowledge reset/rebuild
  -> 챗봇 검색 반영
```

삭제 반영 방식:

- 로컬 폴더에서 파일을 삭제한다.
- `sync_sources.sh`를 실행한다.
- Storage의 `source-live/<department_code>` prefix에서 더 이상 없는 blob을 삭제한다.
- Azure AI Search index를 reset/rebuild하므로 삭제된 파일은 검색 대상에서 제외된다.

동일 기능은 백엔드 API로도 열려 있다.

```bash
curl -X POST http://127.0.0.1:9000/api/source-sync/run \
  -H "Content-Type: application/json" \
  -H "x-source-sync-token: $SOURCE_SYNC_ADMIN_TOKEN" \
  -d '{
    "source_dir": "source_repositories/card_ops",
    "department": "card_ops",
    "reset_index": true
  }'
```

Foundry OpenAPI tool로 붙일 스펙:

```text
docs/foundry-source-sync.openapi.json
```

이 API는 `source_repositories/` 또는 `backend/examples/` 아래 경로만 허용한다. 외부 임의 경로를
에이전트가 건드리지 못하게 막기 위한 제한이다.

## 5. 필요한 Azure 조건

Storage 자동 업로드를 위해 `.env`에 아래 셋 중 하나가 필요하다. 현재 데모 환경은
Storage account `pjyragstore58`, container `uhihi`를 사용하도록 복구했다.

```bash
AZURE_STORAGE_ACCOUNT_KEY=
# 또는
AZURE_STORAGE_CONNECTION_STRING=
# 또는
AZURE_STORAGE_SAS_TOKEN=
```

Azure AI Search 재색인을 위해 아래 설정이 필요하다.

```bash
EMBEDDING_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_INDEX=ops-knowledge
AZURE_SEARCH_API_KEY=
```

Foundry 답변 생성을 위해 아래 설정이 필요하다.

```bash
RAG_PROVIDER=multi_agent
FOUNDRY_PROJECT_ENDPOINT=
FOUNDRY_MODEL_DEPLOYMENT=
FOUNDRY_API_KEY=
```

Foundry 에이전트가 소스 동기화 API를 호출하게 하려면 아래 값도 설정한다.

```bash
SOURCE_SYNC_ADMIN_TOKEN=
```

배포된 백엔드 URL을 `docs/foundry-source-sync.openapi.json`의 `servers.url`에 넣고, Foundry project의
OpenAPI tool 인증 header `x-source-sync-token`에 이 값을 연결한다.

## 6. 검증 방법

챗봇 API 직접 검증:

```bash
curl -X POST http://127.0.0.1:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "자동이체 등록 화면에서 출금계좌가 만료되었거나 사용 불가 상태라고 나와요. 납부자번호는 입력했습니다.",
    "user_role": "branch",
    "include_sources": true
  }'
```

기대 metadata:

```text
rag_provider: multi_agent
answer_backend: foundry
agent_trace에 azure_search_worker, foundry_worker 포함
```

소스 동기화 로컬 검증:

```bash
./scripts/sync_sources.sh \
  --source-dir backend/examples/bank_sample \
  --department bank_sample \
  --skip-storage \
  --skip-azure-search
```

이 명령은 Azure credential 없이 parser/indexer만 확인하는 안전한 로컬 검증이다.

실제 확인 결과:

```text
ruff check backend scripts/sync_sources.py: passed
pytest backend/tests -q: 24 passed
frontend build: passed
./scripts/run_chatbot.sh: backend 9000 + frontend 5173 startup confirmed
sync_sources --skip-storage: Azure AI Search ops-knowledge reset/rebuild, 92 docs uploaded
/api/chat test: 200 OK, answer_backend=foundry, Azure Search hits=12, selected docs=2-6
branch answer safety: internal source paths masked
```

추가 복구/보강 결과:

```text
/api/source-sync/run: added for admin automation and Foundry OpenAPI tool calls
source sync path guard: only source_repositories/ and backend/examples/ are allowed
Foundry OpenAPI spec: docs/foundry-source-sync.openapi.json
```

## 8. Azure 에이전트 자동화 판단

문서 기준으로는 가능하지만, 역할을 나누는 방식이 맞다.

- 답변 생성/검색: Foundry Agent 또는 Foundry IQ Knowledge Base가 Azure AI Search를 도구로 사용한다.
- 소스 추가/삭제 반영: Azure Blob Storage, Azure Functions/Event Grid, Azure AI Search indexer 또는 현재 백엔드의 `/api/source-sync/run` 같은 관리 API가 맡는다.
- Foundry Agent는 OpenAPI tool 또는 Azure Functions tool로 관리 API를 호출할 수 있다. 즉, 에이전트가 직접 파일 시스템을 긁는 것이 아니라, 승인된 API를 호출해 배치를 실행하는 구조가 안전하다.

권장 최종 구조:

```text
department source folder
  -> backend /api/source-sync/run 또는 Azure Function
  -> Azure Blob Storage source-live/<department>
  -> parser + embedding
  -> Azure AI Search ops-knowledge
  -> Foundry Agent/Foundry IQ retrieval
  -> chatbot answer
```

## 7. 오늘 기준 남은 외부 조건

현재 코드 흐름은 구현되어 있지만, 실제 Azure Storage 업로드는 Storage credential이 `.env`에 들어가야 열린다.
Foundry 테스트 리소스가 초기화되면 다음 순서로 복구한다.

1. Foundry project, model deployment, Search connection 값을 다시 확인한다.
2. `.env`의 Foundry/Search 관련 값을 갱신한다.
3. `./scripts/sync_sources.sh --source-dir backend/examples/bank_sample --department bank_sample`로 Search index를 재생성한다.
4. `./scripts/run_chatbot.sh`로 UI를 열고 검증 질문을 실행한다.
