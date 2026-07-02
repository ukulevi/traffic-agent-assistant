[CmdletBinding()]
param(
    [switch]$BuildPdf
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
Set-Location $repoRoot

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path "project_contract.json")) {
    throw "Run this script inside the STWI repository."
}

Invoke-Checked "Documentation validator" { python scripts\validate_docs.py }
Invoke-Checked "Contract tests" { python -m unittest tests.test_project_contract }

if (Get-Command node -ErrorAction SilentlyContinue) {
    Invoke-Checked "presentation.js syntax" { node --check slides\js\presentation.js }
    Invoke-Checked "presentation-tools.js syntax" { node --check slides\js\presentation-tools.js }
} else {
    Write-Warning "Node.js is unavailable; JavaScript syntax checks were skipped."
}

Invoke-Checked "Git whitespace check" { git diff --check }

if ($BuildPdf) {
    if (-not (Get-Command xelatex -ErrorAction SilentlyContinue)) {
        throw "XeLaTeX is unavailable."
    }

    Push-Location report
    try {
        Invoke-Checked "XeLaTeX pass 1" { xelatex -interaction=nonstopmode -halt-on-error main.tex }
        Invoke-Checked "XeLaTeX pass 2" { xelatex -interaction=nonstopmode -halt-on-error main.tex }

        $fatal = Select-String -Path main.log -Pattern "Undefined control sequence|There were undefined references|Emergency stop|Fatal error" -ErrorAction SilentlyContinue
        if ($fatal) {
            $fatal | ForEach-Object { Write-Error $_.Line }
            throw "LaTeX log contains release-blocking errors."
        }
    } finally {
        Pop-Location
    }
}

Write-Host "STWI verification passed." -ForegroundColor Green