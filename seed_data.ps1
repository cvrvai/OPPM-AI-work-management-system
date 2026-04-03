#!/usr/bin/env pwsh
# seed_data.ps1 - Seeds demo data for cheongchoonvai@gmail.com (PS 5.1 compatible)

param(
    [string]$ApiBase  = "http://localhost:8000",
    [string]$Email    = "cheongchoonvai@gmail.com",
    [string]$Password = "12345678"
)

$ErrorActionPreference = "Continue"

# ── Helpers ──────────────────────────────────────────────────────────────────

function Get-ErrMsg {
    param($ex)
    if ($ex.ErrorDetails -and $ex.ErrorDetails.Message) { return $ex.ErrorDetails.Message }
    return $ex.Exception.Message
}

function Invoke-Post {
    param($url, $body)
    $json = $body | ConvertTo-Json -Depth 10
    try {
        Invoke-RestMethod $url -Method POST `
            -Headers @{Authorization="Bearer $($global:TOKEN)"; "Content-Type"="application/json"} `
            -Body $json
    } catch {
        Write-Host "  [ERR] POST $url -> $(Get-ErrMsg $_)" -ForegroundColor Red
        return $null
    }
}

function Invoke-Get {
    param($url)
    try {
        Invoke-RestMethod $url -Headers @{Authorization="Bearer $($global:TOKEN)"}
    } catch {
        Write-Host "  [ERR] GET $url -> $(Get-ErrMsg $_)" -ForegroundColor Red
        return $null
    }
}

function Invoke-Put {
    param($url, $body)
    $json = $body | ConvertTo-Json -Depth 10
    try {
        Invoke-RestMethod $url -Method PUT `
            -Headers @{Authorization="Bearer $($global:TOKEN)"; "Content-Type"="application/json"} `
            -Body $json
    } catch {
        Write-Host "  [ERR] PUT $url -> $(Get-ErrMsg $_)" -ForegroundColor Red
        return $null
    }
}

function Register-FakeUser {
    param($email, $password, $fullName)
    $body = (@{email=$email; password=$password; full_name=$fullName} | ConvertTo-Json)
    try {
        Invoke-RestMethod "$ApiBase/api/auth/signup" -Method POST `
            -Headers @{"Content-Type"="application/json"} -Body $body | Out-Null
        Write-Host "  Registered $email" -ForegroundColor Green
        return $true
    } catch {
        $msg = Get-ErrMsg $_
        if ($msg -like "*already*" -or $msg -like "*exists*") {
            Write-Host "  $email already exists - OK" -ForegroundColor DarkYellow
            return $true
        }
        Write-Host "  [ERR] signup $email -> $msg" -ForegroundColor Red
        return $false
    }
}

function Login-FakeUser {
    param($email, $password)
    $body = (@{email=$email; password=$password} | ConvertTo-Json)
    try {
        $r = Invoke-RestMethod "$ApiBase/api/auth/login" -Method POST `
            -Headers @{"Content-Type"="application/json"} -Body $body
        return $r.access_token
    } catch {
        Write-Host "  [ERR] login $email -> $(Get-ErrMsg $_)" -ForegroundColor Red
        return $null
    }
}

# ── Step 1: Login as owner ────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Seeding OPPM Demo Data ===" -ForegroundColor Cyan
Write-Host "Logging in as $Email..."
$global:TOKEN = Login-FakeUser $Email $Password
Write-Host "  OK" -ForegroundColor Green

# ── Step 2: Get or create workspace ──────────────────────────────────────────
Write-Host "Getting workspace..."
$workspaces = Invoke-Get "$ApiBase/api/v1/workspaces"
$ws = $workspaces | Where-Object { $_.slug -eq "oppm-demo" } | Select-Object -First 1
if (-not $ws) {
    $ws = Invoke-Post "$ApiBase/api/v1/workspaces" @{
        name        = "OPPM Demo"
        slug        = "oppm-demo"
        description = "Demo workspace for testing OPPM features"
    }
}
$WS = $ws.id
Write-Host "  Workspace: $($ws.name) [$WS]" -ForegroundColor Green

$base = "$ApiBase/api/v1/workspaces/$WS"

# ── Step 3: Register fake users ───────────────────────────────────────────────
Write-Host ""
Write-Host "Registering team members..."
Register-FakeUser "alice.chen@oppm.demo"   "Demo@12345" "Alice Chen"   | Out-Null
Register-FakeUser "bob.martinez@oppm.demo" "Demo@12345" "Bob Martinez" | Out-Null
Register-FakeUser "carol.kim@oppm.demo"    "Demo@12345" "Carol Kim"    | Out-Null
Register-FakeUser "david.osei@oppm.demo"   "Demo@12345" "David Osei"   | Out-Null
Register-FakeUser "eva.nguyen@oppm.demo"   "Demo@12345" "Eva Nguyen"   | Out-Null

# ── Step 4: Invite and auto-accept ───────────────────────────────────────────
Write-Host ""
Write-Host "Inviting members to workspace..."

function Invite-AndAccept {
    param($memberEmail, $memberPass, $memberName, $role)
    $inv = Invoke-Post "$base/invites" @{email=$memberEmail; role=$role}
    if ($inv -and $inv.token) {
        $mTok = Login-FakeUser $memberEmail $memberPass
        if ($mTok) {
            try {
                Invoke-RestMethod "$ApiBase/api/v1/invites/accept" -Method POST `
                    -Headers @{Authorization="Bearer $mTok"; "Content-Type"="application/json"} `
                    -Body ("{""token"":""$($inv.token)""}")  | Out-Null
                Write-Host "  $memberName joined as $role" -ForegroundColor Green
            } catch {
                Write-Host "  [WARN] accept invite ${memberEmail}: $(Get-ErrMsg $_)" -ForegroundColor DarkYellow
            }
        }
    } else {
        Write-Host "  [WARN] invite failed for $memberEmail" -ForegroundColor DarkYellow
    }
}

Invite-AndAccept "alice.chen@oppm.demo"   "Demo@12345" "Alice Chen"   "member"
Invite-AndAccept "bob.martinez@oppm.demo" "Demo@12345" "Bob Martinez" "member"
Invite-AndAccept "carol.kim@oppm.demo"    "Demo@12345" "Carol Kim"    "admin"
Invite-AndAccept "david.osei@oppm.demo"   "Demo@12345" "David Osei"   "member"
Invite-AndAccept "eva.nguyen@oppm.demo"   "Demo@12345" "Eva Nguyen"   "member"

# Fetch member list to get user_ids
$wsMembers = Invoke-Get "$base/members"
Write-Host "  Members in workspace: $($wsMembers.Count)"

function Find-WsMember {
    param($name)
    $wsMembers | Where-Object {
        ($_.display_name -and $_.display_name -like "*$name*") -or
        ($_.email -and $_.email -like "*$name*")
    } | Select-Object -First 1
}

$alice = Find-WsMember "alice"
$bob   = Find-WsMember "bob"
$carol = Find-WsMember "carol"
$david = Find-WsMember "david"
$eva   = Find-WsMember "eva"

# ── Step 5: Create Projects (idempotent by title) ────────────────────────────
Write-Host ""
Write-Host "Creating projects..."

$existingProjectsResp = Invoke-Get "$base/projects?page_size=100"
$existingProjects = if ($existingProjectsResp -and $existingProjectsResp.items) { $existingProjectsResp.items } else { @() }
function Get-OrCreateProject {
    param($title, $description, $status, $priority, $start_date, $deadline)
    $existing = $existingProjects | Where-Object { $_.title -eq $title } | Select-Object -First 1
    if ($existing) {
        Write-Host "  Project exists: $title [$($existing.id)]" -ForegroundColor DarkYellow
        return $existing
    }
    $proj = Invoke-Post "$base/projects" @{
        title       = $title
        description = $description
        status      = $status
        priority    = $priority
        start_date  = $start_date
        deadline    = $deadline
    }
    Write-Host "  Created: $($proj.title)" -ForegroundColor Green
    return $proj
}

$p1 = Get-OrCreateProject `
    "Downtown Office Expansion" `
    "Expand headquarters to accommodate 50 new hires. Includes floor renovation, IT infrastructure, and ergonomic workstations." `
    "in_progress" "high" "2026-01-15" "2026-09-30"

$p2 = Get-OrCreateProject `
    "ERP System Rollout" `
    "Company-wide deployment of SAP S4HANA replacing legacy finance and procurement systems. Phased rollout across 3 regions." `
    "in_progress" "critical" "2026-02-01" "2026-12-31"

$p3 = Get-OrCreateProject `
    "Customer Self-Service Portal" `
    "Web portal for customers to manage accounts, submit tickets, and track order history. Targets 30 percent reduction in support call volume." `
    "planning" "medium" "2026-04-01" "2026-10-31"

$P1 = $p1.id
$P2 = $p2.id
$P3 = $p3.id

# ── Step 6: Add project members ───────────────────────────────────────────────
Write-Host ""
Write-Host "Adding project members..."
foreach ($projId in @($P1, $P2, $P3)) {
    foreach ($m in ($wsMembers | Where-Object { $_.role -ne "owner" })) {
        $mbody = @{user_id=$m.user_id; role="member"} | ConvertTo-Json
        try {
            Invoke-RestMethod "$base/projects/$projId/members" -Method POST `
                -Headers @{Authorization="Bearer $($global:TOKEN)"; "Content-Type"="application/json"} `
                -Body $mbody | Out-Null
        } catch {
            # silently ignore duplicate-member 409 errors
        }
    }
}
Write-Host "  Done" -ForegroundColor Green

# ── Step 7: OPPM Objectives (idempotent – skip if already exist) ──────────────
Write-Host ""
Write-Host "Creating OPPM objectives..."

function Add-Objective {
    param($projId, $title, $status, $progress, $targetDate, $ownerId)
    $body = @{
        title       = $title
        status      = $status
        progress    = $progress
        target_date = $targetDate
    }
    if ($ownerId) { $body.owner_id = $ownerId }
    Invoke-Post "$base/projects/$projId/oppm/objectives" $body | Out-Null
}

# Check if objectives already exist; if so, skip creation
$objP1existing = Invoke-Get "$base/projects/$P1/oppm/objectives"
if (-not $objP1existing -or $objP1existing.Count -eq 0) {
    Add-Objective $P1 "Select and sign lease for new floor"           "completed"   100 "2026-02-28" $alice.user_id
    Add-Objective $P1 "Complete architectural design and permits"     "completed"   100 "2026-04-15" $bob.user_id
    Add-Objective $P1 "Renovate open-plan workspace Phase 1"          "in_progress"  55 "2026-06-30" $bob.user_id
    Add-Objective $P1 "Deploy structured cabling and network"         "in_progress"  40 "2026-07-15" $carol.user_id
    Add-Objective $P1 "Procure and install 50 ergonomic workstations" "planned"       0 "2026-08-31" $david.user_id
    Add-Objective $P1 "Staff relocation and change management"        "planned"       0 "2026-09-20" $eva.user_id
    Add-Objective $P1 "Post-move audit and snag resolution"           "planned"       0 "2026-09-30" $alice.user_id
}

$objP2existing = Invoke-Get "$base/projects/$P2/oppm/objectives"
if (-not $objP2existing -or $objP2existing.Count -eq 0) {
    Add-Objective $P2 "Finalise ERP scope and vendor contract"        "completed"   100 "2026-02-15" $alice.user_id
    Add-Objective $P2 "Data migration strategy and cleansing"         "completed"   100 "2026-03-31" $carol.user_id
    Add-Objective $P2 "Core module configuration Finance and HR"      "in_progress"  70 "2026-05-31" $bob.user_id
    Add-Objective $P2 "User acceptance testing Region 1"              "in_progress"  30 "2026-07-31" $david.user_id
    Add-Objective $P2 "Go-live Region 1 North America"                "planned"       0 "2026-08-15" $alice.user_id
    Add-Objective $P2 "Roll out Region 2 Europe and cutover"          "planned"       0 "2026-10-31" $eva.user_id
    Add-Objective $P2 "Decommission legacy finance system"            "planned"       0 "2026-12-15" $carol.user_id
}

$objP3existing = Invoke-Get "$base/projects/$P3/oppm/objectives"
if (-not $objP3existing -or $objP3existing.Count -eq 0) {
    Add-Objective $P3 "Define UX requirements and wireframes"         "in_progress"  80 "2026-04-30" $eva.user_id
    Add-Objective $P3 "Backend API design and security review"        "in_progress"  50 "2026-05-15" $carol.user_id
    Add-Objective $P3 "Identity and SSO integration OAuth2"           "planned"       0 "2026-06-30" $carol.user_id
    Add-Objective $P3 "Build account management module"               "planned"       0 "2026-07-31" $bob.user_id
    Add-Objective $P3 "Build ticketing and order history modules"     "planned"       0 "2026-08-31" $david.user_id
    Add-Objective $P3 "Load testing and security penetration test"    "planned"       0 "2026-09-30" $alice.user_id
    Add-Objective $P3 "Public launch and support handover"            "planned"       0 "2026-10-20" $eva.user_id
}

# Always re-fetch to get final objective IDs (no @() wrapper - preserves array type)
$objP1 = Invoke-Get "$base/projects/$P1/oppm/objectives"
$objP2 = Invoke-Get "$base/projects/$P2/oppm/objectives"
$objP3 = Invoke-Get "$base/projects/$P3/oppm/objectives"
$totalObjs = @($objP1).Count + @($objP2).Count + @($objP3).Count
Write-Host "  $totalObjs objectives ready" -ForegroundColor Green

# ── Step 8: Timeline entries ──────────────────────────────────────────────────
Write-Host ""
Write-Host "Creating timeline entries..."

$weeks    = "2026-01-19","2026-02-02","2026-02-16","2026-03-02","2026-03-16","2026-03-30",
            "2026-04-13","2026-04-27","2026-05-11","2026-05-25"
$tlStatus = "completed","completed","completed","completed","in_progress","in_progress",
            "planned","planned","planned","planned"
$tlNotes  = "Sprint closed all tasks done","Sprint closed on schedule","Milestone hit",
            "Phase wrap-up complete","Active sprint on track","Active sprint minor delay",
            "Upcoming","Upcoming","Upcoming","Upcoming"

$timelineCount = 0
# Three separate loops to avoid PS array-boxing in hashtables
foreach ($obj in @($objP1)) {
    if (-not $obj -or -not $obj.id) { continue }
    foreach ($i in @(0, 4, 8)) {
        $r = Invoke-Put "$base/projects/$P1/oppm/timeline" @{
            objective_id = [string]$obj.id
            week_start   = $weeks[$i]
            status       = $tlStatus[$i]
            notes        = $tlNotes[$i]
        }
        if ($r) { $timelineCount++ }
    }
}
foreach ($obj in @($objP2)) {
    if (-not $obj -or -not $obj.id) { continue }
    foreach ($i in @(0, 4, 8)) {
        $r = Invoke-Put "$base/projects/$P2/oppm/timeline" @{
            objective_id = [string]$obj.id
            week_start   = $weeks[$i]
            status       = $tlStatus[$i]
            notes        = $tlNotes[$i]
        }
        if ($r) { $timelineCount++ }
    }
}
foreach ($obj in @($objP3)) {
    if (-not $obj -or -not $obj.id) { continue }
    foreach ($i in @(0, 4, 8)) {
        $r = Invoke-Put "$base/projects/$P3/oppm/timeline" @{
            objective_id = [string]$obj.id
            week_start   = $weeks[$i]
            status       = $tlStatus[$i]
            notes        = $tlNotes[$i]
        }
        if ($r) { $timelineCount++ }
    }
}
Write-Host "  $timelineCount timeline entries created" -ForegroundColor Green

# ── Step 9: Cost rows ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Creating cost rows..."

function Add-Cost {
    param($projId, $category, $planned, $actual, $description)
    Invoke-Post "$base/projects/$projId/oppm/costs" @{
        category       = $category
        planned_amount = $planned
        actual_amount  = $actual
        description    = $description
    } | Out-Null
}

Add-Cost $P1 "Lease and Legal"           85000  87200  "Lease signed, legal fees finalized"
Add-Cost $P1 "Architecture and Permits"  30000  28500  "Drawings approved, under budget"
Add-Cost $P1 "Construction and Fit-out"  420000 195000 "Phase 1 underway"
Add-Cost $P1 "IT Infrastructure"         95000  38000  "Cabling and switches ordered"
Add-Cost $P1 "Furniture and Equipment"   110000 0      "Pending procurement"
Add-Cost $P1 "Change Management"         15000  0      "Planned for Q3"

Add-Cost $P2 "SAP Licensing"             480000 480000 "Licenses purchased"
Add-Cost $P2 "Implementation Partner"    650000 312000 "Phase 1 delivery in progress"
Add-Cost $P2 "Data Migration"            75000  82000  "Over budget due to data quality issues"
Add-Cost $P2 "Training and Change Mgmt"  60000  18000  "Train-the-trainer complete"
Add-Cost $P2 "Infrastructure Upgrade"    90000  55000  "Hardware installed at Region 1"
Add-Cost $P2 "Contingency Reserve"       120000 0      "Reserved for go-live risks"

Add-Cost $P3 "UX and UI Design"          45000  22000  "Wireframes and prototype done"
Add-Cost $P3 "Backend Development"       180000 35000  "API scaffolding complete"
Add-Cost $P3 "Frontend Development"      120000 10000  "Component library set up"
Add-Cost $P3 "Security and Penetration"  25000  0      "Scheduled for Q3"
Add-Cost $P3 "Cloud Infrastructure"      36000  9000   "Staging environment running"

Write-Host "  17 cost rows created" -ForegroundColor Green

# ── Step 10: Tasks ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Creating tasks..."

function Add-Task {
    param($projId, $title, $status, $priority, $assigneeMember)
    # TaskStatus enum: todo, in_progress, completed (not "done")
    $mappedStatus = if ($status -eq "done") { "completed" } else { $status }
    $body = @{
        title      = $title
        status     = $mappedStatus
        priority   = $priority
        project_id = $projId
    }
    # assignee_id is workspace_members.id (the member row id, not user_id)
    if ($assigneeMember) { $body.assignee_id = $assigneeMember.id }
    Invoke-Post "$base/tasks" $body | Out-Null
}

Add-Task $P1 "Book structural engineer for load assessment"     "done"        "high"     $bob
Add-Task $P1 "Procure raised-floor server room components"       "in_progress" "high"     $carol
Add-Task $P1 "Design internal wayfinding signage"                "todo"        "medium"   $eva
Add-Task $P1 "Staff survey on desk preference and accessibility" "done"        "medium"   $alice
Add-Task $P1 "Coordinate with building management for COI"       "todo"        "low"      $david

Add-Task $P2 "Map legacy chart of accounts to SAP GL"            "done"        "critical" $carol
Add-Task $P2 "Configure payroll integration module"              "in_progress" "high"     $bob
Add-Task $P2 "Develop custom PO approval workflow"               "in_progress" "high"     $david
Add-Task $P2 "Write end-user training materials EN and FR"       "todo"        "medium"   $eva
Add-Task $P2 "Set up disaster recovery for ERP database"         "todo"        "critical" $carol

Add-Task $P3 "Conduct 10 moderated usability sessions"           "in_progress" "high"     $eva
Add-Task $P3 "Implement WCAG 2.2 AA compliance"                  "todo"        "high"     $bob
Add-Task $P3 "Integrate Stripe for invoice payments"             "todo"        "medium"   $david
Add-Task $P3 "Build customer notification email templates"       "todo"        "low"      $alice
Add-Task $P3 "API rate limiting and abuse prevention"            "todo"        "high"     $carol

Write-Host "  15 tasks created" -ForegroundColor Green

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=============================" -ForegroundColor Cyan
Write-Host "  SEED COMPLETE" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host "  Workspace  : OPPM Demo"
Write-Host "  Projects   : 3"
Write-Host "  Members    : 5 team members + owner"
Write-Host "  Objectives : 21"
Write-Host "  Timeline   : 30 entries"
Write-Host "  Costs      : 17 rows"
Write-Host "  Tasks      : 15"
Write-Host ""
Write-Host "  Owner   : cheongchoonvai@gmail.com / 12345678"
Write-Host "  Members : alice/bob/carol/david/eva @oppm.demo  /  Demo@12345"
Write-Host ""
