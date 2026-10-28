"""测试框架版本及执行器反向索引查询。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.executors.models import Environment
from app.platform.db.serialization import model_to_dict
from app.shared.resources.models import Resource, ResourceFile
from app.shared.resources.repository import get_package_file, get_resource


def get_framework_by_version(db: Session, name: str, os: str, arch: str) -> Resource | None:
    return db.scalar(select(Resource).where(Resource.resource_type == "framework", Resource.name == name, Resource.os == os, Resource.arch == arch))


def get_enabled_framework_with_file(db: Session, resource_id: int) -> tuple[Resource | None, ResourceFile | None]:
    resource = get_resource(db, resource_id, "framework")
    if not resource or not resource.enabled:
        return None, None
    return resource, get_package_file(db, resource.id)


def count_environments_by_framework(db: Session, framework_id: int) -> int:
    return db.scalar(select(func.count(Environment.id)).where(Environment.framework_id == framework_id)) or 0


def list_environments_by_framework(db: Session, framework_id: int) -> list[Environment]:
    return list(db.scalars(select(Environment).where(Environment.framework_id == framework_id).order_by(Environment.id)).all())


def list_frameworks(db: Session) -> list[Resource]:
    return list(db.scalars(select(Resource).where(Resource.resource_type == "framework").order_by(Resource.updated_at.desc())).all())


def framework_out(db: Session, item: Resource) -> dict:
    return model_to_dict(item, extra={"used_by_count": count_environments_by_framework(db, item.id)})
