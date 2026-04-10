---
description: "Produce a full phase plan (analysis, design, implementation, docs) for a new feature, bug fix, or refactor in the OPPM system. Use when implementing anything that touches services, DB, or API."
name: "implement-feature"
argument-hint: "Feature: <name> | Scope: feature|fix|refactor | Services: <csv> | Description: <what it does>"
agent: "agent"
tools: [read, search, edit, todo]
---

Produce and execute a full phase plan for the following task.

## Task Input

```
Feature: $feature
Scope: $scope
Services: $services
Description: $description
```

---

## Phase 1 — Analysis

Read and internalize:
- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) — identify which layer this feature lives in
- [MICROSERVICES-REFERENCE.md](../docs/MICROSERVICES-REFERENCE.md) — identify affected services
- [FLOWCHARTS.md](../docs/FLOWCHARTS.md) — identify which flows are affected
- [PHASE-TRACKER.md](../docs/PHASE-TRACKER.md) — check for related open items

Output:
- Files and services affected
- Existing patterns this feature should follow
- Breaking changes or risks
- Security surface: what user input does this touch?
- Performance surface: any DB queries, loops, or external HTTP calls?

**Stop and ask for confirmation before Phase 2.**

---

## Phase 2 — Design

After Phase 1 is confirmed:
- Data flow: describe the request lifecycle end-to-end
- API contracts: new endpoints or changed fields (check [API-REFERENCE.md](../docs/API-REFERENCE.md) for consistency)
- DB changes: new tables, columns, or indexes (check [DATABASE-SCHEMA.md](../docs/DATABASE-SCHEMA.md))
- Folder/file locations: propose paths and validate against naming rules in `oppm-project.instructions.md`
- Flowchart delta: describe in plain language what the flow will look like after this change
- Test surface: list scenarios that need coverage (happy path, edge cases, auth boundary, errors)

---

## Phase 3 — Implementation

Execute in this order:
1. DB migrations or schema changes first
2. Service layer (business logic)
3. API layer (route handlers, validation)
4. Frontend or integration points last

As you write each file, annotate inline suggestions using these formats:
```
Security [LOW|MED|HIGH]: <issue> → <recommended fix>
Performance [LOW|MED|HIGH]: <issue> → <fix> — estimated impact: <X>
Test: <scenario> | Input: <what> | Expected: <what> | Priority: [low|med|high]
```

---

## Phase 4 — Documentation and cleanup

Run in order:
1. Invoke skill `archive-flowchart` if any flow changed
2. Invoke skill `document-feature` always
3. Invoke skill `validate-folder` for any new directories created
4. Update [API-REFERENCE.md](../docs/API-REFERENCE.md) if endpoints changed
5. Update [DATABASE-SCHEMA.md](../docs/DATABASE-SCHEMA.md) if schema changed
6. Append to [PHASE-TRACKER.md](../docs/PHASE-TRACKER.md): `YYYY-MM-DD | <feature> | done`

---

## Completion summary

Output:
- What was built
- Which docs were updated
- Deferred suggestions (label + risk level)
- Recommended next action
