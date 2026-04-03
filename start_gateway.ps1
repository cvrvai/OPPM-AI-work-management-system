$env:PYTHONPATH = 'c:\Users\cheon\work\OPPM AI work management system'
$env:CORE_URLS = 'http://localhost:8000'
$env:AI_URLS = 'http://localhost:8001'
$env:GIT_URLS = 'http://localhost:8002'
$env:MCP_URLS = 'http://localhost:8003'
Set-Location 'c:\Users\cheon\work\OPPM AI work management system\services\gateway'
Get-Content 'c:\Users\cheon\work\OPPM AI work management system\services\core\.env' | ForEach-Object { if ($_ -match '^([^#=][^=]*)=(.*)$') { [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process') } }
uvicorn main:app --port 8080
