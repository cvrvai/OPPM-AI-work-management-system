# Current Phase Tracker

## Task
Chat Panel Enhancement — File upload support (multi-type), persistent chat history per context

## Goal
Allow users to attach files (text/image/binary) to chat messages and persist chat history per workspace/project context across sessions.

## Plan
- [x] Update `chatStore.ts`: add `FileAttachment` type, `getContextKey` export, `contextHistories` with persist middleware, `clearContextHistory` action
- [x] Rewrite `ChatPanel.tsx`: file attachment state + handlers, pending attachment chips UI, paperclip button, file content embedded in API messages, attachment display in message bubbles, clear history button in header, history restored indicator (divider + count)

## Status: Complete ✅

## Files Changed
- `frontend/src/stores/chatStore.ts` — fully rewritten, now exports `FileAttachment`, `ChatMessage`, `getContextKey`; uses Zustand `persist` to store `contextHistories` in localStorage (`oppm-chat-history`)
- `frontend/src/components/ChatPanel.tsx` — fully rewritten with file upload, history UI, attachment chips

## Key Design Decisions
- File types: `.txt/.md/.csv/.json/.xml/.yaml/.yml/.log/.html/.py/.js/.ts` etc. → text extraction (client-side FileReader); `image/*` → data URL; pdf/docx/binary → filename chip only
- Text cap: 10,000 chars per file (truncated with notice)
- Max 5 files per message
- File content embedded only in the CURRENT API message; history messages use display content only
- Images stored as data URL in `FileAttachment.content` (for inline preview); text attachments store `content: ''` to save localStorage space
- History divider shown at `sessionStartIdx` (restored message count captured when context key changes)

## Verification
- No TypeScript errors in either file
- `chatStore` exports verified: `FileAttachment`, `ChatMessage`, `getContextKey`, `useChatStore`
- `ChatPanel` single `export function ChatPanel()` confirmed

## Notes
- Old PHASE-TRACKER archived to `docs/phase-history/2026-04-09-120000-comprehensive-docs-refresh.md`


## Plan
- [x] Archive old tracker → `docs/phase-history/2026-04-09-000000-rag-architecture-upgrade.md`
- [x] Update `ARCHITECTURE.md` — fix Redis "planned" note → active semantic cache; fix table count 23→29; update AI service description
- [x] Update `AI-SYSTEM-CONTEXT.md` — rewrite Section 8 (AI Assistant); add Section 12 (Tool Registry & Agentic Loop)
- [x] Expand `FLOWCHARTS.md` — add 5 new diagrams: RAG pipeline detail, tool registry execution, agentic loop, semantic cache lookup, OPPM data loading
- [x] Update `API-REFERENCE.md` — add feedback endpoints, document `iterations` in ChatResponse
- [x] Update `DATABASE-SCHEMA.md` — fix date, verify `task_owners` documented
- [x] Update `MICROSERVICES-REFERENCE.md` — rewrite AI service section for infrastructure sub-layers
- [x] Update `MICROSERVICES-REVIEW.md` — update AI service assessment to "structured and production-ready"
- [x] Create `docs/AI-PIPELINE-REFERENCE.md` — new dedicated pipeline reference
- [x] Create `docs/TOOL-REGISTRY-REFERENCE.md` — new dedicated tool registry reference

## Files Expected
Modified:
- `docs/ARCHITECTURE.md`
- `docs/AI-SYSTEM-CONTEXT.md`
- `docs/FLOWCHARTS.md`
- `docs/API-REFERENCE.md`
- `docs/DATABASE-SCHEMA.md`
- `docs/MICROSERVICES-REFERENCE.md`
- `docs/MICROSERVICES-REVIEW.md`

Created:
- `docs/AI-PIPELINE-REFERENCE.md`
- `docs/TOOL-REGISTRY-REFERENCE.md`

## Verification
- All dates updated to 2026-04-09
- Table count consistent: 29 tables
- FLOWCHARTS.md has >= 13 diagrams
- Feedback endpoints in API-REFERENCE.md
- New component docs in `docs/` and cross-referenced from ARCHITECTURE.md

## Notes
- tool registry: 21 tools, 4 modules (oppm/task/cost/read)
- agentic loop: max 5 iterations, stops on empty tool_calls
- semantic cache: Redis, cosine >= 0.92, TTL 300s, key prefix `ai:sem_cache:`
- guardrails: `check_input()` + `sanitize_output()` in `infrastructure/rag/guardrails.py`
- feedback: logged to `audit_log` with action `"ai_feedback"`
- `ChatResponse.iterations: int` (new field)
- `FeedbackRequest`: rating, message_content, user_message, comment, model_id