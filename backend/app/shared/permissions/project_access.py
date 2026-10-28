"""测试项目成员的读写权限规则。"""

from typing import Protocol

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.shared.resources.models import ResourceMember


class UserIdentity(Protocol):
    id: int
    role: str


def ensure_project_access(db: Session, project_id: int, user: UserIdentity, write: bool = False) -> None:
    if user.role == "admin":
        return
    member = db.get(ResourceMember, (project_id, user.id))
    if not member or (write and member.role != "developer"):
        raise HTTPException(status_code=403, detail="没有项目权限")
