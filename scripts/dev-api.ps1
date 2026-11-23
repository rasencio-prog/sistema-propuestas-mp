# Levanta la API (FastAPI/uvicorn) en local, sin Docker (ADR-0012).
# Uso: desde la raiz del repo, .\scripts\dev-api.ps1
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend"
Set-Location $backend

if (-not (Test-Path ".venv")) {
    Write-Host "No existe backend\.venv. Corre primero: python -m uv sync (dentro de backend\)." -ForegroundColor Yellow
    exit 1
}

python -m uv run uvicorn sp.main:app --reload --host 0.0.0.0 --port 8000
