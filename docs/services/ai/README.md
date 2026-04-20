# AI Service Feature Inventory

Last updated: 2026-04-20

## Scope

AI microservice mounted through `/api/v1/workspaces/*/ai*`, `/api/v1/workspaces/*/rag*`, and internal `/internal/analyze-commits`.

Primary code roots:

- `services/ai/main.py`
- `services/ai/routers/v1/`
- `services/ai/routers/internal.py`
- `services/ai/services/`
- `services/ai/infrastructure/rag/`
- `services/ai/infrastructure/tools/`
- `services/ai/infrastructure/llm/`

## Current Feature Ownership

| Feature group | Routes (examples) | Main files |
|---|---|---|
| AI model configuration | `/workspaces/{workspace_id}/ai/models*` | `routers/v1/ai.py` |
| Workspace chat | `/workspaces/{workspace_id}/ai/chat` | `routers/v1/ai_chat.py`, `services/ai_chat_service.py` |
| Project chat | `/workspaces/{workspace_id}/projects/{project_id}/ai/chat` (+ stream) | `routers/v1/ai_chat.py`, `services/ai_chat_service.py` |
| Plan suggestion/commit | `/ai/suggest-plan`, `/ai/suggest-plan/commit` | `routers/v1/ai_chat.py`, `services/ai_chat_service.py` |
| Weekly summary | `/ai/weekly-summary` | `routers/v1/ai_chat.py`, `services/ai_chat_service.py` |
| Reindex + capabilities | `/ai/reindex`, `/ai/chat/capabilities` | `routers/v1/ai_chat.py`, `services/document_indexer.py` |
| File parsing & OPPM extraction/fill | `/ai/parse-file`, `/ai/oppm-extract`, `/ai/oppm-fill` | `routers/v1/ai.py`, `routers/v1/oppm_fill.py`, `infrastructure/file_parser.py` |
| RAG query API | `/workspaces/{workspace_id}/rag/query` | `routers/v1/rag.py`, `services/rag_service.py` |
| Feedback logging | `/ai/feedback` (workspace/project) | `routers/v1/ai_chat.py` |
| Internal commit analysis | `/internal/analyze-commits` | `routers/internal.py`, `services/ai_analyzer.py` |

## Service Flowchart

```mermaid
flowchart TD
    A[Client request AI or RAG endpoint] --> B[AI router]
    B --> C[Auth and workspace context]
    C --> D{Endpoint type}
    D -- Chat --> E[ai_chat_service]
    D -- RAG query --> F[rag_service]
    D -- Internal analysis --> G[ai_analyzer]

    E --> H[Guardrails and retrieval context]
    H --> I[TAOR loop and tool registry]
    I --> J[(Shared DB and optional Redis cache)]

    F --> K[Query rewrite and retrievers]
    K --> J

    G --> J
    J --> L[Final response payload]
```

## Current RAG/Tooling Architecture

- TAOR loop with bounded iterations (max 7)
- input and output guardrails
- query rewriting
- parallel retrieval (vector/keyword/structured)
- reranking and project-context boost
- Redis semantic cache
- tool registry (24 tools across oppm/task/cost/read/project)
- multi-provider adapters (OpenAI, Anthropic, Ollama, Kimi)

Detailed refs:

- `docs/ai/AI-PIPELINE-REFERENCE.md`
- `docs/ai/TOOL-REGISTRY-REFERENCE.md`

## AI Evolution Options (for future upgrades)

**See also:** Detailed feasibility analysis in `GRAPH-FEASIBILITY.md` and migration roadmap in `GRAPH-MIGRATION-PATHS.md`

### Option A: Graph API as orchestration layer

Use a graph-based orchestration API for conversation/tool pipelines while keeping existing repository/tool boundaries.

Best when:

- you want stronger stateful orchestration without replacing all retrieval logic
- you need pluggable multi-step execution graphs per query type

Primary impact:

- chat orchestration and tool-call pipeline
- limited API contract shifts

**Feasibility:** ⭐⭐⭐⭐ High | Effort: Medium | Business Impact: Low-Medium
**Recommendation:** Consider after GraphRAG succeeds (non-blocking)

### Option B: GraphRAG replacement

Replace current retrieval stages with graph-native retrieval over entity/relationship graphs.

Best when:

- relationship reasoning is the dominant use case
- vector+keyword retrieval misses dependency/context chains

Primary impact:

- indexing model, retrieval strategy, scoring logic, source/citation shape
- higher migration cost and schema/index changes likely

**Feasibility:** ⭐⭐⭐⭐ High | Effort: Medium-Large | Business Impact: **High**
**Recommendation:** ⭐ Pilot immediately (GraphRAG Hybrid, 4 weeks)

### Option C: Hybrid current RAG + GraphRAG

Keep current retrievers and add graph retrieval as an additional retriever/reranker signal.

Best when:

- you want low-risk incremental rollout
- you need measurable quality gains before full migration

Primary impact:

- add new retriever branch and fusion logic
- minimal disruption to existing API shape

**Feasibility:** ⭐⭐⭐⭐ High | Effort: Medium | Business Impact: High
**Recommendation:** ⭐ **Start here** — pilot path documented in GRAPH-MIGRATION-PATHS.md

### Option D: Graph Database (Neo4j, TigerGraph)

Migrate relationship/entity data to graph-native store alongside PostgreSQL.

Best when:

- deep relationship traversals (4+ hops) become common
- dual-system operational overhead is acceptable

Primary impact:

- new infrastructure, operational complexity
- improved query expressiveness for relationship patterns

**Feasibility:** ⭐⭐⭐ Medium | Effort: Large | Business Impact: Medium
**Recommendation:** Defer — revisit after GraphRAG pilot demonstrates need

## Data Touchpoints

- `ai_models`
- `document_embeddings`
- `audit_log` (feedback/traceability)
- read/write access to shared business tables through AI repositories/tools

## Change Impact Checklist

- Chat/RAG behavior change -> update `docs/FLOWCHARTS.md`, `docs/ARCHITECTURE.md`, and AI docs.
- Tool contracts change -> update `docs/ai/TOOL-REGISTRY-REFERENCE.md` and API docs.
- Retrieval/index shape change -> update schema docs if tables/indexes change.
- Internal analysis contract change -> coordinate with Git service `trigger_ai_analysis` payload/headers.

