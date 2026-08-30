from sqlalchemy.orm import Session

from ..identity.models import User
from ..platform.models import Operation
from ..platform.operations import enqueue_operation
from ..projects.models import Project
from .models import LigandImport
from .schemas import LigandImportCreate


def create_import(
    session: Session, project: Project, payload: LigandImportCreate, user: User
) -> tuple[LigandImport, Operation]:
    values = payload.model_dump(exclude={"metadata"})
    row = LigandImport(project_id=project.id, created_by=user.id, metadata_json=payload.metadata, **values)
    session.add(row)
    session.flush()
    operation = enqueue_operation(
        session,
        topic="ligand.import",
        resource_type="ligand_import",
        resource_id=row.id,
        project_id=project.id,
        organization_id=project.organization_id,
        user=user,
        payload={"ligand_import_id": str(row.id)},
    )
    return row, operation
