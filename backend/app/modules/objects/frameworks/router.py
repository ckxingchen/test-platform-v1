"""测试框架对象上传、查询、下载和删除接口。"""

from app.modules.auth.dependencies import admin, current_user
from app.modules.tasks.guards import ensure_no_tasks
from app.platform.web.helpers import download_response, get_or_404
from app.platform.config.settings import settings
from app.platform.storage.minio import storage
from app.shared.resources.common import remove_resource_files
from app.modules.executors.facade import environment_to_dict, list_environments_by_framework_with_owner
from app.modules.objects.frameworks.repository import count_environments_by_framework, framework_out, list_frameworks as crud_list_frameworks
from app.shared.resources.repository import get_package_file, get_resource
from app.platform.db.session import get_db
from app.modules.users.models import User
from app.shared.resources.models import Resource
from app.modules.executors.schemas import EnvironmentOut
from app.shared.resources.schemas import FrameworkOut, ResourceOut
from app.shared.errors import ServiceError
from app.modules.objects.frameworks import service as framework_service
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

router = APIRouter(prefix="/objects/frameworks", tags=["对象管理"])


@router.get("", response_model=list[FrameworkOut])
def list_frameworks(_: User = Depends(current_user), db: Session = Depends(get_db)):
    """按更新时间倒序返回测试框架对象，附带被多少执行器使用。"""

    return [framework_out(db, item) for item in crud_list_frameworks(db)]


@router.post("", response_model=ResourceOut, status_code=201)
async def upload_framework(
    artifact: UploadFile = File(...),
    name: str = Form(...),
    os: str = Form(...),
    arch: str = Form(...),
    runner_path: str = Form(...),
    user: User = Depends(admin),
    db: Session = Depends(get_db),
):
    """上传并校验测试框架，按 (名称, OS, 架构) 作为独立版本定位。"""

    data = await artifact.read()
    try:
        return framework_service.upload_framework(
            db,
            data,
            artifact.filename,
            artifact.content_type,
            name,
            os,
            arch,
            runner_path,
            user.id,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{framework_id}", response_model=ResourceOut)
def get_framework(framework_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回指定测试框架的元数据。"""

    return get_or_404(get_resource(db, framework_id, "framework"), "测试框架不存在")


@router.get("/{framework_id}/environments", response_model=list[EnvironmentOut])
def list_framework_environments(framework_id: int, _: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回使用指定测试框架的全部执行器（含框架名称化冗余字段）。"""

    framework = get_or_404(get_resource(db, framework_id, "framework"), "测试框架不存在")
    rows = list_environments_by_framework_with_owner(db, framework.id)
    return [environment_to_dict(item, framework, owner) for item, owner in rows]


@router.get("/{framework_id}/download")
def download_framework(framework_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """下载最新测试框架归档（仅管理员）。"""

    item = get_or_404(get_resource(db, framework_id, "framework"), "测试框架不存在")
    file = get_package_file(db, item.id)
    if not file:
        raise HTTPException(status_code=404, detail="归档对象不存在")
    data = storage.get_bytes(settings.framework_bucket, file.object_key)
    return download_response(data, file.relative_path)


@router.delete("/{framework_id}")
def delete_framework(framework_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """删除未被环境或任务使用的测试框架及其当前 MinIO 文件。"""

    item = get_or_404(get_resource(db, framework_id, "framework"), "测试框架不存在")
    if count_environments_by_framework(db, item.id):
        raise HTTPException(status_code=409, detail="测试框架正在被执行环境使用")
    ensure_no_tasks(db, resource_id=item.id, detail="测试框架已有任务记录，不能删除")
    remove_resource_files(db, settings.framework_bucket, item.id)
    db.delete(item)
    db.commit()
    return {"message": "已删除"}
