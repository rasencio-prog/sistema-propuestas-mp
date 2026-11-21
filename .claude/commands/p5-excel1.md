---
description: MVP-1 – Excel 1 de preselección (exportar e importar)
---

Lee CLAUDE.md y docs/06-excel-especificacion.md. Implementa la exportación e importación del Excel de preselección (Excel 1) en modules/review_excel.

1. Migraciones: review_batches y review_decisions (docs/03).
2. Exportación con openpyxl, exactamente según docs/06:
   - Hoja "Oportunidades" con una fila por candidata, ordenada por puntaje descendente; hoja "Instrucciones" en español; hoja oculta "_control" con id de lote, versión, fecha y organización.
   - Columna "Link a la ficha" como hipervínculo clicable; columna "Carpeta destino" con intake/<código>/; columna "Adjuntos cargados".
   - Columnas del sistema bloqueadas (hoja protegida sin contraseña que estorbe el uso normal); columnas de decisión editables con listas cerradas: Decisión (Descargar / Descartar / Dudoso), Motivo (lista + texto libre), Responsable.
   - Fechas en hora de Chile, días restantes y formato condicional para cierres próximos (umbral configurable). Filtros automáticos y encabezado inmovilizado.
   - Nombre de archivo: preseleccion_<AAAA-MM-DD>_lote<N>_v<versión>.xlsx.
3. Importación:
   - Valida lote y versión con la hoja _control; la llave es el código de licitación.
   - Rechaza por fila (sin perder las válidas): código alterado o inexistente, decisión fuera de lista, fila duplicada.
   - Registra cada decisión con usuario y fecha en review_decisions y en audit_events. Si ya había decisión, guarda historial (no sobrescribe en silencio).
   - Estado interno: Descargar → "documentos pendientes"; Descartar → "descartada en preselección"; Dudoso → se mantiene para el próximo lote.
   - Devuelve un informe de importación: aceptadas y rechazadas con motivo por fila.
4. UI mínima (pantalla "Lotes y ejecuciones"): generar y descargar Excel 1, subir el Excel con decisiones, ver el informe de importación.
5. Validación de archivos subidos: tipo, tamaño máximo, xlsx válido sin macros.
6. Pruebas: ida y vuelta completa; filas alteradas; lote equivocado; decisiones repetidas; fechas en hora de Chile.

Al terminar: genera un Excel 1 con los datos reales capturados, déjalo en exports/ y detente. Yo lo marcaré y te lo devolveré para probar la importación.
