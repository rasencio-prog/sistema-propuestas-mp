---
description: Etapa 0 – Descubrimiento y plan (sin código)
---

Lee CLAUDE.md, docs/00-decisiones-propietario.md y el brief completo en docs/brief/. Actúa como arquitecto de software senior. En esta sesión NO escribas código de la aplicación: solo documentos de diseño en docs/.

Lo marcado PENDIENTE en docs/00-decisiones-propietario.md debes proponerlo con justificación.

Entrega estos archivos:
1. docs/01-decisiones-tecnicas.md: stack recomendado para 1-3 usuarios, comparando la arquitectura del brief (FastAPI + Celery/Redis + MinIO) con la alternativa liviana (Postgres gestionado + cola sobre Postgres). Recomienda una y justifica en costo, complejidad y operación. Incluye librerías concretas: extracción PDF/DOCX/XLSX, OCR, Excel (openpyxl), migraciones, scheduler, cliente LLM.
2. docs/02-arquitectura.md: diagrama (Mermaid) de componentes y del flujo de las secciones 5.1 y 7 del brief, con las 3 compuertas humanas.
3. docs/03-modelo-datos.md: diagrama ER (Mermaid) basado en la sección 11 del brief, limitado a lo que necesitan MVP-1 y MVP-2, con claves, índices y restricciones únicas. Marca qué tablas quedan para MVP-3.
4. docs/04-estructura-repo.md: árbol de carpetas basado en la sección 21, ajustado a tu recomendación.
5. docs/05-backlog.md: épicas e historias de usuario para MVP-1 y MVP-2, cada una con criterios de aceptación verificables (usa los de la sección 17), estimación S/M/L y dependencias. Ordénalas según los comandos /p3 a /p9.
6. docs/06-excel-especificacion.md: especificación columna por columna del Excel 1 (sección 5.2) y Excel 2 (sección 5.3): nombre, tipo, origen, protegida sí/no, validación, formato condicional. Agrega en el Excel 1 las columnas "Carpeta destino" (intake/<código>/) y "Adjuntos cargados (Sí/No)". Define la hoja oculta de control (lote, versión, fecha) y las reglas de reimportación.
7. docs/07-plan-pruebas.md: pruebas unitarias, de integración y de aceptación por etapa, incluyendo zona horaria con cambio de horario y el conjunto de evaluación.
8. docs/08-riesgos.md: riesgos y dependencias con mitigación.
9. docs/09-preguntas.md: preguntas imprescindibles para mí, máximo 10, ordenadas por impacto.

No inventes endpoints ni campos de la API: donde no estén confirmados escribe "A VALIDAR EN /p2-api". Al terminar, dame un resumen de 10 líneas con tu recomendación de stack y las preguntas, y detente a esperar mi aprobación.
