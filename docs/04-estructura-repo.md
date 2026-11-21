# 04 · Estructura del repositorio

Estado: **APROBADO** (21-11-2026).

Basada en la sección 21 del brief, ajustada a la arquitectura liviana (`01-decisiones-tecnicas.md`).
Cambios respecto del brief: se quita `/app` como raíz intermedia (no aporta), `workers/` pasa a ser `jobs/` con
tareas de Procrastinate, se agregan `modules/llm`, `modules/workflow`, `modules/audit` y la carpeta `supabase/`.
Las carpetas de MVP-3 (`company_library`, `proposals`, `economics`, `analytics`) **no se crean** hasta su etapa.

```text
sistema-propuestas-mp/
├── .claude/                      # comandos de Claude Code (ya existe)
├── .github/workflows/ci.yml      # ruff, mypy, pytest, lint frontend
├── backend/
│   ├── pyproject.toml            # uv; dependencias fijadas en uv.lock
│   ├── uv.lock
│   ├── alembic.ini
│   ├── migrations/               # Alembic: env.py + versions/ (toda modificación de esquema)
│   ├── src/sp/                   # paquete "sp" (sistema de propuestas)
│   │   ├── main.py               # crea la app FastAPI
│   │   ├── api/                  # rutas REST internas, finas: validan y llaman a modules/
│   │   │   ├── deps.py           # usuario actual, organización, rol requerido
│   │   │   ├── health.py
│   │   │   ├── config_routes.py  # líneas de servicio, perfiles de puntaje, credencial API
│   │   │   ├── radar_routes.py   # corridas, ejecución manual
│   │   │   ├── review_routes.py  # Excel 1 / Excel 2: generar, descargar, importar
│   │   │   └── intake_routes.py  # pendientes, carga, "carga completa"
│   │   ├── core/
│   │   │   ├── settings.py       # pydantic-settings (lee .env sin imprimirlo)
│   │   │   ├── logging.py        # structlog JSON + filtro de secretos
│   │   │   ├── security.py       # verificación JWT (JWKS de Supabase), roles
│   │   │   ├── crypto.py         # Fernet para el ticket
│   │   │   ├── db.py             # engine, sesiones, esquema "app"
│   │   │   ├── storage.py        # interfaz FileStorage + Supabase / local
│   │   │   └── timezones.py      # UTC ↔ America/Santiago, días hábiles
│   │   ├── modules/
│   │   │   ├── audit/            # registro reutilizable de audit_events
│   │   │   ├── users/
│   │   │   ├── organizations/    # organizaciones, miembros, api_credentials
│   │   │   ├── service_lines/    # líneas de servicio + semilla de las 5 del brief
│   │   │   ├── marketplace_adapters/
│   │   │   │   ├── base.py       # interfaz + modelo canónico (CanonicalOpportunity…)
│   │   │   │   ├── quota.py      # cuota diaria, ritmo, backoff
│   │   │   │   └── mp_v1/        # adaptador API Mercado Público v1 (solo campos de docs/10)
│   │   │   ├── opportunities/    # normalización, dedupe, cambios, fechas
│   │   │   ├── classification/   # reglas + clasificador IA opcional
│   │   │   ├── scoring/          # puntaje 0-100, semáforo (determinístico, sin IA)
│   │   │   ├── workflow/         # máquina de estados de bids
│   │   │   ├── review_excel/     # Excel 1 y Excel 2: export, import, _control, row_token
│   │   │   ├── intake/           # carpeta vigilada, carga UI, ZIP seguro, hash
│   │   │   ├── documents/        # extracción PDF/DOCX/XLSX, OCR, chunks, clasificación documental
│   │   │   ├── analysis/         # orquestación de la extracción IA, verificación de citas, contradicciones
│   │   │   └── llm/              # LLMProvider + anthropic_provider + openai_provider, costos
│   │   ├── schemas/              # Pydantic compartidos (API y salidas de IA)
│   │   │   └── extraction/       # esquemas de la ficha (versión en el nombre)
│   │   ├── prompts/              # textos de prompts versionados (semilla de prompt_templates)
│   │   └── jobs/                 # tareas Procrastinate: radar, intake_watch, extract, analyze, excel
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/          # con Postgres real del compose
│   │   ├── acceptance/           # criterios de la sección 17 por etapa
│   │   └── fixtures/             # DATOS FICTICIOS marcados; respuestas API grabadas y saneadas
│   └── evals/
│       ├── harness/              # código del arnés (/p9)
│       ├── templates/            # plantilla de anotación + guía
│       └── data/                 # BASES REALES — excluida en .gitignore
├── frontend/                     # Next.js + TypeScript (mínimo)
│   ├── package.json
│   └── src/app/
│       ├── login/
│       ├── configuracion/        # líneas de servicio y palabras clave
│       ├── lotes/                # lotes y ejecuciones
│       └── documentos/           # carga de documentos
├── infra/
│   ├── docker/
│   │   ├── backend.Dockerfile    # API
│   │   └── worker.Dockerfile     # + tesseract-ocr-spa + libreoffice-core
│   └── compose.yaml              # api, worker, web (Supabase lo levanta su CLI)
├── supabase/                     # config.toml de Supabase CLI (sin migraciones: van por Alembic)
├── data/                         # LOCAL, excluida en .gitignore
│   ├── intake/<código>/          # bandeja vigilada de carga asistida
│   └── exports/                  # Excel generados para revisión
├── docs/
│   ├── 00..09-*.md               # este plan
│   ├── 10-api-validada.md        # sale de /p2-api
│   ├── api-samples/              # respuestas saneadas (sin ticket)
│   ├── decisions/                # ADR
│   └── brief/
├── scripts/                      # utilidades y exploración (no producción): explore_mp_api.py, seed, etc.
├── .env.example                  # sin valores
├── .gitignore                    # .env, data/, backend/evals/data/, exports
├── CLAUDE.md
└── README.md
```

Notas:
- `src/` layout evita importar por accidente desde la carpeta de trabajo y facilita empaquetar el worker y la API desde
  la misma imagen base.
- La carpeta `data/` vive fuera del control de versiones. El repo se trabaja en `C:\dev\sistema-propuestas-mp`, fuera de
  OneDrive (decisión del propietario), para que `.env`, `data/intake` y `data/exports` no se sincronicen con la nube.
- La dirección de dependencias es `api → modules → core`; `modules/*` no importan `api`. Entre módulos se usan servicios
  públicos (`service.py`) y no se tocan las tablas de otro módulo directamente.
