# 06 · Especificación de Excel 1 y Excel 2

Estado: **APROBADO con cambios** (21-11-2026): selección del lote y filtros duros (§1.0), obligatoriedad de motivo y
responsable en la Compuerta 1 (§1.1 y §1.4), creación de la postulación al importar "Descargar" (§1.4), umbrales del
semáforo aprobados como provisionales (§2.4).

Base: secciones 5.2 y 5.3 del brief. Generación y lectura con `openpyxl`. Versión de formato: `excel-spec 1.0`
(se escribe en la hoja de control; si cambia la estructura, sube la versión y la importación rechaza formatos viejos).

## 0. Reglas comunes

| Tema | Regla |
| --- | --- |
| Fechas | Se calculan en UTC y se escriben como fecha-hora **en America/Santiago** (sin zona en la celda, formato `dd-mm-aaaa hh:mm`). El encabezado dice "(hora de Chile)". |
| Montos | Número con formato `#.##0` (separador de miles chileno). Si no es público: texto "No visible". |
| Protección | Hoja protegida **sin contraseña** (no estorba; la integridad real la garantiza `row_token`). Celdas editables con `locked=False`. Se permite filtrar, ordenar y ajustar ancho. |
| Listas cerradas | Validación de datos tipo lista con mensaje de error "Valor no permitido" y estilo "Detener". Las listas largas viven en la hoja oculta `_listas`. |
| Vista | Autofiltro en el encabezado; paneles inmovilizados en fila 2 y columna C; encabezado en negrita con relleno; ancho de columnas fijado. |
| Colores del sistema | Celdas del sistema con fondo gris claro; editables con fondo blanco y borde azul. |
| Fuente | Pie en la hoja de instrucciones: "Fuente de datos: ChileCompra – API de Mercado Público. Generado el <fecha> por Sistema de Propuestas." |
| Nombre de archivo | Excel 1: `preseleccion_<AAAA-MM-DD>_lote<N>_v<versión>.xlsx`. Excel 2: `fichas_<AAAA-MM-DD>_lote<N>_v<versión>.xlsx`. |
| Seguridad | Solo `.xlsx` (nunca `.xlsm`). Valores de texto que empiezan con `=`, `+`, `-` o `@` se escriben como texto (prefijo `'`) para evitar inyección de fórmulas. |

Origen: **API** = dato de la API oficial (campo exacto A VALIDAR EN /p2-api) · **Backend** = calculado de forma
determinística · **Clasificador** = reglas + IA opcional, validado · **IA+cita** = extracción con cita verificada ·
**Persona** = lo llena el revisor · **Construido** = armado por el sistema sin consultar el portal.

---

## 1. Excel 1 — Preselección

Hojas: `Oportunidades` (visible), `Instrucciones` (visible), `_listas` (muy oculta), `_control` (muy oculta).
Una fila por oportunidad candidata, ordenadas por puntaje descendente y luego por fecha de cierre ascendente.

### 1.0 Qué oportunidades entran al lote

Todos los valores son configurables en `scoring_profiles.thresholds` y quedan registrados en `_control`.

1. **Universo:** oportunidades con estado interno `detectada`, o `preseleccionada` con decisión vigente "Dudoso" o sin
   decisión en un lote anterior.
2. **Filtros duros:** estado oficial **Publicada** y cierre de ofertas a **3 días o más** desde la corrida
   (`min_days_to_close = 3`, días corridos). Sin filtro de monto, región ni organismo. Si la fecha de cierre no se pudo
   interpretar, la oportunidad no se descarta: entra con la celda de cierre en naranja.
3. **Selección:** las **50 de mayor puntaje** (`top_n = 50`) **más todas** las que tengan puntaje **≥ 40**
   (`min_score_include = 40`), sin puntaje mínimo duro. Es una unión: si hay más de 50 con puntaje ≥ 40, entran todas;
   si hay menos, se completa hasta 50 con las siguientes por puntaje.
4. Al exportar, las incluidas pasan a `preseleccionada`.

### 1.1 Hoja `Oportunidades`

| Col | Nombre | Tipo | Origen | Protegida | Validación | Formato condicional / notas |
| --- | --- | --- | --- | --- | --- | --- |
| A | Código licitación | Texto | API | Sí | — | **Llave de reimportación.** Negrita. |
| B | Nombre | Texto | API | Sí | — | Ajuste de texto. |
| C | Descripción | Texto (máx. 500 car.) | API | Sí | — | Truncada con "…"; la completa queda en la ficha. |
| D | Organismo | Texto | API | Sí | — | |
| E | Unidad compradora | Texto | API | Sí | — | A VALIDAR EN /p2-api si viene en listado o solo en detalle. |
| F | Región | Texto | API | Sí | — | |
| G | Tipo de licitación | Texto | API | Sí | — | Texto oficial (y código entre paréntesis). A VALIDAR EN /p2-api. |
| H | Monto estimado | Número o "No visible" | API + Backend | Sí | — | "No visible" en gris cursiva. Moneda A VALIDAR EN /p2-api. |
| I | Moneda | Texto | API | Sí | — | CLP / UF / UTM / USD según venga. |
| J | Fecha de cierre (hora de Chile) | Fecha-hora | API + Backend | Sí | — | Convertida desde UTC. Si no se pudo interpretar: texto original + fondo naranja. |
| K | Días corridos al cierre | Entero | Backend | Sí | — | Calculado **al momento de exportar** (el encabezado lo dice). Rojo si ≤ umbral rojo (def. 3), amarillo si ≤ umbral amarillo (def. 7). |
| L | Días hábiles al cierre | Entero | Backend | Sí | — | Lunes a viernes sin feriados de Chile. Mismo formato que K. |
| M | Estado oficial | Texto "Publicada (5)" | API | Sí | — | Si ≠ Publicada, fila en gris. |
| N | Líneas de servicio | Texto (separadas por "; ") | Clasificador | Sí | — | "Sin línea" en naranja si no se asignó ninguna. |
| O | Puntaje de afinidad (0-100) | Entero | Backend | Sí | — | Escala de color de 3 puntos (0 rojo pálido – 50 – 100 verde). |
| P | Justificación | Texto (1-2 líneas) | Backend / Clasificador | Sí | — | Ej.: "Coincide 'mesa de ayuda', rubro 43232300; afinidad 82, plazo 12 días". |
| Q | Link a la ficha | Hipervínculo | Construido | Sí | — | Texto "Ver ficha"; URL construida con el patrón confirmado en /p2-api. El sistema no accede al portal. |
| R | Carpeta destino | Texto `intake/<código>/` | Construido | Sí | — | Ruta relativa a `INTAKE_ROOT`. Se crea **solo** al importar "Descargar". |
| S | Adjuntos cargados (Sí/No) | Texto Sí/No | Backend | Sí | — | "Sí" en verde si hay ≥ 1 documento registrado para esa oportunidad al momento de exportar. |
| T | Decisión | Lista | Persona | **No** | Lista: `Descargar`, `Descartar`, `Dudoso` (vacío permitido) | Verde / gris / amarillo según valor. |
| U | Motivo | Lista | Persona | **No** | Lista de `_listas!A` (abajo) | **Obligatorio solo si Decisión = Descartar.** Opcional en Descargar y Dudoso. |
| V | Comentario | Texto libre (máx. 500) | Persona | **No** | Largo de texto ≤ 500 | Complementa el motivo ("texto libre" del brief). |
| W | Responsable | Lista | Persona | **No** | Lista de `_listas!B` (miembros activos de la organización) | **Obligatorio solo si Decisión = Descargar.** Dudoso no tiene campos obligatorios. |
| X | Verificador | Texto (oculta) | Backend | Sí | — | `row_token` HMAC-SHA256(lote, código, fila) truncado a 16 car. Columna oculta. |

Lista de **Motivos** (`_listas!A`, configurable por organización):
`Alta afinidad`, `Cliente o organismo prioritario`, `Fuera de rubro`, `Monto bajo o no atractivo`, `Plazo insuficiente`,
`Requisitos probablemente inalcanzables`, `Región u organismo no prioritario`, `Ya revisada / duplicada`,
`Falta información para decidir`, `Otro (ver comentario)`.

### 1.2 Hoja `Instrucciones`

Texto en español de Chile: objetivo del lote; significado de cada decisión; qué columnas se editan (T-W); que no se
deben mover, borrar ni agregar filas o columnas; que "Días al cierre" corresponde a la fecha de exportación; cómo
devolver el archivo (pantalla "Lotes y ejecuciones"); qué pasa con "Dudoso" (vuelve en el próximo lote); fuente de datos.

### 1.3 Hoja `_control` (muy oculta, protegida)

| Clave (col. A) | Valor (col. B) |
| --- | --- |
| `format_version` | `excel-spec 1.0` |
| `batch_type` | `preselection` |
| `batch_id` | UUID del lote |
| `batch_number` | N |
| `version` | v |
| `organization_id` | UUID |
| `generated_at_utc` | ISO 8601 con `Z` |
| `generated_at_chile` | `dd-mm-aaaa hh:mm` |
| `generated_by` | email del usuario |
| `row_count` | cantidad de filas de datos |
| `timezone` | `America/Santiago` |
| `tzdata_version` | versión de la base IANA usada |
| `scoring_profile_version` | versión de pesos |
| `selection_rule` | `top_n=50; min_score_include=40; min_days_to_close=3; official_status=Publicada` (valores usados) |
| `signature` | HMAC del contenido de esta hoja (detecta edición de `_control`) |

### 1.4 Reglas de reimportación del Excel 1

Validación del archivo (se rechaza **todo** el archivo):
1. Extensión `.xlsx`, tamaño ≤ 10 MB, contenedor ZIP válido, sin `vbaProject.bin` ni objetos externos.
2. Existen `Oportunidades` y `_control`; `signature` válida; `format_version` soportada.
3. `batch_id` existe, pertenece a la organización del usuario y es de tipo `preselection`.
4. `version` es la **última exportada** de ese lote; si no, error "Este archivo es una versión anterior (vX); descargue la vY".
5. Encabezados idénticos a la especificación (nombre y orden).

Validación por fila (se rechaza solo la fila; las válidas se registran):

| Caso | Resultado |
| --- | --- |
| Decisión vacía | Ignorada (no es error); se informa como "sin decisión". |
| Código no pertenece al lote o `Verificador` no coincide | Rechazada: "código alterado o fila no corresponde al lote". |
| Código repetido en el archivo | Se rechazan **todas** las repeticiones: "fila duplicada". |
| Decisión fuera de lista | Rechazada: "decisión no válida". |
| Descartar sin Motivo | Rechazada: "falta motivo". |
| Descargar sin Responsable | Rechazada: "falta responsable". |
| Dudoso (con o sin motivo, comentario o responsable) | Aceptada; no tiene campos obligatorios. |
| Motivo o Responsable fuera de lista | Rechazada. |
| Misma decisión que la vigente | Aceptada sin cambios ("sin cambio"); no duplica registro. |
| Decisión distinta a la vigente y el estado interno aún lo permite | Aceptada; se guarda nueva decisión con `previous_decision_id` (historial, nunca se sobrescribe). |
| Cambio desde "Descargar" mientras la postulación sigue en `documentos_pendientes` y sin documentos | Aceptada; la postulación pasa a `desistida` (no se borra) y la oportunidad toma el nuevo estado. |
| Decisión distinta y la postulación ya avanzó (p. ej. `en_analisis`) | Rechazada: "la oportunidad ya avanzó; cambie el estado desde la aplicación". |

Efectos de una decisión aceptada (en una transacción por archivo, filas válidas):
- `Descargar` → la oportunidad pasa a `documentos_pendientes` y se **crea la postulación** (`bids`, con
  `status = documentos_pendientes`, el responsable y la decisión de origen), su `document_intakes` y la carpeta
  `intake/<código>/` (ADR-0006).
- `Descartar` → `descartada_preseleccion`.
- `Dudoso` → sigue `preseleccionada` y entra en el próximo lote.
- Cada decisión queda en `review_decisions` (usuario que importa, fecha UTC) y en `audit_events`.
- Reimportar exactamente el mismo archivo (mismo SHA-256) no repite nada: devuelve el informe anterior.
- Informe de importación (pantalla y descarga CSV): aceptadas, sin cambio, sin decisión y rechazadas con fila, código y motivo.

---

## 2. Excel 2 — Fichas resumen y Go/No-Go

Hojas: `Resumen` (visible), `Instrucciones`, una hoja de detalle por licitación (nombre = código oficial, ≤ 31 caracteres),
`_listas` y `_control` (muy ocultas, misma estructura que el Excel 1 con `batch_type = summary`).

Convención de estado de cada valor extraído (aplica a todas las celdas de origen IA+cita):

| Estado | Cómo se ve en la celda | Color |
| --- | --- | --- |
| Encontrado y cita verificada | Valor + nota de celda "Fuente: <documento>, pág./secc. X — «cita»" | Normal |
| No encontrado | Texto "No encontrado" | Fondo amarillo |
| No verificado (cita no coincide) | Valor + prefijo "[No verificado]" | Fondo naranja |
| Contradicción entre documentos | Valor del documento más reciente + "[Contradicción]" y nota con ambos valores | Fondo rojo claro |
| No aplica (las bases lo dicen expresamente) | "No aplica" + nota con la cita | Normal, gris |
| Corregido por persona | Valor corregido + nota "Corregido por <usuario> el <fecha>" | Borde verde |

### 2.1 Hoja `Resumen` (una fila por licitación analizada)

| Col | Nombre | Tipo | Origen | Protegida | Validación | Formato condicional / notas |
| --- | --- | --- | --- | --- | --- | --- |
| A | Código licitación | Hipervínculo a la ficha | API + Construido | Sí | — | Llave. Clic → ficha oficial. |
| B | Nombre | Texto | API | Sí | — | |
| C | Organismo | Texto | API | Sí | — | |
| D | Presupuesto o monto | Número o estado | IA+cita (respaldo API) | Sí | — | Convención de estados. Si difiere del monto de la API, nota "API indica X". |
| E | Moneda | Texto CLP/UF/UTM/USD | IA+cita | Sí | — | |
| F | Impuestos | Texto "Incluye IVA" / "No incluye IVA" / "Exento" / "No encontrado" | IA+cita | Sí | — | |
| G | Plazo de ejecución / contrato | Texto ("24 meses") | IA+cita | Sí | — | |
| H | Plazo de implementación | Texto | IA+cita | Sí | — | "No encontrado" frecuente: es válido. |
| I | Soporte / SLA / garantía técnica | Texto (≤ 300) | IA+cita | Sí | — | |
| J | Garantías | Texto: seriedad y fiel cumplimiento (monto o %, vigencia) | IA+cita | Sí | — | |
| K | Multas (resumen) | Texto (≤ 300) | IA+cita | Sí | — | |
| L | Criterios de evaluación | Texto "Técnica 60 %; Económica 30 %; …" | IA+cita | Sí | — | Rojo si las ponderaciones no suman 100 %. |
| M | Requisitos excluyentes (total) | Entero | Backend | Sí | — | |
| N | Excluyentes no cumple o pendientes | Entero | Backend (IA + revisión) | Sí | — | Rojo si hay ≥ 1 "no cumple"; amarillo si hay pendientes. |
| O | Cierre de preguntas (hora de Chile) | Fecha-hora | API / IA+cita | Sí | — | Prioridad API si existe; si difiere de las bases → contradicción. |
| P | Publicación de respuestas | Fecha-hora | API / IA+cita | Sí | — | |
| Q | Cierre de ofertas | Fecha-hora | API / IA+cita | Sí | — | Rojo si < umbral de días. |
| R | Apertura | Fecha-hora | API / IA+cita | Sí | — | |
| S | Adjudicación estimada | Fecha-hora | API / IA+cita | Sí | — | |
| T | Semáforo | Texto Verde/Amarillo/Rojo | Backend | Sí | — | Relleno del color. Reglas en 2.4. |
| U | Recomendación | Texto Participar / Revisar / No participar | Backend | Sí | — | Sugerencia; nunca decide. |
| V | Motivo del semáforo | Texto | Backend | Sí | — | Ej.: "1 excluyente no cumple; cierre en 2 días hábiles". |
| W | Decisión Go/No-Go | Lista | Persona | **No** | `Go`, `No-Go`, `Más información` (vacío permitido) | Verde / rojo / amarillo. |
| X | Motivo | Lista | Persona | **No** | `_listas` (motivos de Go/No-Go) | Obligatorio si No-Go o Más información. |
| Y | Comentario | Texto libre | Persona | **No** | ≤ 500 | |
| Z | Responsable | Lista | Persona | **No** | Miembros activos | Obligatorio si Go. |
| AA | Verificador | Texto (oculta) | Backend | Sí | — | `row_token`. |

Motivos Go/No-Go: `Buen encaje técnico`, `Monto atractivo`, `Requisito excluyente no cumplible`, `Plazo insuficiente`,
`Garantías o multas desproporcionadas`, `Capacidad operativa insuficiente`, `Riesgo contractual alto`,
`Falta información en bases`, `Otro (ver comentario)`.

### 2.2 Hoja de detalle `<código>`

Bloques verticales con títulos; cada tabla con columnas fijas:

1. **Identificación**: código (link a la ficha), nombre, organismo, estado oficial, fecha de análisis, modelo y versión
   de prompt usados, documentos analizados (nombre, versión, hash corto).
2. **Objeto y alcance**: Campo | Valor | Estado | Documento | Pág./Secc. | Cita | **Valor corregido** (editable) | **Comentario revisor** (editable).
3. **Requisitos excluyentes** y 4. **Requisitos deseables**: N° | Requisito | Documento | Pág./Secc. | Cita | Estado de cita |
   **Cumplimiento** (editable, lista: `Cumple`, `No cumple`, `Pendiente de evidencia`, `Requiere interpretación`) |
   **Comentario** (editable) | Verificador (oculta, = `fingerprint`).
5. **Criterios de evaluación**: Criterio | Ponderación % | Subcriterios | Documento | Pág. | Estado. Fila de total.
6. **Garantías, multas y condiciones de pago**: misma tabla Campo/Valor/Estado/…/Valor corregido.
7. **Documentos y anexos solicitados**: Documento | Obligatorio (Sí/No/No encontrado) | Formato exigido | Fuente.
8. **Fechas del foro y fechas clave**: Tipo | Fecha (hora de Chile) | Texto original | Fuente (API / bases) | Estado.
9. **Riesgos detectados**: Riesgo | Severidad (Alta/Media/Baja) | Fuente.
10. **Datos no encontrados e inconsistencias**: listado automático de campos "No encontrado", "No verificado" y contradicciones con ambos valores y sus fuentes.

Solo son editables "Valor corregido", "Comentario revisor", "Cumplimiento" y "Comentario".

### 2.3 Reglas de reimportación del Excel 2

Las mismas validaciones de archivo y fila del Excel 1 (sección 1.4), más:
- Decisión (actualiza `bids.status` de la postulación existente): `Go` → `aprobada_participar` (registra `bids.go_decision`); `No-Go` → `no_participar`;
  `Más información` → `pendiente_decision`. Go sin Responsable o No-Go sin Motivo → fila rechazada.
- **Correcciones**: cada "Valor corregido" no vacío crea `field_overrides` (vigente); cada "Cumplimiento" crea
  `requirement_reviews` por `fingerprint`. Quedan marcadas como **corrección humana** y un reanálisis no las pisa: si la IA
  luego extrae un valor distinto, la ficha muestra el corregido con nota "La IA ahora indica X".
- Un Verificador de requisito desconocido → fila rechazada (requisito alterado).
- Hoja de detalle faltante o renombrada → se informan sus correcciones como no importadas; la decisión del Resumen sigue
  siendo válida.

### 2.4 Semáforo y recomendación (backend, umbrales configurables en `scoring_profiles.thresholds`)

Umbrales **aprobados como provisionales**; se revisan con las primeras fichas reales y con el conjunto de evaluación.

| Semáforo | Condición (se evalúa en este orden) | Recomendación |
| --- | --- | --- |
| Rojo | ≥ 1 excluyente "No cumple" **o** cierre de ofertas ya pasado **o** días hábiles al cierre < `red_days` (def. 3) | No participar |
| Amarillo | ≥ 1 excluyente pendiente / requiere interpretación **o** algún campo clave (presupuesto, plazo de ejecución, cierre, criterios) No encontrado / No verificado / contradicción **o** días hábiles < `yellow_days` (def. 7) | Revisar |
| Verde | Ninguna de las anteriores | Participar |

Un puntaje alto nunca compensa un excluyente "No cumple" (regla 6.4 del brief).
