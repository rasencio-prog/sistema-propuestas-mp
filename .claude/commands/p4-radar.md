---
description: MVP-1 – Radar: captura, clasificación y puntaje
---

Lee CLAUDE.md, docs/02, docs/03, docs/05 (épica E2), docs/10-api-validada.md y los ADR de docs/decisions/ (en especial ADR-0006 y ADR-0007). Implementa las historias del Radar de MVP-1.

1. Migraciones (Alembic, esquema app): buyers, opportunities (id interno UUID + código oficial único, estado oficial en código y texto, estado interno del embudo en internal_status separado del oficial, monto estimado, URL de ficha, puntaje con desglose y justificación, datos crudos saneados en JSON), opportunity_items, opportunity_dates (tipo de fecha, timestamp UTC, texto original), opportunity_changes, opportunity_service_lines, scoring_profiles, radar_runs, api_quota_usage y api_call_log. La tabla bids NO se crea aquí (nace con "Descargar" en /p5, ADR-0006).
2. Adaptador de Mercado Público en modules/marketplace_adapters, versionado (p. ej. mp_v1), que solo use endpoints y campos confirmados en docs/10. Sin lógica de negocio dentro: devuelve un modelo canónico interno.
3. Control de cuota: contador diario por credencial (api_quota_usage) con límite configurable por debajo de 10.000 (valor inicial 8.000), ritmo máximo configurable, reintentos con backoff exponencial, registro de cada llamada (fecha, estado HTTP, duración, sin el ticket). Al llegar al límite, la corrida termina como "parcial".
4. Patrón de consulta: listado diario liviano → pre-filtro barato → detalle por código solo para candidatos.
5. Normalización y deduplicación por código oficial. Oportunidad nueva → internal_status "detectada". Si una oportunidad ya existe y cambian estado o fechas, registra el cambio en opportunity_changes. Si el estado oficial deja de ser Publicada sin decisión de la Compuerta 1 → "cerrada_sin_decision".
6. Clasificación por línea de servicio en dos capas: (a) reglas determinísticas con palabras clave, exclusiones y rubros; (b) opcional y desactivable, un LLM detrás de la interfaz LLMProvider (ADR-0005) que devuelve JSON validado con líneas y factores, nunca el puntaje. Guarda las líneas en opportunity_service_lines y la justificación legible en opportunities.
7. Puntaje 0-100 calculado en modules/scoring con pesos configurables (scoring_profiles) y explicación por factor, guardado en opportunities. Reproducible: misma entrada, mismo puntaje.
8. Filtros duros configurables (docs/06 sección 1.0): estado oficial Publicada y cierre de ofertas a 3 días o más desde la corrida. Las que no cumplen quedan "detectada" y no entran al Excel. Sin filtro de monto, región ni organismo.
9. Ejecución programada a hora configurable (America/Santiago) con Procrastinate según ADR-0007: tarea horaria que encola el radar solo si ya pasó la hora configurada y no hay corrida exitosa ese día. Ejecución manual desde la UI de administrador. Registro de cada corrida en radar_runs (inicio, fin, consultas, nuevas, actualizadas, errores). Debe funcionar con el backend en el equipo del propietario (ADR-0008).
10. Fechas: parsea según el formato confirmado en docs/10, guarda en UTC y conserva el texto original. Pruebas con fechas cercanas al cambio de horario de Chile (docs/07 sección 1).
11. Pruebas con respuestas grabadas de docs/api-samples (sin llamar a la API real en CI): deduplicación, cambios, cuota, estado interno separado del oficial, filtros duros, clasificación, puntaje y scheduler con reloj simulado.

Fuera de alcance: Excel y tabla bids (siguiente etapa), Compra Ágil, órdenes de compra.

Al terminar: ejecuta una corrida real de un día, muéstrame cuántas oportunidades capturó, cuántas pasan los filtros duros, las 10 con mayor puntaje con su justificación y el consumo de cuota, y detente.
