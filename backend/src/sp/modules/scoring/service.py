"""Puntaje de afinidad 0-100 (E2-7, brief S6.4): el backend calcula con pesos configurables; la IA
(cuando este activada, `/p7-analisis`) solo entrega factores, nunca el puntaje.

Dimensiones sugeridas por el brief (S6.4): afinidad tecnica, capacidad operativa, viabilidad
temporal, atractivo economico y riesgo contractual. En el radar (MVP-1, sin documentos todavia) cada
dimension se calcula solo con metadatos de la API; lo que no tiene senal disponible usa un valor
neutro configurable (`thresholds.*_default`), nunca se inventa evidencia.

Puro y determinista (sin red, sin reloj implicito: `as_of` se recibe como parametro): misma entrada,
mismo puntaje (docs/05 E2-7, prueba de propiedad).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sp.core.timezones import UTC_TZ, chile_calendar_date

DEFAULT_WEIGHTS: dict[str, float] = {
    "service_line_affinity": 0.40,
    "time_viability": 0.15,
    "economic_attractiveness": 0.20,
    "operational_capacity": 0.10,
    "contractual_risk": 0.15,
}

DEFAULT_THRESHOLDS: dict[str, Any] = {
    # Filtros duros (E2-10, docs/06 S1.0) y seleccion del lote (E3-7, usados recien en /p5).
    "min_days_to_close": 3,
    "top_n": 50,
    "min_score_include": 40,
    # Viabilidad temporal: dias corridos hasta el cierre que alcanzan el maximo de la dimension.
    "time_viability_full_score_days": 30,
    # Atractivo economico: rango "dulce" en CLP; fuera de rango decae linealmente hasta 0 al doble/mitad.
    "economic_attractive_min": 5_000_000,
    "economic_attractive_max": 150_000_000,
    "economic_default_when_not_visible": 50,
    # Capacidad operativa: duracion de contrato ideal en meses (TiempoDuracionContrato + su unidad).
    "operational_ideal_min_months": 1,
    "operational_ideal_max_months": 36,
    "operational_default_when_unknown": 50,
    # Riesgo contractual (invertido): reclamos del organismo por encima de este umbral -> riesgo maximo.
    "risk_complaints_low": 0,
    "risk_complaints_high": 500,
    "risk_default_when_unknown": 50,
}

# Tabla 3.6 del manual (docs/03): UnidadTiempoDuracionContrato -> meses por unidad.
_DURATION_UNIT_TO_MONTHS: dict[int, float] = {1: 1 / 720, 2: 1 / 24, 3: 1, 4: 1, 5: 12}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _score_service_line_affinity(best_confidence: float | None) -> float:
    if best_confidence is None:
        return 0.0
    return _clamp(best_confidence * 100)


def _score_time_viability(days_to_close: int | None, thresholds: dict[str, Any]) -> float:
    if days_to_close is None:
        return float(thresholds.get("economic_default_when_not_visible", 50))
    if days_to_close <= 0:
        return 0.0
    full_score_days = max(1, int(thresholds.get("time_viability_full_score_days", 30)))
    return _clamp(100.0 * days_to_close / full_score_days)


def _score_economic_attractiveness(
    estimated_amount: float | None, amount_visibility: str, thresholds: dict[str, Any]
) -> float:
    if amount_visibility != "visible" or estimated_amount is None:
        return float(thresholds.get("economic_default_when_not_visible", 50))

    attractive_min = float(thresholds.get("economic_attractive_min", 5_000_000))
    attractive_max = float(thresholds.get("economic_attractive_max", 150_000_000))
    if attractive_min <= estimated_amount <= attractive_max:
        return 100.0
    if estimated_amount < attractive_min:
        if attractive_min <= 0:
            return 100.0
        return _clamp(100.0 * estimated_amount / attractive_min)
    # Por encima del rango: decae linealmente hasta 0 al doble del maximo.
    overflow_ceiling = attractive_max * 2
    if estimated_amount >= overflow_ceiling:
        return 0.0
    return _clamp(100.0 * (overflow_ceiling - estimated_amount) / (overflow_ceiling - attractive_max))


def _contract_duration_months(duration_value: int | None, duration_unit_code: int | None) -> float | None:
    if duration_value is None or duration_unit_code is None:
        return None
    factor = _DURATION_UNIT_TO_MONTHS.get(duration_unit_code)
    if factor is None:
        return None
    return duration_value * factor


def _score_operational_capacity(
    duration_value: int | None, duration_unit_code: int | None, thresholds: dict[str, Any]
) -> float:
    months = _contract_duration_months(duration_value, duration_unit_code)
    if months is None:
        return float(thresholds.get("operational_default_when_unknown", 50))

    ideal_min = float(thresholds.get("operational_ideal_min_months", 1))
    ideal_max = float(thresholds.get("operational_ideal_max_months", 36))
    if ideal_min <= months <= ideal_max:
        return 100.0
    if months < ideal_min:
        return _clamp(100.0 * months / ideal_min) if ideal_min > 0 else 100.0
    overflow_ceiling = ideal_max * 2
    if months >= overflow_ceiling:
        return 0.0
    return _clamp(100.0 * (overflow_ceiling - months) / (overflow_ceiling - ideal_max))


def _score_contractual_risk(complaints: int | None, thresholds: dict[str, Any]) -> float:
    if complaints is None:
        return float(thresholds.get("risk_default_when_unknown", 50))
    low = float(thresholds.get("risk_complaints_low", 0))
    high = float(thresholds.get("risk_complaints_high", 500))
    if high <= low:
        return 50.0
    risk_fraction = _clamp((complaints - low) / (high - low), 0.0, 1.0)
    return _clamp(100.0 * (1.0 - risk_fraction))


def days_to_close(offers_close_utc: datetime | None, as_of_utc: datetime) -> int | None:
    if offers_close_utc is None:
        return None
    close_date = chile_calendar_date(offers_close_utc.astimezone(UTC_TZ))
    run_date = chile_calendar_date(as_of_utc)
    return (close_date - run_date).days


def compute_score(
    *,
    best_service_line_confidence: float | None,
    offers_close_utc: datetime | None,
    as_of_utc: datetime,
    estimated_amount: float | None,
    amount_visibility: str,
    contract_duration_value: int | None,
    contract_duration_unit_code: int | None,
    buyer_complaints_count_snapshot: int | None,
    weights: dict[str, float] | None = None,
    thresholds: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Calcula el puntaje 0-100 y su desglose por factor (`opportunities.score_breakdown`)."""
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    factor_scores = {
        "service_line_affinity": _score_service_line_affinity(best_service_line_confidence),
        "time_viability": _score_time_viability(days_to_close(offers_close_utc, as_of_utc), thresholds),
        "economic_attractiveness": _score_economic_attractiveness(
            estimated_amount, amount_visibility, thresholds
        ),
        "operational_capacity": _score_operational_capacity(
            contract_duration_value, contract_duration_unit_code, thresholds
        ),
        "contractual_risk": _score_contractual_risk(buyer_complaints_count_snapshot, thresholds),
    }

    total_weight = sum(weights.get(name, 0.0) for name in factor_scores) or 1.0
    weighted_sum = sum(factor_scores[name] * weights.get(name, 0.0) for name in factor_scores)
    score = round(_clamp(weighted_sum / total_weight), 2)

    breakdown = {
        "factors": factor_scores,
        "weights": {name: weights.get(name, 0.0) for name in factor_scores},
        "days_to_close": days_to_close(offers_close_utc, as_of_utc),
    }
    return score, breakdown
