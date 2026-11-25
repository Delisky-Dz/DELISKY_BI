param([switch]$Public)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Project = Split-Path $PSScriptRoot -Parent
$Git = Join-Path $env:ProgramFiles 'Git\cmd\git.exe'

function Get-HttpResult {
    param([uri]$Uri, [switch]$Origin)
    $request = [Net.HttpWebRequest]::Create($Uri)
    $request.Method = 'HEAD'
    $request.AllowAutoRedirect = $false
    $request.Timeout = 8000
    if ($Origin) {
        $request.Proxy = $null
        $request.Host = 'app.delisky-dz.com'
        $request.Headers['X-Forwarded-Proto'] = 'https'
    }
    try { $response = $request.GetResponse() }
    catch [Net.WebException] {
        $response = $_.Exception.Response
        if (-not $response) { return 'UNAVAILABLE' }
    }
    try {
        $code = [int]$response.StatusCode
        if ($code -eq 302 -and $response.Headers['Location'] -ceq '/login/') { return 'PASS' }
        return "FAIL (HTTP $code, expected 302 to /login/)"
    }
    finally { $response.Dispose() }
}

function Get-GitValue {
    param([string[]]$Arguments)
    $result = & $Git --no-optional-locks -C $Project @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Git inspection failed' }
    return ($result -join [Environment]::NewLine).Trim()
}

$gitState = 'FAIL'
try {
    if (-not (Test-Path -LiteralPath $Git)) { $Git = (Get-Command git.exe).Source }
    $branch = Get-GitValue @('branch', '--show-current')
    $head = Get-GitValue @('rev-parse', 'HEAD')
    $originMain = Get-GitValue @('rev-parse', 'refs/remotes/origin/main')
    $changes = Get-GitValue @('status', '--porcelain')
    Write-Host "BRANCH=$branch HEAD=$head ORIGIN_MAIN=$originMain"
    if ($branch -eq 'main' -and $head -eq $originMain -and -not $changes) { $gitState = 'PASS' }
}
catch { Write-Host 'GIT_INSPECTION=UNAVAILABLE' }
Write-Host "GIT_STATE=$gitState"

$listener = 'FAIL'
try {
    $endpoints = [Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    $onPort = @($endpoints | Where-Object { $_.Port -eq 8080 })
    if ($onPort.Count -eq 1 -and $onPort[0].Address.ToString() -eq '127.0.0.1') { $listener = 'PASS' }
    foreach ($ep in $onPort) { Write-Host "LISTEN=$ep" }
    if ($onPort.Count) {
        try {
            Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction Stop | ForEach-Object {
                Write-Host "LISTENER_PID=$($_.OwningProcess)"
                Write-Host "PROCESS=$((Get-Process -Id $_.OwningProcess -ErrorAction Stop).ProcessName)"
            }
        }
        catch { Write-Host 'LISTENER_OWNER=UNAVAILABLE' }
    }
}
catch { $listener = 'UNAVAILABLE' }
Write-Host "WAITRESS_LISTENER=$listener"
$local = Get-HttpResult 'http://127.0.0.1:8080/' -Origin
Write-Host "LOCAL_HTTP=$local"
$external = if ($Public) { Get-HttpResult 'https://app.delisky-dz.com/' } else { 'SKIPPED' }
Write-Host "PUBLIC_HTTP=$external"
if ($gitState -ne 'PASS' -or $listener -ne 'PASS' -or $local -ne 'PASS') { exit 1 }
if ($Public -and $external -ne 'PASS') { exit 2 }
exit 0
