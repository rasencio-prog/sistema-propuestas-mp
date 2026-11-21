---
description: Etapa 1 – Fundaciones del repositorio
---

Lee CLAUDE.md y docs/ (decisiones aprobadas en 01, modelo en 03, estructura en 04). Implementa la Etapa 1 – Fundaciones con el stack aprobado.

Alcance:
1. Estructura de carpetas según docs/04.
2. Docker Compose para desarrollo local: backend, PostgreSQL con pgvector, worker/cola y almacenamiento de archivos según lo aprobado. Un solo comando para levantar todo.
3. Backend con configuración por variables de entorno, logging estructurado en JSON con request_id y endpoint /health.
4. Migraciones iniciales solo para: users, organizations, organization_members, api_credentials (ticket cifrado en reposo), service_lines, audit_events. Semilla con las 5 líneas de servicio del brief (sección 2) y sus palabras clave, editables.
5. Autenticación básica (email + contraseña con hash seguro, o el proveedor aprobado) y roles: administrador, comercial, revisor, solo lectura.
6. Frontend mínimo: login y una página de configuración de líneas de servicio y palabras clave. Nada más.
7. Registro de auditoría reutilizable, usado desde ya en login y cambios de configuración.
8. Pruebas: configuración de pytest (y del frontend si aplica), pruebas de auth, roles y auditoría.
9. CI en GitHub Actions: lint + pruebas en cada push.
10. Completa .env.example sin valores reales. Actualiza el README con instrucciones paso a paso para macOS y Windows.
11. Completa los comandos estándar en CLAUDE.md.

Fuera de alcance: radar, Excel, documentos, IA.

Antes de agregar dependencias grandes no listadas en docs/01, pregúntame. Al terminar: ejecuta las pruebas, muéstrame el resultado, dime los comandos para levantarlo y detente.
