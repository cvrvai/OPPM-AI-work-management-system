# Clean Flowcharts — Miro Ready

Last updated: 2026-05-01

## Purpose

This document extracts the **most important runtime flowcharts** from the system and presents them in a clean, visual format optimized for Miro whiteboarding.

Each flowchart is:
- **Self-contained** — no need to read other docs
- **Color-coded by service** — 🟦 Workspace, 🟩 Intelligence, 🟥 Integrations, 🟨 Automation
- **Mermaid-ready** — copy-paste into Miro's Mermaid import or draw manually

---

## Table of Contents

1. [End-to-End Service Collaboration](#1-end-to-end-service-collaboration)
2. [Request Lifecycle](#2-request-lifecycle)
3. [Cross-Service Calls](#3-cross-service-calls)
4. [App Bootstrap & Auth Refresh](#4-app-bootstrap--auth-refresh)
5. [Workspace Invite Acceptance](#5-workspace-invite-acceptance)
6. [Project Creation Wizard](#6-project-creation-wizard)
7. [Task Report Approval](#7-task-report-approval)
8. [GitHub Webhook to Commit Analysis](#8-github-webhook-to-commit-analysis)
9. [AI Chat & RAG Pipeline](#9-ai-chat--rag-pipeline)
10. [Agentic Tool Loop](#10-agentic-tool-loop)
11. [Gateway Routing Decision](#11-gateway-routing-decision)
12. [RAG Pipeline Step-by-Step](#12-rag-pipeline-step-by-step)

---

## 1. End-to-End Service Collaboration

**Purpose:** Shows how the browser request flows through all services.

```mermaid
flowchart LR
    Browser["🌐 Browser"] --> Frontend["⚛️ React + Vite"]
    Frontend --> Gateway["🛡️ Gateway"]

    Gateway -->|"/api/auth/*"| Workspace["🟦 Workspace\n:8000"]
    Gateway -->|"/api/v1/workspaces/*/ai/*"| Intelligence["🟩 Intelligence\n:8001"]
    Gateway -->|"/api/v1/workspaces/*/rag/*"| Intelligence
    Gateway -->|"/api/v1/workspaces/*/github*"| Integrations["🟥 Integrations\n:8002"]
    Gateway -->|"/api/v1/workspaces/*/git/*"| Integrations
    Gateway -->|"/api/v1/workspaces/*/mcp/*"| Automation["🟨 Automation\n:8003"]
    Gateway -->|"all other /api/*"| Workspace

    Integrations -.->|"POST /internal/analyze-commits\n+ X-Internal-API-Key"| Intelligence

    Workspace --> DB[("💾 PostgreSQL")]
    Intelligence --> DB
    Integrations --> DB
    Automation --> DB

    Workspace --> Redis[("⚡ Redis")]
    Intelligence --> Redis
    Intelligence --> LLM["🧠 LLM APIs"]
    Integrations --> GitHub["🐙 GitHub"]
```

### Miro Tips
- Use **4 colored boxes** for services (🟦🟩🟥🟨)
- Use **1 box** for Gateway
- Use **1 box** for Browser/Frontend
- Draw arrows with **path labels**
- Add **PostgreSQL, Redis, LLM, GitHub** as external boxes

---

## 2. Request Lifecycle

**Purpose:** Shows what happens inside a single API request.

```mermaid
sequenceDiagram
    actor U as 👤 User
    participant G as 🛡️ Gateway
    participant R as 🟦 Router
    participant A as 🔐 Auth Middleware
    participant S as ⚙️ Service
    participant P as 🗄️ Repository
    participant D as 💾 PostgreSQL

    U->>G: HTTP request (/api/...)
    G->>R: Forward by route
    R->>A: Resolve user + workspace
    A-->>R: CurrentUser + WorkspaceContext
    R->>S: Call domain function
    S->>P: Apply business rules
    P->>D: SQLAlchemy async query
    D-->>P: Rows / result
    P-->>S: Domain data
    S-->>R: Response payload
    R-->>G: JSON response
    G-->>U: HTTP response
```

### Miro Tips
- Draw **6 vertical swimlanes**
- Use **arrows** for calls, **dashed arrows** for returns
- Label each step clearly

---

## 3. Cross-Service Calls

**Purpose:** Shows the two main cross-service call chains.

```mermaid
flowchart TD
    subgraph "Chain A: GitHub Push → Analysis"
        A1["🐙 GitHub push"] --> A2["🟥 Webhook route"]
        A2 --> A3["🟥 Store commits"]
        A3 --> A4["🟥 Call AI internal endpoint"]
        A4 --> A5["🟩 Analyze commits"]
        A5 --> A6["💾 commit_analyses stored"]
    end

    subgraph "Chain B: Admin Reindex"
        B1["👤 Admin triggers reindex"] --> B2["🟩 Reindex route"]
        B2 --> B3["🟩 Read workspace data"]
        B3 --> B4["🟩 Generate embeddings"]
        B4 --> B5["💾 document_embeddings upserted"]
    end
```

### Miro Tips
- Draw **2 separate chains** vertically
- Use **color coding** for services
- Add **PostgreSQL** at the end of each chain

---

## 4. App Bootstrap & Auth Refresh

**Purpose:** Shows frontend initialization and token refresh.

```mermaid
flowchart TD
    A["🌐 Browser loads React"] --> B["⚛️ App.tsx initialize"]
    B --> C{"💾 Has local access token?"}
    C -- No --> D["🔓 Render public routes"]
    C -- Yes --> E["📋 fetchWorkspaces"]
    E --> F["🔒 Protected routes render"]
    D --> G["👤 User goes to login"]
    F --> H["📡 API request"]
    H --> I{"❌ API returns 401?"}
    I -- No --> J["✅ Use response"]
    I -- Yes --> K["🔄 POST /api/auth/refresh"]
    K --> L{"✅ Refresh succeeds?"}
    L -- Yes --> M["💾 Store new tokens"]
    M --> N["🔄 Retry original request"]
    L -- No --> O["🗑️ Clear tokens"]
    O --> P["🔀 Redirect to /login"]
```

### Miro Tips
- Use **diamond shapes** for decisions
- Use **emoji icons** for visual clarity
- Draw **2 paths** (with/without token)

---

## 5. Workspace Invite Acceptance

**Purpose:** Shows the invite flow from link click to membership.

```mermaid
flowchart TD
    A["👤 User opens /invites/:token"] --> B["📡 GET /invites/preview/:token"]
    B --> C{"✅ Preview valid?"}
    C -- No --> D["❌ Show invalid state"]
    C -- Yes --> E["📋 Show workspace info"]
    E --> F{"🔐 User authenticated?"}
    F -- No --> G["🔓 Login or Sign Up"]
    G --> H["📡 POST /invites/accept"]
    F -- Yes --> H
    H --> I["🟦 Validate token + rules"]
    I --> J["💾 INSERT workspace_members"]
    J --> K["💾 UPDATE invite (accepted)"]
    K --> L["🔄 Refresh workspace list"]
```

### Miro Tips
- Use **decision diamonds** for validation checks
- Show **both auth paths** converging
- End with **success state**

---

## 6. Project Creation Wizard

**Purpose:** Shows the 2-step project creation flow.

```mermaid
flowchart TD
    A["👤 Open New Project modal"] --> B["📝 Step 1: Project info"]
    B --> C["📋 Title, code, objective, schedule, budget, lead"]
    C --> D["👥 Step 2: Team assignment"]
    D --> E["📋 Select members + roles"]
    E --> F["📡 POST /projects"]
    F --> G["🟦 Create project"]
    G --> H["💾 Creator added as lead"]
    H --> I{"👥 Additional members?"}
    I -- No --> J["🔄 Invalidate queries"]
    I -- Yes --> K["📡 Loop POST /projects/:id/members"]
    K --> L["💾 INSERT project_members"]
    L --> J
```

### Miro Tips
- Show **2 wizard steps** as sequential boxes
- Use **decision** for optional team members
- Show **loop** for multiple member additions

---

## 7. Task Report Approval

**Purpose:** Shows the task report submission and approval flow.

```mermaid
flowchart TD
    A["👤 Member opens project"] --> B["📝 Create task report"]
    B --> C["📡 POST /tasks/:id/reports"]
    C --> D["💾 INSERT task_reports"]
    D --> E["👀 Write-enabled user reviews"]
    E --> F["📡 PATCH /reports/:id/approve"]
    F --> G["🟦 UPDATE is_approved + approved_by"]
    G --> H["🔄 UI refreshes reports"]
```

### Miro Tips
- Simple **linear flow**
- Show **2 actors** (member + approver)
- Highlight **state change**

---

## 8. GitHub Webhook to Commit Analysis

**Purpose:** Shows the full webhook → analysis pipeline.

```mermaid
flowchart TD
    A["🐙 Developer pushes to GitHub"] --> B["📡 POST /api/v1/git/webhook"]
    B --> C["🟥 Find repo_config"]
    C --> D["🔐 Validate HMAC-SHA256"]
    D --> E{"✅ Push event?"}
    E -- No --> F["🚫 Reject/ignore"]
    E -- Yes --> G["✅ Return 200 quickly"]
    G --> H["↻ Background: store commit_events"]
    H --> I["🟥 Call 🟩 /internal/analyze-commits"]
    I --> J["🟩 Analyze vs project context"]
    J --> K["💾 INSERT commit_analyses"]
    K --> L["📡 Frontend GET /commits"]
```

### Miro Tips
- Show **async step** with ↻ symbol
- Highlight **quick response** vs **background processing**
- Show **cross-service call** (🟥 → 🟩)

---

## 9. AI Chat & RAG Pipeline

**Purpose:** Shows the full AI chat flow with RAG and tools.

```mermaid
flowchart TD
    A["👤 User sends message"] --> B["🛡️ Input Guardrail"]
    B -- blocked --> BX["❌ 400 error"]
    B -- safe --> C{"💬 Workspace or Project chat?"}
    C -- Workspace --> D["📡 POST /ai/chat\nRAG only, no tools"]
    C -- Project --> E["📡 POST /projects/:id/ai/chat\nFull pipeline"]

    E --> F["📋 Load project context"]
    F --> G["✍️ Query Rewrite"]
    G --> H{"🔍 Semantic Cache hit?"}
    H -- HIT --> I["📋 Return cached context"]
    H -- MISS --> J["🏷️ Classify query"]
    J --> K["🔍 Parallel retrieval"]
    K --> L["📊 RRF Reranker"]
    L --> M["💾 Store in cache (TTL 5min)"]
    M --> N["📝 Build system prompt"]
    I --> N

    N --> O["🤖 Agentic Tool Loop\nmax 7 iterations"]
    O --> P["🧠 LLM call"]
    P --> Q{"🔧 Tool calls?"}
    Q -- No --> R["✅ Final answer"]
    Q -- Yes --> S["⚙️ Execute tools"]
    S --> T["📡 Inject results"]
    T --> P

    R --> U["🛡️ Output Guardrail"]
    U --> V["💾 Audit log"]
    V --> W["📡 Response to frontend"]
```

### Miro Tips
- This is a **large flowchart** — consider splitting into 2 boards:
  1. **RAG Pipeline** (steps A → N)
  2. **Tool Loop** (steps O → W)
- Use **decision diamonds** for cache hit and tool calls
- Show **loop arrow** for tool iteration

---

## 10. Agentic Tool Loop

**Purpose:** Zooms into the tool execution loop.

```mermaid
flowchart TD
    A["📝 Build system prompt\ncontext + tools"] --> B["🧠 LLM call"]
    B --> C{"🔧 Response contains\ntool_calls?"}
    C -- No --> D["✅ Final text response"]
    C -- Yes --> E["🔧 Parse tool_calls"]
    E --> F["⚙️ Execute each tool\nvia registry"]
    F --> G["📋 Collect ToolResults"]
    G --> H{"🔁 Iteration < 7?"}
    H -- No --> I["📝 Final summary call"]
    I --> J["📦 Return AgentLoopResult\ntext + iterations + entities"]
    H -- Yes --> K["📡 Inject results\nas next user turn"]
    K --> B
    D --> J
```

### Miro Tips
- Show **clear loop** with iteration limit
- Use **decision diamond** for tool_calls check
- Show **exit paths** (no tools vs max iterations)

---

## 11. Gateway Routing Decision

**Purpose:** Shows how the gateway decides which service gets the request.

```mermaid
flowchart TD
    A["📡 Incoming /api request"] --> B{"🔍 Path matches AI?"}
    B -- Yes --> C["🟩 Forward to Intelligence"]
    B -- No --> D{"🔍 Path matches integrations?"}
    D -- Yes --> E["🟥 Forward to Integrations"]
    D -- No --> F{"🔍 Path matches automation?"}
    F -- Yes --> G["🟨 Forward to Automation"]
    F -- No --> H["🟦 Forward to Workspace"]
```

### Miro Tips
- Simple **decision tree**
- Show **4 exit points** (one per service)
- Add **path examples** on each arrow

---

## 12. RAG Pipeline Step-by-Step

**Purpose:** Detailed breakdown of the RAG retrieval pipeline.

```mermaid
flowchart TD
    A["📝 Raw query text"] --> B["Step 1: Input Guardrail\ncheck injection + < 4000 chars"]
    B --> C["Step 2: Query Rewrite\nLLM expands vague queries"]
    C --> D["Step 3: Generate Embedding\nLLM embeds rewritten query"]
    D --> E{"Step 4: Semantic Cache\ncosine ≥ 0.92?"}
    E -- HIT --> F["✅ Return cached context\nskip retrieval"]
    E -- MISS --> G["Step 5: Classify Query\nlabel retriever types"]
    G --> H["Step 6: Parallel Retrieval\nvector + keyword + structured"]
    H --> I["Step 7: RRF Reranker\nReciprocal Rank Fusion"]
    I --> J["Step 8: Project Boost\nup-rank project hits"]
    J --> K["Step 9: Format Context\nbuild retrieval string"]
    K --> L["Step 10: Store in Cache\nTTL 300s, ai:sem_cache: prefix"]
    L --> M["📋 Return context to caller"]
    F --> M
```

### Miro Tips
- Show **10 numbered steps**
- Use **decision diamond** for cache hit
- Show **shortcut path** (cache hit skips steps 5-10)

---

## Miro Import Guide

### Option 1: Mermaid Import (Fastest)

1. Open Miro
2. Add **Mermaid chart** widget
3. Copy-paste any Mermaid block above
4. Miro auto-generates the diagram

### Option 2: Manual Drawing (Most Control)

1. Create **sticky notes** for each step
2. Use **color coding**:
   - 🟦 Blue = Workspace Service
   - 🟩 Green = Intelligence Service
   - 🟥 Red = Integrations Service
   - 🟨 Yellow = Automation Service
   - ⬜ Gray = External (Browser, DB, Redis, LLM, GitHub)
3. Draw **arrows** between steps
4. Add **decision diamonds** for yes/no branches
5. Group related flows with **frames**

### Recommended Board Layout

```
┌─────────────────────────────────────────┐
│  Board 1: Service Collaboration         │
│  - Flowchart #1 (End-to-End)            │
│  - Flowchart #2 (Request Lifecycle)     │
│  - Flowchart #3 (Cross-Service Calls)   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Board 2: User Flows                    │
│  - Flowchart #4 (App Bootstrap)         │
│  - Flowchart #5 (Invite Acceptance)   │
│  - Flowchart #6 (Project Creation)    │
│  - Flowchart #7 (Task Report)         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Board 3: AI & Integration Flows        │
│  - Flowchart #8 (GitHub Webhook)        │
│  - Flowchart #9 (AI Chat Pipeline)    │
│  - Flowchart #10 (Tool Loop)            │
│  - Flowchart #12 (RAG Pipeline)         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Board 4: Gateway & Routing             │
│  - Flowchart #11 (Gateway Routing)      │
│  - API endpoint cards                   │
│  - Service boundary boxes               │
└─────────────────────────────────────────┘
```

---

## Quick Reference: Flowchart Index

| # | Flowchart | Complexity | Best For |
|---|---|---|---|
| 1 | End-to-End Service Collaboration | Medium | Architecture overview |
| 2 | Request Lifecycle | Low | Onboarding new devs |
| 3 | Cross-Service Calls | Medium | Understanding integrations |
| 4 | App Bootstrap & Auth Refresh | Low | Frontend auth flow |
| 5 | Workspace Invite Acceptance | Low | Team onboarding flow |
| 6 | Project Creation Wizard | Medium | Project management UX |
| 7 | Task Report Approval | Low | Task workflow |
| 8 | GitHub Webhook to Analysis | High | Integration architecture |
| 9 | AI Chat & RAG Pipeline | High | AI feature deep-dive |
| 10 | Agentic Tool Loop | Medium | AI tool execution |
| 11 | Gateway Routing Decision | Low | API routing |
| 12 | RAG Pipeline Step-by-Step | High | RAG implementation |
