# ═══════════════════════════════════════════════════════════════
# NHRS Project — OPPM-style data seed script
# Populates objectives, tasks (main + sub), sub-objectives,
# timeline, costs, deliverables, forecasts, risks, and owners.
# ═══════════════════════════════════════════════════════════════
$ErrorActionPreference = "Stop"

$BASE = "http://127.0.0.1:8000"
$AI_BASE = "http://127.0.0.1:8001"
$WS = "2d319367-0375-4da1-96d5-a81aded02a77"
$PROJ = "17d8e127-e8ea-4332-9a81-da07be46b8e7"

# Members (from workspace)
$MEMBER_OWNER = "aa1d1d96-65c9-4f76-b48c-5e6fb3c1e94f"    # vai (owner)
$MEMBER_2     = "b11364de-d9f3-4a5a-a08f-0dda11002320"    # member
$USER_OWNER   = "60022a50-249e-422c-80c7-bb8294d2c7b5"    # vai user_id
$USER_2       = "771a5647-dd03-4a1b-bde9-17c63d80d170"    # member user_id

# ── Login ──────────────────────────────────────────────────
Write-Host "=== Logging in ===" -ForegroundColor Cyan
$login = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST -ContentType "application/json" -Body '{"email":"vai@gmail.com","password":"12345678"}'
$TOK = $login.access_token
$headers = @{Authorization="Bearer $TOK"; "Content-Type"="application/json"}
Write-Host "  Token acquired" -ForegroundColor Green

function ApiPost($url, $body) {
    return Invoke-RestMethod -Uri $url -Method POST -Headers $headers -Body ($body | ConvertTo-Json -Depth 5)
}
function ApiPut($url, $body) {
    return Invoke-RestMethod -Uri $url -Method PUT -Headers $headers -Body ($body | ConvertTo-Json -Depth 5)
}
function ApiDelete($url) {
    try { Invoke-RestMethod -Uri $url -Method DELETE -Headers $headers } catch {}
}

$wsBase = "$BASE/api/v1/workspaces/$WS"
$projBase = "$wsBase/projects/$PROJ"

# ── Step 1: Clean existing data ───────────────────────────
Write-Host "`n=== Cleaning existing data ===" -ForegroundColor Cyan

# Delete existing tasks
$existingTasks = Invoke-RestMethod -Uri "$wsBase/tasks?project_id=$PROJ&page_size=200" -Headers $headers
if ($existingTasks -is [array]) {
    foreach ($t in $existingTasks) { ApiDelete "$wsBase/tasks/$($t.id)" }
    Write-Host "  Deleted $($existingTasks.Count) tasks" -ForegroundColor Yellow
}

# Delete existing objectives
$oppm = Invoke-RestMethod -Uri "$projBase/oppm" -Headers $headers
foreach ($obj in $oppm.objectives) { ApiDelete "$wsBase/oppm/objectives/$($obj.id)" }
Write-Host "  Deleted $($oppm.objectives.Count) objectives" -ForegroundColor Yellow

# Delete existing sub-objectives
foreach ($so in $oppm.sub_objectives) { ApiDelete "$wsBase/oppm/sub-objectives/$($so.id)" }
Write-Host "  Deleted $($oppm.sub_objectives.Count) sub-objectives" -ForegroundColor Yellow

# Delete existing deliverables, forecasts, risks
if ($oppm.deliverables) { foreach ($d in $oppm.deliverables) { ApiDelete "$wsBase/oppm/deliverables/$($d.id)" } }
if ($oppm.forecasts) { foreach ($f in $oppm.forecasts) { ApiDelete "$wsBase/oppm/forecasts/$($f.id)" } }
if ($oppm.risks) { foreach ($r in $oppm.risks) { ApiDelete "$wsBase/oppm/risks/$($r.id)" } }
Write-Host "  Cleaned deliverables/forecasts/risks" -ForegroundColor Yellow

# ── Step 2: Update project info ───────────────────────────
Write-Host "`n=== Updating project metadata ===" -ForegroundColor Cyan
ApiPut "$projBase" @{
    objective_summary = "Build Cambodia's national FHIR-compliant health record sharing platform with AI-powered clinical assistance, serving 500+ health facilities"
    deliverable_output = "Production-ready NHRS system: FHIR API gateway, patient consent portal, mobile clinician app, AI diagnostic assistant, and national data warehouse"
    description = "The National Health Record Sharing System (NHRS) enables secure sharing of electronic health records across Cambodia's healthcare network using HL7 FHIR standards, with AES-256-GCM encryption and AI-powered clinical decision support."
}
Write-Host "  Project info updated" -ForegroundColor Green

# ── Step 3: Create 6 Sub-Objectives ───────────────────────
Write-Host "`n=== Creating sub-objectives ===" -ForegroundColor Cyan
$subObjectives = @(
    @{position=1; label="FHIR Compliance"},
    @{position=2; label="Security & Privacy"},
    @{position=3; label="Interoperability"},
    @{position=4; label="User Experience"},
    @{position=5; label="Scalability"},
    @{position=6; label="AI Integration"}
)
$soIds = @{}
foreach ($so in $subObjectives) {
    $created = ApiPost "$projBase/oppm/sub-objectives" $so
    $soIds[$so.position] = $created.id
    Write-Host "  Sub-Obj $($so.position): $($so.label) = $($created.id)" -ForegroundColor Green
}

# ── Step 4: Create Objectives + Tasks (OPPM hierarchy) ────
Write-Host "`n=== Creating objectives and tasks ===" -ForegroundColor Cyan

# Helper: create main task then subs underneath
function CreateTaskGroup($objId, $mainTask, $subTasks) {
    # Create main task (no parent)
    $main = ApiPost "$wsBase/tasks" @{
        title = $mainTask.title
        description = $mainTask.description
        project_id = $PROJ
        oppm_objective_id = $objId
        priority = $mainTask.priority
        project_contribution = $mainTask.contribution
        start_date = $mainTask.start
        due_date = $mainTask.due
        assignee_id = $mainTask.assignee
        status = $mainTask.status
    }
    # Update progress separately
    if ($mainTask.progress -gt 0) {
        ApiPut "$wsBase/tasks/$($main.id)" @{progress=$mainTask.progress; status=$mainTask.status}
    }
    Write-Host "    Main: $($main.title) [$($main.id)]" -ForegroundColor White

    # Set sub-objective links for main task
    if ($mainTask.subObjPositions) {
        $linkIds = @($mainTask.subObjPositions | ForEach-Object { $soIds[$_] })
        ApiPut "$projBase/oppm/tasks/$($main.id)/sub-objectives" @{sub_objective_ids=$linkIds}
    }

    # Set owner priority for main task (one PUT per owner)
    if ($mainTask.ownerPriority) {
        foreach ($op in $mainTask.ownerPriority) {
            ApiPut "$projBase/oppm/tasks/$($main.id)/owners" @{member_id=$op.member; priority=$op.priority}
        }
    }

    $subResults = @()
    foreach ($sub in $subTasks) {
        $s = ApiPost "$wsBase/tasks" @{
            title = $sub.title
            description = $sub.description
            project_id = $PROJ
            parent_task_id = $main.id
            oppm_objective_id = $objId
            priority = $sub.priority
            project_contribution = $sub.contribution
            start_date = $sub.start
            due_date = $sub.due
            assignee_id = $sub.assignee
            status = $sub.status
        }
        if ($sub.progress -gt 0) {
            ApiPut "$wsBase/tasks/$($s.id)" @{progress=$sub.progress; status=$sub.status}
        }
        # Sub-objective links for sub-task
        if ($sub.subObjPositions) {
            $linkIds = @($sub.subObjPositions | ForEach-Object { $soIds[$_] })
            ApiPut "$projBase/oppm/tasks/$($s.id)/sub-objectives" @{sub_objective_ids=$linkIds}
        }
        # Owner priority for sub-task (one PUT per owner)
        if ($sub.ownerPriority) {
            foreach ($op in $sub.ownerPriority) {
                ApiPut "$projBase/oppm/tasks/$($s.id)/owners" @{member_id=$op.member; priority=$op.priority}
            }
        }
        Write-Host "      Sub: $($s.title)" -ForegroundColor DarkGray
        $subResults += $s
    }
    return @{main=$main; subs=$subResults}
}

# ────────────────────────────────────────────────────────────
# OBJECTIVE 1: Requirements & Regulatory Compliance
# ────────────────────────────────────────────────────────────
$obj1 = ApiPost "$projBase/oppm/objectives" @{title="Requirements & Regulatory Compliance"; sort_order=1}
Write-Host "  Obj 1: $($obj1.title)" -ForegroundColor Yellow

$t1 = CreateTaskGroup $obj1.id @{
    title="Stakeholder requirements gathering"
    description="Conduct workshops with MoH, hospitals, clinics to document functional & non-functional requirements"
    priority="critical"; contribution=8; start="2026-03-18"; due="2026-03-25"
    assignee=$USER_OWNER; status="completed"; progress=100
    subObjPositions=@(1,4)
    ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"}, @{member=$MEMBER_2; priority="B"})
} @(
    @{title="MoH policy review & gap analysis"; description="Review current health data policies and identify compliance gaps"; priority="high"; contribution=3; start="2026-03-18"; due="2026-03-20"; assignee=$USER_OWNER; status="completed"; progress=100; subObjPositions=@(1,2); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="FHIR R4 resource mapping workshop"; description="Map Cambodia health data elements to FHIR R4 profiles (Patient, Encounter, Observation, DiagnosticReport)"; priority="high"; contribution=4; start="2026-03-20"; due="2026-03-24"; assignee=$USER_2; status="completed"; progress=100; subObjPositions=@(1,3); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Data privacy impact assessment"; description="DPIA for handling PHI across multi-facility network"; priority="critical"; contribution=3; start="2026-03-22"; due="2026-03-25"; assignee=$USER_OWNER; status="completed"; progress=100; subObjPositions=@(2); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})}
)

$t2 = CreateTaskGroup $obj1.id @{
    title="Regulatory framework documentation"
    description="Document compliance requirements for Cambodia health data regulations and international standards"
    priority="high"; contribution=5; start="2026-03-25"; due="2026-03-28"
    assignee=$USER_2; status="completed"; progress=100
    subObjPositions=@(1,2)
    ownerPriority=@(@{member=$MEMBER_2; priority="A"}, @{member=$MEMBER_OWNER; priority="B"})
} @(
    @{title="HL7 FHIR conformance statement"; description="Draft FHIR capability statement and conformance resources"; priority="high"; contribution=2; start="2026-03-25"; due="2026-03-27"; assignee=$USER_2; status="completed"; progress=100; subObjPositions=@(1,3); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Consent management policy design"; description="Design patient consent workflows per Cambodia data protection guidelines"; priority="high"; contribution=2; start="2026-03-26"; due="2026-03-28"; assignee=$USER_OWNER; status="completed"; progress=100; subObjPositions=@(2,4); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Security classification matrix"; description="Classify data elements by sensitivity level (public, confidential, restricted)"; priority="medium"; contribution=1; start="2026-03-27"; due="2026-03-28"; assignee=$USER_2; status="completed"; progress=100; subObjPositions=@(2); ownerPriority=@(@{member=$MEMBER_2; priority="A"})}
)

# ────────────────────────────────────────────────────────────
# OBJECTIVE 2: System Architecture & Infrastructure
# ────────────────────────────────────────────────────────────
$obj2 = ApiPost "$projBase/oppm/objectives" @{title="System Architecture & Infrastructure"; sort_order=2}
Write-Host "  Obj 2: $($obj2.title)" -ForegroundColor Yellow

$t3 = CreateTaskGroup $obj2.id @{
    title="Cloud infrastructure provisioning"
    description="Set up AWS/Azure infrastructure with multi-AZ deployment for high availability"
    priority="critical"; contribution=7; start="2026-03-25"; due="2026-04-01"
    assignee=$USER_OWNER; status="completed"; progress=100
    subObjPositions=@(2,5)
    ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})
} @(
    @{title="Kubernetes cluster setup"; description="Deploy EKS cluster with auto-scaling node groups, Istio service mesh"; priority="critical"; contribution=3; start="2026-03-25"; due="2026-03-28"; assignee=$USER_OWNER; status="completed"; progress=100; subObjPositions=@(5); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Database cluster (PostgreSQL HA)"; description="Deploy PostgreSQL with streaming replication, automated failover, point-in-time recovery"; priority="critical"; contribution=3; start="2026-03-27"; due="2026-03-31"; assignee=$USER_2; status="completed"; progress=100; subObjPositions=@(5); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="CI/CD pipeline configuration"; description="GitHub Actions workflows for build, test, security scan, deploy to staging/prod"; priority="high"; contribution=2; start="2026-03-29"; due="2026-04-01"; assignee=$USER_OWNER; status="completed"; progress=100; subObjPositions=@(5); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})}
)

$t4 = CreateTaskGroup $obj2.id @{
    title="FHIR API gateway design"
    description="Design and implement FHIR-compliant API gateway with authentication, rate limiting, and audit logging"
    priority="critical"; contribution=8; start="2026-03-28"; due="2026-04-04"
    assignee=$USER_2; status="in_progress"; progress=75
    subObjPositions=@(1,3,5)
    ownerPriority=@(@{member=$MEMBER_2; priority="A"}, @{member=$MEMBER_OWNER; priority="B"})
} @(
    @{title="HAPI FHIR server deployment"; description="Deploy HAPI FHIR R4 server with custom resource validation interceptors"; priority="critical"; contribution=3; start="2026-03-28"; due="2026-04-01"; assignee=$USER_2; status="completed"; progress=100; subObjPositions=@(1,3); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="OAuth2/SMART on FHIR auth"; description="Implement SMART on FHIR authorization with JWT, scopes, and patient context"; priority="critical"; contribution=4; start="2026-04-01"; due="2026-04-04"; assignee=$USER_OWNER; status="in_progress"; progress=60; subObjPositions=@(1,2); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="API rate limiting & throttling"; description="Configure per-facility rate limits, burst handling, circuit breakers"; priority="high"; contribution=2; start="2026-04-02"; due="2026-04-04"; assignee=$USER_2; status="in_progress"; progress=40; subObjPositions=@(2,5); ownerPriority=@(@{member=$MEMBER_2; priority="B"})}
)

# ────────────────────────────────────────────────────────────
# OBJECTIVE 3: Core Platform Development
# ────────────────────────────────────────────────────────────
$obj3 = ApiPost "$projBase/oppm/objectives" @{title="Core Platform Development"; sort_order=3}
Write-Host "  Obj 3: $($obj3.title)" -ForegroundColor Yellow

$t5 = CreateTaskGroup $obj3.id @{
    title="Patient record management module"
    description="Build CRUD operations for patient demographics, medical history, and clinical documents"
    priority="critical"; contribution=10; start="2026-04-01"; due="2026-04-10"
    assignee=$USER_OWNER; status="in_progress"; progress=50
    subObjPositions=@(1,3,4)
    ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})
} @(
    @{title="Patient FHIR resource API"; description="CRUD for Patient, RelatedPerson, Coverage resources with search by identifier, name, DOB"; priority="critical"; contribution=4; start="2026-04-01"; due="2026-04-04"; assignee=$USER_OWNER; status="completed"; progress=100; subObjPositions=@(1,3); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Clinical document storage"; description="Store and retrieve CDA/FHIR DocumentReference with binary attachments (X-rays, lab results)"; priority="high"; contribution=3; start="2026-04-04"; due="2026-04-07"; assignee=$USER_2; status="in_progress"; progress=65; subObjPositions=@(1,4); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Patient consent engine"; description="Digital consent capture, revocation, and purpose-of-use enforcement per FHIR Consent resource"; priority="critical"; contribution=4; start="2026-04-07"; due="2026-04-10"; assignee=$USER_OWNER; status="in_progress"; progress=30; subObjPositions=@(2,4); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})}
)

$t6 = CreateTaskGroup $obj3.id @{
    title="Encounter & observation tracking"
    description="Track patient encounters, vital signs, observations, and diagnostic results across facilities"
    priority="high"; contribution=8; start="2026-04-04"; due="2026-04-11"
    assignee=$USER_2; status="in_progress"; progress=35
    subObjPositions=@(1,3)
    ownerPriority=@(@{member=$MEMBER_2; priority="A"}, @{member=$MEMBER_OWNER; priority="C"})
} @(
    @{title="Encounter workflow engine"; description="Implement admission-discharge-transfer (ADT) workflows with FHIR Encounter resources"; priority="high"; contribution=3; start="2026-04-04"; due="2026-04-07"; assignee=$USER_2; status="in_progress"; progress=50; subObjPositions=@(1,3); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Vital signs & observations API"; description="Observation resources for blood pressure, temperature, O2 saturation, BMI with LOINC coding"; priority="high"; contribution=3; start="2026-04-07"; due="2026-04-09"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(1,3); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Lab results integration"; description="DiagnosticReport and Specimen resources with reference ranges, abnormal flagging"; priority="medium"; contribution=2; start="2026-04-09"; due="2026-04-11"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(1,3,6); ownerPriority=@(@{member=$MEMBER_2; priority="A"})}
)

$t7 = CreateTaskGroup $obj3.id @{
    title="Medication & prescription management"
    description="E-prescribing workflows with drug interaction checking and dispensation tracking"
    priority="high"; contribution=6; start="2026-04-08"; due="2026-04-14"
    assignee=$USER_OWNER; status="todo"; progress=0
    subObjPositions=@(1,4,6)
    ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})
} @(
    @{title="MedicationRequest API"; description="FHIR MedicationRequest with RxNorm/ATC coding, dosage instructions"; priority="high"; contribution=2; start="2026-04-08"; due="2026-04-10"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(1); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Drug interaction checker (AI)"; description="AI-powered drug-drug and drug-allergy interaction warnings using clinical knowledge base"; priority="high"; contribution=3; start="2026-04-10"; due="2026-04-13"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(6); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Pharmacy dispensation tracking"; description="MedicationDispense resource with barcode verification, inventory integration"; priority="medium"; contribution=2; start="2026-04-12"; due="2026-04-14"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(1,4); ownerPriority=@(@{member=$MEMBER_OWNER; priority="B"})}
)

# ────────────────────────────────────────────────────────────
# OBJECTIVE 4: Interoperability & Data Exchange
# ────────────────────────────────────────────────────────────
$obj4 = ApiPost "$projBase/oppm/objectives" @{title="Interoperability & Data Exchange"; sort_order=4}
Write-Host "  Obj 4: $($obj4.title)" -ForegroundColor Yellow

$t8 = CreateTaskGroup $obj4.id @{
    title="Multi-facility data exchange"
    description="Implement cross-facility health record sharing with subscription-based push notifications"
    priority="critical"; contribution=8; start="2026-04-10"; due="2026-04-18"
    assignee=$USER_2; status="todo"; progress=0
    subObjPositions=@(1,3,5)
    ownerPriority=@(@{member=$MEMBER_2; priority="A"}, @{member=$MEMBER_OWNER; priority="B"})
} @(
    @{title="FHIR Subscription framework"; description="Real-time notifications when patient records change across facilities"; priority="critical"; contribution=3; start="2026-04-10"; due="2026-04-13"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(1,3); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Master Patient Index (MPI)"; description="Probabilistic patient matching with name, DOB, national ID, phone number across facilities"; priority="critical"; contribution=4; start="2026-04-12"; due="2026-04-16"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(3,5); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Data transformation pipelines"; description="ETL pipelines converting legacy HL7v2 messages to FHIR bundles for older hospital systems"; priority="high"; contribution=3; start="2026-04-15"; due="2026-04-18"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(3); ownerPriority=@(@{member=$MEMBER_2; priority="A"})}
)

# ────────────────────────────────────────────────────────────
# OBJECTIVE 5: AI & Clinical Decision Support
# ────────────────────────────────────────────────────────────
$obj5 = ApiPost "$projBase/oppm/objectives" @{title="AI & Clinical Decision Support"; sort_order=5}
Write-Host "  Obj 5: $($obj5.title)" -ForegroundColor Yellow

$t9 = CreateTaskGroup $obj5.id @{
    title="AI diagnostic assistant"
    description="Build AI-powered clinical decision support for preliminary diagnoses and treatment recommendations"
    priority="high"; contribution=7; start="2026-04-14"; due="2026-04-22"
    assignee=$USER_OWNER; status="todo"; progress=0
    subObjPositions=@(6,4)
    ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})
} @(
    @{title="Clinical NLP engine"; description="Extract structured medical concepts from free-text clinical notes using medical NLP"; priority="high"; contribution=3; start="2026-04-14"; due="2026-04-17"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(6); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Differential diagnosis engine"; description="AI model for differential diagnosis based on symptoms, vitals, lab results, and patient history"; priority="high"; contribution=3; start="2026-04-17"; due="2026-04-20"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(6); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Treatment recommendation API"; description="Evidence-based treatment suggestions with confidence scores and literature references"; priority="medium"; contribution=2; start="2026-04-20"; due="2026-04-22"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(6,4); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})}
)

# ────────────────────────────────────────────────────────────
# OBJECTIVE 6: Security, Testing & Deployment
# ────────────────────────────────────────────────────────────
$obj6 = ApiPost "$projBase/oppm/objectives" @{title="Security, Testing & Deployment"; sort_order=6}
Write-Host "  Obj 6: $($obj6.title)" -ForegroundColor Yellow

$t10 = CreateTaskGroup $obj6.id @{
    title="Security hardening & penetration testing"
    description="Comprehensive security audit including OWASP Top 10, HIPAA-aligned controls, and penetration testing"
    priority="critical"; contribution=7; start="2026-04-18"; due="2026-04-24"
    assignee=$USER_2; status="todo"; progress=0
    subObjPositions=@(2)
    ownerPriority=@(@{member=$MEMBER_2; priority="A"}, @{member=$MEMBER_OWNER; priority="B"})
} @(
    @{title="AES-256-GCM encryption layer"; description="Encrypt all PHI at rest and in transit with AES-256-GCM, key rotation via AWS KMS"; priority="critical"; contribution=3; start="2026-04-18"; due="2026-04-20"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(2); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="OWASP security assessment"; description="Automated SAST/DAST scanning + manual code review for OWASP Top 10 vulnerabilities"; priority="critical"; contribution=2; start="2026-04-20"; due="2026-04-22"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(2); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Penetration test (external)"; description="Third-party penetration test of all exposed APIs and web interfaces"; priority="high"; contribution=2; start="2026-04-22"; due="2026-04-24"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(2); ownerPriority=@(@{member=$MEMBER_2; priority="A"})}
)

$t11 = CreateTaskGroup $obj6.id @{
    title="Integration testing & UAT"
    description="End-to-end integration testing with hospital partners and user acceptance testing"
    priority="high"; contribution=6; start="2026-04-22"; due="2026-04-28"
    assignee=$USER_OWNER; status="todo"; progress=0
    subObjPositions=@(3,4,5)
    ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})
} @(
    @{title="Cross-facility integration test"; description="Test record sharing between 3 pilot hospitals with real-world scenarios"; priority="high"; contribution=3; start="2026-04-22"; due="2026-04-25"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(3,5); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Load testing (500 concurrent users)"; description="Simulate 500 concurrent users across multiple facilities with JMeter/Gatling"; priority="high"; contribution=2; start="2026-04-24"; due="2026-04-26"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(5); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="UAT with clinical staff"; description="2-day UAT sessions with doctors, nurses, pharmacists at 3 pilot sites"; priority="medium"; contribution=2; start="2026-04-26"; due="2026-04-28"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(4); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})}
)

$t12 = CreateTaskGroup $obj6.id @{
    title="Production deployment & go-live"
    description="Blue-green deployment to production, data migration, monitoring setup, and go-live support"
    priority="critical"; contribution=5; start="2026-04-27"; due="2026-05-01"
    assignee=$USER_OWNER; status="todo"; progress=0
    subObjPositions=@(2,5)
    ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"}, @{member=$MEMBER_2; priority="A"})
} @(
    @{title="Blue-green deployment setup"; description="Zero-downtime deployment with traffic shifting, rollback strategy"; priority="critical"; contribution=2; start="2026-04-27"; due="2026-04-28"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(5); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})},
    @{title="Production monitoring & alerting"; description="Prometheus/Grafana dashboards, PagerDuty alerts for API latency, error rates, PHI access anomalies"; priority="high"; contribution=2; start="2026-04-28"; due="2026-04-30"; assignee=$USER_2; status="todo"; progress=0; subObjPositions=@(5); ownerPriority=@(@{member=$MEMBER_2; priority="A"})},
    @{title="Go-live support & handover"; description="24/7 on-call support during first week, operational runbook handover to MoH IT team"; priority="high"; contribution=2; start="2026-04-30"; due="2026-05-01"; assignee=$USER_OWNER; status="todo"; progress=0; subObjPositions=@(2,5); ownerPriority=@(@{member=$MEMBER_OWNER; priority="A"})}
)

# ── Step 5: Timeline entries ──────────────────────────────
Write-Host "`n=== Creating timeline entries ===" -ForegroundColor Cyan

# Helper: create timeline entries for a set of tasks
function SetTimeline($tasks, $entries) {
    foreach ($e in $entries) {
        try {
            ApiPut "$projBase/oppm/timeline" @{
                task_id = $e.task_id
                week_start = $e.week_start
                status = $e.status
            }
        } catch {
            Write-Host "    Timeline warning: $($_.Exception.Message)" -ForegroundColor DarkYellow
        }
    }
}

# Week starts (Mondays): W1=2026-03-16, W2=03-23, W3=03-30, W4=04-06, W5=04-13, W6=04-20, W7=04-27
# Collect all task IDs
$allTasks = Invoke-RestMethod -Uri "$wsBase/tasks?project_id=$PROJ&page_size=200" -Headers $headers
$taskMap = @{}
foreach ($t in $allTasks) { $taskMap[$t.title] = $t.id }

$timelineEntries = @(
    # Obj 1 tasks (W1-W2 completed)
    @{task_id=$taskMap["Stakeholder requirements gathering"]; week_start="2026-03-16"; status="completed"},
    @{task_id=$taskMap["Stakeholder requirements gathering"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["MoH policy review & gap analysis"]; week_start="2026-03-16"; status="completed"},
    @{task_id=$taskMap["FHIR R4 resource mapping workshop"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["Data privacy impact assessment"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["Regulatory framework documentation"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["HL7 FHIR conformance statement"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["Consent management policy design"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["Security classification matrix"]; week_start="2026-03-23"; status="completed"},

    # Obj 2 tasks (W2-W3 completed, W3 in progress)
    @{task_id=$taskMap["Cloud infrastructure provisioning"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["Cloud infrastructure provisioning"]; week_start="2026-03-30"; status="completed"},
    @{task_id=$taskMap["Kubernetes cluster setup"]; week_start="2026-03-23"; status="completed"},
    @{task_id=$taskMap["Database cluster (PostgreSQL HA)"]; week_start="2026-03-30"; status="completed"},
    @{task_id=$taskMap["CI/CD pipeline configuration"]; week_start="2026-03-30"; status="completed"},
    @{task_id=$taskMap["FHIR API gateway design"]; week_start="2026-03-30"; status="in_progress"},
    @{task_id=$taskMap["FHIR API gateway design"]; week_start="2026-04-06"; status="in_progress"},
    @{task_id=$taskMap["HAPI FHIR server deployment"]; week_start="2026-03-30"; status="completed"},
    @{task_id=$taskMap["OAuth2/SMART on FHIR auth"]; week_start="2026-04-06"; status="in_progress"},
    @{task_id=$taskMap["API rate limiting & throttling"]; week_start="2026-04-06"; status="in_progress"},

    # Obj 3 tasks (W3-W4 in progress, W5+ planned)
    @{task_id=$taskMap["Patient record management module"]; week_start="2026-04-06"; status="in_progress"},
    @{task_id=$taskMap["Patient FHIR resource API"]; week_start="2026-04-06"; status="completed"},
    @{task_id=$taskMap["Clinical document storage"]; week_start="2026-04-06"; status="in_progress"},
    @{task_id=$taskMap["Patient consent engine"]; week_start="2026-04-06"; status="in_progress"},
    @{task_id=$taskMap["Encounter & observation tracking"]; week_start="2026-04-06"; status="in_progress"},
    @{task_id=$taskMap["Encounter workflow engine"]; week_start="2026-04-06"; status="in_progress"},
    @{task_id=$taskMap["Vital signs & observations API"]; week_start="2026-04-06"; status="planned"},
    @{task_id=$taskMap["Lab results integration"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["Medication & prescription management"]; week_start="2026-04-06"; status="planned"},
    @{task_id=$taskMap["Medication & prescription management"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["MedicationRequest API"]; week_start="2026-04-06"; status="planned"},
    @{task_id=$taskMap["Drug interaction checker (AI)"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["Pharmacy dispensation tracking"]; week_start="2026-04-13"; status="planned"},

    # Obj 4 tasks (W5+ planned)
    @{task_id=$taskMap["Multi-facility data exchange"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["Multi-facility data exchange"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["FHIR Subscription framework"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["Master Patient Index (MPI)"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["Master Patient Index (MPI)"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["Data transformation pipelines"]; week_start="2026-04-20"; status="planned"},

    # Obj 5 tasks (W5-W6 planned)
    @{task_id=$taskMap["AI diagnostic assistant"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["AI diagnostic assistant"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["Clinical NLP engine"]; week_start="2026-04-13"; status="planned"},
    @{task_id=$taskMap["Differential diagnosis engine"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["Treatment recommendation API"]; week_start="2026-04-20"; status="planned"},

    # Obj 6 tasks (W6-W7+ planned)
    @{task_id=$taskMap["Security hardening & penetration testing"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["AES-256-GCM encryption layer"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["OWASP security assessment"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["Penetration test (external)"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["Integration testing & UAT"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["Integration testing & UAT"]; week_start="2026-04-27"; status="planned"},
    @{task_id=$taskMap["Cross-facility integration test"]; week_start="2026-04-20"; status="planned"},
    @{task_id=$taskMap["Load testing (500 concurrent users)"]; week_start="2026-04-27"; status="planned"},
    @{task_id=$taskMap["UAT with clinical staff"]; week_start="2026-04-27"; status="planned"},
    @{task_id=$taskMap["Production deployment & go-live"]; week_start="2026-04-27"; status="planned"},
    @{task_id=$taskMap["Blue-green deployment setup"]; week_start="2026-04-27"; status="planned"},
    @{task_id=$taskMap["Production monitoring & alerting"]; week_start="2026-04-27"; status="planned"},
    @{task_id=$taskMap["Go-live support & handover"]; week_start="2026-04-27"; status="planned"}
)

foreach ($e in $timelineEntries) {
    if ($e.task_id) {
        try {
            ApiPut "$projBase/oppm/timeline" @{task_id=$e.task_id; week_start=$e.week_start; status=$e.status}
        } catch { Write-Host "    TL skip: $($_.Exception.Message)" -ForegroundColor DarkYellow }
    } else {
        Write-Host "    TL skip: task not found" -ForegroundColor DarkYellow
    }
}
Write-Host "  Created $($timelineEntries.Count) timeline entries" -ForegroundColor Green

# ── Step 6: Costs ─────────────────────────────────────────
Write-Host "`n=== Creating cost entries ===" -ForegroundColor Cyan
$costs = @(
    @{category="Infrastructure"; description="AWS/Azure cloud hosting (K8s, RDS, S3, CloudFront)"; planned_amount=45000; actual_amount=38500; period="2026-Q1"},
    @{category="Development"; description="Core platform development team (4 engineers x 6 weeks)"; planned_amount=120000; actual_amount=85000; period="2026-Q1"},
    @{category="Security"; description="Penetration testing & security audit (external vendor)"; planned_amount=25000; actual_amount=0; period="2026-Q2"},
    @{category="Licensing"; description="HAPI FHIR Enterprise license + medical terminology (SNOMED, LOINC)"; planned_amount=15000; actual_amount=15000; period="2026-Q1"},
    @{category="AI/ML"; description="LLM API costs (clinical NLP, diagnostic assistant)"; planned_amount=8000; actual_amount=2500; period="2026-Q1"},
    @{category="Training"; description="Clinical staff training & UAT sessions at 3 pilot hospitals"; planned_amount=12000; actual_amount=0; period="2026-Q2"}
)
foreach ($c in $costs) {
    ApiPost "$projBase/oppm/costs" $c
}
Write-Host "  Created $($costs.Count) cost entries" -ForegroundColor Green

# ── Step 7: Deliverables ──────────────────────────────────
Write-Host "`n=== Creating deliverables ===" -ForegroundColor Cyan
$deliverables = @(
    @{item_number=1; description="FHIR R4 compliant API gateway with 99.9% uptime SLA"},
    @{item_number=2; description="Patient consent management portal (web + mobile responsive)"},
    @{item_number=3; description="Clinician mobile app (iOS/Android) for bedside record access"},
    @{item_number=4; description="AI-powered clinical decision support module"},
    @{item_number=5; description="National health data warehouse with analytics dashboard"},
    @{item_number=6; description="Integration adapters for 5 existing hospital information systems"},
    @{item_number=7; description="Operations runbook and MoH IT team training materials"}
)
foreach ($d in $deliverables) { ApiPost "$projBase/oppm/deliverables" $d }
Write-Host "  Created $($deliverables.Count) deliverables" -ForegroundColor Green

# ── Step 8: Forecasts ─────────────────────────────────────
Write-Host "`n=== Creating forecasts ===" -ForegroundColor Cyan
$forecasts = @(
    @{item_number=1; description="Core platform MVP deployed to 3 pilot hospitals by May 1, 2026"},
    @{item_number=2; description="Full national rollout to 500+ facilities by Q3 2026"},
    @{item_number=3; description="1M patient records migrated within first 6 months"},
    @{item_number=4; description="AI diagnostic accuracy target: 85%+ concordance with specialist diagnoses"},
    @{item_number=5; description="System handles 500 concurrent users with <200ms API response time"}
)
foreach ($f in $forecasts) { ApiPost "$projBase/oppm/forecasts" $f }
Write-Host "  Created $($forecasts.Count) forecasts" -ForegroundColor Green

# ── Step 9: Risks ─────────────────────────────────────────
Write-Host "`n=== Creating risks ===" -ForegroundColor Cyan
$risks = @(
    @{item_number=1; description="Legacy hospital systems may not support HL7v2-to-FHIR conversion"; rag="amber"},
    @{item_number=2; description="Patient data privacy breach during cross-facility exchange"; rag="red"},
    @{item_number=3; description="Clinical staff resistance to new digital workflows"; rag="amber"},
    @{item_number=4; description="AI diagnostic model bias on underrepresented conditions"; rag="amber"},
    @{item_number=5; description="Internet connectivity issues at rural health facilities"; rag="red"},
    @{item_number=6; description="Regulatory changes requiring architecture modifications"; rag="green"}
)
foreach ($r in $risks) { ApiPost "$projBase/oppm/risks" $r }
Write-Host "  Created $($risks.Count) risks" -ForegroundColor Green

# ── Summary ───────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "NHRS OPPM Data Seed Complete!" -ForegroundColor Green
Write-Host "  6 Objectives (main task groups)"
Write-Host "  12 Main Tasks"
Write-Host "  36 Sub-Tasks (3 per main task)"
Write-Host "  6 Sub-Objectives"
Write-Host "  ~55 Timeline entries"
Write-Host "  6 Cost entries"
Write-Host "  7 Deliverables"
Write-Host "  5 Forecasts"
Write-Host "  6 Risks"
Write-Host "========================================" -ForegroundColor Cyan
