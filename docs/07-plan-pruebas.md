# 07 · Plan de pruebas

Estado: **APROBADO con cambios** (21-11-2026): pruebas de filtros duros y selección del lote (`/p4`, `/p5`), creación de
la postulación en "Descargar" (`/p5`), conservación de página y tablas (`/p7`), tope de gasto de IA (`/p7`) y conjunto
de evaluación que funciona desde 5 licitaciones (§3).

Niveles:
- **Unitarias**: lógica pura, sin red ni base (`tests/unit`). Rápidas, en cada push.
- **Integración**: con Postgres real del compose, Storage local y API externa simulada con `respx` (`tests/integration`).
  **Nunca se llama a la API real de Mercado Público ni al LLM real en CI.**
- **Aceptación**: criterios de la sección 17 por etapa (`tests/acceptance`), automáticos cuando es posible y con una
  revisión manual del propietario al cierre de cada etapa.
- **Evaluación**: calidad de la IA sobre el conjunto de evaluación (`backend/evals`), manual / bajo demanda, con costo.

Cobertura objetivo: ≥ 85 % en `scoring`, `review_excel`, `analysis/citations`, `workflow`, `core/timezones`; ≥ 70 % global.

## 1. Pruebas transversales de zona horaria (desde `/p4`)

Chile continental (`America/Santiago`) alterna UTC-4 (invierno) y UTC-3 (verano). Las fechas de transición se obtienen
**de la base `tzdata` fijada en el lockfile**, no se escriben a mano (el gobierno las ha cambiado varias veces).

| Caso | Qué se verifica |
| --- | --- |
| Fin del horario de verano (se atrasa 1 h; una hora local ocurre dos veces) | Un cierre publicado en la hora ambigua se convierte con la regla documentada (`fold=0`, primera ocurrencia) y se guarda el texto original; el Excel muestra la hora local publicada. |
| Inicio del horario de verano (se adelanta 1 h; una hora local no existe) | Un texto con hora inexistente no se "corrige" en silencio: queda marcado `parse_status='unparseable'` o se aplica la regla documentada, con alerta. |
| Cierre a las 23:59 del día previo y posterior a cada transición | Ida y vuelta local → UTC → local exacta. |
| Días corridos y hábiles al cierre cruzando una transición | El conteo no se desplaza un día. |
| Feriados de Chile (incl. feriados movibles del año) | Días hábiles excluyen feriados; se compara con la lista oficial del año. |
| Fechas con y sin zona en la respuesta de la API | Se aplica el formato confirmado en `/p2-api` (A VALIDAR si la API entrega hora local sin zona). |
| Scheduler | Con reloj simulado en ambas transiciones el radar corre exactamente una vez por día local. |
| Prueba de propiedad (`hypothesis`) | Para cualquier instante UTC de 2020-2035: `to_utc(to_chile(t)) == t`. |
| Windows | La suite corre en Windows con el paquete `tzdata` (sin base IANA del sistema). |

Zonas especiales: Magallanes (`America/Punta_Arenas`) e Isla de Pascua (`Pacific/Easter`) tienen otra hora. Se
asume que las fechas de la API vienen en hora continental; A VALIDAR EN /p2-api con una licitación de Magallanes.

## 2. Pruebas por etapa

### `/p3` Fundaciones

| Tipo | Pruebas |
| --- | --- |
| Unitarias | Configuración falla si falta variable obligatoria; filtro de logs elimina `ticket=…` y `Authorization`; cifrado y descifrado Fernet; matriz de permisos por rol. |
| Integración | Migraciones `upgrade`/`downgrade` en base limpia; semilla idempotente de 5 líneas; JWT válido/expirado/firma inválida; usuario sin membresía → 403; `audit_events` no admite UPDATE/DELETE; RLS activado en todas las tablas de `app`. |
| Aceptación | Levantar en Windows con un comando; login; editar una línea de servicio y ver el evento de auditoría; CI en verde. |

### `/p4` Radar

| Tipo | Pruebas |
| --- | --- |
| Unitarias | Adaptador: respuestas grabadas → modelo canónico (incl. campos vacíos frecuentes); pre-filtro; clasificador por reglas (palabras clave con y sin tilde, exclusiones que ganan, rubros); puntaje reproducible y acotado 0-100 (propiedad); parseo de fechas (§1); filtros duros: Publicada sí/no, cierre a 2, 3 y 4 días (borde exacto, cruzando cambio de horario), fecha de cierre no interpretable (no se descarta). |
| Integración | Cuota: al llegar al límite la corrida termina "parcial" y no hace más llamadas; 429/5xx → backoff y reintento; timeout no pierde lo guardado; **segunda corrida del mismo día no crea registros nuevos** [17-MVP1-2]; cambio de estado o fecha → `opportunity_changes`; `internal_status` y estado oficial se actualizan por separado; oportunidad que deja de estar Publicada sin decisión → `cerrada_sin_decision`; ticket nunca aparece en `api_call_log` ni logs (búsqueda en la salida capturada); ejecución manual y programada (hora configurable) con reloj simulado. |
| Aceptación | Corrida real de un día (manual, con ticket): oportunidades capturadas, top 10 con justificación, consumo de cuota; corrida programada registrada en `radar_runs` [17-MVP1-1]. |

### `/p5` Excel 1

| Tipo | Pruebas |
| --- | --- |
| Unitarias | Columnas, orden, tipos y formatos según `06`; validaciones de lista presentes; hoja protegida; `_control` muy oculta y firmada con la regla de selección usada; nombre de archivo; inyección de fórmulas neutralizada. Selección del lote (`06` §1.0): 30 candidatas → entran 30; 80 candidatas con 20 de puntaje ≥ 40 → entran 50; 80 candidatas con 65 de puntaje ≥ 40 → entran 65; empates de puntaje con orden estable; valores configurables. |
| Integración | Ida y vuelta completa; filas alteradas (código cambiado, Verificador roto); código de otro lote; lote desconocido; versión anterior; decisión fuera de lista; fila duplicada; **Descartar sin motivo → rechazada; Descargar sin responsable → rechazada; Dudoso vacío → aceptada**; mismo archivo dos veces (idempotente); cambio de decisión con historial; `.xlsm` renombrado rechazado. **Las filas válidas se registran aunque haya inválidas** [17-MVP1-4]. "Descargar" crea exactamente una postulación (`bids`) con responsable, su intake y su carpeta en la misma transacción (si falla la carpeta, no queda postulación a medias); cambio de Descargar a Descartar sin documentos → postulación `desistida`; Dudoso reaparece en el próximo lote. |
| Aceptación | Excel real generado en `data/exports/`; el propietario lo marca en Excel de escritorio (Windows) y se reimporta; fechas coinciden con la ficha oficial en una muestra [17-MVP1-6]. |

### `/p6` Intake

| Tipo | Pruebas |
| --- | --- |
| Unitarias | Detección de tipo real; reglas de ZIP (bomba de compresión, `../`, rutas absolutas, demasiados archivos); cálculo de hash. |
| Integración | Archivo duplicado (mismo hash) → detectado [17-MVP2-2]; ZIP con subcarpetas; exe renombrado a pdf → rechazado; archivo a medio copiar no se procesa hasta estabilizarse; **carga en oportunidad sin postulación (sin "Descargar") → rechazada** [17-MVP2-1]; documento tardío → nueva versión + `requires_reanalysis`. |
| Aceptación | Carga real de 2-3 licitaciones por carpeta y por UI. |

### `/p7` Análisis

| Tipo | Pruebas |
| --- | --- |
| Unitarias | Normalización de citas (espacios, saltos, guiones de corte de línea, comillas tipográficas); verificador: cita exacta, cita con espacios distintos, **cita falsa → `no_verificado`**, cita en otra página → `no_verificado`; esquemas rechazan valor "encontrado" sin cita; huella de requisitos estable; presupuesto: suma mensual en hora de Chile (cambio de mes a medianoche local), alerta exactamente al 80 %, bloqueo al 100 %. |
| Extracción (página y tablas, aprobación del propietario) | Fixtures ficticios generados para la prueba: PDF de 12 páginas con texto único por página → cada fragmento tiene la página correcta; PDF con portada y páginas romanas → se usa la página física, no la impresa; PDF mixto con 2 páginas escaneadas → OCR solo en esas y con su página; tabla de criterios con ponderaciones → filas y columnas exactas y suma 100 %; tabla que cruza de página → reconocida en ambas páginas con su número; DOCX con títulos y tabla → sección y tabla correctas; XLSX → hoja y celda; DOC/XLS convertidos → mismo resultado que el original moderno. |
| Integración | 2 bases ficticias en fixtures (marcadas como datos de prueba) con un `FakeLLMProvider` de respuestas grabadas: extracción completa; **campo inexistente → `no_encontrado`**; contradicción entre bases y aclaración; **documento con instrucciones maliciosas → ignoradas**; registro de costo en `ai_usage`; reintento de corrida fallida; con costos simulados sobre el tope, el análisis queda `blocked_budget` y se libera al subir el tope (auditado). |
| Contrato del proveedor | Pruebas marcadas `@pytest.mark.llm` (fuera de CI, manuales) que llaman a cada proveedor real con una base ficticia corta y validan el esquema. |
| Aceptación | Análisis de una licitación real cargada por el propietario: campos con cita y estado, costo de la corrida; el propietario compara contra las bases. |

### `/p8` Excel 2

| Tipo | Pruebas |
| --- | --- |
| Unitarias | Semáforo (cada regla y su prioridad); recomendación; formato de cada estado de valor. |
| Integración | Ficha con campos faltantes; contradicción entre documentos; ida y vuelta de decisiones Go/No-Go; **corrección humana que sobrevive a un reanálisis**; prueba que recorre todas las celdas de origen IA del archivo y exige cita verificada o marca [17-MVP2-4]; hoja de detalle por licitación presente [17-MVP2-5]. |
| Aceptación | Excel 2 real con las licitaciones analizadas; el propietario decide sobre fichas reales. |

### `/p9` Evaluación

Ver §3.

## 3. Conjunto de evaluación

- **Calendario (decisión del propietario):** 5 licitaciones anotadas al terminar `/p7`; luego crece hasta 15-20.
  `/p9` se construye para funcionar desde 5. Con n < 15 los resultados se informan como fracciones (p. ej. "4/5 líneas
  correctas") y se marcan **indicativos**: con 5 casos un solo error baja la coincidencia a 80 %. Los umbrales se
  confirman cuando el conjunto llegue a 15-20. Las 5 primeras deberían cubrir al menos 3 líneas de servicio distintas,
  1 negativa y 1 con aclaración o modificación.
- **Composición objetivo:** 15-20 licitaciones TI reales y recientes (idealmente ya cerradas, para que no cambien), repartidas
  entre las 5 líneas de servicio, más 3-5 **negativas** (no TI o con palabras engañosas, p. ej. "soporte de mobiliario"),
  al menos 2 con PDF escaneado, 2 con aclaraciones o modificaciones, 1 con anexos en XLSX y 1 de Magallanes.
- **Anotación (propietario):** por licitación: código, líneas de servicio correctas, fechas clave tal como aparecen en la
  ficha, presupuesto (monto, moneda, impuestos), plazos, SLA, garantías, lista de requisitos excluyentes, y qué campos
  **no existen** en las bases. Plantilla y guía en `/p9`.
- **Ubicación:** `backend/evals/data/` (fuera de git). Al repo solo plantilla, código y resultados agregados sin texto de
  las bases.
- **Métricas y umbrales provisionales** (configurables; los confirma el propietario):

| Métrica | Objetivo | Criterio |
| --- | --- | --- |
| Coincidencia de líneas de servicio | ≥ 85 % | [17-MVP1-5] |
| Exactitud de fechas vs ficha oficial | 100 % | [17-MVP1-6] |
| Recall de requisitos excluyentes (coincidencia aproximada de texto, revisada a mano en los dudosos) | ≥ 90 % | [17-MVP2-3] |
| Valores con cita verificada o marcados | 100 % | [17-MVP2-4] |
| Valores inventados (valor donde la anotación dice "no existe") | 0 | Regla 9 |
| Exactitud por campo de la ficha | informativo | — |
| Costo y tiempo por licitación | informativo | Decisión de proveedor |

- **Uso:** primera corrida con las 5 iniciales (mide clasificación y fechas de MVP-1 y análisis de MVP-2), luego al
  agregar licitaciones, al cambiar prompts o modelos y para comparar las 3 configuraciones (Opus 5.5, Sonnet 5.5,
  OpenAI). Antes de correr se muestra el costo estimado; las corridas cuentan para el tope mensual de IA. Los resultados se guardan con versión de prompt, modelo y fecha para comparar.
