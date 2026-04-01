-- OPPM AI Work Management System — Database Schema
-- Run this in Supabase SQL Editor

-- ══════════════════════════════════════
-- 1. PROJECTS
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(200) NOT NULL,
  description TEXT DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'planning'
    CHECK (status IN ('planning', 'in_progress', 'completed', 'on_hold', 'cancelled')),
  priority VARCHAR(10) NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'critical')),
  progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  deadline DATE,
  lead_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_priority ON projects(priority);

-- ══════════════════════════════════════
-- 2. OPPM OBJECTIVES
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS oppm_objectives (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title VARCHAR(200) NOT NULL,
  owner_id UUID,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_oppm_objectives_project ON oppm_objectives(project_id);

-- ══════════════════════════════════════
-- 3. TASKS
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(200) NOT NULL,
  description TEXT DEFAULT '',
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  oppm_objective_id UUID REFERENCES oppm_objectives(id) ON DELETE SET NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'todo'
    CHECK (status IN ('todo', 'in_progress', 'completed')),
  priority VARCHAR(10) NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'critical')),
  progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  project_contribution INTEGER NOT NULL DEFAULT 0 CHECK (project_contribution >= 0 AND project_contribution <= 100),
  due_date DATE,
  created_by UUID,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_objective ON tasks(oppm_objective_id);
CREATE INDEX idx_tasks_status ON tasks(status);

-- ══════════════════════════════════════
-- 4. OPPM TIMELINE ENTRIES
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS oppm_timeline_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  objective_id UUID NOT NULL REFERENCES oppm_objectives(id) ON DELETE CASCADE,
  week_start DATE NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned', 'in_progress', 'completed', 'at_risk', 'blocked')),
  ai_score INTEGER CHECK (ai_score >= 0 AND ai_score <= 100),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_timeline_project ON oppm_timeline_entries(project_id);
CREATE INDEX idx_timeline_objective ON oppm_timeline_entries(objective_id);

-- ══════════════════════════════════════
-- 5. GITHUB ACCOUNTS
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS github_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_name VARCHAR(100) NOT NULL,
  github_username VARCHAR(100) NOT NULL,
  encrypted_token TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ══════════════════════════════════════
-- 6. REPO CONFIGURATIONS
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS repo_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_name VARCHAR(200) NOT NULL,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  github_account_id UUID NOT NULL REFERENCES github_accounts(id) ON DELETE CASCADE,
  webhook_secret VARCHAR(200) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_repo_configs_project ON repo_configs(project_id);
CREATE UNIQUE INDEX idx_repo_configs_repo ON repo_configs(repo_name);

-- ══════════════════════════════════════
-- 7. COMMIT EVENTS
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS commit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  repo_config_id UUID NOT NULL REFERENCES repo_configs(id) ON DELETE CASCADE,
  commit_hash VARCHAR(40) NOT NULL,
  commit_message TEXT NOT NULL DEFAULT '',
  author_github_username VARCHAR(100) NOT NULL DEFAULT '',
  branch VARCHAR(200) NOT NULL DEFAULT 'main',
  files_changed TEXT[] DEFAULT '{}',
  additions INTEGER NOT NULL DEFAULT 0,
  deletions INTEGER NOT NULL DEFAULT 0,
  pushed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_commits_repo ON commit_events(repo_config_id);
CREATE INDEX idx_commits_pushed ON commit_events(pushed_at DESC);
CREATE INDEX idx_commits_author ON commit_events(author_github_username);

-- ══════════════════════════════════════
-- 8. COMMIT ANALYSES (AI results)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS commit_analyses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  commit_event_id UUID NOT NULL REFERENCES commit_events(id) ON DELETE CASCADE,
  ai_model VARCHAR(100) NOT NULL,
  task_alignment_score INTEGER NOT NULL DEFAULT 0 CHECK (task_alignment_score >= 0 AND task_alignment_score <= 100),
  code_quality_score INTEGER NOT NULL DEFAULT 0 CHECK (code_quality_score >= 0 AND code_quality_score <= 100),
  progress_delta INTEGER NOT NULL DEFAULT 0 CHECK (progress_delta >= 0 AND progress_delta <= 100),
  summary TEXT NOT NULL DEFAULT '',
  quality_flags TEXT[] DEFAULT '{}',
  suggestions TEXT[] DEFAULT '{}',
  matched_task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
  matched_objective_id UUID REFERENCES oppm_objectives(id) ON DELETE SET NULL,
  analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_analyses_commit ON commit_analyses(commit_event_id);
CREATE INDEX idx_analyses_task ON commit_analyses(matched_task_id);

-- ══════════════════════════════════════
-- 9. AI MODELS
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS ai_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  provider VARCHAR(20) NOT NULL CHECK (provider IN ('ollama', 'anthropic', 'openai', 'kimi', 'custom')),
  model_id VARCHAR(100) NOT NULL,
  endpoint_url VARCHAR(300),
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ══════════════════════════════════════
-- 10. MEMBERS (optional, for team features)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(200) NOT NULL,
  email VARCHAR(200) UNIQUE NOT NULL,
  avatar_url TEXT,
  role VARCHAR(50) NOT NULL DEFAULT 'developer',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ══════════════════════════════════════
-- AUTO-UPDATE TIMESTAMPS TRIGGER
-- ══════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tasks_updated_at
  BEFORE UPDATE ON tasks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ══════════════════════════════════════
-- SEED DEFAULT AI MODELS
-- ══════════════════════════════════════
INSERT INTO ai_models (name, provider, model_id, endpoint_url, is_active)
VALUES
  ('Kimi K2.5', 'kimi', 'kimi-k2.5:cloud', NULL, true),
  ('CodeLlama (Ollama)', 'ollama', 'codellama:latest', 'http://localhost:11434', true),
  ('Claude Sonnet', 'anthropic', 'claude-sonnet-4-20250514', NULL, false)
ON CONFLICT DO NOTHING;

-- ══════════════════════════════════════
-- ROW LEVEL SECURITY (basic)
-- ══════════════════════════════════════
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE oppm_objectives ENABLE ROW LEVEL SECURITY;
ALTER TABLE commit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE commit_analyses ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users full access (for solo/demo use)
CREATE POLICY "Allow all for authenticated" ON projects
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON tasks
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON oppm_objectives
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON commit_events
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON commit_analyses
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON github_accounts
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON repo_configs
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON ai_models
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON oppm_timeline_entries
  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON members
  FOR ALL USING (true) WITH CHECK (true);
