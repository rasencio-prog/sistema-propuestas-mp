"""Normalizacion, deduplicacion y filtros duros del radar (docs/02 S2, S4; ADR-0006, ADR-0010, E2-3..E2-11).

Todo lo de aqui opera sobre el modelo canonico (`marketplace_adapters.base`), nunca sobre la
respuesta cruda de la API: el adaptador ya tradujo y coacciono tipos antes de llegar hasta aca.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from sp.core.logging import get_logger
from sp.core.timezones import UTC_TZ, chile_calendar_date, parse_mp_datetime
from sp.modules.marketplace_adapters.base import (
    KNOWN_STATUS_CODES,
    CanonicalBuyer,
    CanonicalListingEntry,
    CanonicalOpportunityDetail,
)
from sp.modules.opportunities.models import (
    Buyer,
    Opportunity,
    OpportunityChange,
    OpportunityDate,
    OpportunityItem,
)

logger = get_logger(__name__)

SOURCE = "mercado_publico"
PUBLISHED_STATUS_CODE = 5
_SOURCE_URL_PATTERN = (
    "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion={code}"
)
_FUNNEL_STATUSES_BEFORE_DOCS = ("detectada", "preseleccionada")


def build_source_url(official_code: str) -> str:
    return _SOURCE_URL_PATTERN.format(code=official_code)


def get_opportunity_by_code(db: Session, official_code: str) -> Opportunity | None:
    stmt = select(Opportunity).where(Opportunity.source == SOURCE, Opportunity.official_code == official_code)
    return db.scalars(stmt).one_or_none()


def needs_detail_fetch(existing: Opportunity | None, listing_entry: CanonicalListingEntry) -> bool:
    """ADR-0010 punto 1-2: nueva + Publicada -> si; conocida con CodigoEstado/FechaCierre
    sin cambios -> no; conocida con cambio -> si."""
    if existing is None:
        return listing_entry.official_status_code == PUBLISHED_STATUS_CODE

    previous_raw = existing.raw_list or {}
    status_changed = existing.official_status_code != listing_entry.official_status_code
    close_changed = previous_raw.get("FechaCierre") != listing_entry.offers_close_raw
    return status_changed or close_changed


def apply_listing_only_update(
    db: Session, *, existing: Opportunity | None, listing_entry: CanonicalListingEntry, now: datetime
) -> Opportunity:
    """ADR-0010 punto 3: licitacion que no necesita detalle, solo actualiza estado oficial."""
    status_documented = listing_entry.official_status_code in KNOWN_STATUS_CODES
    status_text = KNOWN_STATUS_CODES.get(
        listing_entry.official_status_code, str(listing_entry.official_status_code)
    )
    if not status_documented:
        logger.warning(
            "estado_no_documentado",
            official_code=listing_entry.official_code,
            official_status_code=listing_entry.official_status_code,
        )

    if existing is None:
        opportunity = Opportunity(
            source=SOURCE,
            official_code=listing_entry.official_code,
            title=listing_entry.title,
            official_status_code=listing_entry.official_status_code,
            official_status_text=status_text,
            official_status_documented=status_documented,
            internal_status="detectada",
            internal_status_changed_at=now,
            source_url=build_source_url(listing_entry.official_code),
            amount_visibility="unknown",
            raw_list=listing_entry.raw_listing_entry,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(opportunity)
        db.flush()
        return opportunity

    if existing.official_status_code != listing_entry.official_status_code:
        db.add(
            OpportunityChange(
                opportunity_id=existing.id,
                change_type="status",
                field="official_status_code",
                old_value={"value": existing.official_status_code},
                new_value={"value": listing_entry.official_status_code},
                requires_reanalysis=existing.internal_status == "documentos_pendientes",
            )
        )
        existing.official_status_code = listing_entry.official_status_code
        existing.official_status_text = status_text
        existing.official_status_documented = status_documented

    existing.raw_list = listing_entry.raw_listing_entry
    existing.last_seen_at = now
    recompute_internal_status(existing, now=now)
    db.flush()
    return existing


def recompute_internal_status(opportunity: Opportunity, *, now: datetime) -> None:
    """ADR-0006: si el estado oficial deja de ser Publicada sin decision de la Compuerta 1,
    la oportunidad pasa a 'cerrada_sin_decision'. Nunca toca estados terminales posteriores."""
    if (
        opportunity.official_status_code != PUBLISHED_STATUS_CODE
        and opportunity.internal_status in _FUNNEL_STATUSES_BEFORE_DOCS
    ):
        opportunity.internal_status = "cerrada_sin_decision"
        opportunity.internal_status_changed_at = now


def _get_or_create_buyer(db: Session, buyer: CanonicalBuyer) -> Buyer:
    stmt = select(Buyer).where(
        Buyer.source == SOURCE,
        Buyer.organism_code == buyer.organism_code,
        Buyer.unit_code == buyer.unit_code,
    )
    existing = db.scalars(stmt).one_or_none()
    if existing is not None:
        existing.organism_name = buyer.organism_name
        existing.unit_name = buyer.unit_name
        existing.unit_rut = buyer.unit_rut
        existing.region = buyer.region
        existing.commune = buyer.commune
        return existing

    created = Buyer(
        source=SOURCE,
        organism_code=buyer.organism_code,
        organism_name=buyer.organism_name,
        unit_code=buyer.unit_code,
        unit_name=buyer.unit_name,
        unit_rut=buyer.unit_rut,
        region=buyer.region,
        commune=buyer.commune,
    )
    db.add(created)
    db.flush()
    return created


def _detail_content_hash(detail: CanonicalOpportunityDetail) -> str:
    payload = json.dumps(detail.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _replace_items(db: Session, *, opportunity_id: uuid.UUID, detail: CanonicalOpportunityDetail) -> None:
    db.query(OpportunityItem).filter(OpportunityItem.opportunity_id == opportunity_id).delete()
    for item in detail.items:
        db.add(
            OpportunityItem(
                opportunity_id=opportunity_id,
                line_no=item.line_no,
                product_code=item.product_code,
                category_code=item.category_code,
                category_name=item.category_name,
                product_name=item.product_name,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
            )
        )


def _upsert_dates(
    db: Session, *, opportunity_id: uuid.UUID, detail: CanonicalOpportunityDetail
) -> dict[str, datetime | None]:
    """Devuelve el `value_utc` por `date_type` tras el upsert (para detectar cambios de fecha)."""
    existing_rows = {
        row.date_type: row
        for row in db.scalars(select(OpportunityDate).where(OpportunityDate.opportunity_id == opportunity_id))
    }
    new_values: dict[str, datetime | None] = {}
    for canonical_date in detail.dates:
        value_utc, parse_status = parse_mp_datetime(canonical_date.raw_text)
        new_values[canonical_date.date_type] = value_utc
        row = existing_rows.get(canonical_date.date_type)
        if row is None:
            db.add(
                OpportunityDate(
                    opportunity_id=opportunity_id,
                    date_type=canonical_date.date_type,
                    value_utc=value_utc,
                    original_text=canonical_date.raw_text,
                    source_field=canonical_date.date_type,
                    parse_status=parse_status,
                )
            )
        else:
            row.value_utc = value_utc
            row.original_text = canonical_date.raw_text
            row.parse_status = parse_status
    return new_values


def apply_detail(
    db: Session,
    *,
    existing: Opportunity | None,
    detail: CanonicalOpportunityDetail,
    listing_entry: CanonicalListingEntry,
    now: datetime,
) -> Opportunity:
    """Crea o actualiza una oportunidad con el detalle completo (ADR-0010): comprador, items,
    fechas, campos de contrato/pago/adjudicacion, y registra cambios de estado/fecha/monto.

    Tambien guarda `raw_list` con la entrada del listado que disparo este detalle: sin esto,
    `needs_detail_fetch` no tendria con que comparar en la proxima corrida (una oportunidad nueva
    siempre entra por esta funcion, nunca por `apply_listing_only_update`) y pediria detalle de
    nuevo aunque nada haya cambiado."""
    if not detail.official_status_documented:
        logger.warning(
            "estado_no_documentado",
            official_code=detail.official_code,
            official_status_code=detail.official_status_code,
        )

    buyer = _get_or_create_buyer(db, detail.buyer) if detail.buyer else None
    content_hash = _detail_content_hash(detail)

    if existing is None:
        opportunity = Opportunity(
            source=SOURCE,
            official_code=detail.official_code,
            internal_status="detectada",
            internal_status_changed_at=now,
            first_seen_at=now,
        )
        db.add(opportunity)
        is_new = True
    else:
        opportunity = existing
        is_new = False

    if not is_new:
        if opportunity.official_status_code != detail.official_status_code:
            db.add(
                OpportunityChange(
                    opportunity_id=opportunity.id,
                    change_type="status",
                    field="official_status_code",
                    old_value={"value": opportunity.official_status_code},
                    new_value={"value": detail.official_status_code},
                    requires_reanalysis=opportunity.internal_status == "documentos_pendientes",
                )
            )
        if opportunity.estimated_amount != detail.estimated_amount:
            db.add(
                OpportunityChange(
                    opportunity_id=opportunity.id,
                    change_type="amount",
                    field="estimated_amount",
                    old_value={"value": _to_jsonable(opportunity.estimated_amount)},
                    new_value={"value": _to_jsonable(detail.estimated_amount)},
                    requires_reanalysis=False,
                )
            )

    opportunity.opportunity_type_code = detail.opportunity_type_code
    opportunity.opportunity_type_text = detail.opportunity_type_text
    opportunity.title = detail.title
    opportunity.description = detail.description
    opportunity.buyer_id = buyer.id if buyer else None
    opportunity.estimated_amount = detail.estimated_amount
    opportunity.currency = detail.currency
    opportunity.amount_visibility = detail.amount_visibility
    opportunity.official_status_code = detail.official_status_code
    opportunity.official_status_text = detail.official_status_text
    opportunity.official_status_documented = detail.official_status_documented
    opportunity.source_url = build_source_url(detail.official_code)
    opportunity.contract_duration_value = detail.contract_duration_value
    opportunity.contract_duration_unit_code = detail.contract_duration_unit_code
    opportunity.is_renewable = detail.is_renewable
    opportunity.renewal_value = detail.renewal_value
    opportunity.renewal_period_text = detail.renewal_period_text
    opportunity.subcontracting_allowed = detail.subcontracting_allowed
    opportunity.contract_formalization_code = detail.contract_formalization_code
    opportunity.payment_modality_code = detail.payment_modality_code
    opportunity.payment_type_code = detail.payment_type_code
    opportunity.contract_responsible_name = detail.contract_responsible_name
    opportunity.contract_responsible_email = detail.contract_responsible_email
    opportunity.contract_responsible_phone = detail.contract_responsible_phone
    opportunity.payment_responsible_name = detail.payment_responsible_name
    opportunity.payment_responsible_email = detail.payment_responsible_email
    opportunity.buyer_complaints_count_snapshot = detail.buyer_complaints_count_snapshot
    opportunity.is_standard_type = detail.is_standard_type
    opportunity.award_act_type_code = detail.award_act_type_code
    opportunity.award_act_number = detail.award_act_number
    opportunity.award_offerors_count = detail.award_offerors_count
    opportunity.award_act_url = detail.award_act_url
    opportunity.raw_detail = detail.raw_detail
    opportunity.raw_list = listing_entry.raw_listing_entry
    opportunity.content_hash = content_hash
    opportunity.detail_fetched_at = now
    opportunity.last_seen_at = now

    db.flush()  # asegura opportunity.id antes de las tablas satelite

    previous_offers_close = None
    if not is_new:
        previous_offers_close = db.scalars(
            select(OpportunityDate.value_utc).where(
                OpportunityDate.opportunity_id == opportunity.id,
                OpportunityDate.date_type == "offers_close",
            )
        ).one_or_none()

    _replace_items(db, opportunity_id=opportunity.id, detail=detail)
    new_date_values = _upsert_dates(db, opportunity_id=opportunity.id, detail=detail)

    if not is_new:
        new_offers_close = new_date_values.get("offers_close")
        if previous_offers_close != new_offers_close:
            db.add(
                OpportunityChange(
                    opportunity_id=opportunity.id,
                    change_type="date",
                    field="offers_close",
                    old_value={"value": _to_jsonable(previous_offers_close)},
                    new_value={"value": _to_jsonable(new_offers_close)},
                    requires_reanalysis=opportunity.internal_status == "documentos_pendientes",
                )
            )

    recompute_internal_status(opportunity, now=now)
    db.flush()
    return opportunity


def _to_jsonable(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def passes_hard_filters(
    db: Session, opportunity: Opportunity, *, as_of_utc: datetime, min_days_to_close: int
) -> bool:
    """docs/06 S1.0: estado oficial Publicada y cierre a `min_days_to_close` dias corridos o mas
    desde la corrida. Fecha de cierre no interpretable -> no se descarta (entra con alerta)."""
    if opportunity.official_status_code != PUBLISHED_STATUS_CODE:
        return False

    offers_close = db.scalars(
        select(OpportunityDate).where(
            OpportunityDate.opportunity_id == opportunity.id,
            OpportunityDate.date_type == "offers_close",
        )
    ).one_or_none()
    if offers_close is None or offers_close.parse_status != "ok" or offers_close.value_utc is None:
        return True

    close_date = chile_calendar_date(offers_close.value_utc.astimezone(UTC_TZ))
    run_date = chile_calendar_date(as_of_utc)
    return (close_date - run_date).days >= min_days_to_close


def list_eligible_for_batch(db: Session) -> list[Opportunity]:
    """Universo del Excel 1 (docs/06 S1.0, antes de filtros duros y seleccion): detectadas o
    preseleccionadas (estas ultimas sin decision vigente de descarte/descarga)."""
    stmt = select(Opportunity).where(Opportunity.internal_status.in_(("detectada", "preseleccionada")))
    return list(db.scalars(stmt))
