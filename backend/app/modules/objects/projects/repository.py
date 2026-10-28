"""测试项目、文件和成员的专属查询。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.users.models import User
from app.shared.resources.models import Resource, ResourceFile, ResourceMember


def list_projects(db: Session, user: User) -> list[Resource]:
    query = select(Resource).where(Resource.resource_type == "project").order_by(Resource.updated_at.desc())
    if user.role != "admin":
        query = query.join(ResourceMember).where(ResourceMember.user_id == user.id)
    return list(db.scalars(query).all())


def list_project_files(db: Session, project_id: int) -> list[ResourceFile]:
    return list(db.scalars(select(ResourceFile).where(ResourceFile.resource_id == project_id).order_by(ResourceFile.relative_path)).all())


def list_project_members(db: Session, project_id: int) -> list[ResourceMember]:
    return list(db.scalars(select(ResourceMember).where(ResourceMember.resource_id == project_id)).all())
