# 04 · Estructura del repositorio

Estado: **APROBADO** (21-11-2026); entorno local sin Docker revisado el 22-11-2026 (ADR-0012); frontend React + Vite
en vez de Next.js revisado el 22-11-2026 (ADR-0013).

Basada en la sección 21 del brief, ajustada a la arquitectura liviana (`01-decisiones-tecnicas.md`).
Cambios respecto del brief: se quita `/app` como raíz intermedia (no aporta), `workers/` pasa a ser `jobs/` con
tareas de Procrastinate, se agregan `modules/llm`, `modules/workflow`, `modules/audit`.
Las carpetas de MVP-3 (`company_library`, `proposals`, `economics`, `analytics`) **no se crean** hasta su etapa.
Por ADR-0012 (desarrollo en Windows sin Docker): no hay `infra/compose.yaml` ni carpeta `supabase/` de Supabase CLI
local; el `Dockerfile` queda como artefacto opcional solo para la producción futura en un servicio de contenedores.

```text
sistema-propuestas-mp/
├── .claude/                      # comandos de Claude Code (ya existe)
├── .github/workflows/ci.yml      # ruff, mypy, pytest, lint frontend
├── backend/
│   ├── pyproject.toml            # uv; dependencias fijadas en uv.lock
│   ├── uv.lock
│   ├── .venv/                    # entorno virtual nativo de Windows (Python 3.13), excluido en .gitignore
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
│   │   ├── integration/          # con Postgres real: esquema `test` del proyecto Supabase dev (local, ADR-0012) o el servicio Postgres de CI
│   │   ├── acceptance/           # criterios de la sección 17 por etapa
│   │   └── fixtures/             # DATOS FICTICIOS marcados; respuestas API grabadas y saneadas
│   └── evals/
│       ├── harness/              # código del arnés (/p9)
│       ├── templates/            # plantilla de anotación + guía
│       └── data/                 # BASES REALES — excluida en .gitignore
├── frontend/                     # React + Vite + TypeScript, SPA mínima (ADR-0013)
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── .env.local             # VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL (excluido en .gitignore)
│   └── src/
│       ├── main.tsx           # monta React Router
│       ├── App.tsx            # rutas: login, configuración, lotes, documentos
│       ├── lib/
│       │   ├── supabaseClient.ts  # @supabase/supabase-js, solo para el login
│       │   └── apiClient.ts       # fetch a FastAPI con el JWT (VITE_API_BASE_URL)
│       └── pages/
│           ├── Login.tsx
│           ├── Configuracion.tsx  # líneas de servicio y palabras clave
│           ├── Lotes.tsx          # lotes y ejecuciones
│           └── Documentos.tsx     # carga de documentos
├── infra/
│   └── docker/                   # OPCIONAL (ADR-0012): solo para la producción futura en un servicio de
│                                  # contenedores; no se usa para desarrollar ni se exige en /p3
│       ├── backend.Dockerfile    # API
│       └── worker.Dockerfile     # + tesseract-ocr-spa + libreoffice-core
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
│                                  # + lanzadores nativos de Windows (PowerShell, ADR-0012): dev-api.ps1,
│                                  # dev-worker.ps1, dev-web.ps1 (cada uno activa backend/.venv donde corresponde)
├── .env.example                  # sin valores
├── .gitignore                    # .env, backend/.venv, frontend/node_modules, data/, backend/evals/data/, exports
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
