"""Clasificador por linea de servicio (E2-6, docs/05): dos capas.

(a) Reglas deterministicas: palabras clave positivas y de exclusion (con y sin tilde), y rubros
(`category_codes` contra `Items.Listado[].CodigoCategoria`). Las exclusiones ganan siempre. Opera
sobre el **detalle completo** (nombre, descripcion, items), nunca sobre el listado liviano
(ADR-0010).

(b) Capa IA opcional y desactivable detras de `LLMServiceLineClassifier` (protocolo): por defecto
usa `NullLLMClassifier`, que no llama a ningun proveedor y no agrega lineas. La implementacion real
contra un `LLMProvider` (ADR-0005) es trabajo de `/p7-analisis`; aqui solo se deja el punto de
extension ya desactivado, para no construir infraestructura de LLM antes de que haga falta.
"""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import delete
from sqlalchemy.orm import Session

from sp.modules.marketplace_adapters.base import CanonicalOpportunityDetail
from sp.modules.opportunities.models import OpportunityServiceLine
from sp.modules.service_lines.models import ServiceLine

RULES_METHOD = "rules"
LLM_METHOD = "llm"


@dataclass(frozen=True)
class ClassificationMatch:
    service_line_id: uuid.UUID
    service_line_name: str
    method: str
    matched_terms: list[str]
    matched_codes: list[str]
    confidence: float
    justification: str


def _normalize(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _haystack(detail: CanonicalOpportunityDetail) -> str:
    parts = [detail.title, detail.description or ""]
    for item in detail.items:
        parts.extend(filter(None, [item.product_name, item.description, item.category_name]))
    return _normalize(" ".join(parts))


def classify_by_rules(
    detail: CanonicalOpportunityDetail, service_lines: list[ServiceLine]
) -> list[ClassificationMatch]:
    haystack = _haystack(detail)
    item_category_codes = {item.category_code for item in detail.items if item.category_code}

    matches: list[ClassificationMatch] = []
    for line in service_lines:
        if not line.is_active:
            continue

        exclusion_hits = [kw for kw in line.exclusion_keywords if _normalize(kw) in haystack]
        if exclusion_hits:
            # Las exclusiones ganan: nunca se asigna la linea, aunque haya palabras positivas.
            continue

        positive_hits = [kw for kw in line.positive_keywords if _normalize(kw) in haystack]
        category_hits = sorted(item_category_codes & set(line.category_codes))
        if not positive_hits and not category_hits:
            continue

        confidence = min(1.0, round(0.30 + 0.15 * len(positive_hits) + 0.25 * len(category_hits), 2))

        justification_bits = []
        if positive_hits:
            justification_bits.append("palabras clave: " + ", ".join(positive_hits))
        if category_hits:
            justification_bits.append("rubro UNSPSC: " + ", ".join(category_hits))
        justification = f"{line.name} — " + "; ".join(justification_bits) + "."

        matches.append(
            ClassificationMatch(
                service_line_id=line.id,
                service_line_name=line.name,
                method=RULES_METHOD,
                matched_terms=positive_hits,
                matched_codes=category_hits,
                confidence=confidence,
                justification=justification,
            )
        )
    return matches


class LLMServiceLineClassifier(Protocol):
    """Punto de extension para la capa opcional de IA (ADR-0005): solo factores y lineas, nunca
    el puntaje. Implementacion real pendiente de `/p7-analisis` (LLMProvider)."""

    def classify(
        self, detail: CanonicalOpportunityDetail, service_lines: list[ServiceLine]
    ) -> list[ClassificationMatch]: ...


class NullLLMClassifier:
    """Desactivada por defecto (E2-6: "opcional y desactivable"). No llama a ningun proveedor."""

    def classify(
        self, detail: CanonicalOpportunityDetail, service_lines: list[ServiceLine]
    ) -> list[ClassificationMatch]:
        return []


def classify_and_persist(
    db: Session,
    *,
    opportunity_id: uuid.UUID,
    detail: CanonicalOpportunityDetail,
    service_lines: list[ServiceLine],
    llm_classifier: LLMServiceLineClassifier | None = None,
) -> tuple[list[ClassificationMatch], str]:
    """Reemplaza las lineas asignadas (ambos metodos) y devuelve las coincidencias mas una
    justificacion legible para `opportunities.classification_justification`."""
    rule_matches = classify_by_rules(detail, service_lines)
    llm_matches = (llm_classifier or NullLLMClassifier()).classify(detail, service_lines)
    all_matches = rule_matches + llm_matches

    db.execute(delete(OpportunityServiceLine).where(OpportunityServiceLine.opportunity_id == opportunity_id))
    for match in all_matches:
        db.add(
            OpportunityServiceLine(
                opportunity_id=opportunity_id,
                service_line_id=match.service_line_id,
                method=match.method,
                matched_terms=match.matched_terms,
                matched_codes=match.matched_codes,
                confidence=match.confidence,
                justification=match.justification,
            )
        )

    justification = (
        " ".join(match.justification for match in all_matches)
        if all_matches
        else "Sin coincidencias con las lineas de servicio configuradas."
    )
    return all_matches, justification
