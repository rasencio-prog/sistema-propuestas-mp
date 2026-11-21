---
description: MVP-2 – Carga asistida de adjuntos
---

Lee CLAUDE.md, docs/01 (sección 2.3), docs/03, docs/05 (épica E4) y los ADR de docs/decisions/ (en especial ADR-0006 y ADR-0008). Implementa la carga asistida de adjuntos en modules/intake. Recordatorio: el sistema NUNCA descarga desde el portal; una persona baja los archivos.

1. Migración (Alembic, esquema app): opportunity_documents (hash SHA-256, nombre original, tipo, tamaño, origen, usuario, fecha, versión, ruta en almacenamiento), ligada a la postulación (bid_id), con restricción única por postulación + hash.
2. La postulación (bids), su document_intakes y la carpeta intake/<código>/ ya los crea /p5 al importar "Descargar". Aquí se reciben los archivos: la carpeta vive bajo INTAKE_ROOT (configurable; por defecto data/intake/, excluida de git) y el almacenamiento definitivo es Supabase Storage detrás de la interfaz FileStorage (docs/01 sección 2.3).
3. Dos vías de entrada:
   a. Carpeta vigilada: un trabajo del worker (Procrastinate) detecta archivos nuevos en intake/<código>/, espera a que terminen de copiarse y los procesa. Solo funciona donde corre el worker (hoy, el equipo del propietario).
   b. Carga desde la UI: pantalla "Carga de documentos" con las postulaciones pendientes (código, nombre, cierre, link a la ficha) y arrastrar y soltar varios archivos a la vez.
4. Procesamiento de cada archivo: validar extensión y tipo real (PDF, DOCX, XLSX, DOC, XLS, ZIP); si es ZIP, descomprimir con límites de tamaño, cantidad y razón de compresión y rechazar rutas peligrosas; calcular hash; detectar duplicados; copiar al almacenamiento definitivo y mover el original a intake/<código>/_procesados/; registrar en opportunity_documents y audit_events.
5. Al cargar el primer documento, bids.status pasa a "en_analisis" y se actualiza la columna "Adjuntos cargados" para el próximo Excel. Botón "Marcar carga completa" que habilita el análisis.
6. Si una licitación recibe aclaraciones o nuevos archivos después, se versionan y se marca bids.requires_reanalysis.
7. Pruebas (docs/07, sección /p6): archivo duplicado, ZIP con subcarpetas, tipo falso (exe renombrado a pdf), archivo a medio copiar, carga en oportunidad sin postulación (sin "Descargar"; debe rechazarse), documento tardío que crea nueva versión.

Al terminar: dime los pasos para probarlo con una licitación real y detente.
