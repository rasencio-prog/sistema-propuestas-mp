# ADR-0001 · Arquitectura liviana con Supabase y cola sobre Postgres

- Estado: Aceptada
- Fecha: 21-11-2026
- Decide: propietario, a propuesta de `/p1-plan`

## Contexto
El brief (sección 10) propone FastAPI + Celery/Redis + MinIO + Postgres, y como alternativa liviana un servicio
gestionado con cola sobre PostgreSQL para 1-3 usuarios. Hay 1 usuario hoy (máximo 1-3), un radar diario y pocas
licitaciones analizadas al día. El propietario ya eligió Supabase para producción.

## Decisión
Monolito modular FastAPI + un worker del mismo código. Supabase aporta PostgreSQL con pgvector, Storage y Auth.
Los trabajos asíncronos y las tareas programadas usan **Procrastinate** sobre la misma base. Sin Redis, Celery ni MinIO.
En local se replica Supabase con Supabase CLI (Docker). El worker usa conexión directa o pooler en modo sesión
(Procrastinate usa `LISTEN/NOTIFY`; si no está disponible, funciona por sondeo).

## Consecuencias
- Menos piezas que operar y respaldar; costo mensual bajo.
- Encolar un trabajo es parte de la misma transacción que los datos.
- Dependencia de Supabase en Auth y Storage, aislada detrás de interfaces (`AuthVerifier`, `FileStorage`, `JobQueue`).
- Si el volumen creciera mucho, se puede cambiar a Celery/Redis o S3 sin tocar el dominio.
