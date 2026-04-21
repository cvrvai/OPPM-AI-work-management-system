// ── Waterfall Types ──

export type PhaseType = 'requirements' | 'design' | 'development' | 'testing' | 'deployment' | 'maintenance'
export type PhaseStatus = 'not_started' | 'in_progress' | 'completed' | 'approved'
export type DocumentType = 'srs' | 'sdd' | 'test_plan' | 'release_notes' | 'general'

export interface ProjectPhase {
  id: string
  workspace_id: string
  project_id: string
  phase_type: PhaseType
  status: PhaseStatus
  position: number
  start_date: string | null
  end_date: string | null
  gate_approved_by: string | null
  gate_approved_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PhaseDocument {
  id: string
  workspace_id: string
  project_id: string
  phase_id: string
  title: string
  content: string
  document_type: DocumentType
  version: number
  created_by: string | null
  created_at: string
  updated_at: string
}
