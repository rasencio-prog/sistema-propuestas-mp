# ADR-0011 · Resumen IA en el Excel 1 (MVP-1, antes de que exista `bids`)

- Estado: Aceptada (decisión del propietario)
- Fecha: 22-11-2026

## Contexto

El propietario pidió una columna "Resumen IA" (2-3 líneas) en la hoja `Oportunidades` del Excel 1, para decidir más
rápido en la Compuerta 1. Hasta ahora el uso de IA estaba modelado solo para MVP-2 (`analysis_runs`, `ai_usage`),
colgando de `bids` — que recién existe después de la Compuerta 1 (ADR-0006). El resumen IA del Excel 1 ocurre
**antes**, sobre `opportunities` que todavía no tienen postulación.

## Decisión

- El resumen se genera con la misma interfaz `LLMProvider` (ADR-0005), con un modelo económico de clasificación
  (`claude-haiku-5-5` por defecto, configurable) — no el modelo de extracción de MVP-2.
- Entrada: solo campos ya confirmados de la API (nombre, descripción, ítems, organismo, monto si es visible,
  duración del contrato, días al cierre, línea de servicio asignada). Nunca bases ni documentos (no existen en esta
  etapa). Reglas explícitas en el prompt: nunca inventar montos ni plazos que no estén en los datos de entrada; si
  falta un dato relevante, decirlo en vez de omitirlo en silencio.
- Se genera **solo** para las oportunidades que entran al lote de preselección (`docs/06` §1.0: top 50 ∪ puntaje
  ≥ 40), no para todas las `detectada`. Nueva tabla `opportunity_ai_summaries` (ver `docs/03`), con caché por
  `opportunities.content_hash`: si el detalle no cambió desde el último resumen, se reutiliza y no se vuelve a
  llamar al proveedor.
- Cuenta contra el mismo tope mensual de IA (`ai_monthly_budget_usd`, ADR-0005): se registra en `ai_usage` con
  `analysis_run_id` nulo y un nuevo campo `opportunity_id` (nullable) para diferenciarlo de los usos de MVP-2. Si el
  presupuesto está en 100 %, la columna queda vacía con nota "No generado (presupuesto de IA agotado)", igual que
  el resto del sistema deja de iniciar análisis nuevos.
- Desactivable por configuración de la organización (`organizations.settings.ai_summary_enabled`, default `true`);
  si está desactivado, la columna existe pero vacía — nunca se omite la columna completa (mismo formato de Excel en
  ambos casos, no rompe la reimportación).
- No afecta el puntaje ni la clasificación (que siguen siendo determinísticos en el backend, regla ya vigente); es
  puramente informativo para la persona que decide.

## Consecuencias

- Nuevo gasto de IA en MVP-1, antes de lo que contemplaba `docs/01` §2.7 (que situaba el primer uso de IA en la
  clasificación opcional del radar y en el análisis de MVP-2). El resumen usa el modelo más económico (Haiku) y
  tiene caché, así que el costo incremental esperado es bajo; se mide en `/p5-excel1` y se compara contra el tope
  de USD 40/mes.
- Nueva tabla `opportunity_ai_summaries` (migración en `/p5-excel1`, no en esta sesión).
- La hoja `Oportunidades` del Excel 1 puede mostrar una columna vacía con frecuencia al principio (presupuesto
  agotado, función desactivada, o la oportunidad recién entró y aún no se generó) — se documenta en la hoja
  `Instrucciones` para que no se interprete como error.
