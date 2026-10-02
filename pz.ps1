$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    python (Join-Path $PSScriptRoot 'scripts/host.py') @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
