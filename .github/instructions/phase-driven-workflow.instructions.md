---
name: "OPPM Phase Workflow Bridge"
description: "Use when working in OPPM-AI-work-management-system on coding, refactoring, migrations, architecture changes, planning, or documentation bootstrap. Enforces the root doc/ gate, the docs/ planning-history-architecture structure, and coordination with the existing PHASE-TRACKER and phase-history workflow."
applyTo: "**"
---

# OPPM Workflow Bridge

## Startup gate

- Before any implementation, list the root `doc/` folder and read every file in it.
- After reading `doc/`, continue to the high-signal repository docs already required by `.github/copilot-instructions.md` and related repo instructions.
- If `doc/` is missing or empty, stop normal implementation work.

## Bootstrap exception

- The only allowed task while `doc/` is missing or empty is a documentation bootstrap or repair task.
- Bootstrap tasks must create or repair the required `doc/` and `docs/` workflow scaffold before any feature work continues.
- After bootstrap, return to the startup gate and read `doc/` again.

## Phase control

- Check `docs/planning/MASTER_PHASE_PLAN.md` and `docs/planning/CURRENT_PHASE.md` before coding.
- Treat `docs/planning/` as the project-level phase source of truth.
- Keep `docs/PHASE-TRACKER.md` as the task-level tracker until an explicit migration retires it.
- Do not skip phases or implement work outside the approved current phase unless the user explicitly instructs you to do so.

## Execution records

- For each new editing task, archive any completed `docs/PHASE-TRACKER.md` into `docs/phase-history/` before starting a new tracker.
- Keep `docs/planning/CURRENT_PHASE.md` aligned with the active project phase and `docs/PHASE-TRACKER.md` aligned with the active task.
- Write completed phase summaries to `docs/history/`.
- Record architecture changes in `docs/architecture/`, decisions in `docs/decisions/`, and actionable work in `docs/tasks/`.

## Coexistence rules

- `.github/copilot-instructions.md` and `.github/instructions/oppm-project.instructions.md` remain active.
- Use this file for workflow enforcement only; do not duplicate existing architecture scan or naming rules.
- When the project-level plan and task-level tracker disagree, resolve the mismatch before continuing.