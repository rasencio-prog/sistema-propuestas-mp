# 10 · API de Mercado Público — validación con ticket real (`/p2-api`)

Estado: **VALIDADO** (22-11-2026) contra `https://api.mercadopublico.cl` con el ticket real del propietario
(`MP_TICKET`, leído solo desde `.env` vía `python-dotenv`; nunca impreso ni commiteado).
Script usado: `scripts/explore_mp_api.py` (exploratorio, no es código de producción).
Muestras saneadas (ticket eliminado de URLs y cabeceras): `docs/api-samples/*.json`.
Log de la corrida (tiempos, status HTTP, consumo): `docs/api-samples/_run-log.json`.

## 0. Fuentes consultadas

1. Página oficial `https://www.chilecompra.cl/api/` (banner "Última actualización: 19/11/2026"), leída completa.
2. Manual oficial *"Diccionario de Datos - Licitaciones"*
   (`http://www.chilecompra.cl/wp-content/uploads/2026/03/Documentacion-API-Mercado-Publico-Licitaciones.pdf`),
   texto extraído con `pdfplumber` (el PDF no tiene capa de texto accesible por herramientas de renderizado estándar;
   se usó la misma librería que el proyecto ya eligió para producción, ADR-0004).
3. Llamadas reales a `api.mercadopublico.cl` con el ticket del propietario, el 22-11-2026, sobre el listado del
   20-11-2026 (día anterior a la corrida: 1.408 licitaciones) y el detalle de 10 códigos. Nunca se accedió a
   `mercadopublico.cl` (portal) ni se hizo scraping — solo la API.

No se encontró documentación oficial separada para "licitaciones diarias" vs. "detalle por código": es el **mismo
endpoint** (`licitaciones.json`) con distinto parámetro (`fecha` vs. `codigo`); el manual documenta un único
diccionario de campos, pero la respuesta real difiere mucho en riqueza entre ambos usos (ver §2).

## 1. Endpoints y parámetros confirmados

Base: `https://api.mercadopublico.cl/servicios/v1/publico/`. Formatos: `.json` (por defecto si no se indica
extensión), `.xml`, `.jsonp` (con `callback`). El ticket va siempre como parámetro de query `ticket`.

| Uso | Ejemplo de llamada (ticket oculto) | Confirmado |
| --- | --- | --- |
| Listado de licitaciones publicadas/cerradas/etc. en una fecha | `GET licitaciones.json?fecha=20112026&ticket=<TICKET>` | Sí, probado (1.408 resultados) |
| Detalle de una licitación por código | `GET licitaciones.json?codigo=1057389-73-LP26&ticket=<TICKET>` | Sí, probado (10 códigos) |
| Listado filtrado por estado (y opcionalmente fecha) | `GET licitaciones.json?fecha=20112026&estado=adjudicada&ticket=<TICKET>` | Documentado en la página oficial; **no probado** en esta corrida (no era necesario para la muestra) |
| "Activas" (publicadas a la fecha de hoy) | `GET licitaciones.json?estado=activas&ticket=<TICKET>` | Documentado; no probado |
| Listado por organismo o proveedor | `GET licitaciones.json?fecha=...&CodigoOrganismo=<cod>&ticket=<TICKET>` / `...&CodigoProveedor=<cod>&ticket=<TICKET>` | Documentado; no probado |
| Buscar código de proveedor por RUT | `GET Empresas/BuscarProveedor?rutempresaproveedor=<RUT>&ticket=<TICKET>` | Documentado; no probado (no se necesita para MVP-1) |
| Buscar organismos | `GET Empresas/BuscarComprador?ticket=<TICKET>` | Documentado; no probado |
| Órdenes de compra | `GET ordenesdecompra.json?codigo=...&ticket=<TICKET>` (mismos parámetros que licitaciones) | Documentado; **fuera de alcance** (el sistema solo trabaja con licitaciones) |

**No existe ningún parámetro para filtrar por rubro/categoría.** Esto tiene impacto de diseño, ver §6.

**Límites de uso** (página oficial, no medido empíricamente más allá de lo que se describe en §5):
límite duro de **10.000 solicitudes/día por ticket**, no configurable; monitoreo por IP; se recomienda concentrar
descargas masivas entre 22:00 y 07:00; uso abusivo puede derivar en suspensión temporal o bloqueo permanente.
Confirma la decisión ya tomada en `docs/01` de limitar a 8.000/día propios y domiciliar las corridas pesadas en
horario nocturno (ADR-0007/ADR-0008).

## 2. Listado por fecha vs. detalle por código: NO traen los mismos campos

Hallazgo central de esta validación, con impacto directo en el diseño del radar (`docs/02` §4):

- **Listado por `fecha`**: cada licitación trae **solo 4 campos**, siempre los mismos en los 1.408 elementos
  revisados: `CodigoExterno`, `Nombre`, `CodigoEstado`, `FechaCierre`. Nada de comprador, monto, moneda, tipo,
  rubro/ítems ni el resto del diccionario del manual.
- **Detalle por `codigo`**: trae el objeto completo documentado en el manual (≈ 85 campos de licitación + ítems),
  incluyendo `Comprador`, `Fechas`, `Items`, `Adjudicacion`, etc.

Es decir: **el rubro (categoría UNSPSC), el organismo, la unidad compradora, el monto y la moneda NO están
disponibles sin pedir el detalle**, y la API no ofrece ninguna forma de filtrar el listado diario por rubro antes de
pedir el detalle. Un día cualquiera trae cientos de candidatas "Publicada" sin esa información (487 de 1.408 en la
muestra del 20-11-2026); solo se puede pre-filtrar por `Nombre` (palabras clave) y `FechaCierre`/`CodigoEstado` antes
de gastar cuota en el detalle.

### 2.1 Campos del listado (`Listado/Licitacion`)

| Campo | Tipo observado | Ejemplo | Nulo/vacío |
| --- | --- | --- | --- |
| `CodigoExterno` | string | `"1057384-176-L126"` | Nunca, en 1.408 casos |
| `Nombre` | string | `"Servicio de transporte de usuarios de caletas a Hopital Tocopilla."` | Nunca |
| `CodigoEstado` | int | `6` | Nunca |
| `FechaCierre` | string datetime, sin zona | `"2026-11-20T20:00:00"` | No observado nulo en el listado (sí puede venir `null` si la licitación no tiene fecha de cierre definida, no se dio el caso en la muestra) |

Envoltura de la respuesta (ambos usos, listado y detalle): `Cantidad` (int, cantidad de licitaciones devueltas),
`FechaCreacion` (datetime de la consulta), `Version` (string, ej. `"v1"`), `Listado` (array).

### 2.2 Campos del detalle (`Listado/Licitacion`, con `codigo`) — los relevantes para Excel 1 y Excel 2

Tabla reducida a los campos que importan al diseño (la lista completa de 97 campos del manual está en
`docs/api-samples/` como evidencia bruta y no se repite aquí; todos los nombres citados abajo están verificados
contra las 10 muestras reales, no copiados a ciegas del manual).

| Campo | Tipo observado | Ejemplo | Nulo/vacío (de 10 muestras) |
| --- | --- | --- | --- |
| `CodigoExterno` | string | `"1057389-73-LP26"` | Nunca |
| `Nombre` | string | `"AYUDAS TÉCNICAS GES"` | Nunca |
| `Descripcion` | string | *(objeto de la licitación)* | Nunca vacío en la muestra, pero el manual permite `nvarchar max` vacío |
| `CodigoEstado` / `Estado` | int / string | `5` / `"Publicada"` | Nunca; valores observados: 5 Publicada (487/1.408 del día), 6 Cerrada (419), 7 Desierta (86), 8 Adjudicada (386). **Dos códigos del listado no están en la tabla oficial de la página: 15 (29 casos) y 16 (1 caso)** — no se investigó su significado en esta corrida; no bloqueante, pero el adaptador no debe asumir que la lista de 6 estados documentados es exhaustiva: debe guardar también el texto (`Estado`) tal cual llega. |
| `FechaCierre` (**raíz**, fuera de `Fechas`) | — | `null` | **10/10 veces `null` en el detalle.** Es un campo redundante del diccionario que, al consultar por `codigo`, viene siempre vacío. **No usar.** |
| `Fechas.FechaCierre` | string datetime sin zona | `"2026-12-10T16:00:00"` | Nunca nulo en la muestra — **este es el campo real de cierre de ofertas** |
| `Fechas.FechaPublicacion` | datetime sin zona | `"2026-11-20T16:03:00"` | Nunca |
| `Fechas.FechaFinal` (cierre del foro de preguntas) | datetime sin zona | `"2026-11-13T20:00:00"` | Nunca |
| `Fechas.FechaPubRespuestas` | datetime sin zona | `"2026-11-17T20:00:00"` | Nunca |
| `Fechas.FechaActoAperturaTecnica` | datetime sin zona | `"2026-11-23T15:00:00"` | Nunca |
| `Fechas.FechaActoAperturaEconomica` | datetime sin zona | `"2026-11-23T15:00:00"` | Nunca |
| `Fechas.FechaAdjudicacion` / `FechaEstimadaAdjudicacion` | datetime sin zona | `"2026-11-25T18:00:00"` | Nunca |
| `Fechas.FechaSoporteFisico`, `FechaTiempoEvaluacion`, `FechaEstimadaFirma` | datetime sin zona | — | Vacíos 9/10 veces. **`FechaTiempoEvaluacion` tiene un valor centinela observado `"1900-01-04T00:00:00"` en una muestra** (no es una fecha real; es el equivalente a "no definida" de un `datetime` de .NET). El parser debe tratar cualquier fecha ≤ 1950 de estos campos como `parse_status='missing'`, nunca como fecha válida. |
| `Fechas.FechasUsuario`, `FechaVisitaTerreno`, `FechaEntregaAntecedentes` | — | — | Vacíos 10/10 veces en la muestra |
| `Comprador.CodigoOrganismo` / `NombreOrganismo` | string / string | `"7288"` / `"SERVICIO SALUD ARAUCANIA NORTE HOSPITAL VICTORIA"` | Nunca |
| `Comprador.CodigoUnidad` / `NombreUnidad` | string / string | `"1057389"` / `"Bienes y Servicios"` | Nunca. **Confirma que "Unidad compradora" solo viene en el detalle, nunca en el listado.** |
| `Comprador.RegionUnidad` / `ComunaUnidad` | string libre (no codificado) | `"Región de la Araucanía "` / `"Victoria"` | Nunca, salvo `ComunaUnidad` vacío en 1/10 (licitación sin comuna informada) |
| `Tipo` | string, código fijo | `"LP"` | Nunca. Tabla completa en §3. |
| `CodigoTipo` | int | `1` (Pública) / `2` (Privada) | Nunca |
| `Moneda` | string, código fijo | `"CLP"` (también visto `"USD"` en la muestra) | Nunca — **siempre viene, incluso cuando el monto no es visible** |
| `VisibilidadMonto` | int (0/1) | `0` o `1` | Nunca |
| `MontoEstimado` | float o `null` | `18614310.0` | **Siempre `null` cuando `VisibilidadMonto=0` (5/10 casos), siempre con valor cuando `VisibilidadMonto=1` (5/10 casos) — regla 1:1 confirmada en la muestra, sin excepciones.** |
| `Estimacion` | int, código fijo (tabla §3) | `1` (Presupuesto Disponible) | Nunca |
| `Items.Cantidad` / `Items.Listado[]` | int / array | — | Presente en las 10 muestras |
| `Items.Listado[].CodigoCategoria` | string (UNSPSC, 8 dígitos) | `"43231500"` | Nunca, cuando hay ítems. **Es el único lugar donde aparece el rubro — y solo existe en el detalle.** |
| `Items.Listado[].Categoria` | string (ruta jerárquica UNSPSC) | `"Componentes para la fabricación de software / Software de aplicaciones de gestión documental"` | Nunca |
| `Adjudicacion` | objeto o `null` | `null` salvo `CodigoEstado=8` (Adjudicada) | `null` 8/10; con valor en las 2 muestras "Adjudicada" |
| `Adjudicacion.UrlActa` | string, **URL real a mercadopublico.cl** | `"http://www.mercadopublico.cl/Procurement/Modules/RFB/StepsProcessAward/PreviewAwardAct.aspx?qs=..."` | Ver §5 — dato que entrega la propia API, no scraping |

**Formato y zona horaria de todas las fechas**: string ISO-like `AAAA-MM-DDTHH:MM:SS[.fffffff]`, **sin sufijo de zona
ni offset** (ni `Z` ni `+00:00`). Confirma la suposición de `docs/07` §1: la API entrega hora local de Chile
continental sin marca de zona; el texto original se guarda tal cual y se interpreta con la regla ya documentada
(`fold=0`, primera ocurrencia en horas ambiguas).

**Inconsistencia de tipos JSON confirmada:** varios campos que el manual describe como `int`/`bit` llegan en la
práctica como **string**, no como número: `TipoConvocatoria`, `EstadoEtapas`, `TomaRazon`, `Contrato`, `Obras`,
`TipoPago`, `UnidadTiempo`, `SubContratacion`, `TiempoDuracionContrato`, `UnidadTiempoContratoLicitacion`,
`ValorTiempoRenovacion`, `DiasCierreLicitacion`. Otros sí llegan como número: `CodigoEstado`, `CodigoTipo`, `Etapas`,
`EstadoPublicidadOfertas`, `Informada`, `VisibilidadMonto`, `Estimacion`, `Modalidad`, `UnidadTiempoDuracionContrato`,
`ExtensionPlazo`, `EsBaseTipo`, `EsRenovable`, `CantidadReclamos`. El adaptador (modelos Pydantic) debe aceptar y
normalizar ambas formas; no se puede asumir el tipo del manual.

### 2.3 El parámetro `fecha` no filtra estrictamente por fecha de publicación

Hallazgo adicional (22-11-2026, al revisar la muestra para la estrategia del radar, ADR-0010): de las 1.408
licitaciones del listado `fecha=20112026`, solo el 38 % (535) tiene `FechaCierre` igual a esa fecha, y de las 10
muestras de detalle, varias tienen `Fechas.FechaPublicacion` en un día distinto al consultado — incluida una
licitación **Adjudicada** cuya publicación fue el 30-09-2026 y cuyo cierre fue el 13-10-2026, ninguno el 20-11-2026,
pero cuya `Adjudicacion.Fecha` **sí** es 20-11-2026. Lectura: `fecha` trae licitaciones cuyo **estado o fecha
relevante cambió ese día** (publicación, cierre, adjudicación, etc.), no solo las publicadas ese día — pese a que
la página oficial lo describe como "licitaciones publicadas ese día". Esto no está documentado explícitamente por
ChileCompra; es una observación empírica, no una garantía contractual de la API.

Impacto en el diseño: "nueva" se define como *código no visto antes en `opportunities`*, nunca como "aparece en el
listado de hoy" (ver ADR-0010). Y como el listado ya trae `CodigoEstado` y `FechaCierre` sin costo de cuota, alcanza
con comparar esos dos campos contra lo guardado para decidir si una licitación **conocida** necesita un nuevo
detalle, sin tener que re-pedirlo siempre.

### 2.4 Otras inconsistencias observadas (además de los tipos JSON de §2.2)

- `TipoPago`: la muestra trajo el valor `"-1"`, que **no está** en la tabla 3.4 del manual (valores documentados
  1-10). Guardar el valor crudo; no mapear a un texto si el código no está en la tabla — mostrar "código no
  documentado" en vez de inventar una descripción.
- `EmailResponsableContrato`, `FonoResponsableContrato`, `EmailResponsablePago`: en las 10 muestras siempre vienen
  como **string vacío** `""` (nunca `null`). Distinto de `TipoDuracionContrato` y `PeriodoTiempoRenovacion`, que
  vienen siempre `null` (JSON null). El adaptador debe tratar ambos (`""` y `null`) como "no informado".

## 3. Tablas de códigos fijas (del manual oficial, no inventadas)

**Tipo de licitación** (`Tipo`): `L1` Pública <100 UTM · `LE` Pública ≥100 y <1.000 UTM · `LP` Pública ≥1.000 y
<2.000 UTM · `LQ` Pública ≥2.000 y <5.000 UTM · `LR` Pública ≥5.000 UTM · `LS` Pública servicios personales
especializados · `E2` Privada <100 UTM · `CO` Privada ≥100 y <1.000 UTM · `B2` Privada ≥1.000 y <2.000 UTM · `H2`
Privada ≥2.000 y <5.000 UTM · `I2` Privada >5.000 UTM. Confirmado en la muestra: `L1`, `LP`, `LE` observados en
licitaciones reales.

**Moneda**: `CLP` Peso chileno · `CLF` Unidad de Fomento · `USD` Dólar · `UTM` Unidad Tributaria Mensual · `EUR`
Euro. Observados en la muestra: `CLP`, `USD`.

**Estado (`CodigoEstado`)**: 5 Publicada · 6 Cerrada · 7 Desierta · 8 Adjudicada · 18 Revocada · 19 Suspendida
(según la página oficial). En la muestra real aparecieron además **15 y 16, sin documentar** — tratar como
"desconocido, usar el texto de `Estado`" en el `CHECK` de `opportunities.official_status_code`, no como lista cerrada.

**`Estimacion`** (tipo de monto): 1 Presupuesto Disponible · 2 Precio Referencial · 3 Monto no es posible de estimar.

## 4. Muestras guardadas

| Archivo | Contenido |
| --- | --- |
| `docs/api-samples/listado_2026-11-20.json` | Listado completo del 20-11-2026 (1.408 licitaciones, saneado) |
| `docs/api-samples/detalle_<código>.json` (5) | Primeros 5 códigos del listado (rubros variados: transporte, ayudas técnicas, alimentos, servicios profesionales, maquinaria) |
| `docs/api-samples/detalle_ti_<código>.json` (5) | 5 códigos elegidos por palabra clave en `Nombre` (software, licencias, servidores, plataforma) y **confirmados** de rubro TI (`CodigoCategoria` con prefijo `43`, segmento UNSPSC "Information Technology") tras ver el detalle — la API no permite filtrar por rubro antes de esto |
| `docs/api-samples/_run-log.json` | 12 llamadas: status HTTP, duración, URL saneada |

## 5. ¿Entrega la API alguna URL de la ficha o de adjuntos?

**No**, salvo un caso puntual: cuando `CodigoEstado=8` (Adjudicada), el detalle trae `Adjudicacion.UrlActa`, un
enlace real a `mercadopublico.cl` con el acta de adjudicación (confirmado en 2 de las 10 muestras). Es un dato que
devuelve la propia API — no es scraping ni automatización del portal — pero no reemplaza el link a la ficha general
(solo existe para licitaciones ya adjudicadas) y el sistema sigue sin acceder a ese link de forma automática; a lo
sumo se podría mostrar como texto/hipervínculo en la ficha de Excel 2 (nota para `/p8`, fuera de alcance de MVP-1).
Ningún adjunto (bases, anexos) tiene URL en la respuesta.

## 6. Formato de la URL de la ficha pública (construida, sin acceder al portal)

Patrón confirmado por el propietario (sección 4 del brief) y usado tal cual, sin automatizar nada sobre
`mercadopublico.cl`:

```
https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=<código>
```

Dos links para que el propietario confirme a mano (de las muestras reales de esta corrida):

- `https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=1057389-73-LP26`
  (Publicada, "AYUDAS TÉCNICAS GES")
- `https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=1111089-20-LE26`
  (Adjudicada, "LICENCIAS DE SOFTWARE Y COMPLEMENTOS TECNOLÓGICOS")

## 7. Errores observados, tiempos de respuesta y consumo de cuota

- **Consumo total de esta validación: 12 solicitudes** (1 listado + 11 detalles, incluido 1 reintento), sobre un
  límite diario de 10.000 — impacto despreciable.
- **Tiempos**: listado de 1.408 licitaciones ≈ 440 ms; detalles individuales entre 60 ms y 370 ms.
- **1 error 429 ("Too Many Requests")** en la 4ª llamada de detalle consecutiva, pese a respetar 1 solicitud/segundo
  (`time.sleep(1)` entre llamadas). El reintento con 2 segundos de espera tuvo éxito de inmediato. Lectura para el
  diseño: el ritmo real tolerado puede ser más estricto que 1 req/s en rachas cortas, o hay variabilidad de servidor;
  confirma que el backoff ante 429/5xx ya diseñado en `docs/02` §4 (reintentos con backoff exponencial y jitter, la
  candidata queda `detail_pending` si se agotan los intentos) es necesario y correcto, y sugiere no asumir que 1
  req/s garantiza cero 429 — el backoff debe tratarlo como señal esperable, no excepcional.
- Sin errores 5xx en esta corrida. No se probaron escenarios de ticket inválido o vencido (no corresponde arriesgar
  el ticket real del propietario para eso).

## 8. Impacto en el diseño — ajustes concretos

### 8.1 `docs/02-arquitectura.md`

- §4, diagrama de secuencia: el paso "listado diario (endpoint A VALIDAR EN /p2-api)" es
  `GET licitaciones.json?fecha=ddmmaaaa&ticket=...`. **Confirmado y actualizado en el documento.**
- El mismo diagrama ya asume correctamente que el detalle es necesario para "candidatas que pasan pre-filtro": esta
  validación confirma que es **obligatorio**, porque el listado no trae rubro, organismo ni monto. El pre-filtro de
  cuota (antes del detalle) solo puede usar `Nombre`, `CodigoEstado` y `FechaCierre` — nunca categoría UNSPSC.

### 8.2 `docs/03-modelo-datos.md`

- **Cerrado** (línea 25): el mapeo API → canónico queda documentado en este archivo (§2 y §3), ya no es
  "A VALIDAR EN /p2-api" en general.
- `opportunities.opportunity_type_code`: usar los códigos confirmados en §3 (`L1, LE, LP, LQ, LR, E2, CO, B2, H2,
  I2, LS`). Ya no "A VALIDAR".
- `buyers.organism_code` = `Comprador.CodigoOrganismo` (string numérico, ej. `"7288"`); `buyers.unit_code` =
  `Comprador.CodigoUnidad` (string numérico, ej. `"1057389"`). Confirmados, ya no "A VALIDAR".
- `opportunity_items.category_code` (rubro) = `Items.Listado[].CodigoCategoria` (UNSPSC, 8 dígitos). Confirmado que
  **solo existe en el detalle**, nunca en el listado — impacto ya anotado en §8.1.
- `opportunity_dates.date_type`, lista final confirmada (ya no "A VALIDAR"):
  `publication` (`Fechas.FechaPublicacion`), `questions_close` (`Fechas.FechaFinal`, cierre del foro de preguntas),
  `answers_publication` (`Fechas.FechaPubRespuestas`), `offers_close` (`Fechas.FechaCierre` — **no** el campo raíz
  `FechaCierre`, que viene vacío en el detalle), `technical_opening` (`Fechas.FechaActoAperturaTecnica`),
  `economic_opening` (`Fechas.FechaActoAperturaEconomica`), `award_estimated` (`Fechas.FechaEstimadaAdjudicacion`),
  `award_actual` (`Fechas.FechaAdjudicacion`, nuevo tipo, no estaba listado). Opcionales, con `parse_status`
  normalmente `missing` (nunca inventar valor si vienen vacíos o con fecha centinela ≤1950):
  `support_physical`, `evaluation_time`, `estimated_signature`, `site_visit`, `background_delivery`, `user_dates`.
- Nota nueva de robustez (agregar como punto 7 en "Decisiones de modelado" o similar): varios enteros/booleanos de
  la API llegan como string JSON (ver tabla de §2.2); el adaptador coacciona el tipo, nunca falla por eso.
- `api_quota_usage.quota_date` (línea 116) y el punto 6 de "Decisiones de modelado" (línea 522): **sigue sin
  confirmarse** la hora exacta en que ChileCompra reinicia el contador de 10.000/día — la página oficial solo
  informa el límite, no la hora de corte. No bloqueante: se mantiene el supuesto de día calendario de Chile, y el
  límite propio (8.000) da margen de sobra. Queda como riesgo documentado, no como "A VALIDAR" sin resolver.

### 8.3 `docs/05-backlog.md`

- E0-1 a E0-4: cumplidos por este documento, `docs/api-samples/` y los 2 links de §6.
- E0-5: cerrado — todos los "A VALIDAR EN /p2-api" de `docs/02`, `docs/03`, `docs/06` y `docs/07` quedan resueltos o,
  cuando no fue posible validarlos con esta muestra (hora de corte de cuota; fechas de una licitación de Magallanes),
  explícitamente marcados como riesgo pendiente en vez de inventados.

### 8.4 `docs/06-excel-especificacion.md`

- Línea 24 (origen "API"): el mapeo campo-a-campo exacto es el de §2.2 de este documento.
- Columna E "Unidad compradora": **confirmado que solo viene en el detalle** (`Comprador.NombreUnidad`), nunca en
  el listado por fecha. Cualquier oportunidad que llegue al Excel 1 ya tiene que haber pasado por el detalle (lo que
  ya asume el diseño actual del radar).
- Columna G "Tipo de licitación": el **código** viene de la API (`Tipo`, ej. `"LE"`); el **texto oficial** entre
  paréntesis que pide la especificación ("Licitación Pública igual o superior a 100 UTM...") **no viene en la
  respuesta** — se arma con la tabla fija y publicada en §3 de este documento (no es un dato inventado: es la tabla
  3.1 del manual oficial de ChileCompra), igual que ya se hace con feriados (`holidays`) u otras tablas estáticas.
- Columna H "Monto estimado" y su nota "Moneda A VALIDAR": **confirmado** — `Moneda` siempre viene (incluso cuando
  el monto no es visible), y la regla `VisibilidadMonto=0 → MontoEstimado=null` se cumplió sin excepción en las 10
  muestras. Cuando es `null`, la celda debe mostrar "No visible" (ya especificado), nunca `0` ni inventar un monto.
- Columna J "Fecha de cierre": usar **`Fechas.FechaCierre`**, nunca el campo raíz del detalle (que viene vacío). El
  texto llega sin zona horaria, tal como ya asumía `docs/07`; se guarda el texto original tal cual junto con la
  conversión a UTC.
- Columna Q "Link a la ficha": sin cambios de fondo — se sigue construyendo con el patrón de §6, el sistema no
  accede al portal. Nota adicional (no afecta Excel 1): para licitaciones Adjudicadas existe además
  `Adjudicacion.UrlActa`, un link real de la propia API al acta de adjudicación; queda como posible campo informativo
  para la ficha de Excel 2 en `/p8`, no para Excel 1.

### 8.5 `docs/07-plan-pruebas.md`

- Línea 29 ("fechas con y sin zona... A VALIDAR si la API entrega hora local sin zona"): **confirmado** — todas las
  fechas de la API llegan sin zona (hora local de Chile continental). Se aplica la regla ya documentada.
- Línea 35 (fechas de una licitación de Magallanes): **sigue sin validar.** Ninguna de las 10 muestras tomadas
  corresponde a una unidad compradora en Magallanes (se vieron Metropolitana, Araucanía, Biobío, Los Lagos). No se
  puede confirmar sin inventar: se mantiene como pendiente, con una forma concreta de cerrarlo más adelante (no
  bloqueante para MVP-1): cuando el radar real detecte una licitación cuya `Comprador.RegionUnidad` sea Magallanes,
  verificar en `/p4` si sus horas (`Fechas.*`) corresponden a hora de Punta Arenas o de Santiago antes de asumir
  `America/Santiago` para todo el país.
- Agregar un nuevo caso de prueba de robustez de fechas: **fecha centinela de .NET** (`"1900-01-04T00:00:00"` u
  otra fecha ≤ 1950) en campos opcionales de `Fechas.*` debe producir `parse_status='missing'`, no una fecha real
  (hallazgo nuevo de esta validación, no estaba contemplado).

## 9. Catálogo completo del detalle — campos pedidos por el propietario (22-11-2026)

Confirmado contra las 10 muestras reales en `docs/api-samples/detalle_*.json` (no copiado a ciegas del manual).
"Vacío" cuenta `null`, string vacío `""` y los casos de §2.4. Todos estos campos **sí existen** en la respuesta de
la API; ninguno está "no disponible" — lo que varía es qué tan seguido vienen vacíos.

| Grupo | Campo API | Tipo observado | Vacío (de 10) | Ejemplo |
| --- | --- | --- | --- | --- |
| Identificación | `CodigoExterno` | string | 0 | `"1057389-73-LP26"` |
| | `Nombre` | string | 0 | `"AYUDAS TÉCNICAS GES"` |
| | `Tipo` (código) / tabla §3 (texto) | string | 0 | `"LP"` |
| | `CodigoTipo` | int (1 Pública/2 Privada) | 0 | `1` |
| | `TipoConvocatoria` | string ("0"/"1") | 0 | `"1"` |
| | `CodigoEstado` / `Estado` | int / string | 0 | `5` / `"Publicada"` |
| Descripción | `Descripcion` | string (hasta `nvarchar max`) | 0 | — |
| Ítems | `Items.Cantidad` | int | 0 | `24` |
| | `Items.Listado[].Correlativo` | int | 0 | `1` |
| | `Items.Listado[].CodigoProducto` (ONU/UNSPSC, 8 díg.) | int | 0 | `78111803` |
| | `Items.Listado[].CodigoCategoria` (rubro, UNSPSC) | string | 0 | `"78111800"` |
| | `Items.Listado[].Categoria` (ruta jerárquica) | string | 0 | `"Servicios de transporte.../Transporte de pasajeros"` |
| | `Items.Listado[].NombreProducto` | string | 0 | `"Servicios de autobuses contratados"` |
| | `Items.Listado[].Descripcion` | string | 0 | — |
| | `Items.Listado[].UnidadMedida` | string | 0 | `"Global"`, `"Unidad"` |
| | `Items.Listado[].Cantidad` | float | 0 | `1.0` |
| Comprador | `Comprador.CodigoOrganismo` / `NombreOrganismo` | string | 0 | `"7288"` / nombre completo |
| | `Comprador.CodigoUnidad` / `NombreUnidad` | string | 0 | `"1057389"` / `"Bienes y Servicios"` |
| | `Comprador.RutUnidad` | string | 0 | `"61.602.229-6"` |
| | `Comprador.RegionUnidad` | string libre | 0 | `"Región de la Araucanía "` (con espacio final observado) |
| | `Comprador.ComunaUnidad` | string | 1/10 | `"Victoria"` |
| Monto | `MontoEstimado` | float \| null | 5/10 (ligado 1:1 a `VisibilidadMonto=0`) | `18614310.0` |
| | `VisibilidadMonto` | int (0/1) | 0 | `1` |
| | `Moneda` | string (tabla §3) | 0 | `"CLP"`, `"USD"` |
| | `Estimacion` (tabla §3) | int | 0 | `1` |
| | `FuenteFinanciamiento` | string | 3/10 | `"22.04.004.006 - 22.04.005"` |
| | `JustificacionMontoEstimado` | string | 5/10 | — |
| Fechas (cada una → `opportunity_dates`, su `date_type`, UTC y texto original) | `Fechas.FechaPublicacion` → `publication` | datetime sin zona | 0 | `"2026-11-20T16:03:00"` |
| | `Fechas.FechaFinal` (cierre del foro de preguntas) → `questions_close` | datetime sin zona | 0 | — |
| | `Fechas.FechaPubRespuestas` → `answers_publication` | datetime sin zona | 0 | — |
| | `Fechas.FechaCierre` (**no** la raíz, ver §2) → `offers_close` | datetime sin zona | 0 | — |
| | `Fechas.FechaActoAperturaTecnica` → `technical_opening` | datetime sin zona | 0 | — |
| | `Fechas.FechaActoAperturaEconomica` → `economic_opening` | datetime sin zona | 0 | — |
| | `Fechas.FechaEstimadaAdjudicacion` → `award_estimated` | datetime sin zona | 0 | — |
| | `Fechas.FechaAdjudicacion` → `award_actual` | datetime sin zona | 0 (viene igual a la estimada si aún no hay adjudicación real) | — |
| | `Fechas.FechaVisitaTerreno` → `site_visit` | datetime sin zona \| null | 10/10 | — (nunca se vio con valor) |
| Contrato | `TiempoDuracionContrato` / `UnidadTiempoDuracionContrato` (tabla §3.6) | string / int | 0 | `"24"` / `4` (Meses) |
| | `TipoDuracionContrato` | string \| **siempre null** | 10/10 | — |
| | `EsRenovable` | int (0/1) | 0 | `0` |
| | `ValorTiempoRenovacion` / `PeriodoTiempoRenovacion` | string / **siempre null** | 0 / 10 | `"0"` / — |
| | `SubContratacion` | string ("0"/"1") | 0 | `"0"` |
| | `Contrato` (1 requiere suscripción, 2 formaliza con OC; solo visible en tipo LE) | string | 0 | `"0"` |
| | `EsBaseTipo` (licitación tipo) | int (0/1) | 0 | `0` |
| Pago y responsables | `Modalidad` (tabla §3.4) | int | 0 | `1` (Pago a 30 días) |
| | `TipoPago` | string, **valor `"-1"` no documentado observado** (§2.4) | 0 | `"-1"`, `"1"` |
| | `NombreResponsableContrato` / `EmailResponsableContrato` / `FonoResponsableContrato` | string / string vacío / string vacío | 2/10 (nombre) · 10/10 (correo y fono, siempre `""`) | `"Carmen Sanchez Iturra"` |
| | `NombreResponsablePago` / `EmailResponsablePago` | string / string vacío | 2/10 · 10/10 | `"Angelica Escalona Pino"` |
| Otros | `CantidadReclamos` (del organismo, no de esta licitación en particular) | int | 0 | `1263` |
| | `EsBaseTipo` | int | 0 | *(duplicado con Contrato, ver arriba)* |
| Adjudicación (objeto completo `null` salvo `CodigoEstado=8`) | `Adjudicacion.Tipo` (tabla §3.7) | int \| null | 8/10 | `2` (Resolución) |
| | `Adjudicacion.Fecha` | datetime sin zona \| null | 8/10 | `"2026-11-20T00:00:00"` |
| | `Adjudicacion.Numero` | string \| null | 8/10 | `"9723"` |
| | `Adjudicacion.NumeroOferentes` | int \| null | 8/10 | `4` |
| | `Adjudicacion.UrlActa` | string (URL real a mercadopublico.cl) \| null | 8/10 | ver §5 |

## 10. API OCDS de ChileCompra (`api.mercadopublico.cl/APISOCDS`) — exploración punto E

Endpoint probado: `GET https://api.mercadopublico.cl/APISOCDS/OCDS/tender/{id}` y `.../OCDS/record/{id}`
(sin ticket — no pidió autenticación en ninguna prueba). Resultado guardado en `docs/api-samples/ocds_check.json`
(función `check_ocds()` en `scripts/explore_mp_api.py`, usable con `--check-ocds`).

- **Las dos rutas existen** en la aplicación (devuelven `HTTP 200` con cuerpo JSON `{"status":404,"detail":"No se
  encontraron resultados."}` para un ID que no matchea), a diferencia de rutas inventadas (`/releases/`,
  `/compiledRelease/`), que devuelven un 404 de IIS sin cuerpo JSON — confirma que la API existe y estas son sus
  rutas reales.
- **Ninguno de los 3 códigos ya muestreados** (`1057389-73-LP26`, `1057390-75-LE26`, `1111089-20-LE26`, dos
  Publicada y una Adjudicada) devolvió resultados, ni con el código tal cual, ni en minúsculas, ni con el prefijo de
  OCID de Chile (`ocds-70d2nz-`, según `data.open-contracting.org`). No se pudo determinar el formato de ID real que
  espera `/OCDS/tender/{id}` sin descargar el set masivo de datos abiertos (archivos `.jsonl.gz` de cientos de MB en
  `datos-abiertos.chilecompra.cl`), lo que excede el alcance de una validación con ritmo prudente y no es,
  estrictamente, "la API" sino un volcado masivo.
- La publicación OCDS de Chile en Open Contracting Data SÍ reporta **2.788.205 documentos** en su conjunto de
  datos agregado, lo que sugiere que el campo `documents` (con `url`, `title`, `documentType` según el estándar
  OCDS) existe en el dato subyacente — pero no se pudo confirmar su forma exacta llamando a la API en vivo con los
  códigos disponibles.
- Cobertura declarada (fuente: `data.open-contracting.org`): licitaciones desde 2009, actualización "en tiempo
  real" según el publicador original, aunque la propia fuente advierte que la API "puede tardar más de un mes" en
  descargar todo el histórico — es decir, lenta para uso masivo, aceptable para consultas puntuales.

**Conclusión para el diseño:** no se pudo confirmar en esta validación que la API OCDS entregue documentos
descargables para una licitación conocida por su `CodigoExterno`. **No se recomienda** construir ninguna
funcionalidad de MVP-1/MVP-2 sobre esta API hasta no resolver el formato real de ID (quedaría para una validación
aparte, bajo demanda, si en el futuro se quisiera automatizar algo con documentos — lo que además chocaría con la
regla de "los adjuntos los baja y sube una persona" de `CLAUDE.md`, así que no es prioritario). La bandeja de carga
manual (`docs/01` §2.3) sigue siendo el único camino para los adjuntos en MVP-2.

**Dos URLs de documento para abrir a mano:** no se obtuvieron — la API no devolvió ningún documento con los
códigos probados. No hay URLs que dar para esta tarea; se documenta la ausencia en vez de inventarlas.

## 11. Estrategia de detalle del radar, ritmo y cuota (ADR-0010) y resumen IA (ADR-0011)

Las decisiones del propietario sobre cuándo pedir el detalle de una licitación, el ritmo de solicitudes (1 cada 2
segundos por defecto, con backoff exponencial ante 429/5xx), la ventana de corrida (01:00–05:00 hora de Chile) y la
estimación de duración de una corrida diaria (≈18 minutos con el volumen observado) quedan documentadas en
`docs/decisions/ADR-0010-radar-detalle-toda-publicada.md`, para no duplicar el mismo contenido en dos archivos. La
columna "Resumen IA" del Excel 1 (modelo, caché, presupuesto) está en
`docs/decisions/ADR-0011-resumen-ia-excel1.md`.

## 12. Lo que queda genuinamente sin validar (no inventado, declarado)

- Hora exacta de reinicio de la cuota diaria de 10.000 solicitudes (§8.2).
- Comportamiento de fechas en una licitación de la región de Magallanes o Isla de Pascua (§8.5).
- Endpoints no probados por no ser necesarios para MVP-1: filtro por estado/organismo/proveedor en el listado,
  búsqueda de proveedores/organismos, órdenes de compra (todos documentados en la página oficial, solo falta
  probarlos si en el futuro se necesitan).
- Significado de los códigos de estado `15` y `16` observados en la muestra real pero no documentados en la página
  oficial (§3).
- Formato real del identificador que espera la API OCDS (`/APISOCDS/OCDS/tender/{id}` y `.../record/{id}`) y si esa
  API entrega documentos para una licitación dada: las rutas existen, pero ningún código probado (en formato normal,
  minúscula o con prefijo OCID) devolvió resultados (§10). No bloqueante: ninguna historia de MVP-1/MVP-2 depende de
  esta API.
- Significado exacto de `TipoPago="-1"`, observado en una muestra y no documentado en la tabla 3.4 del manual (§2.4).
