# AGENTS.md

## Goal

Build and maintain the Source-Aware Branch Support RAG Chatbot PoC.

## Constraints

- Default local mode uses only the local Qwen OpenAI-compatible server for LLM calls.
- Hackathon demo mode may use Microsoft Foundry Agent, Foundry IQ/Azure AI Search, and Azure-hosted model deployments.
- Do not add external hosted LLM APIs outside Microsoft Foundry/Azure services required for the hackathon demo.
- Keep branch-role answers free of source code, internal API paths, database internals, secrets, and bypass instructions.
- Prefer static extraction first; use LLM summarization as an optional enhancer.
- Keep the sample end-to-end path runnable without production systems.
- Do not store customer PII, account numbers, secrets, or credential material in agent memory, logs, sample data, or Azure Search documents.

## Useful Commands

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

## Implementation Notes

- `backend/app/parsers` converts source files into structured `KnowledgeDocument` objects.
- `backend/app/ingestion/pipeline.py` owns scan, parse, enrich, embed, index, and graph persistence.
- `backend/app/retrieval` owns query analysis, exact/BM25/vector retrieval, RRF, graph expansion, and context building.
- `backend/app/storage/azure_search.py` owns Azure AI Search schema creation and KnowledgeDocument upload for Foundry demo mode.
- `backend/app/foundry` owns Microsoft Foundry Responses API calls.
- `backend/app/agents` owns Supervisor and worker-style orchestration across local retrieval, Foundry generation, and safety.
- `backend/app/rag` owns role-aware answer generation, citations, and safety.
- `backend/examples/bank_sample` must remain small and deterministic so tests are fast.
