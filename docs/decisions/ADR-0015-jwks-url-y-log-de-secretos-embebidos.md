# ADR-0015 · URL del JWKS a partir del origen; enmascarado de secretos embebidos en logs

- Estado: Aceptada
- Fecha: 23-11-2026
- Decide: agente, al diagnosticar un 401 real en `/api/auth/login` durante `/p3-fundaciones`
- Aclara: ADR-0003 (verificación de JWT vía JWKS)

## Contexto

Al probar el login real (frontend → Supabase Auth → backend), el backend rechazaba el JWT con
`401 Token invalido o expirado`, aunque Supabase Auth autenticaba correctamente y el JWKS del proyecto
tenía una clave `ES256` válida. El log (antes de esta ADR, sin detalle del motivo) no bastaba para
diagnosticar; se agregó un log temporal que reveló la causa real:
`PyJWKClientConnectionError: Fail to fetch data from the url, err: "HTTP Error 401: Unauthorized"`.

La URL del JWKS se construía concatenando `SUPABASE_URL` (tal cual venía de `.env`) con
`/auth/v1/.well-known/jwks.json`. `SUPABASE_URL` traía una ruta adicional (`/rest/v1`, pegada de otra
sección del panel de Supabase), así que la URL resultante
(`.../rest/v1/auth/v1/.well-known/jwks.json`) no existe y Supabase la rechaza con 401 — error que el
backend interpretaba, incorrectamente, como "token inválido".

Aparte, revisando `docs/05-backlog.md` E1-2 ("prueba que verifica que un ticket ficticio en una URL
no aparece en el log") se confirmó que el filtro de secretos de `core/logging.py` solo enmascaraba por
nombre de campo, no un secreto embebido dentro de un campo más largo como una URL.

## Decisión

- `core/security.py` expone `jwks_url(supabase_url: str) -> str`, que se queda solo con el origen
  (`scheme://netloc`) de `SUPABASE_URL`, descartando cualquier ruta, antes de construir la URL del
  JWKS. Nunca se exige que `SUPABASE_URL` en `.env` venga "limpio": el código es tolerante a que
  traiga una ruta por error.
- `core/logging.py` agrega `_SECRET_QUERY_PARAM_PATTERN`: además de enmascarar por nombre de campo,
  busca y enmascara patrones `?clave=valor` / `&clave=valor` dentro de valores de texto (p. ej. una
  URL con `?ticket=...`), conservando el resto del valor visible para depurar.
- Se agregó `logger.warning("jwt_rejected", reason=str(exc))` en `api/deps.py` antes de convertir
  `InvalidTokenError` en `401`: el mensaje de PyJWT nunca incluye el token ni secretos, solo la razón
  (firma inválida, expirado, `kid` no encontrado, error de red al buscar el JWKS...), y sin esto un
  401 de autenticación es prácticamente indiagnosticable desde los logs.

## Consecuencias

- `SUPABASE_URL` puede corregirse en `.env` (dejar solo el origen) por prolijidad, pero ya no es
  necesario para que el login funcione: el código se defiende solo.
- El enmascarado de secretos embebidos es una heurística (busca el patrón `clave=valor` con nombres
  de clave conocidos); no sustituye revisar que nunca se construya a propósito una URL con un secreto
  en texto plano fuera de parámetros con esos nombres.
- Pruebas agregadas: `tests/unit/test_security.py::test_jwks_url_discards_any_path_in_supabase_url`
  (3 casos) y `tests/unit/test_logging.py` (campo nombrado como secreto, secreto embebido en URL, y
  verificación end-to-end contra la salida real de `configure_logging`).
