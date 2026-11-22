# ADR-0009 · Zona horaria asumida para las fechas de la API de Mercado Público

- Estado: Aceptada
- Fecha: 22-11-2026

## Contexto

`/p2-api` confirmó con el ticket real (10 muestras de detalle, `docs/10-api-validada.md` §2.2) que todas las fechas
que entrega `api.mercadopublico.cl` llegan como texto `AAAA-MM-DDTHH:MM:SS[.fffffff]`, **sin sufijo de zona ni
offset**. Ninguna de las 10 muestras correspondía a una unidad compradora en Magallanes o Isla de Pascua (se vieron
Región Metropolitana, Araucanía, Biobío y Los Lagos), así que no se pudo confirmar empíricamente en qué hora local
está esa fecha para esas dos zonas especiales.

## Decisión

- Se asume que **toda** fecha devuelta por la API está en hora de **Chile continental** (`America/Santiago`),
  independientemente de la región de la unidad compradora. Es un supuesto, no un hecho confirmado para todo el país.
- El parser (`core/timezones`, `/p4-radar`) aplica esta regla sin excepciones por región.
- Se guarda siempre el texto original (`opportunity_dates.original_text`) además del valor convertido a UTC, para
  poder re-interpretar si el supuesto resulta incorrecto para alguna zona.
- Fechas con año ≤ 1950 (valor centinela observado de .NET, p. ej. `"1900-01-04T00:00:00"`) se tratan como
  `parse_status='missing'`, nunca como instante real.

## Consecuencias

- Si en producción aparece una licitación de Magallanes o Isla de Pascua con una fecha de cierre que en realidad
  está en su propia hora local, la conversión a UTC quedará desplazada 1 hora (Punta Arenas puede diferir de
  Santiago) hasta que se audite el caso real.
- Riesgo documentado (no bloqueante) en `docs/08-riesgos.md`. Procedimiento de cierre: la primera vez que el radar
  real detecte `Comprador.RegionUnidad` en Magallanes o Isla de Pascua, revisar a mano sus `Fechas.*` contra la
  ficha pública antes de confiar en la conversión automática; si difiere, se agrega una excepción por región en
  `core/timezones` (migración de datos si ya hay fechas guardadas mal).
- No bloquea MVP-1 ni MVP-2: el volumen de licitaciones en esas dos zonas es bajo y el propietario prioriza TI, que
  se concentra en regiones con un solo huso horario.
