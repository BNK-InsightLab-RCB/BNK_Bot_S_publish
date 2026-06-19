# Microsoft Foundry Reset Runbook

이 문서는 해커톤 테스트 환경에서 Microsoft Foundry 리소스가 초기화된 뒤, BNK_Bot_S 데모를 다시 연결하기 위한 복구 절차다.

## 목표 구조

```text
backend/examples/bank_sample
  -> local source-aware ingestion
  -> data/ops_knowledge.json
  -> Azure OpenAI text-embedding-3-large
  -> Azure AI Search index
  -> Azure AI Search vector + keyword hybrid retrieval
  -> Azure AI Search semantic reranker
  -> Microsoft Foundry Agent or Responses API with Azure AI Search tool when available
  -> FastAPI /api/chat
  -> React UI
```

참고 워크샵:

- `ChangJu-Ahn/azure_aisearch_workshop`: keyword/vector/hybrid/semantic reranking 실습 흐름
- `09-agentic_retrieval_foundryiq`: Foundry IQ/agentic retrieval은 별도 Ignite LAB511 레포로 연결됨
- 우리 프로젝트의 차별점: 업무 케이스 문서가 아니라 FE/BE/MyBatis/테이블 정의 소스코드를 파싱해 Azure AI Search 지식 문서로 올림

## 다시 만들어야 하는 Azure 리소스

1. Resource Group
2. Azure AI Search service
3. Microsoft Foundry project
4. Azure OpenAI embedding deployment, 예: `text-embedding-3-large`
5. Chat model deployment, 예: `gpt-5.4` 또는 제공된 해커톤 deployment
6. Foundry project connection to Azure AI Search
7. Optional Foundry Agent or Foundry IQ Knowledge Base using the Azure AI Search connection

## 필요한 값

`.env`에 아래 값을 채운다.

```bash
RAG_PROVIDER=multi_agent
EMBEDDING_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://<aoai-resource>.openai.azure.com
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
AZURE_SEARCH_INDEX=ops-knowledge
AZURE_SEARCH_API_KEY=
FOUNDRY_PROJECT_ENDPOINT=https://<foundry-resource>.ai.azure.com/api/projects/<project-name>
FOUNDRY_MODEL_DEPLOYMENT=gpt-5.4
FOUNDRY_AGENT_NAME=
FOUNDRY_AI_SEARCH_CONNECTION_ID=/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>/projects/<project-name>/connections/<search-connection-name>
FOUNDRY_AI_SEARCH_QUERY_TYPE=semantic
FOUNDRY_TOP_K=5
```

API key를 비워두면 `az login` 기반 토큰 인증을 시도한다.

기본값 `EMBEDDING_PROVIDER=hash`는 모델 다운로드 없이 쓰는 384차원 로컬 fallback이다.
`EMBEDDING_PROVIDER=azure_openai`를 켜면 Azure Search index를 반드시 다시 만든다.
`text-embedding-3-large` 기본값은 3072차원이므로 기존 index에 그대로 업로드하면
vector query 차원 오류가 발생한다.

## 복구 순서

1. Azure CLI 로그인

```bash
az login
az account show
```

2. 로컬 샘플 색인 재생성

```bash
python -m backend.app.ingestion.pipeline \
  --source-dir backend/examples/bank_sample \
  --reset-index
```

3. Azure AI Search 업로드

```bash
python scripts/upload_azure_search.py --reset-index
```

또는 한 번에 실행한다.

```bash
python -m backend.app.ingestion.pipeline \
  --source-dir backend/examples/bank_sample \
  --reset-index \
  --upload-azure-search
```

4. Foundry portal에서 Azure AI Search connection이 project에 연결되어 있는지 확인

5. Foundry IQ Knowledge Base를 쓰는 경우

- Knowledge source: Azure AI Search index `ops-knowledge`
- Retrieval mode: portal의 기본 recommended 설정. 앱 내부 직접 검색은 vector+semantic hybrid를 사용하지만, Foundry Azure AI Search tool은 integrated vectorizer가 없으면 `vector_semantic_hybrid`를 거부하므로 이 PoC의 Foundry tool 기본값은 `semantic`으로 둔다.
- Guidance: “Korean branch-operation source code evidence only”, “do not expose source internals to branch role”
- Reasoning effort: 데모는 `medium`, 비용/지연이 문제면 `low`
- Activity analysis 화면에서 query decomposition과 선택된 source/citation을 확인

6. Foundry Agent를 쓰는 경우 agent instructions에 아래 정책을 넣는다.

```text
You are a source-aware branch support agent for Korean bank operations.
Always ground answers with the connected Azure AI Search knowledge source.
For branch users, never expose source code, internal API paths, SQL IDs, table names, class names, method names, secrets, or bypass instructions.
If evidence is insufficient, say what conditions must be checked and what information should be escalated to IT.
Use sections: [가능한 원인], [먼저 확인할 사항], [계속 오류가 발생하는 경우], [IT부서 전달용 정보], [근거], [조치 후 재시도].
```

7. Backend 실행

```bash
RAG_PROVIDER=multi_agent uvicorn backend.app.main:app --reload --port 9000
```

Foundry API 키가 아직 없거나 초기화된 경우에도 `AZURE_SEARCH_ENDPOINT`와
`AZURE_SEARCH_API_KEY`가 있으면 `multi_agent` 모드는 Azure AI Search에서
관련 소스 근거를 검색하고 로컬 guardrail fallback 답변을 반환한다.

8. Frontend 실행

```bash
cd frontend
npm install
npm run dev
```

## Azure Storage container 사용

해커톤 데모에서는 Storage account `pjyragstore58`의 container `uhihi`를 원천 산출물 보관 용도로 사용한다.
검색/답변 경로는 Azure AI Search index `ops-knowledge`를 직접 사용하고, Storage에는 재현 가능한
소스/지식 번들을 보관한다.

업로드 번들 생성:

```bash
mkdir -p data/storage-upload
zip -qr data/storage-upload/source-aware-branch-rag-poc.zip \
  README.md \
  docs/foundry-reset-runbook.md \
  data/ops_knowledge.json \
  backend/examples/bank_sample
```

업로드 대상:

```text
Storage account: pjyragstore58
Container: uhihi
Blob name: source-aware-branch-rag-poc.zip
```

주의:

- `.env`, API key, Search admin key, Foundry key는 절대 번들에 포함하지 않는다.
- Foundry IQ Knowledge Base를 Storage blob에 직접 붙이는 경우에는 이 zip보다 개별 JSONL/문서 파일을 올리는 구성이 더 적합하다.
- 현재 앱의 실제 RAG 검색은 Storage가 아니라 Azure AI Search `ops-knowledge` index를 사용한다.

### 앱에서 드래그 앤 드랍으로 Storage 업로드

프론트엔드 관리자 패널에는 Storage 업로드 drop zone이 있다. 사용자가 파일을 놓으면 브라우저는 파일만
`POST /api/storage/upload`로 보내고, FastAPI 백엔드가 서버 측 권한으로 Azure Blob Storage에 업로드한다.
Storage key나 SAS token은 브라우저에 내려가지 않는다.

`.env`에 다음 값이 있어야 한다.

```bash
AZURE_STORAGE_ACCOUNT=pjyragstore58
AZURE_STORAGE_CONTAINER=uhihi
AZURE_STORAGE_UPLOAD_PREFIX=source-drop
AZURE_STORAGE_ACCOUNT_KEY=<storage-account-key>
# 또는 AZURE_STORAGE_CONNECTION_STRING=<connection-string>
# 또는 AZURE_STORAGE_SAS_TOKEN=<container-sas-token>
```

현재 Storage account/container 값만 있고 key, connection string, SAS가 비어 있으면 업로드 API는 503으로
실패한다. 이 경우 Storage credential을 넣고 backend를 재시작한 뒤 다시 파일을 드롭한다.

중요: Storage 업로드는 원천 파일 보관이다. 새로 올린 파일을 질문 답변에 반영하려면 parser/ingestion을
돌려 `data/ops_knowledge.json`과 Azure AI Search `ops-knowledge` index를 다시 갱신해야 한다.

### 부서 소스 자동 동기화

새 부서나 업무팀 소스는 다음 위치에 둔다.

```text
source_repositories/<department_code>/
  frontend/
  backend/
  mapper/
  docs/
```

파일 추가, 수정, 삭제 후 아래 배치를 실행한다.

```bash
./scripts/sync_sources.sh \
  --source-dir source_repositories/<department_code> \
  --department <department_code>
```

배치 동작:

1. 현재 폴더 파일을 Azure Blob Storage `source-live/<department_code>` prefix로 업로드한다.
2. prefix 안에 더 이상 로컬에 없는 blob은 삭제한다.
3. 소스 파서로 업무 규칙 문서를 다시 만든다.
4. 로컬 JSON/SQLite index를 갱신한다.
5. Azure AI Search `ops-knowledge` index를 reset 후 재생성한다.

따라서 삭제된 파일은 다음 배치 완료 후 검색 결과에서도 제외된다. Storage credential이 없으면 1번에서
명확히 실패하므로 `.env`에 `AZURE_STORAGE_ACCOUNT_KEY`, `AZURE_STORAGE_CONNECTION_STRING`,
`AZURE_STORAGE_SAS_TOKEN` 중 하나를 먼저 넣는다.

## 검증 질문

Branch role:

```text
자동이체 등록 화면에서 출금계좌가 만료되었거나 사용 불가 상태라고 나와요. 납부자번호는 입력했습니다.
```

기대 결과:

- 출금계좌 상태, 납부자번호, 출금일, 중복 등록 여부를 확인하라고 안내한다.
- 소스코드, API path, SQL ID, 테이블명을 노출하지 않는다.
- 마지막에 조건 확인 후 재시도와 IT부서 전달 정보를 안내한다.

IT role:

```text
자동이체 등록 오류가 납니다. 관련 소스와 SQL 단서를 알려주세요.
```

기대 결과:

- 관련 화면, Service, Mapper, SQL, Table 단서를 요약한다.
- 고객 개인정보나 비밀값은 노출하지 않는다.

## 장애 대응

### Foundry 응답이 비어 있음

확인할 것:

- `FOUNDRY_PROJECT_ENDPOINT`가 `/api/projects/<project-name>`까지 포함하는지 확인
- `FOUNDRY_MODEL_DEPLOYMENT`가 실제 deployment name인지 확인
- `FOUNDRY_AI_SEARCH_CONNECTION_ID` 또는 `FOUNDRY_AGENT_NAME` 중 하나가 설정되어 있는지 확인
- `az account get-access-token --scope https://ai.azure.com/.default`가 성공하는지 확인

### Azure Search 업로드 실패

확인할 것:

- `EMBEDDING_PROVIDER=azure_openai`일 때 `AZURE_OPENAI_ENDPOINT`와 embedding deployment가 실제로 존재하는지 확인
- 기존 index가 384차원 local fallback으로 만들어졌다면 `python scripts/upload_azure_search.py --reset-index`로 다시 생성
- `AZURE_SEARCH_ENDPOINT`가 `https://...search.windows.net` 형식인지 확인
- API key를 쓰지 않으면 `az login` 계정에 Search Index Data Contributor 또는 Search Service Contributor 권한이 있는지 확인
- Search service와 Foundry project가 같은 tenant에 있는지 확인

### 데모 중 Foundry가 다시 초기화됨

`RAG_PROVIDER=local`로 전환하고 backend를 재시작한다. 이 경우 로컬 JSON/Elasticsearch 기반 검색과 static answer fallback으로 데모를 계속할 수 있다.
