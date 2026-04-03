#!/usr/bin/env pwsh
# ============================================================
# OPPM AI – Demo Seed Script
# Creates 5 industry accounts, workspaces, and real OPPM data
# across non-software domains.
#
# Usage:
#   cd "OPPM AI work management system"
#   .\seed_demo.ps1
#
# Prerequisites: backend services running on http://localhost:8080
# ============================================================

$BASE       = "http://localhost:8080/api"
$PASS       = "Demo@12345"
$ADMIN_EMAIL = "apitest@oppm.dev"
$ADMIN_PASS  = "TestPass123!"

$PASS_ALL = 0
$SKIP_ALL = 0
$FAIL_ALL = 0

# ── Helpers ────────────────────────────────────────────────────────────────

function Log-Step { param([string]$msg) Write-Host "`n  $msg" -ForegroundColor Cyan }

function T {
  param([string]$label, [scriptblock]$block)
  try {
    $result = & $block
    $sc = if ($result -is [hashtable]) { $result.StatusCode } else { 200 }
    $script:PASS_ALL++
    Write-Host "  [OK]    $label" -ForegroundColor Green
    return $result
  } catch {
    $body = $_.Exception.Message
    if ($body -match '"detail"') {
      $detail = ($body | ConvertFrom-Json -ErrorAction SilentlyContinue).detail
      if ($detail -match "already exists|already registered|duplicate") {
        $script:SKIP_ALL++
        Write-Host "  [SKIP]  $label (already exists)" -ForegroundColor Yellow
        return $null
      }
    }
    $script:FAIL_ALL++
    Write-Host "  [FAIL]  $label  →  $body" -ForegroundColor Red
    return $null
  }
}

function ApiPost {
  param([string]$path, [hashtable]$body, [string]$token = "")
  $headers = @{ "Content-Type" = "application/json" }
  if ($token) { $headers["Authorization"] = "Bearer $token" }
  $json = $body | ConvertTo-Json -Depth 10
  $resp = Invoke-RestMethod -Uri "$BASE$path" -Method Post -Headers $headers -Body $json -ErrorAction Stop
  return $resp
}

function ApiGet {
  param([string]$path, [string]$token)
  $headers = @{ "Authorization" = "Bearer $token" }
  return Invoke-RestMethod -Uri "$BASE$path" -Method Get -Headers $headers -ErrorAction Stop
}

function ApiPut {
  param([string]$path, [hashtable]$body, [string]$token)
  $headers = @{ "Content-Type" = "application/json"; "Authorization" = "Bearer $token" }
  $json = $body | ConvertTo-Json -Depth 10
  return Invoke-RestMethod -Uri "$BASE$path" -Method Put -Headers $headers -Body $json -ErrorAction Stop
}

function Register-And-Login {
  param([string]$email, [string]$displayName)
  # Try register (may already exist)
  try {
    ApiPost "/v1/auth/register" @{ email = $email; password = $PASS; display_name = $displayName } | Out-Null
  } catch { <# ignore duplicate #> }
  # Login
  $resp = ApiPost "/v1/auth/login" @{ email = $email; password = $PASS }
  return $resp.access_token
}

function Create-Workspace {
  param([string]$token, [string]$name, [string]$desc)
  try {
    $ws = ApiPost "/v1/workspaces" @{ name = $name; description = $desc } $token
    return $ws
  } catch {
    # Fetch existing workspaces
    $list = ApiGet "/v1/workspaces" $token
    foreach ($w in $list.items) {
      if ($w.name -eq $name) { return $w }
    }
    return $null
  }
}

function Create-Project {
  param([string]$token, [string]$wsId, [hashtable]$proj)
  try {
    return ApiPost "/v1/workspaces/$wsId/projects" $proj $token
  } catch {
    $list = ApiGet "/v1/workspaces/$wsId/projects" $token
    foreach ($p in $list.items) {
      if ($p.title -eq $proj.title) { return $p }
    }
    return $null
  }
}

function Seed-Objectives {
  param([string]$token, [string]$wsPath, [string]$projId, [array]$titles)
  $objIds = @()
  $order = 1
  foreach ($title in $titles) {
    try {
      $obj = ApiPost "$wsPath/projects/$projId/oppm/objectives" @{
        title = $title; sort_order = $order
      } $token
      $objIds += $obj.id
    } catch {
      $list = ApiGet "$wsPath/projects/$projId/oppm/objectives" $token
      foreach ($o in $list) {
        if ($o.title -eq $title) { $objIds += $o.id; break }
      }
    }
    $order++
  }
  return $objIds
}

function Seed-Timeline {
  param([string]$token, [string]$wsPath, [string]$projId,
        [string]$objId, [string]$weekStart, [string]$status)
  try {
    ApiPut "$wsPath/projects/$projId/oppm/timeline" @{
      objective_id = $objId
      week_start   = $weekStart
      status       = $status
    } $token | Out-Null
  } catch { <# ignore #> }
}

function Seed-Cost {
  param([string]$token, [string]$wsPath, [string]$projId,
        [string]$category, [double]$planned, [double]$actual, [string]$notes)
  try {
    ApiPost "$wsPath/projects/$projId/oppm/costs" @{
      category       = $category
      planned_amount = $planned
      actual_amount  = $actual
      notes          = $notes
      project_id     = $projId
    } $token | Out-Null
  } catch { <# ignore #> }
}

# ── Start ──────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "  OPPM AI — Demo Seed Script" -ForegroundColor Magenta
Write-Host "  5 industries · 5 workspaces · 10 projects" -ForegroundColor Magenta
Write-Host "======================================================" -ForegroundColor Magenta

# ── Health check ───────────────────────────────────────────────────────────

Log-Step "Checking gateway health..."
try {
  $h = Invoke-RestMethod -Uri "$BASE/../health" -Method Get -ErrorAction Stop
  Write-Host "  Gateway: $($h.status ?? 'ok')" -ForegroundColor Green
} catch {
  Write-Host "  [WARN] Gateway not responding — services may still work" -ForegroundColor Yellow
}

# ╔═════════════════════════════════════════════════════════════╗
# ║  INDUSTRY 1 — Architecture & Construction                  ║
# ╚═════════════════════════════════════════════════════════════╝

Log-Step "INDUSTRY 1: Architecture & Construction"

$arch_token = T "Register/Login arch@demo.oppm" {
  Register-And-Login "arch@demo.oppm" "Alex Chen · Lakeview Architecture"
}

if ($arch_token) {
  $arch_ws = T "Create workspace: Lakeview Architecture Studio" {
    Create-Workspace $arch_token "Lakeview Architecture Studio" "A leading architecture firm delivering landmark commercial and heritage projects."
  }
}

if ($arch_token -and $arch_ws) {
  $arch_wid = $arch_ws.id
  $arch_wsp = "/v1/workspaces/$arch_wid"

  # Project 1 — Riverside Tower
  $p1 = T "Create project: Riverside Tower Development" {
    Create-Project $arch_token $arch_wid @{
      title       = "Riverside Tower Development"
      description = "50-floor mixed-use tower on the city waterfront. 85,000 sqm GFA. Targeting LEED Platinum certification."
      status      = "in_progress"
      priority    = "critical"
      start_date  = "2024-01-15"
      deadline    = "2026-06-30"
      progress    = 38
    }
  }

  if ($p1) {
    $pid1 = $p1.id
    $objs1 = Seed-Objectives $arch_token $arch_wsp $pid1 @(
      "Site Preparation & Demolition",
      "Piling & Foundation Works",
      "Steel Structural Framework",
      "Facade & Curtain Wall Glazing",
      "MEP Systems Installation",
      "Interior Fit-Out & FFE"
    )

    $week1 = "2024-02-05"; $week2 = "2024-02-12"; $week3 = "2024-02-19"; $week4 = "2024-02-26"
    $week5 = "2024-03-04"; $week6 = "2024-03-11"; $week7 = "2024-03-18"; $week8 = "2024-03-25"

    T "Seed timeline: Riverside Tower" {
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[0] $week1 "completed"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[0] $week2 "completed"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[0] $week3 "completed"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[0] $week4 "completed"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[1] $week3 "completed"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[1] $week4 "completed"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[1] $week5 "in_progress"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[1] $week6 "in_progress"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[2] $week5 "planned"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[2] $week6 "planned"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[2] $week7 "planned"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[2] $week8 "planned"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[3] $week7 "planned"
      Seed-Timeline $arch_token $arch_wsp $pid1 $objs1[3] $week8 "planned"
      $true
    }

    T "Seed costs: Riverside Tower" {
      Seed-Cost $arch_token $arch_wsp $pid1 "Site Preparation"    4200000  4350000  "Slight over-run due to rock excavation"
      Seed-Cost $arch_token $arch_wsp $pid1 "Structural Works"   28000000 26800000  "Under budget — steel price index fell Q1"
      Seed-Cost $arch_token $arch_wsp $pid1 "Facade & Glazing"   12500000        0  "Procurement in progress"
      Seed-Cost $arch_token $arch_wsp $pid1 "MEP Systems"        18000000        0  "Design stage"
      Seed-Cost $arch_token $arch_wsp $pid1 "Interior Fit-Out"   22000000        0  "TBD — tenant mix not finalised"
      Seed-Cost $arch_token $arch_wsp $pid1 "Professional Fees"   6800000  5100000  "Architecture, engineering, surveying"
      $true
    }
  }

  # Project 2 — Heritage Museum Renovation
  $p2 = T "Create project: Heritage Museum Renovation" {
    Create-Project $arch_token $arch_wid @{
      title       = "Grand Heritage Museum Renovation"
      description = "Conservation and adaptive reuse of a Grade-I listed Victorian building. Annex addition of 4,200 sqm contemporary gallery wing."
      status      = "in_progress"
      priority    = "high"
      start_date  = "2024-03-01"
      deadline    = "2025-09-30"
      progress    = 22
    }
  }

  if ($p2) {
    $pid2 = $p2.id
    $objs2 = Seed-Objectives $arch_token $arch_wsp $pid2 @(
      "Conservation Survey & Planning Consent",
      "Structural Stabilisation Works",
      "Heritage Masonry Restoration",
      "Contemporary Annex Construction",
      "Gallery Systems & Lighting",
      "Public Opening & Commissioning"
    )

    T "Seed timeline: Heritage Museum" {
      Seed-Timeline $arch_token $arch_wsp $pid2 $objs2[0] "2024-03-04" "completed"
      Seed-Timeline $arch_token $arch_wsp $pid2 $objs2[0] "2024-03-11" "completed"
      Seed-Timeline $arch_token $arch_wsp $pid2 $objs2[1] "2024-03-18" "in_progress"
      Seed-Timeline $arch_token $arch_wsp $pid2 $objs2[1] "2024-03-25" "in_progress"
      Seed-Timeline $arch_token $arch_wsp $pid2 $objs2[2] "2024-04-01" "planned"
      Seed-Timeline $arch_token $arch_wsp $pid2 $objs2[2] "2024-04-08" "planned"
      $true
    }

    T "Seed costs: Heritage Museum" {
      Seed-Cost $arch_token $arch_wsp $pid2 "Conservation Survey"     380000   395000  "Slightly over — additional archival research"
      Seed-Cost $arch_token $arch_wsp $pid2 "Structural Works"       2100000  1850000  "On track"
      Seed-Cost $arch_token $arch_wsp $pid2 "Masonry Restoration"    3400000        0  "Starting Q2 2024"
      Seed-Cost $arch_token $arch_wsp $pid2 "Annex Construction"     8200000        0  "Scheduled Q3 2024"
      $true
    }
  }
}

# ╔═════════════════════════════════════════════════════════════╗
# ║  INDUSTRY 2 — Finance & Banking                            ║
# ╚═════════════════════════════════════════════════════════════╝

Log-Step "INDUSTRY 2: Finance & Banking"

$fin_token = T "Register/Login finance@demo.oppm" {
  Register-And-Login "finance@demo.oppm" "Sarah Kim · Meridian Capital Management"
}

if ($fin_token) {
  $fin_ws = T "Create workspace: Meridian Capital Management" {
    Create-Workspace $fin_token "Meridian Capital Management" "Mid-market investment management firm. AUM \$4.2B. Offices in New York, London, Singapore."
  }
}

if ($fin_token -and $fin_ws) {
  $fin_wid = $fin_ws.id
  $fin_wsp = "/v1/workspaces/$fin_wid"

  # Project 1 — ISO 27001 Security Audit
  $p3 = T "Create project: ISO 27001 Information Security Audit" {
    Create-Project $fin_token $fin_wid @{
      title       = "ISO 27001 Information Security Certification"
      description = "Achieve ISO 27001:2022 certification to meet regulatory requirements and institutional client mandates. Baseline audit identified 47 non-conformances."
      status      = "in_progress"
      priority    = "critical"
      start_date  = "2024-02-01"
      deadline    = "2024-12-15"
      progress    = 45
    }
  }

  if ($p3) {
    $pid3 = $p3.id
    $objs3 = Seed-Objectives $fin_token $fin_wsp $pid3 @(
      "Gap Assessment & Risk Register",
      "Policy & Procedure Documentation",
      "Technical Controls Implementation",
      "Staff Awareness Training Programme",
      "Stage 1 & Stage 2 External Audit",
      "Certification & Continuous Improvement"
    )

    T "Seed timeline: ISO 27001" {
      foreach ($w in @("2024-02-05","2024-02-12","2024-02-19","2024-02-26")) {
        Seed-Timeline $fin_token $fin_wsp $pid3 $objs3[0] $w "completed"
      }
      foreach ($w in @("2024-03-04","2024-03-11","2024-03-18","2024-03-25")) {
        Seed-Timeline $fin_token $fin_wsp $pid3 $objs3[1] $w "completed"
      }
      foreach ($w in @("2024-04-01","2024-04-08","2024-04-15","2024-04-22")) {
        Seed-Timeline $fin_token $fin_wsp $pid3 $objs3[2] $w "in_progress"
      }
      foreach ($w in @("2024-04-29","2024-05-06","2024-05-13","2024-05-20")) {
        Seed-Timeline $fin_token $fin_wsp $pid3 $objs3[3] $w "planned"
      }
      foreach ($w in @("2024-09-02","2024-09-09","2024-09-16","2024-09-23")) {
        Seed-Timeline $fin_token $fin_wsp $pid3 $objs3[4] $w "planned"
      }
      $true
    }

    T "Seed costs: ISO 27001" {
      Seed-Cost $fin_token $fin_wsp $pid3 "External Consultancy"      320000   285000  "Gap assessment complete"
      Seed-Cost $fin_token $fin_wsp $pid3 "Internal Staff Time"       180000   142000  "Policy writing team (FTE allocation)"
      Seed-Cost $fin_token $fin_wsp $pid3 "Technical Tooling"         240000   215000  "SIEM, vulnerability scanner, DLP"
      Seed-Cost $fin_token $fin_wsp $pid3 "Training & Awareness"       85000         0  "e-learning platform — Q2 budget"
      Seed-Cost $fin_token $fin_wsp $pid3 "Certification Body Fees"    38000         0  "BSI audit fees"
      $true
    }
  }

  # Project 2 — Core Banking Migration
  $p4 = T "Create project: Core Banking Platform Migration" {
    Create-Project $fin_token $fin_wid @{
      title       = "Core Banking Platform Migration"
      description = "Migration from legacy Temenos T24 v12 to Temenos Transact (v22). Zero-downtime cutover for 1.4 million accounts. Regulatory parallel-run required for 90 days."
      status      = "planning"
      priority    = "critical"
      start_date  = "2024-05-01"
      deadline    = "2025-11-30"
      progress    = 8
    }
  }

  if ($p4) {
    $pid4 = $p4.id
    $objs4 = Seed-Objectives $fin_token $fin_wsp $pid4 @(
      "Business Requirements & Vendor Sign-Off",
      "Data Architecture & Migration Strategy",
      "System Integration & API Layer",
      "User Acceptance Testing (UAT)",
      "Regulatory Parallel Run (90 days)",
      "Phased Cutover & Hypercare"
    )

    T "Seed timeline: Core Banking Migration" {
      foreach ($w in @("2024-05-06","2024-05-13","2024-05-20","2024-05-27")) {
        Seed-Timeline $fin_token $fin_wsp $pid4 $objs4[0] $w "in_progress"
      }
      $true
    }

    T "Seed costs: Core Banking Migration" {
      Seed-Cost $fin_token $fin_wsp $pid4 "Vendor Licensing"       4200000         0  "Transact perpetual licence + 3yr SaaS"
      Seed-Cost $fin_token $fin_wsp $pid4 "Systems Integrator"     8500000   1200000  "Accenture — discovery phase invoiced"
      Seed-Cost $fin_token $fin_wsp $pid4 "Infrastructure"         2100000         0  "Cloud migration (AWS FSx)"
      Seed-Cost $fin_token $fin_wsp $pid4 "Data Cleansing"          950000    380000  "Legacy record remediation"
      Seed-Cost $fin_token $fin_wsp $pid4 "Testing & UAT"           720000         0  "Internal QA + external test partner"
      Seed-Cost $fin_token $fin_wsp $pid4 "Training"                480000         0  "Nationwide branch staff training"
      $true
    }
  }
}

# ╔═════════════════════════════════════════════════════════════╗
# ║  INDUSTRY 3 — Healthcare                                   ║
# ╚═════════════════════════════════════════════════════════════╝

Log-Step "INDUSTRY 3: Healthcare"

$hlt_token = T "Register/Login health@demo.oppm" {
  Register-And-Login "health@demo.oppm" "Dr. Maria Santos · Metro Health Network"
}

if ($hlt_token) {
  $hlt_ws = T "Create workspace: Metro Health Network" {
    Create-Workspace $hlt_token "Metro Health Network" "Regional healthcare provider operating 6 hospitals, 24 clinics. 12,000 staff. Joint Commission accredited."
  }
}

if ($hlt_token -and $hlt_ws) {
  $hlt_wid = $hlt_ws.id
  $hlt_wsp = "/v1/workspaces/$hlt_wid"

  # Project 1 — New ICU Wing
  $p5 = T "Create project: New 48-Bed ICU Wing Construction" {
    Create-Project $hlt_token $hlt_wid @{
      title       = "New 48-Bed ICU Wing — City Central Hospital"
      description = "Design and construction of a 48-bed Level 3 ICU wing with negative-pressure isolation rooms, integrated CDSS, and centralised monitoring. HTM 03-01 compliant HVAC."
      status      = "in_progress"
      priority    = "critical"
      start_date  = "2023-10-01"
      deadline    = "2025-03-31"
      progress    = 55
    }
  }

  if ($p5) {
    $pid5 = $p5.id
    $objs5 = Seed-Objectives $hlt_token $hlt_wsp $pid5 @(
      "Regulatory Approval & Health Planning",
      "Civil & Structural Works",
      "Medical Equipment Procurement",
      "HVAC & Clean-Room Systems",
      "Clinical IT & Nurse Call Systems",
      "CQC Inspection & Accreditation"
    )

    T "Seed timeline: ICU Wing" {
      foreach ($w in @("2023-10-02","2023-10-09","2023-10-16","2023-10-23")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid5 $objs5[0] $w "completed"
      }
      foreach ($w in @("2023-11-06","2023-11-13","2023-11-20","2023-11-27",
                        "2024-01-08","2024-01-15","2024-01-22","2024-01-29")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid5 $objs5[1] $w "completed"
      }
      foreach ($w in @("2024-02-05","2024-02-12","2024-02-19","2024-02-26")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid5 $objs5[2] $w "completed"
      }
      foreach ($w in @("2024-03-04","2024-03-11","2024-03-18","2024-03-25",
                        "2024-04-01","2024-04-08")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid5 $objs5[3] $w "in_progress"
      }
      foreach ($w in @("2024-04-15","2024-04-22","2024-04-29")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid5 $objs5[4] $w "planned"
      }
      foreach ($w in @("2024-12-02","2024-12-09")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid5 $objs5[5] $w "planned"
      }
      $true
    }

    T "Seed costs: ICU Wing" {
      Seed-Cost $hlt_token $hlt_wsp $pid5 "Civil & Structural"      9800000  9650000  "On budget — ground conditions favourable"
      Seed-Cost $hlt_token $hlt_wsp $pid5 "HVAC & Clean-Room"       4200000  3900000  "HTM 03-01 spec procured"
      Seed-Cost $hlt_token $hlt_wsp $pid5 "Medical Equipment"       6500000  5800000  "Pending 8 ventilators — supply chain delay"
      Seed-Cost $hlt_token $hlt_wsp $pid5 "Clinical IT"             1800000   420000  "EPR integration in progress"
      Seed-Cost $hlt_token $hlt_wsp $pid5 "Furniture & Fit-Out"     1200000         0  "Deferred to Q3 2024"
      Seed-Cost $hlt_token $hlt_wsp $pid5 "Project Management"       980000   850000  "Internal PMO + external QS"
      $true
    }
  }

  # Project 2 — EHR Migration
  $p6 = T "Create project: Electronic Health Record System Migration" {
    Create-Project $hlt_token $hlt_wid @{
      title       = "EHR System Migration — Epic Go-Live"
      description = "Replace 3 legacy EPR systems (iPM, Lorenzo, EMIS) with Epic across all 6 hospitals. 1.2 million patient records. 8,400 clinical users. NHS DSPT compliant."
      status      = "in_progress"
      priority    = "high"
      start_date  = "2024-01-01"
      deadline    = "2025-06-30"
      progress    = 30
    }
  }

  if ($p6) {
    $pid6 = $p6.id
    $objs6 = Seed-Objectives $hlt_token $hlt_wsp $pid6 @(
      "Programme Governance & Epic Configuration",
      "Data Migration & Patient Record Validation",
      "Interface Build (Lab, Pharmacy, Imaging)",
      "End-User Training (8,400 staff)",
      "Pilot Go-Live (Hospital 1)",
      "Full Network Rollout (Hospitals 2-6)"
    )

    T "Seed timeline: EHR Migration" {
      foreach ($w in @("2024-01-08","2024-01-15","2024-01-22","2024-01-29",
                        "2024-02-05","2024-02-12")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid6 $objs6[0] $w "completed"
      }
      foreach ($w in @("2024-02-19","2024-02-26","2024-03-04","2024-03-11")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid6 $objs6[1] $w "in_progress"
      }
      foreach ($w in @("2024-03-18","2024-03-25","2024-04-01")) {
        Seed-Timeline $hlt_token $hlt_wsp $pid6 $objs6[2] $w "planned"
      }
      $true
    }

    T "Seed costs: EHR Migration" {
      Seed-Cost $hlt_token $hlt_wsp $pid6 "Epic Licensing"         18500000  3700000  "Year 1 of 5-yr contract"
      Seed-Cost $hlt_token $hlt_wsp $pid6 "Implementation Partner" 12000000  4800000  "Accenture Health — 40% milestone invoiced"
      Seed-Cost $hlt_token $hlt_wsp $pid6 "Infrastructure"          5200000  1800000  "Azure Health Data Services"
      Seed-Cost $hlt_token $hlt_wsp $pid6 "Training & Change Mgmt"  2800000   350000  "Super-user programme launched"
      Seed-Cost $hlt_token $hlt_wsp $pid6 "Data Migration"          1400000   620000  "3 legacy systems mapping"
      $true
    }
  }
}

# ╔═════════════════════════════════════════════════════════════╗
# ║  INDUSTRY 4 — Manufacturing & Industrial                   ║
# ╚═════════════════════════════════════════════════════════════╝

Log-Step "INDUSTRY 4: Manufacturing & Industrial"

$mfg_token = T "Register/Login mfg@demo.oppm" {
  Register-And-Login "mfg@demo.oppm" "James Park · Apex Industrial Solutions"
}

if ($mfg_token) {
  $mfg_ws = T "Create workspace: Apex Industrial Solutions" {
    Create-Workspace $mfg_token "Apex Industrial Solutions" "Precision manufacturer of aerospace components. AS9100D certified. 2,800 employees across 4 plants."
  }
}

if ($mfg_token -and $mfg_ws) {
  $mfg_wid = $mfg_ws.id
  $mfg_wsp = "/v1/workspaces/$mfg_wid"

  # Project 1 — Production Line Automation
  $p7 = T "Create project: Plant 3 Production Line Automation" {
    Create-Project $mfg_token $mfg_wid @{
      title       = "Plant 3 — Robotic Production Line Automation"
      description = "Install 14 Fanuc robotic welding cells, automated guided vehicles (AGVs), and MES integration on the Fuselage Component Line. Target: 40% cycle-time reduction, OEE 85%."
      status      = "in_progress"
      priority    = "high"
      start_date  = "2024-01-08"
      deadline    = "2024-10-31"
      progress    = 42
    }
  }

  if ($p7) {
    $pid7 = $p7.id
    $objs7 = Seed-Objectives $mfg_token $mfg_wsp $pid7 @(
      "Capital Expenditure Approval & Procurement",
      "Civil Works & Factory Preparation",
      "Robot & AGV Installation",
      "MES & Scada Integration",
      "Safety Validation & CE Marking",
      "Operator Training & Production Ramp-Up"
    )

    T "Seed timeline: Production Line Automation" {
      foreach ($w in @("2024-01-08","2024-01-15","2024-01-22","2024-01-29")) {
        Seed-Timeline $mfg_token $mfg_wsp $pid7 $objs7[0] $w "completed"
      }
      foreach ($w in @("2024-02-05","2024-02-12","2024-02-19","2024-02-26")) {
        Seed-Timeline $mfg_token $mfg_wsp $pid7 $objs7[1] $w "completed"
      }
      foreach ($w in @("2024-03-04","2024-03-11","2024-03-18","2024-03-25",
                        "2024-04-01","2024-04-08")) {
        Seed-Timeline $mfg_token $mfg_wsp $pid7 $objs7[2] $w "in_progress"
      }
      foreach ($w in @("2024-04-15","2024-04-22","2024-04-29","2024-05-06")) {
        Seed-Timeline $mfg_token $mfg_wsp $pid7 $objs7[3] $w "planned"
      }
      foreach ($w in @("2024-05-13","2024-05-20","2024-05-27")) {
        Seed-Timeline $mfg_token $mfg_wsp $pid7 $objs7[4] $w "planned"
      }
      foreach ($w in @("2024-06-03","2024-06-10","2024-06-17","2024-06-24")) {
        Seed-Timeline $mfg_token $mfg_wsp $pid7 $objs7[5] $w "planned"
      }
      $true
    }

    T "Seed costs: Production Line Automation" {
      Seed-Cost $mfg_token $mfg_wsp $pid7 "Robotic Welding Cells"   8400000  8400000  "14× Fanuc R-2000iC/165F — fully invoiced"
      Seed-Cost $mfg_token $mfg_wsp $pid7 "AGV Fleet (8 units)"     2100000  2100000  "Jungheinrich EKS 215 — delivered"
      Seed-Cost $mfg_token $mfg_wsp $pid7 "Civil & Electrical"      1800000  1650000  "Concrete reinforcement — under budget"
      Seed-Cost $mfg_token $mfg_wsp $pid7 "MES / Scada Integration"  980000   240000  "SAP ME — implementation ongoing"
      Seed-Cost $mfg_token $mfg_wsp $pid7 "Safety & Guarding"        420000         0  "Risk assessment in progress"
      Seed-Cost $mfg_token $mfg_wsp $pid7 "Training & Ramp-Up"       360000         0  "Scheduled Q3 2024"
      $true
    }
  }

  # Project 2 — ISO 9001 Certification
  $p8 = T "Create project: AS9100D Re-certification Audit" {
    Create-Project $mfg_token $mfg_wid @{
      title       = "AS9100D Re-certification Audit (3-Year Cycle)"
      description = "Tri-annual AS9100D re-certification by Lloyd's Register. Scope: all 4 plants. Previous audit had 3 major and 8 minor non-conformances — all closed. Focus areas: risk management, FOD control, traceability."
      status      = "planning"
      priority    = "critical"
      start_date  = "2024-06-01"
      deadline    = "2024-12-20"
      progress    = 5
    }
  }

  if ($p8) {
    $pid8 = $p8.id
    $objs8 = Seed-Objectives $mfg_token $mfg_wsp $pid8 @(
      "Internal Audit Programme (All 4 Plants)",
      "NCR Close-Out & Corrective Actions",
      "Document Control & Records Review",
      "Management Review Meeting",
      "Stage 1 Desk Audit (Lloyd's Register)",
      "Stage 2 On-Site Certification Audit"
    )

    T "Seed timeline: AS9100D Re-cert" {
      foreach ($w in @("2024-06-03","2024-06-10","2024-06-17","2024-06-24")) {
        Seed-Timeline $mfg_token $mfg_wsp $pid8 $objs8[0] $w "planned"
      }
      $true
    }

    T "Seed costs: AS9100D Re-cert" {
      Seed-Cost $mfg_token $mfg_wsp $pid8 "Internal Audit Resource"  145000         0  "QA team — 3 senior auditors"
      Seed-Cost $mfg_token $mfg_wsp $pid8 "NCR Remediation"           82000         0  "Workshop tooling & process redesign"
      Seed-Cost $mfg_token $mfg_wsp $pid8 "Lloyd's Register Fees"     48000         0  "Stage 1 + Stage 2 + surveillance fee"
      $true
    }
  }
}

# ╔═════════════════════════════════════════════════════════════╗
# ║  INDUSTRY 5 — Higher Education                             ║
# ╚═════════════════════════════════════════════════════════════╝

Log-Step "INDUSTRY 5: Higher Education"

$edu_token = T "Register/Login edu@demo.oppm" {
  Register-And-Login "edu@demo.oppm" "Prof. Lisa Wang · Northgate University"
}

if ($edu_token) {
  $edu_ws = T "Create workspace: Northgate University" {
    Create-Workspace $edu_token "Northgate University" "Research-intensive university. 28,000 students, 4,200 staff. Russell Group member. QS World Ranking #67."
  }
}

if ($edu_token -and $edu_ws) {
  $edu_wid = $edu_ws.id
  $edu_wsp = "/v1/workspaces/$edu_wid"

  # Project 1 — Engineering Faculty Building
  $p9 = T "Create project: New Engineering & Innovation Building" {
    Create-Project $edu_token $edu_wid @{
      title       = "New Engineering & Innovation Building"
      description = "12,400 sqm purpose-built engineering facility with fabrication labs, clean-room, wind tunnel, and 450-seat lecture theatre. BREEAM Excellent target. £42M capital project funded by UKRI and alumni endowment."
      status      = "in_progress"
      priority    = "high"
      start_date  = "2023-09-01"
      deadline    = "2025-09-01"
      progress    = 48
    }
  }

  if ($p9) {
    $pid9 = $p9.id
    $objs9 = Seed-Objectives $edu_token $edu_wsp $pid9 @(
      "Campus Master Plan & Planning Consent",
      "RIBA Stage 4 Technical Design",
      "Groundworks & Structural Frame",
      "Building Envelope & M&E",
      "Lab Equipment & Specialist Fit-Out",
      "AV Systems, IT & Opening Ceremony"
    )

    T "Seed timeline: Engineering Building" {
      foreach ($w in @("2023-09-04","2023-09-11","2023-09-18","2023-09-25",
                        "2023-10-02","2023-10-09")) {
        Seed-Timeline $edu_token $edu_wsp $pid9 $objs9[0] $w "completed"
      }
      foreach ($w in @("2023-10-16","2023-10-23","2023-10-30","2023-11-06",
                        "2023-11-13","2023-11-20")) {
        Seed-Timeline $edu_token $edu_wsp $pid9 $objs9[1] $w "completed"
      }
      foreach ($w in @("2023-11-27","2023-12-04","2024-01-08","2024-01-15",
                        "2024-01-22","2024-01-29","2024-02-05","2024-02-12")) {
        Seed-Timeline $edu_token $edu_wsp $pid9 $objs9[2] $w "completed"
      }
      foreach ($w in @("2024-02-19","2024-02-26","2024-03-04","2024-03-11",
                        "2024-03-18","2024-03-25","2024-04-01","2024-04-08")) {
        Seed-Timeline $edu_token $edu_wsp $pid9 $objs9[3] $w "in_progress"
      }
      foreach ($w in @("2024-07-01","2024-07-08","2024-07-15","2024-07-22")) {
        Seed-Timeline $edu_token $edu_wsp $pid9 $objs9[4] $w "planned"
      }
      foreach ($w in @("2025-08-04","2025-08-11")) {
        Seed-Timeline $edu_token $edu_wsp $pid9 $objs9[5] $w "planned"
      }
      $true
    }

    T "Seed costs: Engineering Building" {
      Seed-Cost $edu_token $edu_wsp $pid9 "Construction Contract"  32000000 18400000  "MC — Mace Group (JCT Design & Build)"
      Seed-Cost $edu_token $edu_wsp $pid9 "Professional Fees"       3800000  3400000  "Architect, structural, M&E engineers"
      Seed-Cost $edu_token $edu_wsp $pid9 "Lab Equipment"           4200000         0  "Procurement Q4 2024"
      Seed-Cost $edu_token $edu_wsp $pid9 "AV & IT Infrastructure"  1200000         0  "University IT — Q1 2025"
      Seed-Cost $edu_token $edu_wsp $pid9 "Furniture & Fit-Out"      800000         0  "Phased with construction"
      $true
    }
  }

  # Project 2 — Online Learning Platform
  $p10 = T "Create project: Digital Learning Platform Launch" {
    Create-Project $edu_token $edu_wid @{
      title       = "Next-Generation Digital Learning Platform"
      description = "Replace Blackboard with Canvas LMS. Integrate Turnitin, Zoom, Panopto, and custom AI-tutoring assistant. 28,000 students, 4,200 staff. WCAG 2.2 AA compliance required. JISC framework procurement."
      status      = "in_progress"
      priority    = "high"
      start_date  = "2024-02-01"
      deadline    = "2025-01-31"
      progress    = 25
    }
  }

  if ($p10) {
    $pid10 = $p10.id
    $objs10 = Seed-Objectives $edu_token $edu_wsp $pid10 @(
      "Procurement & Canvas Contract Sign-Off",
      "Technical Architecture & SSO Integration",
      "Content Migration (3,200 course shells)",
      "Academic & Staff Training Programme",
      "Pilot Semester (3 Faculties — 6,000 students)",
      "University-Wide Go-Live & Legacy Decommission"
    )

    T "Seed timeline: Digital Learning Platform" {
      foreach ($w in @("2024-02-05","2024-02-12","2024-02-19","2024-02-26")) {
        Seed-Timeline $edu_token $edu_wsp $pid10 $objs10[0] $w "completed"
      }
      foreach ($w in @("2024-03-04","2024-03-11","2024-03-18","2024-03-25")) {
        Seed-Timeline $edu_token $edu_wsp $pid10 $objs10[1] $w "in_progress"
      }
      foreach ($w in @("2024-04-01","2024-04-08","2024-04-15","2024-04-22",
                        "2024-04-29","2024-05-06","2024-05-13","2024-05-20")) {
        Seed-Timeline $edu_token $edu_wsp $pid10 $objs10[2] $w "planned"
      }
      $true
    }

    T "Seed costs: Digital Learning Platform" {
      Seed-Cost $edu_token $edu_wsp $pid10 "Canvas LMS Licence"      480000   160000  "Year 1 of 3-yr contract"
      Seed-Cost $edu_token $edu_wsp $pid10 "Implementation Partner"   320000    85000  "Instructure Professional Services"
      Seed-Cost $edu_token $edu_wsp $pid10 "Integration & Dev"        180000    40000  "SSO, MIS feeds, AI tutor API"
      Seed-Cost $edu_token $edu_wsp $pid10 "Content Migration"         95000         0  "3,200 course shells — Q2/Q3 2024"
      Seed-Cost $edu_token $edu_wsp $pid10 "Training"                  60000         0  "Academic development programme"
      $true
    }
  }
}

# ── Summary ────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host "  Seed Complete" -ForegroundColor Magenta
Write-Host "  OK: $PASS_ALL  |  SKIP: $SKIP_ALL  |  FAIL: $FAIL_ALL" -ForegroundColor $(if ($FAIL_ALL -gt 0) { "Red" } elseif ($SKIP_ALL -gt 0) { "Yellow" } else { "Green" })
Write-Host "======================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Demo Accounts Created:" -ForegroundColor Cyan
Write-Host "    arch@demo.oppm      — Lakeview Architecture Studio"
Write-Host "    finance@demo.oppm   — Meridian Capital Management"
Write-Host "    health@demo.oppm    — Metro Health Network"
Write-Host "    mfg@demo.oppm       — Apex Industrial Solutions"
Write-Host "    edu@demo.oppm       — Northgate University"
Write-Host ""
Write-Host "  Password for all demo accounts: $PASS" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Login at: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
