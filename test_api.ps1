$BASE = "http://localhost:8080/api"
$pass = 0; $fail = 0
try {
    Invoke-WebRequest "$BASE/auth/signup" -Method POST -ContentType "application/json" -Body '{"email":"apitest@oppm.dev","password":"TestPass123!","full_name":"API Tester"}' -UseBasicParsing -EA Stop | Out-Null
} catch {}
$login = (Invoke-WebRequest "$BASE/auth/login" -Method POST -ContentType "application/json" -Body '{"email":"apitest@oppm.dev","password":"TestPass123!"}' -UseBasicParsing).Content | ConvertFrom-Json
$TOKEN = $login.access_token
$REFRESH = $login.refresh_token
$H = @{Authorization="Bearer $TOKEN"}
Write-Host "[PASS] POST /auth/login  user=$($login.user.email)"; $pass++

function T($label, $method, $path, $bodyObj=$null) {
    try {
        $a = @{Uri="$BASE$path";Method=$method;Headers=$H;UseBasicParsing=$true;ContentType="application/json";ErrorAction="Stop"}
        if ($bodyObj) { $a.Body = ($bodyObj|ConvertTo-Json -Compress -Depth 10) }
        $r = Invoke-WebRequest @a
        Write-Host "[PASS] $method $path ($($r.StatusCode))"
        $script:pass++
        return ($r.Content | ConvertFrom-Json -EA SilentlyContinue)
    } catch {
        $c = $_.Exception.Response.StatusCode.value__; if (-not $c){$c="?"}
        $d = ""; try{$d=($_.ErrorDetails.Message|ConvertFrom-Json).detail}catch{}
        Write-Host "[FAIL] $method $path ($c) $d"
        $script:fail++
        return $null
    }
}

# AI_T: like T but 400/502 (no LLM available) counts as SKIP, not FAIL
function AI_T($label, $method, $path, $bodyObj=$null) {
    try {
        $a = @{Uri="$BASE$path";Method=$method;Headers=$H;UseBasicParsing=$true;ContentType="application/json";ErrorAction="Stop"}
        if ($bodyObj) { $a.Body = ($bodyObj|ConvertTo-Json -Compress -Depth 10) }
        $r = Invoke-WebRequest @a
        Write-Host "[PASS] $method $path ($($r.StatusCode))"
        $script:pass++
        return ($r.Content | ConvertFrom-Json -EA SilentlyContinue)
    } catch {
        $c = $_.Exception.Response.StatusCode.value__; if (-not $c){$c="?"}
        $d = ""; try{$d=($_.ErrorDetails.Message|ConvertFrom-Json).detail}catch{}
        if ($c -eq 400 -or $c -eq 502) {
            Write-Host "[SKIP] $method $path ($c) $d  (requires active LLM)"
        } else {
            Write-Host "[FAIL] $method $path ($c) $d"
            $script:fail++
        }
        return $null
    }
}

Write-Host ""; Write-Host "--- CORE: AUTH ---"
$me = T "me" GET "/auth/me"; $USER_ID = $me.id
$rf = T "refresh" POST "/auth/refresh" @{refresh_token=$REFRESH}
if ($rf) { $TOKEN=$rf.access_token; $H=@{Authorization="Bearer $TOKEN"} }
T "patch profile" PATCH "/auth/profile" @{full_name="API Tester"} | Out-Null

Write-Host ""; Write-Host "--- CORE: WORKSPACES ---"
T "list workspaces" GET "/v1/workspaces" | Out-Null
$slug = "apitest-$(Get-Random -Max 99999)"
$nws = T "create workspace" POST "/v1/workspaces" @{name="API Test WS";slug=$slug;description="Test"}
$WS = $nws.id; Write-Host "  WS=$WS"
T "get workspace" GET "/v1/workspaces/$WS" | Out-Null
T "update workspace" PUT "/v1/workspaces/$WS" @{name="API Test WS 2";description="Updated"} | Out-Null
T "list members" GET "/v1/workspaces/$WS/members" | Out-Null
T "send invite" POST "/v1/workspaces/$WS/invites" @{email="invite@oppm.dev";role="member"} | Out-Null
T "list invites" GET "/v1/workspaces/$WS/invites" | Out-Null
T "email lookup" GET "/v1/workspaces/$WS/members/lookup?email=apitest%40oppm.dev" | Out-Null
T "update display name" PATCH "/v1/workspaces/$WS/members/me/display-name" @{display_name="API Tester"} | Out-Null

Write-Host ""; Write-Host "--- CORE: DASHBOARD ---"
T "dashboard stats" GET "/v1/workspaces/$WS/dashboard/stats" | Out-Null

Write-Host ""; Write-Host "--- CORE: PROJECTS ---"
T "list projects" GET "/v1/workspaces/$WS/projects" | Out-Null
$np = T "create project" POST "/v1/workspaces/$WS/projects" @{title="Test Project";description="API test";status="planning";priority="medium"}
$PROJID = $np.id; Write-Host "  PROJECT=$PROJID"
T "get project" GET "/v1/workspaces/$WS/projects/$PROJID" | Out-Null
T "update project" PUT "/v1/workspaces/$WS/projects/$PROJID" @{title="Test Project 2";status="in_progress"} | Out-Null
T "project members" GET "/v1/workspaces/$WS/projects/$PROJID/members" | Out-Null

Write-Host ""; Write-Host "--- CORE: TASKS ---"
T "list tasks ws" GET "/v1/workspaces/$WS/tasks" | Out-Null
T "list tasks project" GET "/v1/workspaces/$WS/tasks?project_id=$PROJID" | Out-Null
$nt = T "create task" POST "/v1/workspaces/$WS/tasks" @{project_id=$PROJID;title="Test Task";priority="high";status="todo"}
$TID = $nt.id; Write-Host "  TASK=$TID"
T "get task" GET "/v1/workspaces/$WS/tasks/$TID" | Out-Null
T "update task" PUT "/v1/workspaces/$WS/tasks/$TID" @{status="in_progress";progress=50} | Out-Null

Write-Host ""; Write-Host "--- CORE: OPPM ---"
$no = T "create objective" POST "/v1/workspaces/$WS/projects/$PROJID/oppm/objectives" @{title="Q1 Goal";sort_order=1}
$OID = $no.id; Write-Host "  OBJ=$OID"
T "list objectives" GET "/v1/workspaces/$WS/projects/$PROJID/oppm/objectives" | Out-Null
T "update objective" PUT "/v1/workspaces/$WS/oppm/objectives/$OID" @{title="Q1 Goal Updated"} | Out-Null
T "get timeline" GET "/v1/workspaces/$WS/projects/$PROJID/oppm/timeline" | Out-Null
T "update timeline" PUT "/v1/workspaces/$WS/projects/$PROJID/oppm/timeline" @{objective_id=$OID;week_start="2026-04-07";status="in_progress"} | Out-Null
T "get costs" GET "/v1/workspaces/$WS/projects/$PROJID/oppm/costs" | Out-Null
$nc = T "create cost" POST "/v1/workspaces/$WS/projects/$PROJID/oppm/costs" @{category="Labor";planned_amount=10000;actual_amount=8500}
Write-Host "  COST=$($nc.id)"

Write-Host ""; Write-Host "--- CORE: NOTIFICATIONS ---"
T "list notifications" GET "/v1/notifications" | Out-Null
T "unread count" GET "/v1/notifications/unread-count" | Out-Null
T "mark all read" PUT "/v1/notifications/read-all" | Out-Null

Write-Host ""; Write-Host "--- AI: MODELS ---"
# Schema: name, provider, model_id (NOT model_name), endpoint_url (optional), is_active
$nam = T "create ai model" POST "/v1/workspaces/$WS/ai/models" @{name="Test Ollama";provider="ollama";model_id="llama3.2:3b";endpoint_url="http://localhost:11434";is_active=$true}
$AMID = $nam.id; Write-Host "  AI_MODEL=$AMID"
T "list ai models" GET "/v1/workspaces/$WS/ai/models" | Out-Null
if ($AMID) { T "toggle model" PUT "/v1/workspaces/$WS/ai/models/$AMID/toggle" | Out-Null }

Write-Host ""; Write-Host "--- AI: CHAT ---"
# Schema: messages (array of {role, content}), model_id (optional)
AI_T "workspace chat" POST "/v1/workspaces/$WS/ai/chat" @{messages=@(@{role="user";content="What projects are in progress?"})} | Out-Null
if ($PROJID) {
    AI_T "project chat" POST "/v1/workspaces/$WS/projects/$PROJID/ai/chat" @{messages=@(@{role="user";content="Summarize this project"})} | Out-Null
    AI_T "weekly summary" GET "/v1/workspaces/$WS/projects/$PROJID/ai/weekly-summary" | Out-Null
    AI_T "suggest plan" POST "/v1/workspaces/$WS/projects/$PROJID/ai/suggest-plan" @{description="A building construction project for a 5-story office tower"} | Out-Null
}

Write-Host ""; Write-Host "--- AI: RAG ---"
# Schema: query (string), project_id (optional), top_k (optional)
T "rag query" POST "/v1/workspaces/$WS/rag/query" @{query="What are the project objectives?";top_k=5} | Out-Null

Write-Host ""; Write-Host "--- MCP: TOOLS ---"
T "list tools" GET "/v1/workspaces/$WS/mcp/tools" | Out-Null
# Schema: tool (string), params (dict)
T "call tool" POST "/v1/workspaces/$WS/mcp/call" @{tool="list_projects";params=@{workspace_id=$WS}} | Out-Null

Write-Host ""; Write-Host "--- GIT: ACCOUNTS (READ-ONLY) ---"
# Skipping git write operations (webhook setup requires real GitHub tokens)
T "list github accounts" GET "/v1/workspaces/$WS/github-accounts" | Out-Null
T "list repos" GET "/v1/workspaces/$WS/git/repos" | Out-Null
T "list commits" GET "/v1/workspaces/$WS/commits" | Out-Null
T "recent analyses" GET "/v1/workspaces/$WS/git/recent-analyses" | Out-Null
Write-Host "  [SKIPPED] git write operations (require real GitHub credentials)"

Write-Host ""; Write-Host "--- CLEANUP ---"
T "delete task" DELETE "/v1/workspaces/$WS/tasks/$TID" | Out-Null
T "delete objective" DELETE "/v1/workspaces/$WS/oppm/objectives/$OID" | Out-Null
T "delete project" DELETE "/v1/workspaces/$WS/projects/$PROJID" | Out-Null
T "delete workspace" DELETE "/v1/workspaces/$WS" | Out-Null

Write-Host ""
Write-Host "========================================="
Write-Host "PASSED: $pass   FAILED: $fail   TOTAL: $($pass+$fail)"
Write-Host "========================================="
