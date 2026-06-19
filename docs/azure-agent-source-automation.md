# Azure Agent Source Automation 판단

## 결론

가능하다. 다만 Microsoft Foundry Agent 하나가 소스 파일 업로드, 삭제 감지, 파싱, 색인까지 전부 직접
수행하는 구조가 아니라, Foundry Agent가 승인된 도구를 호출하고 실제 작업은 Azure Functions, Azure AI
Search indexer, 또는 이 프로젝트의 백엔드 API가 수행하는 구조가 맞다.

이 프로젝트에는 다음 구현을 추가했다.

- `POST /api/source-sync/run`: 부서 소스 폴더를 Storage에 동기화하고 Azure AI Search를 재색인한다.
- `GET /api/source-sync/status`: 마지막 동기화 상태를 반환한다.
- `docs/foundry-source-sync.openapi.json`: Foundry OpenAPI tool 등록용 스펙이다.
- `SOURCE_SYNC_ADMIN_TOKEN`: 외부 배포 시 OpenAPI tool 호출을 보호하는 헤더 토큰이다.

## 공식 문서 기준 판단

- Foundry Agent tool은 대화 중 외부 API 호출, 벡터 저장소 조회, Python 실행 등을 수행할 수 있다.
  특히 OpenAPI tool은 외부 HTTP API 연결, Azure Functions tool은 Azure Function 호출에 적합하다.
  문서: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/tool-catalog
- Foundry IQ Knowledge Base는 Azure AI Search를 MCP 기반 지식 도구로 연결해 질의 분해, keyword/vector/hybrid
  검색, semantic reranking, source reference를 제공한다.
  문서: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/foundry-iq-connect
- Azure AI Search Blob indexer는 Blob Storage의 신규/변경 파일을 감지하고, 스케줄 또는 on-demand로 실행할 수 있다.
  문서: https://learn.microsoft.com/en-us/azure/search/search-how-to-index-azure-blob-storage
- 삭제 감지는 자동 변경 감지와 다르게 soft delete 전략이 필요하다.
  문서: https://learn.microsoft.com/en-us/azure/search/search-how-to-index-azure-blob-changed-deleted
- Search indexer는 custom skill을 통해 Azure Functions 또는 컨테이너에 있는 별도 처리 로직을 호출할 수 있다.
  문서: https://learn.microsoft.com/en-us/azure/search/cognitive-search-custom-skill-interface
- Blob Storage 이벤트는 Event Grid를 통해 Azure Functions, Logic Apps, HTTP listener로 전달할 수 있어 업로드 즉시
  배치를 트리거할 수 있다.
  문서: https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blob-event-overview

## 이 PoC에서 권장하는 현실적인 구조

해커톤 데모/로컬 병행 기준:

```text
source_repositories/<department>
  -> ./scripts/sync_sources.sh 또는 POST /api/source-sync/run
  -> Azure Blob Storage source-live/<department>
  -> custom parser: FE/BE/MyBatis/table docs -> KnowledgeDocument
  -> Azure OpenAI embedding
  -> Azure AI Search ops-knowledge
  -> Foundry Responses API / Agent
  -> React chatbot UI
```

Azure 완전 자동화 기준:

```text
Azure Blob Storage source-live/<department>
  -> Event Grid
  -> Azure Function or Container Apps job
  -> same parser/indexer package
  -> Azure AI Search ops-knowledge
  -> Foundry IQ Knowledge Base
  -> Foundry Agent
```

## 왜 Foundry Agent 단독 처리로 두지 않는가

- 소스 파싱은 Java/Vue/MyBatis/XML/테이블 정의를 구조화하는 결정적 배치 작업이다. LLM 대화 에이전트에게
  매번 맡기면 재현성과 삭제 반영이 약해진다.
- 삭제 반영은 "파일이 없어졌다"는 상태 추적이 필요하다. Azure AI Search 문서도 삭제 감지에는 soft delete
  정책을 첫 indexer 실행부터 설정하라고 안내한다.
- 운영 API를 도구로 붙이면 Foundry Agent는 사용자의 승인된 운영 명령만 해석하고, 실제 반영은 검증 가능한
  코드가 처리한다.

## Foundry에 붙이는 방법

1. 이 백엔드를 Azure App Service, Azure Container Apps, 또는 Azure Functions 앞단으로 배포한다.
2. `.env`에 `SOURCE_SYNC_ADMIN_TOKEN`을 설정한다.
3. `docs/foundry-source-sync.openapi.json`의 `servers.url`을 배포 URL로 바꾼다.
4. Foundry project의 Tools에서 OpenAPI tool을 추가한다.
5. 인증은 API key header 방식으로 `x-source-sync-token`에 `SOURCE_SYNC_ADMIN_TOKEN` 값을 연결한다.
6. Agent instructions에 운영 명령은 확인 후 `runSourceSync`를 호출하라고 넣는다.

권장 instructions:

```text
When the user asks to add, update, or delete department source files, do not infer file contents.
Confirm the department code and source directory.
If confirmed, call runSourceSync with reset_index=true and prune_storage=true.
After the tool returns, summarize uploaded_count, deleted_count, indexed_count, and whether Azure AI Search upload succeeded.
Never expose API keys, Storage credentials, or source-sync admin token.
```

## 현재 로컬에서 바로 쓰는 명령

챗봇 실행:

```bash
cd /Users/qkrwnsmir/Documents/BNK_Bot_S_publish
./scripts/run_chatbot.sh
```

부서 소스 동기화:

```bash
cd /Users/qkrwnsmir/Documents/BNK_Bot_S_publish
./scripts/sync_sources.sh \
  --source-dir source_repositories/<department_code> \
  --department <department_code>
```

API로 실행:

```bash
curl -X POST http://127.0.0.1:9000/api/source-sync/run \
  -H "Content-Type: application/json" \
  -H "x-source-sync-token: $SOURCE_SYNC_ADMIN_TOKEN" \
  -d '{
    "source_dir": "source_repositories/card_ops",
    "department": "card_ops",
    "reset_index": true,
    "prune_storage": true
  }'
```
