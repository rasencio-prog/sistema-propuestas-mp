"""Traduce las respuestas crudas de `mp_v1` (schemas.py) al modelo canonico (`base.py`).

Sin logica de negocio (docs/02 S1): solo mapeo de campos, coercion de tipos ya hecha en `schemas.py`,
y el tratamiento de "estado no documentado" (E2-11) y "dato no informado" (docs/10 S2.4: tanto
string vacio como null significan lo mismo). El mapeo de `date_type` esta confirmado en
`docs/03-modelo-datos.md` S8.2 / docs/10 S8.2.
"""

from __future__ import annotations

from sp.modules.marketplace_adapters.base import (
    KNOWN_STATUS_CODES,
    OPPORTUNITY_TYPE_TEXT,
    CanonicalBuyer,
    CanonicalDate,
    CanonicalItem,
    CanonicalListingEntry,
    CanonicalOpportunityDetail,
)
from sp.modules.marketplace_adapters.mp_v1.schemas import (
    RawLicitacionDetail,
    RawListingEntry,
)

# Orden y mapeo confirmados en docs/03 S8.2 (ya no "A VALIDAR"). `Fechas.FechaCierre` es el campo
# real de cierre de ofertas; el `FechaCierre` de la raiz del detalle siempre viene vacio (docs/10 S2.2)
# y no se usa.
_DATE_FIELD_MAP: tuple[tuple[str, str], ...] = (
    ("publication", "FechaPublicacion"),
    ("questions_close", "FechaFinal"),
    ("answers_publication", "FechaPubRespuestas"),
    ("offers_close", "FechaCierre"),
    ("technical_opening", "FechaActoAperturaTecnica"),
    ("economic_opening", "FechaActoAperturaEconomica"),
    ("award_estimated", "FechaEstimadaAdjudicacion"),
    ("award_actual", "FechaAdjudicacion"),
    ("support_physical", "FechaSoporteFisico"),
    ("evaluation_time", "FechaTiempoEvaluacion"),
    ("estimated_signature", "FechaEstimadaFirma"),
    ("site_visit", "FechaVisitaTerreno"),
    ("background_delivery", "FechaEntregaAntecedentes"),
    ("user_dates", "FechasUsuario"),
)


def _not_informed_to_none(value: str | None) -> str | None:
    """ "" y null significan lo mismo: "no informado" (docs/10 S2.4)."""
    if value is None or value == "":
        return None
    return value


def map_listing_entry(raw: RawListingEntry) -> CanonicalListingEntry:
    return CanonicalListingEntry(
        official_code=raw.CodigoExterno,
        title=raw.Nombre,
        official_status_code=raw.CodigoEstado,
        offers_close_raw=raw.FechaCierre,
        raw_listing_entry=raw.model_dump(mode="json"),
    )


def _map_buyer(raw: RawLicitacionDetail) -> CanonicalBuyer | None:
    comprador = raw.Comprador
    if not comprador.CodigoOrganismo or not comprador.CodigoUnidad:
        return None
    return CanonicalBuyer(
        organism_code=comprador.CodigoOrganismo,
        organism_name=comprador.NombreOrganismo or "",
        unit_code=comprador.CodigoUnidad,
        unit_name=comprador.NombreUnidad or "",
        unit_rut=_not_informed_to_none(comprador.RutUnidad),
        region=_not_informed_to_none(comprador.RegionUnidad),
        commune=_not_informed_to_none(comprador.ComunaUnidad),
    )


def _map_items(raw: RawLicitacionDetail) -> list[CanonicalItem]:
    items: list[CanonicalItem] = []
    for idx, raw_item in enumerate(raw.Items.Listado, start=1):
        items.append(
            CanonicalItem(
                line_no=raw_item.Correlativo or idx,
                product_code=raw_item.CodigoProducto,
                category_code=_not_informed_to_none(raw_item.CodigoCategoria),
                category_name=_not_informed_to_none(raw_item.Categoria),
                product_name=_not_informed_to_none(raw_item.NombreProducto),
                description=_not_informed_to_none(raw_item.Descripcion),
                quantity=raw_item.Cantidad,
                unit=_not_informed_to_none(raw_item.UnidadMedida),
            )
        )
    return items


def _map_dates(raw: RawLicitacionDetail) -> list[CanonicalDate]:
    fechas = raw.Fechas
    return [
        CanonicalDate(date_type=date_type, raw_text=getattr(fechas, field_name))
        for date_type, field_name in _DATE_FIELD_MAP
    ]


def _amount_visibility(visibilidad_monto: int | None) -> str:
    if visibilidad_monto is None:
        return "unknown"
    return "visible" if visibilidad_monto == 1 else "not_visible"


def map_detail(raw: RawLicitacionDetail) -> CanonicalOpportunityDetail:
    status_code = raw.CodigoEstado
    status_documented = status_code in KNOWN_STATUS_CODES
    # El detalle siempre trae `Estado` como texto (docs/10 S2.2); si alguna vez faltara, se usa la
    # tabla conocida o, en su defecto, el codigo crudo como texto (nunca se inventa una descripcion).
    status_text = _not_informed_to_none(raw.Estado) or KNOWN_STATUS_CODES.get(status_code, str(status_code))

    opportunity_type_code = _not_informed_to_none(raw.Tipo)
    adjudicacion = raw.Adjudicacion

    return CanonicalOpportunityDetail(
        official_code=raw.CodigoExterno,
        title=raw.Nombre,
        description=_not_informed_to_none(raw.Descripcion),
        opportunity_type_code=opportunity_type_code,
        opportunity_type_text=(
            OPPORTUNITY_TYPE_TEXT.get(opportunity_type_code) if opportunity_type_code else None
        ),
        official_status_code=status_code,
        official_status_text=status_text,
        official_status_documented=status_documented,
        buyer=_map_buyer(raw),
        estimated_amount=raw.MontoEstimado,
        currency=_not_informed_to_none(raw.Moneda),
        amount_visibility=_amount_visibility(raw.VisibilidadMonto),
        items=_map_items(raw),
        dates=_map_dates(raw),
        contract_duration_value=raw.TiempoDuracionContrato,
        contract_duration_unit_code=raw.UnidadTiempoDuracionContrato,
        is_renewable=raw.EsRenovable,
        renewal_value=raw.ValorTiempoRenovacion,
        renewal_period_text=_not_informed_to_none(raw.PeriodoTiempoRenovacion),
        subcontracting_allowed=raw.SubContratacion,
        contract_formalization_code=raw.Contrato,
        payment_modality_code=raw.Modalidad,
        payment_type_code=_not_informed_to_none(raw.TipoPago),
        contract_responsible_name=_not_informed_to_none(raw.NombreResponsableContrato),
        contract_responsible_email=_not_informed_to_none(raw.EmailResponsableContrato),
        contract_responsible_phone=_not_informed_to_none(raw.FonoResponsableContrato),
        payment_responsible_name=_not_informed_to_none(raw.NombreResponsablePago),
        payment_responsible_email=_not_informed_to_none(raw.EmailResponsablePago),
        buyer_complaints_count_snapshot=raw.CantidadReclamos,
        is_standard_type=raw.EsBaseTipo,
        award_act_type_code=adjudicacion.Tipo if adjudicacion else None,
        award_act_number=_not_informed_to_none(adjudicacion.Numero) if adjudicacion else None,
        award_offerors_count=adjudicacion.NumeroOferentes if adjudicacion else None,
        award_act_url=_not_informed_to_none(adjudicacion.UrlActa) if adjudicacion else None,
        raw_detail=raw.model_dump(mode="json"),
    )
