"""Puntaje 0-100 reproducible y explicable (E2-7, ADR-0017): puro, determinista, acotado."""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from sp.core.timezones import UTC_TZ
from sp.modules.scoring.service import compute_score, days_to_close

AS_OF = datetime(2026, 11, 20, 12, 0, tzinfo=UTC_TZ)


def _compute(**overrides):
    base = {
        "best_service_line_confidence": 0.6,
        "offers_close_utc": AS_OF + timedelta(days=10),
        "as_of_utc": AS_OF,
        "estimated_amount": 50_000_000,
        "amount_visibility": "visible",
        "contract_duration_value": 12,
        "contract_duration_unit_code": 4,
        "buyer_complaints_count_snapshot": 10,
    }
    base.update(overrides)
    return compute_score(**base)


def test_same_input_gives_same_score() -> None:
    score1, breakdown1 = _compute()
    score2, breakdown2 = _compute()
    assert score1 == score2
    assert breakdown1 == breakdown2


def test_score_is_bounded_0_100() -> None:
    score, _ = _compute(
        best_service_line_confidence=None,
        offers_close_utc=None,
        estimated_amount=None,
        amount_visibility="not_visible",
        contract_duration_value=None,
        contract_duration_unit_code=None,
        buyer_complaints_count_snapshot=None,
    )
    assert 0 <= score <= 100


def test_higher_confidence_never_lowers_the_score() -> None:
    low, _ = _compute(best_service_line_confidence=0.1)
    high, _ = _compute(best_service_line_confidence=0.9)
    assert high >= low


def test_no_service_line_match_scores_zero_on_that_factor() -> None:
    _, breakdown = _compute(best_service_line_confidence=None)
    assert breakdown["factors"]["service_line_affinity"] == 0.0


def test_no_service_line_match_caps_final_score_regardless_of_other_factors() -> None:
    """ADR-0017 addendum: sin afinidad con ninguna linea, el puntaje queda acotado aunque monto,
    plazo y los demas factores sean ideales (antes de este ajuste podia dar ~46 puntos, ver el caso
    real de Putaendo abajo)."""
    score, breakdown = _compute(
        best_service_line_confidence=None,
        offers_close_utc=AS_OF + timedelta(days=30),  # viabilidad temporal maxima
        estimated_amount=50_000_000,  # dentro del rango atractivo
        amount_visibility="visible",
        contract_duration_value=12,
        contract_duration_unit_code=4,  # dentro del rango ideal
        buyer_complaints_count_snapshot=0,  # riesgo minimo
    )
    assert score <= 15
    assert breakdown["capped_no_affinity"] is True


def test_putaendo_biblioteca_case_without_affinity_stays_low() -> None:
    """Caso real (corrida del 23-11-2026): dos licitaciones de inspeccion/asesoria tecnica para la
    construccion de una biblioteca publica (Putaendo) sin coincidencia con ninguna linea de servicio
    TI, pero con monto visible atractivo y cierre a 10 dias. Antes del ajuste sacaban 46.13 puntos;
    ahora deben quedar acotadas al techo configurable."""
    score, breakdown = _compute(
        best_service_line_confidence=None,
        offers_close_utc=AS_OF + timedelta(days=10),
        estimated_amount=20_300_000,
        amount_visibility="visible",
        contract_duration_value=None,
        contract_duration_unit_code=None,
        buyer_complaints_count_snapshot=None,
    )
    assert score <= 15
    assert breakdown["capped_no_affinity"] is True


def test_custom_no_affinity_cap_threshold_is_respected() -> None:
    score, breakdown = _compute(
        best_service_line_confidence=None,
        thresholds={"no_affinity_score_cap": 5},
    )
    assert score <= 5
    assert breakdown["capped_no_affinity"] is True


def test_affinity_match_is_never_capped() -> None:
    _, breakdown = _compute(best_service_line_confidence=0.9)
    assert breakdown["capped_no_affinity"] is False


def test_amount_not_visible_uses_neutral_default() -> None:
    _, breakdown = _compute(amount_visibility="not_visible", estimated_amount=None)
    assert breakdown["factors"]["economic_attractiveness"] == 50


def test_missing_offers_close_does_not_crash_and_has_no_days_to_close() -> None:
    score, breakdown = _compute(offers_close_utc=None)
    assert breakdown["days_to_close"] is None
    assert 0 <= score <= 100


def test_days_to_close_uses_chile_calendar_dates() -> None:
    offers_close = AS_OF + timedelta(days=5)
    assert days_to_close(offers_close, AS_OF) == 5


def test_custom_weights_change_the_result_deterministically() -> None:
    default_score, _ = _compute()
    custom_score, _ = _compute(weights={"service_line_affinity": 1.0})
    assert default_score != custom_score


@given(
    confidence=st.one_of(st.none(), st.floats(min_value=0, max_value=1)),
    days=st.one_of(st.none(), st.integers(min_value=-30, max_value=400)),
    amount=st.one_of(st.none(), st.floats(min_value=0, max_value=10_000_000_000)),
    visible=st.booleans(),
    duration_value=st.one_of(st.none(), st.integers(min_value=0, max_value=120)),
    complaints=st.one_of(st.none(), st.integers(min_value=0, max_value=100_000)),
)
def test_property_score_always_bounded(confidence, days, amount, visible, duration_value, complaints) -> None:
    offers_close = AS_OF + timedelta(days=days) if days is not None else None
    score, breakdown = compute_score(
        best_service_line_confidence=confidence,
        offers_close_utc=offers_close,
        as_of_utc=AS_OF,
        estimated_amount=amount,
        amount_visibility="visible" if visible else "not_visible",
        contract_duration_value=duration_value,
        contract_duration_unit_code=4 if duration_value is not None else None,
        buyer_complaints_count_snapshot=complaints,
    )
    assert 0 <= score <= 100
    for factor_score in breakdown["factors"].values():
        assert 0 <= factor_score <= 100
