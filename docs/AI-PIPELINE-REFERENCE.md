# AI Pipeline Reference

Last updated: 2026-04-09

## Purpose

This document describes every component of the AI service pipeline in `services/ai/`.

Use this file when you need to understand, change, or extend any part of the AI chat flow, the RAG retrieval stages, the agentic loop, or the supporting infrastructure (guardrails, cache, rewriting).

## System Diagram

```
User message
    │
    ▼
[Input Guardrail]          guardrails.py — check_input()
    │ safe
    ▼
[Query Rewriting]          query_rewriter.py — rewrite_query()
    │ expanded query
    ▼
[Embed Query]              LLM embed call
    │ embedding vector
    ▼
[Semantic Cache Lookup]    semantic_cache.py — SemanticCache.lookup()
    │ MISS                    └── HIT → skip to system prompt build
    ▼
[Query Classifier]         classifier.py
    │ retriever labels
    ▼
[Parallel Retrieval]       retriever.py
  ├── vector retriever      pgvector cosine search
  ├── keyword retriever     full-text search
  └── structured retriever  direct DB queries
    │ candidate sets
    ▼
[RRF Reranker]             reranker.py — Reciprocal Rank Fusion
    │ merged ranked list
    ▼
[Project Boost]            up-rank results matching project_id
    │ boosted context
    ▼
[Semantic Cache Store]     semantic_cache.py — SemanticCache.store()
    │ context string
    ▼
[Build System Prompt]      ai_chat_service.py
  ├── project context       _build_project_context() — tiered windowing
  ├── RAG context           from retrieval above
  └── tool section          registry.to_*_schema() or registry.to_prompt_text()
    │ populated prompt
    ▼
[Agentic Tool Loop]        agent_loop.py — run_agent_loop()
  ├── LLM call
  ├── Parse tool_calls      tool_parser.py
  ├── Execute tools         registry.execute()
  └── Inject results → repeat (max 5 iterations)
    │ final_text
    ▼
[Output Guardrail]         guardrails.py — sanitize_output()
    │ scrubbed text
    ▼
[Audit Log]                AuditRepository — chat entry + iterations
    │
    ▼
Response: message + tool_calls + updated_entities + iterations
```

---

## Component Reference

### Input Guardrail

**File:** `services/ai/infrastructure/rag/guardrails.py`

**Function:** `check_input(text: str) -> tuple[bool, str]`

Returns `(True, "")` if the message passes, or `(False, reason)` if it is blocked.

Blocked conditions:

| Condition | Detail |
|---|---|
| Message length | > 4000 characters |
| Injection patterns | `<\|token\|>`, `[INST]`, `<<SYS>>`, `ignore previous instructions`, `disregard`, `jailbreak`, `roleplay as`, `pretend you are`, `bypass restrictions` |

If the check fails, the route returns HTTP 400 with the reason string.

---

### Query Rewriting

**File:** `services/ai/infrastructure/rag/query_rewriter.py`

**Function:** `rewrite_query(query: str, models: list, project_title: str = "") -> str`

Skipped if:

- query is longer than 300 characters (already specific enough)
- query is 2 words or fewer (likely a lookup term)
- no models are provided

When used, it calls the LLM with `_REWRITE_PROMPT` to expand the query into multiple related search phrases. Returns the original query on any failure.

---

### Embedding

Performed by `rag_service.py` using the first available LLM model's embed endpoint.

The resulting vector is stored as a 1536-dimensional float array and used for both:
- vector retrieval (cosine similarity against `document_embeddings`)
- semantic cache lookup and storage

---

### Semantic Cache

**File:** `services/ai/infrastructure/rag/semantic_cache.py`

**Class:** `SemanticCache`

| Property | Value |
|---|---|
| Backend | Redis via `shared/redis_client.py` |
| Key prefix | `ai:sem_cache:` |
| Similarity threshold | cosine ≥ 0.92 |
| TTL | 300 seconds |
| Fail-safe | returns `None` if Redis unavailable |

**`lookup(query_embedding, workspace_id) -> str | None`**

Scans all cached keys for the workspace, computes cosine similarity, and returns the stored context string if the best match exceeds the threshold.

**`store(query_embedding, workspace_id, context) -> None`**

Serializes the embedding and context and writes to Redis with the configured TTL.

**Module-level:** `get_semantic_cache()` returns the singleton instance.

---

### Query Classifier

**File:** `services/ai/infrastructure/rag/classifier.py`

Analyzes the rewritten query and decides which retrieval paths to activate. Returns a set of retriever labels (e.g., `{"vector", "keyword", "structured"}`).

---

### Retrieval

**File:** `services/ai/infrastructure/rag/retriever.py`

Three retrievers run in parallel:

| Retriever | Method | Source |
|---|---|---|
| Vector | pgvector cosine search | `document_embeddings` |
| Keyword | Full-text search | `document_embeddings` / indexed text |
| Structured | Direct DB queries | Projects, tasks, OPPM tables via `oppm_repo.py` |

---

### RRF Reranker

**File:** `services/ai/infrastructure/rag/reranker.py`

Merges the three retriever result sets using Reciprocal Rank Fusion (RRF):

$$score_d = \sum_{r \in R} \frac{1}{k + rank_r(d)}$$

where $k = 60$ by default. Higher scores indicate stronger cross-retriever agreement.

Project-specific results receive an additional boost when they match the active `project_id`.

---

### Project Context Builder

**File:** `services/ai/services/ai_chat_service.py` — `_build_project_context()`

Loads the full OPPM data tree for the project and formats it as a structured text block. Uses tiered windowing to stay within model context limits.

| Tier | Token budget | Strategy |
|---|---|---|
| TIER1 | 16 000 | Full data — objectives, tasks, timeline, costs, risks, deliverables, forecasts, team, commits |
| TIER2 | 12 000 | Truncate commits and recent analyses |
| Over TIER2 | 4 000 budget | Keep objectives, tasks, costs, team only |

Data sources (via `oppm_repo.py`):

- `oppm_objectives` with sub-objectives
- `tasks` with assignees, owners, dependencies
- `oppm_timeline_entries`
- `project_costs`
- `oppm_deliverables`
- `oppm_forecasts`
- `oppm_risks`
- `workspace_members` (team)
- `commit_analyses` (recent)

---

### Agentic Tool Loop

**File:** `services/ai/infrastructure/rag/agent_loop.py`

**Function:** `run_agent_loop(messages, models, tools, anthropic_tools, registry, project_id, context) -> AgentLoopResult`

Loop logic:

```
for iteration in range(1, MAX_ITERATIONS + 1):
    response = call_with_fallback_tools(models, messages, tools, anthropic_tools)
    tool_calls = parse from response
    if not tool_calls:
        break
    results = [registry.execute(tc.name, tc.args, project_id) for tc in tool_calls]
    inject results as next user message
    collect updated_entities

if iteration == MAX_ITERATIONS:
    make final summary call without tools
```

**`AgentLoopResult`** fields:

| Field | Type | Description |
|---|---|---|
| `final_text` | `str` | The LLM's final answer |
| `all_tool_results` | `list[ToolResult]` | All tool executions across all iterations |
| `updated_entities` | `dict` | Entity types changed (e.g., `{"tasks": ["uuid1"]}`) |
| `iterations` | `int` | How many loop iterations ran |

---

### Output Guardrail

**File:** `services/ai/infrastructure/rag/guardrails.py`

**Function:** `sanitize_output(text: str) -> str`

Replaces sensitive patterns in the response text with `[REDACTED]`.

Patterns detected:

| Pattern | Regex |
|---|---|
| API keys | `api[_-]?key\s*[:=]\s*\S+` |
| Passwords | `password\s*[:=]\s*\S+` |
| JWT tokens | `ey[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.?[A-Za-z0-9_-]*` |
| ENV vars | `[A-Z_]{4,}\s*=\s*\S+` |
| Secrets | `secret\s*[:=]\s*\S+` |

---

### Audit Log

After every project chat completion, an `audit_log` entry is written with:

- `action`: `"ai_chat"`
- `user_id`: the requester
- `workspace_id`: the workspace
- `metadata`: `{ model, iterations, tool_count, project_id }`

User feedback submissions are logged separately with `action = "ai_feedback"`.

---

## LLM Adapter Layer

**Files:** `services/ai/infrastructure/llm/`

### `LLMAdapter` Base Class

Located in `base.py`. Defines the contract:

- `chat(messages, model_name, **kwargs) -> LLMResponse`
- `embed(text, model_name) -> list[float]`
- `call_with_tools(messages, model_name, tools) -> LLMResponse` — default concatenates tool descriptions into the prompt

`LLMResponse` carries:

| Field | Type |
|---|---|
| `text` | `str` |
| `tool_calls` | `list[dict]` |
| `raw_response` | `dict` |

### Native Tool Providers

`NATIVE_TOOL_PROVIDERS = {"openai", "anthropic"}` (in `__init__.py`).

- **OpenAI** (`openai.py`) — uses `tools` parameter with `tool_choice: "auto"`.
- **Anthropic** (`anthropic.py`) — uses `tools` parameter and extracts the system message separately.

### XML-Prompt Providers

- **Ollama** and **Kimi** fall back to injecting tool descriptions as an XML block in the system prompt.
- `to_prompt_text()` from the registry generates the XML tool list.
- `parse_xml_tool_calls()` in `tool_parser.py` extracts `<tool>` tags from the response.

### Tool Parser

**File:** `services/ai/infrastructure/llm/tool_parser.py`

Three parser functions:

| Function | Use case |
|---|---|
| `parse_xml_tool_calls(text)` | Ollama / Kimi responses |
| `parse_openai_tool_calls(response_data)` | OpenAI native function calling |
| `parse_anthropic_tool_calls(response_data)` | Anthropic native tool use |

All return `(clean_text, list_of_tool_call_dicts)`.

---

## RAG Service Entry Point

**File:** `services/ai/services/rag_service.py`

**Function:** `retrieve_with_rag_pipeline(query, workspace_id, project_id, models, project_title) -> str`

Orchestrates steps 1–10 of the full pipeline. Called by `ai_chat_service.py` before the system prompt is built.

---

## Configuration

| Parameter | Default | Configured In |
|---|---|---|
| Max agentic iterations | 5 | `agent_loop.py` `MAX_ITERATIONS` |
| Semantic cache threshold | 0.92 | `semantic_cache.py` `SIMILARITY_THRESHOLD` |
| Semantic cache TTL | 300 s | `semantic_cache.py` `CACHE_TTL` |
| Query rewrite max length | 300 chars | `query_rewriter.py` |
| Project context TIER1 | 16 000 tokens | `ai_chat_service.py` `_TIER1` |
| Project context TIER2 | 12 000 tokens | `ai_chat_service.py` `_TIER2` |
| Input max length | 4 000 chars | `guardrails.py` |
| Redis key prefix | `ai:sem_cache:` | `semantic_cache.py` |
