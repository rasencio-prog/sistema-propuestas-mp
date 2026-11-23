"""Crea (o actualiza) la membresia del primer usuario administrador.

ADR-0003: los roles viven en nuestras tablas, nunca se auto-asignan desde el JWT. El `auth_user_id`
real se obtiene una sola vez, a mano, despues de que la persona inicia sesion por primera vez con
Supabase Auth (Studio del proyecto -> Authentication -> Users -> columna "UID").

Uso (desde backend/, con el entorno activado):
    uv run python ../scripts/seed_admin.py --auth-user-id <uuid-de-supabase> --email robinson@... \
        --full-name "Robinson Asencio" --organization "Databrain SpA" --role admin
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from sqlalchemy import select  # noqa: E402

from sp.core.db import get_session_factory  # noqa: E402
from sp.modules.organizations.models import Organization, OrganizationMember  # noqa: E402
from sp.modules.users.models import User  # noqa: E402

VALID_ROLES = {"admin", "commercial", "reviewer", "read_only"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-user-id", required=True, help="UUID de Supabase auth.users.id")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default=None)
    parser.add_argument("--organization", default="Databrain SpA")
    parser.add_argument("--role", default="admin", choices=sorted(VALID_ROLES))
    args = parser.parse_args()

    auth_user_id = uuid.UUID(args.auth_user_id)

    session = get_session_factory()()
    try:
        organization = session.scalars(
            select(Organization).where(Organization.legal_name == args.organization)
        ).one_or_none()
        if organization is None:
            print(f"No existe la organizacion '{args.organization}'. Corre 'alembic upgrade head' primero.")
            raise SystemExit(1)

        user = session.scalars(select(User).where(User.auth_user_id == auth_user_id)).one_or_none()
        if user is None:
            user = User(auth_user_id=auth_user_id, email=args.email, full_name=args.full_name)
            session.add(user)
            session.flush()
            print(f"Usuario creado: {user.id}")
        else:
            print(f"Usuario ya existia: {user.id}")

        membership = session.scalars(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization.id,
                OrganizationMember.user_id == user.id,
            )
        ).one_or_none()
        if membership is None:
            membership = OrganizationMember(
                organization_id=organization.id, user_id=user.id, role=args.role
            )
            session.add(membership)
            print(f"Membresia creada con rol '{args.role}'.")
        else:
            membership.role = args.role
            print(f"Membresia actualizada a rol '{args.role}'.")

        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
