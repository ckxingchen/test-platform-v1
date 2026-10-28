"""Agent 包增删改查和下载接口。"""

from app.modules.auth.dependencies import admin, current_user
from app.platform.web.helpers import commit_or_conflict, download_response, get_or_404
from app.platform.config.settings import settings
from app.platform.storage.minio import storage
from app.modules.objects.agent_packages.repository import count_environments_by_agent_package, get_agent_package, list_agent_packages
from app.platform.db.session import get_db
from app.modules.users.models import User
from app.modules.objects.agent_packages.schemas import AgentPackageOut
from app.shared.errors import ServiceError
from app.modules.objects.agent_packages.service import upload_agent_package
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

router = APIRouter(prefix="/objects/agents", tags=["Agent 管理"])


@router.get("", response_model=list[AgentPackageOut])
def list_packages(_: User = Depends(current_user), db: Session = Depends(get_db)):
    """按更新时间倒序返回全部 Agent 包。"""

    return list_agent_packages(db)


@router.post("", response_model=AgentPackageOut, status_code=201)
def upload_package(
    file: UploadFile = File(),
    name: str = Form(),
    os: str = Form(),
    arch: str = Form(),
    user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    """上传 Agent 包：校验 bin/ 入口后覆盖 (name, os, arch) 当前最新版本。"""

    data = file.file.read()
    try:
        item = upload_agent_package(db, data, file.filename, file.content_type, name, os, arch, user.id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    return item


@router.get("/{package_id}", response_model=AgentPackageOut)
def read_package(package_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回指定 Agent 包元数据。"""

    return get_or_404(get_agent_package(db, package_id), "Agent 包不存在")


@router.get("/{package_id}/download")
def download_package(package_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """下载 Agent 包当前文件。"""

    item = get_or_404(get_agent_package(db, package_id), "Agent 包不存在")
    data = storage.get_bytes(settings.agent_bucket, item.object_key)
    return download_response(data, item.file_name)


@router.delete("/{package_id}")
def delete_package(package_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """删除未被执行器引用的 Agent 包。"""

    item = get_or_404(get_agent_package(db, package_id), "Agent 包不存在")
    if count_environments_by_agent_package(db, item.id):
        raise HTTPException(status_code=409, detail="Agent 包已被执行器引用，不能删除")
    storage.remove(settings.agent_bucket, item.object_key)
    db.delete(item)
    with commit_or_conflict(db, "删除 Agent 包失败"):
        pass
    return {"message": "已删除"}
