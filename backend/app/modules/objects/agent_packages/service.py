"""Agent 包上传编排：格式校验 + 平台定位 + MinIO 覆盖上传。"""

import io
import re
import tarfile
import zipfile

from app.platform.config.settings import settings
from app.platform.storage.minio import storage
from app.modules.objects.agent_packages.facade import get_agent_package_by_platform
from app.platform.db.base import utcnow
from app.modules.objects.agent_packages.models import AgentPackage
from app.shared.errors import ServiceError
from sqlalchemy.orm import Session

ALLOWED_OS = {"linux", "windows"}
ALLOWED_ARCH = {"x86_64", "arm64"}


def _list_archive_names(data: bytes, filename: str) -> list[str]:
    """只列出归档成员名（不读内容），格式非法抛 ValueError。"""

    names: list[str] = []
    stream = io.BytesIO(data)
    if zipfile.is_zipfile(stream):
        with zipfile.ZipFile(stream) as archive:
            names = [item.filename.replace("\\", "/") for item in archive.infolist() if not item.is_dir()]
    else:
        stream.seek(0)
        try:
            with tarfile.open(fileobj=stream, mode="r:*") as archive:
                names = [item.name for item in archive.getmembers() if item.isfile()]
        except tarfile.TarError as exc:
            raise ValueError(f"不支持的压缩包格式：{filename}") from exc
    return names


def inspect_agent_package(data: bytes, filename: str | None, os_name: str) -> dict:
    """校验 Agent 包结构：必须包含 bin/kw-agent（Linux）或 bin/kw-agent.exe（Windows）。

    返回包内 bin 目录文件清单等元信息。
    """

    try:
        names = _list_archive_names(data, filename or "agent")
    except ValueError as exc:
        raise ServiceError(422, str(exc))
    if not names:
        raise ServiceError(422, "压缩包为空")
    expected = "bin/kw-agent.exe" if os_name == "windows" else "bin/kw-agent"
    candidates = {name.strip("/") for name in names}
    if expected not in candidates:
        raise ServiceError(422, f"Agent 包缺少入口文件 {expected}（包内需包含 bin/ 目录）")
    return {"file_count": len(names), "entry": expected}


def upload_agent_package(
    db: Session,
    data: bytes,
    filename: str | None,
    content_type: str | None,
    name: str,
    os_name: str,
    arch: str,
    user_id: int,
) -> AgentPackage:
    """上传并校验 Agent 包，按 (名称, OS, 架构) 覆盖当前最新版本。"""

    os_name = (os_name or "").strip().lower()
    arch = (arch or "").strip().lower()
    name = (name or "").strip()
    if os_name not in ALLOWED_OS:
        raise ServiceError(422, f"操作系统取值无效：{os_name}")
    if arch not in ALLOWED_ARCH:
        raise ServiceError(422, f"CPU 架构取值无效：{arch}")
    if not name:
        raise ServiceError(422, "请填写 Agent 名称")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        raise ServiceError(422, "Agent 名称只能包含字母、数字、点、横线和下划线")
    inspect = inspect_agent_package(data, filename, os_name)

    # 先查已有记录；这里不能提前 flush，否则 INSERT 会在 file_name/object_key/sha256 赋值前触发非空约束报错。
    item = (
        db.query(AgentPackage)
        .filter(AgentPackage.name == name, AgentPackage.os == os_name, AgentPackage.arch == arch)
        .one_or_none()
    )

    lower = (filename or "").lower()
    suffix = ".tar.gz" if lower.endswith((".tar.gz", ".tgz")) else ".zip"
    object_name = "agent" + suffix
    key = f"{name}/{os_name}-{arch}/{object_name}"
    stored = storage.put_bytes(settings.agent_bucket, key, data, content_type or "application/octet-stream")

    if not item:
        item = AgentPackage(name=name, os=os_name, arch=arch)
    elif item.object_key and item.object_key != key:
        # 覆盖旧版本且存储路径不同，先删旧对象
        storage.remove(settings.agent_bucket, item.object_key)

    item.file_name = filename or object_name
    item.object_key = key
    item.sha256 = stored.sha256
    item.size = stored.size
    item.enabled = True
    item.updated_at = utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
