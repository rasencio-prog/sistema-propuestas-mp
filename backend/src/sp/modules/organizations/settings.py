"""Lectura de `organizations.settings` (jsonb libre, docs/03 S1): claves anidadas por punto, p. ej.
`radar.rate_limit_seconds`. Nunca falla si falta la clave: devuelve el default del llamador."""

from __future__ import annotations

from typing import Any

from sp.modules.organizations.models import Organization


def get_org_setting(organization: Organization, dotted_key: str, default: Any) -> Any:
    node: Any = organization.settings or {}
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
