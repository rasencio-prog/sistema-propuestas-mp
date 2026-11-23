# ADR-0014 · Selección de esquema por `search_path`; tablas de Procrastinate dentro de `app`

- Estado: Aceptada
- Fecha: 22-11-2026
- Decide: agente, en `/p3-fundaciones`, dentro del margen dejado por ADR-0002 y ADR-0012
- Aclara: ADR-0002 (esquema `app`) y ADR-0012 (base de pruebas local, esquema `test`, rol `test_runner`)

## Contexto

ADR-0012 establece que "las mismas migraciones de Alembic (que crean tablas sin calificar el esquema) terminan en
`test` en lugar de en `app`, sin tocar código", confiando en el `search_path` de la conexión. Para que esto funcione
de verdad hacía falta decidir dos detalles que ADR-0012 no fijó:

1. Si las migraciones usan `op.create_table(..., schema="app")` (calificado, no depende de `search_path`) o tablas
   sin calificar (depende 100 % de `search_path`, incluido para `DATABASE_URL`, que hasta ahora no mostraba la opción
   `search_path` en `.env.example`, a diferencia de `TEST_DATABASE_URL`).
2. Dónde viven las tablas de Procrastinate: ADR-0012 menciona un esquema `procrastinate` al describir los permisos
   del rol `test_runner` ("ninguno sobre `app` ni `procrastinate`"), pero Procrastinate instala sus tablas sin
   calificar esquema (confirmado en `procrastinate/sql/schema.sql`: `CREATE TABLE procrastinate_jobs (...)`, con el
   prefijo `procrastinate_` pensado justamente para convivir en el mismo esquema que las tablas de otra aplicación).

## Decisión

- **Ninguna migración (propia o de Procrastinate) califica el esquema.** Ni `op.create_table(..., schema=...)` ni
  `SET search_path` dentro del código de las migraciones. El esquema de destino lo decide por completo el
  `search_path` de la conexión usada para correr `alembic upgrade head`.
- **`DATABASE_URL` incorpora `?options=-csearch_path%3Dapp`**, igual que ya hacía `TEST_DATABASE_URL` con
  `search_path=test`. La usan por igual la app (FastAPI), Alembic y el worker de Procrastinate, así que todos ven el
  esquema `app` como destino por defecto sin ninguna rama de código distinta entre entornos. Se actualiza
  `.env.example` en consecuencia.
- **Las tablas de Procrastinate viven dentro del esquema `app`** (no se crea un esquema `procrastinate` separado):
  es el propio diseño de la librería (prefijo `procrastinate_` en cada tabla, pensado para compartir esquema). Esto
  reinterpreta la frase de ADR-0012 sobre el rol `test_runner` ("ninguno sobre `app` ni `procrastinate`") como
  "ninguno sobre `app`, lo que ya cubre las tablas de Procrastinate al vivir en ese mismo esquema" — no como un
  tercer esquema literal.
- **Cadena única de migraciones:** `alembic.ini` apunta `version_locations` a `backend/migrations/versions` (propias)
  y al paquete vendido `procrastinate.contrib.alembic.versions`. La primera migración propia
  (`0001_app_foundations`) encadena `down_revision = "procrastinate_0043"` (la última revisión de Procrastinate al
  fijar esta versión), de modo que `alembic upgrade head` aplica primero el esquema de Procrastinate y luego el
  propio, en un solo comando, igual en local (`DATABASE_URL`), pruebas (`TEST_DATABASE_URL`) y CI.
- **La extensión `pgvector`** se instala con `CREATE EXTENSION IF NOT EXISTS vector` en una migración separada,
  idempotente. Se asume que la primera vez que alguien corre `alembic upgrade head` es contra `DATABASE_URL` (rol
  con privilegios suficientes en el proyecto Supabase), de modo que cuando más adelante se corra la misma migración
  contra `TEST_DATABASE_URL` (rol `test_runner`, con privilegios mínimos) la extensión ya existe y `IF NOT EXISTS`
  no vuelve a intentar crearla. El README deja esto explícito en el orden de los pasos.

## Consecuencias

- El rol `test_runner` necesita, además de todo sobre el esquema `test`, **ningún permiso adicional**: ni `app` ni
  "procrastinate" como esquema aparte, porque no existe tal esquema. El script SQL de configuración única
  (`README.md`) ya no crea un esquema `procrastinate`.
- Si en el futuro Procrastinate necesitara aislarse en su propio esquema (p. ej. por higiene al crecer el número de
  tablas), es un cambio de `search_path` dentro de una migración puntual con su propio `SET search_path` acotado a
  esa migración — no afecta esta decisión mientras el volumen sea el de 1-3 usuarios previsto.
- Cualquier futura migración debe seguir la misma regla: nunca calificar el esquema ni fijar `search_path` a mano,
  para no romper el mecanismo de `test`.
