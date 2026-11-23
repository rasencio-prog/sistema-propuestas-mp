"""El endpoint `/api/radar/run` (`run_radar_task.defer(...)`) necesita el conector de Procrastinate
abierto; sin un lifespan que lo abra, falla con `AppNotOpen` en cuanto un administrador lo usa
(encontrado al probar la carga inicial completa del radar, /p4-radar segunda revision)."""

from __future__ import annotations

import asyncio

from sp.jobs.app import app as procrastinate_app
from sp.main import _lifespan
from sp.main import app as fastapi_app


def test_lifespan_opens_and_closes_the_procrastinate_connector(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_open_async() -> None:
        calls.append("open")

    async def fake_close_async() -> None:
        calls.append("close")

    monkeypatch.setattr(procrastinate_app, "open_async", fake_open_async)
    monkeypatch.setattr(procrastinate_app, "close_async", fake_close_async)

    async def run() -> None:
        async with _lifespan(fastapi_app):
            assert calls == ["open"]

    asyncio.run(run())
    assert calls == ["open", "close"]
