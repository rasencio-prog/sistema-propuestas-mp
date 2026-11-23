# Levanta el frontend (Vite, React + TypeScript) en local (ADR-0013). Puerto 5173 por defecto.
# Uso: desde la raiz del repo, .\scripts\dev-web.ps1
$ErrorActionPreference = "Stop"
$frontend = Join-Path $PSScriptRoot "..\frontend"
Set-Location $frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "No existe frontend\node_modules. Corre primero: npm install (dentro de frontend\)." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path ".env.local")) {
    Write-Host "Falta frontend\.env.local (VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL). Ver README." -ForegroundColor Yellow
    exit 1
}

npm run dev
