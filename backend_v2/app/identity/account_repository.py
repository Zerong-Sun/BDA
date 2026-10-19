from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.orm import Session

from .models import AccountGrant, RefreshSession, User


class AccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def username_taken(self, username: str) -> bool:
        return (
            self.session.scalar(select(User.id).where(func.lower(User.username) == username.lower()).limit(1))
            is not None
        )

    def locked_user(self, user_id: uuid.UUID) -> User | None:
        return self.session.scalar(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )

    def grant_by_hash(self, digest: str) -> AccountGrant | None:
        return self.session.scalar(
            select(AccountGrant)
            .where(AccountGrant.token_hash == digest)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def locked_grant(self, grant_id: uuid.UUID) -> AccountGrant | None:
        return self.session.scalar(
            select(AccountGrant)
            .where(AccountGrant.id == grant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def grants(self, cursor: tuple[datetime, uuid.UUID] | None, limit: int, realm: str) -> list[AccountGrant]:
        query = (
            select(AccountGrant)
            .where(AccountGrant.realm == realm)
            .order_by(AccountGrant.created_at.desc(), AccountGrant.id.desc())
        )
        if cursor:
            query = query.where(tuple_(AccountGrant.created_at, AccountGrant.id) < cursor)
        return list(self.session.scalars(query.limit(limit)))

    def revoke_sessions(self, user_id: uuid.UUID, now: datetime) -> None:
        self.session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def revoke_family(self, family_id: uuid.UUID, now: datetime) -> None:
        self.session.execute(
            update(RefreshSession)
            .where(RefreshSession.family_id == family_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
