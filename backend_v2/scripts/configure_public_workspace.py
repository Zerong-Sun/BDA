"""Provision a passwordless reader for one explicitly published organization."""

from __future__ import annotations

import argparse
import uuid

from backend_v2.app.core.config import get_settings
from backend_v2.app.core.database import session_scope
from backend_v2.app.identity.models import Organization, OrganizationMember, User
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enable anonymous reading of all projects in a publishing organization"
    )
    parser.add_argument("--organization-id", type=uuid.UUID, required=True)
    args = parser.parse_args()
    if get_settings().deployment_kind != "public":
        parser.error("Run this command only against the Public deployment")
    with session_scope() as session:
        if session.get(Organization, args.organization_id) is None:
            parser.error("Publishing organization does not exist")
        username = "public-reader-" + args.organization_id.hex
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(username=username, display_name="Public visitor", role="viewer", password_hash=None)
            session.add(user)
            session.flush()
            session.add(OrganizationMember(organization_id=args.organization_id, user_id=user.id, role="viewer"))
            session.flush()
        memberships = list(session.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id)))
        if (
            user.role != "viewer"
            or not user.enabled
            or user.password_hash
            or user.oidc_subject
            or user.oidc_issuer
            or len(memberships) != 1
            or memberships[0].organization_id != args.organization_id
            or memberships[0].role != "viewer"
        ):
            parser.error("Existing reader is unsafe; no permissions were changed")
        user_id = user.id
    print(f"BDA_V2_PUBLIC_WORKSPACE_USER_ID={user_id}")
    print(f"BDA_V2_PUBLIC_WORKSPACE_ORGANIZATION_ID={args.organization_id}")


if __name__ == "__main__":
    main()
