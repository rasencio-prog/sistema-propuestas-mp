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

## Adenda: hallazgos de la puesta en marcha real contra Supabase (22-11-2026)

Al ejecutar `alembic upgrade head` por primera vez contra el proyecto Supabase real (`sistema-propuestas-dev`),
aparecieron seis problemas que esta decisión original no prevenía, los seis ya corregidos:

1. **El Session Pooler de Supabase (PgBouncer) ignora en silencio el parámetro de arranque `options`.** La
   cadena `?options=-csearch_path%3Dapp` llega al pooler pero nunca se aplica como `search_path` de la sesión
   real en Postgres: `current_schema()` seguía devolviendo `public`, y las tablas de la Etapa 1 terminaron ahí
   (expuestas por la Data API) en el primer intento. **Corrección:** el `search_path` ya no depende de que el
   pooler honre `options`; se fuerza con un `SET search_path TO <esquema>, public` ejecutado justo después de
   abrir cada conexión física, vía el evento `connect` de SQLAlchemy (`sp.core.db.attach_search_path`) para la
   app/Alembic/pruebas de integración, y vía el callback `configure` de `psycopg_pool` para el worker de
   Procrastinate (`sp/jobs/app.py`). La opción `options=-csearch_path=...` en la URL se conserva igual (no hace
   daño y es coherente con `TEST_DATABASE_URL`), pero ahora es solo una convención propia que
   `extract_target_schema` lee para saber **qué** esquema fijar con el `SET` — no es lo que realmente lo fija.
2. **`alembic upgrade head` corría todas las migraciones (las de Procrastinate + las propias) en una sola
   transacción.** Las migraciones de Procrastinate se autoconfirman internamente
   (`context.autocommit_block()`), pero el registro de `alembic_version` que hace el propio Alembic después de
   cada revisión no estaba dentro de ese bloque autocommit. Un fallo en una migración posterior (ver punto 3)
   revertía ese registro aunque el DDL de Procrastinate ya hubiera quedado aplicado de verdad, dejando
   `alembic_version` desalineado con el estado real de la base. **Corrección:** `transaction_per_migration=True`
   en `context.configure(...)` (`migrations/env.py`, modos online y offline): cada revisión se confirma por
   separado.
3. **Error de Postgres `AmbiguousParameter` en la semilla de líneas de servicio** (migración
   `0003_seed_service_lines`): un mismo parámetro (`:name`) aparecía en dos contextos de tipo distinto dentro de
   un único `INSERT ... SELECT ... WHERE NOT EXISTS (...)` (una vez en la lista `SELECT`, sin tipo inferible, y
   otra vez comparado con una columna `varchar`), y Postgres no logra deducir un tipo único para el parámetro.
   **Corrección:** se separó en dos sentencias (un `SELECT` de existencia y, si no existe, un `INSERT` plano),
   igual que ya hacía `_get_or_create_organization` para la organización.
4. **El esquema `app` no existía al correr `alembic upgrade head` por primera vez en una base nueva**, y nada lo
   creaba a tiempo: las 43 migraciones vendidas de Procrastinate corren **antes** que las propias (porque la
   primera migración propia encadena `down_revision = "procrastinate_0043"`), así que con `app` todavía
   inexistente, esas migraciones (y el propio `alembic_version`) terminaron creándose en `public` antes de que
   `0001_extensions` llegara a crear `app`. Las migraciones propias (`0002` en adelante), corridas ya con `app`
   existente, sí quedaron bien. **Corrección real:** el esquema `app` se crea **antes** de correr cualquier
   migración, a mano, en el mismo paso único del editor SQL que ya crea `test` (ver `README.md` §4). No es solo
   cuestión de orden: se comprobó en la práctica que `CREATE SCHEMA IF NOT EXISTS app` dentro de la migración
   falla igual con el rol restringido `test_runner` aunque `app` ya exista (`permission denied for database
   postgres`) — a diferencia de `CREATE EXTENSION IF NOT EXISTS`, que sí es un no-op sin privilegios especiales
   una vez que la extensión existe, `CREATE SCHEMA` exige el privilegio `CREATE` en la base de datos
   incondicionalmente. Por eso `0001_extensions` **ya no intenta crear el esquema** en absoluto: crear `app` solo
   puede ser un paso manual con un rol privilegiado, nunca parte de una migración pensada para correr también
   con `test_runner`.
5. **El propio `SET search_path` del punto 1 se podía deshacer con un `ROLLBACK` posterior en la misma conexión
   física.** psycopg3 abre conexiones con `autocommit=False`; el `SET` del evento `connect` quedaba dentro de una
   transacción implícita nunca confirmada, así que un `ROLLBACK` posterior (de SQLAlchemy al reciclar la conexión,
   o de cualquier transacción explícita que se deshace) también deshacía el `search_path`, devolviendo la sesión
   al esquema por defecto a mitad de uso. **Corrección:** `attach_search_path` hace `dbapi_connection.commit()`
   justo después del `SET`, para que quede fijo para toda la vida de esa conexión física sin importar cuántas
   transacciones lógicas se abran y cierren encima.
6. **El mismo problema del punto 5, en el worker de Procrastinate.** El callback `configure` de
   `psycopg_pool` (`sp/jobs/app.py`) tampoco confirmaba el `SET search_path`; `psycopg_pool` exige que una
   conexión recién configurada quede en reposo (no con una transacción abierta) y, al verla `INTRANS`, la
   descartaba y reintentaba sin parar (`"connection left in status INTRANS by configure function ...:
   discarded"` en bucle, visto al levantar el worker real). **Corrección:** `await conn.commit()` después del
   `SET` en `_configure_search_path`.

Ninguno de los seis cambia la decisión original (search_path decide el esquema, sin calificar nada en las
migraciones); solo corrigen **cómo** se aplica ese `search_path` en la práctica contra la infraestructura real de
Supabase, y cómo se confirman las migraciones. Quedan aplicados en: `sp/core/db.py`, `sp/core/settings.py`
(`effective_database_url`/`_ensure_search_path`), `sp/jobs/app.py`, `migrations/env.py`,
`migrations/versions/0003_seed_service_lines.py` y `tests/integration/conftest.py`.
