"""Adaptador mp_v1: respuestas crudas (incluidas muestras reales grabadas en docs/api-samples) ->
modelo canonico. Nunca llama a la API real (docs/07 S0)."""

from __future__ import annotations

import json
from pathlib import Path

from sp.modules.marketplace_adapters.mp_v1.mapper import map_detail, map_listing_entry
from sp.modules.marketplace_adapters.mp_v1.schemas import RawLicitacionDetail, RawListingResponse

SAMPLES_DIR = Path(__file__).resolve().parents[4] / "docs" / "api-samples"


def _load(name: str) -> dict:
    return json.loads((SAMPLES_DIR / name).read_text(encoding="utf-8"))


def test_maps_real_listing_sample_only_four_fields() -> None:
    raw = RawListingResponse.model_validate(_load("listado_2026-11-20.json"))
    assert len(raw.Listado) > 1000
    entry = map_listing_entry(raw.Listado[0])
    assert entry.official_code == "1057384-176-L126"
    assert entry.official_status_code == 6
    assert entry.offers_close_raw == "2026-11-20T20:00:00"


def test_maps_real_detail_sample_closed_with_visible_amount() -> None:
    raw = RawLicitacionDetail.model_validate(_load("detalle_1057384-176-L126.json")["Listado"][0])
    detail = map_detail(raw)

    assert detail.official_code == "1057384-176-L126"
    assert detail.official_status_code == 6
    assert detail.official_status_text == "Cerrada"
    assert detail.official_status_documented is True
    assert detail.amount_visibility == "visible"
    assert detail.estimated_amount == 250000.0
    assert detail.buyer is not None
    assert detail.buyer.organism_code == "7385"
    assert detail.buyer.unit_code == "1057384"
    assert len(detail.items) == 1
    assert detail.items[0].category_code == "78111800"
    assert detail.items[0].product_code == 78111803


def test_maps_real_detail_sample_awarded_with_award_fields() -> None:
    raw = RawLicitacionDetail.model_validate(_load("detalle_ti_1111089-20-LE26.json")["Listado"][0])
    detail = map_detail(raw)

    assert detail.official_status_code == 8
    assert detail.official_status_text == "Adjudicada"
    assert detail.award_act_number == "9723"
    assert detail.award_offerors_count == 4
    assert detail.award_act_url is not None and detail.award_act_url.startswith("http")
    assert detail.contract_duration_value == 12
    assert detail.contract_duration_unit_code == 4
    assert detail.is_renewable is False
    assert detail.subcontracting_allowed is True
    # docs/10 S2.4: TipoPago se guarda crudo (string), nunca se mapea a un texto inventado.
    assert detail.payment_type_code == "1"


def test_undocumented_status_code_is_flagged_not_raised() -> None:
    # E2-11: un CodigoEstado fuera de la tabla conocida (ej. 15) se guarda crudo, nunca falla.
    raw = RawLicitacionDetail.model_validate(
        {
            "CodigoExterno": "9999999-1-LE26",
            "Nombre": "Licitacion con estado no documentado",
            "CodigoEstado": 15,
            "Estado": "Estado-15-sin-documentar",
        }
    )
    detail = map_detail(raw)
    assert detail.official_status_code == 15
    assert detail.official_status_documented is False
    assert detail.official_status_text == "Estado-15-sin-documentar"


def test_amount_not_visible_is_none_never_zero() -> None:
    raw = RawLicitacionDetail.model_validate(
        {
            "CodigoExterno": "1-1-LE26",
            "Nombre": "Sin monto visible",
            "CodigoEstado": 5,
            "Estado": "Publicada",
            "VisibilidadMonto": 0,
            "MontoEstimado": None,
            "Moneda": "CLP",
        }
    )
    detail = map_detail(raw)
    assert detail.amount_visibility == "not_visible"
    assert detail.estimated_amount is None


def test_empty_string_and_null_both_treated_as_not_informed() -> None:
    # docs/10 S2.4: EmailResponsableContrato llega como "" (nunca null); se normaliza igual que null.
    raw = RawLicitacionDetail.model_validate(
        {
            "CodigoExterno": "2-1-LE26",
            "Nombre": "Responsables vacios",
            "CodigoEstado": 5,
            "Estado": "Publicada",
            "EmailResponsableContrato": "",
            "NombreResponsablePago": None,
        }
    )
    detail = map_detail(raw)
    assert detail.contract_responsible_email is None
    assert detail.payment_responsible_name is None


def test_string_numeric_and_boolean_fields_are_coerced() -> None:
    # docs/10 S2.2: varios campos documentados como entero/bit llegan como string JSON.
    raw = RawLicitacionDetail.model_validate(
        {
            "CodigoExterno": "3-1-LE26",
            "Nombre": "Tipos inconsistentes",
            "CodigoEstado": 5,
            "Estado": "Publicada",
            "TiempoDuracionContrato": "24",
            "UnidadTiempoDuracionContrato": 4,
            "EsRenovable": "0",
            "SubContratacion": "1",
            "EsBaseTipo": 1,
            "CantidadReclamos": "1263",
        }
    )
    detail = map_detail(raw)
    assert detail.contract_duration_value == 24
    assert detail.is_renewable is False
    assert detail.subcontracting_allowed is True
    assert detail.is_standard_type is True
    assert detail.buyer_complaints_count_snapshot == 1263


def test_dates_mapped_to_all_fourteen_types_with_original_text() -> None:
    raw = RawLicitacionDetail.model_validate(_load("detalle_1057384-176-L126.json")["Listado"][0])
    detail = map_detail(raw)
    date_types = {d.date_type for d in detail.dates}
    assert date_types == {
        "publication",
        "questions_close",
        "answers_publication",
        "offers_close",
        "technical_opening",
        "economic_opening",
        "award_estimated",
        "award_actual",
        "support_physical",
        "evaluation_time",
        "estimated_signature",
        "site_visit",
        "background_delivery",
        "user_dates",
    }


def test_opportunity_type_text_from_fixed_table_never_invented() -> None:
    raw = RawLicitacionDetail.model_validate(
        {
            "CodigoExterno": "4-1-LE26",
            "Nombre": "Tipo conocido",
            "CodigoEstado": 5,
            "Estado": "Publicada",
            "Tipo": "LE",
        }
    )
    detail = map_detail(raw)
    assert detail.opportunity_type_code == "LE"
    assert detail.opportunity_type_text is not None and "100 UTM" in detail.opportunity_type_text
