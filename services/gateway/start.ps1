$env:PYTHONPATH = (Resolve-Path "$PSScriptRoot/../..").Path
$envFile = if (Test-Path "$PSScriptRoot/.env") { "$PSScriptRoot/.env" } else { "$PSScriptRoot/../.env" }
Get-Content $envFile | ForEach-Object {
  if ($_ -match '^([^#=][^=]*)=(.*)$') {
    [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
  }
}
Set-Location $PSScriptRoot
uvicorn main:app --reload --host 127.0.0.1 --port 8080
