from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit.service import record_audit
from ..core.database import get_session
from ..core.problem import DomainError
from .deps import current_user, require_roles
from .models import Organization, OrganizationMember, User
from .schemas import (
    OrganizationCreate,
    OrganizationMemberCreate,
    OrganizationMemberResponse,
    OrganizationResponse,
)

router = APIRouter(prefix="/organizations", tags=["identity"])


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[OrganizationResponse]:
    query = select(Organization).order_by(Organization.name)
    if user.role != "admin":
        query = query.join(OrganizationMember).where(OrganizationMember.user_id == user.id)
    return [OrganizationResponse.model_validate(item) for item in session.scalars(query)]


@router.get("/{organization_id}/members", response_model=list[OrganizationMemberResponse])
def list_organization_members(
    organization_id: uuid.UUID,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> list[OrganizationMemberResponse]:
    """Who is in this organization, and with what role.

    The write side has existed since the beginning and the read side never did, so a
    membership could be granted and then never seen again. Non-admins may only read an
    organization they belong to - the same rule the list endpoint above applies.
    """
    if session.get(Organization, organization_id) is None:
        raise DomainError("organization_not_found", "Organization was not found", status_code=404)
    if user.role != "admin":
        own = session.get(OrganizationMember, (organization_id, user.id))
        if own is None:
            raise DomainError(
                "organization_not_found",
                "Organization was not found",
                status_code=404,
            )
    rows = session.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(User.username)
    ).all()
    return [
        OrganizationMemberResponse(
            user_id=member.user_id,
            username=account.username,
            display_name=account.display_name,
            role=member.role,
        )
        for member, account in rows
    ]


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={"x-permission": "organization.create"},
)
def create_organization(
    payload: OrganizationCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_roles("admin")),
) -> OrganizationResponse:
    if session.scalar(select(Organization.id).where(Organization.name == payload.name.strip())):
        raise DomainError("organization_exists", "An organization with this name already exists", status_code=409)
    organization = Organization(name=payload.name.strip())
    session.add(organization)
    session.flush()
    session.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    record_audit(
        session,
        action="organization.create",
        entity_type="organization",
        entity_id=organization.id,
        organization_id=organization.id,
        actor_id=user.id,
    )
    return OrganizationResponse.model_validate(organization)


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationResponse,
    openapi_extra={"x-permission": "organization.members.manage"},
)
def add_organization_member(
    organization_id: uuid.UUID,
    payload: OrganizationMemberCreate,
    session: Session = Depends(get_session),
    actor: User = Depends(require_roles("admin")),
) -> OrganizationResponse:
    organization = session.get(Organization, organization_id)
    member_user = session.get(User, payload.user_id)
    if organization is None or member_user is None:
        raise DomainError("membership_resource_not_found", "Organization or user was not found", status_code=404)
    membership = session.get(OrganizationMember, (organization.id, member_user.id))
    if membership is None:
        session.add(OrganizationMember(organization_id=organization.id, user_id=member_user.id, role=payload.role))
    else:
        membership.role = payload.role
    record_audit(
        session,
        action="organization.member.upsert",
        entity_type="user",
        entity_id=member_user.id,
        organization_id=organization.id,
        actor_id=actor.id,
        payload={"role": payload.role},
    )
    return OrganizationResponse.model_validate(organization)
