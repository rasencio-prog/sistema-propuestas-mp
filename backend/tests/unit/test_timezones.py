from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from sp.core.timezones import CHILE_TZ, UTC_TZ, chile_calendar_date, parse_mp_datetime, to_utc


def test_parse_normal_datetime_assumes_chile_time() -> None:
    value, status = parse_mp_datetime("2026-12-10T16:00:00")
    assert status == "ok"
    assert value is not None
    # Diciembre en Chile continental es horario de verano (UTC-3): 16:00 local -> 19:00 UTC.
    assert value == datetime(2026, 12, 10, 19, 0, tzinfo=UTC_TZ)


def test_parse_handles_seven_digit_fraction() -> None:
    # Observado en la muestra real (FechaCreacion): ".53" o fracciones mas largas tipo ticks .NET.
    value, status = parse_mp_datetime("2026-09-15T14:39:38.5312345")
    assert status == "ok"
    assert value is not None


def test_parse_empty_and_none_are_missing() -> None:
    assert parse_mp_datetime(None) == (None, "missing")
    assert parse_mp_datetime("") == (None, "missing")
    assert parse_mp_datetime("   ") == (None, "missing")


def test_parse_sentinel_date_is_missing() -> None:
    # docs/10 S2.2: fecha centinela de .NET observada en FechaTiempoEvaluacion.
    value, status = parse_mp_datetime("1900-01-04T00:00:00")
    assert value is None
    assert status == "missing"


def test_parse_any_year_leq_1950_is_missing() -> None:
    value, status = parse_mp_datetime("1950-01-01T00:00:00")
    assert value is None
    assert status == "missing"
    value, status = parse_mp_datetime("1951-01-01T00:00:00")
    assert status == "ok"


def test_parse_unparseable_text_is_not_lost_silently() -> None:
    value, status = parse_mp_datetime("no es una fecha")
    assert value is None
    assert status == "unparseable"


def test_ambiguous_hour_uses_fold_zero_first_occurrence() -> None:
    # Chile atraso el reloj el 2015-04-11 a las 00:00 (quedo en 23:00 del 10-04, UTC-3 -> UTC-4):
    # 23:30 local del 10-04-2015 ocurrio dos veces. fold=0 (primera ocurrencia) debe ser UTC-3.
    value, status = parse_mp_datetime("2015-04-10T23:30:00")
    assert status == "ok"
    assert value is not None
    assert value == datetime(2015, 4, 11, 2, 30, tzinfo=UTC_TZ)


def test_round_trip_to_utc_matches_chile_tz_conversion() -> None:
    naive = datetime(2026, 6, 1, 10, 30)
    assert to_utc(naive) == naive.replace(tzinfo=CHILE_TZ).astimezone(UTC_TZ)


def test_chile_calendar_date_from_utc_instant() -> None:
    # 2026-01-01T02:30:00 UTC es 2025-12-31T23:30:00 en Chile (verano, UTC-3).
    instant = datetime(2026, 1, 1, 2, 30, tzinfo=UTC_TZ)
    assert chile_calendar_date(instant).isoformat() == "2025-12-31"


@given(
    st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2035, 1, 1),
        timezones=st.just(UTC),
    )
)
def test_property_to_chile_and_back_preserves_instant(instant: datetime) -> None:
    # docs/07 S1: para cualquier instante UTC, convertir a Chile y volver a UTC devuelve el mismo
    # instante. Se mantiene el datetime "aware" (con su `fold`) en todo el recorrido: solo al pasar
    # por un texto sin zona (`parse_mp_datetime`, que asume fold=0) se pierde esa informacion, y ahi
    # aplica la regla documentada de ADR-0009 (ver `test_ambiguous_hour_uses_fold_zero_first_occurrence`).
    to_chile = instant.astimezone(CHILE_TZ)
    assert to_chile.astimezone(UTC_TZ) == instant
