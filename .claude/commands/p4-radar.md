---
description: MVP-1 – Radar: captura, clasificación y puntaje
---

Lee CLAUDE.md, docs/03, docs/05 y docs/10-api-validada.md. Implementa las historias del Radar de MVP-1.

1. Migraciones: buyers, opportunities (id interno UUID + código oficial único, estado oficial en código y texto, monto estimado, URL de ficha, datos crudos saneados en JSON), opportunity_dates (tipo de fecha, timestamp UTC, texto original), opportunity_changes y api_call_log.
2. Adaptador de Mercado Público en modules/marketplace_adapters, versionado (p. ej. mp_v1), que solo use endpoints y campos confirmados en docs/10. Sin lógica de negocio dentro: devuelve un modelo canónico interno.
3. Control de cuota: contador diario por organización con límite configurable por debajo de 10.000, ritmo máximo configurable, reintentos con backoff exponencial, registro de cada llamada (fecha, estado HTTP, duración, sin el ticket).
4. Patrón de consulta: listado diario liviano → pre-filtro barato → detalle por código solo para candidatos.
5. Normalización y deduplicación por código oficial. Si una oportunidad ya existe y cambian estado o fechas, registra el cambio en opportunity_changes.
6. Clasificación por línea de servicio en dos capas: (a) reglas determinísticas con palabras clave, exclusiones y rubros; (b) opcional y desactivable, un LLM detrás de una interfaz de proveedor que devuelve JSON validado con líneas y factores, nunca el puntaje. Guarda la justificación legible.
7. Puntaje 0-100 calculado en modules/scoring con pesos configurables y explicación por factor. Reproducible: misma entrada, mismo puntaje.
8. Ejecución programada nocturna (hora configurable, America/Santiago) y ejecución manual desde la UI de administrador, con registro de cada corrida (inicio, fin, consultas, nuevas, actualizadas, errores).
9. Fechas: parsea según el formato confirmado en docs/10, guarda en UTC y conserva el texto original. Pruebas con fechas cercanas al cambio de horario de Chile.
10. Pruebas con respuestas grabadas de docs/api-samples (sin llamar a la API real en CI): deduplicación, cambios, cuota, clasificación y puntaje.

Fuera de alcance: Excel (siguiente etapa), Compra Ágil, órdenes de compra.

Al terminar: ejecuta una corrida real de un día, muéstrame cuántas oportunidades capturó, las 10 con mayor puntaje con su justificación y el consumo de cuota, y detente.
