from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import RefreshSession, User


class IdentityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def user_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username, User.enabled.is_(True)))

    def user_by_username_any_status(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def user_by_oidc(self, issuer: str, subject: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.oidc_issuer == issuer, User.oidc_subject == subject, User.enabled.is_(True))
        )

    def add_refresh_session(self, item: RefreshSession) -> None:
        self.session.add(item)

    def active_refresh_session(self, token_hash: str, now: datetime) -> RefreshSession | None:
        return self.session.scalar(
            select(RefreshSession).where(
                RefreshSession.token_hash == token_hash,
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > now,
            )
        )
