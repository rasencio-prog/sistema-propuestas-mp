# ADR-0012 · Entorno de desarrollo en Windows sin Docker; Supabase en la nube también para desarrollo

- Estado: Aceptada
- Fecha: 22-11-2026
- Modifica: ADR-0001 (ya no se replica Supabase localmente con Supabase CLI) y ADR-0008 (el backend ya no corre en
  contenedores, ni en desarrollo ni, por ahora, en producción)

## Contexto

El equipo del propietario tiene la virtualización deshabilitada en el BIOS y no hay acceso a la BIOS para
habilitarla, por lo que **Docker Desktop no puede instalarse** (y con él, tampoco `supabase start` de Supabase CLI,
que depende de Docker para levantar Postgres/Storage/Auth local). El equipo tiene además 16 GB de RAM con uso alto
de otras aplicaciones, lo que desaconseja sumar contenedores aunque la virtualización estuviera disponible.

Ya instalados y confirmados por el propietario: Python 3.13.3 y Node.js 22.14.0 (v22 LTS).

## Decisión

- **Base de datos, Storage y Auth de desarrollo:** un proyecto Supabase en la nube dedicado, **`sistema-propuestas-dev`**
  (región São Paulo), separado del proyecto de producción que se crea más adelante. No hay réplica local de Supabase:
  se desarrolla siempre contra este proyecto en la nube.
- **Backend (FastAPI) y worker (Procrastinate):** proceso nativo de Windows, Python **3.13** (no 3.12 como decía
  `docs/01` §2.1 originalmente) dentro de un entorno virtual (`backend/.venv`, gestionado con `uv`). Se verifica en
  `/p3-fundaciones` que todas las dependencias fijadas (SQLAlchemy 2.0, `psycopg` 3, Pydantic v2, `structlog`,
  `cryptography`, `holidays`, `tzdata`, Procrastinate, SDK `anthropic` y `openai`, `ruff`, `mypy`, `pytest`) tengan
  rueda binaria o compilen en 3.13 en Windows; si alguna no la tiene, se fija a una versión compatible o, como último
  recurso, se vuelve a 3.12 con una nueva ADR (no se asume de antemano).
- **Frontend:** proceso nativo con Node 22 LTS (`npm run dev` de Vite), sin cambios respecto de lo ya decidido más
  allá de dejar de pasar por un contenedor "web" en desarrollo. El framework del frontend (React + Vite en vez de
  Next.js) es una decisión aparte, ver ADR-0013.
- **Tesseract y LibreOffice:** instalación nativa de los binarios en Windows, recién en `/p7-analisis` (no se
  necesitan antes).
- **Conexión a la base:** ver detalle de cadenas de conexión y variables de entorno en `docs/01` §2.9 y
  `.env.example`. Resumen: la app, Alembic y el worker usan la misma cadena, por el **Session Pooler** de Supabase
  (puerto 5432), porque Procrastinate necesita `LISTEN/NOTIFY` (incompatible con el Transaction Pooler, puerto 6543)
  y porque el Session Pooler funciona por IPv4, sin depender de que la red del propietario tenga IPv6 (la conexión
  directa de Supabase es IPv6 por defecto; el add-on de IPv4 es de pago).
- **Base de pruebas de integración (local):** un esquema **`test`** dentro del mismo proyecto Supabase de desarrollo,
  con un rol de Postgres restringido (`test_runner`) que solo tiene permisos sobre ese esquema y ninguno sobre `app`
  ni `procrastinate`. Las pruebas de integración locales se conectan con ese rol fijando `search_path=test` en la
  cadena de conexión (`TEST_DATABASE_URL`), de modo que las mismas migraciones de Alembic (que crean tablas sin
  calificar el esquema) terminan en `test` en lugar de en `app`, sin tocar código. El rol y el esquema se crean una
  sola vez a mano en el editor SQL de Supabase (instrucciones en `/p3-fundaciones`); no es una migración de Alembic
  porque crear un rol de base de datos es una operación de la instancia, no del esquema de la aplicación. CI sigue
  usando su propio Postgres efímero de GitHub Actions (sin tocar Supabase en absoluto).
- **Producción:** sigue sin decidirse (ADR-0008). Las dos rutas que se evalúan antes de cerrar MVP-2 no cambian por
  esta ADR: (a) un servicio que construye la imagen de contenedor desde el repo (Railway, Render, Fly.io, Cloud Run,
  Azure Container Apps — el *build* del contenedor ocurre en la nube, no en el equipo del propietario) o (b) despliegue
  directo de Python sin contenedor (p. ej. un runtime nativo de un PaaS). Se mantiene un `Dockerfile` opcional en
  `infra/docker/` solo para la ruta (a); no se exige para desarrollar ni se prueba localmente.

## Consecuencias

- **Windows (dev) vs Linux (prod, cuando se elija servicio de contenedores):** se pierde la paridad total que daba
  "todo en contenedores" (ADR-0001 la contaba como ventaja). Diferencias posibles: finales de línea, rutas, y sobre
  todo los binarios nativos de Tesseract/LibreOffice (compilados distinto en Windows que en la imagen Linux del
  Dockerfile). Mitigación: CI corre en Linux (runner de GitHub Actions) como red de seguridad antes de cualquier
  cambio importante; el `Dockerfile` de producción define y prueba el entorno real (Linux) cuando se implemente,
  no se asume que “funciona en mi equipo” sea suficiente para esa parte.
- **Dependencia de conexión a internet para desarrollar:** sin red no hay acceso a la base (Supabase en la nube), así
  que no se puede migrar, correr pruebas de integración ni levantar el backend contra datos reales. Las pruebas
  unitarias (sin red ni base) siguen funcionando sin conexión. No hay mitigación técnica más allá de una red estable;
  queda como riesgo documentado (`docs/08` R-13 revisado).
- **Base de pruebas comparte infraestructura física con los datos de desarrollo** (mismo proyecto Supabase, esquema
  distinto). El aislamiento es por permisos de rol, no solo por convención: si el rol `test_runner` se configurara mal
  y quedara con acceso a `app`, una prueba podría alterar datos reales. Mitigación: permisos otorgados una sola vez,
  documentados, revisables en el panel de Supabase (Database → Roles); ninguna prueba debe correr con las
  credenciales de `DATABASE_URL` (las de la app), solo con `TEST_DATABASE_URL`.
- Se actualiza `docs/01` §2.1 (Python 3.12 → 3.13), §2.3 (Storage: ya no hay Supabase CLI local), §2.8 y §2.9 (entorno
  local y producción actual), §3 (se quita Supabase CLI de las dependencias grandes aprobadas) y `docs/04` (se quita
  `infra/compose.yaml` y el `supabase/` de CLI local; estructura de scripts nativos).
- Costo adicional: cero. El proyecto Supabase de desarrollo puede vivir en el plan Free (con el riesgo ya documentado
  en `docs/08` R-14 de pausa por inactividad, que ahora también aplica al proyecto dev, no solo al de producción).
