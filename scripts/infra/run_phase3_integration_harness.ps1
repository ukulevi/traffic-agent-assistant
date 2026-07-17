param(
    [string]$PythonPath = "python",
    [int]$HealthTimeoutSeconds = 180,
    [switch]$KeepServices
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$composeFile = Join-Path $root "infra\harness\compose.phase3.yaml"
$dockerCandidates = @()
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) {
    $dockerCandidates += $dockerCommand.Source
}
$dockerCandidates += "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$dockerCandidates = @($dockerCandidates | Where-Object { Test-Path $_ })
if (-not $dockerCandidates) {
    throw "Docker CLI was not found"
}
$docker = $dockerCandidates[0]

function Invoke-Docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code $LASTEXITCODE"
    }
}

function New-EphemeralSecret {
    return ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
}

function New-LoopbackPort {
    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    try {
        $listener.Start()
        return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

$env:STWI_QDRANT_API_KEY = New-EphemeralSecret
$env:STWI_QDRANT_READ_ONLY_API_KEY = New-EphemeralSecret
$env:STWI_TSDB_PASSWORD = New-EphemeralSecret
$env:STWI_READER_PASSWORD = New-EphemeralSecret
$ports = @()
while ($ports.Count -lt 3) {
    $candidate = New-LoopbackPort
    if ($candidate -notin $ports) {
        $ports += $candidate
    }
}
$env:QDRANT_HTTP_PORT = [string]$ports[0]
$env:QDRANT_GRPC_PORT = [string]$ports[1]
$env:TSDB_PORT = [string]$ports[2]
$env:STWI_QDRANT_URL = "http://127.0.0.1:$($env:QDRANT_HTTP_PORT)"
$env:STWI_TSDB_DSN = (
    "postgresql://stwi_reader_user:{0}@127.0.0.1:{1}/stwi" -f
    $env:STWI_READER_PASSWORD,
    $env:TSDB_PORT
)

$compose = @("compose", "-f", $composeFile)
$started = $false
Push-Location $root
try {
    Invoke-Docker @compose "config" "--quiet"
    # The harness is intentionally ephemeral; remove any partial state left by
    # an interrupted previous run before starting a clean integration cycle.
    Invoke-Docker @compose "down" "-v" "--remove-orphans"
    $started = $true
    Invoke-Docker @compose "up" "-d"

    $deadline = [DateTime]::UtcNow.AddSeconds($HealthTimeoutSeconds)
    do {
        $containerIds = @(& $docker @compose "ps" "-q")
        $healthy = $containerIds.Count -eq 2
        foreach ($containerId in $containerIds) {
            $status = & $docker inspect --format "{{.State.Health.Status}}" $containerId
            if ($LASTEXITCODE -ne 0 -or $status -ne "healthy") {
                $healthy = $false
            }
        }
        if ($healthy) {
            break
        }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    if (-not $healthy) {
        Invoke-Docker @compose "ps"
        throw "Phase 3 services did not become healthy before the timeout"
    }

    & $PythonPath -m unittest tests.t3_knowledge.test_t3_integration -v
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 3 integration tests failed with exit code $LASTEXITCODE"
    }
}
finally {
    if ($started -and -not $KeepServices) {
        try {
            Invoke-Docker @compose "down" "-v" "--remove-orphans"
        }
        catch {
            Write-Warning "Phase 3 service cleanup failed; run docker compose down manually."
        }
    }
    Pop-Location
    foreach ($name in @(
        "STWI_QDRANT_API_KEY",
        "STWI_QDRANT_READ_ONLY_API_KEY",
        "STWI_TSDB_PASSWORD",
        "STWI_READER_PASSWORD",
        "STWI_QDRANT_URL",
        "STWI_TSDB_DSN",
        "QDRANT_HTTP_PORT",
        "QDRANT_GRPC_PORT",
        "TSDB_PORT"
    )) {
        Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
    }
}
