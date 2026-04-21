# AI Pipeline Reference

Last updated: 2026-04-20

## Purpose

This document describes the current AI-service execution pipeline in `services/ai/`.

Use it when changing chat behavior, RAG retrieval, tool execution, provider adapters, or the boundaries between workspace chat, project chat, and commit analysis.

## Runtime Shape

The AI service is a FastAPI microservice with two main chat modes plus one internal analysis path:

- Project chat: full project context plus TAOR tool loop
- Workspace chat: workspace context plus TAOR tool loop with workspace-scoped/project-creation tools
- Internal commit analysis: git service calls `/internal/analyze-commits` with `X-Internal-API-Key`

## End-To-End Flow

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

## Chat Modes

### Project Chat

Entry route:

- `POST /api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/chat`

Project chat builds:

- full project context from objectives, tasks, costs, risks, deliverables, forecasts, team, and recent commits
- RAG context from retrieval
- tool definitions from the registry

Project chat passes the current `project_id` into tool execution automatically.

### Workspace Chat

Entry route:

- `POST /api/v1/workspaces/{workspace_id}/ai/chat`

Workspace chat builds:

- workspace name and project list
- workspace-scoped RAG context
- the full tool registry

Workspace chat uses the same TAOR loop, but without an implicit current `project_id`. Tools that need a project can still run when the model supplies a `project_id` explicitly, which is why the route now requires write access.

### Internal Commit Analysis

Entry route:

- `POST /internal/analyze-commits`

This path is protected by `X-Internal-API-Key` and is called by the git service after webhook ingestion.

## RAG Pipeline

Primary entry point:

- `services/ai/services/rag_service.py` -> `retrieve_with_rag_pipeline()`

Return type:

- `RAGResult(context, sources, memory_context, chunks)`

### Stage 1: Input Guardrail

File:

- `services/ai/infrastructure/rag/guardrails.py`

`check_input()` blocks:

- prompt-injection style strings
- oversized input above 4000 characters

### Stage 2: Conversation Memory

File:

- `services/ai/infrastructure/rag/memory.py`

`load_memory()` reads recent AI interactions from `audit_log` and returns a trimmed context block.

### Stage 3: Query Rewriting

File:

- `services/ai/infrastructure/rag/query_rewriter.py`

`rewrite_query()` expands vague queries when:

- a model list is available
- the query is not already long or very short

### Stage 4: Embedding

File:

- `services/ai/infrastructure/embedding.py`

`generate_embedding()` creates the query vector used for:

- semantic cache lookup
- vector retrieval

### Stage 5: Semantic Cache

File:

- `services/ai/infrastructure/rag/semantic_cache.py`

Current settings:

- backend: Redis
- threshold: cosine similarity `>= 0.92`
- TTL: `300` seconds
- key prefix: `ai:sem_cache:`

Cache lookup is attempted before retrieval. Cache store happens after new context is built.

### Stage 6: Query Classification

File:

- `services/ai/infrastructure/rag/agent.py`

`classify_query()` is pattern-based and returns an ordered list of retrievers, for example:

- `vector`
- `keyword`
- `structured`

### Stage 7: Parallel Retrieval

Files:

- `services/ai/infrastructure/rag/retrievers/vector_retriever.py`
- `services/ai/infrastructure/rag/retrievers/keyword_retriever.py`
- `services/ai/infrastructure/rag/retrievers/structured_retriever.py`

Retrievers run in parallel and return `RetrievedChunk` objects.

### Stage 8: Reranking And Formatting

Files:

- `services/ai/infrastructure/rag/reranker.py`
- `services/ai/services/rag_service.py`

The AI service:

- merges retriever results with Reciprocal Rank Fusion
- boosts project-specific matches when `project_id` is present
- formats the final retrieved context string

## Project Context Builder

Primary entry point:

- `services/ai/services/ai_chat_service.py` -> `_build_project_context()`

The project-context builder loads:

- project metadata
- objectives and sub-objectives
- tasks with assignees, owners, dependencies, and timeline state
- cost summary and breakdown
- deliverables, forecasts, and risks
- team members and skills
- recent commits and analyses

Current context budgets are character-based:

- max context chars: `32000`
- tier 1 budget: `16000`
- tier 2 budget: `12000`
- tier 3 budget: `4000`

## TAOR Agent Loop

Primary entry point:

- `services/ai/infrastructure/rag/agent_loop.py` -> `run_agent_loop()`

TAOR means:

- Think
- Act
- Observe
- Retry

### Loop Behavior

Each iteration can:

- inject a `<think>` scratchpad block
- parse tool calls from native provider output or `<tool_calls>...</tool_calls>` JSON
- execute tools via the registry
- inject tool results back into the conversation
- trigger a focused RAG requery when confidence is low

Current loop controls:

- `MAX_ITERATIONS = 7`
- stop threshold: confidence `>= 4`
- requery threshold: confidence `<= 2`
- requery begins after iteration `2`

If the maximum is reached, the service requests a final summary call without more tool execution.

### Loop Result

`AgentLoopResult` contains:

- `final_text: str`
- `all_tool_results: list[dict]`
- `updated_entities: list[str]`
- `iterations: int`
- `low_confidence: bool`

## Tool Call Parsing

File:

- `services/ai/infrastructure/llm/tool_parser.py`

Supported parsing modes:

- OpenAI native tool calls: `parse_openai_tool_calls()`
- Anthropic native tool calls: `parse_anthropic_tool_calls()`
- Prompt-based tool calls: `parse_xml_tool_calls()`

Prompt-based mode expects a JSON array inside:

```xml
<tool_calls>
[{"tool": "create_project", "input": {"title": "Example"}}]
</tool_calls>
```

## Tool Registry Injection

Files:

- `services/ai/infrastructure/tools/registry.py`
- `services/ai/infrastructure/tools/base.py`

Provider behavior:

- OpenAI and Anthropic use native schema serialization
- Ollama and Kimi receive a prompt-text tool section with `<tool_calls>` usage instructions

## LLM Adapter Layer

Files:

- `services/ai/infrastructure/llm/base.py`
- `services/ai/infrastructure/llm/__init__.py`
- provider adapters under `services/ai/infrastructure/llm/`

Base adapter contract:

- `call(model_id, prompt, **kwargs) -> LLMResponse`
- `call_json(model_id, prompt, **kwargs) -> dict | None`
- `call_with_tools(model_id, messages, tools=None, **kwargs) -> LLMResponse`
- `health_check(**kwargs) -> bool`

Fallback helpers:

- `call_with_fallback()`
- `call_with_fallback_tools()`

Native tool providers:

- `openai`
- `anthropic`

## Output Guardrail And Audit

Files:

- `services/ai/infrastructure/rag/guardrails.py`
- `services/ai/repositories/notification_repo.py`

`sanitize_output()` scrubs sensitive patterns before the response is returned.

Project chat writes an `audit_log` entry with:

- `action = "ai_chat"`
- `operation = "chat"`
- `project_id`
- truncated user message and AI response
- `tool_calls_count`
- `agent_iterations`

Workspace chat uses `operation = "workspace_chat"` with the same iteration and tool-count metadata.

## Related Files

- `services/ai/main.py`
- `services/ai/routers/v1/ai_chat.py`
- `services/ai/routers/v1/ai.py`
- `services/ai/routers/v1/rag.py`
- `services/ai/routers/internal.py`
- `services/ai/services/ai_chat_service.py`
- `services/ai/services/rag_service.py`
- `services/ai/services/ai_analyzer.py`
- `services/ai/services/document_indexer.py`
- `services/ai/infrastructure/rag/agent_loop.py`
- `services/ai/infrastructure/tools/registry.py`

## Known Architectural Notes

- The AI service shares the same database and ORM layer as the other services.
- Tool execution is a real write path against shared tables, not a simulated plan-only layer.
- Gateway parity matters because both native and nginx gateways need to forward `/internal/analyze-commits` correctly.
