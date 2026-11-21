---
description: MVP-2 – Extracción y análisis IA con citas verificadas
---

Lee CLAUDE.md, docs/03, docs/05 y las secciones 5.3, 6.3 y 8 del brief. Implementa el análisis documental en modules/documents y modules/analysis.

1. Extracción de texto y tablas con la librería aprobada en docs/01, conservando número de página (PDF), sección o encabezado (DOCX) y hoja/celda (XLSX). OCR solo si la página no tiene texto. Guarda fragmentos en document_chunks con su ubicación.
2. Clasificación de cada documento: bases administrativas, bases técnicas, anexo/formulario, aclaración, modificación, otro.
3. Esquemas Pydantic para la extracción (ver ejemplo de la sección 8 del brief). Cada campo de la ficha (presupuesto con moneda e impuestos, plazo de ejecución, plazo de implementación, soporte/SLA, garantías, multas, condiciones de pago, fechas clave, criterios y ponderaciones, requisitos excluyentes y deseables, documentos solicitados, riesgos) tiene: valor, estado (encontrado / no_encontrado / ambiguo), documento, página o sección, cita textual corta.
4. Capa de proveedor LLM con interfaz única (para comparar proveedores en /p9-evals). Prompts versionados en prompt_templates. El texto de los documentos va delimitado como DATOS NO CONFIABLES; el modelo no tiene herramientas ni acciones. La clave del proveedor se lee de .env desde el código.
5. Estrategia de contexto: si las bases son largas, procesa por secciones o recupera fragmentos relevantes por campo; documenta la estrategia elegida.
6. Verificación determinística de citas: para cada valor, comprueba que la cita exista en el fragmento y la página indicados (normalizando espacios, saltos de línea y guiones). Si no existe → estado "no_verificado". Nunca completar un campo sin cita.
7. Contradicciones: si dos documentos dan valores distintos para un mismo campo, registra ambos, prioriza el más reciente y márcalo.
8. Guarda cada corrida en analysis_runs (modelo, versión de prompt, duración, tokens, costo) y los resultados en extracted_fields, requirements y evaluation_criteria. Registra costo en ai_usage.
9. Ejecución asíncrona al marcar "carga completa"; reintento manual; estado visible en la UI.
10. Pruebas con 2 bases de ejemplo en fixtures, marcadas como datos de prueba: extracción, verificación de citas (incluye una cita falsa que debe quedar no_verificada), campo inexistente que debe quedar no_encontrado, y un documento con instrucciones maliciosas que el sistema debe ignorar.

Al terminar: ejecuta el análisis sobre una licitación real que yo haya cargado, muéstrame los campos extraídos con su cita y estado, el costo de la corrida, y detente.
