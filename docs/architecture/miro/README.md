# Miro Presentation Materials

Last updated: 2026-05-01

## Purpose

This folder contains **Miro-ready visual documents** for presentations and whiteboarding. Each file is self-contained, emoji-rich, and color-coded for easy copy-paste into Miro.

## Files

| File | Content | Best For |
|---|---|---|
| [flowcharts.md](flowcharts.md) | 12 runtime flowcharts (service collaboration, request lifecycle, user flows, AI pipeline, RAG, tool loop, gateway routing) | Architecture overview boards |
| [api-pipeline.md](api-pipeline.md) | Every public API endpoint mapped with service colors, inputs, outputs, and cross-service call chains | API interaction boards |
| [er-diagram.md](er-diagram.md) | Visual ER diagram with 32 tables grouped by domain color, relationship map, and Mermaid source | Database schema boards |
| [rag-system.md](rag-system.md) | 5 dedicated RAG pipeline flowcharts (overview, step-by-step, semantic cache, parallel retrieval, project context builder) | AI/RAG deep-dive boards |
| [ai-tool-calling.md](ai-tool-calling.md) | 5 AI tool calling flowcharts (full chat flow, workspace vs project, agentic loop, tool registry, RAG+tools combined) | AI feature boards |

## How to Use

### Option 1: Mermaid Import (Fastest)
1. Open Miro
2. Add **Mermaid chart** widget
3. Copy-paste any Mermaid block from the files above
4. Miro auto-generates the diagram

### Option 2: Manual Drawing (Most Control)
1. Create sticky notes for each step
2. Use the color coding from each file
3. Draw arrows and decision diamonds
4. Group related flows with frames

## Color Legend (All Files)

| Color | Meaning |
|---|---|
| 🟦 Blue | Workspace Service |
| 🟩 Green | Intelligence Service |
| 🟥 Red | Integrations Service |
| 🟨 Yellow | Automation Service |
| ⬜ Gray | External (Browser, DB, Redis, LLM, GitHub) |

## Recommended Board Layout

```
Board 1: Service Architecture
  - flowcharts.md #1 (End-to-End Service Collaboration)
  - flowcharts.md #2 (Request Lifecycle)
  - flowcharts.md #3 (Cross-Service Calls)
  - api-pipeline.md (Cross-Service Interaction Summary)

Board 2: User Flows
  - flowcharts.md #4 (App Bootstrap)
  - flowcharts.md #5 (Invite Acceptance)
  - flowcharts.md #6 (Project Creation)
  - flowcharts.md #7 (Task Report)

Board 3: AI & RAG Deep-Dive
  - rag-system.md #1 (RAG Pipeline Overview)
  - rag-system.md #2 (RAG Step-by-Step)
  - rag-system.md #3 (Semantic Cache)
  - rag-system.md #4 (Parallel Retrieval)
  - rag-system.md #5 (Project Context Builder)

Board 4: AI Tool Calling
  - ai-tool-calling.md #1 (Full AI Chat Flow)
  - ai-tool-calling.md #2 (Workspace vs Project)
  - ai-tool-calling.md #3 (Agentic Tool Loop)
  - ai-tool-calling.md #4 (Tool Registry Execution)
  - ai-tool-calling.md #5 (RAG + Tools Combined)

Board 5: Database Schema
  - er-diagram.md (Entity Boxes + Relationship Map)

Board 6: Gateway & Routing
  - flowcharts.md #11 (Gateway Routing Decision)
  - api-pipeline.md (Request Routing Through Gateway)
```

## Note

For the **technical reference** versions of these flowcharts (with more detailed annotations), see:
- [../flowcharts.md](../flowcharts.md) — Technical runtime flowcharts
- [../api-pipeline-miro.md](../api-pipeline-miro.md) — API interaction reference (legacy location, will be removed)
