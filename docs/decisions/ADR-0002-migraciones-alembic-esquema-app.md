# ADR-0002 · Alembic como única fuente de migraciones; esquema `app` no expuesto

- Estado: Aceptada
- Fecha: 21-11-2026

## Contexto
Toda modificación de esquema debe ir por migración (CLAUDE.md). Supabase expone por defecto las tablas del esquema
`public` a través de su Data API, y el navegador no debe acceder a la base directamente.

## Decisión
- Las migraciones del esquema de la aplicación se escriben y aplican solo con **Alembic** (SQLAlchemy 2.0), versionadas
  en `backend/migrations/`, iguales en local, CI y producción. No se usan las migraciones SQL de Supabase CLI para la app.
- Las tablas viven en el esquema **`app`**, no expuesto por la Data API, y con **RLS activado sin políticas**.
- Solo el backend accede a la base. Los esquemas `auth` y `storage` de Supabase no se modifican.
- Procrastinate administra su propio esquema con su herramienta, invocada desde una migración de Alembic.

## Consecuencias
- Un solo historial de esquema, con `upgrade` y `downgrade` probados en CI.
- Defensa en dos capas contra exposición accidental de datos a clientes de Supabase.
- Cualquier acceso futuro desde el navegador requerirá políticas RLS explícitas y una nueva decisión.
