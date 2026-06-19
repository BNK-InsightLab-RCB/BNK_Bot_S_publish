# Admin Monitoring and KPI Report

## Purpose

The administrator workspace is the operating view for the role-based RAG PoC.
It uses the same design decisions applied to the branch and IT pages:

- Branch answers remain business-safe and hide internal code, API paths, SQL, and secrets.
- IT answers can expose technical evidence, but still avoid secrets and credential material.
- Admin users need both operational status and auditability: local Qwen/local index, Microsoft Foundry, Azure AI Search, Azure Blob Storage, and branch-to-IT tickets must be visible together.

## Implemented Dashboard

The admin page now contains:

- KPI strip: total answers, Microsoft cloud answers, local answers, average response time, open tickets, uploaded artifact volume.
- Local / MS Azure route panel: local Qwen model, local knowledge index count, upload directory, Foundry model, Azure AI Search index, and Azure Blob Storage configuration.
- Drag-and-drop upload: JSON, PDF, Markdown, CSV, XLSX, TXT, Java, XML, Vue, and SQL files are saved to the local sample document directory and uploaded to Azure Blob Storage through the backend.
- Source indexing actions: local index refresh and optional Azure AI Search upload are separate buttons.
- Answer generation log: recent question preview, answer backend, retrieval backend, response time, answer preview, source titles, and agent trace snippets.
- Runtime log table: chat, ticket, storage upload, and ingestion events share one local audit stream.

## Local and Microsoft Logging

Runtime events are stored in `data/runtime_events.json`.

For chat responses, the app records:

- route: `answer_backend` such as `local`, `foundry`, `safety`, or `scope_guard`
- retrieval backend: `local_json`, `azure_ai_search`, `foundry`, or mixed routes
- response duration in milliseconds
- answer preview only, not the full unrestricted answer
- source titles and source count
- Foundry/local supervisor trace snippets

For storage uploads, the app records:

- uploaded file names
- local saved paths
- Azure Blob names
- total uploaded bytes
- success or Azure configuration/upload failure

## Upload and Index Flow

```text
Admin drag-and-drop
  -> POST /api/storage/upload
  -> save to backend/examples/bank_sample/docs/admin_uploads
  -> upload to Azure Blob Storage
  -> append runtime upload event

Admin index button
  -> POST /api/ingest/run
  -> parse source/code/docs/uploaded JSON/PDF/TXT
  -> write local ops_knowledge.json
  -> optionally upload searchable documents to Azure AI Search
  -> append runtime ingest event
```

Uploaded JSON files are mapped to the source-aware schema when they contain fields such as:

```json
{
  "업무명": "자동이체 등록",
  "화면번호": "AUTO_710",
  "화면정보": {"button": "등록"},
  "API": {"path": "/api/ops/auto-debit/register", "role": "자동이체 등록 처리"},
  "dto": ["AutoDebitRequest"],
  "error": ["ACCOUNT_UNAVAILABLE"],
  "exception": ["BizException"]
}
```

PDF files are stored and indexed as uploaded artifacts. If `pypdf` or `PyPDF2`
is installed in the runtime, extracted PDF text is added to the searchable
document; otherwise the PDF is still tracked as a local and Azure Storage
artifact.

## Microsoft Azure / Foundry Monitoring Check

Microsoft Foundry observability supports evaluation, monitoring, and tracing.
The official documentation states that Foundry can collect evaluation metrics,
logs, traces, and model outputs for quality, safety, and operational health:
https://learn.microsoft.com/en-us/azure/foundry/concepts/observability

Foundry Agent Monitoring Dashboard can show token usage, latency, run success
rate, and evaluation outcomes for production traffic after Application
Insights is connected:
https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard

Foundry tracing can capture latency, exceptions, prompt content, and retrieval
operations. Server-side tracing is enabled by connecting Application Insights
to the Foundry project:
https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/trace-agent-setup

Foundry portal evaluations can be run against agents, models, datasets, or
existing traces to measure performance, quality, and safety:
https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluate-generative-ai-app

Azure AI Search can be monitored through built-in metrics and diagnostic logs.
Search latency, QPS, and throttled query percentage are available in the
Monitoring tab, and longer-term query/log analysis requires diagnostic logging
to Log Analytics:
https://learn.microsoft.com/en-us/azure/search/search-monitor-queries
https://learn.microsoft.com/en-us/azure/search/search-monitor-enable-logging

## KPI Set

| KPI | Target | How to Verify |
| --- | --- | --- |
| Grounded answer rate | 90% or higher | `source_count > 0` among chat logs |
| Cloud route usage | Demo mode 60% or higher | `answer_backend=foundry` or retrieval includes `azure` |
| Local fallback health | Local path always available | Ask a known sample question with `RAG_PROVIDER=local` |
| Average response latency | Track trend, investigate spikes | Runtime `duration_ms`; Foundry dashboard latency for hosted route |
| Open ticket count | 0 during demo closeout | Ticket status not `replied` or `closed` |
| Safety/scope block rate | 100% for non-business or bypass prompts | Guardrail regression prompts should return blocked status |
| Upload success rate | 100% after Storage config | Storage upload events with status `uploaded` |
| Azure Search refresh | Index count matches expected docs | Ingest event count and Azure Search document count |

## Validation Plan

1. Run local smoke questions as branch, IT, and admin roles.
2. Confirm runtime log rows distinguish `local`, `foundry`, `safety`, and `scope_guard`.
3. Upload one JSON and one PDF from the admin page.
4. Confirm the files appear in `backend/examples/bank_sample/docs/admin_uploads`.
5. Confirm Azure Blob upload event status is `uploaded`.
6. Run local index refresh; confirm local document count increases when supported uploaded files are present.
7. Run Azure Search refresh when Azure Search credentials are configured.
8. In Foundry portal, check Agent Monitor and Traces after generating Foundry traffic.
9. In Azure AI Search, check Metrics for latency, QPS, and throttled query percentage.
10. Use the KPI panel as the demo-facing operational summary.

## Notes

- The admin dashboard is intentionally based on local app telemetry first.
  Azure portal metrics are still required for authoritative token usage,
  Foundry evaluation scores, and Azure AI Search service-level metrics.
- The app does not expose Azure Storage credentials to the browser.
- Full customer PII, account numbers, secrets, and credential material must not
  be placed in uploaded sample files, logs, or Azure Search documents.
