"""任务引用关系保护规则。"""

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.tasks.models import Task


def ensure_no_tasks(db: Session, *, resource_id: int | None = None, environment_id: int | None = None, detail: str) -> None:
    conditions = []
    if resource_id is not None:
        conditions.append(or_(Task.project_id == resource_id, Task.framework_id == resource_id))
    if environment_id is not None:
        conditions.append(Task.environment_id == environment_id)
    if conditions and db.scalar(select(Task.id).where(or_(*conditions)).limit(1)):
        raise HTTPException(status_code=409, detail=detail)
