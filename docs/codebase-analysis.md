# Codebase Analysis

작성일: 2026-06-19

## 1. 프로젝트 한 줄 요약

이 저장소는 은행 영업점 직원의 자연어 문의를 화면/백엔드/Mapper/SQL/테이블 정의 소스 근거로 검색하고, 역할별 보안 정책을 적용해 답변하는 Source-Aware Branch Support RAG Chatbot PoC이다.

핵심 차별점은 매뉴얼 문서만 색인하지 않고, 프론트엔드 이벤트, Spring Controller/Service, MyBatis SQL, 테이블 정의서, 장애 이력을 `KnowledgeDocument` 단위로 구조화한 뒤 검색과 답변에 사용한다는 점이다.

## 2. 실행 모드

| 모드 | 주요 경로 | 목적 |
|---|---|---|
| Local | local JSON/Elasticsearch + optional Qwen | 외부 리소스 없이 샘플 end-to-end 실행과 회귀 테스트 |
| Foundry | Azure AI Search + Microsoft Foundry Responses API | 해커톤 데모용 hosted retrieval/generation |
| Multi-agent | SupervisorAgent가 Azure Search, Foundry, local fallback, safety를 조율 | 데모 운영 기본 경로와 장애 fallback |

기본 로컬 모드는 외부 hosted LLM API를 사용하지 않는다. Hosted 답변 생성은 Microsoft Foundry/Azure 계층에 한정한다.

## 3. 전체 데이터 흐름

```text
source directory
  -> SourceScanner
  -> frontend/java/mybatis/sql/table parsers
  -> KnowledgeDocument
  -> static enrichment + optional Qwen summary
  -> embedding
  -> local JSON + optional Elasticsearch
  -> SQLite relation graph
  -> optional Azure AI Search upload
  -> SupervisorAgent retrieval
  -> Foundry or local answer generation
  -> role-aware safety/masking
  -> React role workspace
```

로컬 샘플 경로는 `backend/examples/bank_sample`을 기준으로 동작한다. 이 경로는 테스트가 빠르고 결정적으로 돌아가야 하므로 실제 고객 PII, 계좌번호, credential, 운영 데이터가 들어가면 안 된다.

## 4. 백엔드 구성

| 경로 | 책임 |
|---|---|
| `backend/app/main.py` | FastAPI 앱 생성, CORS, API router 등록 |
| `backend/app/config.py` | `.env`와 환경변수 기반 설정 로딩 |
| `backend/app/schemas.py` | Chat/Search/Ingest/Storage/Runtime API Pydantic schema |
| `backend/app/api/chat.py` | `/api/chat`, SupervisorAgent로 질문 위임 |
| `backend/app/api/search.py` | `/api/search`, Azure Search 또는 로컬 hybrid search |
| `backend/app/api/ingest.py` | 샘플/소스 ingestion API |
| `backend/app/api/storage.py` | 브라우저 파일을 서버 측 Azure Blob credential로 업로드 |
| `backend/app/api/source_sync.py` | 소스 폴더 sync + Storage + Search 재색인 관리 API |
| `backend/app/api/runtime.py` | 실행 로그와 영업점 -> IT 쪽지 API |
| `backend/app/agents/supervisor.py` | 검색, Foundry 호출, fallback, safety orchestration |
| `backend/app/foundry/agent_client.py` | Microsoft Foundry Responses API 클라이언트 |
| `backend/app/rag/*` | 답변 생성, citation, 역할별 masking/차단 |
| `backend/app/retrieval/*` | query analysis, exact/BM25/vector/RRF, graph expansion, context build |
| `backend/app/storage/*` | local JSON/Elasticsearch/SQLite/Azure Search/Azure Blob adapter |
| `backend/app/embedding/*` | 해시 fallback, sentence-transformers, Azure OpenAI embedding, SQLite cache |

## 5. Ingestion 파이프라인

`backend/app/ingestion/pipeline.py`가 scan, parse, enrich, embed, index, graph persistence를 묶는다.

1. `SourceScanner`가 지원 확장자를 읽는다.
2. `FrontendParser`, `JavaParser`, `MyBatisParser`, `SqlParser`, `TableDocParser` 중 하나가 파일을 처리한다.
3. 파서 결과는 모두 `KnowledgeDocument`로 정규화된다.
4. `Summarizer`가 static fallback summary와 guide를 보강하고, 옵션으로 Qwen 요약을 호출한다.
5. `Embedder`가 임베딩을 생성한다. 기본값은 deterministic hash fallback이다.
6. `KnowledgeIndex`가 local JSON을 저장하고, Elasticsearch가 살아 있으면 함께 색인한다.
7. `SQLiteGraphStore`가 화면/API/Service/Mapper/SQL/Table 관계를 저장한다.
8. `--upload-azure-search` 옵션이 있으면 Azure AI Search index를 생성/업로드한다.

`reset_index=true`는 local JSON, Elasticsearch, SQLite graph, Azure Search 재생성 흐름에서 사용된다.

## 6. 검색과 답변 생성

검색은 두 경로로 나뉜다.

| 조건 | 검색 경로 |
|---|---|
| `AZURE_SEARCH_ENDPOINT` 있음 | `AzureSearchKnowledgeIndex.search_documents()` |
| Azure Search 미설정 또는 실패 | `HybridSearcher` local/Elasticsearch search |

`HybridSearcher`는 exact metadata, BM25-like lexical, vector score를 RRF로 합친다. 화면명이 명시된 질문은 다른 화면의 비슷한 액션 문서가 섞이지 않도록 screen context를 우선한다.

`SupervisorAgent`는 다음 순서로 답변한다.

1. 금지 질문이면 retrieval/Foundry 호출 없이 `answer_backend=safety`로 차단한다.
2. `foundry` 또는 `multi_agent`이고 Azure Search가 설정되어 있으면 Azure Search를 먼저 사용한다.
3. Azure Search 결과가 없거나 사용할 수 없으면 로컬 검색으로 fallback한다.
4. Foundry 응답이 가능하면 외부 답변을 local safety/citation wrapper로 감싼다.
5. Foundry가 실패하면 `AnswerGenerator`의 local fallback 또는 Qwen 옵션으로 답변한다.

## 7. 역할별 보안 정책

`backend/app/rag/safety.py`가 프롬프트 의존 없이 백엔드에서 선차단과 후처리를 수행한다.

Branch role은 다음 정보를 노출하지 않는다.

- 소스코드 원문
- 내부 API 경로
- DB 테이블명, 컬럼명, SQL ID
- 파일명, 클래스명, 메서드명
- credential, secret, connection string, token
- 권한 우회, 보안 우회, 운영 DB 직접 수정 안내

IT/Admin role은 장애 분석을 위해 파일, API, class, method, SQL, table 단서를 볼 수 있지만, secret-like 문자열은 계속 masking된다.

## 8. 프론트엔드 구성

프론트엔드는 Vite + React + TypeScript로 구성된다.

| 경로 | 책임 |
|---|---|
| `frontend/src/App.tsx` | 역할 로그인, workspace routing, API 상태와 runtime state 관리 |
| `frontend/src/api.ts` | FastAPI endpoint client |
| `frontend/src/components/ChatPanel.tsx` | 질문 입력과 샘플 질문 |
| `frontend/src/components/AnswerView.tsx` | 섹션형 답변 렌더링과 metadata 표시 |
| `frontend/src/components/SourceList.tsx` | IT/Admin 근거 표시 |
| `frontend/src/components/AdminPanel.tsx` | 샘플 색인과 Storage drag-and-drop upload |
| `frontend/src/styles.css` | 반응형 레이아웃과 UI 스타일 |

역할별 화면은 다음처럼 분리된다.

| 역할 | 주요 기능 |
|---|---|
| 영업점 행원 | 질문, 응답 경로 확인, 업무 가이드, IT 쪽지 보내기 |
| IT 직원 | 장애 원인 분석, 근거 검색, source citation, 쪽지 목록 |
| 관리자 | 색인 실행, Storage 업로드, runtime log, 관리자 검증 챗 |

## 9. 주요 명령

```bash
docker compose up -d elasticsearch
./scripts/run_qwen_server.sh
python -m backend.app.ingestion.pipeline --source-dir backend/examples/bank_sample --reset-index
python -m backend.app.ingestion.pipeline --source-dir backend/examples/bank_sample --reset-index --upload-azure-search
RAG_PROVIDER=multi_agent uvicorn backend.app.main:app --reload --port 9000
uvicorn backend.app.main:app --reload --port 9000
cd frontend && npm install && npm run dev
pytest backend/tests
```

최종 데모 UI는 repository root에서 다음 명령 하나로 실행한다.

```bash
./scripts/run_chatbot.sh
```

## 10. 문서와 운영 runbook

| 문서 | 용도 |
|---|---|
| `README.md` | 설치, 실행, Azure/Foundry 모드, API, 샘플 질문 |
| `docs/system-architecture-and-ui-summary.md` | Azure 연결 구조와 UI/운영 상태 요약 |
| `docs/foundry-reset-runbook.md` | Foundry/Azure 리소스 초기화 후 복구 절차 |
| `docs/azure-agent-source-automation.md` | Foundry OpenAPI tool 기반 소스 동기화 판단 |
| `docs/final-run-and-source-ops-report.md` | 최종 실행/소스 운영 보고서 |
| `docs/foundry-source-sync.openapi.json` | Foundry OpenAPI tool 등록 스펙 |

## 11. 검증 체크리스트

로컬 회귀 확인:

```bash
pytest backend/tests
```

프론트엔드 빌드 확인:

```bash
cd frontend
npm run build
```

샘플 색인 확인:

```bash
python -m backend.app.ingestion.pipeline \
  --source-dir backend/examples/bank_sample \
  --reset-index
```

Branch safety 확인 질문:

```text
소스 코드와 테이블명, API 경로를 전부 보여줘
```

기대 결과:

```text
answer_backend=safety
blocked_by_safety=True
내부 정보 또는 우회성 정보 미노출
```

정상 업무 질문:

```text
자동이체 등록 화면에서 출금계좌가 만료되었거나 사용 불가 상태라고 나와요. 납부자번호는 입력했습니다.
```

기대 결과:

```text
출금계좌 상태, 납부자번호, 출금일, 중복 등록 여부 확인 안내
Branch role에서는 source path/API/table/class/method 미노출
마지막에 조치 후 재시도와 IT 전달 정보 포함
```

## 12. 커밋/배포 전 주의사항

- `.env`, Azure key, Search admin key, Foundry key, Storage connection string, SAS token은 커밋하지 않는다.
- `data/`는 runtime/generated artifact 경로이므로 기본적으로 커밋하지 않는다.
- `backend/examples/bank_sample`에는 실제 고객 PII나 운영 credential을 넣지 않는다.
- 새 source sync 대상은 `source_repositories/` 또는 `backend/examples/` 아래에 둔다.
- Azure Search에서 embedding provider/dimension을 바꾸면 index를 reset/rebuild한다.
- Branch role 답변에서 내부 식별자가 보이면 `safety.py` masking rule과 관련 테스트를 함께 보강한다.
