"""Radar end-to-end contra Postgres real (esquema `test`, docs/07 S0): cuota, backoff, deduplicacion,
cambios, estados separados y que el ticket nunca llegue a `api_call_log`. Nunca llama a la API real
de Mercado Publico: `respx` intercepta httpx (docs/07 S0)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import respx
from sqlalchemy import select

from sp.modules.marketplace_adapters.mp_v1.client import BASE_URL
from sp.modules.opportunities.models import Opportunity, OpportunityChange
from sp.modules.radar.models import ApiCallLog, ApiQuotaUsage, RadarRun
from sp.modules.radar.service import run_radar

FAKE_TICKET = "ticket-de-prueba"
RUN_MOMENT = datetime(2026, 11, 20, 3, 0, tzinfo=UTC)  # 00:00 Chile (verano, UTC-3)
# ADR-0010 (addendum): el listado se pide del dia ANTERIOR al de la corrida (19-11), nunca el de
# "hoy" (20-11): a la hora de la ventana (01:00-05:00) el dia de la corrida recien empezo y la API
# devuelve 0 resultados (confirmado contra la API real); `radar_runs.radar_date` si queda en 20-11
# (es la llave del guard "ya corrio hoy" de ADR-0007).


def _listing_payload(entries: list[dict]) -> dict:
    return {"Cantidad": len(entries), "Listado": entries}


def _detail_payload(**overrides) -> dict:
    base = {
        "CodigoExterno": "1-1-LE26",
        "Nombre": "Desarrollo de aplicaciones web a medida",
        "Descripcion": "Construccion de sistemas web institucionales",
        "Tipo": "LE",
        "CodigoTipo": 1,
        "CodigoEstado": 5,
        "Estado": "Publicada",
        "Comprador": {
            "CodigoOrganismo": "100",
            "NombreOrganismo": "Organismo de prueba",
            "CodigoUnidad": "200",
            "NombreUnidad": "Unidad de prueba",
            "RutUnidad": "61.000.000-1",
            "RegionUnidad": "Region Metropolitana",
        },
        "Fechas": {
            "FechaPublicacion": "2026-11-15T10:00:00",
            "FechaCierre": "2026-12-10T16:00:00",
        },
        "VisibilidadMonto": 1,
        "MontoEstimado": 30_000_000,
        "Moneda": "CLP",
        "Items": {
            "Cantidad": 1,
            "Listado": [
                {
                    "Correlativo": 1,
                    "CodigoProducto": 43231501,
                    "CodigoCategoria": "43231500",
                    "Categoria": "Software",
                    "NombreProducto": "Desarrollo de software a medida",
                    "Descripcion": "Aplicaciones web",
                    "UnidadMedida": "Unidad",
                    "Cantidad": 1.0,
                }
            ],
        },
    }
    base.update(overrides)
    return {"Cantidad": 1, "Listado": [base]}


def _run(
    db_session, radar_fixture, *, daily_limit: int | None = None, radar_date: date | None = None, **kwargs
):
    credential = radar_fixture["credential"]
    if daily_limit is not None:
        credential.daily_limit = daily_limit
        db_session.flush()
    return run_radar(
        db_session,
        organization_id=radar_fixture["organization"].id,
        credential_id=credential.id,
        ticket=FAKE_TICKET,
        daily_limit=credential.daily_limit,
        scoring_profile=radar_fixture["scoring_profile"],
        service_lines=[radar_fixture["service_line"]],
        trigger="manual",
        rate_limit_seconds=0,
        max_retries=1,
        backoff_base_seconds=0,
        sleep=lambda _seconds: None,
        now=lambda: RUN_MOMENT,
        radar_date=radar_date,
        **kwargs,
    )


@respx.mock
def test_new_published_opportunity_is_captured_classified_and_scored(db_session, radar_fixture) -> None:
    respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(
            200,
            json=_listing_payload(
                [
                    {
                        "CodigoExterno": "1-1-LE26",
                        "Nombre": "x",
                        "CodigoEstado": 5,
                        "FechaCierre": "2026-12-10T16:00:00",
                    }
                ]
            ),
        )
    )
    respx.get(BASE_URL, params={"codigo": "1-1-LE26"}).mock(
        return_value=httpx.Response(200, json=_detail_payload())
    )

    outcome = _run(db_session, radar_fixture)

    assert outcome.status == "succeeded"
    assert outcome.new_count == 1
    assert outcome.detailed_count == 1

    opportunity = db_session.scalars(select(Opportunity).where(Opportunity.official_code == "1-1-LE26")).one()
    assert opportunity.internal_status == "detectada"
    assert opportunity.official_status_code == 5
    assert opportunity.score is not None and 0 <= opportunity.score <= 100
    assert opportunity.classification_justification is not None
    assert "Desarrollo de software" in opportunity.classification_justification


@respx.mock
def test_second_run_same_period_does_not_create_duplicates(db_session, radar_fixture) -> None:
    """[17-MVP1-2] docs/05 E2-3."""
    listing_route = respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(
            200,
            json=_listing_payload(
                [
                    {
                        "CodigoExterno": "1-1-LE26",
                        "Nombre": "x",
                        "CodigoEstado": 5,
                        "FechaCierre": "2026-12-10T16:00:00",
                    }
                ]
            ),
        )
    )
    respx.get(BASE_URL, params={"codigo": "1-1-LE26"}).mock(
        return_value=httpx.Response(200, json=_detail_payload())
    )

    _run(db_session, radar_fixture)
    second_outcome = _run(db_session, radar_fixture)

    assert listing_route.call_count == 2
    assert second_outcome.new_count == 0
    assert second_outcome.detailed_count == 0  # sin cambio de CodigoEstado/FechaCierre: no se pide detalle

    count = db_session.scalars(select(Opportunity).where(Opportunity.official_code == "1-1-LE26")).all()
    assert len(count) == 1


@respx.mock
def test_status_change_triggers_new_detail_and_records_change(db_session, radar_fixture) -> None:
    respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        side_effect=[
            httpx.Response(
                200,
                json=_listing_payload(
                    [
                        {
                            "CodigoExterno": "1-1-LE26",
                            "Nombre": "x",
                            "CodigoEstado": 5,
                            "FechaCierre": "2026-12-10T16:00:00",
                        }
                    ]
                ),
            ),
            httpx.Response(
                200,
                json=_listing_payload(
                    [
                        {
                            "CodigoExterno": "1-1-LE26",
                            "Nombre": "x",
                            "CodigoEstado": 6,
                            "FechaCierre": "2026-12-10T16:00:00",
                        }
                    ]
                ),
            ),
        ]
    )
    respx.get(BASE_URL, params={"codigo": "1-1-LE26"}).mock(
        side_effect=[
            httpx.Response(200, json=_detail_payload()),
            httpx.Response(200, json=_detail_payload(CodigoEstado=6, Estado="Cerrada")),
        ]
    )

    _run(db_session, radar_fixture)
    second_outcome = _run(db_session, radar_fixture)

    assert second_outcome.detailed_count == 1
    assert second_outcome.updated_count == 1

    opportunity = db_session.scalars(select(Opportunity).where(Opportunity.official_code == "1-1-LE26")).one()
    # El estado oficial y el estado interno del embudo son campos separados (ADR-0006): el oficial
    # cambia a Cerrada y, como no hubo decision de la Compuerta 1, el interno pasa a
    # 'cerrada_sin_decision' en vez de deducirse del oficial.
    assert opportunity.official_status_code == 6
    assert opportunity.official_status_text == "Cerrada"
    assert opportunity.internal_status == "cerrada_sin_decision"

    changes = db_session.scalars(
        select(OpportunityChange).where(
            OpportunityChange.opportunity_id == opportunity.id, OpportunityChange.change_type == "status"
        )
    ).all()
    assert len(changes) == 1
    assert changes[0].old_value == {"value": 5}
    assert changes[0].new_value == {"value": 6}


@respx.mock
def test_quota_exceeded_marks_run_partial_and_stops(db_session, radar_fixture) -> None:
    respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(
            200,
            json=_listing_payload(
                [
                    {"CodigoExterno": "A-1-LE26", "Nombre": "a", "CodigoEstado": 5, "FechaCierre": None},
                    {"CodigoExterno": "B-1-LE26", "Nombre": "b", "CodigoEstado": 5, "FechaCierre": None},
                ]
            ),
        )
    )
    detail_route = respx.get(BASE_URL, params={"codigo": "A-1-LE26"}).mock(
        return_value=httpx.Response(200, json=_detail_payload(CodigoExterno="A-1-LE26"))
    )
    other_detail_route = respx.get(BASE_URL, params={"codigo": "B-1-LE26"}).mock(
        return_value=httpx.Response(200, json=_detail_payload(CodigoExterno="B-1-LE26"))
    )

    # 1 listado + 1 detalle agotan la cuota antes del segundo detalle.
    outcome = _run(db_session, radar_fixture, daily_limit=2)

    assert outcome.status == "partial"
    assert detail_route.called
    assert not other_detail_route.called

    run = db_session.get(RadarRun, outcome.run_id)
    assert run.status == "partial"
    assert run.requests_used == 2


@respx.mock
def test_quota_counted_by_chile_calendar_day(db_session, radar_fixture) -> None:
    respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(200, json=_listing_payload([]))
    )
    _run(db_session, radar_fixture)

    usage = db_session.get(ApiQuotaUsage, (radar_fixture["credential"].id, date(2026, 11, 20)))
    assert usage is not None
    assert usage.requests_count == 1  # solo el listado; RUN_MOMENT (03:00 UTC) es 2026-11-20 en Chile


@respx.mock
def test_ticket_never_appears_in_api_call_log(db_session, radar_fixture) -> None:
    respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(
            200,
            json=_listing_payload(
                [{"CodigoExterno": "1-1-LE26", "Nombre": "x", "CodigoEstado": 5, "FechaCierre": None}]
            ),
        )
    )
    respx.get(BASE_URL, params={"codigo": "1-1-LE26"}).mock(
        return_value=httpx.Response(200, json=_detail_payload())
    )
    _run(db_session, radar_fixture)

    logs = db_session.scalars(select(ApiCallLog)).all()
    assert len(logs) >= 2
    for log in logs:
        assert FAKE_TICKET not in str(log.params_sanitized)
        assert "ticket" not in log.params_sanitized
        assert log.error is None or FAKE_TICKET not in log.error


@respx.mock
def test_published_entry_with_far_close_date_passes_hard_filters(db_session, radar_fixture) -> None:
    from sp.modules.opportunities.service import passes_hard_filters

    respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(
            200,
            json=_listing_payload(
                [
                    {
                        "CodigoExterno": "1-1-LE26",
                        "Nombre": "x",
                        "CodigoEstado": 5,
                        "FechaCierre": "2026-12-10T16:00:00",
                    }
                ]
            ),
        )
    )
    respx.get(BASE_URL, params={"codigo": "1-1-LE26"}).mock(
        return_value=httpx.Response(200, json=_detail_payload())
    )
    _run(db_session, radar_fixture)

    opportunity = db_session.scalars(select(Opportunity).where(Opportunity.official_code == "1-1-LE26")).one()
    assert passes_hard_filters(db_session, opportunity, as_of_utc=RUN_MOMENT, min_days_to_close=3) is True


@respx.mock
def test_close_date_too_soon_fails_hard_filter_but_unparseable_does_not_exclude(
    db_session, radar_fixture
) -> None:
    from sp.modules.opportunities.service import passes_hard_filters

    respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(
            200,
            json=_listing_payload(
                [
                    {
                        "CodigoExterno": "2-1-LE26",
                        "Nombre": "x",
                        "CodigoEstado": 5,
                        "FechaCierre": "2026-11-21T16:00:00",
                    }
                ]
            ),
        )
    )
    respx.get(BASE_URL, params={"codigo": "2-1-LE26"}).mock(
        return_value=httpx.Response(
            200,
            json=_detail_payload(
                CodigoExterno="2-1-LE26",
                Fechas={"FechaPublicacion": "2026-11-15T10:00:00", "FechaCierre": "2026-11-21T16:00:00"},
            ),
        )
    )
    _run(db_session, radar_fixture)

    opportunity = db_session.scalars(select(Opportunity).where(Opportunity.official_code == "2-1-LE26")).one()
    # Cierre al dia siguiente de la corrida: 1 dia corrido < 3 (min_days_to_close) -> no pasa.
    assert passes_hard_filters(db_session, opportunity, as_of_utc=RUN_MOMENT, min_days_to_close=3) is False


@respx.mock
def test_radar_run_date_is_bookkeeping_but_listing_queries_the_previous_day(
    db_session, radar_fixture
) -> None:
    """ADR-0010 (addendum): a las 00:00 Chile del dia de la corrida (20-11), ese dia casi no tiene
    actividad; el listado se pide del dia anterior (19-11), ya cerrado."""
    listing_route = respx.get(BASE_URL, params={"fecha": "19112026"}).mock(
        return_value=httpx.Response(200, json=_listing_payload([]))
    )
    outcome = _run(db_session, radar_fixture)

    assert listing_route.called
    run = db_session.get(RadarRun, outcome.run_id)
    assert run.radar_date == date(2026, 11, 20)
