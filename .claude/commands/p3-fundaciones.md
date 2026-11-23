---
description: Etapa 1 – Fundaciones del repositorio
---

Lee CLAUDE.md y docs/ (decisiones aprobadas en 01, modelo en 03, estructura en 04, ADR en docs/decisions/, en especial
ADR-0001, ADR-0002, ADR-0003, ADR-0008, **ADR-0012** y **ADR-0013**). Implementa la Etapa 1 – Fundaciones con el stack aprobado.

El equipo del propietario no puede correr Docker (ADR-0012): todo el entorno local es nativo de Windows, contra un
proyecto Supabase en la nube dedicado a desarrollo (`sistema-propuestas-dev`). No crear ni requerir
`infra/compose.yaml` ni Supabase CLI local. El `Dockerfile` de `infra/docker/` (si se llega a escribir en esta etapa)
es un artefacto opcional para la producción futura en un servicio de contenedores; no se usa para desarrollar ni
se prueba aquí.

Alcance:
1. Estructura de carpetas según docs/04 (sin `infra/compose.yaml` ni `supabase/` de CLI local).
2. Entorno local en Windows sin Docker (ADR-0012):
   - `backend/.venv` (Python 3.13, gestionado con `uv`). Antes de fijar versiones en `uv.lock`, verifica que cada
     dependencia de docs/01 §2 tenga rueda binaria o compile en 3.13 en Windows; si alguna no la tiene, dímelo y
     propón una alternativa (pin a otra versión, o volver a 3.12 con una nueva ADR) antes de continuar.
   - `scripts/dev-api.ps1`, `scripts/dev-worker.ps1`, `scripts/dev-web.ps1`: lanzadores de PowerShell que activan el
     entorno correspondiente y levantan FastAPI (uvicorn), el worker de Procrastinate y el frontend (`npm run dev` de
     Vite, puerto 5173 por defecto) por separado. Pocos comandos documentados para levantar todo.
   - CORS en el backend (FastAPI): habilita explícitamente el origen `http://localhost:5173` (dev del frontend Vite,
     ADR-0013); sin esto el SPA no puede llamar a la API desde el navegador. Deja el origen configurable por variable
     de entorno para cuando se decida dónde se sirve el frontend en producción.
   - Conexión a la base: una sola variable `DATABASE_URL` (Session Pooler de Supabase, puerto 5432) usada por la app,
     Alembic y el worker, porque Procrastinate necesita `LISTEN/NOTIFY` (incompatible con el Transaction Pooler) y
     porque el Session Pooler funciona por IPv4 sin depender de que la red del propietario tenga IPv6. Verifica esto
     contra la documentación vigente de Supabase antes de fijarlo en código; si algo cambió, dímelo.
   - Habilita la extensión **pgvector** en el proyecto Supabase de desarrollo mediante una migración de Alembic
     (`CREATE EXTENSION IF NOT EXISTS vector;`), no a mano en el panel.
   - Base de pruebas de integración local (docs/07 §0, ADR-0012): crea, documentándolo paso a paso para que yo lo
     ejecute una sola vez en el editor SQL de Supabase, el esquema `test` y un rol `test_runner` con permisos solo
     sobre ese esquema (nada sobre `app` ni `procrastinate`). Define `TEST_DATABASE_URL` (mismo Session Pooler, rol
     `test_runner`, `options=-csearch_path=test`) y un fixture de `pytest` que verifique `current_schema() = 'test'`
     antes de correr `tests/integration`.
3. Backend con configuración por variables de entorno, logging estructurado en JSON con request_id (con filtro que elimina secretos) y endpoint /health con estado de base y cola.
4. Migraciones iniciales con Alembic en el esquema app, con RLS activado y sin políticas (ADR-0002), solo para: users, organizations, organization_members, api_credentials (ticket cifrado en reposo con Fernet), service_lines, audit_events. Incluye la instalación del esquema de Procrastinate. Semilla con las 5 líneas de servicio del brief (sección 2) y sus palabras clave, editables.
5. Autenticación con Supabase Auth (ADR-0003): el backend valida el JWT de Supabase (firma JWKS, expiración, audiencia) usando `SUPABASE_URL`; usuarios, organización y roles viven en nuestras tablas. Roles: administrador, comercial, revisor, solo lectura.
6. Frontend mínimo (React + Vite + TypeScript, SPA, ADR-0013): crea el proyecto con Vite, React Router para navegar
   entre login y una página de configuración de líneas de servicio y palabras clave. Nada más por ahora. El cliente
   `@supabase/supabase-js` para el login usa `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`; las llamadas a la API
   propia usan `VITE_API_BASE_URL`. Las tres van en `frontend/.env.local` (Vite no lee el `.env` de la raíz del
   repo; documenta esta copia en el README). Nunca pongas ahí una clave secreta: Vite expone al navegador cualquier
   variable con prefijo `VITE_`.
7. Registro de auditoría reutilizable, usado desde ya en login y cambios de configuración.
8. Pruebas: configuración de pytest (y del frontend si aplica), pruebas de auth (con JWT de prueba firmados localmente), roles y auditoría. Las de integración corren contra el esquema `test` del punto 2.
9. CI en GitHub Actions: lint + pruebas en cada push, con un servicio Postgres + pgvector propio del workflow (no Supabase; no depende de la red ni del equipo del propietario).
10. Completa .env.example sin valores reales (MP_TICKET, APP_ENCRYPTION_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, DATABASE_URL, TEST_DATABASE_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL — las tres últimas documentadas ahí pero copiadas a `frontend/.env.local`). Actualiza el README con instrucciones paso a paso para Windows sin Docker (y para macOS/Linux si alguna vez se usan, dejando claro que Windows es el entorno real del propietario).
11. Completa los comandos estándar en CLAUDE.md (levantar, pruebas, migraciones, lint) con los comandos de PowerShell reales, no genéricos.

Fuera de alcance: radar, Excel, documentos, IA.

Antes de agregar dependencias grandes no listadas en docs/01, pregúntame. Al terminar: ejecuta las pruebas, muéstrame el resultado, dime los comandos para levantarlo y detente.
