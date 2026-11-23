# ADR-0016 · `pgvector`/`citext` con `SCHEMA public` explícito (no el esquema ambiente)

- Estado: Aceptada
- Fecha: 23-11-2026
- Decide: agente, al diagnosticar un fallo de CI que no se reproducía contra Supabase
- Aclara: ADR-0014 (selección de esquema por `search_path`)

## Contexto

CI (Postgres efímero del workflow) fallaba las pruebas de integración con
`psycopg.errors.UndefinedObject: type "citext" does not exist` al crear la tabla `users` (columna
`email CITEXT`), mientras que localmente, contra el proyecto Supabase real, las 43 pruebas pasaban.

La migración `0001_extensions` instala `vector` y `citext` con `CREATE EXTENSION IF NOT EXISTS` sin
`SCHEMA` explícito, dejando que Postgres decida dónde instalarlas según el `search_path` ambiente en
ese momento (`app, public` o `test, public`, según cuál de las dos corridas independientes de la
migración esté corriendo). Se verificó que en el proyecto Supabase real ambas extensiones terminaron
en `public`, sin importar que el `search_path` activo al crearlas fuera `app, public`. No se pudo
verificar de la misma forma el Postgres efímero del workflow de CI (no hay forma de inspeccionarlo
desde aquí sin Docker, ADR-0012), pero el síntoma es consistente con que ese Postgres sí siga la regla
documentada de Postgres al pie de la letra (instalar en el primer esquema del `search_path` con
privilegio de `CREATE`, es decir `app` o `test`, no `public`): como `app` y `test` corren la migración
de forma independiente (cada una con su propio `alembic_version`, desde cero), la segunda corrida ve la
extensión ya registrada a nivel de base de datos (`IF NOT EXISTS`) y no la reinstala, pero el tipo
sigue viviendo solo en el esquema de la primera corrida — invisible para el `search_path` de la
segunda.

## Decisión

- `CREATE EXTENSION IF NOT EXISTS vector/citext` ahora fija `SCHEMA public` explícito en
  `migrations/versions/0001_extensions.py`. `public` es el único esquema que está siempre presente en
  el `search_path`, tanto para `app` como para `test` (`sp.core.db.attach_search_path` fija
  `"<esquema>, public"`), así que instalar ahí garantiza que ambas corridas vean el tipo sin importar
  cuál se ejecutó primero, sin depender de qué política de "esquema por defecto" tenga el servidor de
  turno.
- No se tocó nada de la configuración del CI (ya creaba los esquemas `app`/`test` igual que el paso
  manual de Supabase, README §4) ni el mecanismo de `search_path`/`attach_search_path` (ADR-0014): el
  problema era específico de dónde cae una extensión sin esquema explícito, no de cómo se fija el
  `search_path` de la sesión.
- El rol `test_runner` restringido (aislamiento probado en `test_schema_isolation.py`) no aplica en CI:
  CI usa el mismo rol superusuario (`postgres`) para `DATABASE_URL` y `TEST_DATABASE_URL`, y
  `is_superuser_connection` ya salta esa prueba específica en ese caso (sin cambios, ya estaba bien).
- Prueba agregada: `test_extension_lives_in_public_not_in_app_or_test` (verifica contra
  `pg_extension`/`pg_namespace` que `vector` y `citext` viven en `public`).

## Consecuencias

- Reinstalar `vector`/`citext` con `SCHEMA public` explícito en una base donde ya existen en `public`
  (como la Supabase real, ya verificado) es un no-op seguro.
- Verificado de nuevo localmente contra Supabase real tras el cambio: 44/44 pruebas pasan (las 43
  anteriores + la nueva). La verificación real de que esto corrige el CI solo se confirma cuando el
  workflow corra en GitHub Actions (no se pudo ejecutar ese Postgres efímero desde aquí).
- Cualquier extensión nueva que se agregue en el futuro debe fijar `SCHEMA public` explícito por la
  misma razón, no confiar en el `search_path` ambiente.
