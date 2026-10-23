"""Authorization for the deployment's LSF account, independent of project write access."""

from __future__ import annotations

from ..core.config import get_settings
from ..core.problem import DomainError
from ..identity.models import User


def lsf_access_blocker(user: User) -> dict | None:
    settings = get_settings()
    approved = settings.lsf_submitter_user_ids
    allowed = user.id in approved if approved else settings.deployment_kind == "private" and user.role == "admin"
    if allowed:
        return None
    return {"code": "lsf_account_not_assigned",
            "message": "Your BDA account has no assigned LSF connection. A project role does not grant access to the deployment owner's cluster account."}


def require_lsf_access(user: User, backend: str) -> None:
    issue = lsf_access_blocker(user) if backend == "lsf" else None
    if issue:
        raise DomainError(issue["code"], issue["message"], status_code=403)


def lsf_target_snapshot() -> dict:
    """Persist routing and credential references, never credential values.

    Poll, collect and cancel must still address the site that accepted this job
    after the deployment switches hosts. Legacy jobs retain their old path.
    """
    settings = get_settings()
    fields = ("lsf_ssh_host", "lsf_ssh_port", "lsf_ssh_user", "lsf_remote_root", "lsf_queue",
              "lsf_staging_mode", "lsf_ssh_key_path", "lsf_ssh_password_ref", "lsf_upload_wrapper")
    return {name: getattr(settings, name) for name in fields}
