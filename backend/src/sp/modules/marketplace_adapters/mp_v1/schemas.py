"""Modelos Pydantic de la respuesta cruda de `licitaciones.json` (docs/10-api-validada.md).

Varios campos que el manual oficial documenta como entero/bit llegan en la practica como string JSON
(docs/10 S2.2, S2.4); estos modelos coaccionan explicitamente esos campos, nunca asumen el tipo del
manual sin verificar (CLAUDE.md). `extra="allow"` en todos: nunca se descarta el resto de la respuesta
(termina en `raw_detail`/`raw_listing_entry`), pero tampoco se inventan campos fuera de los confirmados
en `docs/10`.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        return int(float(stripped))
    raise TypeError(f"No se puede coaccionar a int: {value!r}")


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        return float(stripped)
    raise TypeError(f"No se puede coaccionar a float: {value!r}")


def _coerce_bool01(value: Any) -> bool | None:
    """Campos tipo bit documentados como 0/1 que llegan como int o como string ("0"/"1")."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        return stripped not in ("0", "")
    raise TypeError(f"No se puede coaccionar a bool: {value!r}")


def _coerce_str_or_none(value: Any) -> str | None:
    """Varios campos de responsables llegan como string vacio en vez de null (docs/10 S2.4);
    ambos se tratan como 'no informado' mas arriba, aqui solo se preserva el string vacio tal cual."""
    if value is None:
        return None
    return str(value)


IntFromStr = Annotated[int | None, BeforeValidator(_coerce_int)]
FloatFromStr = Annotated[float | None, BeforeValidator(_coerce_float)]
BoolFromBit = Annotated[bool | None, BeforeValidator(_coerce_bool01)]
OptionalStr = Annotated[str | None, BeforeValidator(_coerce_str_or_none)]
# `CodigoEstado` nunca viene vacio en la muestra real (docs/10 S2.1, S2.2): se coacciona el tipo
# igual que los opcionales, pero el campo sigue siendo obligatorio (nunca `None`).
RequiredIntFromStr = Annotated[int, BeforeValidator(_coerce_int)]


class RawListingEntry(BaseModel):
    """Listado por `fecha` (docs/10 S2.1): siempre estos 4 campos, nada mas."""

    model_config = ConfigDict(extra="allow")

    CodigoExterno: str
    Nombre: str
    CodigoEstado: RequiredIntFromStr
    FechaCierre: OptionalStr = None


class RawListingResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    Cantidad: IntFromStr = None
    Listado: list[RawListingEntry] = []


class RawFechas(BaseModel):
    model_config = ConfigDict(extra="allow")

    FechaPublicacion: OptionalStr = None
    FechaFinal: OptionalStr = None
    FechaPubRespuestas: OptionalStr = None
    FechaCierre: OptionalStr = None
    FechaActoAperturaTecnica: OptionalStr = None
    FechaActoAperturaEconomica: OptionalStr = None
    FechaEstimadaAdjudicacion: OptionalStr = None
    FechaAdjudicacion: OptionalStr = None
    FechaSoporteFisico: OptionalStr = None
    FechaTiempoEvaluacion: OptionalStr = None
    FechaEstimadaFirma: OptionalStr = None
    FechaVisitaTerreno: OptionalStr = None
    FechaEntregaAntecedentes: OptionalStr = None
    FechasUsuario: OptionalStr = None


class RawItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    Correlativo: IntFromStr = None
    CodigoProducto: IntFromStr = None
    CodigoCategoria: OptionalStr = None
    Categoria: OptionalStr = None
    NombreProducto: OptionalStr = None
    Descripcion: OptionalStr = None
    UnidadMedida: OptionalStr = None
    Cantidad: FloatFromStr = None


class RawItems(BaseModel):
    model_config = ConfigDict(extra="allow")

    Cantidad: IntFromStr = None
    Listado: list[RawItem] = []


class RawComprador(BaseModel):
    model_config = ConfigDict(extra="allow")

    CodigoOrganismo: OptionalStr = None
    NombreOrganismo: OptionalStr = None
    CodigoUnidad: OptionalStr = None
    NombreUnidad: OptionalStr = None
    RutUnidad: OptionalStr = None
    RegionUnidad: OptionalStr = None
    ComunaUnidad: OptionalStr = None


class RawAdjudicacion(BaseModel):
    model_config = ConfigDict(extra="allow")

    Tipo: IntFromStr = None
    Fecha: OptionalStr = None
    Numero: OptionalStr = None
    NumeroOferentes: IntFromStr = None
    UrlActa: OptionalStr = None


class RawLicitacionDetail(BaseModel):
    """Detalle por `codigo` (docs/10 S2.2, S9): ~85 campos; solo se modelan los que usa el diseno."""

    model_config = ConfigDict(extra="allow")

    CodigoExterno: str
    Nombre: str
    Descripcion: OptionalStr = None
    Tipo: OptionalStr = None
    CodigoTipo: IntFromStr = None
    CodigoEstado: RequiredIntFromStr
    Estado: OptionalStr = None

    Fechas: RawFechas = RawFechas()
    Comprador: RawComprador = RawComprador()
    Items: RawItems = RawItems()
    Adjudicacion: RawAdjudicacion | None = None

    MontoEstimado: FloatFromStr = None
    VisibilidadMonto: IntFromStr = None
    Moneda: OptionalStr = None
    Estimacion: IntFromStr = None

    TiempoDuracionContrato: IntFromStr = None
    UnidadTiempoDuracionContrato: IntFromStr = None
    TipoDuracionContrato: OptionalStr = None
    EsRenovable: BoolFromBit = None
    ValorTiempoRenovacion: IntFromStr = None
    PeriodoTiempoRenovacion: OptionalStr = None
    SubContratacion: BoolFromBit = None
    Contrato: IntFromStr = None
    EsBaseTipo: BoolFromBit = None

    Modalidad: IntFromStr = None
    # TipoPago: columna "text" en docs/03 (valores no documentados observados, ej. "-1");
    # se guarda crudo, nunca se coacciona a int (docs/10 S2.4).
    TipoPago: OptionalStr = None
    NombreResponsableContrato: OptionalStr = None
    EmailResponsableContrato: OptionalStr = None
    FonoResponsableContrato: OptionalStr = None
    NombreResponsablePago: OptionalStr = None
    EmailResponsablePago: OptionalStr = None
    CantidadReclamos: IntFromStr = None
