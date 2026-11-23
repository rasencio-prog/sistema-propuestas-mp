"""Cliente mp_v1: ritmo, cuota (hooks before/after) y backoff ante 429/5xx (ADR-0010).
Nunca llama a la API real: `respx` simula httpx (docs/07 S0)."""

from __future__ import annotations

import httpx
import respx

from sp.modules.marketplace_adapters.base import ApiCallResult, QuotaExceededError
from sp.modules.marketplace_adapters.mp_v1.client import (
    BASE_URL,
    MarketplaceAdapterError,
    MpV1Client,
)


def _make_client(**kwargs):
    calls_before: list[str] = []
    calls_after: list[ApiCallResult] = []
    sleeps: list[float] = []

    client = MpV1Client(
        "fake-ticket",
        before_call=calls_before.append,
        after_call=calls_after.append,
        sleep=sleeps.append,
        clock=iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]).__next__,
        **kwargs,
    )
    return client, calls_before, calls_after, sleeps


@respx.mock
def test_fetch_listing_success_no_retry() -> None:
    respx.get(BASE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "Cantidad": 1,
                "Listado": [
                    {"CodigoExterno": "1-1-LE26", "Nombre": "x", "CodigoEstado": 5, "FechaCierre": None}
                ],
            },
        )
    )
    client, before, after, sleeps = _make_client()
    entries = client.fetch_listing("20112026")
    assert len(entries) == 1
    assert before == ["listado"]
    assert len(after) == 1
    assert after[0].http_status == 200
    assert after[0].attempt == 1
    assert sleeps == []


@respx.mock
def test_retries_with_exponential_backoff_on_429() -> None:
    route = respx.get(BASE_URL)
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(429),
        httpx.Response(200, json={"Listado": []}),
    ]
    client, before, after, sleeps = _make_client(max_retries=3, backoff_base_seconds=2.0)
    client.fetch_listing("20112026")

    assert [call.attempt for call in after] == [1, 2, 3]
    assert [call.http_status for call in after] == [429, 429, 200]
    assert sleeps == [2.0, 4.0]


@respx.mock
def test_exhausts_retries_and_raises_without_losing_state() -> None:
    respx.get(BASE_URL).mock(return_value=httpx.Response(500))
    client, before, after, sleeps = _make_client(max_retries=3, backoff_base_seconds=2.0)

    try:
        client.fetch_detail("1-1-LE26")
        raised = False
    except MarketplaceAdapterError as exc:
        raised = True
        assert exc.http_status == 500

    assert raised
    assert len(after) == 4  # 1 intento inicial + 3 reintentos
    assert sleeps == [2.0, 4.0, 8.0]


@respx.mock
def test_non_transient_4xx_does_not_retry() -> None:
    respx.get(BASE_URL).mock(return_value=httpx.Response(404))
    client, before, after, sleeps = _make_client()

    try:
        client.fetch_listing("20112026")
        raised = False
    except MarketplaceAdapterError:
        raised = True

    assert raised
    assert len(after) == 1
    assert sleeps == []


@respx.mock
def test_before_call_can_block_a_new_request_quota_exceeded() -> None:
    def before_call(_endpoint_name: str) -> None:
        raise QuotaExceededError("limite alcanzado")

    client = MpV1Client("fake-ticket", before_call=before_call)
    route = respx.get(BASE_URL)
    try:
        client.fetch_listing("20112026")
        raised = False
    except QuotaExceededError:
        raised = True
    assert raised
    assert not route.called


@respx.mock
def test_ticket_never_appears_in_params_sanitized() -> None:
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json={"Listado": []}))
    captured: list[ApiCallResult] = []
    client = MpV1Client("super-secret-ticket", after_call=captured.append)
    client.fetch_listing("20112026")
    assert len(captured) == 1
    assert "super-secret-ticket" not in str(captured[0].params_sanitized)
    assert "ticket" not in captured[0].params_sanitized
