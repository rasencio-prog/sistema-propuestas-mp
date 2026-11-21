---
description: Validación de la API de Mercado Público con ticket real
---

Lee CLAUDE.md y docs/. Objetivo: validar la API pública de Mercado Público con el ticket real antes de diseñar el adaptador definitivo. El ticket está en la variable MP_TICKET del archivo .env: léelo solo desde el código con python-dotenv; no abras ni muestres el .env.

1. Revisa la documentación oficial vigente en https://www.chilecompra.cl/api/ y anota las fuentes consultadas.
2. Crea un script exploratorio en scripts/explore_mp_api.py (no es código de producción) que:
   a. Consulte el listado de licitaciones de un día reciente.
   b. Tome 5 códigos de ese listado, idealmente de rubros TI, y consulte el detalle por código.
   c. Mida cuántas solicitudes consume y respete un ritmo prudente (máx. 1 solicitud por segundo).
   Dame el comando para que yo lo ejecute, o ejecútalo tú si tienes permiso.
3. Guarda las respuestas en docs/api-samples/ saneadas: elimina el ticket de URLs y cabeceras.
4. Escribe docs/10-api-validada.md con:
   - Endpoints y parámetros confirmados, con ejemplo de llamada (ticket como <TICKET>).
   - Tabla de campos reales del listado y del detalle: nombre, tipo, ejemplo, si viene vacío con frecuencia.
   - Qué columnas del Excel 1 (docs/06) se pueden llenar con la API y cuáles no: monto estimado y su visibilidad, tipo de licitación, fechas disponibles con su formato y zona horaria, códigos de estado, rubros de los ítems, organismo y región.
   - Si la API entrega alguna URL de la ficha o de adjuntos.
   - Formato de URL de la ficha pública: arma el link con el patrón https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=<código> SIN acceder al portal. Yo abriré 2 links a mano para confirmar.
   - Errores observados, tiempos de respuesta y consumo de cuota.
   - Impacto en el diseño: lista concreta de ajustes a docs/03, docs/05 y docs/06.
5. Actualiza los documentos de docs/ marcados "A VALIDAR EN /p2-api".

No accedas al portal mercadopublico.cl de forma automatizada: solo a la API. Al terminar, resume hallazgos y ajustes, dame 2 links de ficha para probar y detente.
