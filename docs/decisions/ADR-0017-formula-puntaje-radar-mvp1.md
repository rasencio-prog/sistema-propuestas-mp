# ADR-0017 · Formula de puntaje del radar (MVP-1, sin documentos)

- Estado: Aceptada
- Fecha: 23-11-2026

## Contexto

El brief (S6.4) sugiere 5 dimensiones para el puntaje de afinidad (afinidad tecnica, capacidad
operativa, viabilidad temporal, atractivo economico, riesgo contractual) calculado por el backend
con pesos configurables, pero no fija una formula exacta — la deja para la implementacion, igual que
`scoring_profiles.weights`/`thresholds` (docs/03) estan pensados para eso. En el radar (`/p4-radar`)
todavia no hay documentos (bases): solo el detalle de la API (docs/10 S2.2). Hacia falta una formula
concreta, reproducible y explicable para poder cerrar E2-7.

## Decision

`modules/scoring/service.py` calcula cada dimension solo con metadatos de la API, nunca inventa
evidencia; lo que no tiene senal disponible usa un valor neutro configurable (`thresholds.*_default`):

- **Afinidad tecnica**: la mayor confianza entre las lineas de servicio asignadas por el
  clasificador (`service_lines.classifier`), escalada a 0-100. Sin coincidencia -> 0.
- **Viabilidad temporal**: dias corridos hasta el cierre de ofertas, escalado linealmente hasta un
  umbral configurable (`time_viability_full_score_days`, default 30 dias -> 100).
- **Atractivo economico**: si el monto es visible, 100 dentro de un rango configurable
  (`economic_attractive_min/max`, default 5-150 millones CLP) y decae linealmente fuera de el; si no
  es visible, valor neutro configurable (default 50).
- **Capacidad operativa**: duracion de contrato (meses, via `TiempoDuracionContrato` +
  `UnidadTiempoDuracionContrato`, tabla 3.6 del manual) dentro de un rango ideal configurable
  (default 1-36 meses) -> 100; fuera de rango decae; sin dato -> neutro (default 50).
- **Riesgo contractual** (invertido): `CantidadReclamos` del organismo normalizado entre un piso y un
  techo configurables (default 0-500); sin dato -> neutro (default 50).

El puntaje final es el promedio ponderado de las 5 dimensiones (pesos en `scoring_profiles.weights`,
default 40/15/20/10/15 %), redondeado a 2 decimales y acotado a 0-100. Puro y determinista: la misma
entrada (detalle + clasificacion + perfil de puntaje + instante de la corrida) siempre da el mismo
puntaje (docs/05 E2-7).

## Consecuencias

- El puntaje de MVP-1 es preliminar por diseno (el brief lo llama "puntaje de afinidad preliminar",
  S5.1): no conoce plazos de implementacion, SLA, garantias ni criterios de evaluacion, que solo
  existen en las bases (MVP-2, `/p7-analisis`).
- Los valores por defecto (rangos de monto, dias, meses, reclamos) son una propuesta razonable, no
  una medicion empirica: quedan en `scoring_profiles.thresholds`, editables por un administrador sin
  tocar codigo (UI pendiente, igual que el resto de "configurables" de esta etapa — ver E3-7).
- Si en `/p9-evals` el puntaje no correlaciona bien con las decisiones reales del propietario, se
  ajustan pesos/umbrales o se agregan factores, sin tocar el resto del dominio (la formula vive solo
  en `modules/scoring/service.py`).

## Addendum (23-11-2026): la afinidad de linea de servicio es una condicion, no solo un factor

La primera corrida real (`/p4-radar`) mostro el problema del promedio ponderado puro: dos
licitaciones de Putaendo (inspeccion tecnica y asesoria para la construccion de una biblioteca
publica, sin ninguna coincidencia con las lineas de servicio TI configuradas) sacaron **46.13
puntos**, solo porque el monto era atractivo y el plazo viable compensaban un `service_line_affinity`
en 0 dentro del promedio ponderado (peso 40 %, pero los otros 60 % igual sumaban lo suficiente). Un
puntaje así de alto en un rubro completamente fuera de lo que la empresa hace es enganoso para quien
revisa el Excel 1.

**Decision**: despues de calcular el promedio ponderado normal, si `best_service_line_confidence` es
`None` (ninguna linea activa coincidio, `classify_by_rules`/el LLM no devolvieron matches), el
puntaje final se acota a un techo configurable `thresholds.no_affinity_score_cap` (default **15**),
sin importar que tan bien puntuen los demas factores. Si el puntaje ponderado ya era menor al techo,
no se toca (el techo nunca sube un puntaje, solo lo baja). Se guarda `breakdown.capped_no_affinity`
(booleano) para que quede explicito en `opportunities.score_breakdown` cuando se aplico el recorte,
sin perder el detalle de los factores originales.

Umbral configurable por perfil (`scoring_profiles.thresholds.no_affinity_score_cap`, migracion
`0005_no_affinity_score_cap` fusiona la clave en los perfiles ya sembrados sin pisar si un
administrador ya la edito a mano).
