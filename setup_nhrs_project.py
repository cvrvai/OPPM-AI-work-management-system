import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'oppm',
    'user': 'oppm',
    'password': 'oppm_dev_password'
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def create_nhrs_project(cur):
    """Create the NHRS project in the projects table."""
    workspace_id = '4cb12b24-daca-4c05-8ebd-75eb58e16bd1'  # ic project workspace
    lead_id = '6c0a23bf-5ffd-40f9-87fb-a6b06aee940f'  # workspace member id for choonvai@gmail.com

    project_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO projects (
            id, workspace_id, title, description, status, priority, progress,
            start_date, deadline, lead_id, metadata, project_code, objective_summary,
            budget, planning_hours, methodology
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s
        )
    """, (
        project_id, workspace_id,
        'National Health Record Sharing System (NHRS)',
        'Multi-phase health record sharing system with AI-powered clinical assistance, FHIR R4 compliance, and ML intelligence. Version 3.0.',
        'in_progress', 'critical', 0,
        '2026-01-01', '2026-08-02', lead_id,
        '{"version": "3.0", "date": "2026-03-22", "compliance_target": 64, "compliance_current": 51}',
        'NHRS-3.0',
        'Build a secure, FHIR-compliant health record sharing system with AI clinical assistance and ML intelligence.',
        0, 0, 'oppm'
    ))
    print(f"Created NHRS project with ID: {project_id}")
    return project_id

def create_new_tables(cur):
    """Create new tables needed for full OPPM support."""

    # 1. Project Team Members
    cur.execute("""
        CREATE TABLE IF NOT EXISTS project_team_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            role VARCHAR(100),
            responsibility TEXT,
            priority_level VARCHAR(20) CHECK (priority_level IN ('primary_owner', 'primary_helper', 'secondary_helper')),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("Created project_team_members table")

    # 2. Project Compliance Scores
    cur.execute("""
        CREATE TABLE IF NOT EXISTS project_compliance_scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            domain VARCHAR(100) NOT NULL,
            score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 10),
            max_score SMALLINT NOT NULL DEFAULT 10,
            rating VARCHAR(20),
            recorded_at DATE DEFAULT CURRENT_DATE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("Created project_compliance_scores table")

    # 3. Phase Tasks (sub-tasks under each phase)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS phase_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phase_id UUID NOT NULL REFERENCES project_phases(id) ON DELETE CASCADE,
            task_number VARCHAR(10),
            title VARCHAR(200) NOT NULL,
            assigned_to UUID REFERENCES project_team_members(id),
            status VARCHAR(20) DEFAULT 'not_started'
                CHECK (status IN ('not_started', 'in_progress', 'complete')),
            target_date DATE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("Created phase_tasks table")

def insert_team_members(cur, project_id):
    """Insert NHRS team members."""
    members = [
        (project_id, 'Cheong Choonvai', 'Project Lead', 'Frontend, RAG-SYSTEM, Architecture', 'primary_owner'),
        (project_id, 'Sothea', 'Backend Lead', 'Backend API, Infrastructure, Database', 'primary_helper'),
        (project_id, 'Lyhour', 'Governance Lead', 'AI Safety, Compliance, Policy Framework', 'primary_helper'),
        (project_id, 'Parinha', 'ML Engineer', 'ML-Service Models, Training Pipelines', 'secondary_helper'),
    ]
    cur.executemany("""
        INSERT INTO project_team_members (project_id, name, role, responsibility, priority_level)
        VALUES (%s, %s, %s, %s, %s)
    """, members)
    print(f"Inserted {len(members)} team members")

def insert_sub_objectives(cur, project_id):
    """Insert NHRS sub objectives (6 columns)."""
    objectives = [
        (project_id, 1, 'Security & Auth', 'JWT, MFA, RBAC, AES-256-GCM encryption, Redis blocklist', 'complete'),
        (project_id, 2, 'Consent & Privacy', 'Patient consent model, RLS, PDPA compliance, audit logging', 'complete'),
        (project_id, 3, 'Clinical Standards', 'FHIR R4, ICD-10, LOINC, RxNorm, SOAP notes, drug interactions', 'in_progress'),
        (project_id, 4, 'AI & RAG System', 'Dual Qdrant retrieval, governance injection, Ollama LLM', 'in_progress'),
        (project_id, 5, 'ML Intelligence', 'Risk scorer, disease classifier, anomaly detector, readmission', 'not_started'),
        (project_id, 6, 'Ops & Reliability', 'CI/CD, Sentry monitoring, k6 load testing, key rotation', 'not_started'),
    ]
    # Use existing oppm_sub_objectives table (label column instead of title)
    cur.executemany("""
        INSERT INTO oppm_sub_objectives (project_id, position, label)
        VALUES (%s, %s, %s)
    """, [(pid, pos, label) for pid, pos, label, desc, stat in objectives])
    print(f"Inserted {len(objectives)} sub objectives")

def insert_phases(cur, project_id):
    """Insert NHRS phases. Returns dict of phase_number -> phase_id."""
    workspace_id = '4cb12b24-daca-4c05-8ebd-75eb58e16bd1'
    phases = [
        (project_id, 1, 'Phase 1 — Production Safety Gates', 'requirements', '2026-03-22', 'completed'),
        (project_id, 2, 'Phase 2 — Clinical Standards Foundation', 'design', '2026-05-03', 'in_progress'),
        (project_id, 3, 'Phase 3 — Clinical Workflow Completion', 'development', '2026-06-14', 'not_started'),
        (project_id, 4, 'Phase 4 — Advanced AI Intelligence', 'testing', '2026-07-12', 'not_started'),
        (project_id, 5, 'Phase 5 — Operations & Reliability', 'deployment', '2026-08-02', 'not_started'),
    ]

    phase_ids = {}
    for pid, num, title, phase_type, end_date, status in phases:
        phase_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO project_phases (id, workspace_id, project_id, phase_type, status, position, end_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (phase_id, workspace_id, pid, phase_type, status, num, end_date))
        phase_ids[num] = phase_id
        print(f"Inserted phase {num}: {title} -> {phase_id}")

    return phase_ids

def insert_phase_tasks(cur, phase_ids):
    """Insert tasks under each phase."""
    tasks_data = {
        1: [
            ('1.1', 'Redis JWT blocklist implementation', 'complete', '2026-01-15'),
            ('1.2', 'AES-256-GCM encryption layer', 'complete', '2026-01-20'),
            ('1.3', 'RAG consent gating', 'complete', '2026-02-01'),
            ('1.4', 'Rate limiting middleware', 'complete', '2026-02-10'),
            ('1.5', 'Test suite (103 tests passing)', 'complete', '2026-02-15'),
            ('1.6', 'RBAC integration tests', 'complete', '2026-02-20'),
            ('1.7', 'Audit READ logging', 'complete', '2026-02-25'),
            ('1.8', 'Database SSL configuration', 'complete', '2026-03-01'),
        ],
        2: [
            ('2.1', 'ICD-10 code field on medical records', 'not_started', '2026-04-10'),
            ('2.2', 'LOINC codes on lab results', 'not_started', '2026-04-12'),
            ('2.3', 'RxNorm codes on prescriptions', 'not_started', '2026-04-13'),
            ('2.4', 'FHIR R4 adapter layer', 'not_started', '2026-04-17'),
            ('2.5', 'FHIR R4 API endpoints', 'not_started', '2026-04-19'),
            ('2.6', 'Data retention policy (7yr)', 'not_started', '2026-04-20'),
            ('2.7', 'UI: ICD-10 picker component', 'not_started', '2026-04-22'),
            ('2.8', 'UI: SOAP note structured form', 'not_started', '2026-04-25'),
            ('2.9', 'UI: LOINC picker for lab orders', 'not_started', '2026-04-26'),
        ],
        3: [
            ('3.1', 'SOAP note model', 'not_started', '2026-05-15'),
            ('3.2', 'Drug interaction service', 'not_started', '2026-05-20'),
            ('3.3', 'Allergy model', 'not_started', '2026-05-25'),
            ('3.4', 'Discharge summary service', 'not_started', '2026-05-30'),
            ('3.5', 'Referral model', 'not_started', '2026-06-01'),
            ('3.6', 'Lab notifications', 'not_started', '2026-06-05'),
            ('3.7', 'UI: Drug warning component', 'not_started', '2026-06-08'),
            ('3.8', 'UI: Discharge form', 'not_started', '2026-06-10'),
            ('3.9', 'UI: Consent scope picker', 'not_started', '2026-06-12'),
            ('3.10', 'UI: Allergy badge', 'not_started', '2026-06-14'),
        ],
        4: [
            ('4.1', 'Confidence scoring engine', 'not_started', '2026-06-20'),
            ('4.2', 'Hallucination detection', 'not_started', '2026-06-25'),
            ('4.3', 'ML-Service integration', 'not_started', '2026-06-30'),
            ('4.4', 'Chain-of-thought reasoning', 'not_started', '2026-07-05'),
            ('4.5', 'UI: Confidence bar', 'not_started', '2026-07-08'),
            ('4.6', 'UI: Risk score badge', 'not_started', '2026-07-10'),
            ('4.7', 'UI: Disclaimer modal', 'not_started', '2026-07-12'),
        ],
        5: [
            ('5.1', 'CI/CD GitHub Actions pipeline', 'not_started', '2026-07-15'),
            ('5.2', 'Sentry monitoring setup', 'not_started', '2026-07-18'),
            ('5.3', 'k6 load testing suite', 'not_started', '2026-07-22'),
            ('5.4', 'AES key rotation service', 'not_started', '2026-07-25'),
            ('5.5', 'Redis Sentinel HA setup', 'not_started', '2026-07-28'),
            ('5.6', 'UI: Health status dashboard', 'not_started', '2026-07-30'),
            ('5.7', 'UI: Audit PDF export', 'not_started', '2026-08-01'),
            ('5.8', 'UI: Patient access ledger', 'not_started', '2026-08-02'),
        ],
    }

    total = 0
    for phase_num, tasks in tasks_data.items():
        phase_id = phase_ids[phase_num]
        for task_num, title, status, target_date in tasks:
            cur.execute("""
                INSERT INTO phase_tasks (phase_id, task_number, title, status, target_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (phase_id, task_num, title, status, target_date))
            total += 1
    print(f"Inserted {total} phase tasks")

def insert_compliance_scores(cur, project_id):
    """Insert compliance scores."""
    scores = [
        (project_id, 'Authentication & Security', 8, 10, 'Strong'),
        (project_id, 'RBAC & Access Control', 7, 10, 'Good — needs tests'),
        (project_id, 'Consent Management', 8, 10, 'Strong'),
        (project_id, 'Audit Logging', 6, 10, 'Partial'),
        (project_id, 'Encryption & Data Protection', 8, 10, 'Strong'),
        (project_id, 'Clinical Data Standards (FHIR)', 2, 10, 'Major Gap'),
        (project_id, 'Privacy & PDPA Compliance', 6, 10, 'Partial'),
        (project_id, 'AI Clinical Safety', 6, 10, 'In Progress'),
    ]
    cur.executemany("""
        INSERT INTO project_compliance_scores (project_id, domain, score, max_score, rating)
        VALUES (%s, %s, %s, %s, %s)
    """, scores)
    print(f"Inserted {len(scores)} compliance scores")

def insert_deliverables(cur, project_id):
    """Insert summary deliverables."""
    deliverables = [
        (project_id, 1, 'AES-256-GCM encrypted medical records with consent gating', 'done'),
        (project_id, 2, 'JWT + TOTP MFA authentication with Redis token revocation', 'done'),
        (project_id, 3, 'AI-powered RAG clinical assistant with governance injection', 'done'),
        (project_id, 4, 'FHIR R4 compliant API with ICD-10 / LOINC / RxNorm coding', 'in_progress'),
        (project_id, 5, 'ML risk scoring and disease classification integrated in UI', 'planned'),
        (project_id, 6, 'Full CI/CD pipeline with monitoring, load testing, key rotation', 'planned'),
    ]
    # Existing oppm_deliverables uses 'description' not 'title', and no 'status' column
    cur.executemany("""
        INSERT INTO oppm_deliverables (project_id, item_number, description)
        VALUES (%s, %s, %s)
    """, [(pid, num, desc) for pid, num, desc, stat in deliverables])
    print(f"Inserted {len(deliverables)} deliverables")

def insert_forecasts(cur, project_id):
    """Insert forecast / expectations."""
    forecasts = [
        (project_id, 1, 'System production-ready after Phase 5 completion (Aug 2026)'),
        (project_id, 2, 'FHIR R4 compliance achieved in Phase 2 — enables external system integration'),
        (project_id, 3, 'Ollama concurrency bottleneck becomes critical at 10+ simultaneous users'),
        (project_id, 4, 'Compliance score reaches minimum 64/80 threshold by end of Phase 3'),
    ]
    # Existing oppm_forecasts uses 'description' not 'expectation'
    cur.executemany("""
        INSERT INTO oppm_forecasts (project_id, item_number, description)
        VALUES (%s, %s, %s)
    """, forecasts)
    print(f"Inserted {len(forecasts)} forecasts")

def insert_risks(cur, project_id):
    """Insert risks."""
    risks = [
        (project_id, 1, 'No drug interaction checking — unsafe for clinical prescription use', 'red'),
        (project_id, 2, 'Clinical data standards (FHIR/ICD-10) score only 2/10 — no interoperability', 'red'),
        (project_id, 3, 'Ollama single-threaded LLM causes queuing under concurrent AI load', 'amber'),
        (project_id, 4, 'No AES key rotation mechanism — cannot safely rotate encryption keys', 'red'),
    ]
    # Existing oppm_risks uses 'description' and 'rag'
    cur.executemany("""
        INSERT INTO oppm_risks (project_id, item_number, description, rag)
        VALUES (%s, %s, %s, %s)
    """, risks)
    print(f"Inserted {len(risks)} risks")

def verify_data(cur, project_id):
    """Run verification queries."""
    print("\n" + "="*60)
    print("VERIFICATION RESULTS")
    print("="*60)

    # Project
    cur.execute("SELECT title, status, priority, progress FROM projects WHERE id = %s", (project_id,))
    row = cur.fetchone()
    print(f"\nProject: {row[0]} | Status: {row[1]} | Priority: {row[2]} | Progress: {row[3]}%")

    # Team Members
    cur.execute("SELECT name, role, priority_level FROM project_team_members WHERE project_id = %s ORDER BY priority_level", (project_id,))
    print("\n--- Team Members ---")
    for r in cur.fetchall():
        print(f"  {r[0]} | {r[1]} | {r[2]}")

    # Sub Objectives
    cur.execute("SELECT position, label FROM oppm_sub_objectives WHERE project_id = %s ORDER BY position", (project_id,))
    print("\n--- Sub Objectives ---")
    for r in cur.fetchall():
        print(f"  {r[0]}. {r[1]}")

    # Phases
    cur.execute("SELECT position, phase_type, status, end_date FROM project_phases WHERE project_id = %s ORDER BY position", (project_id,))
    print("\n--- Phases ---")
    for r in cur.fetchall():
        print(f"  Phase {r[0]} | Type: {r[1]} | Status: {r[2]} | End: {r[3]}")

    # Phase Tasks
    cur.execute("""
        SELECT pt.task_number, pt.title, pt.status, pt.target_date, pp.position as phase_num
        FROM phase_tasks pt
        JOIN project_phases pp ON pt.phase_id = pp.id
        WHERE pp.project_id = %s
        ORDER BY pt.task_number
    """, (project_id,))
    print("\n--- Phase Tasks ---")
    for r in cur.fetchall():
        print(f"  {r[0]} | {r[1]} | Status: {r[2]} | Target: {r[3]} | Phase: {r[4]}")

    # Compliance Scores
    cur.execute("SELECT domain, score, max_score, rating FROM project_compliance_scores WHERE project_id = %s", (project_id,))
    print("\n--- Compliance Scores ---")
    total = 0
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}/{r[2]} | {r[3]}")
        total += r[1]
    print(f"  TOTAL: {total}/80")

    # Deliverables
    cur.execute("SELECT item_number, description FROM oppm_deliverables WHERE project_id = %s ORDER BY item_number", (project_id,))
    print("\n--- Deliverables ---")
    for r in cur.fetchall():
        print(f"  {r[0]}. {r[1]}")

    # Forecasts
    cur.execute("SELECT item_number, description FROM oppm_forecasts WHERE project_id = %s ORDER BY item_number", (project_id,))
    print("\n--- Forecasts ---")
    for r in cur.fetchall():
        print(f"  {r[0]}. {r[1]}")

    # Risks
    cur.execute("SELECT item_number, description, rag FROM oppm_risks WHERE project_id = %s ORDER BY item_number", (project_id,))
    print("\n--- Risks ---")
    for r in cur.fetchall():
        print(f"  {r[0]}. [{r[2].upper()}] {r[1]}")

def main():
    conn = get_connection()
    cur = conn.cursor()

    try:
        print("Creating new tables...")
        create_new_tables(cur)

        print("\nCreating NHRS project...")
        project_id = create_nhrs_project(cur)

        print("\nInserting team members...")
        insert_team_members(cur, project_id)

        print("\nInserting sub objectives...")
        insert_sub_objectives(cur, project_id)

        print("\nInserting phases...")
        phase_ids = insert_phases(cur, project_id)

        print("\nInserting phase tasks...")
        insert_phase_tasks(cur, phase_ids)

        print("\nInserting compliance scores...")
        insert_compliance_scores(cur, project_id)

        print("\nInserting deliverables...")
        insert_deliverables(cur, project_id)

        print("\nInserting forecasts...")
        insert_forecasts(cur, project_id)

        print("\nInserting risks...")
        insert_risks(cur, project_id)

        conn.commit()
        print("\nAll data committed successfully!")

        verify_data(cur, project_id)

        print(f"\n{'='*60}")
        print(f"NHRS Project ID: {project_id}")
        print(f"Use this ID for all future queries.")
        print(f"{'='*60}")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
