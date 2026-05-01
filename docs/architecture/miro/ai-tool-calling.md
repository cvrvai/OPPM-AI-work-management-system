# AI Tool Calling with RAG — Miro Ready

Last updated: 2026-05-01

## Purpose

This document visualizes the **complete AI chat flow** combining RAG retrieval with the agentic tool loop. Use it to understand how the Intelligence Service processes user messages end-to-end.

Each flowchart is:
- **Self-contained** — copy-paste into Miro
- **Color-coded by phase** — 🟦 Input, 🟩 RAG, 🟨 Tool Loop, 🟥 Output
- **Mermaid-ready** — import directly or draw manually

---

## Table of Contents

1. [Full AI Chat Flow](#1-full-ai-chat-flow)
2. [Workspace vs Project Chat](#2-workspace-vs-project-chat)
3. [Agentic Tool Loop Detail](#3-agentic-tool-loop-detail)
4. [Tool Registry Execution](#4-tool-registry-execution)
5. [RAG + Tools Combined](#5-rag--tools-combined)

---

## 1. Full AI Chat Flow

**Purpose:** End-to-end flow from user message to AI response.

```mermaid
flowchart TD
    A["👤 User sends message"] --> B["🛡️ Input Guardrail"]
    B -- blocked --> BX["❌ 400 error"]
    B -- safe --> C{"💬 Workspace or Project chat?"}

    C -- Workspace --> D["📡 POST /ai/chat\nRAG only, no tools"]
    C -- Project --> E["📡 POST /projects/:id/ai/chat\nFull pipeline"]

    E --> F["📋 Load Project Context"]
    F --> G["✍️ Query Rewrite"]
    G --> H{"🔍 Semantic Cache hit?"}
    H -- HIT --> I["📋 Return cached context"]
    H -- MISS --> J["🏷️ Classify query"]
    J --> K["🔍 Parallel retrieval"]
    K --> L["📊 RRF Reranker"]
    L --> M["💾 Store in cache (TTL 5min)"]
    M --> N["📝 Build system prompt"]
    I --> N
    D --> N

    N --> O["🤖 Agentic Tool Loop\nmax 7 iterations"]
    O --> P["🧠 LLM call"]
    P --> Q{"🔧 Tool calls?"}
    Q -- No --> R["✅ Final answer"]
    Q -- Yes --> S["⚙️ Execute tools"]
    S --> T["📡 Inject results"]
    T --> P

    R --> U["🛡️ Output Guardrail"]
    U --> V["💾 Audit log"]
    V --> W["📡 Response to frontend\nmessage + tool_calls + updated_entities + iterations"]
```

### Miro Tips
- This is a **large flowchart** — consider splitting into 2 boards:
  1. **RAG Pipeline** (steps A → N)
  2. **Tool Loop** (steps O → W)
- Use **decision diamonds** for chat type, cache hit, and tool calls
- Show **loop arrow** for tool iteration

---

## 2. Workspace vs Project Chat

**Purpose:** Compares the two chat modes side-by-side.

```mermaid
flowchart TD
    subgraph "Workspace Chat"
        A1["👤 User message"] --> B1["📡 POST /ai/chat"]
        B1 --> C1["📋 Workspace context\nname + project list"]
        C1 --> D1["🔍 Workspace-scoped RAG"]
        D1 --> E1["📝 System prompt + tools"]
        E1 --> F1["🤖 Tool loop"]
    end

    subgraph "Project Chat"
        A2["👤 User message"] --> B2["📡 POST /projects/:id/ai/chat"]
        B2 --> C2["📋 Full project context\nobjectives, tasks, risks, costs, team, commits"]
        C2 --> D2["🔍 Project-boosted RAG"]
        D2 --> E2["📝 System prompt + tools"]
        E2 --> F2["🤖 Tool loop"]
    end

    F1 --> G["🛡️ Output Guardrail"]
    F2 --> G
    G --> H["💾 Audit Log"]
    H --> I["📡 Response"]
```

### Miro Tips
- Draw **2 vertical swimlanes** side-by-side
- Show **same ending** converging
- Highlight **extra context** in project chat

---

## 3. Agentic Tool Loop Detail

**Purpose:** Zooms into the tool execution loop.

```mermaid
flowchart TD
    A["📝 Build system prompt\ncontext + tools"] --> B["🧠 LLM call"]
    B --> C{"🔧 Response contains\ntool_calls?"}
    C -- No --> D["✅ Final text response"]
    C -- Yes --> E["🔧 Parse tool_calls\nOpenAI / Anthropic / XML"]
    E --> F["⚙️ Execute each tool\nvia registry.execute()"]
    F --> G["📋 Collect ToolResults\nsuccess + result + error"]
    G --> H{"🔁 Iteration < 7?"}
    H -- No --> I["📝 Final summary call\nno tools included"]
    I --> J["📦 Return AgentLoopResult\nfinal_text + iterations + updated_entities"]
    H -- Yes --> K["📡 Inject results\nas next user turn text"]
    K --> B
    D --> J
```

### Miro Tips
- Show **clear loop** with iteration limit
- Use **decision diamond** for tool_calls check
- Show **exit paths** (no tools vs max iterations)

---

## 4. Tool Registry Execution

**Purpose:** How tools are discovered, parsed, and executed.

```mermaid
flowchart TD
    A["🧠 LLM Response"] --> B{"🔧 Native or Prompt-based?"}
    B -- Native --> C["OpenAI / Anthropic\nparse_openai_tool_calls()"]
    B -- Prompt --> D["Ollama / Kimi\nparse_xml_tool_calls()"]
    C --> E["📋 ToolCall objects"]
    D --> E
    E --> F["🔍 registry.execute()"]
    F --> G["⚙️ Tool Handler\ncreate_task, update_objective, etc."]
    G --> H["💾 Shared DB Write"]
    H --> I["📋 ToolResult\nsuccess + updated_entities"]
    I --> J["📡 Inject as user turn"]
    J --> K["🧠 Next LLM call"]
```

### Miro Tips
- Show **2 parsing paths** converging
- Highlight **registry.execute()** as central hub
- Show **DB write** as real side effect

---

## 5. RAG + Tools Combined

**Purpose:** Shows how RAG context and tool results feed into the same LLM prompt.

```mermaid
flowchart TD
    subgraph "Phase 1: RAG"
        A["👤 User Query"] --> B["🔍 RAG Pipeline"]
        B --> C["📋 Retrieved Context"]
    end

    subgraph "Phase 2: Tool Loop"
        D["📝 System Prompt\ncontext + RAG + tools"] --> E["🧠 LLM Call"]
        E --> F{"🔧 Tool Calls?"}
        F -- Yes --> G["⚙️ Execute Tools"]
        G --> H["📡 Inject Results"]
        H --> E
        F -- No --> I["✅ Final Answer"]
    end

    subgraph "Phase 3: Output"
        I --> J["🛡️ Output Guardrail"]
        J --> K["💾 Audit Log"]
        K --> L["📡 Frontend Response"]
    end

    C --> D
```

### Miro Tips
- Draw **3 horizontal phases**
- Show **RAG output** feeding into tool loop
- Use **different colors** for each phase

---

## Miro Import Guide

### Option 1: Mermaid Import (Fastest)

1. Open Miro
2. Add **Mermaid chart** widget
3. Copy-paste any Mermaid block above
4. Miro auto-generates the diagram

### Option 2: Manual Drawing (Most Control)

1. Use **4 colors** for phases:
   - 🟦 Blue = Input / Guardrails
   - 🟩 Green = RAG / Retrieval
   - 🟨 Yellow = Tool Loop
   - 🟥 Red = Output / Response
2. Add **emoji icons** for visual clarity
3. Use **decision diamonds** for yes/no branches
4. Label **all arrows** with action names
