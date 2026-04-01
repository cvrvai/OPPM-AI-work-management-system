-- ══════════════════════════════════════════════════════════════
-- OPPM AI Work Management System — Database Schema (v2)
-- Multi-tenant, workspace-scoped, OPPM-compliant
-- ══════════════════════════════════════════════════════════════

-- ══════════════════════════════════════
-- 1. WORKSPACES (multi-tenant root)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(200) NOT NULL,
  slug VARCHAR(100) NOT NULL UNIQUE,
  description TEXT DEFAULT '',
  plan VARCHAR(20) NOT NULL DEFAULT 'free'
    CHECK (plan IN ('free', 'pro', 'enterprise')),
  settings JSONB DEFAULT '{}',
  created_by UUID NOT NULL,  -- references auth.users(id)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_workspaces_slug ON workspaces(slug);

-- ══════════════════════════════════════
-- 2. WORKSPACE MEMBERS (links auth.users → workspace)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS workspace_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id UUID NOT NULL,  -- references auth.users(id)
  role VARCHAR(20) NOT NULL DEFAULT 'member'
    CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
  display_name VARCHAR(200),
  avatar_url TEXT,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, user_id)
);

CREATE INDEX idx_ws_members_workspace ON workspace_members(workspace_id);
CREATE INDEX idx_ws_members_user ON workspace_members(user_id);

-- ══════════════════════════════════════
-- 3. WORKSPACE INVITES
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS workspace_invites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  email VARCHAR(300) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'member'
    CHECK (role IN ('admin', 'member', 'viewer')),
  invited_by UUID NOT NULL,  -- references auth.users(id)
  token VARCHAR(64) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  accepted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ws_invites_workspace ON workspace_invites(workspace_id);
CREATE INDEX idx_ws_invites_token ON workspace_invites(token);

-- ══════════════════════════════════════
-- 4. PROJECTS (workspace-scoped)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title VARCHAR(200) NOT NULL,
  description TEXT DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'planning'
    CHECK (status IN ('planning', 'in_progress', 'completed', 'on_hold', 'cancelled')),
  priority VARCHAR(10) NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'critical')),
  progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  start_date DATE,
  deadline DATE,
  lead_id UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_projects_workspace ON projects(workspace_id);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_priority ON projects(priority);

-- ══════════════════════════════════════
-- 5. PROJECT MEMBERS (team assignment for OPPM)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS project_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  member_id UUID NOT NULL REFERENCES workspace_members(id) ON DELETE CASCADE,
  role VARCHAR(30) NOT NULL DEFAULT 'contributor'
    CHECK (role IN ('lead', 'contributor', 'reviewer', 'observer')),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(project_id, member_id)
);

CREATE INDEX idx_project_members_project ON project_members(project_id);
CREATE INDEX idx_project_members_member ON project_members(member_id);

-- ══════════════════════════════════════
-- 6. OPPM OBJECTIVES (sub-objectives)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS oppm_objectives (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title VARCHAR(200) NOT NULL,
  owner_id UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_oppm_objectives_project ON oppm_objectives(project_id);

-- ══════════════════════════════════════
-- 7. TASKS (workspace-scoped via project)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(200) NOT NULL,
  description TEXT DEFAULT '',
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  oppm_objective_id UUID REFERENCES oppm_objectives(id) ON DELETE SET NULL,
  assignee_id UUID REFERENCES workspace_members(id) ON DELETE SET NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'todo'
    CHECK (status IN ('todo', 'in_progress', 'completed')),
  priority VARCHAR(10) NOT NULL DEFAULT 'medium'
    CHECK (priority IN ('low', 'medium', 'high', 'critical')),
  progress INTEGER NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
  project_contribution INTEGER NOT NULL DEFAULT 0 CHECK (project_contribution >= 0 AND project_contribution <= 100),
  due_date DATE,
  created_by UUID,  -- references auth.users(id)
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_objective ON tasks(oppm_objective_id);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id);
CREATE INDEX idx_tasks_status ON tasks(status);

-- ══════════════════════════════════════
-- 8. TASK ASSIGNEES (multi-assign junction)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS task_assignees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  member_id UUID NOT NULL REFERENCES workspace_members(id) ON DELETE CASCADE,
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(task_id, member_id)
);

CREATE INDEX idx_task_assignees_task ON task_assignees(task_id);
CREATE INDEX idx_task_assignees_member ON task_assignees(member_id);

-- ══════════════════════════════════════
-- 9. OPPM TIMELINE ENTRIES (weekly dots)
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
-- 10. PROJECT COSTS (OPPM costs quadrant)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS project_costs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  category VARCHAR(100) NOT NULL,
  description TEXT DEFAULT '',
  planned_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
  actual_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
  period VARCHAR(20),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_project_costs_project ON project_costs(project_id);

-- ══════════════════════════════════════
-- 11. GITHUB ACCOUNTS (workspace-scoped)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS github_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  account_name VARCHAR(100) NOT NULL,
  github_username VARCHAR(100) NOT NULL,
  encrypted_token TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_github_accounts_workspace ON github_accounts(workspace_id);

-- ══════════════════════════════════════
-- 12. REPO CONFIGURATIONS
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
-- 13. COMMIT EVENTS
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
-- 14. COMMIT ANALYSES (AI results)
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
-- 15. AI MODELS (workspace-scoped)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS ai_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  provider VARCHAR(20) NOT NULL CHECK (provider IN ('ollama', 'anthropic', 'openai', 'kimi', 'custom')),
  model_id VARCHAR(100) NOT NULL,
  endpoint_url VARCHAR(300),
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_models_workspace ON ai_models(workspace_id);

-- ══════════════════════════════════════
-- 16. NOTIFICATIONS (user-scoped)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id UUID,  -- references auth.users(id)
  type VARCHAR(50) NOT NULL DEFAULT 'info'
    CHECK (type IN ('info', 'success', 'warning', 'error', 'ai_analysis', 'commit', 'task_update')),
  title VARCHAR(300) NOT NULL,
  message TEXT DEFAULT '',
  is_read BOOLEAN NOT NULL DEFAULT false,
  link VARCHAR(500),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_workspace ON notifications(workspace_id);
CREATE INDEX idx_notifications_read ON notifications(is_read);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);

-- ══════════════════════════════════════
-- 17. AUDIT LOG (compliance trail)
-- ══════════════════════════════════════
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  user_id UUID,  -- references auth.users(id)
  action VARCHAR(50) NOT NULL,
  entity_type VARCHAR(50) NOT NULL,
  entity_id UUID,
  old_data JSONB,
  new_data JSONB,
  ip_address INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_workspace ON audit_log(workspace_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

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

CREATE TRIGGER workspaces_updated_at
  BEFORE UPDATE ON workspaces
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tasks_updated_at
  BEFORE UPDATE ON tasks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER project_costs_updated_at
  BEFORE UPDATE ON project_costs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ══════════════════════════════════════
-- ROW LEVEL SECURITY (workspace-scoped)
-- ══════════════════════════════════════
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE oppm_objectives ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_assignees ENABLE ROW LEVEL SECURITY;
ALTER TABLE oppm_timeline_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_costs ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE repo_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE commit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE commit_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- ── Helper: check if user is member of a workspace ──
CREATE OR REPLACE FUNCTION is_workspace_member(ws_id UUID)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM workspace_members
    WHERE workspace_id = ws_id AND user_id = auth.uid()
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ── Helper: check if user has admin+ role ──
CREATE OR REPLACE FUNCTION is_workspace_admin(ws_id UUID)
RETURNS BOOLEAN AS $$
  SELECT EXISTS (
    SELECT 1 FROM workspace_members
    WHERE workspace_id = ws_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'admin')
  );
$$ LANGUAGE sql SECURITY DEFINER STABLE;

-- ── Workspaces: user can see workspaces they belong to ──
CREATE POLICY "ws_select" ON workspaces
  FOR SELECT USING (is_workspace_member(id));
CREATE POLICY "ws_insert" ON workspaces
  FOR INSERT WITH CHECK (created_by = auth.uid());
CREATE POLICY "ws_update" ON workspaces
  FOR UPDATE USING (is_workspace_admin(id));
CREATE POLICY "ws_delete" ON workspaces
  FOR DELETE USING (
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = id AND user_id = auth.uid() AND role = 'owner'
    )
  );

-- ── Workspace Members: visible to workspace members ──
CREATE POLICY "wsm_select" ON workspace_members
  FOR SELECT USING (is_workspace_member(workspace_id));
CREATE POLICY "wsm_insert" ON workspace_members
  FOR INSERT WITH CHECK (is_workspace_admin(workspace_id));
CREATE POLICY "wsm_update" ON workspace_members
  FOR UPDATE USING (is_workspace_admin(workspace_id));
CREATE POLICY "wsm_delete" ON workspace_members
  FOR DELETE USING (is_workspace_admin(workspace_id));

-- ── Workspace Invites ──
CREATE POLICY "wsi_select" ON workspace_invites
  FOR SELECT USING (is_workspace_member(workspace_id));
CREATE POLICY "wsi_insert" ON workspace_invites
  FOR INSERT WITH CHECK (is_workspace_admin(workspace_id));
CREATE POLICY "wsi_delete" ON workspace_invites
  FOR DELETE USING (is_workspace_admin(workspace_id));

-- ── Projects: workspace-scoped ──
CREATE POLICY "proj_select" ON projects
  FOR SELECT USING (is_workspace_member(workspace_id));
CREATE POLICY "proj_insert" ON projects
  FOR INSERT WITH CHECK (is_workspace_member(workspace_id));
CREATE POLICY "proj_update" ON projects
  FOR UPDATE USING (is_workspace_member(workspace_id));
CREATE POLICY "proj_delete" ON projects
  FOR DELETE USING (is_workspace_admin(workspace_id));

-- ── Project Members ──
CREATE POLICY "pm_select" ON project_members
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "pm_insert" ON project_members
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "pm_delete" ON project_members
  FOR DELETE USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_admin(p.workspace_id))
  );

-- ── OPPM Objectives: workspace-scoped via project ──
CREATE POLICY "obj_select" ON oppm_objectives
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "obj_insert" ON oppm_objectives
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "obj_update" ON oppm_objectives
  FOR UPDATE USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "obj_delete" ON oppm_objectives
  FOR DELETE USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_admin(p.workspace_id))
  );

-- ── Tasks: workspace-scoped via project ──
CREATE POLICY "task_select" ON tasks
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "task_insert" ON tasks
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "task_update" ON tasks
  FOR UPDATE USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "task_delete" ON tasks
  FOR DELETE USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_admin(p.workspace_id))
  );

-- ── Task Assignees ──
CREATE POLICY "ta_select" ON task_assignees
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM tasks t
      JOIN projects p ON p.id = t.project_id
      WHERE t.id = task_id AND is_workspace_member(p.workspace_id)
    )
  );
CREATE POLICY "ta_manage" ON task_assignees
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM tasks t
      JOIN projects p ON p.id = t.project_id
      WHERE t.id = task_id AND is_workspace_member(p.workspace_id)
    )
  );

-- ── Timeline Entries ──
CREATE POLICY "tl_select" ON oppm_timeline_entries
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "tl_manage" ON oppm_timeline_entries
  FOR ALL USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );

-- ── Project Costs ──
CREATE POLICY "cost_select" ON project_costs
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "cost_manage" ON project_costs
  FOR ALL USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );

-- ── GitHub Accounts: workspace-scoped ──
CREATE POLICY "gh_select" ON github_accounts
  FOR SELECT USING (is_workspace_member(workspace_id));
CREATE POLICY "gh_insert" ON github_accounts
  FOR INSERT WITH CHECK (is_workspace_member(workspace_id));
CREATE POLICY "gh_delete" ON github_accounts
  FOR DELETE USING (is_workspace_admin(workspace_id));

-- ── Repo Configs: via project workspace ──
CREATE POLICY "rc_select" ON repo_configs
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );
CREATE POLICY "rc_manage" ON repo_configs
  FOR ALL USING (
    EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND is_workspace_member(p.workspace_id))
  );

-- ── Commit Events: via repo → project → workspace ──
CREATE POLICY "ce_select" ON commit_events
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM repo_configs rc
      JOIN projects p ON p.id = rc.project_id
      WHERE rc.id = repo_config_id AND is_workspace_member(p.workspace_id)
    )
  );
CREATE POLICY "ce_insert" ON commit_events
  FOR INSERT WITH CHECK (true);  -- webhooks insert via service role

-- ── Commit Analyses: via commit → repo → project → workspace ──
CREATE POLICY "ca_select" ON commit_analyses
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM commit_events ce
      JOIN repo_configs rc ON rc.id = ce.repo_config_id
      JOIN projects p ON p.id = rc.project_id
      WHERE ce.id = commit_event_id AND is_workspace_member(p.workspace_id)
    )
  );
CREATE POLICY "ca_insert" ON commit_analyses
  FOR INSERT WITH CHECK (true);  -- service role inserts

-- ── AI Models: workspace-scoped ──
CREATE POLICY "ai_select" ON ai_models
  FOR SELECT USING (is_workspace_member(workspace_id));
CREATE POLICY "ai_manage" ON ai_models
  FOR ALL USING (is_workspace_admin(workspace_id));

-- ── Notifications: user-scoped ──
CREATE POLICY "notif_select" ON notifications
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "notif_insert" ON notifications
  FOR INSERT WITH CHECK (true);  -- service role inserts
CREATE POLICY "notif_update" ON notifications
  FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "notif_delete" ON notifications
  FOR DELETE USING (user_id = auth.uid());

-- ── Audit Log: workspace admins only ──
CREATE POLICY "audit_select" ON audit_log
  FOR SELECT USING (is_workspace_admin(workspace_id));
CREATE POLICY "audit_insert" ON audit_log
  FOR INSERT WITH CHECK (true);  -- service role inserts
