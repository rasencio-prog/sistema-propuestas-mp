"""E1-2 (docs/05-backlog): un ticket/secreto no debe aparecer en el log, ni como campo propio ni
embebido dentro de un valor mas largo (p. ej. una URL)."""

from __future__ import annotations

import json

import structlog

from sp.core.logging import _scrub_secrets, configure_logging

FAKE_TICKET = "FICTICIO-TICKET-123456"


def test_scrub_secrets_masks_field_named_like_a_secret() -> None:
    event = {"event": "mp_call", "mp_ticket": FAKE_TICKET, "status": "ok"}

    scrubbed = _scrub_secrets(None, "info", event)

    assert scrubbed["mp_ticket"] == "***"
    assert FAKE_TICKET not in json.dumps(scrubbed)


def test_scrub_secrets_masks_ticket_embedded_in_a_url() -> None:
    url = (
        f"https://api.mercadopublico.cl/servicios/v1/publico/licitaciones?ticket={FAKE_TICKET}&fecha=20261122"
    )
    event = {"event": "mp_call", "url": url}

    scrubbed = _scrub_secrets(None, "info", event)

    assert FAKE_TICKET not in scrubbed["url"]
    assert FAKE_TICKET not in json.dumps(scrubbed)
    assert "fecha=20261122" in scrubbed["url"]  # el resto de la URL sigue siendo util para depurar


def test_configured_logger_output_never_contains_the_ticket(capsys) -> None:
    configure_logging("INFO")
    logger = structlog.get_logger("test")

    logger.info(
        "mp_call",
        url=f"https://api.mercadopublico.cl/...?ticket={FAKE_TICKET}",
        mp_ticket=FAKE_TICKET,
    )

    captured = capsys.readouterr()
    assert FAKE_TICKET not in captured.out
    assert FAKE_TICKET not in captured.err
