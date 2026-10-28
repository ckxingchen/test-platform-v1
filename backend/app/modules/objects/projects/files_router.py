"""测试项目文件上传、更新、下载和删除接口。"""

from pathlib import PurePosixPath

from app.modules.auth.dependencies import current_user
from app.modules.objects.projects.access import get_accessible_project
from app.platform.web.helpers import download_response, get_or_404
from app.platform.config.settings import settings
from app.platform.storage.minio import storage
from app.modules.objects.projects.repository import list_project_files as crud_list_project_files
from app.shared.resources.repository import get_file, get_file_by_path
from app.platform.db.base import utcnow
from app.platform.db.session import get_db
from app.modules.users.models import User
from app.shared.resources.models import Resource, ResourceFile
from app.shared.resources.schemas import ResourceFileOut
from app.shared.files.archive import read_archive, strip_archive_root
from app.shared.files.paths import validate_relative_path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

router = APIRouter(prefix="/objects/projects/{project_id}/files", tags=["对象管理"])


def _file(db: Session, project_id: int, file_id: int) -> ResourceFile:
    """读取项目文件并校验其所属项目。"""

    return get_or_404(get_file(db, project_id, file_id), "对象文件不存在")


def _save_project_file(db: Session, project: Resource, user: User, relative_path: str, data: bytes, content_type: str, conflict_policy: str) -> ResourceFile | None:
    """校验路径并将测试项目文件保存到 MinIO。"""

    try:
        relative_path = validate_relative_path(relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    item = get_file_by_path(db, project.id, relative_path)
    if item and conflict_policy == "skip":
        return None
    if item and conflict_policy == "fail":
        raise HTTPException(status_code=409, detail=f"文件已存在：{relative_path}")
    key = f"{project.name}/{relative_path}"
    stored = storage.put_bytes(settings.project_bucket, key, data, content_type)
    if item:
        item.object_version_id, item.sha256, item.size = stored.version_id, stored.sha256, stored.size
        item.updated_by, item.updated_at = user.id, utcnow()
    else:
        item = ResourceFile(resource_id=project.id, relative_path=relative_path, object_key=key, object_version_id=stored.version_id, sha256=stored.sha256, size=stored.size, updated_by=user.id)
        db.add(item)
    project.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[ResourceFileOut])
def list_project_files(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """按原相对路径返回测试项目当前文件清单。"""

    get_accessible_project(db, project_id, user)
    return crud_list_project_files(db, project_id)


@router.post("/batch")
async def upload_project_files(project_id: int, relative_paths: list[str] = Form(...), files: list[UploadFile] = File(...), conflict_policy: str = Form("replace"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """批量上传项目文件并逐项返回处理结果。"""

    project = get_accessible_project(db, project_id, user, write=True)
    if len(relative_paths) != len(files):
        raise HTTPException(status_code=422, detail="路径数量与文件数量不一致")
    if conflict_policy not in {"replace", "skip", "fail"}:
        raise HTTPException(status_code=422, detail="文件冲突策略无效")
    results = []
    for path, upload in zip(relative_paths, files):
        try:
            item = _save_project_file(db, project, user, path, await upload.read(), upload.content_type or "application/octet-stream", conflict_policy)
            results.append({"relative_path": path, "success": True, "file": ResourceFileOut.model_validate(item).model_dump(mode="json") if item else None, "skipped": item is None})
        except HTTPException as exc:
            db.rollback()
            results.append({"relative_path": path, "success": False, "error": exc.detail})
    return {"results": results}


@router.post("/archive")
async def upload_project_archive(project_id: int, artifact: UploadFile = File(...), conflict_policy: str = Form("replace"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """上传整个项目压缩包（ZIP / TAR.GZ），解压后按目录结构入库。"""

    project = get_accessible_project(db, project_id, user, write=True)
    if conflict_policy not in {"replace", "skip", "fail"}:
        raise HTTPException(status_code=422, detail="文件冲突策略无效")
    try:
        archive_files = read_archive(await artifact.read(), artifact.filename or "archive")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    raw_paths = list(archive_files.keys())
    paths = strip_archive_root(raw_paths)
    results = []
    for raw_path, path in zip(raw_paths, paths):
        try:
            item = _save_project_file(db, project, user, path, archive_files[raw_path], "application/octet-stream", conflict_policy)
            results.append({"relative_path": path, "success": True, "file": ResourceFileOut.model_validate(item).model_dump(mode="json") if item else None, "skipped": item is None})
        except HTTPException as exc:
            db.rollback()
            results.append({"relative_path": path, "success": False, "error": exc.detail})
    return {"results": results}


@router.put("/{file_id}", response_model=ResourceFileOut)
async def update_project_file(project_id: int, file_id: int, file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """在原相对路径覆盖指定项目文件。"""

    project = get_accessible_project(db, project_id, user, write=True)
    current = _file(db, project_id, file_id)
    return _save_project_file(db, project, user, current.relative_path, await file.read(), file.content_type or "application/octet-stream", "replace")


@router.get("/{file_id}/download")
def download_project_file(project_id: int, file_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """下载测试项目中的指定文件。"""

    get_accessible_project(db, project_id, user)
    item = _file(db, project_id, file_id)
    data = storage.get_bytes(settings.project_bucket, item.object_key, item.object_version_id)
    filename = PurePosixPath(item.relative_path).name
    return download_response(data, filename)


@router.delete("/{file_id}")
def delete_project_file(project_id: int, file_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """删除测试项目中的当前文件对象。"""

    get_accessible_project(db, project_id, user, write=True)
    item = _file(db, project_id, file_id)
    storage.remove(settings.project_bucket, item.object_key)
    db.delete(item)
    db.commit()
    return {"message": "已删除"}
