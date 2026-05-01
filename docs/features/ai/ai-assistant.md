# Feature: AI Assistant, Plan Suggestion, Weekly Summary, Reindex, RAG, And Model Configuration

Last updated: 2026-05-01

## What It Does

- Workspace chat with RAG plus workspace-scoped tool execution for write-capable members
- Project chat with agentic tool loop — up to 7 LLM iterations, executing registry tools to read or write project data
- Input guardrails (injection detection, length limit) and output guardrails (sensitive data scrub)
- LLM-based query rewriting before retrieval for better recall
- Semantic cache (Redis, cosine ≥ 0.92, TTL 300 s) to skip re-retrieval on repeated questions
- Tool registry with 24 tools across five categories: oppm (5), task (5), cost (5), read (6), project (3)
- Native LLM function calling for OpenAI and Anthropic; XML-prompt-based tool execution for Ollama and Kimi
- Suggested project plans (generate + commit)
- Weekly project summaries
- OPPM fill assistance
- Server-side file parsing and OPPM image extraction
- Workspace reindexing for retrieval
- RAG query endpoint
- Per-workspace AI model configuration
- User feedback (thumbs up/down) logged to `audit_log`

## How It Works

1. `frontend/src/components/ChatPanel.tsx` opens in workspace or project context.
2. Workspace chat posts to `/ai/chat`:
   - The route now requires write access because the implementation can execute tools.
   - RAG context and memory are loaded across the workspace.
   - The full tool registry is exposed so the assistant can create or update workspace/project data, including creating a project before adding objectives or tasks.
3. Project chat posts to `/projects/{project_id}/ai/chat`:
   - Input guardrail checks message for injection patterns and length.
   - Query rewriting expands vague queries into richer search terms (skipped for queries > 300 chars or ≤ 2 words).
   - RAG pipeline: semantic cache lookup → classify → parallel vector + keyword + structured retrieval → RRF rerank → project boost → cache store.
   - Full project context (objectives, tasks, risks, costs, team, commits) is loaded using tiered windowing.
   - Agentic tool loop runs up to 7 iterations: LLM call → parse tool calls → execute via registry → inject results as next user turn → optionally requery on low confidence → repeat until confident answer or max iterations.
   - Output guardrail scrubs sensitive patterns before the response is returned.
   - Response includes `message`, `tool_calls`, `updated_entities`, `iterations`, and `low_confidence`.
4. Users can submit feedback via `POST /projects/{id}/ai/feedback` or `POST /workspaces/{ws}/ai/feedback`.
5. Project quick actions call `suggest-plan`, `suggest-plan/commit`, `weekly-summary`, and `oppm-fill`.
6. File and image helpers call `parse-file` and `oppm-extract` on the intelligence service.
7. Admins manage `ai_models` from `frontend/src/pages/Settings.tsx`.
8. `POST /ai/reindex` rebuilds retrieval data for the workspace.
9. `POST /rag/query` runs the RAG pipeline against workspace data and memory context.

## Frontend Files

- `frontend/src/components/ChatPanel.tsx`
- `frontend/src/pages/Settings.tsx`

## Backend Files

- `services/intelligence/domains/chat/router.py`
- `services/intelligence/domains/models/router.py`
- `services/intelligence/domains/rag/router.py`
- `services/intelligence/domains/chat/service.py`
- `services/intelligence/domains/rag/service.py`
- `services/intelligence/domains/rag/document_indexer.py`
- `services/intelligence/infrastructure/rag/agent_loop.py`
- `services/intelligence/infrastructure/rag/query_rewriter.py`
- `services/intelligence/infrastructure/rag/guardrails.py`
- `services/intelligence/infrastructure/rag/semantic_cache.py`
- `services/intelligence/infrastructure/tools/registry.py`
- `services/intelligence/infrastructure/tools/oppm_tools.py`
- `services/intelligence/infrastructure/tools/task_tools.py`
- `services/intelligence/infrastructure/tools/cost_tools.py`
- `services/intelligence/infrastructure/tools/read_tools.py`
- `services/intelligence/infrastructure/tools/project_tools.py`
- `services/intelligence/infrastructure/llm/tool_parser.py`
- `services/intelligence/infrastructure/file_parser.py`
- `shared/models/ai_model.py`
- `shared/models/embedding.py`

## Primary Tables

- `ai_models`
- `document_embeddings`
- `audit_log` — feedback and memory context

## Detailed Pipeline Reference

### End-To-End Flow

```text
User message
  -> Input guardrail                    guardrails.py
  -> Conversation memory load          memory.py
  -> Query rewriting                   query_rewriter.py
  -> Query embedding                   embedding.py
  -> Semantic cache lookup             semantic_cache.py
      -> HIT  -> reuse cached context
      -> MISS -> continue
  -> Query classification              agent.py
  -> Parallel retrievers               retrievers/
      -> vector
      -> keyword
      -> structured
  -> RRF rerank                        reranker.py
  -> Project boost                     rag_service.py
  -> Context formatting                rag_service.py
  -> Semantic cache store              semantic_cache.py
  -> Prompt construction               ai_chat_service.py
  -> TAOR agent loop                   agent_loop.py
      -> LLM call
      -> parse tool calls
      -> execute tools
      -> inject observations
      -> optional requery
  -> Output guardrail                  guardrails.py
  -> Audit log                         AuditRepository
  -> Response                          message + tool_calls + updated_entities + iterations + low_confidence
```

### RAG Pipeline Stages

| Stage | File | What it does |
|---|---|---|
| 1. Input Guardrail | `infrastructure/rag/guardrails.py` | Blocks prompt-injection strings and input > 4000 chars |
| 2. Conversation Memory | `infrastructure/rag/memory.py` | Loads recent AI interactions from `audit_log` |
| 3. Query Rewriting | `infrastructure/rag/query_rewriter.py` | Expands vague queries when a model list is available |
| 4. Embedding | `infrastructure/embedding.py` | Creates query vector for cache + retrieval |
| 5. Semantic Cache | `infrastructure/rag/semantic_cache.py` | Redis-backed, cosine ≥ 0.92, TTL 300s |
| 6. Query Classification | `infrastructure/rag/agent.py` | Pattern-based retriever ordering (vector/keyword/structured) |
| 7. Parallel Retrieval | `retrievers/vector_retriever.py`, `keyword_retriever.py`, `structured_retriever.py` | Run in parallel, return `RetrievedChunk` objects |
| 8. Reranking & Formatting | `infrastructure/rag/reranker.py`, `domains/rag/service.py` | RRF fusion + project boost + context formatting |

### Project Context Builder

Primary entry point: `services/intelligence/domains/chat/service.py` -> `_build_project_context()`

Loads into tiered character budgets (max 32000 total):
- Tier 1 (16000): project metadata, objectives, tasks, costs
- Tier 2 (12000): deliverables, forecasts, risks, team, commits
- Tier 3 (4000): remaining context

### TAOR Agent Loop

Primary entry point: `services/intelligence/infrastructure/rag/agent_loop.py` -> `run_agent_loop()`

Controls:
- `MAX_ITERATIONS = 7`
- Stop threshold: confidence `>= 4`
- Requery threshold: confidence `<= 2` (begins after iteration 2)

`AgentLoopResult` fields: `final_text`, `all_tool_results`, `updated_entities`, `iterations`, `low_confidence`

### Tool Call Parsing

File: `services/intelligence/infrastructure/llm/tool_parser.py`

- OpenAI native: `parse_openai_tool_calls()`
- Anthropic native: `parse_anthropic_tool_calls()`
- Prompt-based (Ollama/Kimi): `parse_xml_tool_calls()` expecting `<tool_calls>[...]</tool_calls>`

### LLM Adapter Layer

Files: `services/intelligence/infrastructure/llm/base.py`, `__init__.py`, provider adapters

Base contract:
- `call(model_id, prompt, **kwargs) -> LLMResponse`
- `call_json(model_id, prompt, **kwargs) -> dict | None`
- `call_with_tools(model_id, messages, tools=None, **kwargs) -> LLMResponse`
- `health_check(**kwargs) -> bool`

### Output Guardrail & Audit

`sanitize_output()` scrubs sensitive patterns before returning.

Audit log entries:
- Project chat: `action = "ai_chat"`, `operation = "chat"`
- Workspace chat: `operation = "workspace_chat"`
- Both include: `project_id`, truncated message/response, `tool_calls_count`, `agent_iterations`

## Update Notes

- AI model configuration is workspace-scoped.
- RAG and chat behavior depend on indexed workspace data, not just live tables.
- `GET /ai/chat/capabilities` now reflects write-capable tool access via `can_execute_tools` based on the caller's workspace role.
- Feedback is written to `audit_log` with `action = "ai_feedback"` and `metadata` containing rating, comment, and related message content.
