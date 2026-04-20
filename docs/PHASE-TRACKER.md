# Current Phase Tracker

## Task
Graph API, GraphRAG, and Graph Database Feasibility Assessment

## Goal
Evaluate whether the OPPM AI system can adopt graph technologies (Graph API orchestration, GraphRAG entity/relationship retrieval, Graph Database storage). Provide feasibility analysis, effort estimates, and a sequenced migration path. **Recommendation: Pilot GraphRAG hybrid immediately; defer Graph API and Graph DB.**

## Plan
- [x] Archive previous phase tracker
- [x] Review current AI chat API structure and contracts
- [x] Analyze current RAG pipeline and tool orchestration
- [x] Create comprehensive feasibility report (GRAPH-FEASIBILITY.md)
  - Current architecture overview
  - Graph API assessment (technical compatibility, effort, pilots)
  - GraphRAG assessment (entity extraction, retrieval integration, hybrid approach)
  - Graph Database assessment (multi-tenancy, schema mapping, operational costs)
  - Recommendation matrix
- [x] Create migration decision tree and sequencing (GRAPH-MIGRATION-PATHS.md)
  - Go/no-go checkpoints per phase
  - Detailed stage breakdown for GraphRAG pilot (4 weeks)
  - Risk mitigation strategies
- [x] Update AI service doc with feasibility findings and links
- [x] Document session plan

## Status
Complete

## Files Created
- `docs/services/ai/GRAPH-FEASIBILITY.md` — 37KB comprehensive feasibility analysis
- `docs/services/ai/GRAPH-MIGRATION-PATHS.md` — decision tree, stages, checkpoints
- `docs/phase-history/2026-04-20-102342-database-subfolder-by-service-ARCHIVED.md`

## Files Modified
- `docs/services/ai/README.md` — updated AI Evolution Options with feasibility ratings and links

## Verification

**Feasibility Analysis:**
- ✅ Current AI architecture documented (chat endpoints, RAG pipeline, TAOR loop, tool registry)
- ✅ Graph API assessed: High feasibility, Medium effort, Low-Medium impact → defer
- ✅ GraphRAG assessed: High feasibility, Medium-Large effort, **High impact** → **pilot immediately**
- ✅ Graph Database assessed: Medium feasibility, Large effort, Medium impact → defer
- ✅ Recommendation matrix provided (effort vs. impact)

**Migration Path:**
- ✅ GraphRAG Hybrid pilot sequenced (Weeks 1-4: extract → index → retrieve → validate)
- ✅ Go/no-go checkpoints defined (validation at Week 4)
- ✅ Graph API orchestration deferred to Weeks 9-12 (if GraphRAG succeeds)
- ✅ Graph Database deferred to Weeks 13-16 (or never if not needed)
- ✅ Risk mitigation strategies documented

**Documentation Quality:**
- ✅ All recommendations grounded in code review (routers, services, agent_loop, registry)
- ✅ Concrete effort estimates (T-shirt sizes + rationale)
- ✅ Success criteria clear for each pilot phase
- ✅ All docs link to services/ai and database/ai hubs for future maintenance

## Key Findings

### Recommendation Summary
**Proceed with GraphRAG Hybrid Pilot (4 weeks, starting immediately).**

| Approach | Feasibility | Effort | Impact | Status |
|----------|-------------|--------|--------|--------|
| Graph API | ⭐⭐⭐⭐ High | Medium | Low-Medium | ⏸️ Defer to Week 9 |
| GraphRAG Hybrid | ⭐⭐⭐⭐ High | Medium-Large | **High** | ▶️ **Start Week 1** |
| Graph Database | ⭐⭐⭐ Medium | Large | Medium | ⏸️ Defer to Week 13 |

### Why GraphRAG First?
- OPPM data is inherently graph-like (tasks depend on tasks, people own objectives, costs allocate to multiple levels)
- Current vector + keyword retrieval misses relationship reasoning ("Who is blocked?" "What are critical tasks?")
- Hybrid approach (add graph retrievers alongside current ones) is low-risk
- Pilot is self-contained: 4 weeks, measurable quality improvement (≥10% relevance gain)
- No backward compatibility risk (graph retrievers are optional if validation fails)

### GraphRAG Pilot Stages
1. **Week 1:** Entity extraction + Redis indexing
2. **Week 2:** Graph entity/path retrievers
3. **Week 3:** Entity resolution + RRF fusion (5-way merge)
4. **Week 4:** A/B testing and validation (measure relevance, latency, errors)

**Success criteria:** Relevance improves ≥10%, latency < 5% slower, zero new errors.

### Decision Point (End of Week 4)
- ✅ Metrics pass → Proceed to full rollout (Weeks 5-8)
- ❌ Metrics fail → Debug for 1 week OR defer to Q3

## Next Steps (for implementation team)

1. **Review this assessment** with stakeholders (engineering, product, ops)
   - Confirm GraphRAG is priority
   - Agree on pilot success metrics

2. **Prepare GraphRAG pilot kickoff** (Week 1)
   - Set up entity extraction scaffold in `document_indexer.py`
   - Design Redis index schema
   - Define entity types and relationships

3. **Schedule Graph API design review** (Week 9, conditional on GraphRAG success)

4. **Create infrastructure capacity plan**
   - Storage overhead for entity/relationship index (~50MB/workspace)
   - Latency targets (< 50ms for retriever calls)
   - Monitoring dashboard for graph index quality

## Notes

- **No runtime code changes in this task** — assessment and planning only
- **Feasibility reports are grounded in code** — reviewed routers, services, RAG pipeline, agent loop, tool registry
- **All documents link to service/database hubs** — follow docs/services/ and docs/database/ patterns for future maintenance
- **Risk mitigation strategies included** — entity quality validation, consistency checking, fallback paths
- **Go/no-go checkpoints** ensure team can make informed stop/continue decisions

---

## Appendix: Assessment Highlights

### Current AI Architecture (Overview)
- **Chat endpoint:** `POST /api/v1/workspaces/{ws}/projects/{project}/ai/chat`
- **Request:** messages array + optional model_id
- **Response:** message + tool_calls + updated_entities + iterations + low_confidence
- **RAG:** 10-stage pipeline (guardrail → memory → rewrite → embed → cache → classify → parallel retrieve → rerank → format)
- **Retrievers:** vector (pgvector) + keyword (PostgreSQL FTS) + structured (SQL filters)
- **Tool orchestration:** TAOR loop (Think → Act → Observe → Retry, max 7 iterations)
- **Tools:** 24 tools across 5 categories (oppm, task, cost, read, project)
- **State management:** Stateless per request, conversation history passed as array, results accumulated

### GraphRAG Value Proposition
**Current limitations:**
- Vector retrieval misses dependencies (e.g., "What is task X's blocker?")
- Keyword retrieval is term-based; doesn't understand relationships
- Structured retriever requires pre-defined filters; not flexible for ad-hoc queries

**GraphRAG additions:**
- Entity retrieval (find related persons, tasks, objectives, costs from graph)
- Path retrieval (find dependency chains, ownership paths, cost allocations)
- Entity resolution (map query text to actual task/person/objective IDs)
- Parallel 5-way RRF fusion (vector + keyword + structured + entity + path)

### GraphRAG Implementation Outline
1. Extract entities from tasks, objectives, people, costs → Redis index
2. Build two new retrievers (entity, path) + entity resolver
3. Integrate with existing RRF merger (now 5-way instead of 3-way)
4. Validate on staging, A/B test with 10% of workspaces
5. If relevance ↑10%, full rollout; else debug or defer

---

**Document owner:** AI Service Team  
**Last updated:** 2026-04-21  
**Next milestone:** GraphRAG pilot validation (End of Week 4, ~2026-05-20)

