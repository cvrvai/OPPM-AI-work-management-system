---
description: "Safely update a named flow in /docs/FLOWCHARTS.md — always archives the previous version before writing. Use when any service flow, request lifecycle, or integration flow has changed."
name: "update-flowchart"
argument-hint: "Flow: <flow name> | Change: <what changed>"
agent: "agent"
tools: [read, search, edit]
---

Safely update a flowchart in [FLOWCHARTS.md](../docs/FLOWCHARTS.md), always archiving the previous version first.

## Task Input

```
Flow: $flow
Change: $change
```

---

## Step 1 — Read and summarize the current flow

- Open [FLOWCHARTS.md](../docs/FLOWCHARTS.md)
- Find the section for the named flow
- Output a plain-language summary: "The current flow does X → Y → Z"
- Identify all steps that will change, be added, or be removed

---

## Step 2 — Describe the new flow

Before touching any file, write out the updated flow in plain language:
"After this change, the flow will do: A → B → C"

Highlight:
- What is new
- What is removed
- What is reordered

**Stop and ask for confirmation before Step 3.**

---

## Step 3 — Archive the old flow

Invoke skill: `archive-flowchart`

This will:
- Copy the current flow section to `docs/phase-history/FLOWCHARTS-YYYY-MM-DD-<slug>.md`
- Add a changelog entry at the top of `FLOWCHARTS.md`

Do not modify `FLOWCHARTS.md` until the archive is confirmed written.

---

## Step 4 — Write the updated flow

- Update only the relevant section in [FLOWCHARTS.md](../docs/FLOWCHARTS.md)
- Keep the same heading structure and Mermaid/markdown format as the existing sections
- Do not rewrite unrelated flows

---

## Step 5 — Confirm

Output:
- Archive file path created
- Section(s) updated in `FLOWCHARTS.md`
- Plain-language summary of what changed
