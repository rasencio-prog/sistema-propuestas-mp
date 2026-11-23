# Sistema de Propuestas – Mercado Público + IA

Plataforma para detectar licitaciones en Mercado Público, analizarlas con IA y preparar propuestas con revisión humana.
Especificación: `docs/brief/`. Reglas del proyecto para el agente: `CLAUDE.md`.

## Cómo trabajar con Claude Code en VS Code

1. Completa `docs/00-decisiones-propietario.md`.
2. Copia `.env.example` como `.env` y completa `MP_TICKET` (solo hace falta desde `/p2-api`) y, desde `/p3-fundaciones`,
   las variables de Supabase (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `DATABASE_URL`, `TEST_DATABASE_URL`) y
   `APP_ENCRYPTION_KEY`. El entorno local es Windows nativo, sin Docker (ADR-0012): no se necesita Docker Desktop ni
   Supabase CLI; se desarrolla contra un proyecto Supabase en la nube dedicado a desarrollo.
3. Abre el panel de Claude Code y ejecuta los comandos en orden. Cada uno termina con el agente detenido esperando tu revisión.

| Orden | Comando | Etapa | Tu revisión antes de seguir |
| --- | --- | --- | --- |
| 1 | `/p1-plan` | Descubrimiento y plan (sin código) | Aprobar stack, modelo de datos y backlog |
| 2 | `/p2-api` | Validación de la API con ticket real | Abrir 2 links de ficha y revisar el informe |
| 3 | `/p3-fundaciones` | Repo, entorno Windows sin Docker, base de datos (Supabase dev), login | Levantarlo en local |
| 4 | `/p4-radar` | Captura, clasificación y puntaje | Revisar las oportunidades capturadas |
| 5 | `/p5-excel1` | Excel de preselección | Marcar decisiones en un Excel real |
| 6 | `/p6-intake` | Carga asistida de adjuntos | Cargar adjuntos de 2 o 3 licitaciones |
| 7 | `/p7-analisis` | Análisis IA con citas verificadas | Comparar contra las bases |
| 8 | `/p8-excel2` | Fichas resumen y Go/No-Go | Decidir sobre fichas reales |
| 9 | `/p9-evals` | Conjunto de evaluación | Confirmar umbrales |

Comandos de apoyo: `/cierre-etapa` (antes de cada commit), `/corregir <qué pasó>` (cuando algo falla),
`/retomar` (al abrir una sesión nueva).

## Rutina por etapa
1. `git checkout -b etapa-N-nombre`
2. `/clear` para empezar con el contexto limpio, luego el comando de la etapa.
3. Revisar lo entregado; pedir ajustes en el mismo chat.
4. `/cierre-etapa`, revisar el resumen, commit y merge a `main`.
