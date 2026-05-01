# Graph API, GraphRAG, and Graph Database Feasibility Assessment

**Last updated:** 2026-04-21  
**Status:** Complete feasibility analysis  
**Recommendation:** Hybrid GraphRAG as next phase; Graph API as optional orchestration enhancement; standalone graph database deferred

---

## Executive Summary

### Graph API
**Feasibility:** ⭐⭐⭐⭐ (High) | **Effort:** Medium | **Impact:** Low-to-Medium

A graph-based orchestration layer for conversation/tool pipelines is **technically feasible** with minimal API contract changes. Current TAOR loop is already implicit DAG (Directed Acyclic Graph) logic. Adopting explicit graph orchestration would make agent loops more transparent and composable, but provides limited immediate benefit since the current implementation already handles iteration order well. **Recommendation:** Adopt if you need multi-agent coordination or recursive sub-graphs; defer for single-agent scenarios.

### GraphRAG
**Feasibility:** ⭐⭐⭐⭐ (High) | **Effort:** Medium | **Impact:** High

Graph-native retrieval is **highly feasible** and offers substantial business value. OPPM data (objectives, tasks, dependencies, costs, risks) is inherently relational and graph-like. Entity extraction (projects, tasks, objectives, people, costs) and relationship indexing (task dependencies, ownership chains, cost allocations) would improve retrieval quality over vector/keyword alone. **Recommendation:** Pilot hybrid approach first (GraphRAG as additional retriever alongside current vector/keyword), then evaluate replacement within 2-3 sprints.

### Graph Database
**Feasibility:** ⭐⭐⭐ (Medium) | **Effort:** High | **Impact:** Medium

Multi-tenant graph database adoption is **feasible but costly**. Neo4j and TigerGraph both support workspace isolation, but dual-write/dual-read migration is risky and operationally complex. Benefits are primarily in query expressiveness and relationship traversal efficiency, not fundamental capability gaps. **Recommendation:** Defer graph database as primary store. Use dual-write to Neo4j for relationship queries while keeping PostgreSQL as source-of-truth. Revisit after GraphRAG pilot.

---

## Current AI Architecture Overview

### Chat Request/Response Contract

**Entry points:**
- `POST /api/v1/workspaces/{workspace_id}/projects/{project_id}/ai/chat` — project-scoped
- `POST /api/v1/workspaces/{workspace_id}/ai/chat` — workspace-scoped

**Request (`ChatRequest`):**
```python
{
  "messages": [{"role": "user|assistant", "content": str}],
  "model_id": str | None,  # Optional; falls back to workspace config or Ollama
}
```

**Response (`ChatResponse`):**
```python
{
  "message": str,           # Final LLM response
  "tool_calls": [
    {
      "tool_name": str,
      "tool_input": dict,
      "result": str,
      "success": bool,
    }
  ],
  "updated_entities": [str],  # e.g., ["tasks", "projects", "oppm_objectives"]
  "iterations": int,          # Number of TAOR loops executed
  "low_confidence": bool,     # LLM ended below confidence threshold 4
}
```

**Streaming variant** (`/ai/chat/stream`):
- Server-Sent Events with `event: tool_call` and `event: message` frames

### RAG Pipeline

**Multi-stage retrieval flow:**

1. **Input Guardrail** — block injection attacks, enforce 4000-char limit
2. **Conversation Memory** — load recent audit_log entries (trimmed context)
3. **Query Rewriting** — LLM expands vague queries for better recall
4. **Embedding** — generate query vector (for cache + retrieval)
5. **Semantic Cache Lookup** — Redis with cosine similarity ≥ 0.92, TTL 300s
6. **Query Classification** — pattern-based selection of retrievers (vector | keyword | structured)
7. **Parallel Retrieval** — run selected retrievers concurrently
   - **Vector Retriever** — embedding similarity search (pgvector)
   - **Keyword Retriever** — BM25-style full-text search
   - **Structured Retriever** — entity/relationship queries (tasks, objectives, costs)
8. **Reranking** — Reciprocal Rank Fusion (RRF) merge + project-specific boost
9. **Output Formatting** — context string + sources metadata
10. **Cache Storage** — store (embedding, context, workspace_id, project_id) tuple

**Return type:** `RAGResult(context, sources, memory_context, chunks)`

### Tool Orchestration (TAOR Loop)

**5 tool categories (24 total tools):**

| Category | Tools | Purpose |
|----------|-------|---------|
| `oppm` | create_objective, update_objective, delete_objective, set_timeline_status, bulk_set_timeline | Objective/timeline management |
| `task` | create_task, update_task, delete_task, assign_task, set_task_dependency | Task CRUD and dependencies |
| `cost` | update_project_costs, create_risk, update_risk, create_deliverable, update_project_metadata | Cost/risk/deliverable management |
| `read` | get_project_summary, get_task_details, search_tasks, get_risk_status, get_cost_breakdown, get_team_workload | Read-only queries |
| `project` | (3 specialized tools, see TOOL-REGISTRY-REFERENCE.md) | Project-specific operations |

**TAOR Loop (`run_agent_loop` in `agent_loop.py`):**

```
Iteration N (max 7):
  1. THINK
     - LLM outputs <think>block with what_i_know, what_i_need, confidence (1-5), next_action
     - Confidence ≥ 4 + no tool calls → early stop, return answer
  
  2. ACT
     - Parse tool calls from LLM response
     - Dedup: skip identical tool calls from previous iterations
     - Execute tools in parallel (batch-safe via registry)
     - Collect results
  
  3. OBSERVE
     - Inject tool results back to LLM (truncated to 1000 chars per tool)
     - Format as structured observation + extracted reasoning
  
  4. RETRY
     - If confidence ≤ 2 and iteration ≥ 2: trigger RAG re-query with gap phrase
     - Update context with new retrieval
     - Continue to next iteration
  
Termination:
  - Confidence ≥ 4 and no tool calls → answer
  - Iteration ≥ 7 (max_iterations) → wrap-up call
  - Error or timeout → return partial result with low_confidence=true
```

**State management:**
- Conversation history passed as message array (stateless per request)
- Tool execution context: (session, workspace_id, project_id, user_id)
- Results accumulated in `all_tool_results` list
- Updated entities tracked in `updated_entities` list

### Data Flow

```
User Message
  ↓
Input Guardrail (check_input)
  ↓
Conversation Memory Load (load_memory from audit_log)
  ↓
Query Rewriting (rewrite_query via LLM)
  ↓
Embedding Generation (generate_embedding)
  ↓
Semantic Cache Lookup (Redis)
  ├─ MISS →
  │   ↓
  │   Query Classification (classify_query)
  │   ↓
  │   Parallel Retrievers (vector | keyword | structured)
  │   ↓
  │   RRF Reranking + Project Boost
  │   ↓
  │   Format Context
  │   ↓
  │   Cache Storage (Redis)
  │
  └─ HIT → Use cached context

Context → System Prompt Construction
  ↓
TAOR Agent Loop (up to 7 iterations)
  ├─ Think (confidence + next_action)
  ├─ Act (tool execution)
  ├─ Observe (result injection)
  └─ Retry (RAG re-query if low confidence)
  
Final Response → Output Guardrail (sanitize_output)
  ↓
Audit Log Entry (AuditRepository)
  ↓
Response to Client (ChatResponse)
```

**State bottlenecks / pain points:**
- Conversation history grows with each message; truncated to recent entries
- Tool results truncated to 1000 chars; may lose detail if tools return large data
- Semantic cache is coarse (workspace + project level); no per-query memory
- No explicit conversation state machine; relies on LLM to track context

---

## Graph API Assessment

### What Problem Does It Solve?

**Current state:**
- TAOR loop is linear iteration with implicit DAG logic
- Tool calls are unordered within each iteration (parallel execution)
- Dependencies between iterations are implicit in observation injection

**Limitations:**
- No explicit orchestration for multi-agent scenarios (e.g., run tool A, then conditionally run tool B or C)
- No built-in support for recursive sub-agents
- Tool execution order is implicit; hard to visualize or optimize

**Graph API would:**
- Represent orchestration as explicit DAG (nodes = agents/tools, edges = data flow)
- Support conditional branches (if confidence < 2, query RAG; else answer)
- Enable multi-agent collaboration (agent A runs, feeds results to agent B)
- Improve auditability and visualization

### API Contract Compatibility

**Current chat endpoint:**
```python
POST /api/v1/workspaces/{ws}/projects/{project}/ai/chat
{
  "messages": [...],
  "model_id": str | None,
}
→ ChatResponse { message, tool_calls, updated_entities, iterations, low_confidence }
```

**Proposed Graph API endpoint (additive, not breaking):**
```python
POST /api/v1/workspaces/{ws}/projects/{project}/ai/chat/graph
{
  "messages": [...],
  "model_id": str | None,
  "graph_config": {
    "max_iterations": 7,
    "confidence_threshold": 4,
    "retrieval_strategy": "vector|hybrid|graphrag",  # Optional: specify retrievers
  }
}
→ ChatResponse { message, tool_calls, updated_entities, iterations, low_confidence, orchestration_trace }
```

**Changes required:**
- Define graph schema (nodes, edges, execution rules)
- Create orchestration executor separate from TAOR loop
- Add `orchestration_trace` to response (optional debugging)
- Backward compatible: existing `/ai/chat` endpoint unchanged

### Refactoring Required

**Low-impact changes:**
1. Extract TAOR loop iterations into graph nodes
   - Current file: `services/intelligence/infrastructure/rag/agent_loop.py`
   - Create: `services/intelligence/infrastructure/orchestration/graph_engine.py`
   - Each iteration becomes a node with input (previous message) and output (next message + results)

2. Define orchestration language (YAML or Python DSL)
   ```yaml
   nodes:
     - id: think
       type: llm_reason
       inputs: [conversation_history, rag_context]
       outputs: [think_block, next_action]
     
     - id: act
       type: tool_batch
       inputs: [tool_calls]
       outputs: [tool_results]
     
     - id: decide_retry
       type: conditional
       condition: confidence <= 2 && iteration >= 2
       true_branch: requery
       false_branch: observe
     
     - id: requery
       type: rag_pipeline
       inputs: [gap_phrase]
       outputs: [new_context]
   
   edges:
     - from: think
       to: act
     - from: act
       to: decide_retry
     - from: decide_retry.requery
       to: observe
   ```

3. Implement graph executor
   - Traverse DAG in topological order
   - Handle conditional branching
   - Batch independent nodes
   - Track execution trace

**Moderate-impact changes:**
1. Update tool registry to support graph-aware execution
2. Extend LLM call wrapper to accept graph context
3. Add orchestration tracing and visualization

**No changes:**
- Chat endpoint request/response (backward compatible)
- Tool implementations (no tool-level changes)
- RAG pipeline (reusable by graph nodes)
- Database schema or audit logging

### Effort Estimate

**T-shirt size:** **Medium (2-3 weeks)**

- Graph engine skeleton: 1 week (design + implementation + testing)
- Integration with existing agent loop: 3-4 days (ensure backward compat)
- Orchestration tracing and visualization: 2-3 days
- Documentation and examples: 2 days

**Risk factors:**
- **Low:** Graph abstraction adds complexity; requires careful API design to avoid confusion
- **Medium:** Backward compatibility testing needed to ensure existing chat flow unaffected
- **Low:** Tool execution order may differ (parallelization); needs validation

### Pilot Scope

**Day 1 pilot:** Multi-agent conversation scenario
- **Use case:** "Summarize all tasks for Q2 and suggest an optimized timeline"
  - Agent 1: Fetch tasks (via `search_tasks`, `get_project_summary`)
  - Agent 2: Analyze dependencies (via `set_task_dependency`, `get_task_details`)
  - Agent 3: Synthesize and suggest timeline (via `bulk_set_timeline`)
- **Success criteria:**
  - Graph orchestration completes in same time as current TAOR loop
  - Results are identical or better
  - Trace log shows explicit agent handoff

**After pilot:**
- Conditional branching (e.g., if no risks detected, skip risk creation)
- Nested sub-agents (e.g., cost agent spawns sub-agent for each category)

---

## GraphRAG Assessment

### Current Retrieval vs. Entity/Relationship Reasoning

**Current retrieval pipeline:**

| Retriever | Input | Output | Best for |
|-----------|-------|--------|----------|
| Vector | embedding query | top-k similar chunks (pgvector) | Semantic similarity (e.g., "What are the project goals?") |
| Keyword | full-text query | ranked chunks (PostgreSQL FTS) | Exact term matching (e.g., "Find tasks with status='blocked'") |
| Structured | SQL-like filters | entities + fields | Faceted queries (e.g., "high-priority tasks for Q2") |

**Limitations:**
- Vector retrieval misses dependencies (e.g., "What is task X's blocker?")
- Keyword retrieval is term-based; doesn't understand relationships
- Structured retriever requires pre-defined filters; not flexible for ad-hoc entity relationships
- No built-in traversal of task dependencies, ownership chains, or cost breakdowns

**GraphRAG would add:**

| Retriever | Input | Output | Best for |
|-----------|-------|--------|----------|
| Graph Entity | entity name/type | connected entities + paths | Relationship reasoning (e.g., "Who is assigned to tasks blocking X?") |
| Graph Path | source entity → target entity | shortest/important paths | Dependency chains (e.g., "What are the critical path tasks?") |
| Graph Expansion | query entity | related entities (1-2 hops) | Context enrichment (e.g., "Get all tasks + their owners + cost allocations") |

### Entity Extraction and Indexing Model

**Proposed entities in OPPM domain:**

```
Person
  ├─ member_id, name, email, role, skills[]
  └─ relationships: assigned_to(Task), owns(Objective), manages(Project)

Project
  ├─ project_id, title, status, priority, deadline, budget
  └─ relationships: has_objective(Objective), has_task(Task), has_cost(Cost), has_risk(Risk)

Objective
  ├─ objective_id, title, owner_id, sort_order
  └─ relationships: parent_objective(Objective), has_task(Task), has_cost(Cost)

Task
  ├─ task_id, title, status, priority, due_date, estimated_hours
  └─ relationships: 
      assigned_to(Person), owner(Person), parent_task(Task),
      depends_on(Task), has_cost(Cost), in_objective(Objective)

Cost
  ├─ cost_id, category, planned_amount, actual_amount, period
  └─ relationships: for_project(Project), for_objective(Objective), for_task(Task)

Risk
  ├─ risk_id, description, rag (Red/Amber/Green), item_number
  └─ relationships: for_project(Project)

Deliverable
  ├─ deliverable_id, description, item_number
  └─ relationships: for_project(Project)

Timeline
  ├─ timeline_id, task_id, week_start, status (Planned/InProgress/Complete/AtRisk)
  └─ relationships: for_task(Task), for_project(Project)
```

**Relationships (edges):**
- `assigned_to` (Task → Person) — task assignment
- `owner` (Task → Person, Objective → Person) — ownership chain
- `depends_on` (Task → Task) — task dependency
- `parent_task` (Task → Task) — task hierarchy
- `parent_objective` (Objective → Objective) — objective hierarchy
- `has_task` (Project → Task, Objective → Task) — scope
- `has_cost` (Project → Cost, Objective → Cost, Task → Cost) — cost allocation
- `for_project` (Cost → Project, Risk → Project, Timeline → Project)

**Indexing strategy:**

1. **On project/task creation/update:** Extract and index entities
   - Trigger: POST/PUT to `/api/v1/workspaces/.../projects` or `/tasks`
   - Handler: `document_indexer.py` enhanced with `extract_graph_entities()`
   - Storage: Dual-write to PostgreSQL (existing) + graph index (Redis or Neo4j)

2. **On dependency/assignment changes:** Update relationships
   - Trigger: Tool execution (assign_task, set_task_dependency, etc.)
   - Handler: Tool result callback updates graph index

3. **Periodic re-indexing:** Full workspace re-index (nightly)
   - Existing endpoint: `POST /api/v1/workspaces/.../ai/reindex`
   - Enhanced to include graph index rebuild

**Index data structure (Redis hashes/sets for MVP):**
```
# Entity index
entity:{entity_type}:{entity_id} = {json: name, title, owner, status, ...}
entities:{entity_type} = set of entity_ids (for discovery)

# Relationship index
rel:{rel_type}:{from_id}:{to_id} = {timestamp, confidence_score}
rels:outbound:{from_id} = set of (rel_type:to_id) (for expansion queries)
rels:inbound:{to_id} = set of (rel_type:from_id) (for reverse traversal)

# Path index (pre-computed for common paths)
paths:{project_id}:critical_path = [task1, task2, task3]
paths:{project_id}:owners:{person_id} = [task1, task2] (owned/assigned)
```

### Query Planning and Entity Resolution

**Query classification enhancement (current: `classify_query()`):**

```python
def classify_query_with_graph(query: str, project_context: dict) -> dict:
    """
    Returns structured query plan with retriever recommendations.
    
    Example input: "Who is blocked on the database redesign task?"
    
    Returns:
    {
        "intent": "find_blocked_person",
        "entities": [
            {"type": "task", "name": "database redesign", "resolution": "search_tasks"},
            {"type": "person", "name": None, "resolution": "graph_traverse"},
        ],
        "retrievers": ["structured", "graph_path"],  # Ordered by relevance
        "graph_query": {
            "start": "task",
            "pattern": "task <-depends_on- Task <-assigned_to- Person",
            "filters": [{"entity_type": "task", "field": "title", "contains": "database redesign"}],
        },
        "confidence": 0.9,
    }
    """
```

**Entity resolution (new service: `entity_resolver.py`):**

```python
async def resolve_entities(query: str, workspace_id: str, project_id: str) -> dict[str, str]:
    """
    Fuzzy-match entity names in query to actual IDs in the project.
    
    Example:
      query = "Assign the API task to Alice"
      returns = {
        "task_id": "task-123",  # Matched "API task" to highest-scoring task
        "person_id": "person-456",  # Matched "Alice" to person
      }
    """
    # 1. NER on query to identify entity types (task, person, objective, etc.)
    # 2. For each entity, search index (BM25) + embedding similarity
    # 3. Return top match (or ask user to clarify if ambiguous)
```

### Hybrid vs. Replacement Paths

**Option A: Hybrid (Recommended for MVP)**
- Keep vector + keyword + structured retrievers as-is
- Add graph entity/path retrievers as new branch
- RRF merge all 4-5 retrievers
- Parallel execution (no latency impact)
- Easier rollback if graph index becomes inconsistent

**Cost:**
- ~2-3 weeks to implement graph entity extraction + indexers
- +1-2ms latency per chat (parallel retrieval, network round-trip to graph store)
- +5-10% Redis/storage overhead for graph index

**Option B: GraphRAG Replacement**
- Remove vector/keyword/structured retrievers
- Replace with pure graph entity + path queries
- Requires embedding model only for query classification (not retrieval)
- Simpler retrieval pipeline
- Riskier: single point of failure if graph index is stale

**Cost:**
- ~4-5 weeks (includes fallback logic, testing)
- -2-3ms latency (fewer retrievers)
- Requires comprehensive entity extraction to avoid missing entities

**Recommendation:** Start with hybrid (Option A). After 2-3 sprints of monitoring quality metrics, decide whether to replace vector/keyword or keep both.

### Schema/Index Changes Needed

**PostgreSQL schema changes (minimal):**
- Add `document_vectors` table (already exists)
- Add `graph_entity` table (new) for entity metadata
  ```sql
  CREATE TABLE graph_entity (
      id UUID PRIMARY KEY,
      workspace_id UUID NOT NULL,
      entity_type VARCHAR NOT NULL,  -- Person, Task, Objective, etc.
      entity_ref_id UUID,  -- FK to actual entity (task_id, person_id, etc.)
      data JSONB,  -- Denormalized entity data for quick lookup
      indexed_at TIMESTAMP,
      FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
      UNIQUE (workspace_id, entity_type, entity_ref_id)
  );
  
  CREATE TABLE graph_relationship (
      id UUID PRIMARY KEY,
      workspace_id UUID NOT NULL,
      from_entity_id UUID NOT NULL,
      to_entity_id UUID NOT NULL,
      rel_type VARCHAR NOT NULL,  -- assigned_to, depends_on, owns, etc.
      metadata JSONB,
      indexed_at TIMESTAMP,
      FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
      FOREIGN KEY (from_entity_id) REFERENCES graph_entity(id) ON DELETE CASCADE,
      FOREIGN KEY (to_entity_id) REFERENCES graph_entity(id) ON DELETE CASCADE,
      UNIQUE (workspace_id, from_entity_id, to_entity_id, rel_type)
  );
  
  CREATE INDEX ON graph_relationship(workspace_id, from_entity_id);
  CREATE INDEX ON graph_relationship(workspace_id, to_entity_id);
  CREATE INDEX ON graph_relationship(workspace_id, rel_type);
  ```

**Redis index (for MVP; later migrate to dedicated graph DB):**
- `entity:{type}:{id}` → JSON
- `rels:outbound:{id}` → set of (rel_type:target_id)
- `rels:inbound:{id}` → set of (rel_type:source_id)

**Query changes:**
- New retriever: `services/intelligence/infrastructure/rag/retrievers/graph_retriever.py`
- Entity resolution: `services/intelligence/domains/analysis/entity_resolver.py`
- Graph query builder: `services/intelligence/infrastructure/rag/graph_query_builder.py`

### Effort Estimate

**T-shirt size:** **Medium-to-Large (3-4 weeks)**

- Entity extraction + indexing: 1 week
- Graph retrievers (entity + path): 1 week
- Entity resolution and query planning: 4-5 days
- RRF fusion with graph results: 2-3 days
- Testing + monitoring: 3-4 days

**Risk factors:**
- **Medium:** Entity extraction must be accurate; garbage in = garbage out for graph queries
- **Medium:** Graph index consistency with PostgreSQL (dual-write consistency)
- **Low:** Performance impact if graph store is slow (mitigate with Redis caching + batching)

### Pilot Scope

**Suggested pilot (Week 1-2):**

**Phase 1: Entity Extraction (MVP)**
- Extract tasks, objectives, people, costs from a single project
- Build Redis index (simple key-value store)
- Test entity resolution on common entities (task names, people)

**Phase 2: Graph Query (Week 2-3)**
- Implement graph entity retriever (return connected entities)
- Implement graph path retriever (find dependency chains)
- Integrate with RRF merger

**Phase 3: Validation (Week 3-4)**
- Run A/B test on live workspace
- Compare hybrid RAG (vector + keyword + graph) vs. current RAG (vector + keyword + structured)
- Metrics: retrieval relevance (human-rated), latency, cache hit rate

**Success criteria:**
- Graph entity extraction accuracy ≥ 95%
- Hybrid retrieval latency + 1-2ms (acceptable)
- At least 1 query type shows 10%+ improvement in relevance
- No regression in existing chat quality

---

## Graph Database Assessment

### Multi-Tenant Design in Graph Databases

**Neo4j multi-tenancy patterns:**

1. **Separate graphs per workspace** (simplest, most isolated)
   - Each workspace gets its own Neo4j instance or graph
   - Pros: Complete isolation, easy compliance, simple queries
   - Cons: Operational overhead (manage N instances), high storage/memory cost
   - Cost: ~$100-500/month per workspace for production Neo4j

2. **Shared graph with label-based isolation** (standard)
   - Single Neo4j instance; all entities labeled with workspace_id
   - Cypher queries filter by workspace_id automatically
   - Pros: Cost-efficient, shared resources
   - Cons: Must enforce workspace isolation in query layer (risk of data leak)
   - Cost: ~$500-2000/month for single instance

3. **Federated querying** (advanced)
   - Multiple Neo4j instances, unified query layer
   - Pros: Scalability, isolation
   - Cons: Complex, not recommended for most scenarios

**Recommendation for OPPM:** Pattern 2 (shared graph with label-based isolation) is operationally simplest. Pattern 1 if data segregation is a regulatory requirement.

### Schema Mapping (Relational → Property Graph)

**PostgreSQL relational schema:**
```sql
-- Current
projects (id, workspace_id, title, status, deadline)
tasks (id, project_id, title, status, due_date)
task_assignees (task_id, user_id)
task_dependencies (task_id, depends_on_task_id)
oppm_objectives (id, project_id, title, owner_id)
project_costs (id, project_id, category, amount)
```

**Neo4j property graph schema:**
```cypher
-- Nodes
(:Workspace {workspace_id, name})
(:Project {id, title, status, deadline})
(:Task {id, title, status, due_date})
(:Objective {id, title})
(:Person {id, name, email})
(:Cost {id, category, amount})

-- Relationships
(Person)-[:ASSIGNED_TO]->(Task)
(Person)-[:OWNS]->(Objective)
(Task)-[:DEPENDS_ON]->(Task)
(Task)-[:IN_OBJECTIVE]->(Objective)
(Task)-[:COSTS]->(Cost)
(Project)-[:HAS_TASK]->(Task)
(Project)-[:HAS_OBJECTIVE]->(Objective)

-- Workspace isolation
(:Workspace {workspace_id})-[:CONTAINS]->(Project)
(:Workspace {workspace_id})-[:CONTAINS]->(Person)
```

**Query examples (Cypher):**

Current (PostgreSQL):
```sql
SELECT t.* FROM tasks t
WHERE t.project_id = ? AND t.status = 'blocked'
ORDER BY t.due_date;
```

Proposed (Neo4j):
```cypher
MATCH (w:Workspace {workspace_id: $ws})-[:CONTAINS]->(p:Project {id: $project})
MATCH (p)-[:HAS_TASK]->(t:Task {status: 'blocked'})
RETURN t ORDER BY t.due_date;
```

**Advantage:** Neo4j query is simpler for multi-hop queries:

PostgreSQL (complex JOIN):
```sql
SELECT DISTINCT t.*, p.name
FROM tasks t
JOIN task_assignees ta ON t.id = ta.task_id
JOIN persons p ON ta.user_id = p.id
JOIN task_dependencies td ON t.id = td.task_id
JOIN tasks blocker ON td.depends_on_task_id = blocker.id
WHERE t.project_id = ? AND blocker.status = 'completed' AND ta.user_id != p.id
ORDER BY t.due_date;
```

Neo4j (single query):
```cypher
MATCH (w:Workspace {workspace_id: $ws})-[:CONTAINS]->(p:Project {id: $project})
MATCH (p)-[:HAS_TASK]->(t:Task)
MATCH (t)-[:DEPENDS_ON]->(blocker:Task {status: 'completed'})
MATCH (t)-[:ASSIGNED_TO]->(person:Person)
WHERE person.id != $current_user_id
RETURN DISTINCT t, person
ORDER BY t.due_date;
```

### Query Performance Considerations

**PostgreSQL (relational, current):**
- Strengths: Fast for pre-defined queries (JOINs), full-text search, aggregations
- Weaknesses: Complex JOINs for deep relationships, recursive CTEs for tree traversal
- Example latency: 10-50ms for multi-hop queries on 100K tasks

**Neo4j (graph, proposed):**
- Strengths: Fast for relationship traversal (1-hop, 2-hop queries), pattern matching
- Weaknesses: Aggregations slower than SQL, full-text search requires plugins
- Example latency: 5-20ms for 2-3 hop queries (better than PostgreSQL if index is warm)

**Hybrid approach (recommended):**
- Keep PostgreSQL as primary transactional store
- Use Neo4j for relationship queries (dual-write on mutations)
- Cache frequent queries (Redis)
- Fallback to PostgreSQL for aggregations/full-text search

**Query latency estimates:**

| Query Type | PostgreSQL | Neo4j (cold) | Neo4j (warm) |
|------------|-----------|--------------|--------------|
| Find tasks in project | 5-10ms | 20-30ms | 5-10ms |
| Find blocked tasks by person | 20-50ms | 50-100ms | 10-20ms |
| Find critical path (BFS) | 100-300ms | 20-50ms | 10-20ms |
| Find all dependencies (DFS) | 300-1000ms | 50-100ms | 20-30ms |
| Aggregate costs by objective | 10-30ms | 100-200ms | 50-100ms |

**Recommendation:** Use Neo4j for relationship queries (path-finding, dependency chains); PostgreSQL for transactional writes and aggregations.

### Dual-Write/Dual-Read Migration Strategy

**Phase 1: Dual-Write (No UI change)**
- All writes to PostgreSQL go through write handler
- Write handler also updates Neo4j (async, fire-and-forget)
- Reads from PostgreSQL only (no Neo4j integration)
- Risk: Neo4j gets out of sync if writes fail

**Implementation:**
```python
# services/workspace/domains/project/service.py (example)
async def create_task(session, data) -> Task:
    # 1. Write to PostgreSQL (primary)
    task = Task(...)
    session.add(task)
    await session.commit()
    
    # 2. Async write to Neo4j (secondary)
    asyncio.create_task(
        neo4j_client.execute(
            "CREATE (t:Task {id: $id, title: $title}) RETURN t",
            {"id": task.id, "title": task.title}
        )
    )
    
    return task
```

**Phase 2: Validation (1-2 weeks)**
- Periodic consistency check: compare PostgreSQL and Neo4j record counts
- Metrics: Neo4j lag (staleness), sync success rate
- If lag > 5 minutes or sync rate < 99%, trigger re-index

**Phase 3: Dual-Read (Gradual activation)**
- Add feature flag: `use_neo4j_for_relationship_queries` (default: off)
- Enable for specific query types (e.g., find critical path)
- A/B test on 10% of workspaces → 50% → 100%
- Fallback to PostgreSQL if Neo4j latency > 100ms

**Implementation:**
```python
# services/intelligence/infrastructure/rag/retrievers/graph_retriever.py
async def retrieve(self, query, workspace_id, **filters):
    if not feature_flag("use_neo4j_for_relationship_queries"):
        return []  # Fallback to PostgreSQL queries
    
    try:
        result = await neo4j_client.execute(cypher_query, params)
        return result
    except Exception as e:
        logger.warning("Neo4j query failed, falling back: %s", e)
        return await postgresql_fallback_query(...)
```

**Phase 4: Cutover (if validated)**
- Promote Neo4j reads to primary for relationship queries
- Keep PostgreSQL as authoritative source for transactions
- Monitor for 2-4 weeks before fully deprecating fallback

### Operational Overhead

**Costs:**

| Scenario | PostgreSQL only | PostgreSQL + Neo4j |
|----------|-----------------|-------------------|
| Development | Free (Postgres Docker) | +$0 (Neo4j Docker) |
| Staging | ~$50/month (RDS) | +$100/month (Neo4j Aura) |
| Production (1 workspace) | ~$100-200/month (RDS) | +$300-500/month (Neo4j Aura) |
| Production (10 workspaces) | ~$300-500/month | +$1000-2000/month (shared instance or per-workspace) |

**Operations:**
- Backup strategy for Neo4j (weekly snapshots → S3)
- Replication (Neo4j Causal Cluster for HA)
- Monitoring (Neo4j metrics, query latency, memory usage)
- Maintenance windows (Neo4j version upgrades, schema migrations)

**Team training:** Developers must learn Cypher query language and graph query patterns.

### Effort Estimate

**T-shirt size:** **Large (4-6 weeks)**

- Neo4j setup + Docker + schema design: 3-4 days
- Dual-write implementation: 1 week
- Validation and consistency checking: 1 week
- Fallback handling and feature flags: 3-4 days
- Testing + monitoring: 1 week

**Total:** 4-6 weeks if done alongside other work; ~3-4 weeks if dedicated team.

### Risk Factors

- **High:** Data consistency between PostgreSQL and Neo4j; any sync failure creates data integrity risk
- **High:** Operational complexity (backup, replication, monitoring for dual systems)
- **Medium:** Cardinality explosion; graph could grow to millions of nodes if not pruned (e.g., archive old tasks)
- **Medium:** Query performance benefits only realized for specific query patterns (not all queries benefit)

---

## Recommendation Matrix

### Summary Table

| Approach | Feasibility | Effort | Business Impact | Recommendation |
|----------|-------------|--------|-----------------|-----------------|
| Graph API | ⭐⭐⭐⭐ High | Medium | Low-Medium | Consider after MVP |
| GraphRAG (Hybrid) | ⭐⭐⭐⭐ High | Medium-Large | **High** | **Pilot immediately (next sprint)** |
| Graph Database | ⭐⭐⭐ Medium | Large | Medium | Defer; revisit after GraphRAG pilot |

### Recommended Path (12-16 weeks)

**Weeks 1-4: GraphRAG Hybrid MVP**
- Week 1: Entity extraction + Redis indexing
- Week 2: Graph entity/path retrievers
- Week 3: Entity resolution + RRF fusion
- Week 4: Validation, A/B testing, monitoring

**Decision Point (Week 4):**
- If relevance improves ≥ 10% and no regressions → proceed to Phase 2
- Else → debug and extend pilot by 1 week, or defer GraphRAG

**Weeks 5-8: GraphRAG Full Rollout (if validated)**
- Scale entity extraction to all workspaces
- Migrate from Redis to dedicated Neo4j instance (optional)
- Add graph-specific features (critical path finder, dependency analyzer)

**Weeks 9-12: Graph API Orchestration (optional, low priority)**
- Only if multi-agent scenarios emerge or Graph API demand is high
- Lower priority than GraphRAG; can be deferred

**Weeks 13-16: Graph Database Migration (Phase 2, if warranted)**
- Evaluate if Neo4j would provide sufficient performance gains
- Design dual-write strategy
- Pilot with one workspace

**Not Recommended for First Year:**
- Replacing PostgreSQL entirely with Neo4j
- Standalone Graph API without GraphRAG (limited benefit)
- Graph database for primary storage (operational risk too high)

---

## Appendix: Detailed Data Flow Diagrams

### Current RAG Pipeline (Text)
```
User Query
  → Input Guardrail
  → Conversation Memory Load (audit_log)
  → Query Rewriting (LLM)
  → Embedding (model)
  → Semantic Cache Lookup (Redis)
      MISS →
      → Query Classification (pattern)
      → Parallel Retrievers:
          • Vector (pgvector)
          • Keyword (PostgreSQL FTS)
          • Structured (SQL filters)
      → RRF Merge
      → Project Boost
      → Format Results
      → Cache Store (Redis)
      ←
  → Final Context + Sources
```

### Proposed GraphRAG Hybrid Pipeline (Text)
```
User Query (same as above)
  → Input Guardrail
  → Conversation Memory Load (audit_log)
  → Query Rewriting (LLM)
  → Embedding (model)
  → Semantic Cache Lookup (Redis)
      MISS →
      → Query Classification (pattern + semantic)
      → Parallel Retrievers:
          • Vector (pgvector) ← current
          • Keyword (PostgreSQL FTS) ← current
          • Structured (SQL filters) ← current
          • Graph Entity (Redis/Neo4j) ← NEW
          • Graph Path (Redis/Neo4j) ← NEW
      → RRF Merge (now 5-way fusion)
      → Project Boost
      → Format Results
      → Cache Store (Redis)
      ←
  → Final Context + Sources (enriched with entity relationships)
```

### Proposed Graph API Orchestration (Text)
```
User Message
  → Graph Engine
      Node: Think
        Input: conversation_history, rag_context
        Action: LLM think block
        Output: what_i_know, what_i_need, confidence, next_action
      
      Decision: confidence >= 4 && no tool calls?
        YES → Node: Final Answer
        NO →
      
      Node: Act
        Input: tool_calls
        Action: Tool execution (parallel batch)
        Output: tool_results
      
      Node: Decide Retry
        Condition: confidence <= 2 && iteration >= 2?
        YES → Node: Requery (call RAG pipeline)
        NO → Node: Observe
      
      Node: Observe
        Input: tool_results, previous_messages
        Action: Inject observation back to LLM
        Output: updated_messages
      
      Loop: iteration count >= 7?
        NO → back to Node: Think
        YES → Node: Wrap Up (final synthesis)
      
      Node: Final Answer
        Output: message, tool_calls, updated_entities, iterations, low_confidence

  → Output Guardrail
  → Audit Log
  → Response to Client
```

---

## References

- `docs/services/intelligence/README.md` — Intelligence service overview
- `docs/ai/AI-PIPELINE-REFERENCE.md` — Current RAG pipeline details
- `docs/ai/TOOL-REGISTRY-REFERENCE.md` — Tool definitions and contracts
- `docs/DATABASE-SCHEMA.md` — PostgreSQL schema (29 tables, 7 domains)
- `services/intelligence/domains/chat/router.py` — Chat endpoint implementation
- `services/intelligence/domains/chat/service.py` — Chat orchestration logic
- `services/intelligence/domains/rag/service.py` — RAG pipeline implementation
- `services/intelligence/infrastructure/rag/agent_loop.py` — TAOR loop implementation
- `services/intelligence/infrastructure/tools/registry.py` — Tool registry

---

## Next Steps

1. **Review this assessment with stakeholders**
   - Confirm GraphRAG is highest priority
   - Agree on pilot scope and success metrics

2. **Create GraphRAG implementation RFC**
   - Detailed design for entity extraction
   - Entity resolution strategy
   - Redis vs. Neo4j decision for initial index

3. **Prepare pilot project**
   - Select a staging workspace for A/B testing
   - Define relevance evaluation criteria (human scoring, click-through rate, etc.)

4. **Schedule Graph API design review** (lower priority)
   - If multi-agent scenarios emerge in next 2-3 sprints, revisit

5. **Defer graph database evaluation**
   - Revisit after GraphRAG pilot shows performance characteristics
   - Gather ops team feedback on maintenance burden

---

**Document ownership:** Intelligence Service Team  
**Last reviewed:** 2026-04-21  
**Next review:** After GraphRAG pilot (estimated 2026-05-30)
