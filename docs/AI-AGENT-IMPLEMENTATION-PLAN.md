# OPPM AI Agent — Implementation Plan

> **Status:** Ready for implementation
> **Goal:** Transform OPPM's AI from a "prompt + tool list" system into a skill-aware, self-improving agent platform
> **Estimated Duration:** 8 weeks (1 developer)
> **Priority:** High — directly impacts portfolio value and user experience

---

## Overview

This plan implements the architecture described in `docs/AI-AGENT-ARCHITECTURE-RESEARCH.md`. It builds on OPPM's existing skill system, tool registry, and agent loop — adding **perception**, **planning**, **verification**, and **learning** layers.

**Key principle:** Incremental improvement. Each phase delivers user-visible value. We don't rebuild — we enhance.

---

## Phase 1: Foundation — Structured Template Reference (Week 1-2)

### Goal
Give the AI a **structured, programmatic** understanding of the OPPM template so it never guesses row numbers, column widths, or border colors.

### Current State
- The AI learns OPPM layout from a **text prompt** (~500 lines in `service.py`)
- Border rules, font sizes, and column widths are buried in prose
- The AI sometimes outputs wrong ranges because it "forgets" the template

### Deliverables

#### 1.1 Create `TemplateReference` class

```python
# services/intelligence/infrastructure/perception/template_reference.py

class TemplateReference:
    """Loads and queries OPPM template definitions from YAML files."""

    def __init__(self, template_path: str):
        self.data = yaml.safe_load(open(template_path))

    def get_border_rule(self, section: str) -> dict:
        """Get border rule for a section (header, task_area, timeline)."""
        return self.data["borders"][section]

    def get_font_rule(self, element: str) -> dict:
        """Get font rule for an element (project_title, task_number, etc.)."""
        return self.data["fonts"][element]

    def get_column_width(self, column_id: str) -> int:
        """Get standard width for a column."""
        for col in self.data["columns"]:
            if col["id"] == column_id:
                return col["width"]
        return None

    def get_row_height(self, section: str) -> int:
        """Get standard row height for a section."""
        return self.data["row_heights"][section]["height"]

    def get_content_template(self, row_name: str) -> str:
        """Get content template for a header row."""
        return self.data["content"][row_name]

    def validate_action(self, action: dict) -> list[str]:
        """Validate an action against the template. Returns list of warnings."""
        warnings = []
        # Example: if action sets border on J-AI, warn that timeline should be NONE
        if action.get("action") == "set_border":
            range_str = action.get("params", {}).get("range", "")
            if "J" in range_str and "AI" in range_str:
                style = action.get("params", {}).get("style")
                if style != "NONE":
                    warnings.append(f"Timeline area {range_str} should have style=NONE")
        return warnings
```

#### 1.2 Update OPPM Skill Pre-flight

Modify `oppm_skill.py` pre-flight to inject template reference into context:

```python
async def oppm_preflight(session, ctx: SkillContext):
    # ... existing loads ...

    # NEW: Load template reference
    template = TemplateReference("services/intelligence/skills/oppm-traditional/template.yaml")

    # Build template summary for LLM
    template_summary = f"""
    ## TEMPLATE REFERENCE (Structured Rules)

    ### Border Rules
    - Header (A1:AL5): {template.get_border_rule('header')}
    - Task area (A6:AL{{N}}): {template.get_border_rule('task_area')}
    - Timeline (J6:AI{{N}}): {template.get_border_rule('timeline')}

    ### Font Rules
    - Title row: {template.get_font_rule('project_title')}
    - Task numbers: {template.get_font_rule('task_number')}
    - Task titles: {template.get_font_rule('task_title')}

    ### Column Widths
    - A-F (sub-objectives): {template.get_column_width('A')}px
    - G (separator): {template.get_column_width('G')}px
    - H (task numbers): {template.get_column_width('H')}px
    - I (task titles): {template.get_column_width('I')}px
    - J-AI (timeline): {template.get_column_width('J')}px each
    - AJ-AL (owners): {template.get_column_width('AJ')}px each

    ### Row Heights
    - Task rows: {template.get_row_height('task_rows')}px
    """

    return {
        # ... existing data ...
        "template_summary": template_summary,
        "template": template,  # For programmatic access in post-flight
    }
```

#### 1.3 Update System Prompt

Replace the text-only OPPM rules in the system prompt with:

```
## OPPM Template Rules

You have access to a STRUCTURED TEMPLATE REFERENCE that defines exact values.
ALWAYS use these values — never guess:

{template_summary}

When generating actions, reference the template for exact ranges, colors, and sizes.
```

#### 1.4 Add Template Validation

Before executing actions, validate them against the template:

```python
# In sheet_action_executor.py or chat service
template = TemplateReference("...")
for action in actions:
    warnings = template.validate_action(action)
    if warnings:
        logger.warning("Template validation warnings: %s", warnings)
        # Optionally: ask user for confirmation
```

### Acceptance Criteria
- [ ] AI outputs correct column widths (40, 10, 50, 280, 25, 80) without being told in the prompt
- [ ] AI knows timeline area (J-AI) should have NO borders
- [ ] AI knows header rows (1-5) should have black borders
- [ ] AI can answer "What should the border on row 5 be?" by querying the template

---

## Phase 2: Planning — Strategic Action Sequences (Week 3)

### Goal
Add a **planning step** so the AI thinks before acting, and the user can review the plan.

### Current State
- The AI jumps straight to tool calls
- Complex requests ("recreate the form") produce 20+ actions with no explanation
- If an action fails, the AI doesn't know how to recover

### Deliverables

#### 2.1 Create `PlanGenerator` class

```python
# services/intelligence/infrastructure/planner/plan_generator.py

@dataclass
class PlanStep:
    id: int
    action: str
    params: dict
    depends_on: list[int]  # Step IDs that must complete before this one
    description: str         # Human-readable description

@dataclass
class Plan:
    steps: list[PlanStep]
    estimated_duration_ms: int
    affected_ranges: list[str]  # Sheet ranges that will be modified

class PlanGenerator:
    """Generates a plan from user intent + current sheet state."""

    async def generate_plan(self, intent: str, snapshot: SheetSnapshot, template: TemplateReference) -> Plan:
        prompt = f"""
        You are a planning assistant. Given the user's request and the current sheet state,
        generate a step-by-step plan to achieve the goal.

        User request: {intent}
        Current sheet state: {snapshot.text_summary}
        Template rules: {template.summary}

        Output a JSON plan with steps. Each step has:
        - id: step number
        - action: the tool action (e.g., "set_border", "set_value")
        - params: action parameters
        - depends_on: list of step IDs that must complete first
        - description: human-readable explanation

        Rules:
        - Order matters: clear_sheet must be first if used
        - set_value should come before set_border on the same range
        - set_row_height should come after insert_rows
        """

        plan_json = await self.llm.call_json(prompt)
        return self._parse_plan(plan_json)
```

#### 2.2 Add Plan Review UI

In `ChatPanel.tsx`, add a plan review step:

```typescript
// When AI returns a plan instead of immediate actions
interface PlanReviewProps {
  plan: Plan;
  onApprove: () => void;
  onReject: () => void;
  onModify: (modifiedPlan: Plan) => void;
}

const PlanReview: React.FC<PlanReviewProps> = ({ plan, onApprove }) => {
  return (
    <div className="plan-review">
      <h3>AI Plan: {plan.description}</h3>
      <ol>
        {plan.steps.map(step => (
          <li key={step.id}>
            {step.description}
            <code>{JSON.stringify(step.params)}</code>
          </li>
        ))}
      </ol>
      <button onClick={onApprove}>✓ Approve & Execute</button>
      <button onClick={onReject}>✗ Cancel</button>
    </div>
  );
};
```

#### 2.3 Update Agent Loop for Plans

Modify `run_agent_loop` to accept an optional plan:

```python
async def run_agent_loop(
    session,
    messages,
    tools,
    skill_context,
    plan: Plan | None = None,  # NEW
) -> AgentLoopResult:
    if plan:
        # Execute plan step by step with verification after each batch
        for batch in plan.topological_batches():
            results = await execute_batch(batch)
            verify = await verify_batch(batch, results)
            if not verify.passed:
                # Replan
                plan = await planner.replan(plan, verify.failures)
        return AgentLoopResult(final_text="Plan executed successfully")
    else:
        # Existing TAOR loop
        return await _taor_loop(session, messages, tools, skill_context)
```

### Acceptance Criteria
- [ ] When user says "recreate the form", AI shows a plan with 15+ steps before executing
- [ ] User can click "Approve" to execute or "Cancel" to abort
- [ ] Plan respects dependencies (clear_sheet first, then values, then borders)
- [ ] If a step fails, AI replans from that point

---

## Phase 3: Verification — Self-Checking (Week 4)

### Goal
The AI verifies its own work after executing actions.

### Current State
- After executing actions, the AI assumes they worked
- User has to manually check if borders were applied correctly

### Deliverables

#### 3.1 Create `SheetVerifier` class

```python
# services/intelligence/infrastructure/planner/sheet_verifier.py

class SheetVerifier:
    """Verifies that executed actions produced the expected result."""

    async def verify_action(self, action: dict, before: SheetSnapshot, after: SheetSnapshot) -> VerificationResult:
        action_type = action["action"]
        params = action.get("params", {})

        if action_type == "set_border":
            return self._verify_border(params, before, after)
        elif action_type == "set_value":
            return self._verify_value(params, before, after)
        elif action_type == "set_background":
            return self._verify_background(params, before, after)
        # ... etc

    def _verify_border(self, params, before, after):
        range_str = params["range"]
        expected_style = params["style"]

        # Check a sample cell in the range
        cell = after.get_cell(range_str.split(":")[0])
        actual_border = cell.get("b", "")

        if expected_style == "NONE":
            if "S" in actual_border or "K" in actual_border or "M" in actual_border:
                return VerificationResult(passed=False, message=f"Expected no borders on {range_str}, found {actual_border}")
        else:
            if expected_style not in actual_border:
                return VerificationResult(passed=False, message=f"Expected {expected_style} border on {range_str}, found {actual_border}")

        return VerificationResult(passed=True)
```

#### 3.2 Add Verification to ChatPanel

Show verification status in the UI:

```typescript
interface VerificationBadgeProps {
  status: "pending" | "passed" | "failed";
  message?: string;
}

const VerificationBadge: React.FC<VerificationBadgeProps> = ({ status, message }) => {
  const icons = {
    pending: "⏳",
    passed: "✓",
    failed: "✗"
  };
  return (
    <span className={`verification-badge ${status}`}>
      {icons[status]} {message}
    </span>
  );
};
```

### Acceptance Criteria
- [ ] After applying borders, AI confirms: "✓ Verified: A1:AL5 has SOLID #000000 borders"
- [ ] If verification fails, AI shows: "✗ Verification failed: Expected SOLID on A6, found NONE"
- [ ] User sees verification status for each action batch

---

## Phase 4: Learning — Feedback Memory (Week 5-6)

### Goal
The AI remembers corrections and improves over time.

### Current State
- The AI makes the same mistakes every session
- There's no way to teach it "row 5 should also have a border"

### Deliverables

#### 4.1 Create Database Table

```sql
-- migration: 006-ai-corrections.sql
CREATE TABLE IF NOT EXISTS workspace_ai_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    context TEXT NOT NULL,           -- e.g., "header borders"
    wrong_action JSONB NOT NULL,     -- What the AI did
    correct_action JSONB NOT NULL,   -- What it should have done
    reason TEXT,                     -- Why it was wrong
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    usage_count INTEGER DEFAULT 1    -- How many times this correction was applied
);

CREATE INDEX idx_corrections_workspace ON workspace_ai_corrections(workspace_id);
CREATE INDEX idx_corrections_skill ON workspace_ai_corrections(skill_name);
```

#### 4.2 Create `FeedbackMemory` class

```python
# services/intelligence/infrastructure/learning/feedback_memory.py

class FeedbackMemory:
    """Stores and retrieves user corrections."""

    async def store_correction(self, workspace_id: str, skill_name: str, correction: Correction):
        await self.db.execute(
            """
            INSERT INTO workspace_ai_corrections
            (workspace_id, skill_name, context, wrong_action, correct_action, reason)
            VALUES (:ws_id, :skill, :ctx, :wrong, :correct, :reason)
            """,
            {
                "ws_id": workspace_id,
                "skill": skill_name,
                "ctx": correction.context,
                "wrong": json.dumps(correction.wrong_action),
                "correct": json.dumps(correction.correct_action),
                "reason": correction.reason,
            }
        )

    async def get_relevant_corrections(self, workspace_id: str, skill_name: str, intent: str) -> list[Correction]:
        # Simple: return recent corrections for this skill
        # Advanced: semantic search using embeddings
        result = await self.db.execute(
            """
            SELECT * FROM workspace_ai_corrections
            WHERE workspace_id = :ws_id AND skill_name = :skill
            ORDER BY usage_count DESC, created_at DESC
            LIMIT 10
            """,
            {"ws_id": workspace_id, "skill": skill_name}
        )
        return [self._row_to_correction(row) for row in result.fetchall()]
```

#### 4.3 Inject Corrections into Prompt

```python
# In chat service, before calling the LLM
corrections = await feedback_memory.get_relevant_corrections(workspace_id, "oppm", user_message)
if corrections:
    correction_text = "\n".join([
        f"- When handling '{c.context}', do NOT {c.wrong_action}. Instead: {c.correct_action}. Reason: {c.reason}"
        for c in corrections
    ])
    system_prompt += f"\n\n## Past Corrections (learn from these)\n{correction_text}"
```

#### 4.4 Add Feedback UI

In `ChatPanel.tsx`, add thumbs up/down to each AI response:

```typescript
const ChatMessage: React.FC<{ message: Message }> = ({ message }) => {
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);

  const submitFeedback = async (type: "up" | "down", correction?: string) => {
    await api.submitFeedback({
      messageId: message.id,
      type,
      correction,  // If thumbs down, ask what should have happened
    });
  };

  return (
    <div className="chat-message">
      {message.text}
      <div className="feedback-buttons">
        <button onClick={() => submitFeedback("up")}>👍</button>
        <button onClick={() => {
          const correction = prompt("What should the AI have done instead?");
          submitFeedback("down", correction);
        }}>👎</button>
      </div>
    </div>
  );
};
```

### Acceptance Criteria
- [ ] User can click 👎 and type a correction
- [ ] Correction is stored in database
- [ ] Next session, AI receives correction in system prompt
- [ ] AI makes fewer repeated mistakes over time

---

## Phase 5: Declarative Skills (Week 7-8)

### Goal
Skills are stored as YAML in the database, editable via UI.

### Current State
- Skills are Python code in `oppm_skill.py`
- Adding a new skill requires code changes + deployment

### Deliverables

#### 5.1 Create `workspace_skills` Table

```sql
-- migration: 007-workspace-skills.sql
CREATE TABLE IF NOT EXISTS workspace_skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    yaml_content TEXT NOT NULL,      -- Full skill YAML
    version INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    is_builtin BOOLEAN DEFAULT false, -- True for system skills
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, name)
);

CREATE INDEX idx_ws_skills_workspace ON workspace_skills(workspace_id);
CREATE INDEX idx_ws_skills_active ON workspace_skills(is_active);
```

#### 5.2 Create `SkillLoader` class

```python
# services/intelligence/infrastructure/skills/loader.py

class SkillLoader:
    """Loads skills from filesystem (built-in) or database (custom)."""

    def __init__(self, builtin_path: str, db_session: AsyncSession):
        self.builtin_path = builtin_path
        self.db = db_session

    async def load_skill(self, workspace_id: str, name: str) -> Skill:
        # Try custom skill from DB first
        custom = await self._load_from_db(workspace_id, name)
        if custom:
            return custom

        # Fall back to built-in
        return self._load_from_filesystem(name)

    def _load_from_filesystem(self, name: str) -> Skill:
        path = os.path.join(self.builtin_path, name, "skill.yaml")
        with open(path) as f:
            data = yaml.safe_load(f)
        return Skill(**data)

    async def _load_from_db(self, workspace_id: str, name: str) -> Skill | None:
        result = await self.db.execute(
            select(WorkspaceSkill)
            .where(WorkspaceSkill.workspace_id == workspace_id)
            .where(WorkspaceSkill.name == name)
            .where(WorkspaceSkill.is_active == true)
        )
        row = result.scalar_one_or_none()
        if row:
            data = yaml.safe_load(row.yaml_content)
            return Skill(**data)
        return None
```

#### 5.3 Build Skill Editor UI

In `frontend/src/pages/Settings.tsx`, add a "Skills" tab:

```typescript
const SkillEditor: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);

  return (
    <div className="skill-editor">
      <div className="skill-list">
        {skills.map(skill => (
          <button key={skill.name} onClick={() => setSelectedSkill(skill)}>
            {skill.name}
          </button>
        ))}
      </div>
      {selectedSkill && (
        <div className="skill-form">
          <textarea
            value={selectedSkill.yamlContent}
            onChange={e => updateSkill(selectedSkill.name, e.target.value)}
            rows={40}
            cols={80}
          />
          <button onClick={() => saveSkill(selectedSkill)}>Save</button>
        </div>
      )}
    </div>
  );
};
```

#### 5.4 Migrate Existing Skills

1. Convert `oppm_skill.py` to `services/intelligence/skills/oppm-traditional/skill.yaml`
2. Update `SKILL_REGISTRY` to load from YAML instead of Python
3. Keep Python pre/post-flight hooks as named functions referenced in YAML:

```yaml
# skill.yaml
pre_flight:
  module: "infrastructure.skills.oppm_skill"
  function: "oppm_preflight"

post_flight:
  module: "infrastructure.skills.oppm_skill"
  function: "oppm_postflight"
```

### Acceptance Criteria
- [ ] Skills are loaded from YAML files
- [ ] Admin can edit skill YAML in Settings page
- [ ] Changes take effect without restarting service
- [ ] New skill variants (Agile, Construction) can be created via UI

---

## Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| YAML parsing errors | Medium | Medium | Validate YAML on save; show errors in UI |
| Plan generation too slow | Medium | High | Cache plans; use rule-based for common requests |
| Verification false positives | Medium | Low | Make verification warnings, not blockers |
| Feedback memory grows too large | Low | Medium | Auto-archive old corrections; limit to 10 per skill |
| Users confused by plan review | Medium | Medium | Make it optional ("Auto-execute" toggle) |

---

## Success Metrics

| Metric | Baseline | Target (8 weeks) |
|---|---|---|
| Border accuracy (correct range + style) | 60% | 95% |
| User corrections per session | 5 | 1 |
| Plan approval rate | N/A | 80% |
| Verification pass rate | N/A | 90% |
| Time to fill empty OPPM form | 30 min (manual) | 2 min (AI) |

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Create Phase 1 branch** and start with `TemplateReference`
3. **Set up monitoring** for the success metrics
4. **Schedule weekly demos** to show progress

---

*Document version: 1.0*
*Last updated: 2026-05-03*
