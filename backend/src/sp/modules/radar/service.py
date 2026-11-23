"""Orquestacion de una corrida del radar (docs/02 S4, ADR-0010, E2-3..E2-11).

Estrategia de detalle (ADR-0010): se pide el detalle completo de todo codigo nuevo en estado
Publicada y de todo codigo conocido cuyo `CodigoEstado`/`FechaCierre` cambio en el listado; el resto
solo actualiza el estado oficial desde el listado, sin gastar cuota.

Fuente del listado (ADR-0010 addendum 2, `listing_source`, configurable): por defecto `"activas"`
(`estado=activas`, el universo completo de licitaciones Publicada vigentes a la fecha de la
consulta) en vez de `"fecha"` (el dia calendario anterior). Esto hace que el radar no dependa de que
el backend (en el equipo del propietario, ADR-0008) haya estado encendido todas las noches: sirve
tanto de carga inicial (si la cuota se agota a mitad de camino, la corrida queda "parcial" y la
siguiente retoma donde quedo, porque las mismas licitaciones siguen apareciendo en `activas` hasta
que dejen de estar Publicada) como de corrida diaria normal. Contrapartida confirmada contra la API
real (23-11-2026): `estado=activas` trae siempre `CodigoEstado=5`, nunca otro valor -- una
licitacion conocida que dejo de estar Publicada simplemente desaparece del listado en vez de
aparecer con un codigo distinto. Por eso, cuando `listing_source="activas"`, el radar ademas pide el
detalle de toda licitacion conocida que sigue marcada Publicada en la base pero ya no aparece en el
listado (`list_published_codes_missing_from_active_listing`), para aprender su estado real y poder
aplicar `recompute_internal_status` (si no hubo decision de la Compuerta 1 -> `cerrada_sin_decision`).
El listado por fecha (`"fecha"`) sigue disponible como opcion: ese listado si trae licitaciones en
cualquier estado el dia que cambian (docs/10 S2.3), por lo que no necesita este paso adicional.

Resultado de "status" de la corrida:
- `failed`: el listado mismo no se pudo obtener tras los reintentos.
- `partial`: se agoto la cuota diaria antes de terminar de procesar el listado (ADR-0010).
- `succeeded`: se proceso todo el listado. Un codigo cuyo detalle fallo tras los reintentos queda
  implicitamente pendiente (su fila no se crea/actualiza) y se reintenta solo en la corrida
  siguiente, porque seguira viendose "nuevo" o "con cambio" frente al listado de ese dia — nunca se
  pierde lo ya guardado (ADR-0010).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from sp.core.logging import get_logger
from sp.core.timezones import UTC_TZ, chile_calendar_date
from sp.modules.marketplace_adapters.base import (
    CanonicalListingEntry,
    CanonicalOpportunityDetail,
    MarketplaceAdapter,
    QuotaExceededError,
)
from sp.modules.marketplace_adapters.mp_v1.client import MarketplaceAdapterError, MpV1Client
from sp.modules.opportunities.models import Opportunity, OpportunityDate
from sp.modules.opportunities.service import (
    apply_detail,
    apply_listing_only_update,
    get_opportunity_by_code,
    list_published_codes_missing_from_active_listing,
    needs_detail_fetch,
)
from sp.modules.radar.models import RadarRun
from sp.modules.radar.quota import QuotaManager
from sp.modules.scoring.models import ScoringProfile
from sp.modules.scoring.service import compute_score
from sp.modules.service_lines.classifier import LLMServiceLineClassifier, classify_and_persist
from sp.modules.service_lines.models import ServiceLine

logger = get_logger(__name__)

DEFAULT_RATE_LIMIT_SECONDS = 2.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_LISTING_SOURCE = "activas"
_VALID_LISTING_SOURCES = ("activas", "fecha")


@dataclass
class RadarRunOutcome:
    run_id: uuid.UUID
    status: str
    listed_count: int = 0
    new_count: int = 0
    updated_count: int = 0
    detailed_count: int = 0
    requests_used: int = 0
    errors: list[dict] = field(default_factory=list)


def _offers_close_utc(db: Session, opportunity_id: uuid.UUID) -> datetime | None:
    return db.scalars(
        select(OpportunityDate.value_utc).where(
            OpportunityDate.opportunity_id == opportunity_id,
            OpportunityDate.date_type == "offers_close",
        )
    ).one_or_none()


def _score_and_classify(
    db: Session,
    *,
    opportunity: Opportunity,
    detail: CanonicalOpportunityDetail,
    service_lines: list[ServiceLine],
    scoring_profile: ScoringProfile,
    as_of_utc: datetime,
    llm_classifier: LLMServiceLineClassifier | None,
) -> None:
    matches, justification = classify_and_persist(
        db,
        opportunity_id=opportunity.id,
        detail=detail,
        service_lines=service_lines,
        llm_classifier=llm_classifier,
    )
    best_confidence = max((match.confidence for match in matches), default=None)
    offers_close_utc = _offers_close_utc(db, opportunity.id)

    score, breakdown = compute_score(
        best_service_line_confidence=best_confidence,
        offers_close_utc=offers_close_utc,
        as_of_utc=as_of_utc,
        estimated_amount=opportunity.estimated_amount,
        amount_visibility=opportunity.amount_visibility,
        contract_duration_value=opportunity.contract_duration_value,
        contract_duration_unit_code=opportunity.contract_duration_unit_code,
        buyer_complaints_count_snapshot=opportunity.buyer_complaints_count_snapshot,
        weights=scoring_profile.weights,
        thresholds=scoring_profile.thresholds,
    )
    opportunity.score = score
    opportunity.score_breakdown = breakdown
    opportunity.scoring_profile_id = scoring_profile.id
    opportunity.classification_justification = justification
    opportunity.classified_at = as_of_utc


def _synthetic_listing_entry_from_detail(detail: CanonicalOpportunityDetail) -> CanonicalListingEntry:
    """Para una licitacion que desaparecio del listado `activas` (ADR-0010 addendum 2): no tenemos
    una fila de listado fresca, pero el detalle recien pedido ya trae su estado y fecha de cierre
    reales. Se arma con la misma forma que una fila de listado real para que `opportunity.raw_list`
    quede consistente de cara a la proxima comparacion de `needs_detail_fetch`."""
    offers_close_raw = next((d.raw_text for d in detail.dates if d.date_type == "offers_close"), None)
    return CanonicalListingEntry(
        official_code=detail.official_code,
        title=detail.title,
        official_status_code=detail.official_status_code,
        offers_close_raw=offers_close_raw,
        raw_listing_entry={
            "CodigoExterno": detail.official_code,
            "Nombre": detail.title,
            "CodigoEstado": detail.official_status_code,
            "FechaCierre": offers_close_raw,
            "_source": "detalle_tras_desaparecer_de_activas",
        },
    )


def run_radar(
    db: Session,
    *,
    organization_id: uuid.UUID,
    credential_id: uuid.UUID,
    ticket: str,
    daily_limit: int,
    scoring_profile: ScoringProfile,
    service_lines: list[ServiceLine],
    trigger: str,
    radar_date: date | None = None,
    listing_date: date | None = None,
    listing_source: str = DEFAULT_LISTING_SOURCE,
    rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_base_seconds: float = DEFAULT_BACKOFF_BASE_SECONDS,
    llm_classifier: LLMServiceLineClassifier | None = None,
    http_client: httpx.Client | None = None,
    adapter_factory: Callable[..., MarketplaceAdapter] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(UTC_TZ),
) -> RadarRunOutcome:
    if listing_source not in _VALID_LISTING_SOURCES:
        raise ValueError(
            f"listing_source invalido: {listing_source!r} (valores validos: {_VALID_LISTING_SOURCES})"
        )

    run_moment = now()
    effective_radar_date = radar_date or chile_calendar_date(run_moment)
    # El listado liviano por fecha se pide para el dia calendario de Chile ANTERIOR al de la corrida,
    # nunca el de hoy: la ventana de ejecucion (01:00-05:00, ADR-0010) cae en las primeras horas del
    # dia, cuando "hoy" casi no tiene actividad todavia (confirmado contra la API real: `fecha=<hoy>`
    # a esa hora devuelve 0 resultados). `radar_date` sigue siendo el dia de la corrida (asi lo usa
    # el guard "ya corrio hoy" del scheduler, ADR-0007); `listing_date` es el dia cuya actividad se
    # procesa, ya cerrado y completo. Solo aplica cuando `listing_source="fecha"`.
    effective_listing_date = listing_date or (effective_radar_date - timedelta(days=1))

    run = RadarRun(
        organization_id=organization_id,
        radar_date=effective_radar_date,
        trigger=trigger,
        status="running",
        started_at=run_moment,
    )
    db.add(run)
    db.commit()

    quota_manager = QuotaManager(
        db,
        credential_id=credential_id,
        daily_limit=daily_limit,
        rate_limit_seconds=rate_limit_seconds,
        radar_run_id=run.id,
        sleep=sleep,
        clock=clock,
        now=now,
    )
    requests_used_before = quota_manager.current_count()

    client = (
        adapter_factory(
            ticket,
            http_client=http_client,
            before_call=quota_manager.before_call,
            after_call=quota_manager.after_call,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            sleep=sleep,
            clock=clock,
        )
        if adapter_factory is not None
        else MpV1Client(
            ticket,
            http_client=http_client,
            before_call=quota_manager.before_call,
            after_call=quota_manager.after_call,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            sleep=sleep,
            clock=clock,
        )
    )

    outcome = RadarRunOutcome(run_id=run.id, status="running")
    errors: list[dict] = []

    try:
        listing = (
            client.fetch_active_listing()
            if listing_source == "activas"
            else client.fetch_listing(effective_listing_date.strftime("%d%m%Y"))
        )
        db.commit()
    except QuotaExceededError:
        outcome.status = "partial"
        outcome.errors = [{"stage": "listing", "error": "quota_exceeded"}]
        _finalize_run(db, run, outcome, requests_used_before, quota_manager, now)
        return outcome
    except MarketplaceAdapterError as exc:
        outcome.status = "failed"
        outcome.errors = [{"stage": "listing", "error": str(exc)}]
        logger.error("radar_listing_failed", radar_run_id=str(run.id), error=str(exc))
        _finalize_run(db, run, outcome, requests_used_before, quota_manager, now)
        return outcome

    outcome.listed_count = len(listing)
    status = "succeeded"

    for entry in listing:
        existing = get_opportunity_by_code(db, entry.official_code)

        if not needs_detail_fetch(existing, entry):
            apply_listing_only_update(db, existing=existing, listing_entry=entry, now=run_moment)
            if existing is None:
                outcome.new_count += 1
            db.commit()
            continue

        try:
            detail = client.fetch_detail(entry.official_code)
        except QuotaExceededError:
            errors.append(
                {"official_code": entry.official_code, "stage": "detail", "error": "quota_exceeded"}
            )
            db.commit()
            status = "partial"
            break
        except MarketplaceAdapterError as exc:
            errors.append({"official_code": entry.official_code, "stage": "detail", "error": str(exc)})
            logger.warning(
                "radar_detail_failed",
                radar_run_id=str(run.id),
                official_code=entry.official_code,
                error=str(exc),
            )
            db.commit()
            continue

        opportunity = apply_detail(db, existing=existing, detail=detail, listing_entry=entry, now=run_moment)
        if existing is None:
            outcome.new_count += 1
        else:
            outcome.updated_count += 1
        outcome.detailed_count += 1

        _score_and_classify(
            db,
            opportunity=opportunity,
            detail=detail,
            service_lines=service_lines,
            scoring_profile=scoring_profile,
            as_of_utc=run_moment,
            llm_classifier=llm_classifier,
        )
        db.commit()

    if listing_source == "activas" and status == "succeeded":
        # ADR-0010 addendum 2: `estado=activas` nunca muestra un estado distinto de Publicada -- una
        # licitacion conocida que dejo de estarlo simplemente desaparece del listado. Sin este paso,
        # quedaria marcada Publicada/`detectada` para siempre, sin pasar nunca a
        # `cerrada_sin_decision` (ADR-0006).
        present_codes = {entry.official_code for entry in listing}
        disappeared_codes = list_published_codes_missing_from_active_listing(db, present_codes=present_codes)

        for official_code in disappeared_codes:
            existing = get_opportunity_by_code(db, official_code)
            if existing is None:
                continue

            try:
                detail = client.fetch_detail(official_code)
            except QuotaExceededError:
                errors.append(
                    {"official_code": official_code, "stage": "detail_disappeared", "error": "quota_exceeded"}
                )
                db.commit()
                status = "partial"
                break
            except MarketplaceAdapterError as exc:
                errors.append(
                    {"official_code": official_code, "stage": "detail_disappeared", "error": str(exc)}
                )
                logger.warning(
                    "radar_detail_disappeared_failed",
                    radar_run_id=str(run.id),
                    official_code=official_code,
                    error=str(exc),
                )
                db.commit()
                continue

            synthetic_entry = _synthetic_listing_entry_from_detail(detail)
            opportunity = apply_detail(
                db, existing=existing, detail=detail, listing_entry=synthetic_entry, now=run_moment
            )
            outcome.updated_count += 1
            outcome.detailed_count += 1

            _score_and_classify(
                db,
                opportunity=opportunity,
                detail=detail,
                service_lines=service_lines,
                scoring_profile=scoring_profile,
                as_of_utc=run_moment,
                llm_classifier=llm_classifier,
            )
            db.commit()

    outcome.status = status
    outcome.errors = errors
    _finalize_run(db, run, outcome, requests_used_before, quota_manager, now)
    return outcome


def _another_succeeded_run_exists(db: Session, run: RadarRun) -> bool:
    stmt = select(RadarRun.id).where(
        RadarRun.organization_id == run.organization_id,
        RadarRun.radar_date == run.radar_date,
        RadarRun.status == "succeeded",
        RadarRun.id != run.id,
    )
    return db.scalars(stmt).first() is not None


def _finalize_run(
    db: Session,
    run: RadarRun,
    outcome: RadarRunOutcome,
    requests_used_before: int,
    quota_manager: QuotaManager,
    now: Callable[[], datetime],
) -> None:
    outcome.requests_used = quota_manager.current_count() - requests_used_before

    if outcome.status == "succeeded" and _another_succeeded_run_exists(db, run):
        # ADR-0007: la restriccion unica de `radar_runs` garantiza una sola corrida "succeeded"
        # por organizacion y fecha radar. Una segunda corrida manual el mismo dia que tambien
        # habria terminado bien no puede reclamar ese mismo lugar; sus datos ya quedaron
        # guardados (deduplicados) en las tablas de oportunidades, solo se registra como "parcial"
        # para no perder el commit final de sus contadores.
        outcome.status = "partial"
        outcome.errors = [*outcome.errors, {"stage": "finalize", "error": "ya_existe_corrida_succeeded_hoy"}]

    run.status = outcome.status
    run.listed_count = outcome.listed_count
    run.new_count = outcome.new_count
    run.updated_count = outcome.updated_count
    run.detailed_count = outcome.detailed_count
    run.requests_used = outcome.requests_used
    run.errors = outcome.errors
    run.finished_at = now()
    db.commit()
    logger.info(
        "radar_run_finished",
        radar_run_id=str(run.id),
        status=outcome.status,
        listed_count=outcome.listed_count,
        new_count=outcome.new_count,
        updated_count=outcome.updated_count,
        detailed_count=outcome.detailed_count,
        requests_used=outcome.requests_used,
        error_count=len(outcome.errors),
    )
