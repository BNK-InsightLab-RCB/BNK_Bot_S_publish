# Source-Aware Branch Support RAG Chatbot

소스코드 기반 영업점 운영지원 RAG 챗봇 PoC입니다. 이 프로젝트는 매뉴얼 문서만 검색하는 RAG가 아니라, 화면 코드, Spring Controller/Service, MyBatis SQL, 테이블 정의서에서 업무 규칙 단위의 지식 문서를 생성한 뒤 영업점 직원용 안내와 IT 담당자용 요약을 분리해 제공합니다.

## Architecture

```text
sample/source repository
  -> source scanner
  -> frontend/java/mybatis/sql/table parsers
  -> static business-rule extractor
  -> optional Qwen summary enhancer
  -> embeddings
  -> Elasticsearch + local JSON checkpoint
  -> SQLite relation graph
  -> hybrid retrieval + RRF
  -> role-aware RAG answer
  -> React UI
```

## Documentation

- [Codebase analysis](docs/codebase-analysis.md): repository structure, runtime modes, data flow, module ownership, and validation checklist.
- [System architecture and UI summary](docs/system-architecture-and-ui-summary.md): Azure/Foundry integration and role-based UI overview.
- [Foundry reset runbook](docs/foundry-reset-runbook.md): recovery steps after hackathon Azure/Foundry resources are reset.
- [Source automation judgment](docs/azure-agent-source-automation.md): Foundry OpenAPI tool and source sync automation design.
- [Admin monitoring and KPI report](docs/admin-monitoring-kpi-report.md): administrator dashboard, local/MS monitoring, upload flow, and KPI validation plan.

## Requirements

- Python 3.11+
- Docker Desktop
- Node.js 20+
- macOS native MLX Qwen server for LLM calls
- Azure CLI for Microsoft Foundry demo mode

The MVP is designed to keep the end-to-end sample testable even when Elasticsearch or Qwen is not running. When those services are available, the same pipeline writes to Elasticsearch and calls the local OpenAI-compatible Qwen server.

For the Microsoft hackathon demo, the same source-aware documents can also be uploaded to Azure AI Search and queried through Microsoft Foundry Agent/Foundry IQ style retrieval. Local mode remains the deterministic fallback.

The Azure path follows the workshop flow in
[ChangJu-Ahn/azure_aisearch_workshop](https://github.com/ChangJu-Ahn/azure_aisearch_workshop):
keyword search, vector search, hybrid search, score tuning, semantic reranking,
and Foundry IQ/agentic retrieval over the same source-aware index.

## Source Knowledge JSON

The ingestion pipeline stores the same source-derived JSON in the local
`data/ops_knowledge.json` checkpoint and, when enabled, in Azure AI Search. Each
chunk stays close to one screen event, backend method, mapper SQL, table
definition, or incident note so the LLM gets a compact but actionable evidence
unit.

For demo review or Blob upload, the local index can also be exported as one
Korean-formatted JSON file per evidence chunk:

```bash
.venv/bin/python scripts/export_knowledge_json_pages.py \
  --local-index-path data/ops_knowledge.json \
  --output-dir backend/examples/bank_sample/docs/admin_uploads/bnk_hackathon_json_pages \
  --reset-output
```

Each file uses the review schema `업무명`, `화면번호`, `화면정보`, `API`, `dto`,
`error`, `exception`, `업무규칙`, `요약`, and `근거`. For the BNK hackathon demo,
the generated pages are uploaded under Azure Blob prefix
`source-live/bnk_hackathon/json-pages/`.

Core fields extracted from source code:

- `business_name`: 업무명 inferred from screen name or backend method.
- `screen_id`, `screen_name`, `screen_info`: screen number/name, menu id, input fields, and button context.
- `api_path`, `http_method`, `api_description`: API endpoint and what business action it performs.
- `dto_names`, `dto_fields`, `input_fields`: request DTOs, request getter fields, and branch-facing screen inputs.
- `validation_conditions`, `auth_codes`: if-condition checks and role/authority codes.
- `error_codes`, `error_messages`, `exception_types`: business error codes, user-visible messages, and thrown exception classes.
- `call_chain`: frontend API call, controller/service method, mapper SQL, and related SQL ids where linked.
- `tables`, `columns`, `sql_id`: data objects used by mapper SQL or table definition files.
- `branch_guide`, `it_guide`, `business_rules`: role-aware explanation snippets used for answer generation.

Branch users see only business-safe citations. IT/admin users can see API,
DTO, exception, SQL, table, and file-line evidence.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Run Elasticsearch

```bash
docker compose up -d elasticsearch
```

The Docker compose file limits Elasticsearch JVM heap to 2 GB for a Mac M4 Pro / 24 GB RAM PoC.

## Run Qwen Local Server

```bash
./scripts/run_qwen_server.sh
```

To keep Qwen running in the background on macOS, install it as a user LaunchAgent:

```bash
.venv/bin/pip install mlx-lm
./scripts/qwen_service.sh start
./scripts/qwen_service.sh status
./scripts/qwen_service.sh logs
./scripts/qwen_service.sh stop
```

`start` keeps the local Qwen OpenAI-compatible server alive after the terminal is
closed and restarts it if it exits. Logs are written to `data/logs/qwen.out.log`
and `data/logs/qwen.err.log`.

This script runs:

```bash
mlx_lm.server --model "Qwen/Qwen3-14B-MLX-4bit"
```

No external LLM API is used.

## Microsoft Foundry Demo Mode

Foundry mode keeps the source analysis pipeline local and moves the hosted retrieval/answering layer to Microsoft services:

```text
source parser
  -> KnowledgeDocument
  -> Azure OpenAI text-embedding-3-large embeddings
  -> optional Azure Blob Storage source bundle
  -> Azure AI Search index
  -> Azure AI Search vector + keyword hybrid retrieval
  -> semantic reranker
  -> Microsoft Foundry Responses API / Agent with Azure AI Search tool when configured
  -> local role guardrail
  -> React UI
```

Copy `.env.example` to `.env` and fill these values after creating the Azure resources:

```bash
RAG_PROVIDER=multi_agent
EMBEDDING_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://<aoai-resource>.openai.azure.com
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
AZURE_SEARCH_INDEX=ops-knowledge
AZURE_SEARCH_API_KEY=<optional-admin-key-if-not-using-az-login>
FOUNDRY_PROJECT_ENDPOINT=https://<foundry-resource>.ai.azure.com/api/projects/<project-name>
FOUNDRY_MODEL_DEPLOYMENT=gpt-5.4
# Preferred route: call a published Foundry Agent that has the Azure AI Search
# tool connected to AZURE_SEARCH_INDEX.
FOUNDRY_AGENT_NAME=test-agent
FOUNDRY_AGENT_VERSION=3
FOUNDRY_SQL_AGENT_NAME=SQLGenerator-Agent
FOUNDRY_SQL_AGENT_VERSION=3
# Fallback route: let this backend attach the Search tool directly.
FOUNDRY_AI_SEARCH_CONNECTION_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>/projects/<project>/connections/<search-connection>

# Optional: surface Foundry/OpenAI metrics in the admin dashboard via Azure Monitor.
AZURE_MONITOR_RESOURCE_ID=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<foundry-account>
AZURE_MONITOR_METRIC_NAMES=TokenTransaction,ProcessedPromptTokens,GeneratedTokens,Requests,Latency
AZURE_MONITOR_TOKEN_LIMIT=1000000
```

If `AZURE_OPENAI_API_KEY`, `AZURE_SEARCH_API_KEY`, and `FOUNDRY_API_KEY` are empty,
the backend uses Azure CLI tokens:

```bash
az login
```

Ingest locally and upload the same knowledge documents to Azure AI Search:

```bash
python -m backend.app.ingestion.pipeline \
  --source-dir backend/examples/bank_sample \
  --reset-index \
  --upload-azure-search
```

The default `EMBEDDING_PROVIDER=hash` is a deterministic local fallback with no
model download. When `EMBEDDING_PROVIDER=azure_openai`, the index must be
recreated because `text-embedding-3-large` vectors use a different dimension from
the local fallback embedding. Use `--reset-index` for that run.

For the current hackathon tenant, the Storage container is used as a source
artifact store rather than the runtime retriever:

```bash
mkdir -p data/storage-upload
zip -qr data/storage-upload/source-aware-branch-rag-poc.zip \
  README.md \
  docs/foundry-reset-runbook.md \
  data/ops_knowledge.json \
  backend/examples/bank_sample
```

Upload that bundle to `pjyragstore58/uhihi/source-aware-branch-rag-poc.zip`. Do not include
`.env` or API keys in the Storage bundle.

The app also exposes a drag-and-drop upload path for source artifacts:

```text
React admin panel
  -> POST /api/storage/upload
  -> FastAPI multipart handler
  -> Azure Blob Storage container
```

Configure one server-side credential in `.env` before using the drop zone:

```bash
AZURE_STORAGE_ACCOUNT=pjyragstore58
AZURE_STORAGE_CONTAINER=uhihi
AZURE_STORAGE_UPLOAD_PREFIX=source-drop
ADMIN_UPLOAD_LOCAL_DIR=backend/examples/bank_sample/docs/admin_uploads
AZURE_STORAGE_ACCOUNT_KEY=<storage-account-key>
# or AZURE_STORAGE_CONNECTION_STRING=<connection-string>
# or AZURE_STORAGE_SAS_TOKEN=<container-sas-token>
```

The browser never receives Storage credentials. Drag-and-drop uploads are saved
to the local sample document directory and Azure Blob Storage. Runtime chat
retrieval still uses the local JSON/Elasticsearch index or Azure AI Search
`ops-knowledge`, so after uploading new source files, run the ingestion/upload
pipeline again from the admin page or CLI to refresh the searchable index.

For source package batch sync, place department files under:

```text
source_repositories/<department_code>/
  frontend/
  backend/
  mapper/
  docs/
```

Then run:

```bash
./scripts/sync_sources.sh \
  --source-dir source_repositories/<department_code> \
  --department <department_code>
```

The sync job uploads the current source tree to Azure Blob Storage under
`source-live/<department_code>`, prunes stale blobs in that prefix, rebuilds the
local knowledge index, and uploads the resulting searchable documents to Azure
AI Search. Because it resets and rebuilds the Search index by default, deleted
source files disappear from chatbot retrieval after the job completes.

The same workflow is exposed as an admin API so Microsoft Foundry can call it
through an OpenAPI tool after this backend is deployed to Azure:

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

Use [docs/foundry-source-sync.openapi.json](docs/foundry-source-sync.openapi.json)
as the Foundry OpenAPI tool definition. Set `SOURCE_SYNC_ADMIN_TOKEN` before
exposing the endpoint outside your laptop.

You can also re-upload an existing local index after Foundry resources are reset:

```bash
python scripts/upload_azure_search.py --reset-index
```

## Ingest Sample Source

```bash
python -m backend.app.ingestion.pipeline \
  --source-dir backend/examples/bank_sample \
  --reset-index \
  --generate-summaries
```

For a faster static-only run:

```bash
python -m backend.app.ingestion.pipeline \
  --source-dir backend/examples/bank_sample \
  --reset-index
```

For Foundry demo mode, append `--upload-azure-search` after `.env` is configured.

## Run Backend

```bash
uvicorn backend.app.main:app --reload --port 9000
```

To use the local Qwen server for chat responses instead of the static fallback:

```bash
ENABLE_LLM_CHAT=true uvicorn backend.app.main:app --reload --port 9000
```

To run with the Supervisor multi-agent route and Microsoft Foundry:

```bash
RAG_PROVIDER=multi_agent uvicorn backend.app.main:app --reload --port 9000
```

`multi_agent` mode uses a Foundry Agent first when `FOUNDRY_AGENT_NAME` or
`FOUNDRY_AI_SEARCH_CONNECTION_ID` is configured. In that route, the backend sends
the user's question to Foundry, and the Foundry Agent/Search tool performs
retrieval against `AZURE_SEARCH_INDEX`. If Foundry is unavailable, the backend
falls back to direct Azure AI Search retrieval and then local role guardrails.
For IT users, the backend first asks local Qwen to answer exactly `yes` or `no`
for SQL-generation intent. `yes` routes to `FOUNDRY_SQL_AGENT_NAME`; `no` routes
to the normal RAG agent.

The admin dashboard can show real Microsoft-side model metrics when
`AZURE_MONITOR_RESOURCE_ID` is set and the signed-in Azure CLI identity can read
Azure Monitor metrics for that resource. Without it, the UI keeps demo values so
the local PoC remains runnable.

Important endpoints:

- `GET /api/health`
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/ingest/run`
- `GET /api/ingest/status`
- `POST /api/search`
- `POST /api/chat`
- `POST /api/storage/upload`
- `POST /api/runtime/tickets`
- `POST /api/runtime/tickets/{ticket_id}/replies`

`GET /api/health` includes `rag_provider` so the demo operator can confirm whether the backend is using `local`, `foundry`, or `multi_agent`.

## Run Chatbot UI

For the final demo path, run one command from the repository root:

```bash
./scripts/run_chatbot.sh
```

The script starts FastAPI on `http://127.0.0.1:9000`, starts the React UI on
`http://127.0.0.1:5173`, and opens the browser. With the current hackathon
configuration, chat answers use Azure AI Search retrieval and Microsoft Foundry
generation. Qwen remains available only when switching to local mode with
`RAG_PROVIDER=local` and `ENABLE_LLM_CHAT=true`.

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:9000`.

## Test

```bash
pytest backend/tests
```

The end-to-end tests use the bundled sample source and the local JSON index fallback, so they do not require Elasticsearch or Qwen to be running.

## Sample Questions

- 고객조회 화면에서 저장이 안돼요.
- 고객번호 넣었는데 고객이 조회되지 않아요.
- 저장 권한이 없다고 나오는데 어떻게 해야 하나요?
- 해지 고객 수정이 안되는 이유가 뭐예요?

## Security Model

`branch` role responses hide source code, internal API paths, table details, and implementation identifiers. `it` role responses may include file names, method names, SQL IDs, and table names after sensitive values are masked. The safety guard blocks guidance for permission bypass, security bypass, direct production DB updates, and secret exposure.

## Project Intent

본 PoC의 핵심은 단순히 매뉴얼이나 소스코드를 벡터DB에 저장하는 것이 아니라, 소스코드 내부의 화면 흐름, API 호출, Controller-Service-Mapper-SQL 연결, 조건문, 권한 검증, 상태값 분기, 예외 메시지를 자동 분석하여 업무 규칙 단위의 지식 데이터로 변환하는 것이다.

이를 통해 영업점 직원의 자연어 문의가 들어왔을 때 관련 화면과 소스 위치를 찾는 것에 그치지 않고, 해당 화면에서 발생 가능한 오류 조건과 조치 방법을 영업점 직원이 이해할 수 있는 업무 언어로 안내할 수 있다.

초기 PoC는 Mac M4 Pro 24GB 환경에서 Qwen3-14B-MLX-4bit와 Elasticsearch를 활용하여 로컬 환경 중심으로 구현하며, 향후 운영 로그, 장애 이력, ITSM, 배포 이력과 연계하여 장애 대응 자동화 수준을 높이는 방향으로 확장한다.

해커톤 데모 모드에서는 Microsoft Foundry Agent, Foundry IQ/Azure AI Search 기반 검색, Supervisor-style multi-agent orchestration을 사용한다. 기본 로컬 모드는 계속 Qwen과 Elasticsearch/local JSON fallback으로 동작하므로 Foundry 테스트 리소스가 초기화되어도 샘플 end-to-end 테스트는 유지된다.
