# 03 · Modelo de datos (MVP-1 y MVP-2)

Base: sección 11 del brief, limitado a lo que necesitan MVP-1 y MVP-2. Las tablas de MVP-3 se listan al final.

Estado: **APROBADO con cambios** (21-11-2026, ADR-0006). Cambios respecto de la propuesta:
- El estado interno del embudo, el puntaje y la clasificación viven en `opportunities` (`internal_status`, `score`, …).
- `bid_service_lines` pasa a llamarse `opportunity_service_lines`.
- `bids` (postulación) se crea **solo** cuando la Compuerta 1 decide "Descargar"; su campo se llama `status`.
- `review_batch_items` y `review_decisions` se refieren a la oportunidad; `bid_id` solo es obligatorio en la Compuerta 2.
- Nueva clave `ai_monthly_budget_usd` / `ai_budget_alert_pct` en `organizations.settings` y estado
  `blocked_budget` en `analysis_runs`.

## 1. Convenciones

- PostgreSQL 15+ (Supabase), esquema **`app`** (no expuesto por la Data API) con RLS activado y sin políticas.
- Identificadores internos `uuid` (`gen_random_uuid()`); el código oficial de Mercado Público va en un campo separado.
  Excepciones: `audit_events` y `api_call_log` usan `bigint identity` (alto volumen, solo inserción).
- Fechas: `timestamptz` siempre en UTC. Las fechas oficiales guardan además el **texto original** publicado.
- Columnas comunes: `created_at`, `updated_at` (`timestamptz`, default `now()`); borrado lógico `deleted_at` donde se indica.
- Listas cerradas como `text` + `CHECK` (más fáciles de migrar que `ENUM`).
- Multiempresa: hoy hay una sola organización. Los datos públicos de `opportunities` y `buyers` son globales, pero
  `opportunities` también guarda el estado del embudo, el puntaje y la clasificación, que dependen de la organización
  (decisión del propietario, ADR-0006). Al habilitar multiempresa esos campos se mueven, por migración, a una tabla por
  organización. Postulaciones, documentos y análisis ya llevan `organization_id` (directo o vía `bids`).
- Nombres de campos de la API de Mercado Público: **confirmados en `/p2-api`**. Las columnas de abajo son el modelo
  canónico interno; el mapeo API → canónico se documenta en `docs/10-api-validada.md`.
- La cola de trabajos (Procrastinate) crea su propio esquema `procrastinate`; no se modela aquí.

## 2. Diagrama ER

```mermaid
erDiagram
    organizations ||--o{ organization_members : tiene
    users ||--o{ organization_members : pertenece
    organizations ||--o{ api_credentials : posee
    organizations ||--o{ service_lines : configura
    organizations ||--o{ scoring_profiles : configura
    organizations ||--o{ radar_runs : ejecuta
    organizations ||--o{ audit_events : registra
    api_credentials ||--o{ api_quota_usage : consume
    api_credentials ||--o{ api_call_log : registra
    radar_runs ||--o{ api_call_log : agrupa

    buyers ||--o{ opportunities : compra
    opportunities ||--o{ opportunity_items : contiene
    opportunities ||--o{ opportunity_dates : tiene
    opportunities ||--o{ opportunity_changes : cambia
    opportunities ||--o| opportunity_ai_summaries : "resumen IA (ADR-0011)"

    scoring_profiles ||--o{ opportunities : puntua
    opportunities ||--o{ opportunity_service_lines : clasifica
    service_lines ||--o{ opportunity_service_lines : asigna

    review_batches ||--o{ review_batch_items : incluye
    opportunities ||--o{ review_batch_items : aparece
    review_batches ||--o{ review_imports : recibe
    review_imports ||--o{ review_decisions : produce
    opportunities ||--o{ review_decisions : decide

    organizations ||--o{ bids : postula
    opportunities ||--o| bids : "pasa a postulacion"
    review_decisions ||--o| bids : "Descargar crea"
    bids ||--o{ review_decisions : "C2 decide"

    bids ||--o| document_intakes : habilita
    bids ||--o{ opportunity_documents : documenta
    opportunity_documents ||--o{ document_chunks : fragmenta

    bids ||--o{ analysis_runs : analiza
    prompt_templates ||--o{ analysis_runs : usa
    analysis_runs ||--o{ extracted_fields : produce
    analysis_runs ||--o{ requirements : produce
    analysis_runs ||--o{ evaluation_criteria : produce
    analysis_runs ||--o{ ai_usage : cuesta
    extracted_fields ||--o{ evidence_links : cita
    requirements ||--o{ evidence_links : cita
    evaluation_criteria ||--o{ evidence_links : cita
    opportunity_documents ||--o{ evidence_links : fuente
    document_chunks ||--o{ evidence_links : fragmento
    bids ||--o{ field_overrides : corrige
    bids ||--o{ requirement_reviews : revisa

    organizations {
        uuid id PK
        text legal_name
        text rut UK
        jsonb settings
        timestamptz deleted_at
    }
    users {
        uuid id PK
        uuid auth_user_id UK "Supabase auth.users.id"
        citext email UK
        text full_name
        text status "active|disabled"
        text auth_provider
        timestamptz deleted_at
    }
    organization_members {
        uuid organization_id PK,FK
        uuid user_id PK,FK
        text role "admin|commercial|reviewer|read_only"
    }
    api_credentials {
        uuid id PK
        uuid organization_id FK
        text provider "mercado_publico"
        bytea ticket_encrypted "Fernet"
        text holder_name
        date valid_until
        int daily_limit "<=10000, default 8000"
        int max_rps
        bool is_active
    }
    api_quota_usage {
        uuid credential_id PK,FK
        date quota_date PK "dia de cuota, A VALIDAR"
        int requests_count
    }
    api_call_log {
        bigint id PK
        uuid credential_id FK
        uuid radar_run_id FK
        text endpoint_name "logico, sin ticket"
        jsonb params_sanitized
        int http_status
        int duration_ms
        int attempt
        text correlation_id
        text error
        timestamptz called_at
    }
    radar_runs {
        uuid id PK
        uuid organization_id FK
        date radar_date
        text trigger "scheduled|manual"
        text status "running|succeeded|partial|failed"
        int requests_used
        int listed_count
        int new_count
        int updated_count
        int detailed_count
        jsonb errors
    }
    service_lines {
        uuid id PK
        uuid organization_id FK
        text name
        text description
        text_arr positive_keywords
        text_arr exclusion_keywords
        text_arr category_codes "rubros"
        bool is_active
        timestamptz deleted_at
    }
    scoring_profiles {
        uuid id PK
        uuid organization_id FK
        int version
        jsonb weights
        jsonb thresholds
        bool is_active
    }
    buyers {
        uuid id PK
        text source
        text organism_code "= Comprador.CodigoOrganismo, confirmado /p2-api"
        text organism_name
        text unit_code "= Comprador.CodigoUnidad, confirmado /p2-api"
        text unit_name
        text unit_rut "= Comprador.RutUnidad, confirmado /p2-api"
        text region
        text commune
    }
    opportunities {
        uuid id PK
        text source "mercado_publico"
        text official_code UK
        text opportunity_type_code "= Tipo; valores L1/LE/LP/LQ/LR/E2/CO/B2/H2/I2/LS, confirmado /p2-api"
        text opportunity_type_text
        text title
        text description
        uuid buyer_id FK
        numeric estimated_amount "null si no visible"
        text currency
        text amount_visibility "visible|not_visible|unknown"
        int official_status_code
        text official_status_text
        bool official_status_documented "false si CodigoEstado no está en la tabla conocida (ej. 15, 16 observados en /p2-api); genera alerta en el log, nunca falla"
        text internal_status "embudo hasta C1"
        timestamptz internal_status_changed_at
        numeric score "0-100"
        jsonb score_breakdown
        uuid scoring_profile_id FK
        text classification_justification
        timestamptz classified_at
        text source_url "link construido a la ficha"
        int contract_duration_value "= TiempoDuracionContrato, confirmado /p2-api"
        int contract_duration_unit_code "= UnidadTiempoDuracionContrato; tabla 3.6 del manual (1 Horas...5 Años)"
        bool is_renewable "= EsRenovable"
        int renewal_value "= ValorTiempoRenovacion; casi siempre vacío en la muestra"
        text renewal_period_text "= PeriodoTiempoRenovacion; siempre null en la muestra"
        bool subcontracting_allowed "= SubContratacion"
        int contract_formalization_code "= Contrato (1 requiere suscripción, 2 formaliza con OC; solo visible en tipo LE)"
        int payment_modality_code "= Modalidad; tabla 3.4 del manual"
        text payment_type_code "= TipoPago; se vio '-1' no documentado, guardar crudo"
        text contract_responsible_name "= NombreResponsableContrato"
        text contract_responsible_email "= EmailResponsableContrato; viene '' casi siempre"
        text contract_responsible_phone "= FonoResponsableContrato; viene '' casi siempre"
        text payment_responsible_name "= NombreResponsablePago"
        text payment_responsible_email "= EmailResponsablePago; viene '' casi siempre"
        int buyer_complaints_count_snapshot "= CantidadReclamos; cuenta del organismo al momento de la consulta, no exclusiva de esta licitación"
        bool is_standard_type "= EsBaseTipo"
        int award_act_type_code "= Adjudicacion.Tipo; tabla 3.7 del manual; null salvo Adjudicada"
        text award_act_number "= Adjudicacion.Numero"
        int award_offerors_count "= Adjudicacion.NumeroOferentes"
        text award_act_url "= Adjudicacion.UrlActa; URL real de la propia API a mercadopublico.cl, no es scraping"
        jsonb raw_list "saneado"
        jsonb raw_detail "saneado"
        text content_hash
        timestamptz detail_fetched_at
        timestamptz first_seen_at
        timestamptz last_seen_at
    }
    opportunity_items {
        uuid id PK
        uuid opportunity_id FK
        int line_no
        int product_code "código ONU/UNSPSC = Items.Listado[].CodigoProducto, confirmado /p2-api"
        text category_code "rubro UNSPSC = Items.Listado[].CodigoCategoria; solo en el detalle, confirmado /p2-api"
        text category_name
        text product_name
        text description "= Items.Listado[].Descripcion, confirmado /p2-api"
        numeric quantity
        text unit
    }
    opportunity_dates {
        uuid id PK
        uuid opportunity_id FK
        text date_type
        timestamptz value_utc "null si no parseable"
        text original_text
        text source_field
        text parse_status "ok|unparseable|missing"
    }
    opportunity_changes {
        uuid id PK
        uuid opportunity_id FK
        uuid radar_run_id FK
        text change_type "status|date|amount|other"
        text field
        jsonb old_value
        jsonb new_value
        bool requires_reanalysis
        timestamptz detected_at
    }
    opportunity_ai_summaries {
        uuid id PK
        uuid opportunity_id FK UK
        text summary_text
        text model "ej. claude-haiku-5-5"
        text prompt_version
        text content_hash "= opportunities.content_hash al momento de generar; no se regenera si no cambia"
        text status "generado|no_generado_presupuesto|desactivado"
        uuid ai_usage_id FK
        timestamptz generated_at
    }
    bids {
        uuid id PK
        uuid organization_id FK
        uuid opportunity_id FK,UK
        uuid created_by_decision_id FK "decision C1 Descargar"
        text status "desde documentos_pendientes"
        uuid assignee_user_id FK
        text go_decision "null|go|no_go|more_info"
        uuid current_analysis_run_id FK
        bool requires_reanalysis
        timestamptz status_changed_at
    }
    opportunity_service_lines {
        uuid opportunity_id PK,FK
        uuid service_line_id PK,FK
        text method PK "rules|llm"
        text_arr matched_terms
        text_arr matched_codes
        numeric confidence
        text justification
    }
    review_batches {
        uuid id PK
        uuid organization_id FK
        text batch_type "preselection|summary"
        int batch_number
        int version
        text format_version
        text file_name
        text storage_path
        text file_sha256
        int row_count
        uuid exported_by FK
        timestamptz exported_at
        text status "exported|superseded|closed"
    }
    review_batch_items {
        uuid batch_id PK,FK
        uuid opportunity_id PK,FK
        uuid bid_id FK "solo Excel 2"
        int row_number
        text row_token "HMAC"
        jsonb snapshot
    }
    review_imports {
        uuid id PK
        uuid batch_id FK
        text file_sha256
        text file_name
        uuid imported_by FK
        int accepted_count
        int rejected_count
        jsonb report
        text status
    }
    review_decisions {
        uuid id PK
        uuid import_id FK
        uuid batch_id FK
        uuid opportunity_id FK
        uuid bid_id FK "obligatorio en c2"
        text gate "c1|c2"
        text decision
        text reason_code
        text reason_text
        uuid assignee_user_id FK
        uuid decided_by FK
        timestamptz decided_at
        uuid previous_decision_id FK
        bool is_current
    }
    document_intakes {
        uuid id PK
        uuid bid_id FK,UK
        text folder_path "intake/codigo/"
        text status "pending|receiving|complete"
        timestamptz completed_at
        uuid completed_by FK
    }
    opportunity_documents {
        uuid id PK
        uuid organization_id FK
        uuid bid_id FK
        text original_filename
        text extension
        text mime_type
        bigint size_bytes
        text sha256
        text storage_path
        text origin "ui_upload|watched_folder|zip_member"
        uuid parent_document_id FK "si viene de un ZIP"
        int version
        uuid supersedes_id FK
        text doc_class "bases_adm|bases_tec|anexo|aclaracion|modificacion|otro"
        text status "stored|extracted|failed|rejected"
        uuid uploaded_by FK
        timestamptz uploaded_at
        timestamptz deleted_at
    }
    document_chunks {
        uuid id PK
        uuid document_id FK
        int seq
        int page_number
        text section_path
        text sheet_name
        text cell_range
        text text
        bool is_table
        bool ocr
        numeric ocr_confidence
    }
    prompt_templates {
        uuid id PK
        text name
        int version
        text purpose
        text system_text
        jsonb output_schema
        text status "draft|active|retired"
    }
    analysis_runs {
        uuid id PK
        uuid organization_id FK
        uuid bid_id FK
        text analysis_type
        text provider
        text model
        uuid prompt_template_id FK
        text status "queued|blocked_budget|running|succeeded|failed"
        uuid_arr input_document_ids
        int duration_ms
        jsonb result_json
        text error
        uuid triggered_by FK
    }
    extracted_fields {
        uuid id PK
        uuid analysis_run_id FK
        uuid bid_id FK
        text field_key
        text value_text
        jsonb value_json
        text status "found|not_found|not_verified|ambiguous|contradiction|not_applicable"
        text note
    }
    requirements {
        uuid id PK
        uuid analysis_run_id FK
        uuid bid_id FK
        text fingerprint "hash texto normalizado"
        text text
        text kind "mandatory|desirable"
        text category
        text ai_compliance_status
    }
    requirement_reviews {
        uuid id PK
        uuid bid_id FK
        text fingerprint
        text compliance_status "meets|does_not_meet|pending_evidence|needs_interpretation"
        text comment
        uuid reviewed_by FK
        text source "excel2|ui"
        bool is_current
    }
    field_overrides {
        uuid id PK
        uuid bid_id FK
        text field_key
        text value_text
        jsonb value_json
        text reason
        uuid created_by FK
        bool is_current
    }
    evaluation_criteria {
        uuid id PK
        uuid analysis_run_id FK
        uuid bid_id FK
        text name
        numeric weight_pct
        jsonb subcriteria
        text status
    }
    evidence_links {
        uuid id PK
        uuid extracted_field_id FK
        uuid requirement_id FK
        uuid criterion_id FK
        uuid document_id FK
        uuid chunk_id FK
        int page_number
        text section_path
        text cell_ref
        text quote
        bool verified
        text verification_method
    }
    ai_usage {
        uuid id PK
        uuid organization_id FK
        uuid analysis_run_id FK "nulo si el uso es un resumen IA de Excel 1 (ADR-0011)"
        uuid opportunity_id FK "solo para resumen IA de Excel 1 (ADR-0011); nulo en usos de MVP-2"
        text provider
        text model
        int input_tokens
        int output_tokens
        int cache_read_tokens
        int cache_write_tokens
        numeric cost_usd
    }
    audit_events {
        bigint id PK
        uuid organization_id FK
        uuid user_id FK
        text actor_type "user|system"
        text action
        text entity_type
        uuid entity_id
        text request_id
        inet ip
        jsonb metadata
        timestamptz occurred_at
    }
```

## 3. Claves, restricciones e índices

| Tabla | Restricciones únicas / CHECK | Índices adicionales | Etapa |
| --- | --- | --- | --- |
| organizations | `UNIQUE(rut)` (parcial, `deleted_at IS NULL`) | — | p3 |
| users | `UNIQUE(auth_user_id)`, `UNIQUE(email)` | — | p3 |
| organization_members | PK `(organization_id, user_id)`; `CHECK role IN (…)` | `(user_id)` | p3 |
| api_credentials | Parcial `UNIQUE(organization_id, provider) WHERE is_active`; `CHECK daily_limit BETWEEN 1 AND 10000` | — | p3 |
| service_lines | `UNIQUE(organization_id, lower(name)) WHERE deleted_at IS NULL` | GIN en `positive_keywords`, `category_codes` | p3 |
| audit_events | Solo inserción: se revoca `UPDATE/DELETE` al rol de la app | `(organization_id, occurred_at DESC)`, `(entity_type, entity_id)` | p3 |
| scoring_profiles | `UNIQUE(organization_id, version)`; parcial `UNIQUE(organization_id) WHERE is_active` | — | p4 |
| radar_runs | Parcial `UNIQUE(organization_id, radar_date) WHERE status = 'succeeded'` (no corre dos veces el mismo día) | `(organization_id, started_at DESC)` | p4 |
| api_quota_usage | PK `(credential_id, quota_date)`; incremento atómico con `UPDATE … RETURNING` | — | p4 |
| api_call_log | — | `(credential_id, called_at)`, `(radar_run_id)` | p4 |
| buyers | `UNIQUE(source, organism_code, unit_code)` | `(region)` | p4 |
| opportunities | `UNIQUE(source, official_code)` ← deduplicación; `CHECK internal_status IN ('detectada','preseleccionada','descartada_preseleccion','documentos_pendientes','cerrada_sin_decision')`; `CHECK score BETWEEN 0 AND 100` | `(official_status_code)`, `(buyer_id)`, `(internal_status, score DESC)`, GIN trigram en `title` | p4 |
| opportunity_items | `UNIQUE(opportunity_id, line_no)` | `(category_code)` | p4 |
| opportunity_dates | `UNIQUE(opportunity_id, date_type)`; `CHECK date_type IN ('publication','questions_close','answers_publication','offers_close','technical_opening','economic_opening','award_estimated','award_actual','support_physical','evaluation_time','estimated_signature','site_visit','background_delivery','user_dates')` — lista final confirmada en `/p2-api` (docs/10 §8.2) | `(date_type, value_utc)` para "próximos cierres" | p4 |
| opportunity_changes | — | `(opportunity_id, detected_at DESC)` | p4 |
| opportunity_ai_summaries | `UNIQUE(opportunity_id)` | — | p5 (ADR-0011) |
| opportunity_service_lines | PK `(opportunity_id, service_line_id, method)` | `(service_line_id)` | p4 |
| review_batches | `UNIQUE(organization_id, batch_type, batch_number, version)` | — | p5 |
| review_batch_items | PK `(batch_id, opportunity_id)`; `UNIQUE(batch_id, row_number)`; `CHECK` `bid_id` no nulo si el lote es `summary` (validado en servicio) | `(opportunity_id)`, `(bid_id)` | p5 |
| review_imports | `UNIQUE(batch_id, file_sha256)` ← reimportar el mismo archivo es idempotente | — | p5 |
| review_decisions | Parcial `UNIQUE(opportunity_id, gate) WHERE is_current`; `CHECK (gate = 'c1' OR bid_id IS NOT NULL)`; `CHECK` de decisión según `gate` | `(batch_id)`, `(opportunity_id, decided_at DESC)` | p5 (c1) / p8 (c2) |
| bids | `UNIQUE(organization_id, opportunity_id)`; `UNIQUE(created_by_decision_id)`; `CHECK status IN ('documentos_pendientes','en_analisis','pendiente_decision','aprobada_participar','no_participar','en_preparacion','en_revision','aprobada','presentada','adjudicada','no_adjudicada','desistida','cerrada')` | `(organization_id, status)` | p5 (al importar "Descargar") |
| document_intakes | `UNIQUE(bid_id)` | `(status)` | p5 (se crea con "Descargar") |
| opportunity_documents | `UNIQUE(bid_id, sha256)` ← duplicado detectado | `(bid_id, uploaded_at)`, `(organization_id)` | p6 |
| document_chunks | `UNIQUE(document_id, seq)` | `(document_id, page_number)`; GIN `to_tsvector('spanish', text)` | p7 |
| prompt_templates | `UNIQUE(name, version)`; parcial `UNIQUE(name) WHERE status='active'` | — | p7 |
| analysis_runs | — | `(bid_id, created_at DESC)`, `(status)` | p7 |
| extracted_fields | `UNIQUE(analysis_run_id, field_key)`; `CHECK status IN (…)`; `CHECK (status <> 'found' OR value_text IS NOT NULL)` | `(bid_id, field_key)` | p7 |
| requirements | `UNIQUE(analysis_run_id, fingerprint)` | `(bid_id, fingerprint)` | p7 |
| evaluation_criteria | — | `(analysis_run_id)` | p7 |
| evidence_links | `CHECK num_nonnulls(extracted_field_id, requirement_id, criterion_id) = 1` | `(document_id)`, una por cada FK | p7 |
| ai_usage | `CHECK num_nonnulls(analysis_run_id, opportunity_id) = 1` (ADR-0011) | `(organization_id, created_at)` | p7 (MVP-2) / p5 (resumen IA) |
| field_overrides | Parcial `UNIQUE(bid_id, field_key) WHERE is_current` | — | p8 |
| requirement_reviews | Parcial `UNIQUE(bid_id, fingerprint) WHERE is_current` | — | p8 |

Claves foráneas: todas con `ON DELETE RESTRICT` (nada se borra en cascada; se usa borrado lógico), salvo
`document_chunks → opportunity_documents` y `opportunity_service_lines → opportunities`, que son `ON DELETE CASCADE`
por ser derivados recalculables.

## 4. Decisiones de modelado

1. **Estado del embudo en `opportunities`, postulación desde "Descargar"** (decisión del propietario, ADR-0006).
   `opportunities.internal_status` recorre `detectada → preseleccionada → descartada_preseleccion | documentos_pendientes`
   (más `cerrada_sin_decision` si el estado oficial deja de ser Publicada sin decisión). Al importar "Descargar", en la
   misma transacción: la oportunidad pasa a `documentos_pendientes`, se crea `bids` con `status = documentos_pendientes`,
   `created_by_decision_id` y responsable, y se crean `document_intakes` y la carpeta. Desde ahí avanza solo
   `bids.status`; el **estado vigente** que muestran pantallas y Excel es `bids.status` si hay postulación y, si no,
   `opportunities.internal_status`. Cambiar una decisión "Descargar" ya aplicada solo se permite mientras la postulación
   siga en `documentos_pendientes` sin documentos; en ese caso la postulación pasa a `desistida` (no se borra).
2. **Resultados de IA inmutables + correcciones humanas aparte.** `extracted_fields`, `requirements` y
   `evaluation_criteria` cuelgan de una corrida (`analysis_runs`) y nunca se editan. Las correcciones del revisor van a
   `field_overrides` y `requirement_reviews`. La "vista vigente" de una ficha = última corrida exitosa
   (`bids.current_analysis_run_id`) + correcciones vigentes encima. Así un reanálisis **no pisa** correcciones humanas.
3. **Requisitos con huella (`fingerprint`)**: hash del texto normalizado (minúsculas, sin tildes ni espacios extra).
   Permite reconocer el mismo requisito entre corridas y conservar su estado de cumplimiento revisado. Si el texto cambia
   por una modificación de bases, aparece como requisito nuevo y el antiguo se marca "ya no presente".
4. **Una sola tabla de citas** (`evidence_links`) con tres FK opcionales y un `CHECK` de exactamente una, en vez de una
   referencia polimórfica sin integridad.
5. **`review_batch_items` + `row_token`**: cada fila exportada lleva un token HMAC (lote + código + fila) en una
   columna oculta protegida. Detecta códigos alterados aunque se cambien por otro código válido del mismo lote.
6. **Día de cuota** (`api_quota_usage.quota_date`): se asume día calendario de Chile; la página oficial solo confirma
   el límite (10.000/día por ticket), no la hora exacta de reinicio — queda como riesgo documentado (no bloqueante,
   ver `docs/10-api-validada.md` §8.2 y `docs/08` R-03), no como dato inventado.
7. **Tipos JSON inconsistentes con el manual** (confirmado en `/p2-api`, docs/10 §2.2): varios campos documentados
   como entero/bit por ChileCompra llegan como string (`"0"`/`"1"`, etc.). El adaptador coacciona el tipo; nunca
   asume el tipo documentado sin verificar.
8. **El radar pide el detalle de toda licitación nueva en Publicada, no solo las que pasan un filtro de palabras
   clave** (ADR-0010): el listado no trae rubro, así que un pre-filtro por título descartaría candidatas válidas.
   Una conocida solo se vuelve a detallar si el listado muestra cambio de `CodigoEstado` o `FechaCierre`.
9. **Resumen IA del Excel 1 antes de que exista `bids`** (ADR-0011): `opportunity_ai_summaries` cuelga de
   `opportunities`, no de `bids`; usa el mismo presupuesto mensual de IA (`ai_usage.opportunity_id`) y se cachea por
   `content_hash` para no regenerar si el detalle no cambió.

## 5. Tablas que quedan para MVP-3 (no se crean ahora)

`company_documents`, `projects_experience`, `professionals`, `cost_catalog`, `currency_values`, `proposals`,
`proposal_files`, `tasks`, `approvals`, `compliance_matrix`, `saved_filters` / `alerts`, y la columna
`document_chunks.embedding vector(…)` (pgvector) para búsqueda semántica sobre la biblioteca empresarial.
También quedan para después las tablas de Compra Ágil y órdenes de compra.
