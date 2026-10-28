"""测试项目对象创建、查询和删除接口。"""

from app.modules.auth.dependencies import admin, current_user
from app.modules.objects.projects.access import get_accessible_project
from app.modules.tasks.guards import ensure_no_tasks
from app.platform.web.helpers import commit_or_conflict, get_or_404
from app.platform.config.settings import settings
from app.shared.resources.common import remove_resource_files
from app.modules.objects.projects.repository import list_projects as crud_list_projects
from app.shared.resources.repository import get_resource
from app.modules.tasks.facade import list_tasks_with_names
from app.platform.db.session import get_db
from app.modules.users.models import User
from app.shared.resources.models import Resource, ResourceMember
from app.modules.tasks.schemas import TaskOut
from app.shared.resources.schemas import ResourceCreate, ResourceOut
from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

router = APIRouter(prefix="/objects/projects", tags=["对象管理"])



@router.get("", response_model=list[ResourceOut])
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回当前用户有权访问的测试项目。"""

    return crud_list_projects(db, user)


@router.post("", response_model=ResourceOut, status_code=201)
def create_project(data: ResourceCreate, user: User = Depends(admin), db: Session = Depends(get_db)):
    """创建一个以原目录结构保存文件的测试项目对象。"""

    item = Resource(resource_type="project", name=data.name, metadata_json={}, created_by=user.id)
    db.add(item)
    with commit_or_conflict(db, "测试项目名称已存在"):
        pass
    db.refresh(item)
    return item


@router.get("/{project_id}", response_model=ResourceOut)
def get_project(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回指定测试项目的元数据。"""

    return get_accessible_project(db, project_id, user)


@router.get("/{project_id}/tasks", response_model=list[TaskOut])
def list_project_tasks(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """返回指定测试项目的全部任务（含名称化冗余，按项目权限过滤）。"""

    item = get_accessible_project(db, project_id, user)
    return list_tasks_with_names(db, project_id=item.id)


@router.delete("/{project_id}")
def delete_project(project_id: int, _: User = Depends(admin), db: Session = Depends(get_db)):
    """删除尚无任务记录的测试项目及其当前 MinIO 文件。"""

    item = get_or_404(get_resource(db, project_id, "project"), "测试项目不存在")
    ensure_no_tasks(db, resource_id=item.id, detail="测试项目已有任务记录，不能删除")
    remove_resource_files(db, settings.project_bucket, item.id)
    db.execute(delete(ResourceMember).where(ResourceMember.resource_id == item.id))
    db.delete(item)
    db.commit()
    return {"message": "已删除"}
