# OPPM AI — System Flowcharts

## 1. Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Gateway
    participant Core Service
    participant Database
    participant Redis

    User->>Frontend: Enter email + password
    Frontend->>Gateway: POST /api/auth/login<br/>{email, password}
    Gateway->>Core Service: Route to core:8000
    Core Service->>Database: SELECT user WHERE email = ?
    Database-->>Core Service: user row (password_hash)
    Core Service->>Core Service: bcrypt.verify(password, hash)
    Core Service->>Core Service: jwt.encode({sub: user_id, exp: +15min})
    Core Service-->>Gateway: {access_token, refresh_token, expires_in, user}
    Gateway-->>Frontend: {access_token, refresh_token, expires_in, user}
    Frontend->>Frontend: Store tokens in localStorage<br/>via authStore

    Note over Frontend,Redis: Subsequent API calls

    Frontend->>Gateway: GET /api/v1/workspaces<br/>Authorization: Bearer {access_token}
    Gateway->>Core Service: Round-robin to core:8000
    Core Service->>Core Service: jwt.decode(token, SECRET_KEY) → user_id
    Core Service->>Redis: Check token blacklist
    Redis-->>Core Service: Not blacklisted
    Core Service->>Database: Query workspace_members<br/>WHERE user_id = {user_id}
    Database-->>Core Service: User's workspaces
    Core Service-->>Frontend: 200 OK [{workspaces}]

    Note over Frontend: On 401 response

    Frontend->>Gateway: POST /api/auth/refresh<br/>{refresh_token}
    Gateway->>Core Service: Route to core:8000
    Core Service->>Database: Validate refresh_token (not revoked, not expired)
    Core Service->>Core Service: Issue new access_token + refresh_token
    Core Service-->>Frontend: New tokens
    Frontend->>Frontend: Update localStorage, retry original request
```

## 2. Workspace Creation & Invite Flow

```mermaid
sequenceDiagram
    actor Owner
    actor Invitee
    participant Frontend
    participant Backend API
    participant Database
    participant Email

    Owner->>Frontend: Create workspace "My Team"
    Frontend->>Backend API: POST /api/v1/workspaces<br/>{name, slug, description}
    Backend API->>Database: INSERT workspace
    Backend API->>Database: INSERT workspace_member<br/>(user_id, role=owner)
    Backend API-->>Frontend: 201 Created {workspace}

    Owner->>Frontend: Invite teammate
    Frontend->>Backend API: POST /api/v1/workspaces/:ws/invites<br/>{email, role: "member"}
    Backend API->>Database: INSERT workspace_invite<br/>(token, expires_at=+7 days)
    Backend API->>Email: Send invite link
    Backend API-->>Frontend: 201 Created {invite}

    Note over Invitee: Receives email with invite token

    Invitee->>Frontend: Click invite link
    Frontend->>Backend API: POST /api/v1/invites/accept<br/>{token}
    Backend API->>Database: Validate token (not expired, not used)
    Backend API->>Database: INSERT workspace_member<br/>(user_id, role from invite)
    Backend API->>Database: UPDATE invite (accepted_at)
    Backend API-->>Frontend: 200 OK {workspace}
```

## 3. GitHub Webhook Flow

```mermaid
sequenceDiagram
    participant GitHub
    participant Backend API
    participant Rate Limiter
    participant Database
    participant AI Provider

    GitHub->>Backend API: POST /api/v1/git/webhook<br/>X-Hub-Signature-256: sha256=...
    Backend API->>Rate Limiter: Check webhook rate limit<br/>(30 req/min)
    Rate Limiter-->>Backend API: OK (tokens available)
    Backend API->>Backend API: Validate HMAC signature<br/>(webhook_secret)

    alt Invalid signature
        Backend API-->>GitHub: 401 Unauthorized
    end

    Backend API->>Database: Find repo_config by repo name
    Backend API->>Database: INSERT commit_event<br/>(hash, message, author, branch)

    Backend API->>Database: Query active AI models<br/>for workspace
    loop For each active AI model
        Backend API->>AI Provider: Analyze commit<br/>(message, files, diff context)
        AI Provider-->>Backend API: {quality_score, alignment_score,<br/>progress_delta, summary}
        Backend API->>Database: INSERT commit_analysis
    end

    Backend API->>Database: INSERT notification<br/>(type=commit, title, message)
    Backend API-->>GitHub: 200 OK
```

## 4. OPPM Dashboard Data Flow

```mermaid
flowchart TD
    A[User opens OPPM View] --> B[Frontend queries workspace-scoped data]

    B --> C[GET /projects/:id]
    B --> D[GET /projects/:id/oppm/objectives]
    B --> E[GET /projects/:id/oppm/timeline]
    B --> F[GET /projects/:id/oppm/costs]
    B --> G[GET /projects/:id/members]

    C --> H{Compose OPPM Grid}
    D --> H
    E --> H
    F --> H
    G --> H

    H --> I[Header Row: Project meta + timeline months]
    H --> J[Objectives Column: Goals with owners]
    H --> K[Timeline Grid: Month × Objective status cells]
    H --> L[Team Section: Members with roles]
    H --> M[Cost Section: Budget vs Actual]

    I --> N[Render OPPM One-Page View]
    J --> N
    K --> N
    L --> N
    M --> N

    style H fill:#e3f2fd
    style N fill:#c8e6c9
```

## 5. AI Commit Analysis Flow

```mermaid
flowchart TD
    A[Webhook receives push event] --> B[Extract commits from payload]
    B --> C{For each commit}
    C --> D[Store commit_event in DB]
    D --> E[Load active AI models for workspace]
    E --> F{For each AI model}

    F --> G{Provider type?}
    G -->|Ollama| H[OllamaAdapter.call_json]
    G -->|OpenAI| I[OpenAIAdapter.call_json]
    G -->|Anthropic| J[AnthropicAdapter.call_json]
    G -->|Kimi| K[KimiAdapter.call_json]

    H --> L[Parse JSON response]
    I --> L
    J --> L
    K --> L

    L --> M{Valid response?}
    M -->|Yes| N[Store commit_analysis]
    M -->|No| O[Log error, skip]

    N --> P[Calculate progress_delta]
    P --> Q{progress_delta > 0?}
    Q -->|Yes| R[Update task progress]
    R --> S[Recalculate project progress]
    Q -->|No| T[No progress update]

    S --> U[Create notification]
    T --> U

    style A fill:#fff3e0
    style N fill:#c8e6c9
    style O fill:#ffcdd2
```

## 6. Multi-Tenant Data Isolation

```mermaid
flowchart TD
    A[API Request] --> B[Validate token via<br/>jwt.decode(token, SECRET_KEY) → user_id]
    B --> C[Extract workspace_id from URL path]
    C --> D{Is user a member<br/>of this workspace?}

    D -->|No| E[403 Forbidden]
    D -->|Yes| F[Determine user role in workspace]

    F --> G{Required permission?}

    G -->|Read| H[Allow - all members can read]
    G -->|Write| I{Role >= member?}
    G -->|Admin| J{Role >= admin?}
    G -->|Owner| K{Role == owner?}

    I -->|No| E
    I -->|Yes| L[Allow operation]

    J -->|No| E
    J -->|Yes| L

    K -->|No| E
    K -->|Yes| L

    L --> M[Execute with workspace_id filter]
    M --> N[workspace_id filter enforced<br/>at repository layer]

    style E fill:#ffcdd2
    style L fill:#c8e6c9
    style N fill:#e3f2fd
```

## 7. Frontend State Management

```mermaid
flowchart TD
    subgraph Zustand Stores
        AS[authStore<br/>user, accessToken, refreshToken, loading]
        WS[workspaceStore<br/>workspaces, currentWorkspace]
    end

    subgraph React Query
        RQ1[useQuery: projects]
        RQ2[useQuery: tasks]
        RQ3[useQuery: objectives]
        RQ4[useQuery: notifications]
    end

    subgraph Custom Hooks
        UW[useWorkspaceId<br/>→ workspace UUID]
        UP[useWsPath<br/>→ /v1/workspaces/:ws]
    end

    AS --> UW
    WS --> UW
    UW --> UP
    UP --> RQ1
    UP --> RQ2
    UP --> RQ3
    UP --> RQ4

    RQ1 --> Pages
    RQ2 --> Pages
    RQ3 --> Pages
    RQ4 --> Pages

    style AS fill:#e3f2fd
    style WS fill:#e3f2fd
    style UW fill:#fff3e0
    style UP fill:#fff3e0
```
