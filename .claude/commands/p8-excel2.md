---
description: MVP-2 – Excel 2 de fichas resumen y decisión Go/No-Go
---

Lee CLAUDE.md, docs/06 y la sección 5.3 del brief. Implementa el Excel de fichas resumen (Excel 2) en modules/review_excel, reutilizando la infraestructura del Excel 1.

1. Hoja "Resumen" (una fila por licitación analizada): código con link a la ficha, nombre, organismo, presupuesto (moneda, con/sin impuestos), plazo de ejecución, plazo de implementación, soporte/SLA, garantías, multas (resumen), criterios con ponderación, requisitos excluyentes (total y cuántos pendientes o no cumple), fechas clave en hora de Chile, semáforo, recomendación y columnas de decisión: Go / No-Go / Más información, motivo, responsable.
2. Una hoja de detalle por licitación (nombre de hoja = código): objeto y alcance; tabla de requisitos excluyentes y deseables con documento, página y estado de cumplimiento editable (cumple / no cumple / pendiente de evidencia / requiere interpretación); criterios y ponderaciones; garantías, multas y pagos; documentos y anexos solicitados; fechas del foro; riesgos; datos no encontrados y contradicciones.
3. Reglas visuales: "No encontrado", "No verificado" y contradicciones con color destacado y nota; cada valor con su referencia (documento, página); semáforo calculado en el backend con reglas configurables (p. ej. rojo si hay un excluyente en "no cumple" o el cierre es en menos de N días).
4. Importación: decisiones Go/No-Go y estados de requisitos corregidos por el revisor, con las mismas validaciones del Excel 1. Las correcciones humanas quedan registradas como tales y no se pisan en un reanálisis.
5. Estados internos: Go → "aprobada para participar"; No-Go → "no participar"; Más información → "pendiente de decisión".
6. Crear la tabla bids (postulaciones) al registrar Go, como base para MVP-3.
7. Pruebas: ficha con campos faltantes, contradicción entre documentos, ida y vuelta de decisiones, corrección humana que sobrevive a un reanálisis.

Al terminar: genera el Excel 2 con las licitaciones reales analizadas, déjalo en exports/ y detente.
