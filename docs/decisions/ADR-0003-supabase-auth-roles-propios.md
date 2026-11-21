# ADR-0003 · Supabase Auth con roles en tablas propias

- Estado: Aceptada
- Fecha: 21-11-2026

## Contexto
Se necesita login seguro desde MVP-1 y roles (administrador, comercial, revisor, solo lectura), con la arquitectura
preparada para multiempresa.

## Decisión
- Identidad con **Supabase Auth** (email + contraseña; MFA TOTP disponible para el administrador).
- El frontend obtiene el JWT y lo envía a FastAPI. **El backend valida el JWT** (firma con las claves JWKS del proyecto,
  expiración, audiencia) y resuelve usuario, organización y rol desde `app.users` y `app.organization_members`.
- **Los roles y permisos viven en nuestras tablas**, nunca en metadatos de Supabase.
- En CI se usan JWT de prueba firmados localmente.

## Consecuencias
- No se implementa ni se guarda hashing de contraseñas propio.
- Cambiar de proveedor de identidad solo afecta a `core/security.py` y al login del frontend.
- Un usuario autenticado sin membresía activa recibe 403.
