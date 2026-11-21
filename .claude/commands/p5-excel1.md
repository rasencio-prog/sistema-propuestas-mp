---
description: MVP-1 – Excel 1 de preselección (exportar e importar)
---

Lee CLAUDE.md, docs/03, docs/05 (épica E3), docs/06-excel-especificacion.md y los ADR de docs/decisions/ (en especial ADR-0006). Implementa la exportación e importación del Excel de preselección (Excel 1) en modules/review_excel.

1. Migraciones (Alembic, esquema app): review_batches, review_batch_items, review_imports, review_decisions, bids y document_intakes (docs/03). La tabla bids se crea en esta etapa porque nace con la decisión "Descargar" (ADR-0006).
2. Selección del lote exactamente según docs/06 sección 1.0:
   - Universo: oportunidades en "detectada", o "preseleccionada" con decisión vigente "Dudoso" o sin decisión.
   - Filtros duros: estado oficial Publicada y cierre de ofertas a 3 días o más desde la corrida. Sin filtro de monto, región ni organismo. Fecha de cierre no interpretable: entra con alerta, no se descarta.
   - Entran las 50 de mayor puntaje más todas con puntaje >= 40 (unión). Todos los valores configurables en scoring_profiles.thresholds y registrados en _control.
   - Al exportar, las incluidas pasan a internal_status "preseleccionada".
3. Exportación con openpyxl, exactamente según docs/06 sección 1:
   - Hoja "Oportunidades" con una fila por candidata, ordenada por puntaje descendente; hoja "Instrucciones" en español; hojas muy ocultas "_listas" y "_control" (lote, versión, fecha, organización, regla de selección usada, firma).
   - Columna "Link a la ficha" como hipervínculo clicable; columna "Carpeta destino" con intake/<código>/; columna "Adjuntos cargados"; columna oculta "Verificador" (row_token).
   - Columnas del sistema bloqueadas (hoja protegida sin contraseña que estorbe el uso normal); columnas editables con listas cerradas: Decisión (Descargar / Descartar / Dudoso), Motivo (lista), Comentario (texto libre), Responsable.
   - Fechas en hora de Chile, días corridos y hábiles al cierre y formato condicional para cierres próximos (umbrales configurables). Filtros automáticos y paneles inmovilizados.
   - Nombre de archivo: preseleccion_<AAAA-MM-DD>_lote<N>_v<versión>.xlsx.
4. Importación según docs/06 sección 1.4:
   - Valida archivo, firma de _control, lote, organización y que sea la última versión del lote; la llave es el código de licitación más el Verificador.
   - Rechaza por fila (sin perder las válidas): código alterado o inexistente en el lote, decisión fuera de lista, fila duplicada, Descartar sin Motivo, Descargar sin Responsable. Motivo obligatorio solo en Descartar; Responsable obligatorio solo en Descargar; Dudoso sin campos obligatorios.
   - Registra cada decisión con usuario y fecha en review_decisions y en audit_events. Si ya había decisión, guarda historial con previous_decision_id (no sobrescribe en silencio). El mismo archivo importado dos veces no duplica nada.
   - Efectos, en una transacción:
     - Descargar → opportunities.internal_status "documentos_pendientes" + se crea la postulación en bids (status "documentos_pendientes", responsable, created_by_decision_id enlazado a la decisión) + document_intakes + carpeta intake/<código>/ bajo INTAKE_ROOT.
     - Descartar → "descartada_preseleccion".
     - Dudoso → sigue "preseleccionada" y vuelve en el próximo lote.
     - Revertir un "Descargar" solo si la postulación sigue en "documentos_pendientes" sin documentos: la postulación pasa a "desistida" (no se borra). Si ya avanzó, la fila se rechaza.
   - Devuelve un informe de importación: aceptadas, sin cambio, sin decisión y rechazadas con motivo por fila (pantalla y CSV).
5. UI mínima (pantalla "Lotes y ejecuciones"): generar y descargar Excel 1, subir el Excel con decisiones, ver el informe de importación.
6. Validación de archivos subidos: solo xlsx, tamaño máximo, sin macros ni vínculos externos.
7. Pruebas (docs/07, sección /p5): selección del lote (casos de 30, 80/20 y 80/65 candidatas); ida y vuelta completa; filas alteradas; lote equivocado; versión anterior; decisiones repetidas; obligatoriedad de Motivo y Responsable; Dudoso vacío aceptado; creación de exactamente una postulación por "Descargar"; reversión a "desistida"; fechas en hora de Chile.

Al terminar: genera un Excel 1 con los datos reales capturados, déjalo en data/exports/ y detente. Yo lo marcaré y te lo devolveré para probar la importación.
