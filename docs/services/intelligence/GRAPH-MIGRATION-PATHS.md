# Graph Technology Migration Paths

**Last updated:** 2026-04-21  
**Status:** Decision framework for staged adoption  

---

## Overview

This document provides a decision tree and sequencing framework for adopting Graph API, GraphRAG, and Graph Database technologies in the OPPM AI system.

**TL;DR:**
- **Next 4 weeks:** Pilot GraphRAG hybrid (vector + keyword + graph retrievers)
- **After validation:** Full GraphRAG rollout or investigate further
- **Later (6+ months):** Consider Graph API if multi-agent scenarios appear
- **Defer indefinitely:** Graph database as primary store (high operational cost, limited gains over PostgreSQL)

---

## Decision Tree

```
START: "Should we adopt graph technologies?"
│
├─ QUESTION 1: Are entity relationships the dominant use case?
│  (e.g., "Who is blocked on the critical path?" "What are task dependencies?")
│  │
│  ├─ YES → GraphRAG is high-value, proceed to QUESTION 2
│  │
│  └─ NO → Graph adoption is lower priority
│     └─ Skip to section "Not Recommended at This Time"
│
├─ QUESTION 2: Can we pilot with existing infrastructure (Redis/PostgreSQL)?
│  (Avoid buying new tools/licenses initially)
│  │
│  ├─ YES → Start GraphRAG Hybrid Pilot (Week 1)
│  │        └─ Proceed to "Immediate Path: GraphRAG Hybrid (4 weeks)"
│  │
│  └─ NO → Delay pilot until budget/infrastructure available
│
├─ QUESTION 3: Do we need explicit multi-agent orchestration?
│  (E.g., Agent A runs, then Agent B runs, conditionally Agent C runs)
│  │
│  ├─ YES → Graph API is valuable, queue after GraphRAG
│  │        └─ See "Deferred Path: Graph API Orchestration (Weeks 9-12)"
│  │
│  └─ NO → Graph API is low priority, skip for now
│
├─ QUESTION 4: Is dual-system operational overhead acceptable?
│  (Managing PostgreSQL + Neo4j in production)
│  │
│  ├─ YES → Graph Database may be useful after GraphRAG succeeds
│  │        └─ See "Deferred Path: Graph Database (Weeks 13-16)"
│  │
│  └─ NO → Stay with PostgreSQL + Redis for now
│        └─ Revisit when operational team grows
│
END: Sequencing path determined
```

---

## Immediate Path: GraphRAG Hybrid (Weeks 1-4)

### Goal
Add graph-native entity/relationship retrieval alongside current vector/keyword/structured retrieval. Measure if relevance improves without breaking existing chat behavior.

### Stages

#### Stage 1: Entity Extraction + Indexing (Week 1)

**Deliverables:**
- Entity extraction function in `document_indexer.py`
- Redis index schema for entities and relationships
- Trigger handlers for create/update/delete operations

**Implementation:**
```python
# services/intelligence/domains/document_indexer/service.py (enhanced)

async def extract_graph_entities(workspace_id, project_id, session):
    """Extract entities from project data."""
    entities = {
        "persons": await fetch_persons(workspace_id),
        "projects": await fetch_projects(workspace_id, project_id),
        "objectives": await fetch_objectives(workspace_id, project_id),
        "tasks": await fetch_tasks(workspace_id, project_id),
        "costs": await fetch_costs(workspace_id, project_id),
    }
    
    # Index to Redis
    for entity_type, records in entities.items():
        for record in records:
            key = f"entity:{entity_type}:{record['id']}"
            await redis.hset(key, mapping={"data": json.dumps(record)})
            # Add to discovery set
            await redis.sadd(f"entities:{entity_type}", record['id'])
```

**Success criteria:**
- Extraction latency < 500ms for project with 1000 tasks
- Entity index has > 95% coverage (all tasks, objectives, people indexed)
- Redis storage < 50MB per workspace

#### Stage 2: Graph Retrievers (Week 2)

**Deliverables:**
- `GraphEntityRetriever` class
- `GraphPathRetriever` class
- Integration with existing retriever pipeline

**Implementation:**
```python
# services/intelligence/infrastructure/rag/retrievers/graph_retriever.py (new)

class GraphEntityRetriever(BaseRetriever):
    """Retrieve related entities (1-2 hops from query entity)."""
    
    async def retrieve(self, query, workspace_id, top_k=5, **filters):
        # 1. Resolve query to entity ID
        entity_id = await entity_resolver.resolve(query, workspace_id)
        
        # 2. Fetch entity and related entities from Redis
        entity_data = await redis.hget(f"entity:*:{entity_id}", "data")
        related = await redis.smembers(f"rels:outbound:{entity_id}")
        
        # 3. Return as RetrievedChunk
        chunks = [
            RetrievedChunk(
                text=json.dumps(entity_data),
                entity_type="entity",
                entity_id=entity_id,
                score=1.0,
            )
        ]
        for rel in related[:top_k]:
            related_entity = await redis.hget(f"entity:{rel}", "data")
            chunks.append(RetrievedChunk(
                text=json.dumps(related_entity),
                entity_type="entity",
                entity_id=rel,
                score=0.8,
            ))
        return chunks

class GraphPathRetriever(BaseRetriever):
    """Retrieve paths/chains (e.g., dependency chains, ownership paths)."""
    
    async def retrieve(self, query, workspace_id, top_k=3, **filters):
        # 1. Classify query for path type (dependency, ownership, cost allocation)
        path_type = classify_path_query(query)
        
        # 2. Find start/end entities
        start = await entity_resolver.resolve(query, workspace_id, entity_type="task")
        
        # 3. BFS/DFS to find paths
        paths = await find_paths(workspace_id, start, path_type, max_depth=3, limit=top_k)
        
        # 4. Format as chunks
        chunks = [
            RetrievedChunk(
                text=f"Path: {' → '.join(p)}",
                entity_type="path",
                entity_id=start,
                score=1.0 - (0.1 * len(path)),  # Penalize longer paths
            )
            for path in paths
        ]
        return chunks
```

**Success criteria:**
- Retriever latency < 50ms
- Both retrievers callable from agent loop
- No errors when integrated with RRF merger

#### Stage 3: Entity Resolution + RRF Fusion (Week 3)

**Deliverables:**
- Entity resolution service
- Updated RRF merger to handle 5 retrievers
- Query classification enhancements

**Implementation:**
```python
# services/intelligence/domains/analysis/entity_resolver.py (new)

async def resolve_entity(query, workspace_id, entity_type=None):
    """Fuzzy-match entity names to actual IDs."""
    # 1. NER on query
    tokens = query.split()
    
    # 2. BM25 search on entity names
    matches = []
    for et in (entity_type if entity_type else ["task", "objective", "person"]):
        entity_ids = await redis.smembers(f"entities:{et}")
        for eid in entity_ids:
            entity = json.loads(await redis.hget(f"entity:{et}:{eid}", "data"))
            score = bm25_score(query, entity.get("name", ""))
            matches.append((score, eid, entity))
    
    # 3. Return top match
    if matches:
        _, eid, entity = max(matches)
        return eid
    return None
```

**Success criteria:**
- Entity resolution accuracy > 90% for common queries
- RRF merger handles 5 retrievers without latency regression
- Query classification distinguishes graph vs. vector retrieval needs

#### Stage 4: Validation & A/B Testing (Week 4)

**Deliverables:**
- Monitoring dashboard (retrieval quality metrics)
- A/B test harness (control: current RAG, treatment: GraphRAG hybrid)
- Evaluation criteria and human scoring framework

**Success criteria:**
- Deploy to 10% of workspaces (treatment group)
- Measure:
  - Relevance score (manual, 1-5 scale, 30 sampled queries)
  - Latency (should be < 5% slower)
  - Error rate (no new errors from graph retrievers)
  - User satisfaction (if available)
- If relevance improves ≥ 10%, proceed to full rollout
- If latency increases > 10%, investigate caching strategy

---

## Decision Point: GraphRAG Validation (End of Week 4)

### Success Path (If Relevance Improves ≥ 10%)

**Action:**
- Proceed to "Full Rollout: GraphRAG Across All Workspaces" (Weeks 5-8)
- Promote treatment group to 100%
- Monitor closely for 2-4 weeks

**Timeline:**
- Week 5: Scale entity extraction to all workspaces
- Week 6: Full RAG hybrid deployment
- Week 7-8: Monitoring and edge case handling

### Fallback Path (If No Improvement or Regression)

**Action:**
- Debug entity extraction quality
- Review entity resolution accuracy
- Extend pilot by 1 week with improvements
- OR defer GraphRAG to future (keep PostgreSQL + Redis as-is)

**Checkpoint decision (end of Week 5):**
- Is improvement path clear? → Continue pilot, aim for Week 7 rollout
- Unclear/problematic? → Defer to Q3 after other priorities

---

## Deferred Path: Graph API Orchestration (Weeks 9-12)

### Prerequisites
- ✅ GraphRAG hybrid successfully deployed (after validation)
- ✅ TAOR loop is running reliably
- ✅ Multi-agent scenarios have been identified (from user research or roadmap)

### Goal
Replace implicit TAOR loop iterations with explicit graph orchestration. Enable multi-agent coordination, conditional tool execution, and sub-agent delegation.

### Stages

#### Stage 1: Orchestration Engine Design (Week 9)

**Deliverables:**
- Graph orchestration DSL (YAML or Python-based)
- Execution engine scaffold
- Test suite for DAG traversal

**Definition example:**
```yaml
# config/orchestrations/multi_agent_planning.yaml
name: multi_agent_planning
description: "Multi-agent workflow for project planning"

nodes:
  - id: gather_info
    type: tool_batch
    tools: [get_project_summary, search_tasks, get_cost_breakdown]
    outputs: {project_data, task_data, costs}
  
  - id: analyze_dependencies
    type: agent
    prompt: "Analyze task dependencies and critical path"
    inputs: {task_data}
    tools: [get_task_details, search_tasks]
    outputs: {critical_path, bottlenecks}
  
  - id: suggest_timeline
    type: agent
    prompt: "Suggest optimized timeline based on analysis"
    inputs: {critical_path, bottlenecks, project_data}
    tools: [bulk_set_timeline, update_project_metadata]
    outputs: {suggested_timeline, notes}
  
  - id: finalize
    type: template
    template: "Final plan: {suggested_timeline}\n\nKey recommendations: {notes}"
    inputs: {suggested_timeline, notes}

edges:
  - from: gather_info
    to: analyze_dependencies
  - from: analyze_dependencies
    to: suggest_timeline
  - from: suggest_timeline
    to: finalize
```

**Success criteria:**
- DSL is parseable and executable
- DAG validation catches cycles and missing inputs
- Execution engine can trace through nodes

#### Stage 2: Integration with Chat Service (Week 10)

**Deliverables:**
- Graph orchestration endpoint (`/ai/chat/graph`)
- Router integration
- Backward compatibility verification

**Endpoint:**
```python
@router.post("/workspaces/{ws}/projects/{project}/ai/chat/graph")
async def graph_orchestration(
    request: ChatRequest,
    orchestration_id: str,  # Selects which graph to execute
    ws: WorkspaceContext = Depends(require_write),
    session: AsyncSession = Depends(get_session),
):
    # Load orchestration definition
    orchestration = load_orchestration(orchestration_id)
    
    # Execute graph
    result = await graph_engine.execute(
        session=session,
        orchestration=orchestration,
        user_messages=request.messages,
        project_id=project,
        workspace_id=ws.workspace_id,
    )
    
    return ChatResponse(...)
```

**Success criteria:**
- Existing `/ai/chat` endpoint unchanged (backward compat)
- New `/ai/chat/graph` endpoint works end-to-end
- Tool execution results match non-graph version

#### Stage 3: Multi-Agent Scenarios (Week 11)

**Deliverables:**
- 2-3 orchestration templates for common scenarios
- Sub-agent delegation logic
- Conditional branching examples

**Example scenarios:**
1. "Weekly status sync" — gather data, analyze risks, suggest actions
2. "Plan optimization" — find critical path, suggest timeline adjustments
3. "Budget review" — aggregate costs, flag overages, suggest reallocation

**Success criteria:**
- Each scenario completes without manual intervention
- Results are equivalent or better than sequential manual agent calls
- Users find orchestration templates useful

#### Stage 4: Validation & Documentation (Week 12)

**Deliverables:**
- Performance benchmarks (latency vs. TAOR loop)
- User guide for orchestration design
- Monitoring dashboard for orchestration traces

**Success criteria:**
- Graph orchestration latency < 1.5x TAOR loop latency
- 0 new errors introduced
- At least 1 orchestration template adopted by users

---

## Deferred Path: Graph Database (Weeks 13-16, Post-GraphRAG)

### Prerequisites
- ✅ GraphRAG hybrid successfully deployed and validated
- ✅ Entity extraction and indexing proven reliable
- ✅ Operational budget and team capacity available

### Goal
Migrate from Redis graph index to dedicated Neo4j instance. Improve query performance for deep relationship traversals (4+ hops).

### Stages

#### Stage 1: Neo4j Setup & Schema Design (Week 13, days 1-2)

**Deliverables:**
- Neo4j instance (Aura or self-hosted)
- Property graph schema (nodes, relationships)
- Schema migration scripts

#### Stage 2: Dual-Write Implementation (Week 13, days 3-5)

**Deliverables:**
- Async write handlers for all mutations
- Consistency check service
- Fallback logic if Neo4j unavailable

#### Stage 3: Validation & Cutover (Weeks 14-15)

**Deliverables:**
- 1-week validation on staging
- A/B test with 10% of workspaces (read from Neo4j only for specific queries)
- Rollback plan

#### Stage 4: Full Migration (Week 16)

**Deliverables:**
- 100% Neo4j reads for graph queries
- PostgreSQL remains authoritative for transactions
- Monitoring and alerting

---

## Not Recommended at This Time

### Standalone Graph API (without GraphRAG)
**Why not:**
- Current TAOR loop handles single-agent scenarios well
- Graph API adds complexity without clear benefit
- Defer until multi-agent scenarios are common

**Revisit if:**
- Users request explicit agent coordination
- More than 2-3 team members request graph orchestration templates

### Graph Database as Primary Store
**Why not:**
- High operational overhead for dual systems
- PostgreSQL is reliable, fast for OPPM use cases
- Graph benefits are realized through targeted queries, not full replacement

**Revisit if:**
- Query latency becomes a bottleneck (> 500ms for key queries)
- Workspace count grows to 1000+ (at which point operational automation pays off)
- GraphRAG pilot shows persistent Neo4j need

---

## Timeline Summary

```
Week 1-4:    GraphRAG Hybrid Pilot
  │
  ├─ Decision Point: Validation Results
  │  ├─ Success (relevance ↑10%) → Week 5-8 Full Rollout
  │  └─ Needs Work → Week 5 Debug + Re-Validate
  │
  └─ Week 5-8: GraphRAG Full Rollout (if validated)
     │
     ├─ Week 9-12: Graph API Orchestration (optional, if demand)
     │
     └─ Week 13-16: Graph Database Migration (if needed after GraphRAG)

Parallel work: Other product priorities, not blocking GraphRAG
```

---

## Go/No-Go Checkpoints

### Checkpoint 1: End of Week 4 (GraphRAG Pilot)
**Question:** Did entity/path retrieval improve relevance ≥ 10%?
- **YES** → Proceed to full rollout
- **NO** → Extend pilot 1 week OR defer to Q3

### Checkpoint 2: End of Week 8 (GraphRAG Rollout)
**Question:** Is GraphRAG stable (error rate < 0.1%, no regressions)?
- **YES** → Proceed to Graph API design
- **NO** → Stabilize before moving forward

### Checkpoint 3: End of Week 12 (Graph API)
**Question:** Do users value orchestration templates? Is latency acceptable?
- **YES** → Proceed to graph database migration
- **NO** → Archive orchestration code, document lessons learned

### Checkpoint 4: End of Week 16 (Graph Database)
**Question:** Is dual-system operational cost justified by performance gains?
- **YES** → Promote Neo4j to production
- **NO** → Keep Redis index, deprecate Neo4j

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Entity extraction quality poor | Medium | High | Pilot on small workspace first, human validation |
| Graph index out of sync with PostgreSQL | Medium | High | Consistency checker runs hourly, alerts on divergence |
| Neo4j operational overhead too high | Medium | Medium | Start with Aura (managed), migrate to self-hosted only if cost justified |
| Latency regression from graph queries | Medium | Medium | Cache frequently accessed paths in Redis, monitor tail latency |
| User adoption of orchestration templates low | Low | Low | Start with 1-2 templates, gather feedback, iterate |

---

## References

- `docs/services/intelligence/GRAPH-FEASIBILITY.md` — Detailed feasibility analysis
- `docs/services/intelligence/README.md` — Intelligence service overview
- `docs/database/ai/README.md` — Database ownership and schema

---

**Document owner:** AI Team  
**Last updated:** 2026-04-21  
**Next review:** After GraphRAG pilot validation (expected 2026-05-20)
