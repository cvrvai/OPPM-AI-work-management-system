# Flowcharts

Last updated: 2026-04-20

## Purpose

These flowcharts describe runtime paths based on the current implementation.

Use this file in two passes:

1. Read **Service Interaction Charts** to understand service boundaries and cross-service behavior.
2. Read **Detailed Feature Flow Charts** to understand endpoint-level and function-level behavior.

## Service Interaction Charts

### S1. End-to-End Service Collaboration Map

```mermaid
flowchart LR
    Browser[Browser] --> Frontend[Frontend React + Vite]
    Frontend --> Gateway[Gateway Python or nginx]

    Gateway -->|/api/auth + default /api/v1| Core[Core Service]
    Gateway -->|/api/v1/workspaces/:ws/ai*| AI[AI Service]
    Gateway -->|/api/v1/workspaces/:ws/rag*| AI
    Gateway -->|/api/v1/workspaces/:ws/projects/:id/ai*| AI
    Gateway -->|/api/v1/workspaces/:ws/github-accounts*| Git[Git Service]
    Gateway -->|/api/v1/workspaces/:ws/commits*| Git
    Gateway -->|/api/v1/workspaces/:ws/git/*| Git
    Gateway -->|/api/v1/workspaces/:ws/mcp/*| MCP[MCP Service]

    Git -->|POST /internal/analyze-commits + X-Internal-API-Key| AI

    Core --> DB[(PostgreSQL)]
    AI --> DB
    Git --> DB
    MCP --> DB

    Core --> Redis[(Redis)]
    AI --> Redis

    AI --> LLM[LLM Providers]
    Git --> GH[GitHub]
```

### S2. Backend Function Lifecycle (Router To Data)

```mermaid
sequenceDiagram
    participant U as User / Frontend
    participant G as Gateway
    participant R as Service Router
    participant A as shared/auth.py
    participant S as Service Function
    participant P as Repository
    participant D as shared/database.py + PostgreSQL

    U->>G: HTTP request (/api/...)
    G->>R: Forward by route pattern
    R->>A: Resolve user and workspace context
    A-->>R: CurrentUser + WorkspaceContext
    R->>S: Call domain function
    S->>P: Apply business rules and persistence call
    P->>D: SQLAlchemy async query
    D-->>P: Rows / mutation result
    P-->>S: Domain data
    S-->>R: Response payload
    R-->>G: JSON response
    G-->>U: HTTP response
```

### S3. Cross-Service Calls (Current Runtime)

```mermaid
flowchart TD
    A[GitHub push event] --> B[Git webhook route]
    B --> C[Store commits in Git service]
    C --> D[Git calls AI internal endpoint]
    D --> E[AI analyzes commits]
    E --> F[commit_analyses stored in shared DB]

    G[Admin reindex request] --> H[AI reindex route]
    H --> I[AI reads workspace data]
    I --> J[Embeddings generated]
    J --> K[document_embeddings upserted]

    L[Model integration request] --> M[MCP list or call route]
    M --> N[MCP tool executes with workspace_id]
    N --> O[Shared DB reads or writes]
```

## Detailed Feature Flow Charts

## 1. App Bootstrap And Auth Refresh

```mermaid
flowchart TD
    A[Browser loads React app] --> B[App.tsx initialize]
    B --> C{Has local access token?}
    C -- No --> D[Render public routes]
    C -- Yes --> E[fetchWorkspaces after auth init]
    D --> F[User goes to login or invite page]
    E --> G[Protected routes render]

    G --> H[User makes API request]
    H --> I{API returns 401?}
    I -- No --> J[Use response]
    I -- Yes --> K[POST /api/auth/refresh]
    K --> L{Refresh succeeds?}
    L -- Yes --> M[Store new tokens]
    M --> N[Retry original request once]
    L -- No --> O[Clear tokens]
    O --> P[ProtectedRoute redirects to /login]
```

## 2. Workspace Invite Acceptance

```mermaid
flowchart TD
    A[User opens /invites/:token] --> B[Frontend calls GET /api/v1/invites/preview/:token]
    B --> C{Preview valid?}
    C -- No --> D[Show invalid or expired state]
    C -- Yes --> E[Show workspace name, role, member count]
    E --> F{User authenticated?}
    F -- No --> G[User logs in or signs up]
    G --> H[POST /api/v1/invites/accept]
    F -- Yes --> H[POST /api/v1/invites/accept]
    H --> I[Core service validates token and membership rules]
    I --> J[workspace_members row created]
    J --> K[Invite marked accepted]
    K --> L[Frontend refreshes workspace list]
```

## 3. Project Creation Wizard

```mermaid
flowchart TD
    A[User opens New Project modal] --> B[Step 1 project info]
    B --> C[Title, code, objective summary, schedule, budget, lead]
    C --> D[Step 2 team assignment]
    D --> E[Select workspace members and project roles]
    E --> F[POST /api/v1/workspaces/:ws/projects]
    F --> G[Core creates project]
    G --> H[Creator workspace membership added as project lead]
    H --> I{Additional team members selected?}
    I -- No --> J[Invalidate project queries]
    I -- Yes --> K[Frontend loops POST /projects/:project_id/members]
    K --> L[Backend stores project_members rows]
    L --> J[Invalidate project queries]
```

## 4. Task Report Approval Flow

```mermaid
flowchart TD
    A[Member opens project detail page] --> B[Create task report]
    B --> C[POST /api/v1/workspaces/:ws/tasks/:task_id/reports]
    C --> D[task_reports row created]
    D --> E[Write-enabled user reviews report]
    E --> F[PATCH /reports/:report_id/approve]
    F --> G[Core updates is_approved and approved_by]
    G --> H[UI refreshes task reports]
```

## 5. GitHub Webhook To Commit Analysis

```mermaid
flowchart TD
    A[Developer pushes to GitHub] --> B[GitHub sends POST /api/v1/git/webhook]
    B --> C[Git service locates repo_config by repository full name]
    C --> D[Validate X-Hub-Signature-256 with webhook secret]
    D --> E{Signature valid and push event?}
    E -- No --> F[Reject or ignore request]
    E -- Yes --> G[Return accepted response quickly]
    G --> H[Background task stores commit_events]
    H --> I[Git service calls AI /internal/analyze-commits]
    I --> J[AI service analyzes commits against project context]
    J --> K[commit_analyses rows stored]
    K --> L[Frontend can fetch recent analyses and reports]
```

## 6. AI Chat And RAG Retrieval

```mermaid
flowchart TD
    A[User sends AI message] --> B[Input Guardrail\ncheck length + injection patterns]
    B -- blocked --> BX[400 error returned]
    B -- safe --> C{Workspace chat or project chat?}
    C -- Workspace --> D[POST /ai/chat\nRAG only no tools]
    C -- Project --> E[POST /projects/:id/ai/chat\nfull pipeline]

    E --> F[Load project context\nobjectives tasks risks costs team commits]
    F --> G[Query Rewriting\nLLM expands vague query]
    G --> H{Semantic Cache\nhit?}
    H -- HIT --> I[Return cached RAG context]
    H -- MISS --> J[Classify query\nselect retrievers]
    J --> K[Parallel retrieval\nvector + keyword + structured]
    K --> L[RRF Reranker\nmerge + boost project results]
    L --> M[Store in semantic cache TTL 5min]
    M --> N[Build system prompt\ncontext + RAG + tool section]
    I --> N

    N --> O[Agentic Tool Loop\nmax 7 iterations]
    O --> P[LLM call\nnative tools or XML prompt]
    P --> Q{Tool calls\nin response?}
    Q -- No --> R[Final answer]
    Q -- Yes --> S[Execute tools via registry\nOPPM tasks costs risks deliverables]
    S --> T[Inject tool results\nas next user turn]
    T --> P

    R --> U[Output Guardrail\nscrub sensitive patterns]
    U --> V[Audit log\niterations + tool count]
    V --> W[Response to frontend\nmessage + tool_calls + updated_entities + iterations]
```

## 6a. User Feedback Flow

```mermaid
flowchart TD
    A[User clicks thumbs up or down] --> B[POST /projects/:id/ai/feedback]
    B --> C[Store in audit_log\nrating + user message + ai message + comment]
    C --> D[200 ok returned]
```

## 7. Workspace Reindex Flow

```mermaid
flowchart TD
    A[Admin triggers reindex] --> B[POST /api/v1/workspaces/:ws/ai/reindex]
    B --> C[AI document indexer walks workspace data]
    C --> D[Projects, tasks, objectives, costs, members, commits gathered]
    D --> E[Embeddings generated]
    E --> F[document_embeddings upserted]
    F --> G[Capabilities endpoint reflects updated index count]
```

## 8. Gateway Routing Decision

```mermaid
flowchart TD
    A[Incoming /api request] --> B{Path matches AI pattern?}
    B -- Yes --> C[Forward to AI service]
    B -- No --> D{Path matches Git pattern?}
    D -- Yes --> E[Forward to Git service]
    D -- No --> F{Path matches MCP pattern?}
    F -- Yes --> G[Forward to MCP service]
    F -- No --> H[Forward to Core service]
```

## Notes

- Native development uses the Python gateway in `services/gateway/`.
- Docker deployments use nginx rules in `gateway/nginx.conf`.
- Those routing rules must stay aligned.
- The internal AI analysis route is not part of the public frontend API surface.
- The exact-match route `/internal/analyze-commits` is forwarded to the AI service for service-to-service use.

---

## 9. RAG Pipeline — Step By Step

```mermaid
flowchart TD
    A[Raw query text] --> B[Step 1: Input Guardrail\ncheck_input - block injection or > 4000 chars]
    B --> C[Step 2: Query Rewriting\nrewrite_query if 3+ words and < 300 chars]
    C --> D[Step 3: Generate Embedding\nLLM embed rewritten query]
    D --> E{Step 4: Semantic Cache\nlookup cosine >= 0.92}
    E -- HIT --> F[Return cached context\nskip retrieval]
    E -- MISS --> G[Step 5: Classify Query\nlabel retriever types]
    G --> H[Step 6: Parallel Retrieval\nvector + keyword + structured]
    H --> I[Step 7: RRF Reranker\nReciprocal Rank Fusion merge]
    I --> J[Step 8: Project Boost\nup-rank project-specific hits]
    J --> K[Step 9: Format Context\nbuild retrieval string]
    K --> L[Step 10: Store in Semantic Cache\nTTL 300 s — ai:sem_cache: prefix]
    L --> M[Return context to caller]
    F --> M
```

## 10. Agentic Tool Loop

```mermaid
flowchart TD
    A[Build system prompt\ncontext + tool section] --> B[LLM call\nnative tools or XML prompt]
    B --> C{Response contains\ntool_calls?}
    C -- No --> D[Final text response]
    C -- Yes --> E[Parse tool_calls\nvia tool_parser.py]
    E --> F[Execute each tool\nvia registry.execute]
    F --> G[Collect tool results\nToolResult objects]
    G --> H{Iteration count\n< max 7?}
    H -- No --> I[Final summary call\nno tools included]
    I --> J[Return AgentLoopResult\nfinal_text + iterations + updated_entities]
    H -- Yes --> K[Inject results\nas next user turn text]
    K --> B
    D --> J
```

## 11. Tool Registry Execution

```mermaid
flowchart TD
    A[AI service calls get_registry] --> B{Registry initialized?}
    B -- No --> C[Auto-import oppm_tools\ntask_tools cost_tools\nread_tools project_tools]
    C --> D[All 24 tools registered]
    B -- Yes --> D
    D --> E{LLM provider\nnative or prompt-based?}
    E -- OpenAI / Anthropic --> F[to_openai_schema or\nto_anthropic_schema]
    E -- Ollama / Kimi --> G[to_prompt_text\nprompt-text tool section]
    F --> H[LLM returns native tool_calls JSON]
    G --> I[LLM returns JSON inside\n<tool_calls> tags]
    H --> J[parse_openai_tool_calls or\nparse_anthropic_tool_calls]
    I --> K[parse_xml_tool_calls]
    J --> L[registry.execute tool_name + args]
    K --> L
    L --> M{Tool requires\nproject context?}
    M -- Yes --> N[Inject project_id\nfrom ChatRequest]
    M -- No --> O[Execute handler directly]
    N --> O
    O --> P[Return ToolResult\nsuccess + result + updated_entities]
```

## 12. Semantic Cache Lookup And Store

```mermaid
flowchart TD
    A[Query text] --> B[Generate query embedding]
    B --> C{Redis\navailable?}
    C -- No --> D[Return None - cache miss]
    C -- Yes --> E[Scan ai:sem_cache: keys\nin workspace namespace]
    E --> F[Compute cosine similarity\nbetween query and each cached embedding]
    F --> G{Best similarity\n>= 0.92?}
    G -- No --> H[Return None - cache miss]
    G -- Yes --> I[Return cached context string]

    J[RAG result ready] --> K{Redis\navailable?}
    K -- No --> L[Skip store - fail-safe]
    K -- Yes --> M[Serialize result + embedding]
    M --> N[SET ai:sem_cache:hash_key\nEX 300 seconds]
```

## 13. OPPM Project Context Loading

```mermaid
flowchart TD
    A[_build_project_context called\nproject_id + workspace_id] --> B[Load project record\ntitle status budget dates lead]
    B --> C[Load objectives\nwith A/B/C priority and owner]
    C --> D[Load sub-objectives\npositions 1-6]
    D --> E[Load tasks\nwith assignees dependencies owners]
    E --> F[Load timeline entries\nweek_start + status + quality]
    F --> G[Load project costs\ncategory planned actual]
    G --> H[Load deliverables]
    H --> I[Load forecasts]
    I --> J[Load risks]
    J --> K[Load team members\nwith skills]
    K --> L[Load recent commits\nand analyses]
    L --> M{Total context\nsize?}
    M -- <= TIER1 16K --> N[Include full data]
    M -- <= TIER2 12K --> O[Truncate commits\nand analyses]
    M -- > TIER2 --> P[Keep objectives + tasks\ncosts + team only]
    N --> Q[Return formatted context string]
    O --> Q
    P --> Q
```

## 14. Core Service Function Flow (Workspace To OPPM)

```mermaid
flowchart TD
    A[Core Router /api/v1/workspaces/... ] --> B[shared.auth dependencies]
    B --> C{Role gate}
    C -- viewer/member/admin/owner --> D[Core service function]
    C -- unauthorized --> X[403 response]
    D --> E[Repository call]
    E --> F[Shared ORM models]
    F --> G[(PostgreSQL)]
    G --> H[Service response shaping]
    H --> I[JSON response]
```

## 15. AI Service Function Flow (Chat And Tools)

```mermaid
flowchart TD
    A[AI Router /api/v1/workspaces/:ws/... ] --> B[Auth + workspace context]
    B --> C[ai_chat_service or rag_service]
    C --> D[Guardrails + query rewrite + retrieval]
    D --> E{Tool call needed?}
    E -- No --> F[Final model response]
    E -- Yes --> G[Tool registry execute]
    G --> H[AI repositories + shared DB]
    H --> I[Updated entities + tool output]
    I --> F
    F --> J[Output guardrail]
    J --> K[JSON or SSE response]
```

## 16. Git Service Function Flow (Webhook To Analysis)

```mermaid
flowchart TD
    A[Git Router /api/v1/git/webhook] --> B[Find repo config]
    B --> C[Validate HMAC signature]
    C --> D{Push event?}
    D -- No --> E[Ignore or return]
    D -- Yes --> F[Accept quickly]
    F --> G[Background task stores commits]
    G --> H[Call AI /internal/analyze-commits]
    H --> I[AI writes commit analyses]
    I --> J[Frontend reads /commits and /git/recent-analyses]
```

## 17. MCP Service Function Flow (Tool Discovery And Call)

```mermaid
flowchart TD
    A[MCP Router /api/v1/workspaces/:ws/mcp/*] --> B[Auth + workspace context]
    B --> C{Endpoint}
    C -- GET /tools --> D[List TOOL_REGISTRY metadata]
    C -- POST /call --> E[Resolve tool by name]
    E --> F[Inject workspace_id into params]
    F --> G[Execute tool function]
    G --> H{Execution success?}
    H -- Yes --> I[Return tool result payload]
    H -- No --> J[Return MCP error payload]
```
