# 09 · Preguntas para el propietario

Estado: **RESPONDIDAS** el 21-11-2026. Se conserva el registro de pregunta, respuesta y dónde quedó aplicada.

| # | Pregunta | Respuesta del propietario | Aplicado en |
| --- | --- | --- | --- |
| 1 | ¿Dónde corren la API y el worker en producción? | Por ahora en su equipo (Windows + Docker). Radar programado a hora configurable y manual. Todo en contenedores; servicio en la nube (Railway, Render, Fly.io, Cloud Run o Azure Container Apps) se elige antes de cerrar MVP-2. | ADR-0008, `01` §2.9, `08` R-11 |
| 2 | ¿Arquitectura liviana con Supabase, Procrastinate y Supabase Auth? | Aprobada. El backend valida el JWT de Supabase; los roles viven en tablas propias. | ADR-0001, ADR-0003 |
| 3 | ¿Mover el repo fuera de OneDrive? | Sí, a `C:\dev\sistema-propuestas-mp`; lo hace el propietario. | `04`, `08` R-12 (resuelto) |
| 4 | Proveedores de IA, tope de gasto y retención | Comparar Anthropic (Opus 5.5 y Sonnet 5.5) contra OpenAI detrás de la capa propia. Tope configurable, inicial USD 40/mes, alerta al 80 %. Sin retención cero en MVP-1/2; sí exige que el proveedor no use los datos para entrenar. Se revisa en MVP-3. | ADR-0005, `01` §2.7, `05` E5-11, E7-4 |
| 5 | ¿Cuándo estará el conjunto de evaluación? | 5 licitaciones anotadas al terminar `/p7`; luego 15-20. `/p9` debe funcionar desde 5. | `07` §3, `05` E7-6, cierre MVP-1 |
| 6 | ¿pdfplumber + Tesseract en vez de Docling? | Aprobado; Docling como plan B documentado. Exige pruebas de número de página y tablas. | ADR-0004, `05` E5-1, `07` `/p7` |
| 7 | ¿Qué entra al Excel 1? | Sin puntaje mínimo duro: las 50 de mayor puntaje más todas con puntaje ≥ 40; ambos configurables. | `06` §1.0, `05` E3-1, E3-7 |
| 8 | Filtros duros iniciales | Solo estado oficial Publicada y cierre a 3 días o más desde la corrida (configurable). Sin filtro de monto, región ni organismo. | `06` §1.0, `05` E2-10, `02` §2 |
| 9 | Reglas de la Compuerta 1 | Motivo obligatorio en Descartar; responsable obligatorio en Descargar; Dudoso sin obligatorios. | `06` §1.1 y §1.4, `05` E3-3 |
| 10 | Umbrales del semáforo | Aprobados como provisionales y configurables. | `06` §2.4 |

Desvío adicional resuelto: **`bids` al detectar — NO aprobado.** El estado del embudo va en `opportunities`; `bids`
nace con "Descargar" (ADR-0006, `03`, `05`, `02`, `06`).

## Preguntas abiertas

Ninguna bloqueante para `/p2-api`. Quedan para más adelante:
- Servicio de contenedores para producción (antes de cerrar MVP-2).
- Confirmación de umbrales de calidad cuando el conjunto de evaluación llegue a 15-20 licitaciones.
