"""Modelo canonico interno del radar (docs/02 S1, docs/03): lo unico que conocen los modulos de
negocio (`opportunities`, `scoring`, `service_lines`). Ningun adaptador de mercado expone aqui sus
nombres de campo originales ni logica de negocio (CLAUDE.md, ADR vigente de arquitectura).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

# Estados oficiales documentados por ChileCompra (docs/10 S3). Cualquier otro codigo observado
# (ej. 15, 16) se guarda crudo con `official_status_documented=False` (E2-11).
KNOWN_STATUS_CODES: dict[int, str] = {
    5: "Publicada",
    6: "Cerrada",
    7: "Desierta",
    8: "Adjudicada",
    18: "Revocada",
    19: "Suspendida",
}

# Tabla 3.1 del manual oficial (docs/10 S3): texto construido a partir de una tabla fija publicada,
# no inventado (igual tratamiento que `holidays` para dias habiles).
OPPORTUNITY_TYPE_TEXT: dict[str, str] = {
    "L1": "Licitación Pública menor a 100 UTM",
    "LE": "Licitación Pública igual o superior a 100 UTM e inferior a 1.000 UTM",
    "LP": "Licitación Pública igual o superior a 1.000 UTM e inferior a 2.000 UTM",
    "LQ": "Licitación Pública igual o superior a 2.000 UTM e inferior a 5.000 UTM",
    "LR": "Licitación Pública igual o superior a 5.000 UTM",
    "LS": "Licitación Pública de servicios personales especializados",
    "E2": "Licitación Privada menor a 100 UTM",
    "CO": "Licitación Privada igual o superior a 100 UTM e inferior a 1.000 UTM",
    "B2": "Licitación Privada igual o superior a 1.000 UTM e inferior a 2.000 UTM",
    "H2": "Licitación Privada igual o superior a 2.000 UTM e inferior a 5.000 UTM",
    "I2": "Licitación Privada superior a 5.000 UTM",
}


class CanonicalListingEntry(BaseModel):
    """Una fila del listado diario liviano (docs/10 S2.1): solo 4 campos, nunca rubro/monto/comprador."""

    official_code: str
    title: str
    official_status_code: int
    offers_close_raw: str | None
    raw_listing_entry: dict


class CanonicalBuyer(BaseModel):
    organism_code: str
    organism_name: str
    unit_code: str
    unit_name: str
    unit_rut: str | None
    region: str | None
    commune: str | None


class CanonicalItem(BaseModel):
    line_no: int
    product_code: int | None
    category_code: str | None
    category_name: str | None
    product_name: str | None
    description: str | None
    quantity: float | None
    unit: str | None


class CanonicalDate(BaseModel):
    date_type: str
    raw_text: str | None


class CanonicalOpportunityDetail(BaseModel):
    """Detalle completo de una licitacion (docs/10 S2.2, S9), ya coaccionado a tipos propios."""

    official_code: str
    title: str
    description: str | None
    opportunity_type_code: str | None
    opportunity_type_text: str | None

    official_status_code: int
    official_status_text: str
    official_status_documented: bool

    buyer: CanonicalBuyer | None

    estimated_amount: float | None
    currency: str | None
    amount_visibility: str  # visible|not_visible|unknown

    items: list[CanonicalItem]
    dates: list[CanonicalDate]

    contract_duration_value: int | None
    contract_duration_unit_code: int | None
    is_renewable: bool | None
    renewal_value: int | None
    renewal_period_text: str | None
    subcontracting_allowed: bool | None
    contract_formalization_code: int | None
    payment_modality_code: int | None
    payment_type_code: str | None
    contract_responsible_name: str | None
    contract_responsible_email: str | None
    contract_responsible_phone: str | None
    payment_responsible_name: str | None
    payment_responsible_email: str | None
    buyer_complaints_count_snapshot: int | None
    is_standard_type: bool | None
    award_act_type_code: int | None
    award_act_number: str | None
    award_offerors_count: int | None
    award_act_url: str | None

    raw_detail: dict


class ApiCallResult(BaseModel):
    """Metadatos de una llamada HTTP real al adaptador, para `api_call_log` (nunca el ticket)."""

    endpoint_name: str
    params_sanitized: dict
    http_status: int | None
    duration_ms: int
    attempt: int
    error: str | None = None


class QuotaExceededError(Exception):
    """La cuota diaria propia (`api_credentials.daily_limit`) se agoto: la corrida termina 'parcial'."""


class MarketplaceAdapter(Protocol):
    """Protocolo que debe cumplir cualquier version de adaptador (`mp_v1`, futuro `mp_v2`)."""

    def fetch_listing(self, fecha_ddmmaaaa: str) -> list[CanonicalListingEntry]: ...

    def fetch_active_listing(self) -> list[CanonicalListingEntry]: ...

    def fetch_detail(self, official_code: str) -> CanonicalOpportunityDetail: ...
