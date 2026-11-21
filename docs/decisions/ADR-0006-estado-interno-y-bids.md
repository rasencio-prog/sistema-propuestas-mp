# ADR-0006 · Estado interno del embudo en `opportunities`; `bids` nace con "Descargar"

- Estado: Aceptada (reemplaza la propuesta de `/p1-plan` de crear `bids` al detectar, rechazada por el propietario)
- Fecha: 21-11-2026

## Contexto
El brief exige separar el estado oficial de Mercado Público del estado interno. La propuesta inicial creaba la
postulación (`bids`) al detectar cada oportunidad. El propietario la rechazó: una postulación solo tiene sentido cuando
se decide documentar la licitación.

## Decisión
- `opportunities.internal_status` guarda el embudo hasta la Compuerta 1: `detectada`, `preseleccionada`,
  `descartada_preseleccion`, `documentos_pendientes` y `cerrada_sin_decision`. Es un campo distinto de
  `official_status_code` / `official_status_text`.
- Puntaje, desglose y justificación de clasificación también se guardan en `opportunities`; las líneas asignadas en
  `opportunity_service_lines`.
- La tabla `bids` se crea **cuando la Compuerta 1 decide "Descargar"**, en la misma transacción que deja la oportunidad
  en `documentos_pendientes` y crea el intake y la carpeta. Desde ahí `bids.status` lleva el estado de la postulación
  (`documentos_pendientes`, `en_analisis`, `pendiente_decision`, `aprobada_participar`, `no_participar`, etc.).
- `documentos_pendientes` es el último valor del embudo en `opportunities`; el **estado vigente** que se muestra es
  `bids.status` si existe postulación y, si no, `opportunities.internal_status`.
- Documentos, análisis y Excel 2 cuelgan de `bids`. Las decisiones de la Compuerta 1 cuelgan de la oportunidad.
- Revertir un "Descargar" solo se permite si la postulación sigue sin documentos; queda `desistida`, no se borra.

## Consecuencias
- No hay postulaciones vacías por cada oportunidad detectada.
- `/p8-excel2` ya no crea la tabla `bids`: actualiza la postulación existente con la decisión Go/No-Go.
- `opportunities` deja de ser puramente pública: el embudo y el puntaje dependen de la organización. Es correcto con una
  organización; al habilitar multiempresa esos campos se mueven por migración a una tabla por organización.
