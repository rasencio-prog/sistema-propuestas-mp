"""Cliente HTTP del adaptador `mp_v1` (ADR-0010): mismo endpoint `licitaciones.json` con `fecha` o
`codigo` (docs/10 S1). El ticket solo vive en memoria aqui (nunca se loguea, CLAUDE.md); el filtro de
`core/logging` ademas enmascara cualquier `ticket=` que se escape a un log.

Reintentos con backoff exponencial ante 429/5xx (2s/4s/8s, maximo 3 reintentos, ADR-0010): se trata
como comportamiento esperable, no excepcional (`/p2-api` observo un 429 real respetando 1 req/s).
El ritmo (cuanto esperar ANTES de cada solicitud nueva, sin contar reintentos) y el techo de cuota
diaria los decide quien inyecta `before_call`/`after_call` (`modules/radar/quota.py`), no este cliente:
aqui solo se sabe hablar con la API, sin logica de cuota propia.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from sp.modules.marketplace_adapters.base import (
    ApiCallResult,
    CanonicalListingEntry,
    CanonicalOpportunityDetail,
)
from sp.modules.marketplace_adapters.mp_v1.mapper import map_detail, map_listing_entry
from sp.modules.marketplace_adapters.mp_v1.schemas import (
    RawLicitacionDetail,
    RawListingResponse,
)

BASE_URL = "https://api.mercadopublico.cl/servicios/v1/publico/licitaciones.json"
_RETRYABLE_STATUS = {429}


class MarketplaceAdapterError(Exception):
    """La llamada a la API agoto los reintentos sin exito (nunca se pierde lo ya guardado, ADR-0010)."""

    def __init__(self, endpoint_name: str, http_status: int | None, error: str | None) -> None:
        self.endpoint_name = endpoint_name
        self.http_status = http_status
        self.error = error
        super().__init__(f"{endpoint_name}: HTTP {http_status} ({error})")


def _is_transient(status: int | None, error: str | None) -> bool:
    if error is not None:
        return True
    if status is None:
        return False
    return status in _RETRYABLE_STATUS or status >= 500


class MpV1Client:
    def __init__(
        self,
        ticket: str,
        *,
        http_client: httpx.Client | None = None,
        before_call: Callable[[str], None] | None = None,
        after_call: Callable[[ApiCallResult], None] | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._ticket = ticket
        self._client = http_client or httpx.Client(timeout=timeout_seconds)
        self._before_call = before_call or (lambda endpoint_name: None)
        self._after_call = after_call or (lambda result: None)
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._sleep = sleep
        self._clock = clock

    def fetch_listing(self, fecha_ddmmaaaa: str) -> list[CanonicalListingEntry]:
        data = self._request("listado", {"fecha": fecha_ddmmaaaa})
        parsed = RawListingResponse.model_validate(data)
        return [map_listing_entry(entry) for entry in parsed.Listado]

    def fetch_detail(self, official_code: str) -> CanonicalOpportunityDetail:
        data = self._request("detalle", {"codigo": official_code})
        listado = data.get("Listado") or []
        if not listado:
            raise MarketplaceAdapterError("detalle", 200, f"sin resultados para {official_code}")
        parsed = RawLicitacionDetail.model_validate(listado[0])
        return map_detail(parsed)

    def _request(self, endpoint_name: str, params: dict[str, str]) -> dict[str, Any]:
        self._before_call(endpoint_name)

        last_status: int | None = None
        last_error: str | None = None
        total_attempts = self._max_retries + 1

        for attempt in range(1, total_attempts + 1):
            start = self._clock()
            status: int | None = None
            transport_error: str | None = None
            payload: dict[str, Any] | None = None
            try:
                response = self._client.get(BASE_URL, params={**params, "ticket": self._ticket})
                status = response.status_code
                if status < 300:
                    payload = response.json()
            except httpx.HTTPError as exc:
                transport_error = str(exc)

            log_error = (
                transport_error
                if transport_error is not None
                else (None if payload is not None else f"HTTP {status}")
            )

            duration_ms = max(0, int((self._clock() - start) * 1000))
            self._after_call(
                ApiCallResult(
                    endpoint_name=endpoint_name,
                    params_sanitized=params,
                    http_status=status,
                    duration_ms=duration_ms,
                    attempt=attempt,
                    error=log_error,
                )
            )

            if payload is not None:
                return payload

            last_status, last_error = status, log_error
            if not _is_transient(status, transport_error) or attempt >= total_attempts:
                break
            self._sleep(self._backoff_base_seconds * (2 ** (attempt - 1)))

        raise MarketplaceAdapterError(endpoint_name, last_status, last_error)
