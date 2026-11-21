---
description: Etapa 1 – Fundaciones del repositorio
---

Lee CLAUDE.md y docs/ (decisiones aprobadas en 01, modelo en 03, estructura en 04, ADR en docs/decisions/). Implementa la Etapa 1 – Fundaciones con el stack aprobado.

Alcance:
1. Estructura de carpetas según docs/04.
2. Entorno local en Windows con Docker (ADR-0001 y ADR-0008): Supabase CLI levanta PostgreSQL con pgvector, Storage y Auth; Docker Compose (infra/compose.yaml) levanta api, worker (Procrastinate) y web. Pocos comandos documentados para levantar todo. Las mismas imágenes deben poder desplegarse después en un servicio de contenedores: sin estado, configuración solo por variables de entorno, logs a la salida estándar.
3. Backend con configuración por variables de entorno, logging estructurado en JSON con request_id (con filtro que elimina secretos) y endpoint /health con estado de base y cola.
4. Migraciones iniciales con Alembic en el esquema app, con RLS activado y sin políticas (ADR-0002), solo para: users, organizations, organization_members, api_credentials (ticket cifrado en reposo con Fernet), service_lines, audit_events. Incluye la instalación del esquema de Procrastinate. Semilla con las 5 líneas de servicio del brief (sección 2) y sus palabras clave, editables.
5. Autenticación con Supabase Auth (ADR-0003): el backend valida el JWT de Supabase (firma JWKS, expiración, audiencia); usuarios, organización y roles viven en nuestras tablas. Roles: administrador, comercial, revisor, solo lectura.
6. Frontend mínimo: login y una página de configuración de líneas de servicio y palabras clave. Nada más.
7. Registro de auditoría reutilizable, usado desde ya en login y cambios de configuración.
8. Pruebas: configuración de pytest (y del frontend si aplica), pruebas de auth (con JWT de prueba firmados localmente), roles y auditoría.
9. CI en GitHub Actions: lint + pruebas en cada push.
10. Completa .env.example sin valores reales. Actualiza el README con instrucciones paso a paso para macOS y Windows.
11. Completa los comandos estándar en CLAUDE.md.

Fuera de alcance: radar, Excel, documentos, IA.

Antes de agregar dependencias grandes no listadas en docs/01, pregúntame. Al terminar: ejecuta las pruebas, muéstrame el resultado, dime los comandos para levantarlo y detente.
