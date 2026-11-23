"""Clasificador por reglas (E2-6): palabras clave con/sin tilde, exclusiones que ganan, rubros.
Siempre sobre el detalle completo, nunca sobre el listado liviano (ADR-0010)."""

from __future__ import annotations

import uuid

from sp.modules.marketplace_adapters.base import CanonicalItem, CanonicalOpportunityDetail
from sp.modules.service_lines.classifier import classify_by_rules
from sp.modules.service_lines.models import ServiceLine


def _service_line(
    name: str,
    *,
    positive_keywords: list[str] | None = None,
    exclusion_keywords: list[str] | None = None,
    category_codes: list[str] | None = None,
    is_active: bool = True,
) -> ServiceLine:
    line = ServiceLine(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        name=name,
        positive_keywords=positive_keywords or [],
        exclusion_keywords=exclusion_keywords or [],
        category_codes=category_codes or [],
        is_active=is_active,
    )
    return line


def _detail(title: str, description: str | None = None, items: list[CanonicalItem] | None = None):
    return CanonicalOpportunityDetail(
        official_code="1-1-LE26",
        title=title,
        description=description,
        opportunity_type_code=None,
        opportunity_type_text=None,
        official_status_code=5,
        official_status_text="Publicada",
        official_status_documented=True,
        buyer=None,
        estimated_amount=None,
        currency=None,
        amount_visibility="unknown",
        items=items or [],
        dates=[],
        contract_duration_value=None,
        contract_duration_unit_code=None,
        is_renewable=None,
        renewal_value=None,
        renewal_period_text=None,
        subcontracting_allowed=None,
        contract_formalization_code=None,
        payment_modality_code=None,
        payment_type_code=None,
        contract_responsible_name=None,
        contract_responsible_email=None,
        contract_responsible_phone=None,
        payment_responsible_name=None,
        payment_responsible_email=None,
        buyer_complaints_count_snapshot=None,
        is_standard_type=None,
        award_act_type_code=None,
        award_act_number=None,
        award_offerors_count=None,
        award_act_url=None,
        raw_detail={},
    )


def test_matches_positive_keyword_case_and_accent_insensitive() -> None:
    line = _service_line("Desarrollo de software", positive_keywords=["mantención evolutiva"])
    detail = _detail("Servicio de MANTENCION EVOLUTIVA de sistema")
    matches = classify_by_rules(detail, [line])
    assert len(matches) == 1
    assert matches[0].service_line_id == line.id
    assert matches[0].matched_terms == ["mantención evolutiva"]


def test_exclusion_keyword_always_wins_over_positive_match() -> None:
    line = _service_line(
        "Soporte y servicios informáticos",
        positive_keywords=["soporte"],
        exclusion_keywords=["mobiliario"],
    )
    detail = _detail("Soporte de mobiliario de oficina")
    matches = classify_by_rules(detail, [line])
    assert matches == []


def test_category_code_match_on_items_not_on_listing() -> None:
    line = _service_line("Desarrollo de software", category_codes=["43231500"])
    item = CanonicalItem(
        line_no=1,
        product_code=43231501,
        category_code="43231500",
        category_name="Software",
        product_name="Licencia",
        description=None,
        quantity=1.0,
        unit="Unidad",
    )
    detail = _detail("Titulo generico sin palabras clave", items=[item])
    matches = classify_by_rules(detail, [line])
    assert len(matches) == 1
    assert matches[0].matched_codes == ["43231500"]


def test_inactive_service_line_is_never_matched() -> None:
    line = _service_line("Linea inactiva", positive_keywords=["software"], is_active=False)
    detail = _detail("Desarrollo de software a medida")
    assert classify_by_rules(detail, [line]) == []


def test_no_match_without_keywords_or_category() -> None:
    line = _service_line("Consultoría TI", positive_keywords=["auditoría"])
    detail = _detail("Compra de alimentos para casino institucional")
    assert classify_by_rules(detail, [line]) == []


def test_multiple_service_lines_can_match_independently() -> None:
    dev = _service_line("Desarrollo de software", positive_keywords=["aplicaciones"])
    cloud = _service_line("Cloud y servicios tecnológicos", positive_keywords=["migración cloud"])
    detail = _detail("Desarrollo de aplicaciones con migración cloud incluida")
    matches = classify_by_rules(detail, [dev, cloud])
    assert {m.service_line_id for m in matches} == {dev.id, cloud.id}
