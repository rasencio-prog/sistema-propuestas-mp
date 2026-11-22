# 01 · Decisiones técnicas (propuesta para aprobación)

Estado: **APROBADO con cambios** el 21-11-2026. Cada decisión marcada con ⚑ está registrada como ADR en
`docs/decisions/` (lista en §4). Cambios respecto de la propuesta: producción local en Docker (ADR-0008), presupuesto
de IA y condición de no entrenamiento (§2.7), pruebas de página y tablas en la extracción (§2.6).

Contexto que condiciona todo: 1 usuario hoy (máximo 1-3), radar diario nocturno, solo licitaciones, desarrollo en Windows
con Docker, producción ya elegida por el propietario en **Supabase** (PostgreSQL + pgvector + Storage + Auth).

---

## 1. Comparación de arquitecturas

| Criterio | A. Brief de referencia: FastAPI + Celery/Redis + MinIO + Postgres propio | B. Liviana: FastAPI + Postgres gestionado (Supabase) + cola sobre Postgres |
| --- | --- | --- |
| Piezas a operar | 5-6 contenedores: API, worker, beat, Redis, MinIO, Postgres | 2 procesos propios (API, worker) + Supabase gestionado |
| Costo mensual estimado (1-3 usuarios) | VPS 4 GB (~USD 20-40) + respaldos y almacenamiento a cargo nuestro | Supabase Free para piloto / Pro USD 25 + host de API/worker (~USD 5-20) |
| Respaldos, parches, TLS de la base | Nuestros | Del proveedor (Pro incluye respaldos diarios) |
| Volumen de trabajos | Diseñado para miles/seg | Decenas por día (radar 1 vez/día + análisis de pocas licitaciones) — sobra |
| Consistencia trabajo ↔ datos | Dos sistemas (Redis y Postgres): un trabajo puede encolarse aunque la transacción falle | La cola vive en la misma base: se encola dentro de la misma transacción |
| Paridad dev/prod | Alta (todo en Docker) | Alta si en local se usa Supabase CLI (también Docker) |
| Riesgo de lock-in | Bajo | Medio-bajo: Auth y Storage son de Supabase, pero detrás de interfaces propias; la base es Postgres estándar |
| Escalar a multiempresa | Directo | Directo hasta cientos de usuarios; luego se agrega Redis si hiciera falta |

### Recomendación: **B — arquitectura liviana** ⚑

- **Costo:** menos de la mitad y sin tiempo de administración de servidores.
- **Complejidad:** se eliminan Redis, Celery beat y MinIO; menos dependencias que mantener y probar en Windows.
- **Operación:** respaldos y parches de la base los hace Supabase; nosotros solo operamos dos procesos Python sin estado.
- **Coherencia con lo ya decidido:** el propietario eligió Supabase para producción.
- **Salida de emergencia:** monolito modular con interfaces (`JobQueue`, `FileStorage`, `AuthVerifier`, `LLMProvider`).
  Si algún día hiciera falta, se cambia Procrastinate por Celery o Supabase Storage por S3 sin tocar el dominio.

Lo que **no** cambia respecto del brief: FastAPI, PostgreSQL + pgvector, openpyxl, Docker, monolito modular, frontend Next.js
mínimo.

---

## 2. Stack concreto

### 2.1 Backend

| Necesidad | Elección | Por qué | Descartado |
| --- | --- | --- | --- |
| Lenguaje | Python 3.12 | Ecosistema de documentos y Excel; 3.12 tiene ruedas binarias estables para todas las librerías elegidas | 3.13: algunas ruedas OCR/PDF aún tardan |
| Gestor de paquetes | `uv` | Rápido, lockfile reproducible, funciona igual en Windows | Poetry (más lento) |
| API | FastAPI + Pydantic v2 | Indicado en el brief; esquemas Pydantic sirven también para validar salidas de la IA | — |
| ORM / acceso a datos | SQLAlchemy 2.0 + `psycopg` 3 | Estándar, tipado, compatible con Alembic y Procrastinate | asyncpg directo (más código) |
| Migraciones | **Alembic** ⚑ | Toda modificación de esquema por migración, versionada en el repo, misma herramienta local y prod | Migraciones SQL de Supabase CLI (sin autogeneración desde modelos) |
| Configuración | `pydantic-settings` + `python-dotenv` | Lee `.env` sin imprimirlo; tipado y validación de variables | — |
| Logging | `structlog` (JSON) | `request_id`, `job_id`, `batch_id`, `opportunity_code` como campos; filtro que enmascara secretos | logging plano |
| Cliente HTTP | `httpx` + `tenacity` | Timeouts, reintentos con backoff exponencial y jitter | requests |
| Cifrado del ticket | `cryptography` (Fernet), clave en `APP_ENCRYPTION_KEY` | Portable entre local y Supabase; rotación de clave posible (MultiFernet) | Supabase Vault (ata el cifrado a Supabase) |
| Feriados para días hábiles | `holidays` (calendario CL) | Días hábiles al cierre en el Excel 1; se valida contra lista oficial anual | Tabla manual |
| Zona horaria | `zoneinfo` + paquete **`tzdata`** | Windows no trae base IANA; `tzdata` la fija por versión en el lockfile | pytz |

### 2.2 Cola de trabajos y scheduler ⚑

- **Procrastinate** (cola sobre PostgreSQL, licencia MIT): trabajos con reintentos, bloqueos por clave
  (p. ej. un solo análisis por oportunidad a la vez), tareas periódicas tipo cron y trabajos encolados en la misma
  transacción que los datos.
- **Scheduler del radar:** tarea periódica **cada hora**; el propio trabajo decide si corresponde correr comparando la hora
  configurada en `America/Santiago` y si ya existe una corrida exitosa para la "fecha radar" de hoy. Ventajas: inmune a
  cambios de horario, se recupera solo si el equipo estuvo apagado, nunca corre dos veces el mismo día.
- Detalle operativo: el worker se conecta a Supabase por la **conexión directa / pooler en modo sesión** (puerto 5432),
  no por el pooler en modo transacción, porque Procrastinate usa `LISTEN/NOTIFY`. Si no estuviera disponible, Procrastinate
  funciona por sondeo (polling) cada pocos segundos, suficiente para este volumen.
- Alternativas evaluadas: Celery + Redis (exceso de piezas), `pgqueuer` (más joven, sin cron maduro), cola casera con
  `SELECT … FOR UPDATE SKIP LOCKED` (reinventar reintentos y cron).

### 2.3 Almacenamiento de archivos ⚑

- Interfaz `FileStorage` con dos implementaciones: **Supabase Storage** (bucket privado `documents`, prod y local vía
  Supabase CLI) y **disco local** (pruebas unitarias).
- Rutas lógicas: `org/<org_id>/opportunities/<código>/v<n>/<sha256>-<nombre>`; los Excel exportados en
  `org/<org_id>/exports/…`.
- **Bandeja de carga (`intake/<código>/`)**: carpeta del sistema de archivos local (configurable, `INTAKE_ROOT`), vigilada
  por el worker. Tras validar y calcular el hash, el archivo se copia al almacenamiento definitivo y se mueve a
  `intake/<código>/_procesados/`. Mientras el backend corre en el equipo del propietario (ADR-0008) ambas vías funcionan;
  cuando pase a un servicio de contenedores en la nube, la vía principal será la carga desde la UI, porque la carpeta
  vigilada solo existe donde corre el worker.

### 2.4 Autenticación ⚑

- **Supabase Auth** (email + contraseña; MFA TOTP disponible para el administrador). El frontend obtiene el JWT y lo
  envía a FastAPI; FastAPI verifica la firma con las claves JWKS del proyecto y resuelve usuario, organización y rol desde
  tablas propias (`users`, `organization_members`).
- Los roles y permisos viven en nuestras tablas, no en Supabase: administrador, comercial, revisor, solo lectura
  (técnico y aprobador quedan definidos para MVP-3).
- **El navegador nunca habla directo con la base**: las tablas van en el esquema `app` (no expuesto por la Data API de
  Supabase) y además con RLS activado sin políticas (deniega todo a `anon` y `authenticated`). Solo el backend accede.

### 2.5 Frontend

- **Next.js (App Router) + TypeScript**, como dice el brief, pero mínimo: login, líneas de servicio/palabras clave,
  lotes y ejecuciones, carga de documentos. Componentes con Tailwind + shadcn/ui. Cliente `@supabase/supabase-js` solo
  para el login.
- Se consideró FastAPI + Jinja2 + HTMX (sin Node): más simple para 4 pantallas, pero obligaría a rehacer la UI en la
  etapa "Pantallas web". Se mantiene Next.js para no desviarse del brief.

### 2.6 Documentos: extracción, OCR y Excel ⚑ (desvío parcial del brief)

| Formato | Librería | Ubicación que se conserva |
| --- | --- | --- |
| PDF con texto | `pdfplumber` (MIT) | Página, coordenadas; tablas con `extract_tables` |
| PDF escaneado / página sin texto | `pypdfium2` (render a imagen) + **Tesseract 5** con `spa` vía `pytesseract` | Página; marca `ocr=true` y confianza media |
| DOCX | `python-docx` | Encabezado/sección (estilos Heading), número de párrafo, tablas |
| XLSX | `openpyxl` (solo lectura, `data_only=True`) | Hoja y celda (`Hoja!B12`) |
| DOC / XLS / RTF (heredados) | LibreOffice headless (`soffice --convert-to`) en el contenedor worker → DOCX/XLSX | Igual que el formato convertido; se guarda el original |
| ZIP | `zipfile` (stdlib) con límites | Ruta interna del archivo |
| Detección de tipo real | `filetype` + validación estructural (abrir el archivo) | — |

- **Pruebas obligatorias (aprobación del propietario):** cada fragmento conserva su número de página (PDF, incluidas las
  páginas con OCR), su sección (DOCX) o su hoja y celda (XLSX); y las tablas se extraen como tablas (filas y columnas),
  verificado con fixtures que incluyen una tabla de criterios con ponderaciones y una tabla que cruza de página.
- **Desvío respecto del brief (aprobado):** el brief sugiere **Docling**. Docling es de muy buena calidad en tablas, pero arrastra
  PyTorch y modelos (imagen Docker de varios GB, lento en CPU). Para 1-3 usuarios y bases TI que en su mayoría son PDF
  con texto, se propone `pdfplumber` + Tesseract y dejar **Docling como plan B**, activable detrás de la interfaz
  `DocumentExtractor`, si en `/p9-evals` la extracción de tablas (criterios y ponderaciones) no alcanza el umbral.
- **PyMuPDF descartado** por licencia AGPL (problema para el SaaS futuro).
- **Excel 1 y Excel 2:** `openpyxl` (validaciones, protección de hoja, formato condicional, hipervínculos, hojas ocultas).
- Generación DOCX (`docxtpl`) queda para MVP-3.

### 2.7 Proveedor de IA ⚑ (aprobado: comparar Anthropic Opus 5.5 y Sonnet 5.5 contra OpenAI)

Interfaz propia `LLMProvider` (delgada, sin LiteLLM ni LangChain): `extract(schema, system, documents) -> modelo Pydantic validado`,
con registro de tokens, costo y latencia. Dos implementaciones para comparar en `/p9-evals`:

| | Opción 1 — Anthropic (Claude) | Opción 2 — OpenAI |
| --- | --- | --- |
| Modelo de extracción | `claude-opus-5-5` (USD 4 / 20 por millón de tokens entrada/salida) y, como variante económica dentro del mismo eval, `claude-sonnet-5-5` (USD 2 / 10) | Modelo de gama alta vigente de OpenAI con salidas estructuradas por JSON Schema — **ID y precio se fijan en `/p7` desde la documentación oficial** |
| Modelo de clasificación (capa opcional del radar) | `claude-haiku-5-5` (USD 0,10 / 0,50) | Modelo pequeño vigente de OpenAI |
| Contexto | 1 M tokens: bases completas de una licitación en una sola llamada | A verificar en `/p7` |
| Salida estructurada | `output_config.format` con JSON Schema generado desde Pydantic | JSON Schema estricto |
| Costos extra | Prompt caching (documentos fijos, varias llamadas por licitación) y Batch API (50 % menos) para el eval | Caché y batch propios |
| Uso de datos | **Requisito:** que el proveedor no use los datos para entrenar modelos (condición estándar de la API comercial; se verifica y se anota la fuente en `/p7`). Retención cero no se exige en MVP-1/2 | Mismo requisito |
| SDK | `anthropic` (oficial) | `openai` (oficial) |

Precios de Anthropic según la referencia vigente al 06-10-2026; se reconfirman al implementar `/p7`.

Notas de diseño que aplican a ambos:
- **Las citas se verifican en el backend** (determinístico), no se confía en la función de citas del proveedor
  (en Claude, además, la función de citas no se puede combinar con salida estructurada).
- **Estrategia de contexto MVP-2:** documentos completos con marcadores explícitos de página/sección
  (`[[doc=bases_tecnicas.pdf|p=12]]`), una llamada por grupo de campos de la ficha, documentos en el prefijo cacheado.
  Bases TI típicas (20-150 páginas) caben holgadas; sobre 600 páginas o 32 MB se divide por documento.
  Sin embeddings en MVP-2: pgvector se activa en MVP-3 (biblioteca empresarial).
- Los parámetros de muestreo (`temperature`) ya no se aceptan en los modelos actuales de Claude: la reproducibilidad se
  garantiza porque **el puntaje y el semáforo los calcula el backend**; la IA solo entrega factores.
- Costo estimado por licitación (100 páginas ≈ 60-80 k tokens, ~4 llamadas con caché): del orden de USD 0,30-1,00 con
  Opus 5.5; menos con Sonnet 5.5. Se mide de verdad en `/p9`.
- Se comparan **tres configuraciones** en `/p9`: Claude Opus 5.5, Claude Sonnet 5.5 y el modelo vigente de OpenAI. Se
  decide con el conjunto de evaluación (calidad en español, recall de excluyentes, valores inventados = 0, costo).
- **Presupuesto de IA (aprobado):** tope mensual configurable por organización, **valor inicial USD 40**, con **alerta al
  80 %**. Se calcula sumando `ai_usage.cost_usd` del mes calendario en hora de Chile. Al llegar al 80 %: evento de
  auditoría, aviso en "Lotes y ejecuciones" y advertencia en el log. Al llegar al 100 %: no se inician nuevos análisis
  (quedan en espera con estado `bloqueado_presupuesto`) hasta el mes siguiente o hasta que un administrador suba el tope
  (cambio auditado). Las corridas del eval cuentan para el mismo tope.
- **Primer uso de IA, antes de lo previsto aquí:** el resumen de 2-3 líneas del Excel 1 (MVP-1, columna "Resumen IA")
  también usa `LLMProvider` y cuenta contra este mismo tope, con modelo económico (Haiku) y caché — decisión del
  propietario posterior a esta sección, documentada en ADR-0011.
- Retención cero de datos y transferencia internacional se revisan en MVP-3 (CV y datos de la empresa).

### 2.8 Calidad y herramientas

| Ámbito | Herramienta |
| --- | --- |
| Lint y formato Python | `ruff` (lint + format) |
| Tipos | `mypy` en modo gradual (estricto en `scoring`, `review_excel`, `analysis`) |
| Pruebas | `pytest`, `pytest-cov`, `respx` (simular httpx), `freezegun`/`time-machine` (tiempo), `hypothesis` (fechas y puntaje) |
| Base de pruebas | Postgres con pgvector del `docker compose` en una base `test` separada |
| Frontend | ESLint + Prettier; Vitest para lo poco que haya |
| CI | GitHub Actions: ruff, mypy, pytest (servicio Postgres), lint del frontend |
| Pre-commit | `ruff`, detección de secretos (`gitleaks`) |

### 2.9 Entornos

| Entorno | Base, Storage, Auth | API y worker |
| --- | --- | --- |
| Local (Windows) | **Supabase CLI** (`supabase start`, sobre Docker Desktop) | `docker compose` con `api`, `worker` (incluye Tesseract y LibreOffice) y `web` |
| CI | Postgres + pgvector en contenedor; Auth simulado con JWT de prueba firmado localmente | — |
| Producción (ahora) | Proyecto Supabase en la nube (Pro recomendado: respaldos diarios y sin pausa por inactividad) | **En el equipo del propietario** (Windows + Docker), mismos contenedores que en desarrollo. Radar programado a hora configurable y ejecución manual (ADR-0008) |
| Producción (antes de cerrar MVP-2) | Igual | Servicio de contenedores a elegir: Railway, Render, Fly.io, Cloud Run o Azure Container Apps. Requisitos ya cumplidos por diseño: imágenes sin estado, configuración solo por variables de entorno, archivos en Supabase Storage, worker y API como procesos separados de la misma imagen |

---

## 3. Dependencias grandes aprobadas

Supabase CLI, Procrastinate, Tesseract (binario), LibreOffice headless (binario en la imagen del worker, ~400 MB),
SDK `anthropic` y `openai`, Next.js. Docling queda **como plan B documentado**: se instala solo si el eval lo
justifica, con nueva aprobación.

## 4. ADR registrados (`docs/decisions/`)

1. [ADR-0001](decisions/ADR-0001-arquitectura-liviana-supabase.md) Arquitectura liviana con Supabase y cola sobre Postgres (Procrastinate).
2. [ADR-0002](decisions/ADR-0002-migraciones-alembic-esquema-app.md) Alembic como única fuente de migraciones; esquema `app` no expuesto + RLS sin políticas.
3. [ADR-0003](decisions/ADR-0003-supabase-auth-roles-propios.md) Supabase Auth con roles propios.
4. [ADR-0004](decisions/ADR-0004-extraccion-pdfplumber-tesseract.md) Extracción con pdfplumber + Tesseract; Docling como plan B.
5. [ADR-0005](decisions/ADR-0005-proveedores-ia-y-presupuesto.md) Capa `LLMProvider` propia; proveedores a comparar y presupuesto.
6. [ADR-0006](decisions/ADR-0006-estado-interno-y-bids.md) Estado interno del embudo en `opportunities`; `bids` nace con "Descargar".
7. [ADR-0007](decisions/ADR-0007-scheduler-radar.md) Scheduler horario con guarda de "ya corrió hoy" en hora de Chile.
8. [ADR-0008](decisions/ADR-0008-produccion-local-contenedores.md) Producción inicial en el equipo del propietario; contenedores listos para un servicio en la nube.
9. [ADR-0009](decisions/ADR-0009-zona-horaria-api-mp.md) Zona horaria asumida (`America/Santiago`) para las fechas de la API; Magallanes/Isla de Pascua como riesgo.
10. [ADR-0010](decisions/ADR-0010-radar-detalle-toda-publicada.md) El radar pide el detalle de toda licitación nueva en Publicada; ritmo, backoff y ventana de cuota.
11. [ADR-0011](decisions/ADR-0011-resumen-ia-excel1.md) Resumen IA en el Excel 1 (MVP-1), cacheado y contra el mismo presupuesto de IA.
