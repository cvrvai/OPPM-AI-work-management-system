param(
    [switch]$Tunnel,
    [switch]$Docker
)

& (Join-Path $PSScriptRoot "deploy\scripts\start-all.ps1") @PSBoundParameters

