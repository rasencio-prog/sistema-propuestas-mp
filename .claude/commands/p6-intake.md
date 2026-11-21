---
description: MVP-2 – Carga asistida de adjuntos
---

Lee CLAUDE.md, docs/03 y docs/05. Implementa la carga asistida de adjuntos en modules/intake. Recordatorio: el sistema NUNCA descarga desde el portal; una persona baja los archivos.

1. Migración: opportunity_documents (hash SHA-256, nombre original, tipo, tamaño, origen "carga asistida", usuario, fecha, versión, ruta en almacenamiento) con restricción única por oportunidad + hash.
2. Al importar una decisión "Descargar", crea la carpeta intake/<código>/ (en el almacenamiento definido en docs/01; en local, una carpeta del proyecto) y un registro pendiente.
3. Dos vías de entrada:
   a. Carpeta vigilada: un proceso detecta archivos nuevos en intake/<código>/, espera a que terminen de copiarse y los procesa.
   b. Carga desde la UI: pantalla "Carga de documentos" con las oportunidades pendientes (código, nombre, cierre, link a la ficha) y arrastrar y soltar varios archivos a la vez.
4. Procesamiento de cada archivo: validar extensión y tipo real (PDF, DOCX, XLSX, DOC, XLS, ZIP); si es ZIP, descomprimir con límites de tamaño y cantidad y rechazar rutas peligrosas; calcular hash; detectar duplicados; mover al almacenamiento definitivo; registrar en opportunity_documents y audit_events.
5. Al cargar el primer documento, el estado interno pasa a "en análisis" y se actualiza la columna "Adjuntos cargados" para el próximo Excel. Botón "Marcar carga completa" que habilita el análisis.
6. Si una licitación recibe aclaraciones o nuevos archivos después, se versionan y se marca "requiere reanálisis".
7. Pruebas: archivo duplicado, ZIP con subcarpetas, tipo falso (exe renombrado a pdf), archivo a medio copiar, carga en oportunidad no aprobada (debe rechazarse).

Al terminar: dime los pasos para probarlo con una licitación real y detente.
