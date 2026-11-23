"""ADR-0010: decision de pedir detalle, sin tocar la base (logica pura)."""

from __future__ import annotations

from datetime import UTC, datetime

from sp.modules.marketplace_adapters.base import CanonicalListingEntry
from sp.modules.opportunities.models import Opportunity
from sp.modules.opportunities.service import build_source_url, needs_detail_fetch, recompute_internal_status

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _listing(
    code: str = "1-1-LE26", status: int = 5, close: str | None = "2026-12-01T00:00:00"
) -> CanonicalListingEntry:
    return CanonicalListingEntry(
        official_code=code,
        title="x",
        official_status_code=status,
        offers_close_raw=close,
        raw_listing_entry={"CodigoExterno": code, "CodigoEstado": status, "FechaCierre": close},
    )


def test_new_and_published_needs_detail() -> None:
    assert needs_detail_fetch(None, _listing(status=5)) is True


def test_new_and_not_published_does_not_need_detail() -> None:
    assert needs_detail_fetch(None, _listing(status=6)) is False


def test_known_without_change_does_not_need_detail() -> None:
    existing = Opportunity(
        official_code="1-1-LE26",
        title="x",
        official_status_code=6,
        official_status_text="Cerrada",
        raw_list={"FechaCierre": "2026-12-01T00:00:00"},
    )
    assert needs_detail_fetch(existing, _listing(status=6, close="2026-12-01T00:00:00")) is False


def test_known_with_status_change_needs_detail() -> None:
    existing = Opportunity(
        official_code="1-1-LE26",
        title="x",
        official_status_code=5,
        official_status_text="Publicada",
        raw_list={"FechaCierre": "2026-12-01T00:00:00"},
    )
    assert needs_detail_fetch(existing, _listing(status=6, close="2026-12-01T00:00:00")) is True


def test_known_with_close_date_change_needs_detail() -> None:
    existing = Opportunity(
        official_code="1-1-LE26",
        title="x",
        official_status_code=5,
        official_status_text="Publicada",
        raw_list={"FechaCierre": "2026-12-01T00:00:00"},
    )
    assert needs_detail_fetch(existing, _listing(status=5, close="2026-12-15T00:00:00")) is True


def test_source_url_matches_confirmed_pattern() -> None:
    assert build_source_url("1057389-73-LP26") == (
        "https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx"
        "?idlicitacion=1057389-73-LP26"
    )


def test_recompute_internal_status_moves_detectada_to_cerrada_sin_decision() -> None:
    opportunity = Opportunity(
        official_code="1-1-LE26",
        title="x",
        official_status_code=6,
        official_status_text="Cerrada",
        internal_status="detectada",
    )
    recompute_internal_status(opportunity, now=NOW)
    assert opportunity.internal_status == "cerrada_sin_decision"
    assert opportunity.internal_status_changed_at == NOW


def test_recompute_internal_status_never_touches_documentos_pendientes() -> None:
    opportunity = Opportunity(
        official_code="1-1-LE26",
        title="x",
        official_status_code=6,
        official_status_text="Cerrada",
        internal_status="documentos_pendientes",
    )
    recompute_internal_status(opportunity, now=NOW)
    assert opportunity.internal_status == "documentos_pendientes"


def test_recompute_internal_status_keeps_published_detectada_unchanged() -> None:
    opportunity = Opportunity(
        official_code="1-1-LE26",
        title="x",
        official_status_code=5,
        official_status_text="Publicada",
        internal_status="detectada",
    )
    recompute_internal_status(opportunity, now=NOW)
    assert opportunity.internal_status == "detectada"
