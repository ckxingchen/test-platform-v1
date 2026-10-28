"""对象资源和资源文件基础数据库查询。"""

from app.shared.resources.models import Resource, ResourceFile
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_resource(db: Session, resource_id: int, resource_type: str | None = None) -> Resource | None:
    """按编号读取资源，并可选校验资源类型。"""

    item = db.get(Resource, resource_id)
    if not item or (resource_type and item.resource_type != resource_type):
        return None
    return item


def get_file(db: Session, resource_id: int, file_id: int) -> ResourceFile | None:
    """读取指定资源下的文件。"""

    item = db.get(ResourceFile, file_id)
    return item if item and item.resource_id == resource_id else None


def get_file_by_path(db: Session, resource_id: int, relative_path: str) -> ResourceFile | None:
    """按资源编号与相对路径读取文件。"""

    return db.scalar(
        select(ResourceFile).where(
            ResourceFile.resource_id == resource_id,
            ResourceFile.relative_path == relative_path,
        )
    )


def get_package_file(db: Session, resource_id: int) -> ResourceFile | None:
    """读取资源的首个归档文件。"""

    return db.scalar(select(ResourceFile).where(ResourceFile.resource_id == resource_id).limit(1))


def list_resource_files(db: Session, resource_id: int) -> list[ResourceFile]:
    """返回指定资源的全部文件（不排序，用于任务快照冻结）。"""

    return db.scalars(select(ResourceFile).where(ResourceFile.resource_id == resource_id)).all()
