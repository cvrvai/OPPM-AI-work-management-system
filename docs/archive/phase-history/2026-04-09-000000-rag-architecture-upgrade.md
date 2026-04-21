# Phase Tracker — RAG Architecture Upgrade

*Archived: 2026-04-09*

## Task
RAG Architecture Upgrade — Agentic Loop, Guardrails, Query Rewriting, Semantic Cache, Feedback

## Goal
1. Replace single-shot tool calling with an agentic multi-turn loop (max 5 iterations)
2. Add query rewriting/expansion before retrieval for better recall
3. Add input guardrails (prompt injection check) and output guardrails (sensitive data scrub)
4. Add lightweight semantic cache via Redis to reduce latency/cost
5. Add user feedback endpoint (thumbs up/down) to enable future model improvement

## Status: Complete

## Plan
- [x] Create `infrastructure/rag/agent_loop.py` — multi-turn agentic tool loop
- [x] Create `infrastructure/rag/query_rewriter.py` — LLM-based query expansion
- [x] Create `infrastructure/rag/guardrails.py` — input/output safety filters
- [x] Create `infrastructure/rag/semantic_cache.py` — embedding-based Redis cache
- [x] Update `services/rag_service.py` — add query rewriting step + cache
- [x] Update `services/ai_chat_service.py` — use agent loop + guardrails
- [x] Update `routers/v1/ai_chat.py` + `schemas/ai_chat.py` — feedback endpoint
- [x] Update `docs/FLOWCHARTS.md` — new AI Chat flow diagram

## Files Changed
New:
- `services/ai/infrastructure/rag/agent_loop.py`
- `services/ai/infrastructure/rag/query_rewriter.py`
- `services/ai/infrastructure/rag/guardrails.py`
- `services/ai/infrastructure/rag/semantic_cache.py`

Modified:
- `services/ai/infrastructure/rag/__init__.py`
- `services/ai/services/rag_service.py`
- `services/ai/services/ai_chat_service.py`
- `services/ai/routers/v1/ai_chat.py`
- `services/ai/schemas/ai_chat.py`
- `docs/FLOWCHARTS.md`

## Verification
- [x] Agent loop created with max 5 iterations, stops on empty tool_calls
- [x] Query rewriting skips queries > 300 chars or <= 2 words
- [x] Guardrails block injection patterns and scrub sensitive output
- [x] Semantic cache uses cosine >= 0.92, TTL 300s, prefix `ai:sem_cache:`
- [x] Feedback endpoints POST to audit_log with action "ai_feedback"
