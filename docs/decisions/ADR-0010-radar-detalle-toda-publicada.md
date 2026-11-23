# ADR-0010 · El radar pide el detalle de toda licitación nueva en estado Publicada

- Estado: Aceptada (decisión del propietario, reemplaza el prefiltro por palabras clave antes del detalle)
- Fecha: 22-11-2026

## Contexto

`/p2-api` confirmó (`docs/10-api-validada.md` §2) que el listado diario (`licitaciones.json?fecha=...`) trae **solo
4 campos** por licitación: `CodigoExterno`, `Nombre`, `CodigoEstado`, `FechaCierre`. El rubro (UNSPSC), el
organismo, la unidad compradora y el monto **no existen sin pedir el detalle por código**, y la API no tiene ningún
parámetro para filtrar el listado por rubro. El diseño original de `docs/02` (§4) asumía un "pre-filtro barato"
antes de pedir detalle; en la práctica ese pre-filtro solo podría usar el `Nombre` (palabras clave), lo que
descartaría candidatas válidas cuyo título no menciona términos TI explícitos pero cuyos ítems sí son de rubro TI
(se observó esto en la propia muestra: de 5 códigos elegidos solo por orden de aparición, ninguno era TI; hubo que
buscar por palabra clave en el nombre y confirmar después con el detalle).

También se confirmó que el parámetro `fecha` no filtra estrictamente por fecha de publicación: trae licitaciones
cuyo estado o estampa de tiempo relevante cambió ese día (nuevas publicaciones, cierres, adjudicaciones, etc.). Por
eso "nueva" se define como *código no visto antes en `opportunities`*, no como "publicada hoy" según la API.

## Decisión

1. El radar pide el **detalle completo** de **toda** licitación del listado diario cuyo `CodigoExterno` sea nuevo
   (no existe en `opportunities`) y cuyo `CodigoEstado` sea 5 (Publicada). No hay pre-filtro por palabras clave antes
   del detalle: la clasificación y el puntaje se calculan siempre sobre el detalle completo (nombre, descripción,
   ítems con categoría UNSPSC, organismo, monto), nunca sobre el listado liviano.
2. Para una licitación **ya conocida**, el radar NO vuelve a pedir el detalle salvo que el listado muestre un
   cambio de `CodigoEstado` o de `FechaCierre` respecto de lo guardado (ambos campos vienen gratis en el listado,
   sin gastar cuota). Si cambia, se pide el detalle de nuevo y se registra en `opportunity_changes`.
3. Licitaciones del listado en otro estado (Cerrada, Desierta, Adjudicada, códigos no documentados) que **ya**
   existen en `opportunities` solo actualizan `official_status_code`/`official_status_text` desde el listado (sin
   detalle); si son nuevas para el sistema y no están Publicada, se guardan con los 4 campos del listado y
   `internal_status='detectada'`, sin gastar una llamada de detalle (no van a entrar al Excel 1 de todos modos,
   filtro duro de `docs/06` §1.0).
4. **Ritmo**: 1 solicitud cada 2 segundos por defecto (`radar.rate_limit_seconds`, configurable), con backoff
   exponencial ante 429/5xx (2s, 4s, 8s antes de cada reintento; máx. 3 reintentos; si se agotan, la candidata queda
   `detail_pending` y se reintenta en la corrida siguiente, sin perder lo ya guardado — ya diseñado en `docs/02` §4).
   `/p2-api` observó un 429 real incluso respetando 1 req/s, lo que confirma que el backoff debe tratarse como
   comportamiento esperable, no excepcional.
5. **Cuota**: el contador diario (`api_quota_usage.quota_date`) usa el día calendario de **Chile**
   (`America/Santiago`), con límite propio de 8.000/día (de los 10.000 que permite el ticket). La corrida se
   programa en una ventana configurable **01:00–05:00** hora de Chile (dentro del rango 22:00–07:00 que recomienda
   ChileCompra para descargas masivas), vía el scheduler horario ya diseñado en ADR-0007. Cada corrida registra su
   consumo real en `radar_runs.requests_used` y en `api_quota_usage`.

### Estimación de duración de una corrida diaria

Con el volumen observado en `/p2-api` (1.408 licitaciones en el listado de un día, de las cuales 487 en estado
Publicada): en régimen estable, el número de detalles a pedir por corrida es del orden de las licitaciones
Publicada **nuevas** ese día (≤ 487, probablemente menos en la práctica porque buena parte de las 487 ya se habrán
detallado en una corrida anterior) más un margen por cambios de estado/fecha en conocidas (se estima +10 %, ~50).
Con un presupuesto conservador de **550 solicitudes de detalle** + 1 de listado, a 1 solicitud cada 2 segundos:
`551 × 2 s ≈ 18 minutos`. Incluso al triple de volumen (~1.650 solicitudes), la corrida toma ~55 minutos — muy por
debajo de la ventana de 4 horas (01:00–05:00) y del límite propio de 8.000/día. Esta cuenta se revisa con datos
reales en `/p4-radar`.

## Consecuencias

- El radar consume más cuota por día que el diseño original (pedía detalle solo de "candidatas que pasan
  pre-filtro"); con el volumen observado sigue muy por debajo del límite propio de 8.000/día.
- La clasificación por línea de servicio (reglas + LLM opcional) siempre tiene disponible el detalle completo
  (ítems con categoría UNSPSC), lo que mejora su precisión frente a clasificar solo por título.
- `opportunities` con estado oficial distinto de Publicada y sin detalle guardan menos campos (solo los 4 del
  listado); si más adelante cambian a Publicada, ahí se pide su detalle por primera vez.
- Impacto en código (a implementar en `/p4-radar`, no en esta sesión): la lógica de "¿pido detalle?" compara
  `CodigoEstado`/`FechaCierre` del listado contra lo guardado antes de decidir, en vez de aplicar un filtro de
  palabras clave.

## Addendum (`/p4-radar`, 23-11-2026): el listado se pide del día anterior, no del día de la corrida

Al ejecutar una corrida real contra la API en producción (dentro de la ventana 01:00-05:00), el parámetro
`fecha` enviado a `licitaciones.json` **no debe ser el día calendario de la corrida, sino el día anterior**:
a esa hora el día de la corrida recién empezó (0-5 horas de antigüedad) y la API devuelve `Cantidad: 0`
(confirmado contra la API real el 23-11-2026, hora `01:28` de Chile, para `fecha=23112026`); el día anterior,
ya cerrado por completo, es el que tiene la actividad real a procesar — consistente con que la propia
validación de `/p2-api` (`docs/10` §0.3) ya había consultado el listado de "el día anterior a la corrida",
no el de ese mismo día.

`radar_runs.radar_date` sigue siendo el día de la corrida (es la llave del guard "ya corrió hoy" de
ADR-0007, que no cambia); el día que se le pide a la API es un concepto separado (`listing_date` en
`modules/radar/service.py`), por defecto `radar_date - 1 día`, pero configurable si alguna vez hiciera
falta reprocesar un día especifico a mano.

## Addendum 2 (`/p4-radar`, segunda revisión, 23-11-2026): fuente principal = `estado=activas`

El backend corre en el equipo del propietario (ADR-0008), que puede estar apagado alguna noche. Con
el listado por `fecha`, una corrida que no se ejecuta un día no se recupera sola: el día siguiente
pide el listado de "ayer" (el día que sí se perdió), no el que faltó. Se cambia la fuente principal a
`GET licitaciones.json?estado=activas&ticket=...` (docs/10 §1): el universo completo de licitaciones
Publicada vigentes **a la fecha de la consulta**, sin importar cuándo se publicaron. Confirmado con
una consulta real el 23-11-2026 (docs/10, nueva sección): 5.194 licitaciones, los mismos 4 campos
livianos del listado por fecha (`CodigoExterno`, `Nombre`, `CodigoEstado`, `FechaCierre`), **siempre**
con `CodigoEstado=5`.

**Decisión**:

1. `listing_source` (configurable, `organizations.settings` clave `radar.listing_source`) por defecto
   `"activas"`; `"fecha"` sigue disponible como opción. El dedupe por código oficial no cambia: nuevo
   -> detalle completo; conocido con `FechaCierre` distinto -> vuelve a detalle; conocido sin cambios
   -> solo actualiza desde el listado, sin gastar cuota.
2. Como `activas` siempre trae el mismo universo vigente (no un recorte de "un día"), también sirve
   de **carga inicial**: si la cuota se agota a mitad de camino, la corrida queda "parcial" (sin
   cambios respecto del diseño original) y la corrida siguiente retoma donde quedó, porque las
   mismas licitaciones pendientes siguen apareciendo en `activas` hasta que dejen de estar Publicada.
3. **Contrapartida que no tiene el listado por fecha**: como `activas` nunca muestra un `CodigoEstado`
   distinto de 5, una licitación conocida que deja de estar Publicada (cerrada, desierta, adjudicada,
   revocada, suspendida) **desaparece del listado** en vez de aparecer con su nuevo estado. Sin
   manejar esto, quedaría marcada Publicada/`detectada` para siempre y nunca pasaría a
   `cerrada_sin_decision` (ADR-0006) cuando corresponde. El radar calcula, en cada corrida con
   `listing_source="activas"`, qué códigos conocidos siguen marcados Publicada en la base pero ya no
   aparecen en el listado fresco, y pide su detalle (mismo mecanismo de cuota/ritmo/backoff que
   cualquier otro detalle) para aprender el estado real antes de aplicar `recompute_internal_status`.
   Esto no hace falta con `listing_source="fecha"`: ese listado ya trae licitaciones en cualquier
   estado el día que cambian (docs/10 §2.3).
4. El listado por fecha sigue siendo la opción a usar si alguna vez hace falta reprocesar un día
   calendario específico a mano (p. ej. para auditar qué pasó un día puntual).
