# ADR-0018 · Semilla de `api_credentials` desde `MP_TICKET` en la migracion del radar

- Estado: Aceptada (bridge temporal hasta que exista E1-7)
- Fecha: 23-11-2026

## Contexto

`docs/05-backlog.md` E1-7 ("Como administrador quiero registrar el ticket de la API cifrado") quedo
pendiente al cierre de `/p3-fundaciones`: el modelo de datos y el cifrado (Fernet, `core/crypto.py`)
existen, pero no hay endpoint para dar de alta el ticket. El radar (`/p4-radar`) necesita una fila en
`api_credentials` (cifrada, `daily_limit`) para poder controlar la cuota (ADR-0010, `api_quota_usage`
referencia `credential_id`). Sin esa fila, el radar no puede correr en absoluto.

## Decision

La migracion `0004_radar_opportunities` siembra, de forma idempotente, una fila en `api_credentials`
(organizacion "Databrain SpA", `provider='mercado_publico'`, `holder_name='Robinson Asencio'`
docs/00, `daily_limit=8000`) **solo si** `MP_TICKET` esta presente en el entorno al momento de
migrar, cifrandolo con `sp.core.crypto.encrypt` (la misma funcion Fernet que usara el resto de la
app para descifrarlo, nunca una reimplementacion propia del cifrado dentro de la migracion). Si
`MP_TICKET` no esta presente (p. ej. en CI, que usa un Postgres efimero sin ticket real), la
migracion no crea la fila y el radar simplemente no tiene credencial activa hasta que se configure a
mano o se corra esta migracion con el ticket real en el entorno.

Es la unica migracion de este repo que importa codigo de `sp.*` (`sp.core.crypto`, `sp.core.
settings`): una excepcion deliberada y acotada a infraestructura (cifrado), no a logica de negocio
—a diferencia de las semillas de `0003` (lineas de servicio), que son datos puros sin dependencias.

## Consecuencias

- Mientras no exista el endpoint de E1-7, rotar el ticket requiere correr esta migracion de nuevo
  (no es idempotente para *actualizar* un ticket ya sembrado, solo para no duplicar la fila) o
  editar la fila a mano. Aceptable para 1 usuario administrador.
- Cuando se construya E1-7, su endpoint reemplaza este camino para altas y rotaciones nuevas; esta
  semilla deja de ser necesaria pero no hace falta revertirla (la fila sembrada sigue siendo valida).
- CI nunca tiene `MP_TICKET` real: las pruebas de integracion del radar crean su propia fila de
  `api_credentials` de prueba con un ticket ficticio cifrado, sin depender de esta semilla.
