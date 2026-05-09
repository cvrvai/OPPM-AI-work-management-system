-- Migration 008: Dashboard performance indexes
-- Addresses N+1 query slowness in get_dashboard_stats

-- Index for tasks JOINed by workspace via projects
CREATE INDEX IF NOT EXISTS idx_tasks_project_id_status
    ON tasks(project_id, status);

-- Index for repo_configs filtered by project_id
CREATE INDEX IF NOT EXISTS idx_repo_configs_project_id
    ON repo_configs(project_id);

-- Index for commit_events time-range + repo filter
CREATE INDEX IF NOT EXISTS idx_commit_events_repo_pushed
    ON commit_events(repo_config_id, pushed_at DESC);

-- Index for commit_analyses looked up by commit_event_id
CREATE INDEX IF NOT EXISTS idx_commit_analyses_event_id
    ON commit_analyses(commit_event_id);