# Service-Oriented ER Diagram

Last updated: 2026-04-20

## Purpose

This ER diagram groups the main relationship chains by service/data domain.

For full canonical schema and all table details, use:

- [../ERD.md](../ERD.md)
- [../DATABASE-SCHEMA.md](../DATABASE-SCHEMA.md)

## ER View

```mermaid
erDiagram
    users ||--o{ workspace_members : member_of
    users ||--o{ refresh_tokens : has
    workspaces ||--o{ workspace_members : contains
    workspaces ||--o{ workspace_invites : invites
    workspace_members ||--o{ member_skills : has

    workspaces ||--o{ projects : owns
    workspace_members ||--o{ projects : leads
    projects ||--o{ project_members : includes
    workspace_members ||--o{ project_members : assigned

    projects ||--o{ tasks : contains
    tasks ||--o{ task_reports : reports
    tasks ||--o{ task_dependencies : depends_on
    tasks ||--o{ task_assignees : legacy

    projects ||--o{ oppm_objectives : tracks
    projects ||--o{ oppm_sub_objectives : structures
    tasks ||--o{ task_sub_objectives : maps
    projects ||--o{ oppm_timeline_entries : schedules
    projects ||--o{ project_costs : budgets
    projects ||--o{ oppm_deliverables : delivers
    projects ||--o{ oppm_forecasts : forecasts
    projects ||--o{ oppm_risks : risks

    workspaces ||--o{ github_accounts : connects
    github_accounts ||--o{ repo_configs : authorizes
    repo_configs ||--o{ commit_events : receives
    commit_events ||--o{ commit_analyses : analyzed

    workspaces ||--o{ ai_models : configures
    workspaces ||--o{ document_embeddings : indexes

    workspaces ||--o{ notifications : scopes
    workspaces ||--o{ audit_log : records
```

## Service-Domain Notes

- Core service is the main owner for schema evolution and most table writes.
- AI service owns AI-specific tables and can mutate shared business tables via tools.
- Git service owns GitHub ingestion tables and analysis persistence flow.
- MCP and gateway do not own dedicated table domains.

