# Levanta el worker de Procrastinate en local, sin Docker (ADR-0012).
# Sin tareas todavia (Etapa 1): valida que el worker se conecta y lee su esquema de colas.
# Uso: desde la raiz del repo, .\scripts\dev-worker.ps1
$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "..\backend"
Set-Location $backend

if (-not (Test-Path ".venv")) {
    Write-Host "No existe backend\.venv. Corre primero: python -m uv sync (dentro de backend\)." -ForegroundColor Yellow
    exit 1
}

python -m uv run procrastinate --app sp.jobs.app.app worker
