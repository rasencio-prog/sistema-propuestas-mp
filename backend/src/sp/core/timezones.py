"""Conversion de fechas de la API de Mercado Publico (ADR-0009, ADR-0010).

Todas las fechas que entrega `api.mercadopublico.cl` llegan como texto
`AAAA-MM-DDTHH:MM:SS[.fffffff]`, sin sufijo de zona ni offset (docs/10 S2.2). Se asume que esa hora
local es siempre America/Santiago (ADR-0009), incluso para Magallanes/Isla de Pascua (riesgo
documentado, no bloqueante). Una hora local ambigua (fin del horario de verano) se interpreta con
`fold=0` (primera ocurrencia).

Una fecha centinela de .NET (ano <= 1950, ej. "1900-01-04T00:00:00", visto en `FechaTiempoEvaluacion`)
nunca es una fecha real: se trata como ausente (`parse_status='missing'`), igual que un texto vacio.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

CHILE_TZ = ZoneInfo("America/Santiago")
UTC_TZ = ZoneInfo("UTC")

_SENTINEL_MAX_YEAR = 1950


def parse_mp_datetime(raw: str | None) -> tuple[datetime | None, str]:
    """Parsea un texto de fecha/hora de la API de Mercado Publico.

    Devuelve `(instante_utc, parse_status)` con `parse_status` en `{"ok", "unparseable", "missing"}`.
    `instante_utc` es `None` salvo cuando `parse_status == "ok"`.
    """
    if raw is None:
        return None, "missing"
    text = raw.strip()
    if text == "":
        return None, "missing"

    # La API puede entregar hasta 7 cifras de fraccion de segundo (ticks de .NET);
    # `datetime.fromisoformat` solo acepta hasta 6 (microsegundos).
    if "." in text:
        base, _, frac = text.partition(".")
        frac = (frac + "000000")[:6]
        text = f"{base}.{frac}"

    try:
        naive = datetime.fromisoformat(text)
    except ValueError:
        return None, "unparseable"

    if naive.tzinfo is not None:
        # Nunca observado en la muestra real (docs/10 S2.2), pero si algun dia llega con offset,
        # se respeta en vez de reinterpretarlo como hora de Chile.
        if naive.year <= _SENTINEL_MAX_YEAR:
            return None, "missing"
        return naive.astimezone(UTC_TZ), "ok"

    if naive.year <= _SENTINEL_MAX_YEAR:
        return None, "missing"

    local = naive.replace(tzinfo=CHILE_TZ, fold=0)
    return local.astimezone(UTC_TZ), "ok"


def chile_calendar_date(instant: datetime | None = None) -> date:
    """Fecha calendario en America/Santiago para un instante dado (default: ahora)."""
    moment = instant if instant is not None else datetime.now(tz=UTC_TZ)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC_TZ)
    return moment.astimezone(CHILE_TZ).date()


def chile_now() -> datetime:
    return datetime.now(tz=UTC_TZ).astimezone(CHILE_TZ)


def to_utc(local_naive: datetime) -> datetime:
    """Convierte un `datetime` naive, interpretado como hora de Chile, a UTC (fold=0)."""
    return local_naive.replace(tzinfo=CHILE_TZ, fold=0).astimezone(UTC_TZ)
