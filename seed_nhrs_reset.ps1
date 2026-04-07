# ═══════════════════════════════════════════════════════════════
# NHRS Project — Clean reset seed (4 objectives × 3 root tasks)
# Wipes all existing objectives/tasks, adds 2 project members,
# creates a clean 4×3 structure that fits the OPPM template exactly.
# Usage: ./seed_nhrs_reset.ps1
# ═══════════════════════════════════════════════════════════════
$ErrorActionPreference = "Stop"

$BASE = "http://127.0.0.1:8000"
$WS   = "2d319367-0375-4da1-96d5-a81aded02a77"
$PROJ = "17d8e127-e8ea-4332-9a81-da07be46b8e7"

# Workspace member IDs (NOT user_ids — these reference workspace_members.id)
$MEMBER_OWNER = "aa1d1d96-65c9-4f76-b48c-5e6fb3c1e94f"   # vai (owner)
$MEMBER_2     = "b11364de-d9f3-4a5a-a08f-0dda11002320"   # member 2
# User IDs (used for task assignee_id)
$USER_OWNER   = "60022a50-249e-422c-80c7-bb8294d2c7b5"
$USER_2       = "771a5647-dd03-4a1b-bde9-17c63d80d170"

# ── Login ──────────────────────────────────────────────────
Write-Host "=== Logging in ===" -ForegroundColor Cyan
$login   = Invoke-RestMethod -Uri "$BASE/api/auth/login" -Method POST `
               -ContentType "application/json" `
               -Body '{"email":"vai@gmail.com","password":"12345678"}'
$TOK     = $login.access_token
$headers = @{ Authorization = "Bearer $TOK"; "Content-Type" = "application/json" }
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

$wsBase   = "$BASE/api/v1/workspaces/$WS"
$projBase = "$wsBase/projects/$PROJ"

# ── Step 1: Wipe existing tasks ────────────────────────────
Write-Host "`n=== Deleting all existing tasks ===" -ForegroundColor Cyan
$existingTasks = Invoke-RestMethod -Uri "$wsBase/tasks?project_id=$PROJ&page_size=200" -Headers $headers
$taskList = if ($existingTasks -is [array]) { $existingTasks } `
            elseif ($existingTasks.items) { $existingTasks.items } `
            else { @() }
foreach ($t in $taskList) { ApiDelete "$wsBase/tasks/$($t.id)" }
Write-Host "  Deleted $($taskList.Count) tasks" -ForegroundColor Yellow

# ── Step 2: Wipe existing objectives (+ sub-objectives) ───
Write-Host "`n=== Deleting all existing objectives ===" -ForegroundColor Cyan
$oppm = Invoke-RestMethod -Uri "$projBase/oppm" -Headers $headers
foreach ($obj in $oppm.objectives) { ApiDelete "$wsBase/oppm/objectives/$($obj.id)" }
foreach ($so  in $oppm.sub_objectives) { ApiDelete "$wsBase/oppm/sub-objectives/$($so.id)" }
Write-Host "  Deleted $($oppm.objectives.Count) objectives, $($oppm.sub_objectives.Count) sub-objectives" -ForegroundColor Yellow

# ── Step 3: Add project members ────────────────────────────
Write-Host "`n=== Adding project members ===" -ForegroundColor Cyan
# Remove any existing members first (ignore errors)
$existingMembers = try {
    (Invoke-RestMethod -Uri "$projBase/members" -Headers $headers)
} catch { @() }
$memberList = if ($existingMembers -is [array]) { $existingMembers } `
              elseif ($existingMembers.items) { $existingMembers.items } `
              else { @() }
foreach ($m in $memberList) {
    try { ApiDelete "$projBase/members/$($m.id)" } catch {}
}

# Add owner as lead (user_id field accepts workspace_member_id per the API)
try {
    ApiPost "$projBase/members" @{ user_id = $MEMBER_OWNER; role = "lead" } | Out-Null
    Write-Host "  Added vai (lead)" -ForegroundColor Green
} catch { Write-Host "  vai already member (skipped)" -ForegroundColor DarkYellow }

try {
    ApiPost "$projBase/members" @{ user_id = $MEMBER_2; role = "contributor" } | Out-Null
    Write-Host "  Added member 2 (contributor)" -ForegroundColor Green
} catch { Write-Host "  member 2 already member (skipped)" -ForegroundColor DarkYellow }

# ── Step 4: Create 4 objectives × 3 root tasks ────────────
Write-Host "`n=== Creating 4 objectives and 12 root tasks ===" -ForegroundColor Cyan

# Helper: create one root task under an objective
function MakeTask($objId, $title, $due, $assignee, $status = "todo") {
    $t = ApiPost "$wsBase/tasks" @{
        title             = $title
        project_id        = $PROJ
        oppm_objective_id = $objId
        due_date          = $due
        assignee_id       = $assignee
        status            = $status
        priority          = "high"
    }
    Write-Host "    $($t.title)" -ForegroundColor DarkGray
    return $t
}

# ── Objective 1 ────────────────────────────────────────────
$obj1 = ApiPost "$projBase/oppm/objectives" @{ title = "Requirements & Policy Analysis"; sort_order = 10 }
Write-Host "  Obj 1: $($obj1.title)" -ForegroundColor Yellow
MakeTask $obj1.id "Stakeholder requirements gathering"  "2026-03-25" $USER_OWNER "completed" | Out-Null
MakeTask $obj1.id "MoH policy review & gap analysis"    "2026-03-20" $USER_OWNER "completed" | Out-Null
MakeTask $obj1.id "FHIR R4 resource mapping workshop"   "2026-03-24" $USER_2     "completed" | Out-Null

# ── Objective 2 ────────────────────────────────────────────
$obj2 = ApiPost "$projBase/oppm/objectives" @{ title = "Compliance & Data Governance"; sort_order = 20 }
Write-Host "  Obj 2: $($obj2.title)" -ForegroundColor Yellow
MakeTask $obj2.id "Data privacy impact assessment"      "2026-03-25" $USER_OWNER "completed" | Out-Null
MakeTask $obj2.id "Regulatory framework documentation"  "2026-03-28" $USER_2     "completed" | Out-Null
MakeTask $obj2.id "HL7 FHIR conformance statement"      "2026-03-27" $USER_2     "completed" | Out-Null

# ── Objective 3 ────────────────────────────────────────────
$obj3 = ApiPost "$projBase/oppm/objectives" @{ title = "Security & Infrastructure Design"; sort_order = 30 }
Write-Host "  Obj 3: $($obj3.title)" -ForegroundColor Yellow
MakeTask $obj3.id "Consent management policy design"    "2026-03-28" $USER_OWNER "completed" | Out-Null
MakeTask $obj3.id "Security classification matrix"      "2026-03-28" $USER_2     "completed" | Out-Null
MakeTask $obj3.id "Cloud infrastructure provisioning"   "2026-04-01" $USER_OWNER "completed" | Out-Null

# ── Objective 4 ────────────────────────────────────────────
$obj4 = ApiPost "$projBase/oppm/objectives" @{ title = "System Architecture & Design"; sort_order = 40 }
Write-Host "  Obj 4: $($obj4.title)" -ForegroundColor Yellow
MakeTask $obj4.id "Kubernetes cluster setup"            "2026-03-28" $USER_OWNER "completed" | Out-Null
MakeTask $obj4.id "Database cluster (PostgreSQL HA)"    "2026-03-31" $USER_2     "completed" | Out-Null
MakeTask $obj4.id "CI/CD pipeline configuration"        "2026-04-01" $USER_OWNER "in_progress" | Out-Null

Write-Host "`n=== Done ===" -ForegroundColor Green
Write-Host "  4 objectives, 12 root tasks created" -ForegroundColor Green
Write-Host "  2 project members added (vai=lead, member2=contributor)" -ForegroundColor Green
Write-Host "`nNow open the NHRS OPPM view, click Reset then AI Fill." -ForegroundColor Cyan
