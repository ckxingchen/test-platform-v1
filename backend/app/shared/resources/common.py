"""数据访问层公共件：模型转字典与资源文件清理。

本模块不 import fastapi，保持可独立单测。
"""

from app.platform.db.serialization import model_to_dict
from app.platform.storage.minio import storage
from app.shared.resources.models import ResourceFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session


def remove_resource_files(db: Session, bucket: str, resource_id: int) -> None:
    """删除资源全部 MinIO 对象及其 ResourceFile 记录（不 commit）。"""

    files = db.scalars(select(ResourceFile).where(ResourceFile.resource_id == resource_id)).all()
    for file in files:
        storage.remove(bucket, file.object_key)
    db.execute(delete(ResourceFile).where(ResourceFile.resource_id == resource_id))
