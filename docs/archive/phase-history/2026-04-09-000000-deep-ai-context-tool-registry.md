# Phase Tracker Archive

## Task
Deep AI Context & Scalable Tool-Calling Architecture

## Goal
1. Enrich AI project context — include ALL OPPM data (sub-objectives, deliverables, risks, dependencies, assignees, costs breakdown) in `_build_project_context()`
2. Replace hardcoded tool system with a registry-based architecture supporting native LLM function calling
3. Add new read/write/analysis tools for richer AI capabilities

## Status: Complete (archived 2026-04-09)

## Files Modified
- `services/ai/repositories/oppm_repo.py` — added DeliverableRepository, ForecastRepository, RiskRepository, TaskDetailRepository
- `services/ai/services/ai_chat_service.py` — expanded context builder, tiered windowing, dynamic tool section, registry-based execution
- `services/ai/infrastructure/rag/retrievers/structured_retriever.py` — expanded to 7 retrieval patterns
- `services/ai/infrastructure/llm/base.py` — added tool_calls/raw_response to LLMResponse, call_with_tools()
- `services/ai/infrastructure/llm/openai.py` — native function calling
- `services/ai/infrastructure/llm/anthropic.py` — native tool_use
- `services/ai/infrastructure/llm/__init__.py` — call_with_fallback_tools(), NATIVE_TOOL_PROVIDERS

## Files Created
- `services/ai/infrastructure/tools/__init__.py`
- `services/ai/infrastructure/tools/base.py`
- `services/ai/infrastructure/tools/registry.py`
- `services/ai/infrastructure/tools/oppm_tools.py`
- `services/ai/infrastructure/tools/task_tools.py`
- `services/ai/infrastructure/tools/cost_tools.py`
- `services/ai/infrastructure/tools/read_tools.py`
- `services/ai/infrastructure/llm/tool_parser.py`
