# Graph Technology Feasibility Assessment — Quick Reference

**Status:** ✅ Complete  
**Created:** 2026-04-21  
**For:** OPPM AI Work Management System  

---

## One-Sentence Summary per Approach

| Approach | Summary | Recommendation |
|----------|---------|-----------------|
| **Graph API** | Graph-based orchestration for multi-agent coordination; minimal immediate benefit for single-agent scenarios | ⏸️ Defer to Week 9 |
| **GraphRAG** | Entity/relationship retrieval to complement vector/keyword; high value for OPPM's relational data | ▶️ **Pilot now (4 weeks)** |
| **Graph Database** | Dedicated graph store (Neo4j/TigerGraph) for relationship queries; operational overhead high until PostgreSQL queries become bottleneck | ⏸️ Defer indefinitely or post-pilot |

---

## Quick Feasibility Matrix

```
                     Low Effort          Medium Effort        High Effort
High Impact          GraphRAG ✓          ——                   ——
Medium Impact        ——                  ——                   Graph DB
Low Impact           ——                  Graph API ✗          ——

✓ = Recommended (start now)
✗ = Lower priority (defer)
```

---

## The Plan: GraphRAG Hybrid Pilot (4 Weeks)

### Timeline
- **Week 1:** Extract entities from tasks/objectives/people/costs → Index in Redis
- **Week 2:** Build graph entity retriever + graph path retriever
- **Week 3:** Entity resolution + integrate with RRF (now 5-way merge)
- **Week 4:** A/B test with 10% of workspaces; validate metrics

### Success Criteria
- ✅ Relevance improves ≥ 10% (human scoring on 30 sampled queries)
- ✅ Latency < 5% slower (parallel retriever calls)
- ✅ Zero new errors from graph retrievers
- ✅ Entity extraction accuracy > 95%

### If It Works (End of Week 4)
→ Full rollout to all workspaces (Weeks 5-8) + consider Graph API (Weeks 9-12)

### If It Doesn't Work (End of Week 4)
→ Debug for 1 week OR defer to Q3

---

## Why GraphRAG First?

**OPPM data is inherently graph-like:**
- Tasks depend on tasks (dependency chains)
- People own objectives & are assigned to tasks
- Costs allocate to projects/objectives/tasks (multi-level)
- Timelines track progress through task relationships

**Current RAG misses relationship reasoning:**
- Vector retrieval finds "similar" chunks; doesn't traverse relationships
- Keyword retrieval finds exact terms; doesn't understand dependencies
- Structured retriever is pre-defined filters; not flexible for ad-hoc paths

**Example gap query:** "Who is blocked on the critical path?" (today's RAG struggles)
- GraphRAG: Find tasks with status='blocked' → Traverse depends_on relationships → Return assigned persons

---

## Key Deliverables

### New Documents (in `docs/services/ai/`)
1. **GRAPH-FEASIBILITY.md** (37KB)
   - Detailed analysis of all three approaches
   - Current architecture overview
   - Effort/risk/impact breakdown
   - Pilot scopes for each approach

2. **GRAPH-MIGRATION-PATHS.md** (17KB)
   - Decision tree (when to choose each option)
   - Stage-by-stage implementation for GraphRAG
   - Go/no-go checkpoints
   - Risk mitigation strategies

### Updated Documents
1. **docs/services/ai/README.md**
   - Enhanced AI Evolution Options with feasibility ratings
   - Links to detailed assessments

2. **docs/PHASE-TRACKER.md**
   - New tracker for this assessment
   - Links to findings and next steps

---

## For the Engineering Team

### Week 1 Action Items (GraphRAG Pilot Kickoff)
- [ ] Review GRAPH-FEASIBILITY.md and GRAPH-MIGRATION-PATHS.md
- [ ] Confirm GraphRAG is priority with product/stakeholders
- [ ] Design entity extraction schema (which entities, which relationships)
- [ ] Set up Redis index keys and expiry strategy
- [ ] Define entity resolution accuracy target (> 90% for MVP)

### Code Changes Required
**Files to create:**
- `services/ai/services/entity_resolver.py` — resolve query text to entity IDs
- `services/ai/infrastructure/rag/retrievers/graph_retriever.py` — entity + path retrieval
- `services/ai/infrastructure/rag/graph_query_builder.py` — Cypher/query builder (if using Neo4j later)

**Files to enhance:**
- `services/ai/services/document_indexer.py` — add `extract_graph_entities()`
- `services/ai/services/rag_service.py` — integrate graph retrievers into RRF

**No changes to:**
- `services/ai/routers/v1/ai_chat.py` — backward compatible
- `services/ai/services/ai_chat_service.py` — no TAOR loop changes
- Database schema — entity indexing is application-level initially

### Metrics to Track (Week 4 Validation)
1. **Relevance** (human-scored, 1-5 scale, 30 queries)
   - Current RAG baseline score
   - GraphRAG hybrid score
   - Goal: +10% improvement

2. **Latency** (99th percentile)
   - Current RAG latency
   - GraphRAG hybrid latency
   - Goal: < 5% slower (parallel retriever calls)

3. **Quality metrics**
   - Entity extraction coverage (% of entities indexed)
   - Entity resolution accuracy (% correctly matched)
   - Graph index staleness (seconds behind PostgreSQL)
   - Error rate (% of queries with retriever failures)

4. **User feedback** (if available)
   - Are answers more useful?
   - Are citations clearer?
   - Any negative user experience?

---

## For the Ops/Infrastructure Team

### Storage Requirements (MVP Phase)
- **Redis entity index:** ~50MB per workspace (conservative estimate)
- **Redis relationship index:** ~30MB per workspace
- **Total:** ~100MB per workspace

### Monitoring Needs
- Entity extraction success rate
- Graph index staleness (lag between PostgreSQL and index)
- Consistency check frequency (recommend hourly)
- Alert threshold (alert if lag > 5 minutes)

### No New Infrastructure (Week 1-4)
- Use existing Redis instance
- No Neo4j, TigerGraph, or other graph DB needed for MVP
- Evaluate separate graph store only after pilot validation (Week 8+)

---

## Decision Checkpoint: End of Week 4

### Scenario A: Validation Passes ✅
**Metrics:** Relevance ↑10%, latency acceptable, error rate < 0.1%

**Action:** Proceed to full rollout (Weeks 5-8)
- Scale entity extraction to all workspaces
- Deploy to 100% of users
- Then evaluate Graph API (Week 9) or Graph Database (Week 13)

### Scenario B: Mixed Results ⚠️
**Metrics:** Modest improvement (5-10%) OR latency issues OR errors

**Action:** Debug for 1 week
- Improve entity extraction quality?
- Add caching to reduce latency?
- Fix retriever error rates?
- Re-evaluate Week 5

### Scenario C: No Improvement ❌
**Metrics:** Relevance flat or down, latency increased, high error rate

**Action:** Defer to Q3
- Archive pilot code and learnings
- Document blockers
- Revisit when more time available

---

## Not Recommended (At This Time)

### Graph API Without GraphRAG
- Current TAOR loop works well for single-agent scenarios
- Graph orchestration adds complexity without proven need
- Defer until multi-agent scenarios are common

### Graph Database as Primary Store
- Operational overhead (backup, replication, monitoring) too high
- PostgreSQL is reliable and fast for OPPM use cases
- Graph benefits only for specific relationship queries, not all queries
- Evaluate after GraphRAG pilot shows if Neo4j queries are frequent enough

### Replacing Vector/Keyword Retrieval Entirely
- Start with hybrid (keep current retrievers, add graph)
- Only remove vector/keyword if graph outperforms consistently
- Safer to validate incrementally

---

## Document Links

📄 **Full Feasibility Analysis:** [`docs/services/ai/GRAPH-FEASIBILITY.md`](./GRAPH-FEASIBILITY.md)
- 37KB detailed report with architecture overview, assessments, effort/risk analysis, pilot scopes

📄 **Migration Decision Tree:** [`docs/services/ai/GRAPH-MIGRATION-PATHS.md`](./GRAPH-MIGRATION-PATHS.md)
- 17KB implementation roadmap with stages, checkpoints, go/no-go criteria, risk mitigation

📄 **AI Service Overview:** [`docs/services/ai/README.md`](./README.md)
- Updated with feasibility findings and evolution options

📄 **Phase Tracker:** [`docs/PHASE-TRACKER.md`](../PHASE-TRACKER.md)
- Current task status and next steps

---

## Questions?

**For technical deep-dives:**
→ See GRAPH-FEASIBILITY.md (current architecture section + detailed assessments)

**For implementation planning:**
→ See GRAPH-MIGRATION-PATHS.md (stages, effort estimates, success criteria)

**For quick scheduling:**
→ See timeline summary above

---

**Assessment completed by:** AI Service Architect  
**Date:** 2026-04-21  
**Approval:** Pending stakeholder review  
**Next review:** After GraphRAG pilot validation (~2026-05-20)
