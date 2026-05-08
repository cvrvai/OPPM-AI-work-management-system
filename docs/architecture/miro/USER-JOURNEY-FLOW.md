# System — Full User Journey & Feature Flow

> **For:** Miro whiteboard presentation
> **Purpose:** Complete user journey from first landing to daily operations
> **Last updated:** 2026-05-07
> **Color coding:**
> - 🟦 Blue = Auth & Onboarding
> - 🟩 Green = Workspace & Project Management
> - 🟥 Red = AI & Intelligence
> - 🟨 Yellow = Integrations & GitHub
> - 🟪 Purple = OPPM & Reporting
> - ⬜ Gray = External systems

---

## Table of Contents

1. [Master User Journey Map](#1-master-user-journey-map)
2. [Phase 1: Landing & Authentication](#2-phase-1--landing--authentication)
3. [Phase 2: Workspace Onboarding](#3-phase-2--workspace-onboarding)
4. [Phase 3: Project Creation](#4-phase-3--project-creation)
5. [Phase 4: Daily Task Management](#5-phase-4--daily-task-management)
6. [Phase 5: AI-Powered OPPM](#6-phase-5--ai-powered-oppm)
7. [Phase 6: GitHub Integration](#7-phase-6--github-integration)
8. [Phase 7: Team Collaboration](#7-phase-7--team-collaboration)
9. [Phase 8: Reporting & Analytics](#8-phase-8--reporting--analytics)
10. [Feature Flow Matrix](#10-feature-flow-matrix)

---

## 1. Master User Journey Map

**Purpose:** High-level overview of the entire user journey from landing to power user.

```mermaid
flowchart LR
    subgraph "Phase 1: Discovery"
        A1["🌐 Landing Page"] --> A2["🔐 Sign Up / Login"]
        A2 --> A3["📧 Email Verification"]
    end

    subgraph "Phase 2: Onboarding"
        B1["🏢 Create Workspace"] --> B2["👥 Invite Team"]
        B2 --> B3["⚙️ Configure Settings"]
    end

    subgraph "Phase 3: Setup"
        C1["📁 Create Project"] --> C2["📝 Define Tasks"]
        C2 --> C3["📅 Set Timeline"]
        C3 --> C4["👤 Assign Owners"]
    end

    subgraph "Phase 4: Daily Work"
        D1["📋 View Dashboard"] --> D2["✅ Update Tasks"]
        D2 --> D3["🤖 Ask AI Assistant"]
        D3 --> D4["📊 Review OPPM"]
    end

    subgraph "Phase 5: Integration"
        E1["🔗 Connect GitHub"] --> E2["📡 Auto-sync Commits"]
        E2 --> E3["📈 Track Progress"]
    end

    subgraph "Phase 6: Collaboration"
        F1["💬 Team Chat"] --> F2["📎 Share Reports"]
        F2 --> F3["✅ Approve Work"]
    end

    subgraph "Phase 7: Growth"
        G1["📊 Analytics"] --> G2["🎯 Optimize Workflow"]
        G2 --> G3["🏆 Scale Team"]
    end

    A3 --> B1
    B3 --> C1
    C4 --> D1
    D4 --> E1
    E3 --> F1
    F3 --> G1

    style A1 fill:#e1f5fe
    style A2 fill:#e1f5fe
    style A3 fill:#e1f5fe
    style B1 fill:#e8f5e9
    style B2 fill:#e8f5e9
    style B3 fill:#e8f5e9
    style C1 fill:#e8f5e9
    style C2 fill:#e8f5e9
    style C3 fill:#e8f5e9
    style C4 fill:#e8f5e9
    style D1 fill:#fff3e0
    style D2 fill:#fff3e0
    style D3 fill:#ffebee
    style D4 fill:#f3e5f5
    style E1 fill:#fff8e1
    style E2 fill:#fff8e1
    style E3 fill:#fff8e1
    style F1 fill:#e8f5e9
    style F2 fill:#e8f5e9
    style F3 fill:#e8f5e9
    style G1 fill:#f3e5f5
    style G2 fill:#f3e5f5
    style G3 fill:#f3e5f5
```

### Miro Layout Tips
- **Horizontal swimlanes** for each phase
- **Color-coded phases** (see legend above)
- **Arrow thickness** indicates frequency (thick = daily, thin = one-time)
- Add **time estimates** under each phase (e.g., "Phase 1: 2 minutes")

---

## 2. Phase 1: Landing & Authentication

**Purpose:** First-time user experience from landing to authenticated.

```mermaid
flowchart TD
    A["🌐 User visits oppm.app"] --> B{"👤 New or Returning?"}
    
    B --"New"--> C["📄 Landing Page"]
    C --> D["✨ Feature Showcase"]
    D --> E["📝 Sign Up Form"]
    E --> F["📧 Enter Email + Password"]
    F --> G["✅ POST /auth/register"]
    G --> H{"🎉 Success?"}
    H --"No"--> I["❌ Show Error"]
    I --> F
    H --"Yes"--> J["📨 Send Verification Email"]
    J --> K["📧 User clicks link"]
    K --> L["✅ Email Verified"]
    
    B --"Returning"--> M["🔐 Login Form"]
    M --> N["📧 Enter Credentials"]
    N --> O["✅ POST /auth/login"]
    O --> P{"🎉 Valid?"}
    P --"No"--> Q["❌ Show Error"]
    Q --> N
    P --"Yes"--> R["💾 Store JWT Tokens"]
    
    L --> R
    R --> S["🔄 Fetch Workspaces"]
    S --> T{"🏢 Has Workspaces?"}
    T --"No"--> U["🎯 Onboarding Flow"]
    T --"Yes"--> V["📋 Workspace Selector"]
    V --> W["🏠 Dashboard"]
    U --> W

    style A fill:#e1f5fe
    style C fill:#e1f5fe
    style D fill:#e1f5fe
    style E fill:#e1f5fe
    style F fill:#e1f5fe
    style G fill:#e1f5fe
    style H fill:#fff9c4
    style I fill:#ffebee
    style J fill:#e1f5fe
    style K fill:#e1f5fe
    style L fill:#e8f5e9
    style M fill:#e1f5fe
    style N fill:#e1f5fe
    style O fill:#e1f5fe
    style P fill:#fff9c4
    style Q fill:#ffebee
    style R fill:#e8f5e9
    style S fill:#e8f5e9
    style T fill:#fff9c4
    style U fill:#f3e5f5
    style V fill:#e8f5e9
    style W fill:#e8f5e9
```

### Key Decision Points
| # | Decision | Outcome |
|---|----------|---------|
| 1 | New or Returning? | Different flows for registration vs login |
| 2 | Registration success? | Retry on error |
| 3 | Has workspaces? | Skip onboarding if returning user |

### Miro Tips
- Use **2 colors**: Blue for auth steps, Green for success
- Show **loop backs** for error retry
- Add **time estimate**: "Phase 1: 2-5 minutes"

---

## 3. Phase 2: Workspace Onboarding

**Purpose:** First-time workspace setup and team invitation.

```mermaid
flowchart TD
    A["🎯 Onboarding Start"] --> B["🏢 Create Workspace"]
    B --> C["📝 Enter Workspace Name"]
    C --> D["📋 Select Plan"]
    D --> E["✅ POST /workspaces"]
    E --> F["💾 Workspace Created"]
    
    F --> G["👥 Invite Team Members"]
    G --> H["📧 Enter Email Addresses"]
    H --> I["📨 Send Invites"]
    I --> J["⏳ Await Acceptance"]
    
    J --> K["📧 User receives invite"]
    K --> L["🔗 Clicks Accept Link"]
    L --> M{"🔐 Logged In?"}
    M --"No"--> N["🔐 Login / Sign Up"]
    N --> O["✅ Join Workspace"]
    M --"Yes"--> O
    
    O --> P["🎉 Member Added"]
    P --> Q["📊 Workspace Dashboard"]
    
    F --> R["⚙️ Configure Settings"]
    R --> S["🤖 AI Model Selection"]
    S --> T["🔗 GitHub Connection"]
    T --> Q

    style A fill:#f3e5f5
    style B fill:#e8f5e9
    style C fill:#e8f5e9
    style D fill:#e8f5e9
    style E fill:#e8f5e9
    style F fill:#e8f5e9
    style G fill:#e8f5e9
    style H fill:#e8f5e9
    style I fill:#e8f5e9
    style J fill:#fff3e0
    style K fill:#e1f5fe
    style L fill:#e1f5fe
    style M fill:#fff9c4
    style N fill:#e1f5fe
    style O fill:#e8f5e9
    style P fill:#e8f5e9
    style Q fill:#e8f5e9
    style R fill:#fff3e0
    style S fill:#ffebee
    style T fill:#fff8e1
```

### Key Decision Points
| # | Decision | Outcome |
|---|----------|---------|
| 1 | Invitee logged in? | Redirect to login if needed |
| 2 | Plan selection | Free / Pro / Enterprise |

### Miro Tips
- Show **parallel paths**: Invite team + Configure settings happen simultaneously
- Use **dashed arrows** for async steps (email sending)
- Add **role icons**: Admin (👑), Member (👤), Viewer (👁️)

---

## 4. Phase 3: Project Creation

**Purpose:** Creating a new project with full OPPM setup.

```mermaid
flowchart TD
    A["📊 Workspace Dashboard"] --> B["➕ New Project"]
    B --> C["📝 Step 1: Project Info"]
    C --> D["📋 Title, Code, Objective"]
    D --> E["📅 Schedule & Budget"]
    E --> F["👤 Project Lead"]
    F --> G["➡️ Next"]
    
    G --> H["👥 Step 2: Team Assignment"]
    H --> I["📋 Select Members"]
    I --> J["🎭 Assign Roles"]
    J --> K["✅ POST /projects"]
    
    K --> L["💾 Project Created"]
    L --> M["📝 Auto-create OPPM"]
    M --> N["📊 OPPM View"]
    
    N --> O["📝 Add Tasks"]
    O --> P["📅 Set Timeline"]
    P --> Q["👤 Assign Owners"]
    Q --> R["🎯 Define Objectives"]
    R --> S["✅ Project Ready"]
    
    S --> T["📋 Project Dashboard"]

    style A fill:#e8f5e9
    style B fill:#e8f5e9
    style C fill:#fff3e0
    style D fill:#fff3e0
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#fff3e0
    style H fill:#fff3e0
    style I fill:#fff3e0
    style J fill:#fff3e0
    style K fill:#e8f5e9
    style L fill:#e8f5e9
    style M fill:#f3e5f5
    style N fill:#f3e5f5
    style O fill:#f3e5f5
    style P fill:#f3e5f5
    style Q fill:#f3e5f5
    style R fill:#f3e5f5
    style S fill:#e8f5e9
    style T fill:#e8f5e9
```

### Key Decision Points
| # | Decision | Outcome |
|---|----------|---------|
| 1 | Project methodology | Traditional OPPM / Agile / Waterfall |
| 2 | Team roles | Lead, Member, Viewer |

### Miro Tips
- Show **2-step wizard** clearly
- Use **purple** for OPPM-specific steps
- Add **progress bar** visualization

---

## 5. Phase 4: Daily Task Management

**Purpose:** Day-to-day task updates and tracking.

```mermaid
flowchart TD
    A["🏠 Dashboard"] --> B["📋 View Tasks"]
    B --> C{"🎯 Filter?"}
    C --"By Status"--> D["📊 Status Filter"]
    C --"By Owner"--> E["👤 Owner Filter"]
    C --"By Date"--> F["📅 Date Filter"]
    C --"None"--> G["📋 All Tasks"]
    
    D --> G
    E --> G
    F --> G
    
    G --> H["📝 Select Task"]
    H --> I["📊 Task Detail"]
    I --> J{"✏️ Action?"}
    
    J --"Update Status"--> K["🔄 Change Status"]
    K --> L["💾 Save"]
    
    J --"Add Report"--> M["📝 Write Report"]
    M --> N["📡 Submit"]
    N --> O["👀 Await Approval"]
    
    J --"Edit Details"--> P["✏️ Modify Task"]
    P --> L
    
    J --"View History"--> Q["📜 Activity Log"]
    Q --> I
    
    L --> R["🔄 Update OPPM"]
    R --> S["📊 Refresh Dashboard"]
    
    O --> T{"✅ Approved?"}
    T --"Yes"--> S
    T --"No"--> U["📝 Revise Report"]
    U --> M

    style A fill:#e8f5e9
    style B fill:#e8f5e9
    style C fill:#fff9c4
    style D fill:#fff3e0
    style E fill:#fff3e0
    style F fill:#fff3e0
    style G fill:#e8f5e9
    style H fill:#e8f5e9
    style I fill:#e8f5e9
    style J fill:#fff9c4
    style K fill:#fff3e0
    style L fill:#e8f5e9
    style M fill:#fff3e0
    style N fill:#e8f5e9
    style O fill:#fff3e0
    style P fill:#fff3e0
    style Q fill:#e8f5e9
    style R fill:#f3e5f5
    style S fill:#e8f5e9
    style T fill:#fff9c4
    style U fill:#ffebee
```

### Key Decision Points
| # | Decision | Outcome |
|---|----------|---------|
| 1 | Filter type? | Status / Owner / Date / None |
| 2 | Action on task? | Update / Report / Edit / History |
| 3 | Report approved? | Revise if rejected |

### Miro Tips
- Show **4 filter options** as branches
- Use **diamond** for action selection
- Show **approval loop** clearly

---

## 6. Phase 5: AI-Powered OPPM

**Purpose:** Using AI to create, fill, and manage OPPM sheets.

```mermaid
flowchart TD
    A["📊 OPPM View"] --> B["🤖 Open AI Chat"]
    B --> C["💬 Type Request"]
    
    C --"Fill the form"--> D["📝 AI Analyzes Project"]
    D --> E["📋 Generates Actions"]
    E --> F["✅ Execute Sheet Actions"]
    F --> G["📊 OPPM Updated"]
    
    C --"Make it standard"--> H["🔧 AI Applies Template"]
    H --> I["📋 Standard Formatting"]
    I --> G
    
    C --"Add task"--> J["➕ AI Creates Task"]
    J --> K["📝 Adds to Sheet"]
    K --> G
    
    C --"Update timeline"--> L["📅 AI Sets Timeline"]
    L --> M["🎯 Updates Status"]
    M --> G
    
    C --"Recreate form"--> N["🗑️ Clear Sheet"]
    N --> O["🏗️ Scaffold Form"]
    O --> G
    
    G --> P{"✅ Satisfied?"}
    P --"No"--> Q["💬 Refine Request"]
    Q --> C
    P --"Yes"--> R["💾 Save Changes"]

    style A fill:#f3e5f5
    style B fill:#ffebee
    style C fill:#ffebee
    style D fill:#ffebee
    style E fill:#ffebee
    style F fill:#ffebee
    style G fill:#f3e5f5
    style H fill:#ffebee
    style I fill:#ffebee
    style J fill:#ffebee
    style K fill:#ffebee
    style L fill:#ffebee
    style M fill:#ffebee
    style N fill:#ffebee
    style O fill:#ffebee
    style P fill:#fff9c4
    style Q fill:#ffebee
    style R fill:#e8f5e9
```

### AI Request Types
| Request | AI Action | Result |
|---------|-----------|--------|
| "Fill the form" | Analyzes project data → generates actions | Complete OPPM |
| "Make it standard" | Applies template rules | Standardized formatting |
| "Add task X" | Creates task row | New task added |
| "Update timeline" | Sets status dots | Timeline updated |
| "Recreate form" | Clears + scaffolds | Fresh form |

### Miro Tips
- Use **red** for AI steps
- Show **5 request types** as branches
- Add **feedback loop** for refinement

---

## 7. Phase 6: GitHub Integration

**Purpose:** Connecting GitHub for automatic commit tracking.

```mermaid
flowchart TD
    A["⚙️ Settings"] --> B["🔗 GitHub Settings"]
    B --> C["🔐 Connect Account"]
    C --> D["🐙 OAuth to GitHub"]
    D --> E["✅ Authorize App"]
    E --> F["📋 Select Repositories"]
    F --> G["💾 Store Config"]
    
    G --> H["🐙 Developer Pushes Code"]
    H --> I["📡 GitHub Webhook"]
    I --> J["🟥 Receive Payload"]
    J --> K["✅ Validate HMAC"]
    K --> L["💾 Store Commit"]
    
    L --> M["🟥 Call AI Analysis"]
    M --> N["🟩 Analyze vs Project"]
    N --> O["💾 Store Analysis"]
    
    O --> P["📊 Commits View"]
    P --> Q["📈 Impact Score"]
    Q --> R["🎯 Suggested Tasks"]

    style A fill:#fff3e0
    style B fill:#fff8e1
    style C fill:#fff8e1
    style D fill:#fff8e1
    style E fill:#fff8e1
    style F fill:#fff8e1
    style G fill:#fff8e1
    style H fill:#e1f5fe
    style I fill:#fff8e1
    style J fill:#fff8e1
    style K fill:#fff8e1
    style L fill:#fff8e1
    style M fill:#fff8e1
    style N fill:#ffebee
    style O fill:#ffebee
    style P fill:#e8f5e9
    style Q fill:#e8f5e9
    style R fill:#e8f5e9
```

### Key Decision Points
| # | Decision | Outcome |
|---|----------|---------|
| 1 | Repository selection | Which repos to track |
| 2 | Webhook validation | HMAC-SHA256 check |

### Miro Tips
- Show **2 phases**: Setup (yellow) + Runtime (green)
- Use **dashed arrows** for webhook flow
- Add **GitHub icon** 🐙

---

## 8. Phase 7: Team Collaboration

**Purpose:** Team communication and approval workflows.

```mermaid
flowchart TD
    A["👤 Member"] --> B["📝 Submits Report"]
    B --> C["📡 POST /reports"]
    C --> D["💾 Report Stored"]
    D --> E["🔔 Notify Lead"]
    
    E --> F["👤 Lead Reviews"]
    F --> G{"✅ Approve?"}
    
    G --"Yes"--> H["✅ PATCH /approve"]
    H --> I["💾 Update Status"]
    I --> J["🔔 Notify Member"]
    J --> K["📊 Dashboard Updated"]
    
    G --"No"--> L["📝 Request Changes"]
    L --> M["🔔 Notify Member"]
    M --> N["📝 Member Revises"]
    N --> B
    
    K --> O["💬 Team Chat"]
    O --> P["📎 Share Files"]
    P --> Q["📊 View Analytics"]

    style A fill:#e1f5fe
    style B fill:#fff3e0
    style C fill:#e8f5e9
    style D fill:#e8f5e9
    style E fill:#fff3e0
    style F fill:#e1f5fe
    style G fill:#fff9c4
    style H fill:#e8f5e9
    style I fill:#e8f5e9
    style J fill:#fff3e0
    style K fill:#e8f5e9
    style L fill:#ffebee
    style M fill:#fff3e0
    style N fill:#e1f5fe
    style O fill:#e8f5e9
    style P fill:#e8f5e9
    style Q fill:#e8f5e9
```

### Key Decision Points
| # | Decision | Outcome |
|---|----------|---------|
| 1 | Approve report? | Yes → notify + update / No → request changes |

### Miro Tips
- Show **2 actors** (Member + Lead)
- Use **loop back** for revision cycle
- Add **notification icons** 🔔

---

## 9. Phase 8: Reporting & Analytics

**Purpose:** Viewing project health and generating reports.

```mermaid
flowchart TD
    A["📊 Dashboard"] --> B{"📈 Report Type?"}
    
    B --"Project Health"--> C["🎯 Status Overview"]
    C --> D["📊 Progress Bars"]
    D --> E["🚦 Risk Indicators"]
    
    B --"Task Analytics"--> F["📋 Task Breakdown"]
    F --> G["⏱️ Time Tracking"]
    G --> H["👤 Workload Distribution"]
    
    B --"OPPM Export"--> I["📄 Generate PDF"]
    I --> J["📊 Generate Excel"]
    J --> K["💾 Download"]
    
    B --"Git Insights"--> L["🐙 Commit Activity"]
    L --> M["📈 Code Velocity"]
    M --> N["🎯 Impact Analysis"]
    
    E --> O["📊 Final Report"]
    H --> O
    K --> O
    N --> O
    
    O --> P["💾 Save / Share"]
    P --> Q["📧 Email Report"]
    P --> R["🔗 Share Link"]

    style A fill:#e8f5e9
    style B fill:#fff9c4
    style C fill:#f3e5f5
    style D fill:#f3e5f5
    style E fill:#f3e5f5
    style F fill:#f3e5f5
    style G fill:#f3e5f5
    style H fill:#f3e5f5
    style I fill:#f3e5f5
    style J fill:#f3e5f5
    style K fill:#f3e5f5
    style L fill:#f3e5f5
    style M fill:#f3e5f5
    style N fill:#f3e5f5
    style O fill:#e8f5e9
    style P fill:#e8f5e9
    style Q fill:#e1f5fe
    style R fill:#e1f5fe
```

### Report Types
| Type | Data | Format |
|------|------|--------|
| Project Health | Status, progress, risks | Dashboard |
| Task Analytics | Breakdown, time, workload | Charts |
| OPPM Export | Full OPPM form | PDF / Excel |
| Git Insights | Commits, velocity, impact | Charts |

### Miro Tips
- Show **4 report branches**
- Use **purple** for analytics
- Add **export icons** 📄 📊

---

## 10. Feature Flow Matrix

**Purpose:** Cross-reference all features with their flows.

| Feature | Phase | Entry Point | Key Flow | Complexity |
|---------|-------|-------------|----------|------------|
| **Sign Up** | 1 | Landing page | Register → Verify → Login | Low |
| **Login** | 1 | Landing page | Credentials → JWT → Dashboard | Low |
| **Create Workspace** | 2 | Onboarding | Name → Plan → Invite | Medium |
| **Invite Members** | 2 | Workspace settings | Email → Link → Accept | Medium |
| **Create Project** | 3 | Dashboard | Wizard → Team → OPPM | Medium |
| **Add Tasks** | 4 | Project view | Form → Save → Update OPPM | Low |
| **Update Status** | 4 | Task detail | Select → Save → Refresh | Low |
| **Submit Report** | 4 | Task detail | Write → Submit → Await approval | Medium |
| **Approve Report** | 7 | Notifications | Review → Approve/Reject → Notify | Medium |
| **AI Fill OPPM** | 5 | AI Chat | Request → Analyze → Execute | High |
| **AI Make Standard** | 5 | AI Chat | Request → Template → Apply | Medium |
| **AI Add Task** | 5 | AI Chat | Request → Generate → Insert | Low |
| **Connect GitHub** | 6 | Settings | OAuth → Select repos → Webhook | Medium |
| **View Commits** | 6 | Commits tab | Push → Analyze → Display | Medium |
| **Export OPPM** | 8 | OPPM view | Generate → Download | Low |
| **View Analytics** | 8 | Dashboard | Select → Filter → Display | Medium |
| **Team Chat** | 7 | Chat panel | Message → Send → Receive | Low |
| **Update Profile** | 2 | Settings | Edit → Save → Confirm | Low |
| **Switch Workspace** | 2 | Header dropdown | Select → Load → Refresh | Low |

### Miro Tips
- Create **table sticky notes** for each row
- Use **color coding** for complexity (Green=Low, Yellow=Medium, Red=High)
- Group by **phase** with frames

---

## Miro Board Layout Recommendation

```
┌─────────────────────────────────────────────────────────────┐
│  BOARD 1: Master Journey (High-Level)                     │
│  - Phase 1-7 horizontal flow                                │
│  - Color-coded swimlanes                                    │
│  - Time estimates per phase                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  BOARD 2: Authentication & Onboarding (Phase 1-2)         │
│  - Landing → Login/Register → Verify → Workspace            │
│  - Invite flow detail                                       │
│  - Decision diamonds for auth states                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  BOARD 3: Project Lifecycle (Phase 3-4)                     │
│  - Creation wizard (2 steps)                                │
│  - Task management daily flow                               │
│  - Report submission & approval                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  BOARD 4: AI & Integrations (Phase 5-6)                   │
│  - AI chat flow (5 request types)                           │
│  - GitHub connection & webhook                              │
│  - Commit analysis pipeline                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  BOARD 5: Collaboration & Analytics (Phase 7-8)             │
│  - Team collaboration flow                                  │
│  - Reporting & export options                               │
│  - Feature flow matrix table                                │
└─────────────────────────────────────────────────────────────┘
```

---

## How to Import into Miro

### Option 1: Mermaid Import (Recommended)
1. Open Miro board
2. Add **Mermaid Chart** widget
3. Copy-paste any Mermaid block from this document
4. Miro auto-generates the diagram
5. Adjust colors and layout as needed

### Option 2: Manual Drawing
1. Create **frames** for each phase
2. Use **sticky notes** for each step
3. Use **arrows** for connections
4. Add **decision diamonds** for branches
5. Use **color coding** from legend

### Color Palette
| Color | Hex | Use |
|-------|-----|-----|
| Blue | #E1F5FE | Auth & external |
| Green | #E8F5E9 | Workspace & success |
| Yellow | #FFF3E0 | Forms & input |
| Red | #FFEBEE | AI & processing |
| Purple | #F3E5F5 | OPPM & analytics |
| Gray | #F5F5F5 | External systems |

---

*Last updated: 2026-05-07*
*Version: 1.0*
