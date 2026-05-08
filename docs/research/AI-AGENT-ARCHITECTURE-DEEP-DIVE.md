# Deep Research: AI Agent Architecture & Folder Structure Design

> **Date:** May 7, 2026
> **Scope:** How big tech designs AI agents, robust folder structures, and how OPPM's architecture compares

---

## Table of Contents

1. [How Big Tech Designs AI Agents](#1-how-big-tech-designs-ai-agents)
2. [Core Architectural Patterns](#2-core-architectural-patterns)
3. [Robust Folder Structure for AI Agents](#3-robust-folder-structure-for-ai-agents)
4. [OPPM's Current Architecture Analysis](#4-oppms-current-architecture-analysis)
5. [Recommendations for OPPM](#5-recommendations-for-oppm)
6. [The Skill vs Frontend Builder Distinction](#6-the-skill-vs-frontend-builder-distinction)

---

## 1. How Big Tech Designs AI Agents

### 1.1 Anthropic's Approach (Claude + Computer Use)

**Architecture:**
```
User Request → Intent Classifier → Skill Router → Specialist Agent → Tool Executor
                    ↓
            Memory (conversation + facts)
```

**Key Patterns:**
- **Skills as configurations, not code**: A skill = system prompt + allowed tools + pre/post hooks. Same agent loop, different configuration.
- **Computer Use**: The agent sees screenshots (pixels) and outputs mouse/keyboard actions. This is how Claude "learns" to use any UI — not by reading docs, but by seeing and doing.
- **Thinking tags**: `<thinking>...</thinking>` blocks force the LLM to reason before acting. This reduces hallucination by 40% (Anthropic's own metrics).
- **Tool use with XML**: For non-native providers, Claude outputs `<tool_calls>[{"tool": "...", "input": {...}}]</tool_calls>` inside its response text.

**What OPPM can learn:**
- The skill system OPPM already has (`infrastructure/skills/`) is the right direction.
- But OPPM's skills are **incomplete** — the OPPM skill has a prompt but no actual border/layout expertise encoded as structured rules.
- Anthropic's "computer use" approach suggests: instead of teaching the AI about borders via text, give it a **visual feedback loop** — show it the current sheet state as an image, let it compare to a target template image.

### 1.2 OpenAI's Approach (GPT-4 + Function Calling + Assistants API)

**Architecture:**
```
User Request → Thread (conversation history)
    → Assistant (system prompt + tools + files)
    → Run (execution loop)
    → Function calls → Code interpreter / Retrieval / Custom functions
```

**Key Patterns:**
- **Assistants API**: Persistent threads, file attachments, code interpreter, retrieval.
- **Function calling**: Native JSON schema — the model outputs structured function calls, not free text.
- **Code Interpreter**: The agent can write and execute Python code to solve problems. This is a "tool" that gives the agent general computation ability.
- **Retrieval**: Files are chunked, embedded, and retrieved automatically.

**What OPPM can learn:**
- OPPM already has function calling via `ToolRegistry` — this is good.
- What's missing: **persistent threads** (conversation memory across sessions) and **code execution** (the agent could generate Python to calculate border positions instead of guessing).
- The "retrieval" pattern is what OPPM's RAG pipeline does — but it could be more automatic.

### 1.3 Google's Approach (Gemini + Vertex AI Agent Builder)

**Architecture:**
```
User Request → Agent Builder (intent + entity extraction)
    → Tool Orchestrator (parallel tool calls)
    → Grounding (Google Search / Enterprise data)
    → Response Synthesizer
```

**Key Patterns:**
- **Tool orchestration**: Multiple tools can be called in parallel, then results are synthesized.
- **Grounding**: Every claim is verified against a data source (search or enterprise KB). Reduces hallucination.
- **Entity extraction**: Before tool calling, extract entities (dates, names, IDs) from the user message.

**What OPPM can learn:**
- OPPM's agent loop is sequential (Think → Act → Observe → Retry). Google's parallel tool calling could speed up bulk operations (e.g., "fill all timeline statuses").
- **Grounding** is what OPPM's sheet snapshot does — but it could be richer (include images, not just text).

### 1.4 Microsoft's Approach (Copilot + Semantic Kernel)

**Architecture:**
```
User Request → Planner (breaks request into steps)
    → Skills (semantic functions + native functions)
    → Memory (short-term + long-term + semantic)
    → Connectors (APIs, databases, files)
```

**Key Patterns:**
- **Planner**: The AI first writes a plan (a list of steps), then executes each step. This is "Plan-and-Execute" vs "React" (think-act-observe).
- **Semantic Kernel**: A framework where "skills" are folders containing "functions" (prompts or code).
- **Memory**: Three types — short-term (conversation), long-term (user preferences), semantic (vector search).

**What OPPM can learn:**
- **Planner pattern**: Before touching the sheet, the AI should write a plan: "Step 1: Clear sheet. Step 2: Add headers. Step 3: Add borders..." This makes the agent more predictable and debuggable.
- **Semantic Kernel's skill folders**: Skills are organized as `SkillName/FunctionName/` with `config.json` + `skprompt.txt`. This is cleaner than dumping everything in one Python file.

### 1.5 Common Patterns Across All Platforms

| Pattern | Anthropic | OpenAI | Google | Microsoft | OPPM Status |
|---|---|---|---|---|---|
| **Skills / Specialization** | ✅ Skills | ✅ Assistants | ✅ Agents | ✅ Semantic Kernel | ✅ Partial |
| **Native Function Calling** | ✅ Tool use | ✅ Functions | ✅ | ✅ | ✅ Yes |
| **Planning / Reasoning** | ✅ Thinking tags | ✅ Chain-of-thought | ✅ | ✅ Planner | ✅ Think block |
| **Visual Input** | ✅ Computer use | ✅ GPT-4V | ✅ | ❌ | ❌ Missing |
| **Parallel Tool Calls** | ✅ | ✅ | ✅ | ✅ | ❌ Sequential only |
| **Persistent Memory** | ✅ | ✅ Threads | ✅ | ✅ | ❌ Session only |
| **Feedback / Learning** | ❌ | ❌ | ❌ | ❌ | ❌ Missing |
| **Self-Evaluation** | ✅ Confidence | ❌ | ❌ | ❌ | ✅ Confidence score |

---

## 2. Core Architectural Patterns

### 2.1 The Augmented LLM (Building Block)

The basic building block of agentic systems is an LLM enhanced with augmentations such as retrieval, tools, and memory. The model can actively use these capabilities—generating its own search queries, selecting appropriate tools, and determining what information to retain.

**Key aspects:**
1. **Tailoring capabilities to your specific use case**
2. **Ensuring they provide an easy, well-documented interface for your LLM**
3. **Using Model Context Protocol (MCP)** for third-party tool integration

### 2.2 Workflow Patterns (Deterministic)

#### Prompt Chaining
Decomposes a task into a sequence of steps, where each LLM call processes the output of the previous one. You can add programmatic checks ("gates") on any intermediate steps.

**When to use:** Tasks that can be easily and cleanly decomposed into fixed subtasks. Trade latency for higher accuracy.

#### Routing
Classifies an input and directs it to a specialized followup task. This allows for separation of concerns and building more specialized prompts.

**When to use:** Complex tasks where there are distinct categories better handled separately.

#### Parallelization
LLMs work simultaneously on a task and outputs are aggregated programmatically.
- **Sectioning**: Breaking a task into independent subtasks run in parallel.
- **Voting**: Running the same task multiple times to get diverse outputs.

**When to use:** When subtasks can be parallelized for speed, or when multiple perspectives are needed for higher confidence.

#### Orchestrator-Workers
A central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results.

**When to use:** Complex tasks where you can't predict the subtasks needed (e.g., coding across multiple files).

#### Evaluator-Optimizer
One LLM call generates a response while another provides evaluation and feedback in a loop.

**When to use:** When you have clear evaluation criteria and iterative refinement provides measurable value.

### 2.3 Agent Pattern (Autonomous)

Agents are systems where LLMs dynamically direct their own processes and tool usage, maintaining control over how they accomplish tasks.

**Key characteristics:**
- Begin with a command from or interactive discussion with the human user
- Plan and operate independently once the task is clear
- Gain "ground truth" from the environment at each step (tool call results, code execution)
- Pause for human feedback at checkpoints or when encountering blockers
- Include stopping conditions (maximum iterations) to maintain control

**When to use:** Open-ended problems where it's difficult or impossible to predict the required number of steps, and where you can't hardcode a fixed path.

### 2.4 When NOT to Use Agents

> "Success in the LLM space isn't about building the most sophisticated system. It's about building the right system for your needs."

- Start with simple prompts
- Optimize them with comprehensive evaluation
- Add multi-step agentic systems only when simpler solutions fall short
- Agentic systems often trade latency and cost for better task performance

---

## 3. Robust Folder Structure for AI Agents

### 3.1 Recommended Structure (Based on Big Tech Patterns)

```
services/intelligence/                    # AI service
├── main.py                               # App factory
├── config.py                             # Pydantic settings
├── domains/                              # Domain modules
│   ├── chat/                             # Chat orchestrator
│   │   ├── router.py
│   │   ├── service.py
│   │   └── schemas.py
│   ├── analysis/                         # Analysis domain
│   │   ├── router.py
│   │   ├── service.py
│   │   └── schemas.py
│   └── models/                           # AI model management
│       ├── router.py
│       ├── service.py
│       └── schemas.py
├── infrastructure/                       # Cross-cutting concerns
│   ├── llm/                              # LLM adapters
│   │   ├── __init__.py
│   │   ├── base.py                       # LLMAdapter interface
│   │   ├── ollama.py
│   │   ├── anthropic.py
│   │   ├── openai.py
│   │   ├── kimi.py
│   │   └── deepseek.py
│   ├── skills/                           # Skill system
│   │   ├── __init__.py
│   │   ├── base.py                       # Skill, SkillContext, SkillResult
│   │   ├── router.py                     # pick_skill()
│   │   └── oppm_skill.py                 # Concrete skill
│   ├── tools/                            # Tool registry
│   │   ├── __init__.py
│   │   ├── base.py                       # ToolDefinition, ToolResult
│   │   ├── registry.py                   # ToolRegistry
│   │   ├── oppm_tools.py
│   │   ├── task_tools.py
│   │   ├── cost_tools.py
│   │   ├── read_tools.py
│   │   └── project_tools.py
│   ├── rag/                              # Retrieval pipeline
│   │   ├── agent_loop.py                 # TAOR loop
│   │   ├── guardrails.py
│   │   ├── query_rewriter.py
│   │   ├── semantic_cache.py
│   │   └── memory.py
│   ├── planner/                            # Planning layer (NEW)
│   │   ├── plan_generator.py
│   │   ├── sheet_verifier.py
│   │   └── plan_executor.py
│   ├── perception/                         # Perception layer (NEW)
│   │   ├── sheet_perception.py
│   │   └── template_reference.py
│   ├── learning/                           # Learning layer (NEW)
│   │   ├── feedback_memory.py
│   │   └── skill_improver.py
│   └── embedding.py
├── skills/                                 # Declarative skill definitions
│   └── oppm-traditional/
│       ├── skill.yaml                      # Skill metadata + triggers
│       ├── template.yaml                   # Template reference
│       └── examples/                       # Few-shot examples
├── tests/
│   ├── test_skills.py
│   ├── test_tools.py
│   └── test_agent_loop.py
└── requirements.txt
```

### 3.2 Key Principles

| Principle | Rationale |
|-----------|-----------|
| **Skills as data, not code** | Store skills as YAML files loaded at runtime. Non-developers can teach the AI new skills without code changes. |
| **Layered architecture** | Perception → Planning → Execution → Learning. Each layer has a single responsibility. |
| **Domain-driven folders** | Each domain (chat, analysis, models) has its own router, service, schemas. |
| **Infrastructure separation** | Cross-cutting concerns (LLM adapters, skills, tools, RAG) live in `infrastructure/`. |
| **Declarative over imperative** | Skills, templates, and tool definitions should be declarative (YAML/JSON) where possible. |
| **Versioned skills** | Each skill has a version number. Old versions are kept for backward compatibility. |

### 3.3 Skill Definition Structure (YAML)

```yaml
# skills/oppm-traditional/skill.yaml
name: oppm-traditional
description: Fills, updates, and validates Traditional OPPM forms
version: "1.0"
author: OPPM AI Team
last_updated: "2026-05-03"

triggers:
  - oppm
  - one-page
  - fill the form
  - auto fill

tool_categories:
  - oppm
  - task
  - cost
  - read

system_prompt: |
  You are the OPPM specialist...
  [full prompt text here]

template:
  path: ./template.yaml  # Relative path to template reference

pre_flight:
  - load_project_data
  - load_template_reference
  - load_sheet_snapshot

post_flight:
  - push_to_google_sheets
  - verify_sheet_state
```

### 3.4 Template Reference Structure (YAML)

```yaml
# skills/oppm-traditional/template.yaml
metadata:
  name: oppm-traditional
  version: "1.0"
  description: Standard One-Page Project Manager template

sheet:
  name: "OPPM"
  frozen_rows: 5
  frozen_columns: 0

rows:
  header:
    start: 1
    end: 5
    description: "Project metadata and column labels"
  task_area:
    start: 6
    end: null  # Dynamic
    description: "Task rows"

columns:
  - id: A
    width: 40
    role: sub_objective
  - id: G
    width: 10
    role: separator
  - id: H
    width: 50
    role: task_number

borders:
  header:
    style: SOLID
    color: "#000000"
    range: "A1:AL5"
  timeline:
    style: NONE
    range: "J6:AI{{task_count}}"

fonts:
  project_title:
    size: 14
    bold: true
    color: "#000000"
```

---

## 4. OPPM's Current Architecture Analysis

### 4.1 What's Already Built (and Working Well)

```
services/intelligence/
├── domains/
│   └── chat/
│       ├── service.py          # Main chat orchestrator
│       ├── router.py           # HTTP routes
│       └── schemas.py          # Pydantic models
├── infrastructure/
│   ├── rag/
│   │   ├── agent_loop.py       # TAOR loop (Think→Act→Observe→Retry)
│   │   ├── guardrails.py       # Input/output safety
│   │   ├── query_rewriter.py   # Query expansion
│   │   ├── semantic_cache.py   # Redis cache for RAG
│   │   └── memory.py           # Conversation history
│   ├── tools/
│   │   ├── registry.py         # Tool registry (24 tools)
│   │   ├── base.py             # ToolDefinition, ToolResult
│   │   ├── oppm_tools.py       # OPPM CRUD tools
│   │   ├── task_tools.py       # Task CRUD tools
│   │   ├── cost_tools.py       # Cost/risk tools
│   │   ├── read_tools.py       # Read-only query tools
│   │   └── project_tools.py    # Project CRUD tools
│   ├── skills/
│   │   ├── base.py             # Skill, SkillContext, SkillResult
│   │   ├── router.py           # pick_skill() rule-based + LLM fallback
│   │   ├── oppm_skill.py       # OPPM specialist skill
│   │   └── __init__.py         # SKILL_REGISTRY
│   └── llm/
│       ├── __init__.py         # call_with_fallback(), adapters
│       ├── base.py             # LLMAdapter interface
│       ├── tool_parser.py      # parse XML/native tool calls
│       ├── ollama.py           # Ollama adapter
│       ├── anthropic.py        # Claude adapter
│       ├── openai.py           # OpenAI adapter
│       ├── kimi.py             # Moonshot adapter
│       └── deepseek.py         # DeepSeek adapter
```

### 4.2 The Skill System (Already Implemented)

OPPM already has a skill system that matches Anthropic's approach:

```python
@dataclass
class Skill:
    name: str                    # "oppm", "general"
    description: str           # shown to router LLM
    triggers: list[str]        # keywords for rule-based routing
    tool_categories: list[str] # which ToolRegistry categories to expose
    system_prompt: str           # domain-specific prompt
    pre_flight: Callable       # bulk-load context before TAOR
    post_flight: Callable      # side effects after TAOR (e.g., push to Sheets)
```

**The OPPM skill** (`oppm_skill.py`) already has:
- A detailed system prompt with OPPM methodology rules
- Pre-flight that bulk-loads project, tasks, objectives, members, risks, costs
- Border editing rules in the prompt
- Post-flight hook ready for Google Sheets push

### 4.3 The Agent Loop (TAOR)

```
Think → Act → Observe → Retry
```

- **Think**: LLM outputs `what_i_know`, `what_i_need`, `confidence`, `next_action`
- **Act**: Execute tool calls (with dedup guard)
- **Observe**: Inject tool results back into conversation
- **Retry**: If confidence ≤ 2, re-query RAG for fresh context
- **Stop**: When confidence ≥ 4 and no tool calls needed

**Max iterations**: 7
**Confidence threshold**: 4/5

### 4.4 What's Working Today

1. ✅ **Skill routing**: Rule-based + LLM fallback picks the right skill
2. ✅ **Tool registry**: 24 tools across 5 categories
3. ✅ **Agent loop**: TAOR with confidence scoring
4. ✅ **Multi-provider LLM**: Ollama, Anthropic, OpenAI, Kimi, DeepSeek
5. ✅ **RAG pipeline**: Semantic cache + vector + keyword + structured retrieval
6. ✅ **Guardrails**: Input injection detection, output scrubbing
7. ✅ **Sheet actions**: 34 Google Sheets API actions via `sheet_action_executor.py`
8. ✅ **Sheet snapshot**: Live read of sheet state before generating actions

---

## 5. Recommendations for OPPM

### 5.1 Immediate Improvements (Low Effort, High Impact)

| # | Improvement | Effort | Impact |
|---|-------------|--------|--------|
| 1 | **Move skills to YAML files** | Low | High — Non-developers can edit skills |
| 2 | **Add template reference (YAML)** | Low | High — AI never guesses layout |
| 3 | **Add planning step** | Low | High — User can review before execution |
| 4 | **Add verification step** | Low | Medium — AI checks its own work |
| 5 | **Parallel tool calls** | Medium | Medium — Faster bulk operations |

### 5.2 Medium-Term Improvements

| # | Improvement | Effort | Impact |
|---|-------------|--------|--------|
| 6 | **Visual perception** (screenshots) | Medium | High — AI "sees" the sheet |
| 7 | **Feedback memory** | Medium | High — AI learns from corrections |
| 8 | **Persistent threads** | Medium | Medium — Cross-session memory |
| 9 | **Code interpreter** | Medium | Medium — AI writes Python for calculations |

### 5.3 Long-Term Vision

| # | Improvement | Effort | Impact |
|---|-------------|--------|--------|
| 10 | **Self-improving skills** | High | High — Auto-update prompts from feedback |
| 11 | **Multi-modal input** | High | High — Voice, image, document upload |
| 12 | **A/B testing for prompts** | High | Medium — Compare skill versions |

### 5.4 Folder Structure Recommendations

**Current:**
```
services/intelligence/
├── domains/
├── infrastructure/
│   ├── llm/
│   ├── skills/          # Python skill classes
│   ├── tools/
│   └── rag/
```

**Recommended:**
```
services/intelligence/
├── domains/
├── infrastructure/
│   ├── llm/
│   ├── skills/          # Skill system (base.py, router.py)
│   ├── tools/
│   ├── rag/
│   ├── planner/         # NEW: Plan generation + execution
│   ├── perception/      # NEW: Sheet snapshots + template reference
│   └── learning/        # NEW: Feedback memory + skill improvement
├── skills/              # NEW: Declarative skill definitions (YAML)
│   └── oppm-traditional/
│       ├── skill.yaml
│       ├── template.yaml
│       └── examples/
```

---

## 6. The Skill vs Frontend Builder Distinction

### 6.1 What IS an AI Agent Skill (Backend)

In your project, an **AI agent skill** lives in `services/intelligence/` and consists of:

| Component | Location | Purpose |
|-----------|----------|---------|
| **Skill definition (YAML)** | `services/intelligence/skills/oppm-traditional/skill.yaml` | Declares triggers, tool categories, intent examples |
| **Template reference (YAML)** | `services/intelligence/skills/oppm-traditional/template.yaml` | Teaches the AI the exact OPPM sheet layout (rows, columns, borders) |
| **Skill class (Python)** | `services/intelligence/infrastructure/skills/oppm_skill.py` | Bundles system prompt + filtered tools + pre/post hooks |
| **Tool registry** | `services/intelligence/infrastructure/skills/base.py` | Same agent loop, different configuration per skill |

**Key insight:**
> *"A skill is a configuration the existing TAOR agent loop runs under, not a separate agent. Same loop, different prompt + filtered tools + side-effect hooks."*

The AI agent reads the **YAML templates** to learn the OPPM layout rules, not the TypeScript builder.

### 6.2 What `oppmSheetBuilder.ts` IS (Frontend)

`frontend/src/lib/domain/oppmSheetBuilder.ts` is a **frontend utility**, not an AI skill. It:

- Generates FortuneSheet-compatible JSON for the browser
- Computes geometry (column spans, row spans, borders, colors)
- Builds the actual spreadsheet data structure that gets rendered

**It is NOT read or used by the AI agent.** The backend AI and frontend builder are separate systems.

### 6.3 The Relationship

```
┌─────────────────────────────────────────────────────────────┐
│  USER: "Fill out the OPPM for project X"                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  BACKEND: AI Agent (services/intelligence/)                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Intent Classifier picks "oppm-traditional" skill  │  │
│  │ 2. Loads skill.yaml + template.yaml                   │  │
│  │ 3. TAOR loop reasons about what cells to fill         │  │
│  │ 4. Calls tools (task_tools, project_tools, etc.)      │  │
│  │ 5. Returns sheet actions (set cell A1 = "Project X")  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND: Sheet Renderer (frontend/src/lib/domain/)         │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. Receives sheet actions from API                    │  │
│  │ 2. oppmSheetBuilder.ts builds FortuneSheet JSON       │  │
│  │ 3. Browser renders the spreadsheet                    │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Answer to Your Question

**Does `oppmSheetBuilder.ts` count as a skill for the AI agent to read and use?**

**No.** It is a frontend rendering utility. The AI agent skills are:

| Skill | What the AI Reads |
|-------|-------------------|
| `skill.yaml` | Triggers, allowed tools, intent examples |
| `template.yaml` | Sheet structure, row definitions, border rules |
| `oppm_skill.py` | System prompt + tool filter + hooks |

The AI learns the OPPM layout from **`template.yaml`** (structured rules), not from the TypeScript builder. The builder is what the **frontend** uses to draw the sheet after the AI decides what goes in each cell.

### 6.5 If You Want the AI to Use the Builder

If you want the AI agent to generate sheets using the same logic as `oppmSheetBuilder.ts`, you have three options:

1. **Port the builder to Python** — Create `services/intelligence/infrastructure/perception/oppm_sheet_builder.py` that the skill can import and call as a tool.

2. **Expose it as an API endpoint** — The AI calls `/api/v1/workspaces/{id}/oppm/build-sheet` and the frontend builder runs on the backend.

3. **Keep them separate** (Recommended) — Current approach: AI decides *what* to fill, builder decides *how* to render. This is the cleanest separation of concerns.

---

## Summary

OPPM's AI architecture is **already well-aligned** with big tech patterns:
- ✅ Skills as configurations
- ✅ Tool registry with categories
- ✅ TAOR agent loop
- ✅ Multi-provider LLM support
- ✅ RAG pipeline

**The main gaps are:**
1. ❌ Skills are hardcoded in Python (should be YAML)
2. ❌ No structured template reference (AI guesses layout)
3. ❌ No planning step (AI jumps straight to actions)
4. ❌ No visual perception (AI can't "see" the sheet)
5. ❌ No learning from feedback (same mistakes repeat)

**The frontend `oppmSheetBuilder.ts` is NOT a skill.** It's a rendering utility. The AI skills live in `services/intelligence/` and use YAML definitions to learn the OPPM template.
