"""测试框架上传编排：校验 + 包检视 + 版本定位 + 文件 upsert。"""

import re

from app.platform.config.settings import settings
from app.platform.storage.minio import storage
from app.modules.objects.frameworks.repository import get_framework_by_version
from app.shared.resources.repository import get_package_file
from app.platform.db.base import utcnow
from app.shared.resources.models import Resource, ResourceFile
from app.shared.errors import ServiceError
from app.modules.objects.frameworks.package import inspect_framework_package
from sqlalchemy.orm import Session

# 允许的操作系统与 CPU 架构取值（与前端下拉一致，弹窗选择为准）
ALLOWED_OS = {"linux", "windows"}
ALLOWED_ARCH = {"x86_64", "arm64"}


def upload_framework(
    db: Session,
    data: bytes,
    filename: str | None,
    content_type: str | None,
    name: str,
    os: str,
    arch: str,
    runner_path: str,
    user_id: int,
) -> Resource:
    """上传并校验测试框架，按 (名称, OS, 架构) 作为独立版本定位。"""

    os = (os or "").strip().lower()
    arch = (arch or "").strip().lower()
    name = (name or "").strip()
    if os not in ALLOWED_OS:
        raise ServiceError(422, f"操作系统取值无效：{os}")
    if arch not in ALLOWED_ARCH:
        raise ServiceError(422, f"CPU 架构取值无效：{arch}")
    if not name:
        raise ServiceError(422, "请填写框架名称")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise ServiceError(422, "框架名称只能包含字母、数字、点、横线和下划线")

    try:
        metadata = inspect_framework_package(data, filename or "framework", runner_path)
    except ValueError as exc:
        raise ServiceError(422, str(exc))
    metadata["name"] = name
    metadata["os"] = os
    metadata["arch"] = arch

    item = get_framework_by_version(db, name, os, arch)
    if not item:
        item = Resource(resource_type="framework", name=name, os=os, arch=arch, metadata_json=metadata, created_by=user_id)
        db.add(item)
        db.flush()

    suffix = ".tar.gz" if (filename or "").lower().endswith((".tar.gz", ".tgz")) else ".zip"
    object_name = "framework" + suffix
    key = f"{name}/{os}-{arch}/{object_name}"
    stored = storage.put_bytes(settings.framework_bucket, key, data, content_type or "application/octet-stream")
    current = get_package_file(db, item.id)
    if current:
        if current.object_key != key:
            storage.remove(settings.framework_bucket, current.object_key)
        current.relative_path, current.object_key = object_name, key
        current.object_version_id, current.sha256, current.size = stored.version_id, stored.sha256, stored.size
        current.updated_by, current.updated_at = user_id, utcnow()
    else:
        db.add(
            ResourceFile(
                resource_id=item.id,
                relative_path=object_name,
                object_key=key,
                object_version_id=stored.version_id,
                sha256=stored.sha256,
                size=stored.size,
                updated_by=user_id,
            )
        )
    item.metadata_json = metadata
    item.enabled = True
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    return item
