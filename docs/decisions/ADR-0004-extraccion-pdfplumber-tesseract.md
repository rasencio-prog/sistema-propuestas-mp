# ADR-0004 · Extracción con pdfplumber + Tesseract; Docling como plan B

- Estado: Aceptada (desvío del brief aprobado por el propietario)
- Fecha: 21-11-2026

## Contexto
El brief sugiere Docling. Docling extrae muy bien las tablas, pero depende de PyTorch y de modelos (imagen de varios GB,
lento en CPU). Las bases TI son mayoritariamente PDF con texto y el volumen es bajo. PyMuPDF se descarta por licencia AGPL.

## Decisión
- PDF con texto: `pdfplumber` (texto y tablas, con página).
- Páginas sin texto: render con `pypdfium2` + **Tesseract 5** (`spa`) vía `pytesseract`, solo en esas páginas.
- DOCX: `python-docx`; XLSX: `openpyxl`; DOC/XLS/RTF: conversión con LibreOffice headless en el worker.
- Todo detrás de la interfaz `DocumentExtractor`.
- **Docling queda como plan B documentado**: se activa detrás de la misma interfaz solo si el conjunto de evaluación
  muestra que la extracción de tablas no alcanza el umbral, y requiere nueva aprobación por ser dependencia grande.
- **Pruebas obligatorias**: cada fragmento conserva su número de página (incluidas páginas con OCR y PDF con portada sin
  numerar), su sección (DOCX) o su hoja y celda (XLSX); las tablas se extraen con filas y columnas, incluida una tabla
  que cruza de página.

## Consecuencias
- Imagen del worker más liviana (Tesseract + LibreOffice, sin PyTorch).
- Riesgo de menor calidad en tablas complejas, medido en `/p9` y mitigado por el plan B.
