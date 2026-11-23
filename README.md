# Sistema de Propuestas – Mercado Público + IA

Plataforma para detectar licitaciones en Mercado Público, analizarlas con IA y preparar propuestas con revisión humana.
Especificación: `docs/brief/`. Reglas del proyecto para el agente: `CLAUDE.md`.

## Entorno local: Windows nativo, sin Docker (ADR-0012)

El equipo del propietario no puede correr Docker (virtualización deshabilitada). Todo corre como procesos nativos
de Windows (Python 3.13 vía `uv`, Node 22 para el frontend) contra un proyecto **Supabase en la nube** dedicado a
desarrollo (`sistema-propuestas-dev`). No hace falta instalar Docker Desktop ni Supabase CLI.

### Requisitos ya instalados (confirmados por el propietario)

- Python 3.13.3
- Node.js 22.14.0 (LTS)
- Acceso al proyecto Supabase `sistema-propuestas-dev` (URL, claves y contraseña de base de datos)

### 1. Instalar `uv` (gestor de paquetes de Python)

```powershell
pip install --user uv
```

Si `uv` no queda en el PATH, en todos los comandos de abajo puedes usar `python -m uv` en vez de `uv`
(hace exactamente lo mismo).

### 2. Backend: crear el entorno virtual e instalar dependencias

```powershell
cd backend
python -m uv python pin 3.13
python -m uv sync
```

Esto crea `backend\.venv` (excluido de git) y fija `backend\uv.lock`. Las dependencias ya se verificaron: todas
tienen rueda binaria para Windows / Python 3.13 (sin necesidad de compilador).

### 3. Completar `.env` (raíz del repo)

```powershell
cd ..
copy .env.example .env
```

Completa en `.env` (nunca se versiona; ver `.env.example` para dónde sacar cada valor en el panel de Supabase):

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`
- `DATABASE_URL` (Session Pooler, puerto 5432, con `options=-csearch_path=app` — ya viene en el formato de ejemplo)
- `APP_ENCRYPTION_KEY` (generar una vez con el comando que indica el comentario del archivo)
- `TEST_DATABASE_URL` (requiere el paso 4 primero)
- `MP_TICKET` solo hace falta desde `/p2-api` (ya validado en esta etapa, pero no se usa todavía en el código)

### 4. Configuración única en Supabase: esquema `test` y rol `test_runner` (ADR-0012)

Esto se hace **una sola vez**, a mano, en el **editor SQL** del proyecto `sistema-propuestas-dev`
(panel de Supabase → SQL Editor). Es una operación de la instancia (crear un rol de Postgres), no un cambio de
esquema de la aplicación, por eso no es una migración de Alembic.

```sql
-- 1) Esquema para las pruebas de integracion locales (ADR-0012, docs/07 S0).
CREATE SCHEMA IF NOT EXISTS test;

-- 2) Rol restringido para las pruebas: todo sobre "test", nada sobre "app"
--    (las tablas de Procrastinate viven dentro de "app" tambien, ver ADR-0014,
--    asi que "ningun permiso sobre app" ya las cubre).
--    Cambia la contrasena antes de usarla en TEST_DATABASE_URL.
CREATE ROLE test_runner WITH LOGIN PASSWORD 'cambia-esta-contrasena';

-- Con USAGE + CREATE en el esquema "test", test_runner puede correr "alembic upgrade head"
-- (las tablas que cree quedan de su propiedad; no hace falta otorgar nada mas).
GRANT USAGE, CREATE ON SCHEMA test TO test_runner;

-- test_runner nunca debe tener permisos sobre "app" ni "public": no se otorga nada ahi
-- (por defecto un rol nuevo no tiene ningun permiso sobre esquemas que no sean el suyo).
```

Con eso, completa `TEST_DATABASE_URL` en `.env` (Session Pooler, mismo proyecto, usuario `test_runner`,
`options=-csearch_path=test`; formato exacto en el comentario de `.env.example`).

### 5. Migraciones (crea las tablas en `app`, instala pgvector/citext y el esquema de Procrastinate)

```powershell
cd backend
python -m uv run alembic upgrade head
```

Importante: corre esto **antes** que cualquier prueba de integración (crea la extensión `vector` con privilegios
que el rol `test_runner` no tiene; ver ADR-0014).

### 6. Levantar el backend y el worker

En dos terminales de PowerShell distintas, desde la raíz del repo:

```powershell
.\scripts\dev-api.ps1       # FastAPI (uvicorn) en http://localhost:8000, con recarga automatica
.\scripts\dev-worker.ps1    # Worker de Procrastinate (sin tareas todavia en esta etapa)
```

Verifica con `curl http://localhost:8000/health` (debe responder `{"status":"ok", ...}`).

### 7. Frontend

```powershell
cd frontend
npm install
```

Crea `frontend\.env.local` (Vite no lee el `.env` de la raíz) con:

```
VITE_SUPABASE_URL=...        # igual que SUPABASE_URL
VITE_SUPABASE_ANON_KEY=...   # igual que SUPABASE_ANON_KEY (nunca una clave secreta)
VITE_API_BASE_URL=http://localhost:8000
```

Luego, desde la raíz del repo:

```powershell
.\scripts\dev-web.ps1
```

Abre `http://localhost:5173`.

### 8. Primer usuario administrador

La migración siembra la organización ("Databrain SpA") y las 5 líneas de servicio, pero **no** puede crear tu
usuario porque todavía no existe tu identidad en Supabase Auth. Pasos:

1. Crea tu usuario en el panel de Supabase (Authentication → Users → Add user) o regístrate desde el login del
   frontend si está habilitado el alta propia.
2. Copia tu `UID` (columna de esa misma tabla).
3. Desde `backend/`, con el entorno activado:

   ```powershell
   python -m uv run python ../scripts/seed_admin.py --auth-user-id <tu-UID> --email tu@correo.cl --full-name "Tu Nombre"
   ```

Después de esto, el login debería devolver rol `admin` y la página de Configuración debería listar las 5 líneas
de servicio.

## Comandos estándar (ver también CLAUDE.md)

| Acción | Comando |
| --- | --- |
| Levantar API | `.\scripts\dev-api.ps1` |
| Levantar worker | `.\scripts\dev-worker.ps1` |
| Levantar frontend | `.\scripts\dev-web.ps1` |
| Migrar | `cd backend; python -m uv run alembic upgrade head` |
| Pruebas backend | `cd backend; python -m uv run pytest` |
| Lint backend | `cd backend; python -m uv run ruff check .` |
| Formato backend | `cd backend; python -m uv run ruff format .` |
| Tipos backend | `cd backend; python -m uv run mypy src` |
| Lint frontend | `cd frontend; npm run lint` |
| Build frontend | `cd frontend; npm run build` |

## macOS / Linux (no es el entorno real del propietario, solo si alguna vez se usa)

Los mismos comandos funcionan igual, reemplazando los `.ps1` por sus pasos equivalentes (`source .venv/bin/activate`
no hace falta con `uv run`; el resto — `uv sync`, `alembic upgrade head`, `uvicorn`, `npm run dev` — es idéntico).

## Cómo trabajar con Claude Code en VS Code

1. Completa `docs/00-decisiones-propietario.md`.
2. Sigue los pasos de arriba para levantar el entorno local.
3. Abre el panel de Claude Code y ejecuta los comandos en orden. Cada uno termina con el agente detenido esperando tu revisión.

| Orden | Comando | Etapa | Tu revisión antes de seguir |
| --- | --- | --- | --- |
| 1 | `/p1-plan` | Descubrimiento y plan (sin código) | Aprobar stack, modelo de datos y backlog |
| 2 | `/p2-api` | Validación de la API con ticket real | Abrir 2 links de ficha y revisar el informe |
| 3 | `/p3-fundaciones` | Repo, entorno Windows sin Docker, base de datos (Supabase dev), login | Levantarlo en local |
| 4 | `/p4-radar` | Captura, clasificación y puntaje | Revisar las oportunidades capturadas |
| 5 | `/p5-excel1` | Excel de preselección | Marcar decisiones en un Excel real |
| 6 | `/p6-intake` | Carga asistida de adjuntos | Cargar adjuntos de 2 o 3 licitaciones |
| 7 | `/p7-analisis` | Análisis IA con citas verificadas | Comparar contra las bases |
| 8 | `/p8-excel2` | Fichas resumen y Go/No-Go | Decidir sobre fichas reales |
| 9 | `/p9-evals` | Conjunto de evaluación | Confirmar umbrales |

Comandos de apoyo: `/cierre-etapa` (antes de cada commit), `/corregir <qué pasó>` (cuando algo falla),
`/retomar` (al abrir una sesión nueva).

## Rutina por etapa
1. `git checkout -b etapa-N-nombre`
2. `/clear` para empezar con el contexto limpio, luego el comando de la etapa.
3. Revisar lo entregado; pedir ajustes en el mismo chat.
4. `/cierre-etapa`, revisar el resumen, commit y merge a `main`.
