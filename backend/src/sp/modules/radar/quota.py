"""Control de cuota y ritmo del radar (ADR-0010, E2-2): techo diario configurable (`api_credentials.
daily_limit`, por debajo de 10.000) contado por **dia calendario de Chile**, y ritmo configurable
entre solicitudes nuevas (no entre reintentos: esos los paga el backoff del cliente).

Se conecta al cliente del adaptador (`MpV1Client`) como `before_call`/`after_call`: el cliente no
sabe nada de cuota ni de Postgres, solo llama a estos hooks.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from datetime import date, datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from sp.core.timezones import UTC_TZ, chile_calendar_date
from sp.modules.marketplace_adapters.base import ApiCallResult, QuotaExceededError
from sp.modules.radar.models import ApiCallLog, ApiQuotaUsage


class QuotaManager:
    def __init__(
        self,
        db: Session,
        *,
        credential_id: uuid.UUID,
        daily_limit: int,
        rate_limit_seconds: float,
        radar_run_id: uuid.UUID | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(tz=UTC_TZ),
    ) -> None:
        self._db = db
        self._credential_id = credential_id
        self._daily_limit = daily_limit
        self._rate_limit_seconds = rate_limit_seconds
        self._radar_run_id = radar_run_id
        self._sleep = sleep
        self._clock = clock
        self._now = now
        self._last_call_monotonic: float | None = None
        self._current_correlation_id: str | None = None

    def current_count(self, *, quota_date: date | None = None) -> int:
        quota_date = quota_date or chile_calendar_date(self._now())
        row = self._db.get(ApiQuotaUsage, (self._credential_id, quota_date))
        return row.requests_count if row is not None else 0

    def quota_exceeded(self) -> bool:
        return self.current_count() >= self._daily_limit

    def before_call(self, _endpoint_name: str) -> None:
        """Techo de cuota (antes de iniciar una solicitud nueva) + espera del ritmo configurado."""
        if self.quota_exceeded():
            raise QuotaExceededError(f"Limite diario de cuota alcanzado ({self._daily_limit}).")
        self._current_correlation_id = str(uuid.uuid4())
        self._pace()

    def _pace(self) -> None:
        if self._last_call_monotonic is not None:
            elapsed = self._clock() - self._last_call_monotonic
            remaining = self._rate_limit_seconds - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_call_monotonic = self._clock()

    def after_call(self, result: ApiCallResult) -> None:
        """Registra la llamada real (`api_call_log`) y cuenta cuota consumida (`api_quota_usage`),
        por cada intento real hecho a la API (incluidos reintentos: tambien consumen cuota real
        del lado de ChileCompra)."""
        today = chile_calendar_date(self._now())
        stmt = (
            pg_insert(ApiQuotaUsage)
            .values(credential_id=self._credential_id, quota_date=today, requests_count=1)
            .on_conflict_do_update(
                index_elements=[ApiQuotaUsage.credential_id, ApiQuotaUsage.quota_date],
                set_={
                    "requests_count": ApiQuotaUsage.requests_count + 1,
                    "updated_at": text("now()"),
                },
            )
        )
        self._db.execute(stmt)
        self._db.add(
            ApiCallLog(
                credential_id=self._credential_id,
                radar_run_id=self._radar_run_id,
                endpoint_name=result.endpoint_name,
                params_sanitized=result.params_sanitized,
                http_status=result.http_status,
                duration_ms=result.duration_ms,
                attempt=result.attempt,
                correlation_id=self._current_correlation_id,
                error=result.error,
            )
        )
        self._db.flush()
