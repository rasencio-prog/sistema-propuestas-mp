---
description: MVP-2 – Excel 2 de fichas resumen y decisión Go/No-Go
---

Lee CLAUDE.md, docs/03, docs/05 (épica E6), docs/06 sección 2, los ADR de docs/decisions/ (en especial ADR-0006) y la sección 5.3 del brief. Implementa el Excel de fichas resumen (Excel 2) en modules/review_excel, reutilizando la infraestructura del Excel 1.

1. Migraciones (Alembic, esquema app): field_overrides y requirement_reviews (docs/03). La tabla bids ya existe desde /p5: no se crea aquí.
2. Hoja "Resumen" (una fila por postulación analizada) según docs/06 sección 2.1: código con link a la ficha, nombre, organismo, presupuesto (moneda, con/sin impuestos), plazo de ejecución, plazo de implementación, soporte/SLA, garantías, multas (resumen), criterios con ponderación, requisitos excluyentes (total y cuántos pendientes o no cumple), fechas clave en hora de Chile, semáforo, recomendación, motivo del semáforo y columnas de decisión: Go / No-Go / Más información, motivo, comentario, responsable, Verificador oculto.
3. Una hoja de detalle por licitación (nombre de hoja = código) según docs/06 sección 2.2: objeto y alcance; tabla de requisitos excluyentes y deseables con documento, página y estado de cumplimiento editable (cumple / no cumple / pendiente de evidencia / requiere interpretación); criterios y ponderaciones; garantías, multas y pagos; documentos y anexos solicitados; fechas del foro; riesgos; datos no encontrados y contradicciones. Columnas "Valor corregido" y "Comentario" editables.
4. Reglas visuales: "No encontrado", "No verificado", contradicciones y valores corregidos por persona con el color y la nota de docs/06; cada valor con su referencia (documento, página). Semáforo y recomendación calculados en el backend con las reglas de docs/06 sección 2.4 y umbrales configurables en scoring_profiles.thresholds (provisionales).
5. Importación según docs/06 sección 2.3, con las mismas validaciones de archivo y fila del Excel 1: decisiones Go/No-Go, valores corregidos y estados de cumplimiento. Las correcciones humanas se guardan en field_overrides y requirement_reviews (por fingerprint), quedan registradas como tales y no se pisan en un reanálisis.
6. Al exportar una postulación en el Excel 2, su bids.status pasa de "en_analisis" a "pendiente_decision" (docs/02 sección 3.2). La decisión Go/No-Go actualiza bids.status (y bids.go_decision) de la postulación existente, con historial en review_decisions (gate c2) y audit_events: Go → "aprobada_participar"; No-Go → "no_participar"; Más información → "pendiente_decision".
7. Pruebas (docs/07, sección /p8): ficha con campos faltantes, contradicción entre documentos, ida y vuelta de decisiones, corrección humana que sobrevive a un reanálisis, recorrido de todas las celdas de origen IA (cita verificada o marca), reglas del semáforo.

Al terminar: genera el Excel 2 con las licitaciones reales analizadas, déjalo en data/exports/ y detente.
