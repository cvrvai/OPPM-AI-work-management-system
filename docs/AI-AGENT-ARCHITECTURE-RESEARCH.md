# AI Agent Architecture Research & Design

> **Status:** Research document — summarizes how cloud companies design AI agents, analyzes OPPM's current system, and proposes a concrete architecture upgrade path.
> **Goal:** Transform OPPM's AI from a "prompt + tool list" system into a truly smart, skill-aware, self-improving agent platform.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [How Cloud Companies Build AI Agents](#2-how-cloud-companies-build-ai-agents)
3. [Current OPPM AI Architecture](#3-current-oppm-ai-architecture)
4. [Gap Analysis](#4-gap-analysis)
5. [Proposed Architecture](#5-proposed-architecture)
6. [Implementation Roadmap](#6-implementation-roadmap)
7. [Folder Structure Proposal](#7-folder-structure-proposal)
8. [Alternative Approaches](#8-alternative-approaches)
9. [Portfolio Value](#9-portfolio-value)

---

## 1. Executive Summary

This document researches how leading AI companies (Anthropic, OpenAI, Google, Microsoft) architect their AI agent systems, then applies those patterns to the OPPM project. The goal is to evolve OPPM's AI from a "prompt + tool list" chatbot into a **skill-aware, self-improving, multi-modal agent** that truly understands OPPM methodology and can intelligently manipulate Google Sheets.

**Key insight:** The difference between a "smart" and "not smart" AI system is not the LLM model — it's the **architecture around the LLM**: skills, memory, planning, feedback loops, and structured reasoning.

---

## 2. How Cloud Companies Build AI Agents

### 2.1 Anthropic's Approach (Claude + Computer Use)

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

### 2.2 OpenAI's Approach (GPT-4 + Function Calling + Assistants API)

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

### 2.3 Google's Approach (Gemini + Vertex AI Agent Builder)

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

### 2.4 Microsoft's Approach (Copilot + Semantic Kernel)

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

### 2.5 Common Patterns Across All Platforms

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

## 3. Current OPPM AI Architecture

### 3.1 What's Already Built (and working well)

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

### 3.2 The Skill System (Already Implemented)

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

### 3.3 The Agent Loop (TAOR)

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

### 3.4 What's Working Today

1. ✅ **Skill routing**: Rule-based + LLM fallback picks the right skill
2. ✅ **Tool registry**: 24 tools across 5 categories
3. ✅ **Agent loop**: TAOR with confidence scoring
4. ✅ **Multi-provider LLM**: Ollama, Anthropic, OpenAI, Kimi, DeepSeek
5. ✅ **RAG pipeline**: Semantic cache + vector + keyword + structured retrieval
6. ✅ **Guardrails**: Input injection detection, output scrubbing
7. ✅ **Sheet actions**: 34 Google Sheets API actions via `sheet_action_executor.py`
8. ✅ **Sheet snapshot**: Live read of sheet state before generating actions

---

## 4. Gap Analysis

### 4.1 Why the AI Still Seems "Not Smart"

**Problem 1: No Visual Understanding**
- The AI reads the sheet as **text** (cell values, border strings like `T:S1#CCCCCC`).
- It never **sees** the sheet. A human looking at a spreadsheet instantly understands layout, alignment, spacing, visual hierarchy.
- **Fix**: Generate a screenshot of the current sheet + target template, feed to a vision-capable model (GPT-4V, Claude 3.5 Sonnet with computer use).

**Problem 2: No Planning Step**
- The AI jumps straight to tool calls. It doesn't plan: "First I'll clear the sheet, then add headers, then borders..."
- When something fails (e.g., merge_cells fails because range is wrong), it doesn't backtrack and replan.
- **Fix**: Add a **Planner** step before the TAOR loop. The planner outputs a JSON plan: `[{"step": 1, "action": "clear_sheet", "depends_on": []}, ...]`

**Problem 3: No Learning from Failures**
- When the AI outputs wrong actions (e.g., wrong border range), the user corrects it. But the AI doesn't remember this correction for next time.
- There's no feedback loop that says: "Last time I suggested A1:AL5 for header borders, but the user said it should be A1:AL6. Remember this."
- **Fix**: Add a **feedback memory** system that stores corrections and injects them into future prompts.

**Problem 4: Border Knowledge is Text-Only**
- The AI knows borders exist (from the prompt), but it doesn't truly understand spatial relationships.
- It can't "see" that column G is a separator, or that the timeline area is J-AI.
- **Fix**: Encode the OPPM template as a **structured grid definition** (JSON/YAML) that the AI can reference programmatically, not just read as text.

**Problem 5: No Self-Evaluation After Actions**
- After executing actions, the AI doesn't verify the result. It doesn't re-read the sheet to confirm borders were applied correctly.
- **Fix**: Add a **verification step** after tool execution — re-fetch the snapshot and compare against expected state.

**Problem 6: Skills Are Hardcoded in Python**
- Adding a new skill requires editing Python files, restarting the service.
- There's no way for a non-developer to teach the AI a new skill (e.g., "Agile OPPM variant" or "Construction OPPM").
- **Fix**: Store skills as **declarative files** (YAML/JSON) in a database, loaded at runtime. Skills become data, not code.

### 4.2 Gap Summary Table

| Gap | Impact | Priority | Effort |
|---|---|---|---|
| No visual understanding | AI can't "see" layout issues | **High** | Medium |
| No planning step | Actions are reactive, not strategic | **High** | Low |
| No learning from failures | Same mistakes repeat | **High** | Medium |
| Border knowledge is text-only | Spatial reasoning is weak | **Medium** | Low |
| No self-evaluation | Can't verify its own work | **Medium** | Low |
| Skills are hardcoded | Hard to add new domains | **Medium** | Medium |
| No parallel tool calls | Slow for bulk operations | **Low** | Medium |
| No persistent memory | Forgets user preferences | **Low** | Medium |

---

## 5. Proposed Architecture

### 5.1 Vision: The "Smart OPPM Agent"

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SMART OPPM AGENT                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 1: Perception                                                         │
│    ├── Text Snapshot (existing) — cell values, borders, formulas            │
│    ├── Visual Snapshot (NEW) — screenshot of current sheet                  │
│    └── Template Reference (NEW) — JSON definition of "standard" layout      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 2: Planning                                                           │
│    ├── Intent Parser (existing) — what does the user want?                  │
│    ├── Skill Router (existing) — which skill to activate?                   │
│    └── Plan Generator (NEW) — break request into steps with dependencies      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 3: Execution                                                          │
│    ├── TAOR Agent Loop (existing) — Think→Act→Observe→Retry                 │
│    ├── Parallel Tool Calls (NEW) — execute independent tools together       │
│    └── Verification Step (NEW) — re-check state after actions               │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 4: Learning                                                           │
│    ├── Feedback Memory (NEW) — store user corrections                       │
│    ├── Skill Improvement (NEW) — auto-update prompts from feedback            │
│    └── A/B Testing (NEW) — compare prompt versions for accuracy             │
├─────────────────────────────────────────────────────────────────────────────┤
│  Layer 5: Skills (Declarative)                                               │
│    ├── oppm-traditional.skill.yaml                                            │
│    ├── oppm-agile.skill.yaml                                                │
│    ├── oppm-construction.skill.yaml                                           │
│    └── google-sheets-expert.skill.yaml                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Layer 1: Perception (Making the AI "See")

**Current:** The AI reads a text snapshot:
```json
{"cells": [{"r": 1, "c": 1, "v": "Project Title", "b": "T:S1#000000|B:S1#000000"}]}
```

**Proposed:** Add a **Visual Perception** module:

```python
# services/intelligence/infrastructure/perception/
class SheetPerception:
    """Generates both text and visual representations of the sheet state."""

    async def get_snapshot(self, sheet_id: str) -> SheetSnapshot:
        # Existing: text snapshot
        text = await self._get_text_snapshot(sheet_id)
        # NEW: generate image using headless browser or Sheets API thumbnail
        image = await self._get_visual_snapshot(sheet_id)
        # NEW: compare against template
        template_match = await self._compare_to_template(text, image)
        return SheetSnapshot(text=text, image=image, template_match=template_match)
```

**Implementation options:**
1. **Google Sheets API thumbnail**: `spreadsheets.get?includeGridData=false` returns a thumbnail URL.
2. **Puppeteer/Playwright**: Render the sheet in a headless browser, take screenshot.
3. **FortuneSheet renderer**: Use the existing frontend renderer to generate an image.

**For the AI prompt:**
```
You have access to:
1. TEXT snapshot: structured cell data (values, borders, colors)
2. VISUAL snapshot: a screenshot of the current sheet
3. TEMPLATE reference: the "standard" OPPM layout as a structured definition

Use the VISUAL snapshot to understand spatial relationships (which cells are merged,
where borders are thick vs thin, column widths). Use the TEXT snapshot for exact
values and formulas. Use the TEMPLATE to know what "correct" looks like.
```

### 5.3 Layer 2: Planning (Making the AI Strategic)

**Current:** The AI jumps straight to tool calls.

**Proposed:** Add a **Plan Generator** before the TAOR loop:

```python
# services/intelligence/infrastructure/planner/
class PlanGenerator:
    """Breaks a user request into a dependency graph of steps."""

    async def generate_plan(self, intent: str, snapshot: SheetSnapshot) -> Plan:
        prompt = f"""
        Given the user's request and the current sheet state, generate a plan.
        Each step has: id, action, params, depends_on (list of step ids).

        Request: {intent}
        Current state: {snapshot.text_summary}

        Output a JSON plan. Example:
        {{
          "steps": [
            {{"id": 1, "action": "clear_sheet", "params": {{}}, "depends_on": []}},
            {{"id": 2, "action": "set_value", "params": {{"range": "A1", "value": "Project: X"}}, "depends_on": []}},
            {{"id": 3, "action": "set_border", "params": {{"range": "A1:AL5", "style": "SOLID"}}, "depends_on": [2]}},
            {{"id": 4, "action": "set_background", "params": {{"range": "A5:AL5", "color": "#E8E8E8"}}, "depends_on": [3]}}
          ]
        }}
        """
        return await self.llm.call_json(prompt)
```

**Benefits:**
- The user can **review the plan** before execution ("Here's what I'll do: 1. Clear sheet 2. Add headers... Approve?")
- If a step fails, the planner can **replan** from the failure point.
- Dependencies ensure correct ordering (e.g., don't set borders before values are written).

### 5.4 Layer 3: Execution (Making the AI Reliable)

**Current:** Sequential tool calls, one at a time.

**Proposed:** Add **parallel execution** and **verification**:

```python
# In agent_loop.py
async def execute_plan(plan: Plan) -> ExecutionResult:
    for batch in plan.topological_batches():  # group independent steps
        # Execute batch in parallel
        results = await asyncio.gather(*[
            execute_step(step) for step in batch
        ])

        # Verify: re-fetch snapshot and check expected state
        snapshot = await perception.get_snapshot(sheet_id)
        verification = await verify_batch(batch, results, snapshot)

        if not verification.passed:
            # Replan from failure
            plan = await planner.replan(plan, verification.failures)
            continue

    return ExecutionResult(success=True)
```

**Verification example:**
```python
async def verify_step(step, snapshot):
    if step.action == "set_border":
        expected_range = step.params["range"]
        expected_style = step.params["style"]
        actual = snapshot.get_border(expected_range)
        if actual != expected_style:
            return VerificationResult(
                passed=False,
                message=f"Expected {expected_style} border on {expected_range}, got {actual}"
            )
```

### 5.5 Layer 4: Learning (Making the AI Improve)

**Current:** The AI starts fresh every conversation.

**Proposed:** Add **Feedback Memory** and **Skill Improvement**:

```python
# services/intelligence/infrastructure/learning/
class FeedbackMemory:
    """Stores user corrections and injects them into future prompts."""

    async def store_correction(self, workspace_id: str, correction: Correction):
        """Example correction:
        {
          "skill": "oppm",
          "context": "header borders",
          "wrong_action": {"range": "A1:AL5", "style": "SOLID"},
          "correct_action": {"range": "A1:AL6", "style": "SOLID"},
          "reason": "Header includes row 6 (the column labels)"
        }
        """
        await self.db.corrections.insert(correction)

    async def get_relevant_corrections(self, workspace_id: str, intent: str) -> list[Correction]:
        # Semantic search over past corrections
        return await self.rag.search_corrections(workspace_id, intent)
```

**Skill Improvement:**
```python
class SkillImprover:
    """Automatically updates skill prompts based on feedback."""

    async def improve_skill(self, skill: Skill, corrections: list[Correction]):
        # Generate a prompt patch from corrections
        patch = await self.llm.call(f"""
        Given these user corrections to the {skill.name} skill,
        suggest a patch to the system prompt that would prevent these mistakes.

        Current prompt: {skill.system_prompt}
        Corrections: {corrections}

        Output a diff-style patch.
        """)

        # Apply patch (with human review in production)
        skill.system_prompt = apply_patch(skill.system_prompt, patch)
```

### 5.6 Layer 5: Declarative Skills (Making the AI Extensible)

**Current:** Skills are Python dataclasses with hardcoded prompts.

**Proposed:** Store skills as **YAML files** in the database:

```yaml
# oppm-traditional.skill.yaml
name: oppm-traditional
description: Fills and updates Traditional OPPM forms
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
extra_tools:
  - push_oppm_to_sheet
system_prompt: |
  You are the OPPM specialist...
  [full prompt text here]
template:
  header_rows: 5
  task_start_row: 6
  columns:
    A-F: sub_objectives
    G: separator
    H: task_number
    I: task_title
    J-AI: timeline
    AJ-AL: owners
  border_rules:
    header:
      style: SOLID
      width: 1
      color: "#000000"
    tasks:
      style: SOLID
      width: 1
      color: "#CCCCCC"
    timeline:
      style: NONE
```

**Benefits:**
- Non-developers can create new OPPM variants (Agile, Construction, etc.) by editing YAML.
- Skills can be versioned, A/B tested, and rolled back.
- The AI can reference the template programmatically: "According to the template, header rows are 1-5, so I should apply borders to A1:AL5."

---

## 6. Implementation Roadmap

### Phase 1: Foundation (Week 1-2) — Make the AI "See"

**Goal:** Give the AI visual + structured understanding of the OPPM template.

**Tasks:**
1. Create `services/intelligence/infrastructure/perception/` module
   - `SheetPerception` class that combines text + visual snapshot
   - `TemplateReference` class that loads OPPM template from YAML
2. Create `docs/skills/oppm-traditional.template.yaml` — structured OPPM template definition
3. Update the OPPM skill's pre-flight to include template reference in context
4. Update the system prompt to reference the template: "Use the TEMPLATE REFERENCE below for exact row/column/border rules"

**Deliverable:** The AI can answer "What should the border on row 5 be?" by looking at the template, not guessing.

### Phase 2: Planning (Week 3) — Make the AI Strategic

**Goal:** Add a planning step before execution.

**Tasks:**
1. Create `services/intelligence/infrastructure/planner/` module
   - `PlanGenerator` class
   - `Plan` dataclass with dependency graph
2. Add "plan review" UI in ChatPanel — show the user the planned steps before executing
3. Update agent loop to accept a plan and execute it step-by-step

**Deliverable:** When user says "recreate the form", the AI shows: "I'll do: 1. Clear sheet 2. Add title..." and the user clicks "Approve".

### Phase 3: Verification (Week 4) — Make the AI Reliable

**Goal:** The AI verifies its own work.

**Tasks:**
1. Add `verify_step()` function after each batch of tool calls
2. Re-fetch sheet snapshot and compare against expected state
3. If verification fails, auto-retry or ask user for guidance
4. Add "verification passed/failed" indicator in ChatPanel

**Deliverable:** After applying borders, the AI confirms: "✓ Verified: A1:AL5 has SOLID #000000 borders on all sides."

### Phase 4: Learning (Week 5-6) — Make the AI Improve

**Goal:** The AI learns from corrections.

**Tasks:**
1. Create `services/intelligence/infrastructure/learning/` module
   - `FeedbackMemory` class
   - `Correction` schema
2. Add "👍 / 👎" feedback buttons to ChatPanel for each action batch
3. Store corrections in `workspace_ai_corrections` table
4. Inject relevant corrections into the system prompt

**Deliverable:** User says "No, row 5 should also have a border" → AI stores correction → Next time, AI gets it right.

### Phase 5: Declarative Skills (Week 7-8) — Make the AI Extensible

**Goal:** Skills are data, not code.

**Tasks:**
1. Create `workspace_skills` table (id, workspace_id, name, yaml_content, version, is_active)
2. Build skill editor UI in Settings page
3. Migrate existing `oppm_skill.py` to YAML format
4. Add `oppm-agile` and `oppm-construction` variants as examples

**Deliverable:** A project manager can create a new "Healthcare OPPM" skill by filling out a form, no code needed.

---

## 7. Folder Structure Proposal

### Current Structure (simplified)

```
services/intelligence/
├── domains/
│   └── chat/
│       ├── service.py          # 600+ lines, everything mixed together
│       ├── router.py
│       └── schemas.py
├── infrastructure/
│   ├── rag/
│   │   └── agent_loop.py       # TAOR loop
│   ├── tools/
│   │   ├── registry.py
│   │   ├── oppm_tools.py
│   │   └── ...
│   ├── skills/
│   │   ├── base.py
│   │   ├── router.py
│   │   └── oppm_skill.py       # 400+ lines of prompt + pre/post flight
│   └── llm/
│       └── ...
```

### Proposed Structure

```
services/intelligence/
├── domains/
│   └── chat/
│       ├── service.py              # Thin orchestrator (~100 lines)
│       ├── router.py
│       ├── schemas.py
│       └── __init__.py
├── infrastructure/
│   ├── perception/                 # NEW: How the AI "sees"
│   │   ├── __init__.py
│   │   ├── sheet_perception.py   # Text + visual snapshot
│   │   ├── template_reference.py # Load template from YAML
│   │   └── visual_snapshot.py    # Screenshot generation
│   ├── planner/                    # NEW: Strategic planning
│   │   ├── __init__.py
│   │   ├── plan_generator.py     # Break request into steps
│   │   ├── plan_executor.py      # Execute with verification
│   │   └── plan_models.py        # Plan, Step, Dependency
│   ├── rag/
│   │   ├── agent_loop.py         # Existing TAOR loop
│   │   ├── guardrails.py
│   │   ├── query_rewriter.py
│   │   ├── semantic_cache.py
│   │   └── memory.py
│   ├── tools/
│   │   ├── registry.py
│   │   ├── base.py
│   │   ├── oppm_tools.py
│   │   ├── task_tools.py
│   │   ├── cost_tools.py
│   │   ├── read_tools.py
│   │   ├── project_tools.py
│   │   └── sheet_tools.py        # NEW: Google Sheets actions as tools
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── base.py               # Skill, SkillContext, SkillResult
│   │   ├── registry.py           # SkillRegistry (load from DB)
│   │   ├── router.py             # pick_skill()
│   │   ├── loader.py             # NEW: Load skills from YAML/DB
│   │   └── oppm/                 # Skill definitions
│   │       ├── traditional.yaml
│   │       ├── agile.yaml
│   │       └── construction.yaml
│   ├── learning/                 # NEW: Self-improvement
│   │   ├── __init__.py
│   │   ├── feedback_memory.py    # Store/retrieve corrections
│   │   ├── skill_improver.py     # Auto-update prompts
│   │   └── correction_models.py  # Correction schema
│   └── llm/
│       ├── __init__.py
│       ├── base.py
│       ├── tool_parser.py
│       ├── ollama.py
│       ├── anthropic.py
│       ├── openai.py
│       ├── kimi.py
│       └── deepseek.py
├── skills/                         # NEW: Declarative skill library
│   ├── oppm-traditional/
│   │   ├── skill.yaml
│   │   ├── template.yaml
│   │   └── examples/
│   │       ├── fill_form.json
│   │       ├── add_border.json
│   │       └── recreate.json
│   ├── oppm-agile/
│   │   ├── skill.yaml
│   │   └── template.yaml
│   └── google-sheets-expert/
│       ├── skill.yaml
│       └── examples/
│           ├── border_math.json
│           └── merge_cells.json
└── config.py
```

### Frontend Structure ( additions)

```
frontend/src/
├── components/
│   └── ChatPanel.tsx             # Add plan review UI, verification indicators
├── hooks/
│   └── usePlanReview.ts          # NEW: Plan approval flow
├── stores/
│   └── aiStore.ts                # NEW: AI state (plan, verification, feedback)
└── types/
    └── ai.ts                     # NEW: Plan, Step, Verification types
```

---

## 8. Alternative Approaches

### Option A: Full Multi-Agent System (CrewAI / AutoGen style)

Instead of one agent with skills, use multiple specialized agents:
- **Layout Agent**: Handles borders, merges, formatting
- **Content Agent**: Handles task names, objectives, dates
- **Timeline Agent**: Handles Gantt chart coloring
- **Orchestrator Agent**: Coordinates the others

**Pros:** Each agent has a narrow focus, easier to debug.
**Cons:** More complex, harder to coordinate, overkill for OPPM's scope.
**Verdict:** Not recommended for OPPM. The skill system achieves the same benefit with less complexity.

### Option B: Code Generation (OpenAI Code Interpreter style)

Instead of tool calls, let the AI generate Python code that manipulates the sheet:
```python
# AI generates this code
gs = GoogleSheetsAPI(sheet_id)
gs.clear_sheet()
gs.set_value("A1", "Project: X")
gs.set_border("A1:AL5", style="SOLID", color="#000000")
```

**Pros:** The AI can use loops, conditionals, variables. Much more flexible.
**Cons:** Security risk (code injection), harder to verify, requires sandboxing.
**Verdict:** Interesting for future, but too risky for now. Stick with structured tool calls.

### Option C: Fine-Tuned Model

Train a custom model specifically for OPPM sheet manipulation.

**Pros:** The model "just knows" OPPM rules. No need for long prompts.
**Cons:** Expensive, requires training data, model drift over time.
**Verdict:** Not recommended. Prompt engineering + skills + feedback is more agile and cheaper.

### Option D: MCP (Model Context Protocol) Server

Expose OPPM tools as an MCP server that any AI client can use.

**Pros:** Standard protocol, works with Claude Desktop, Cursor, etc.
**Cons:** Requires MCP client support, adds protocol overhead.
**Verdict:** OPPM already has HTTP MCP tools in `services/automation/`. Could expand this to be a full MCP server. Good for **external** AI tools, but internal agent should use direct function calls for speed.

---

## 9. Portfolio Value

### Why This Matters for Your AI Engineer Portfolio

**1. Demonstrates Architecture Thinking**
- You didn't just "add a feature" — you designed a **system** that can learn and improve.
- The 5-layer architecture (Perception → Planning → Execution → Learning → Skills) shows you understand how to decompose complex AI problems.

**2. Shows You Know Industry Best Practices**
- You researched Anthropic, OpenAI, Google, Microsoft and synthesized their patterns.
- You understand the difference between ReAct, Plan-and-Execute, and Multi-Agent.
- You can justify trade-offs (e.g., why skills vs. multi-agent).

**3. Proves You Can Build Self-Improving Systems**
- The feedback loop + skill improvement is the holy grail of AI engineering.
- Most portfolios show "I built a chatbot." Yours shows "I built a chatbot that learns from its mistakes."

**4. Demonstrates Full-Stack AI Engineering**
- Backend: Python FastAPI, SQLAlchemy, async architecture
- AI: LLM adapters, tool calling, RAG, agent loops
- Frontend: React, TypeScript, real-time UI
- DevOps: Docker, microservices, gateway routing

**5. Shows Product Thinking**
- You identified the real problem: "The AI doesn't understand OPPM layout."
- You proposed solutions that are **practical** (template YAML) not just theoretical.
- You prioritized by impact vs. effort.

### Talking Points for Interviews

> "I built an AI agent system for project management. The challenge was that the AI could generate text but didn't understand spreadsheet layout. I solved this by adding a **perception layer** that gives the AI both text and visual context, a **planning layer** that breaks requests into verifiable steps, and a **learning layer** that stores corrections so the AI improves over time. The system uses a **skill architecture** inspired by Anthropic's approach — each skill is a bundle of domain knowledge + allowed tools + pre/post hooks. Skills are stored as YAML so non-developers can create new variants."

---

## Appendix A: Recommended Reading

1. **Anthropic: Building Effective Agents** — https://www.anthropic.com/research/building-effective-agents
2. **OpenAI: Function Calling Guide** — https://platform.openai.com/docs/guides/function-calling
3. **Microsoft: Semantic Kernel** — https://learn.microsoft.com/en-us/semantic-kernel/
4. **Google: Vertex AI Agent Builder** — https://cloud.google.com/agent-builder
5. **ReAct Paper** (Reasoning + Acting) — Yao et al., 2022
6. **Plan-and-Execute Paper** — Wang et al., 2023
7. **OPPM Book** — Clark Campbell, *The New One-Page Project Manager*

## Appendix B: Skill YAML Schema

```yaml
# skill.schema.json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["name", "description", "triggers", "tool_categories", "system_prompt"],
  "properties": {
    "name": { "type": "string" },
    "description": { "type": "string" },
    "version": { "type": "string" },
    "triggers": { "type": "array", "items": { "type": "string" } },
    "intent_examples": { "type": "array", "items": { "type": "string" } },
    "tool_categories": { "type": "array", "items": { "type": "string" } },
    "extra_tools": { "type": "array", "items": { "type": "string" } },
    "system_prompt": { "type": "string" },
    "template": { "type": "object" },
    "output_contract": { "type": "object" },
    "examples": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "user_input": { "type": "string" },
          "context": { "type": "string" },
          "expected_actions": { "type": "array" }
        }
      }
    }
  }
}
```

---

*Document version: 1.0*
*Last updated: 2026-05-03*
*Author: OPPM AI Architecture Team*
